"""Part 8 — metric theo query + gộp overall / by_slice, và paired bootstrap để so hai arm.

Định nghĩa theo spec Part 8 (k = metrics.k, mọi ngưỡng ở config `metrics`):
- recall@k   = |{d ∈ top-k : rel(d) ≥ recall_relevant_min}| / |{d : rel(d) ≥ recall_relevant_min}|
- ndcg@k     = DCG/IDCG, gain 2^rel − 1, sản phẩm chưa gán nhãn = 0
- mrr@k      = 1/rank của kết quả đầu tiên có rel ≥ mrr_relevant_min, 0 nếu không có trong top-k
- judged@k   = tỷ lệ kết quả trong top-k đã có nhãn
- constraint_precision = trên query có filter: tỷ lệ kết quả thoả filter (evaluator pandas `store/filters.mask`);
  filter chấm = `filter` cấp parent của gold + phần `child_filter` chấm được trên items (giá lte/lt → unit_price_min)
- filter_recall_loss   = số cặp (qid, product) có rel ≥ 1 bị filter cứng của arm loại
- parent_dup_rate      = trung bình số kết quả vượt 1 cùng `parent_product_id` trong top-k
- zero_result_in_catalog / out_of_catalog, hub_score_max
Query không xác định được một metric (vd không có sản phẩm liên quan) bị loại khỏi trung bình metric đó và được đếm
riêng — không tính là 0.

Phase A (05/10, kiến trúc search OTA §4–§6; gold v4 chưa chốt tên trường → `MetricsConfig.gold_fields`):
- forbidden_hits / forbidden_n  = trong top-k, số kết quả khớp `forbidden_filter` (AST, evaluator pandas) HOẶC nằm trong danh
  sách `forbidden`; None/None khi câu không có hai thứ đó. Gộp: `forbidden_at_10` (micro) và `forbidden_query_rate`.
- direction_ok      = 1/0, chỉ khi câu có `origin` / `destination_city`: mọi kết quả `flight_route` trong top-k phải đúng
  chiều (so sau `fold`); None khi câu không nêu chiều HOẶC top-k không có `flight_route` nào (không có gì để chấm —
  không tính là đúng rỗng). Gộp: `direction_accuracy`.
- filter_pass_ok / filter_pass_n = kết quả top-k thoả filter cứng arm đã áp (`applied_filter`); None khi arm không lọc.
- parse_ok          = {trường: đúng/sai} so `diagnostics.queryPlan` của arm APP với `expected_parse` của gold (chuỗi so sau
  `fold`); None khi gold không có `expected_parse` hoặc arm không phát queryPlan. Gộp: `parse_accuracy` {trường: tỷ lệ}.
Mọi cột cũ giữ nguyên giá trị; dòng per_query cũ (không có cột mới) vẫn gộp ra cùng số recall / ndcg.

Paired bootstrap: Δ = (B − A) × 100 (điểm phần trăm) trên các qid cả hai arm đều xác định; p một phía = P(Δ* < 0)
+ ½·P(Δ* = 0) (mid-p) để một arm so với chính nó cho p = 0,5 đúng như spec.
"""
from __future__ import annotations

import json
import math
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np
import pandas as pd
import yaml

from evaluation.vector_bench.lexical import fold

from .config import DEFAULT_GOLD_FIELDS, MetricsConfig, WinRule
from .store import filters as F


class MetricsError(ValueError):
    pass


# ------------------------------------------------------------------ gold
@dataclass
class GoldQuery:
    qid: str
    text: str
    slice: str
    judgments: dict[str, int]
    filter: dict | None = None               # AST chấm constraint precision (amenity có thể là khoá) — `constraint_filter`
    expected_no_result: bool = False
    status: str = "active"
    child_filter: dict | None = None         # nguyên văn gold.jsonl (điều kiện cấp room / chuyến bay)
    # Phase A (05/10) — trường gold v4, đọc qua `MetricsConfig.gold_fields`; `forbidden_filter` có thể do
    # `forbidden_overrides` gắn khi gold không có (gold thắng).
    forbidden_filter: dict | None = None     # AST (khoá amenity / features chuỗi): kết quả KHÔNG được xuất hiện trong top-k
    forbidden: tuple[str, ...] = ()          # product_id cấm tường minh
    origin: str | None = None                # chiều bay kỳ vọng — attributes.originCity của catalog
    destination_city: str | None = None      # attributes.destinationCity
    expected_parse: dict | None = None       # {taxonomy, destination, origin, destination_city, must_not, price_max, price_min, star_min}
    family: str | None = None                # họ câu (chẩn đoán, không vào metric)

    @property
    def has_forbidden(self) -> bool:
        return self.forbidden_filter is not None or bool(self.forbidden)


