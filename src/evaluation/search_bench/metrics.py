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
- parse_ok          = {trường: đúng/sai} so `diagnostics.queryPlan` của arm APP với `expected_parse` của gold (dạng chuẩn theo
  trường: chuỗi `fold`, giá / số khách int, sao float, danh sách sắp xếp; None ≡ thiếu, danh sách None ≡ rỗng); None khi gold
  không có `expected_parse` hoặc arm không phát queryPlan. Gộp: `parse_accuracy` {trường: tỷ lệ}.
Mọi cột cũ giữ nguyên giá trị; dòng per_query cũ (không có cột mới) vẫn gộp ra cùng số recall / ndcg.

06/10 — nhãn theo câu và khối rubric:
- `query_annotations.yaml` (`load_annotations` / `apply_annotations`): forbidden_filter, forbidden, origin, destination_city,
  expected_parse, family theo qid cho câu gold chưa có trường đó (gold thắng). Thay `forbidden_v3.yaml` (đã xoá; định dạng
  {qid: AST} cũ vẫn đọc được qua `metrics.forbidden_overrides`).
- `block` = "v3" khi qid có trong gold.jsonl của tag `gold_v3` (rubric v3), "v4" khi thêm từ gold_v4 (rubric v4 —
  docs/spec/bench/gold-guide.md: không trộn hai rubric trong một con số mà không ghi rõ). `aggregate` thêm `by_block` (cùng
  bộ metric như by_slice), `by_family` (họ ≥ 2 câu: ndcg / recall trung bình) và `overall.family_macro_ndcg@k` (trung bình
  theo họ của trung bình trong họ; câu không có họ là một họ riêng).
- `guard_lines`: giá trị guard Phase A + PASS/FAIL theo `metrics.guards_proposed` (đề xuất, chỉ báo — `sb guards`).
- `weak_grid`: quy tắc "kết quả yếu" của hợp đồng search §3.4 trên lưới ngưỡng (`sb weak-results`).

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
    expected_parse: dict | None = None       # khoá ⊆ PARSE_FIELDS
    family: str | None = None                # họ câu: biến thể không dấu / gõ sai cùng ý định (by_family, family_macro_ndcg)
    block: str | None = None                 # "v3" | "v4": khối rubric (runner.load_env gắn — `block_of`)
    # 06/10 (người dùng chốt phương án b): variant catalog KHÔNG vi phạm loại cốt lõi của câu (query_annotations.yaml);
    # `project_rubric_v4` hạ nhãn ≥ 1 của sản phẩm ngoài danh sách về 0 lúc chấm — gold.jsonl không đổi.
    allowed_variants: tuple[str, ...] | None = None
    v4_projected: int = 0                    # số cặp bị chiếu về 0 ở câu này (per_query `v4_projected_n`)

    @property
    def has_forbidden(self) -> bool:
        return self.forbidden_filter is not None or bool(self.forbidden)


#: trường của `expected_parse` được so với queryPlan (thiếu trường nào trong gold thì không so trường đó)
PARSE_FIELDS = ("taxonomy", "destination", "origin", "destination_city", "must_not", "must_not_brands", "must_not_taxonomies",
                "price_max", "price_min", "star_min", "party_total")
#: kiểu của từng trường parse (dạng chuẩn để so — `canon_parse`)
PARSE_STR_FIELDS = ("taxonomy", "destination", "origin", "destination_city")
PARSE_LIST_FIELDS = ("must_not", "must_not_brands", "must_not_taxonomies")
PARSE_INT_FIELDS = ("price_max", "price_min", "party_total")
PARSE_FLOAT_FIELDS = ("star_min",)

#: variant của search unit (catalog.py `search_unit_variants`) — miền giá trị của `allowed_variants`
UNIT_VARIANTS = ("hotel_property", "attraction", "combo", "flight_route", "golf")

