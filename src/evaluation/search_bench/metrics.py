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

Paired bootstrap: Δ = (B − A) × 100 (điểm phần trăm) trên các qid cả hai arm đều xác định; p một phía = P(Δ* < 0)
+ ½·P(Δ* = 0) (mid-p) để một arm so với chính nó cho p = 0,5 đúng như spec.
"""
from __future__ import annotations

import json
import math
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

from .config import MetricsConfig, WinRule
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


def load_gold(path: Path, *, include_retired: bool = False) -> list[GoldQuery]:
    """gold.jsonl (spec Part 5); mặc định bỏ query `retired` (Part 11)."""
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
                       child_filter=child)
        if include_retired or gq.status == "active":
            out.append(gq)
    return out


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
                   applied_filter: dict | None = None) -> dict[str, Any]:
    m = ctx.cfg
    k = m.k
    j = gq.judgments
    parent_of = ctx.items["parent_product_id"].to_dict() if "parent_product_id" in ctx.items else {}
    ok, n = constraint_hits(top_ids, ctx.resolve(gq.filter), ctx.items, k)
    row: dict[str, Any] = {
        "qid": gq.qid, "slice": gq.slice, "expected_no_result": gq.expected_no_result,
        "top_ids": list(top_ids[:k]), "top_scores": list(top_scores[:k]) if top_scores is not None else None,
        "ranks_of_relevant": ranks_of_relevant(top_ids, j, k, m.recall_relevant_min),
        f"recall@{k}": recall_at_k(top_ids, j, k, m.recall_relevant_min),
        f"ndcg@{k}": ndcg_at_k(top_ids, j, k),
        f"mrr@{k}": mrr_at_k(top_ids, j, k, m.mrr_relevant_min),
        f"judged@{k}": judged_at_k(top_ids, j, k),
        "constraint_ok": ok, "constraint_n": n,
        "filter_recall_loss": filter_recall_loss(j, ctx.resolve(applied_filter), ctx.items, m.recall_relevant_min),
        "n_dup_parent": dup_parent_count(top_ids, parent_of, k),
        "zero_result": len(top_ids) == 0,
    }
    for kk in m.extra_recall_k:
        row[f"recall@{kk}"] = recall_at_k(top_ids, j, kk, m.recall_relevant_min)
    return row


def _mean(values: Iterable[float | None]) -> tuple[float | None, int]:
    v = [x for x in values if x is not None and not (isinstance(x, float) and math.isnan(x))]
    return (float(np.mean(v)) if v else None), len(v)


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
    by_slice: dict[str, dict] = {}
    for s in sorted({r["slice"] for r in rows}):
        rs = [r for r in rows if r["slice"] == s]
        by_slice[s] = {mname: _mean(r[mname] for r in rs)[0] for mname in rank_metrics}
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