#: trường của `expected_parse` được so với queryPlan (thiếu trường nào trong gold thì không so trường đó)
PARSE_FIELDS = ("taxonomy", "destination", "origin", "destination_city", "must_not", "price_max", "price_min", "star_min")

CHILD_TO_ITEMS = {"unit_price": "unit_price_min"}      # child_filter (gold_schema) → cột items.parquet


def _conjuncts(node: dict | None) -> list[dict]:
    if not node:
        return []
    return list(node["and"]) if next(iter(node)) == "and" else [node]


def constraint_filter(flt: dict | None, child_filter: dict | None) -> dict | None:
    """`filter` cấp parent + điều kiện child chấm được trên items: `unit_price ≤ X` (có phòng giá ≤ X) tương đương
    `unit_price_min ≤ X`. `max_occupancy`, `departure_date` và `gte` trên giá không có cột tương ứng → bỏ qua."""
    extra = []
    for n in _conjuncts(child_filter):
        (op, arg), = n.items()
        if op in ("lte", "lt") and isinstance(arg, list) and arg and arg[0] in CHILD_TO_ITEMS:
            extra.append({op: [CHILD_TO_ITEMS[arg[0]], arg[1]]})
    parts = _conjuncts(flt) + extra
    return None if not parts else parts[0] if len(parts) == 1 else {"and": parts}


def _opt_str(v: Any) -> str | None:
    return v.strip() if isinstance(v, str) and v.strip() else None


def _phase_a_fields(r: dict, names: Mapping[str, str], where: str) -> dict:
    """Trường gold v4 của một bản ghi (tên theo `names`); kiểu sai hoặc khoá `expected_parse` ngoài `PARSE_FIELDS` → MetricsError."""
    fb = r.get(names["forbidden_filter"]) or None
    if fb is not None:
        try:
            F.validate(fb)
        except F.FilterError as e:
            raise MetricsError(f"{where}: {names['forbidden_filter']}: {e}") from None
    forb = r.get(names["forbidden"]) or []
    if not isinstance(forb, list) or not all(isinstance(x, str) for x in forb):
        raise MetricsError(f"{where}: {names['forbidden']} phải là danh sách product_id")
    ep = r.get(names["expected_parse"]) or None
    if ep is not None:
        if not isinstance(ep, dict):
            raise MetricsError(f"{where}: {names['expected_parse']} phải là object")
        unknown = sorted(str(k) for k in ep if k not in PARSE_FIELDS)
        if unknown:     # khoá gõ sai (vd price_maximum) sẽ không bao giờ được so → báo thay vì lặng lẽ bỏ qua
            raise MetricsError(f"{where}: {names['expected_parse']} có khoá lạ {unknown} (chỉ nhận {', '.join(PARSE_FIELDS)})")
    return {"forbidden_filter": fb, "forbidden": tuple(forb), "origin": _opt_str(r.get(names["origin"])),
            "destination_city": _opt_str(r.get(names["destination_city"])), "expected_parse": ep,
            "family": _opt_str(r.get(names["family"]))}


def load_gold(path: Path, *, include_retired: bool = False, gold_fields: Mapping[str, str] | None = None) -> list[GoldQuery]:
    """gold.jsonl (spec Part 5); mặc định bỏ query `retired` (Part 11). `gold_fields`: tên trường Phase A trong file →
    tên nội bộ (mặc định `DEFAULT_GOLD_FIELDS`); khoá lạ trong bản ghi được bỏ qua."""
    names = {**DEFAULT_GOLD_FIELDS, **(gold_fields or {})}
    out = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            r = json.loads(line)
            j = {str(k): int(v) for k, v in (r.get("judgments") or {}).items()}
        except (json.JSONDecodeError, TypeError, ValueError) as e:
            raise MetricsError(f"{path.name}:{lineno}: {e}") from None
        bad = [k for k, v in j.items() if v not in (0, 1, 2)]
        if bad:
            raise MetricsError(f"{path.name}:{lineno}: nhãn phải là 0/1/2 ({bad[:3]})")
        child = r.get("child_filter") or None
        gq = GoldQuery(qid=r["qid"], text=r.get("text", ""), slice=r["slice"], judgments=j,
                       filter=constraint_filter(r.get("filter") or None, child),
                       expected_no_result=bool(r.get("expected_no_result", False)), status=r.get("status", "active"),
                       child_filter=child, **_phase_a_fields(r, names, f"{path.name}:{lineno}"))
        if include_retired or gq.status == "active":
            out.append(gq)
    return out