#: khối rubric (gold-guide.md "Rubric v4"): câu có trong tag gold_v3 theo rubric v3, câu thêm từ gold_v4 theo rubric v4
BLOCKS = ("v3", "v4")
RUBRIC_V3_TAG = "gold_v3"
#: dự phòng khi không đọc được tag gold_v3 qua git: qid ≤ giá trị này là câu v3 (gold_v4 bắt đầu từ c0673)
RUBRIC_V3_MAX_QID = "c0672"

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


def _check_expected_parse(ep: Any, where: str, label: str) -> dict | None:
    """`expected_parse` hợp lệ (None / {} → None): khoá ⊆ PARSE_FIELDS, giá trị đúng kiểu từng trường (null luôn được — nghĩa
    là kỳ vọng parser không ra gì). Khoá gõ sai (vd price_maximum) sẽ không bao giờ được so → báo thay vì lặng lẽ bỏ qua."""
    if ep is None or ep == {}:
        return None
    if not isinstance(ep, dict):
        raise MetricsError(f"{where}: {label} phải là object")
    unknown = sorted(str(k) for k in ep if k not in PARSE_FIELDS)
    if unknown:
        raise MetricsError(f"{where}: {label} có khoá lạ {unknown} (chỉ nhận {', '.join(PARSE_FIELDS)})")
    for f, v in ep.items():
        if v is None:
            continue
        if f in PARSE_STR_FIELDS:
            ok = isinstance(v, str)
        elif f in PARSE_LIST_FIELDS:
            ok = isinstance(v, list) and all(isinstance(x, str) for x in v)
        else:
            ok = isinstance(v, (int, float)) and not isinstance(v, bool)
        if not ok:
            raise MetricsError(f"{where}: {label}.{f} sai kiểu ({type(v).__name__}: {v!r})")
    return dict(ep)


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
    ep = _check_expected_parse(r.get(names["expected_parse"]) or None, where, names["expected_parse"])
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
    """{qid: AST} chẩn đoán cho gold chưa có trường `forbidden` (định dạng `config/forbidden_v3.yaml` của 05/10 — đã chuyển vào
    query_annotations.yaml; giữ để `metrics.forbidden_overrides` cũ còn dùng được). File không có → {}."""
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


# ------------------------------------------------------------------ nhãn theo câu (06/10, query_annotations.yaml)
ANNOTATIONS_VERSION = 1
ANNOTATION_TOP_KEYS = ("version", "annotated_by", "queries")
#: khoá của một câu trong `queries` (tên nội bộ của GoldQuery — không qua `gold_fields`)
ANNOTATION_KEYS = ("forbidden_filter", "forbidden", "origin", "destination_city", "expected_parse", "family",
                   "allowed_variants")


def load_annotations(path: Path) -> dict[str, dict]:
    """`config/query_annotations.yaml` → {qid: {khoá: giá trị}} đã kiểm (chỉ khoá có giá trị khác null; `expected_parse` giữ
    nguyên các trường null bên trong vì null ở đó là kỳ vọng). Không có file, sai version, khoá lạ (cấp file hoặc cấp câu),
    filter AST sai, `expected_parse` sai khoá / kiểu → MetricsError."""
    if not path.exists():
        raise MetricsError(f"không thấy {path} (metrics.annotations) — đặt null trong sbench.yaml nếu không dùng")
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        raise MetricsError(f"{path.name}: YAML hỏng: {e}") from None
    if not isinstance(raw, dict):
        raise MetricsError(f"{path.name}: phải là mapping {{version, annotated_by, queries}}")
    unknown = sorted(str(k) for k in raw if k not in ANNOTATION_TOP_KEYS)
    if unknown:
        raise MetricsError(f"{path.name}: khoá lạ {unknown} (chỉ nhận {', '.join(ANNOTATION_TOP_KEYS)})")
    if raw.get("version") != ANNOTATIONS_VERSION:
        raise MetricsError(f"{path.name}: version phải là {ANNOTATIONS_VERSION}, gặp {raw.get('version')!r}")
    queries = raw.get("queries") or {}
    if not isinstance(queries, dict):
        raise MetricsError(f"{path.name}: queries phải là mapping qid → {{khoá: giá trị}}")
    out: dict[str, dict] = {}
    for qid, entry in queries.items():
        where = f"{path.name}: {qid}"
        entry = entry or {}
        if not isinstance(entry, dict):
            raise MetricsError(f"{where}: phải là mapping khoá → giá trị")
        bad = sorted(str(k) for k in entry if k not in ANNOTATION_KEYS)
        if bad:
            raise MetricsError(f"{where}: khoá lạ {bad} (chỉ nhận {', '.join(ANNOTATION_KEYS)})")
        a: dict[str, Any] = {}
        if entry.get("forbidden_filter") is not None:
            try:
                F.validate(entry["forbidden_filter"])
            except F.FilterError as e:
                raise MetricsError(f"{where}: forbidden_filter: {e}") from None
            a["forbidden_filter"] = entry["forbidden_filter"]
        if entry.get("forbidden") is not None:
            forb = entry["forbidden"]
            if not isinstance(forb, list) or not all(isinstance(x, str) for x in forb):
                raise MetricsError(f"{where}: forbidden phải là danh sách product_id")
            a["forbidden"] = tuple(forb)
        for f in ("origin", "destination_city", "family"):
            v = entry.get(f)
            if v is not None and not isinstance(v, str):
                raise MetricsError(f"{where}: {f} phải là chuỗi hoặc null")
            if _opt_str(v) is not None:
                a[f] = _opt_str(v)
        ep = _check_expected_parse(entry.get("expected_parse"), where, "expected_parse")
        if ep is not None:
            a["expected_parse"] = ep
        av = entry.get("allowed_variants")
        if av is not None:
            if not isinstance(av, list) or not av or not all(isinstance(x, str) and x in UNIT_VARIANTS for x in av):
                raise MetricsError(f"{where}: allowed_variants phải là danh sách khác rỗng gồm {', '.join(UNIT_VARIANTS)}")
            a["allowed_variants"] = tuple(dict.fromkeys(av))
        out[str(qid)] = a
    return out


def project_rubric_v4(gq: GoldQuery, variant_of: Mapping[str, str]) -> int:
    """Chiếu rubric v4 lúc chấm (gold-guide "Rubric v4", 06/10 — phương án b): nhãn ≥ 1 của sản phẩm có variant ngoài
    `allowed_variants` của câu → 0 (sai loại cốt lõi là ràng buộc cứng). Sản phẩm không có trong `variant_of` giữ nguyên.
    Sửa `gq.judgments` tại chỗ, ghi `gq.v4_projected`; trả số cặp đổi. Câu không có `allowed_variants` → 0."""
    if not gq.allowed_variants:
        gq.v4_projected = 0
        return 0
    n = 0
    for pid, lab in gq.judgments.items():
        v = variant_of.get(pid)
        if lab >= 1 and v is not None and v not in gq.allowed_variants:
            gq.judgments[pid] = 0
            n += 1
    gq.v4_projected = n
    return n