def load_forbidden_overrides(path: Path) -> dict[str, dict]:
    """`config/forbidden_v3.yaml`: {qid: AST} chẩn đoán cho gold chưa có trường `forbidden`. File không có → {}."""
    if not path.exists():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise MetricsError(f"{path}: phải là mapping qid → filter AST")
    out: dict[str, dict] = {}
    for qid, node in raw.items():
        try:
            F.validate(node)
        except F.FilterError as e:
            raise MetricsError(f"{path.name}: {qid}: {e}") from None
        out[str(qid)] = node
    return out


def apply_forbidden_overrides(gold: list[GoldQuery], overrides: Mapping[str, dict]) -> int:
    """Gắn `forbidden_filter` từ overrides cho câu CHƯA có spec cấm nào — không `forbidden_filter` lẫn danh sách `forbidden`
    (gold thắng: câu đã liệt kê product_id cấm tường minh không nhận thêm filter chẩn đoán); trả số câu được gắn."""
    n = 0
    for g in gold:
        if not g.has_forbidden and g.qid in overrides:
            g.forbidden_filter = overrides[g.qid]
            n += 1
    return n


# ------------------------------------------------------------------ metric theo query
def recall_at_k(top_ids: list[str], judgments: dict[str, int], k: int, rel_min: int) -> float | None:
    relevant = {p for p, r in judgments.items() if r >= rel_min}
    if not relevant:
        return None
    return len(relevant & set(top_ids[:k])) / len(relevant)


def ndcg_at_k(top_ids: list[str], judgments: dict[str, int], k: int) -> float | None:
    ideal = sorted((r for r in judgments.values() if r > 0), reverse=True)[:k]
    idcg = sum((2 ** r - 1) / math.log2(i + 2) for i, r in enumerate(ideal))
    if idcg == 0:
        return None
    dcg = sum((2 ** judgments.get(p, 0) - 1) / math.log2(i + 2) for i, p in enumerate(top_ids[:k]))
    return dcg / idcg


def mrr_at_k(top_ids: list[str], judgments: dict[str, int], k: int, rel_min: int) -> float | None:
    if not any(r >= rel_min for r in judgments.values()):
        return None
    for i, p in enumerate(top_ids[:k], 1):
        if judgments.get(p, 0) >= rel_min:
            return 1.0 / i
    return 0.0


def judged_at_k(top_ids: list[str], judgments: dict[str, int], k: int) -> float | None:
    top = top_ids[:k]
    if not top:
        return None
    return sum(1 for p in top if p in judgments) / len(top)


def ranks_of_relevant(top_ids: list[str], judgments: dict[str, int], k: int, rel_min: int) -> list[int]:
    return [i for i, p in enumerate(top_ids[:k], 1) if judgments.get(p, 0) >= rel_min]


def dup_parent_count(top_ids: list[str], parent_of: dict[str, str | None], k: int) -> int:
    """Số kết quả vượt 1 cùng một cha trong top-k. Không có cha (None / NaN từ parquet / chuỗi rỗng) thì không tính."""
    c = Counter(parent_of.get(p) for p in top_ids[:k])
    return sum(n - 1 for par, n in c.items() if isinstance(par, str) and par)


def constraint_hits(top_ids: list[str], resolved_filter: dict | None, items: pd.DataFrame, k: int) -> tuple[int, int]:
    """(số kết quả thoả filter, số kết quả) trong top-k; `items` đánh index theo product_id."""
    top = top_ids[:k]
    if resolved_filter is None or not top:
        return 0, 0
    missing = [p for p in top if p not in items.index]
    if missing:
        raise MetricsError(f"{len(missing)} product_id không có trong items, ví dụ {missing[:3]}")
    return int(F.mask(resolved_filter, items.loc[top]).sum()), len(top)