def apply_annotations(gold: list[GoldQuery], annotations: Mapping[str, Mapping[str, Any]], *,
                      known_qids: Iterable[str] | None = None) -> dict[str, int]:
    """Gắn nhãn theo câu cho câu gold CHƯA có trường đó (gold thắng từng trường). Phần cấm (`forbidden_filter` + `forbidden`)
    là một khối như `apply_forbidden_overrides`: câu gold đã có một trong hai thì không nhận gì. `known_qids` (vd mọi qid
    của gold/gold.jsonl, kể cả retired) → qid lạ (gõ sai) là MetricsError; câu có trong `known_qids` nhưng không có trong
    `gold` đang chấm (fixture, gold cũ) chỉ bị bỏ qua. Trả {trường: số câu được gắn}."""
    if known_qids is not None:
        unknown = sorted(set(annotations) - set(known_qids))
        if unknown:
            raise MetricsError(f"annotations: {len(unknown)} qid không có trong gold ({', '.join(unknown[:5])}"
                               f"{' …' if len(unknown) > 5 else ''})")
    by = {g.qid: g for g in gold}
    n: Counter = Counter()
    for qid, a in annotations.items():
        g = by.get(qid)
        if g is None:
            continue
        if not g.has_forbidden and ("forbidden_filter" in a or "forbidden" in a):
            g.forbidden_filter = a.get("forbidden_filter")
            g.forbidden = tuple(a.get("forbidden") or ())
            n["forbidden"] += 1
        for f in ("origin", "destination_city", "expected_parse", "family", "allowed_variants"):
            if f in a and getattr(g, f) is None:
                setattr(g, f, a[f])
                n[f] += 1
    return dict(n)


def block_of(qid: str, v3_qids: set[str] | frozenset[str] | None) -> str:
    """Khối rubric của một câu: "v3" khi qid có trong gold_v3 (dự phòng khi không đọc được tag: qid ≤ RUBRIC_V3_MAX_QID)."""
    if v3_qids is None:
        return "v3" if qid <= RUBRIC_V3_MAX_QID else "v4"
    return "v3" if qid in v3_qids else "v4"


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


def _d(v: Any) -> dict:
    return v if isinstance(v, dict) else {}


#: khoá diagnostics theo câu mà arm APP luôn lưu vào `extra` (app_adapter 06/10) — có khoá này mà vắng `queryPlan` nghĩa là
#: backend không parse ra gì (contract: queryPlan chỉ phát khi có gì để khai)
_APP_DIAG_KEYS = ("stageMs", "filteredCount", "relevantCount")


def plan_fields(extra: Mapping[str, Any] | None) -> dict[str, Any] | None:
    """Giá trị parser của arm APP theo `PARSE_FIELDS`, đọc từ diagnostics đã lưu (`queryPlan` contract 1.15.0) — KHÔNG phụ
    thuộc cờ filter của arm (queryPlan được phát cả khi mọi cờ tắt; `appliedFilters` mới là "đã lọc gì"):
    - taxonomy        = queryPlan.taxonomy.value, chỉ khi source là "query" hoặc "param" (không thì None)
    - destination     = queryPlan.route.destinationCity khi parse ra tuyến bay (route có origin hoặc destinationCity), không thì
                        phần tử duy nhất của `derivedDestinations` (None khi 0 hoặc ≥ 2 địa danh)
    - origin / destination_city = queryPlan.route.origin / destinationCity
    - must_not / must_not_brands / must_not_taxonomies = queryPlan.mustNot.amenities / brands / taxonomies (sắp xếp; khoá
      `taxonomies` mới, có thể vắng → [])
    - price_max / price_min = queryPlan.price.max / min · star_min = queryPlan.star.min · party_total = queryPlan.party.total
      (khoá mới, có thể vắng → None)
    None khi không có `queryPlan` (arm không phải APP, hoặc backend chưa phát). Arm APP đã lưu diagnostics theo câu (khoá
    `_APP_DIAG_KEYS`, có từ 06/10) mà không có `queryPlan` = backend không parse ra gì → so như plan rỗng (mọi trường None /
    []), không bỏ câu khỏi `parse_accuracy` (trước 06/10 23/154 câu bị bỏ, làm số parse cao giả)."""
    if not extra:
        return None
    qp = extra.get("queryPlan")
    if not isinstance(qp, dict):
        if not any(k in extra for k in _APP_DIAG_KEYS):
            return None
        qp = {}
    tax = _d(qp.get("taxonomy"))
    route = _d(qp.get("route"))
    must_not = _d(qp.get("mustNot"))
    if route.get("origin") or route.get("destinationCity"):
        dest = route.get("destinationCity")
    else:
        derived = extra.get("derivedDestinations") or []
        dest = derived[0] if isinstance(derived, list) and len(derived) == 1 else None
    price, star, party = _d(qp.get("price")), _d(qp.get("star")), _d(qp.get("party"))
    return {"taxonomy": tax.get("value") if tax.get("source") in ("query", "param") else None,
            "destination": dest, "origin": route.get("origin"), "destination_city": route.get("destinationCity"),
            "must_not": sorted(must_not.get("amenities") or []), "must_not_brands": sorted(must_not.get("brands") or []),
            "must_not_taxonomies": sorted(must_not.get("taxonomies") or []),
            "price_max": price.get("max"), "price_min": price.get("min"), "star_min": star.get("min"),
            "party_total": party.get("total")}