def filter_recall_loss(judgments: dict[str, int], applied_filter: dict | None, items: pd.DataFrame, rel_min: int) -> int:
    """Số sản phẩm có rel ≥ rel_min mà filter cứng arm áp (đã resolve) loại bỏ."""
    if applied_filter is None:
        return 0
    relevant = [p for p, r in judgments.items() if r >= rel_min and p in items.index]
    if not relevant:
        return 0
    return int((~F.mask(applied_filter, items.loc[relevant])).sum())


def _rows_of(top: list[str], items: pd.DataFrame, what: str) -> pd.DataFrame:
    missing = [p for p in top if p not in items.index]
    if missing:
        raise MetricsError(f"{what}: {len(missing)} product_id không có trong items, ví dụ {missing[:3]}")
    return items.loc[top]


def forbidden_hits(top_ids: list[str], resolved_forbidden: dict | None, forbidden_ids: Iterable[str], items: pd.DataFrame,
                   k: int) -> tuple[int | None, int | None]:
    """(số kết quả cấm, số kết quả) trong top-k: cấm = khớp `forbidden_filter` (đã resolve) HOẶC nằm trong `forbidden_ids`.
    (None, None) khi câu không có hai thứ đó; (0, 0) khi có spec mà không có kết quả."""
    banned = set(forbidden_ids or ())
    if resolved_forbidden is None and not banned:
        return None, None
    top = top_ids[:k]
    if not top:
        return 0, 0
    hit = np.array([p in banned for p in top], dtype=bool)
    if resolved_forbidden is not None:
        hit |= F.mask(resolved_forbidden, _rows_of(top, items, "forbidden_filter"))
    return int(hit.sum()), len(top)


def _same_city(a: Any, b: str) -> bool:
    return isinstance(a, str) and fold(a) == fold(b)


def direction_ok(top_ids: list[str], origin: str | None, destination_city: str | None, items: pd.DataFrame, k: int) -> int | None:
    """1 khi mọi `flight_route` trong top-k đúng chiều (origin_city = origin, destination_city = destination_city — chỉ so
    phần câu nêu; so sau `fold`), 0 khi có chặng sai; None khi câu không nêu chiều HOẶC top-k không có `flight_route` nào
    (câu không xác định cho `direction_accuracy` — không tính là 1 rỗng). Cột `origin_city` / `destination_city` là cột RAM
    `runner.load_env` gắn — thiếu thì báo lỗi rõ."""
    if not origin and not destination_city:
        return None
    top = top_ids[:k]
    if not top:
        return None
    for col in ("variant", "origin_city", "destination_city"):
        if col not in items.columns:
            raise MetricsError(f"items thiếu cột {col!r} — dựng EvalContext qua runner.load_env (cột RAM Phase A)")
    rows = _rows_of(top, items, "direction_ok")
    seen_route = False
    for variant, oc, dc in zip(rows["variant"], rows["origin_city"], rows["destination_city"]):
        if variant != "flight_route":
            continue
        seen_route = True
        if origin and not _same_city(oc, origin):
            return 0
        if destination_city and not _same_city(dc, destination_city):
            return 0
    return 1 if seen_route else None


def filter_pass(top_ids: list[str], resolved_applied: dict | None, items: pd.DataFrame, k: int) -> tuple[int | None, int | None]:
    """(số kết quả thoả filter cứng arm đã áp, số kết quả) trong top-k; (None, None) khi arm không lọc."""
    if resolved_applied is None:
        return None, None
    top = top_ids[:k]
    if not top:
        return 0, 0
    return int(F.mask(resolved_applied, _rows_of(top, items, "filter_pass")).sum()), len(top)


def plan_fields(extra: Mapping[str, Any] | None) -> dict[str, Any] | None:
    """Giá trị parse của arm APP theo `PARSE_FIELDS`, đọc từ diagnostics đã lưu (`queryPlan` contract 1.15.0; điểm đến lấy ở
    `appliedFilters.hard.destination` rồi `destinationFilter.value` vì queryPlan không khai điểm đến). None khi không có
    `queryPlan` (arm không phải APP, hoặc backend chưa phát)."""
    if not extra or not isinstance(extra.get("queryPlan"), dict):
        return None
    qp = extra["queryPlan"]
    route = qp.get("route") or {}
    hard = ((extra.get("appliedFilters") or {}).get("hard") or {})
    dest = hard.get("destination")
    if dest is None:
        dest = (extra.get("destinationFilter") or {}).get("value")
    price, star = qp.get("price") or {}, qp.get("star") or {}
    return {"taxonomy": (qp.get("taxonomy") or {}).get("value"), "destination": dest, "origin": route.get("origin"),
            "destination_city": route.get("destinationCity"),
            "must_not": sorted((qp.get("mustNot") or {}).get("amenities") or []),
            "price_max": price.get("max"), "price_min": price.get("min"), "star_min": star.get("min")}


def _canon(v: Any) -> Any:
    """Dạng so sánh của một giá trị parse: chuỗi → fold, danh sách → sắp xếp, số → float, None giữ None."""
    if isinstance(v, str):
        return fold(v)
    if isinstance(v, (list, tuple)):
        return sorted(_canon(x) for x in v)
    if isinstance(v, bool) or v is None:
        return v
    if isinstance(v, (int, float)):
        return float(v)
    return v


def parse_ok(expected: Mapping[str, Any] | None, extra: Mapping[str, Any] | None) -> dict[str, bool] | None:
    """{trường: đúng?} cho các trường của `PARSE_FIELDS` có trong `expected`; None khi thiếu expected hoặc queryPlan."""
    if not expected:
        return None
    got = plan_fields(extra)
    if got is None:
        return None
    return {f: _canon(expected[f]) == _canon(got.get(f)) for f in PARSE_FIELDS if f in expected}


def hub_scores(top_lists: Iterable[list[str]], n_items: int, depth: int) -> dict[str, float]:
    """Số lần mỗi sản phẩm lọt top-`depth` / kỳ vọng (= n_query × depth / n_items)."""
    lists = [t[:depth] for t in top_lists]
    if not lists or n_items <= 0:
        return {}
    expected = len(lists) * depth / n_items
    return {p: n / expected for p, n in Counter(p for t in lists for p in t).items()}


# ------------------------------------------------------------------ một query → một dòng per_query
@dataclass
class EvalContext:
    cfg: MetricsConfig
    items: pd.DataFrame                              # index = product_id, cột như items.parquet
    key_to_id: dict[str, int] = field(default_factory=dict)

    def resolve(self, node: dict | None) -> dict | None:
        if not node:
            return None
        F.validate(node)
        return F.resolve(node, self.key_to_id)