def canon_parse(field_name: str, v: Any) -> Any:
    """Dạng so sánh của một giá trị parse theo trường: chuỗi → `fold` (chuỗi rỗng ≡ None), danh sách → sắp xếp các chuỗi đã
    fold (None ≡ []), giá / số khách → int, sao → float; None giữ None. Giá trị sai kiểu giữ nguyên (so bằng ==)."""
    if field_name in PARSE_LIST_FIELDS:
        if v is None:
            return []
        if isinstance(v, (list, tuple)):
            return sorted(fold(x) if isinstance(x, str) else x for x in v)
        return v
    if v is None:
        return None
    if field_name in PARSE_STR_FIELDS:
        return (fold(v) or None) if isinstance(v, str) else v
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return v
    if field_name in PARSE_INT_FIELDS:
        return int(round(v))
    return float(v)


def parse_ok(expected: Mapping[str, Any] | None, extra: Mapping[str, Any] | None) -> dict[str, bool] | None:
    """{trường: đúng?} cho các trường của `PARSE_FIELDS` có trong `expected` (so dạng `canon_parse`; trường parser không ra
    ≡ None); None khi thiếu expected hoặc queryPlan."""
    if not expected:
        return None
    got = plan_fields(extra)
    if got is None:
        return None
    return {f: canon_parse(f, expected[f]) == canon_parse(f, got.get(f)) for f in PARSE_FIELDS if f in expected}


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
    row.update({"block": gq.block, "family": gq.family,       # 06/10: khối rubric + họ câu (by_block / by_family)
                "v4_projected_n": gq.v4_projected})           # số cặp nhãn bị chiếu rubric v4 về 0 (runner.load_env)
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


def _constraint_precision(rows: list[dict]) -> float | None:
    filtered = [r for r in rows if r["constraint_n"]]
    total_n = sum(r["constraint_n"] for r in filtered)
    return (sum(r["constraint_ok"] for r in filtered) / total_n) if total_n else None


def _zero_rates(rows: list[dict]) -> tuple[float | None, float | None]:
    """(zero_result_in_catalog, zero_result_out_of_catalog)."""
    in_cat = [r for r in rows if not r["expected_no_result"]]
    ooc = [r for r in rows if r["expected_no_result"]]
    return ((sum(r["zero_result"] for r in in_cat) / len(in_cat)) if in_cat else None,
            (sum(r["zero_result"] for r in ooc) / len(ooc)) if ooc else None)


def _group_metrics(rs: list[dict], rank_metrics: list[str]) -> dict[str, Any]:
    """Bộ metric của một nhóm câu (slice / khối rubric)."""
    out: dict[str, Any] = {mname: _mean(r[mname] for r in rs)[0] for mname in rank_metrics}
    # zero-result và constraint precision theo nhóm (M2 cần zero-result theo slice; slice out_of_catalog thì zero_result cao là
    # đúng thiết kế — đọc cùng expected_no_result)
    out["zero_result"] = sum(r["zero_result"] for r in rs) / len(rs)
    cn = sum(r["constraint_n"] for r in rs)
    out["constraint_precision"] = (sum(r["constraint_ok"] for r in rs) / cn) if cn else None
    out.update(phase_a_aggregate(rs))
    out["n"] = len(rs)
    return out


def _key_of(r: dict, key: str) -> str | None:
    v = r.get(key)
    return v if isinstance(v, str) and v else None


def family_aggregate(rows: list[dict], k: int) -> tuple[dict[str, dict], float | None]:
    """(by_family, family_macro_ndcg@k). by_family: chỉ họ có ≥ 2 câu trong `rows` → {n, ndcg@k, recall@k, qids}. Macro: mỗi
    họ (câu không có họ, hoặc họ chỉ một câu, là một họ riêng) lấy trung bình ndcg@k các câu xác định trong họ, rồi lấy
    trung bình các họ — biến thể không dấu / gõ sai của một ý định chỉ được tính một phiếu (kiến trúc §15)."""
    groups: dict[str, list[dict]] = {}
    for r in rows:
        fam = _key_of(r, "family")
        groups.setdefault(f"family:{fam}" if fam else f"qid:{r['qid']}", []).append(r)
    by_family: dict[str, dict] = {}
    for g, rs in sorted(groups.items()):
        if g.startswith("family:") and len(rs) >= 2:
            by_family[g[len("family:"):]] = {"n": len(rs), f"ndcg@{k}": _mean(r.get(f"ndcg@{k}") for r in rs)[0],
                                             f"recall@{k}": _mean(r.get(f"recall@{k}") for r in rs)[0],
                                             "qids": sorted(r["qid"] for r in rs)}
    means = [m for m in (_mean(r.get(f"ndcg@{k}") for r in rs)[0] for rs in groups.values()) if m is not None]
    return by_family, (float(np.mean(means)) if means else None)


def aggregate(rows: list[dict], cfg: MetricsConfig, *, hub_score_max: float | None = None) -> dict:
    """overall + by_slice như `results.json` (spec §1.4); `n_defined` = số query mỗi metric thật sự tính. 06/10: `by_block`
    (khối rubric v3 / v4, cùng bộ metric như by_slice — chỉ dòng có cột `block`), `by_family` và
    `overall.family_macro_ndcg@k` (`family_aggregate`)."""
    k = cfg.k
    rank_metrics = [f"recall@{k}", f"ndcg@{k}", f"mrr@{k}", f"judged@{k}", *(f"recall@{kk}" for kk in cfg.extra_recall_k)]
    overall: dict[str, Any] = {}
    n_defined: dict[str, int] = {}
    for mname in rank_metrics:
        overall[mname], n_defined[mname] = _mean(r[mname] for r in rows)
    overall["constraint_precision"] = _constraint_precision(rows)
    overall["filter_recall_loss"] = int(sum(r["filter_recall_loss"] for r in rows))
    overall["parent_dup_rate"], _ = _mean(float(r["n_dup_parent"]) for r in rows)
    overall["zero_result_in_catalog"], overall["zero_result_out_of_catalog"] = _zero_rates(rows)
    overall["hub_score_max"] = hub_score_max
    overall.update(phase_a_aggregate(rows))
    by_family, overall[f"family_macro_ndcg@{k}"] = family_aggregate(rows, k)
    by_slice = {s: _group_metrics([r for r in rows if r["slice"] == s], rank_metrics) for s in sorted({r["slice"] for r in rows})}
    blocks = sorted({b for b in (_key_of(r, "block") for r in rows) if b})
    by_block = {b: _group_metrics([r for r in rows if _key_of(r, "block") == b], rank_metrics) for b in blocks}
    return {"overall": overall, "by_slice": by_slice, "by_block": by_block, "by_family": by_family, "n_queries": len(rows),
            "n_defined": n_defined}


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


def _num(v: Any) -> float | None:
    if v is None or isinstance(v, bool) or not isinstance(v, (int, float)) or (isinstance(v, float) and math.isnan(v)):
        return None
    return float(v)