def evaluate_query(gq: GoldQuery, top_ids: list[str], ctx: EvalContext, *, top_scores: list[float] | None = None,
                   applied_filter: dict | None = None, extra: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Một dòng per_query. `extra`: diagnostics arm APP đã lưu (`Retrieved.extra`) — chỉ dùng cho `parse_ok`."""
    m = ctx.cfg
    k = m.k
    j = gq.judgments
    parent_of = ctx.items["parent_product_id"].to_dict() if "parent_product_id" in ctx.items else {}
    ok, n = constraint_hits(top_ids, ctx.resolve(gq.filter), ctx.items, k)
    applied = ctx.resolve(applied_filter)
    row: dict[str, Any] = {
        "qid": gq.qid, "slice": gq.slice, "expected_no_result": gq.expected_no_result,
        "top_ids": list(top_ids[:k]), "top_scores": list(top_scores[:k]) if top_scores is not None else None,
        "ranks_of_relevant": ranks_of_relevant(top_ids, j, k, m.recall_relevant_min),
        f"recall@{k}": recall_at_k(top_ids, j, k, m.recall_relevant_min),
        f"ndcg@{k}": ndcg_at_k(top_ids, j, k),
        f"mrr@{k}": mrr_at_k(top_ids, j, k, m.mrr_relevant_min),
        f"judged@{k}": judged_at_k(top_ids, j, k),
        "constraint_ok": ok, "constraint_n": n,
        "filter_recall_loss": filter_recall_loss(j, applied, ctx.items, m.recall_relevant_min),
        "n_dup_parent": dup_parent_count(top_ids, parent_of, k),
        "zero_result": len(top_ids) == 0,
    }
    for kk in m.extra_recall_k:
        row[f"recall@{kk}"] = recall_at_k(top_ids, j, kk, m.recall_relevant_min)
    # Phase A (05/10) — None khi câu / arm không định nghĩa metric đó (aggregate bỏ qua, không tính 0)
    fh, fn = forbidden_hits(top_ids, ctx.resolve(gq.forbidden_filter), gq.forbidden, ctx.items, k)
    fp_ok, fp_n = filter_pass(top_ids, applied, ctx.items, k)
    po = parse_ok(gq.expected_parse, extra)
    row.update({"forbidden_hits": fh, "forbidden_n": fn,
                "direction_ok": direction_ok(top_ids, gq.origin, gq.destination_city, ctx.items, k),
                "filter_pass_ok": fp_ok, "filter_pass_n": fp_n,
                "parse_ok": json.dumps(po, ensure_ascii=False) if po is not None else None})   # JSON để vào parquet
    return row


def add_condensed_metrics(row: dict[str, Any], gq: GoldQuery, cfg: MetricsConfig) -> dict[str, Any]:
    """Gắn metric condensed vào một dòng nhưng giữ nguyên metric full.

    Condensed evaluation bỏ các kết quả chưa có judgment rồi dồn hạng của phần còn lại. Cách này chỉ dùng để đọc
    chất lượng sau khi pool đã chạm cap; coverage từ danh sách full luôn được báo cạnh metric condensed.
    """
    k = cfg.k
    full = list(row.get("top_ids") or [])[:k]
    judged = [p for p in full if p in gq.judgments]
    row["condensed_top_ids"] = judged
    row["condensed_n"] = len(judged)
    row["full_n"] = len(full)
    row[f"condensed_recall@{k}"] = recall_at_k(judged, gq.judgments, k, cfg.recall_relevant_min)
    row[f"condensed_ndcg@{k}"] = ndcg_at_k(judged, gq.judgments, k)
    row[f"condensed_mrr@{k}"] = mrr_at_k(judged, gq.judgments, k, cfg.mrr_relevant_min)
    row[f"condensed_judged@{k}"] = judged_at_k(judged, gq.judgments, k)
    for kk in cfg.extra_recall_k:
        row[f"condensed_recall@{kk}"] = recall_at_k(judged, gq.judgments, kk, cfg.recall_relevant_min)
    return row


def condensed_view(rows: list[dict], cfg: MetricsConfig) -> list[dict]:
    """Trả view tương thích aggregate/compare_rows, dùng metric condensed và giữ field vận hành từ full."""
    names = [f"recall@{cfg.k}", f"ndcg@{cfg.k}", f"mrr@{cfg.k}", f"judged@{cfg.k}",
             *(f"recall@{kk}" for kk in cfg.extra_recall_k)]
    out = []
    for row in rows:
        missing = [name for name in names if f"condensed_{name}" not in row]
        if missing:
            raise MetricsError(f"dòng {row.get('qid', '?')} thiếu condensed metrics: {', '.join(missing)}")
        view = dict(row)
        condensed_ids = row.get("condensed_top_ids")
        view["top_ids"] = [] if condensed_ids is None else list(condensed_ids)
        for name in names:
            view[name] = row[f"condensed_{name}"]
        out.append(view)
    return out


def aggregate_condensed(rows: list[dict], cfg: MetricsConfig) -> dict:
    """Aggregate condensed kèm coverage của danh sách full để report luôn thể hiện phần bị bỏ do chưa label."""
    agg = aggregate(condensed_view(rows, cfg), cfg)
    full_n = sum(int(r.get("full_n", len(r.get("top_ids") or []))) for r in rows)
    judged_n = sum(int(r.get("condensed_n", len(r.get("condensed_top_ids") or []))) for r in rows)
    agg["mode"] = "condensed"
    agg["coverage"] = {
        "full_results": full_n,
        "judged_results": judged_n,
        "retained_ratio": (judged_n / full_n) if full_n else None,
        "empty_queries": sum(1 for r in rows if not (r.get("condensed_top_ids") or [])),
    }
    return agg


def _mean(values: Iterable[float | None]) -> tuple[float | None, int]:
    v = [x for x in values if x is not None and not (isinstance(x, float) and math.isnan(x))]
    return (float(np.mean(v)) if v else None), len(v)


def _parse_ok_of(r: dict) -> dict[str, bool] | None:
    v = r.get("parse_ok")
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    if isinstance(v, str):
        try:
            v = json.loads(v)
        except ValueError:
            return None
    return v if isinstance(v, dict) else None


def _defined(r: dict, col: str) -> bool:
    v = r.get(col)
    return v is not None and not (isinstance(v, float) and math.isnan(v))


def _micro(rows: list[dict], ok_col: str, n_col: str) -> tuple[float | None, list[dict]]:
    """(Σok / Σn trên dòng có n, các dòng đó); None khi không dòng nào định nghĩa."""
    defined = [r for r in rows if _defined(r, n_col)]
    total = sum(int(r[n_col]) for r in defined)
    return ((sum(int(r[ok_col]) for r in defined) / total) if total else None), defined


def phase_a_aggregate(rows: list[dict]) -> dict[str, Any]:
    """forbidden_at_10, forbidden_query_rate, direction_accuracy, filter_pass_rate, parse_accuracy — None-safe: None khi không
    query nào định nghĩa (dòng per_query cũ không có cột → mọi giá trị None). Tên `forbidden_at_10` cố định theo đề xuất
    guard `forbidden_at_10_max` (k của bench = 10)."""
    out: dict[str, Any] = {}
    out["forbidden_at_10"], fb = _micro(rows, "forbidden_hits", "forbidden_n")
    out["forbidden_query_rate"] = (sum(1 for r in fb if int(r["forbidden_hits"]) > 0) / len(fb)) if fb else None
    out["direction_accuracy"], _ = _mean(float(r["direction_ok"]) if _defined(r, "direction_ok") else None for r in rows)
    out["filter_pass_rate"], _ = _micro(rows, "filter_pass_ok", "filter_pass_n")
    per_field: dict[str, list[bool]] = {}
    for r in rows:
        po = _parse_ok_of(r)
        if po:
            for f, okv in po.items():
                per_field.setdefault(f, []).append(bool(okv))
    out["parse_accuracy"] = {f: sum(v) / len(v) for f, v in sorted(per_field.items())} if per_field else None
    return out


def aggregate(rows: list[dict], cfg: MetricsConfig, *, hub_score_max: float | None = None) -> dict:
    """overall + by_slice như `results.json` (spec §1.4); `n_defined` = số query mỗi metric thật sự tính."""
    k = cfg.k
    rank_metrics = [f"recall@{k}", f"ndcg@{k}", f"mrr@{k}", f"judged@{k}", *(f"recall@{kk}" for kk in cfg.extra_recall_k)]
    overall: dict[str, Any] = {}
    n_defined: dict[str, int] = {}
    for mname in rank_metrics:
        overall[mname], n_defined[mname] = _mean(r[mname] for r in rows)
    filtered = [r for r in rows if r["constraint_n"]]
    total_n = sum(r["constraint_n"] for r in filtered)
    overall["constraint_precision"] = (sum(r["constraint_ok"] for r in filtered) / total_n) if total_n else None
    overall["filter_recall_loss"] = int(sum(r["filter_recall_loss"] for r in rows))
    overall["parent_dup_rate"], _ = _mean(float(r["n_dup_parent"]) for r in rows)
    in_cat = [r for r in rows if not r["expected_no_result"]]
    ooc = [r for r in rows if r["expected_no_result"]]
    overall["zero_result_in_catalog"] = (sum(r["zero_result"] for r in in_cat) / len(in_cat)) if in_cat else None
    overall["zero_result_out_of_catalog"] = (sum(r["zero_result"] for r in ooc) / len(ooc)) if ooc else None
    overall["hub_score_max"] = hub_score_max
    overall.update(phase_a_aggregate(rows))
    by_slice: dict[str, dict] = {}
    for s in sorted({r["slice"] for r in rows}):
        rs = [r for r in rows if r["slice"] == s]
        by_slice[s] = {mname: _mean(r[mname] for r in rs)[0] for mname in rank_metrics}
        # zero-result và constraint precision theo slice (M2 cần zero-result theo slice; slice out_of_catalog thì
        # zero_result cao là đúng thiết kế — đọc cùng expected_no_result)
        by_slice[s]["zero_result"] = sum(r["zero_result"] for r in rs) / len(rs)
        cn = sum(r["constraint_n"] for r in rs)
        by_slice[s]["constraint_precision"] = (sum(r["constraint_ok"] for r in rs) / cn) if cn else None
        by_slice[s].update(phase_a_aggregate(rs))
        by_slice[s]["n"] = len(rs)
    return {"overall": overall, "by_slice": by_slice, "n_queries": len(rows), "n_defined": n_defined}


# ------------------------------------------------------------------ so hai arm
def paired_bootstrap(a: dict[str, float | None], b: dict[str, float | None], *, n_boot: int, seed: int) -> dict:
    """Δ = (b − a)·100 trên qid cả hai xác định. Trả mean, CI95 (percentile), p một phía mid-p, n cặp, n bị loại."""
    common = sorted(set(a) & set(b))
    pairs = [(a[q], b[q]) for q in common if a[q] is not None and b[q] is not None
             and not (isinstance(a[q], float) and math.isnan(a[q])) and not (isinstance(b[q], float) and math.isnan(b[q]))]
    dropped = len(set(a) | set(b)) - len(pairs)
    if not pairs:
        return {"delta": None, "ci95": [None, None], "p_one_sided": None, "n": 0, "n_dropped": dropped}
    d = np.array([(y - x) * 100.0 for x, y in pairs])
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(d), size=(n_boot, len(d)))
    means = d[idx].mean(axis=1)
    p = float((means < 0).mean() + 0.5 * (means == 0).mean())
    lo, hi = np.percentile(means, [2.5, 97.5])
    return {"delta": float(d.mean()), "ci95": [float(lo), float(hi)], "p_one_sided": p, "n": len(d), "n_dropped": dropped}


def slice_deltas(rows_a: list[dict], rows_b: list[dict], metric: str) -> dict[str, float]:
    """Δ trung bình (điểm) theo slice của metric, trên qid cả hai arm xác định."""
    a = {r["qid"]: (r["slice"], r[metric]) for r in rows_a}
    b = {r["qid"]: r[metric] for r in rows_b}
    acc: dict[str, list[float]] = {}
    for q, (s, va) in a.items():
        vb = b.get(q)
        if va is not None and vb is not None:
            acc.setdefault(s, []).append((vb - va) * 100.0)
    return {s: float(np.mean(v)) for s, v in sorted(acc.items())}


def win_verdict(recall: dict, ndcg: dict, slice_ndcg_deltas: dict[str, float], rule: WinRule) -> tuple[str, str]:
    """Kết luận cặp theo win_rule (spec Part 8): WIN nếu Δrecall ≥ min, p < p_max và không slice nào thua > max_slice_loss;
    không thì TIE nếu |Δndcg| < tie_delta_ndcg; còn lại LOSE. Chỉ để đọc report — chọn arm ở cổng dùng select() (Part 10)."""
    worst = min(slice_ndcg_deltas.items(), key=lambda kv: kv[1]) if slice_ndcg_deltas else (None, 0.0)
    if recall["delta"] is not None and recall["delta"] >= rule.min_delta_recall and recall["p_one_sided"] < rule.p_max \
            and worst[1] >= -rule.max_slice_loss:
        return "WIN", f"Δrecall {recall['delta']:+.2f}, p {recall['p_one_sided']:.3f}, slice kém nhất {worst[0]} {worst[1]:+.2f}"
    if ndcg["delta"] is not None and abs(ndcg["delta"]) < rule.tie_delta_ndcg:
        return "TIE", f"|Δndcg| {abs(ndcg['delta']):.2f} < {rule.tie_delta_ndcg}"
    return "LOSE", (f"Δrecall {recall['delta']}, p {recall['p_one_sided']}, Δndcg {ndcg['delta']}, "
                    f"slice kém nhất {worst[0]} {worst[1]:+.2f}")


def compare_rows(rows_a: list[dict], rows_b: list[dict], cfg: MetricsConfig, *, seed: int) -> dict:
    """vs_parent / `sb compare`: bootstrap Δrecall@k và Δndcg@k, Δ theo slice, kết luận win_rule."""
    k = cfg.k
    out = {}
    for mname in (f"recall@{k}", f"ndcg@{k}"):
        out[mname] = paired_bootstrap({r["qid"]: r[mname] for r in rows_a}, {r["qid"]: r[mname] for r in rows_b},
                                      n_boot=cfg.bootstrap, seed=seed)
    out["slice_delta_ndcg"] = slice_deltas(rows_a, rows_b, f"ndcg@{k}")
    out["verdict"], out["reason"] = win_verdict(out[f"recall@{k}"], out[f"ndcg@{k}"], out["slice_delta_ndcg"], cfg.win_rule)
    return out