def group_delta_stats(rows_a: list[dict], rows_b: list[dict], metric: str, key: str) -> dict[str, dict[str, Any]]:
    """Theo nhóm `key` (vd "block") của A: {nhóm: {a, b, delta, n}} — a / b = trung bình metric của từng arm trên các qid CẢ HAI
    xác định (n cặp), delta = (b − a)·100 điểm. Dòng thiếu cột `key` hoặc metric (artifact cũ) bị bỏ qua."""
    b_of = {r["qid"]: _num(r.get(metric)) for r in rows_b}
    acc: dict[str, list[tuple[float, float]]] = {}
    for r in rows_a:
        g, va, vb = _key_of(r, key), _num(r.get(metric)), b_of.get(r["qid"])
        if g is None or va is None or vb is None:
            continue
        acc.setdefault(g, []).append((va, vb))
    out = {}
    for g, pairs in sorted(acc.items()):
        a, b = float(np.mean([x for x, _ in pairs])), float(np.mean([y for _, y in pairs]))
        out[g] = {"a": a, "b": b, "delta": (b - a) * 100.0, "n": len(pairs)}
    return out


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


# ------------------------------------------------------------------ guard Phase A (06/10, `sb guards` — chỉ báo, không chặn)
#: (tên giá trị, chiều so, khoá ngưỡng trong `metrics.guards_proposed`); chiều None = chỉ báo giá trị, không có ngưỡng
GUARD_SPECS: tuple[tuple[str, str | None, str | None], ...] = (
    ("forbidden_at_10", "max", "forbidden_at_10_max"),
    ("forbidden_query_rate", None, None),
    ("direction_accuracy", "min", "direction_accuracy_min"),
    ("filter_pass_rate", "min", "filter_pass_min"),
    ("constraint_precision", "min", "constraint_precision_min"),
    ("zero_result_in_catalog", "max", "zero_result_in_catalog_max"),
    ("zero_result_out_of_catalog", None, None),
)
_GUARD_EPS = 1e-12


def guard_status(value: float | None, op: str | None, threshold: float | None) -> str:
    """PASS / FAIL theo ngưỡng (sai số 1e-12); "n/a" khi không câu nào định nghĩa giá trị; "-" khi không có ngưỡng."""
    if value is None:
        return "n/a"
    if op is None or threshold is None:
        return "-"
    ok = value <= threshold + _GUARD_EPS if op == "max" else value >= threshold - _GUARD_EPS
    return "PASS" if ok else "FAIL"


def guard_lines(rows: list[dict], proposed: Any) -> list[dict[str, Any]]:
    """Giá trị guard Phase A của một arm trên `rows` (cùng công thức với `aggregate`) kèm PASS/FAIL theo `proposed`
    (`GuardsProposed` hoặc object cùng thuộc tính): mỗi dòng {name, value, op, threshold, status, n (số câu định nghĩa),
    bad (qid làm trượt, sắp xếp)}. `parse_accuracy` tách mỗi trường một dòng `parse_accuracy.<trường>` (ngưỡng
    parse_accuracy_min). Dòng per_query cũ thiếu cột Phase A → giá trị None, status "n/a"."""
    pa = phase_a_aggregate(rows)
    zin, zooc = _zero_rates(rows)
    values = {**pa, "constraint_precision": _constraint_precision(rows), "zero_result_in_catalog": zin,
              "zero_result_out_of_catalog": zooc}
    fb = [r for r in rows if _defined(r, "forbidden_n")]
    dr = [r for r in rows if _defined(r, "direction_ok")]
    fp = [r for r in rows if _defined(r, "filter_pass_n")]
    cp = [r for r in rows if r.get("constraint_n")]
    incat = [r for r in rows if not r.get("expected_no_result")]
    support = {
        "forbidden_at_10": (fb, [r for r in fb if int(r["forbidden_hits"]) > 0]),
        "forbidden_query_rate": (fb, [r for r in fb if int(r["forbidden_hits"]) > 0]),
        "direction_accuracy": (dr, [r for r in dr if not int(r["direction_ok"])]),
        "filter_pass_rate": (fp, [r for r in fp if int(r["filter_pass_ok"]) < int(r["filter_pass_n"])]),
        "constraint_precision": (cp, [r for r in cp if int(r["constraint_ok"]) < int(r["constraint_n"])]),
        "zero_result_in_catalog": (incat, [r for r in incat if r.get("zero_result")]),
        "zero_result_out_of_catalog": ([r for r in rows if r.get("expected_no_result")],
                                       [r for r in rows if r.get("expected_no_result") and not r.get("zero_result")]),
    }
    out = []
    for name, op, key in GUARD_SPECS:
        thr = getattr(proposed, key) if (key and proposed is not None) else None
        val = values.get(name)
        n_rows, bad = support[name]
        out.append({"name": name, "value": val, "op": op, "threshold": thr, "status": guard_status(val, op, thr),
                    "n": len(n_rows), "bad": sorted(r["qid"] for r in bad)})
    per_field: dict[str, tuple[list[str], list[str]]] = {}
    for r in rows:
        po = _parse_ok_of(r)
        for f, okv in (po or {}).items():
            seen, bad = per_field.setdefault(f, ([], []))
            seen.append(r["qid"])
            if not okv:
                bad.append(r["qid"])
    thr = getattr(proposed, "parse_accuracy_min", None) if proposed is not None else None
    order = {f: i for i, f in enumerate(PARSE_FIELDS)}
    for f in sorted(per_field, key=lambda x: (order.get(x, len(order)), x)):
        seen, bad = per_field[f]
        val = (len(seen) - len(bad)) / len(seen)
        out.append({"name": f"parse_accuracy.{f}", "value": val, "op": "min", "threshold": thr,
                    "status": guard_status(val, "min", thr), "n": len(seen), "bad": sorted(bad)})
    return out


# ------------------------------------------------------------------ "kết quả yếu" (06/10, hợp đồng search §3.4, `sb weak-results`)
def is_weak(top: float | None, margin: float | None, top_min: float, margin_min: float) -> bool:
    """Quy tắc client của hợp đồng §3.4: weak khi topScore < WEAK_RESULT_TOP_SCORE HOẶC margin < WEAK_RESULT_MARGIN. Không có
    margin (thiếu vector truy vấn) → chỉ xét topScore. `top` None (results rỗng) → False: câu rỗng không phải "yếu", đếm riêng."""
    if top is None:
        return False
    return top < top_min or (margin is not None and margin < margin_min)


def weak_grid(entries: list[Mapping[str, Any]], top_grid: Iterable[float], margin_grid: Iterable[float]) -> dict[str, Any]:
    """`entries`: {qid, ooc (expected_no_result), top (topScore | None khi rỗng), margin (| None)}. Với mỗi (T, M) của lưới:
    `ooc_suppressed` = câu ngoài catalog KHÔNG hiện kết quả (rỗng HOẶC weak) — muốn cao; `in_weak` = câu trong catalog có kết
    quả nhưng bị gắn weak (báo động giả) — muốn thấp. Câu trong catalog rỗng (`n_in_empty`) không phụ thuộc ngưỡng."""
    ooc = [e for e in entries if e["ooc"]]
    inc = [e for e in entries if not e["ooc"]]
    cells = []
    for t in top_grid:
        for m in margin_grid:
            cells.append({"top": float(t), "margin": float(m),
                          "ooc_suppressed": sum(1 for e in ooc if e["top"] is None or is_weak(e["top"], e["margin"], t, m)),
                          "in_weak": sum(1 for e in inc if is_weak(e["top"], e["margin"], t, m))})
    return {"cells": cells, "n_ooc": len(ooc), "n_in": len(inc), "n_ooc_empty": sum(1 for e in ooc if e["top"] is None),
            "n_in_empty": sum(1 for e in inc if e["top"] is None),
            "n_no_margin": sum(1 for e in entries if e["top"] is not None and e["margin"] is None)}
