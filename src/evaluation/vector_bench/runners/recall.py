"""Recall có dung sai (spec P6.1) — dùng chung cho smoke, quality (A1/A3) và gate G3.

Với query i, k: G = min(k, n_match_i) dòng đầu của GT (tập chặt), s_last = điểm phần tử cuối của G.
Kết quả engine → đổi id sang row, bỏ dòng vùng biên. Mỗi dòng còn lại: vi phạm nếu không thoả filter;
ngược lại trúng nếu row ∈ G hoặc cosine thật (fp32 từ vectors.npy) ≥ s_last − tie_eps.
recall_i = min(trúng, |G|) / |G|. n_match_i = 0: không tính recall, trả gì cũng là vi phạm. short_i = trả ít hơn |G|.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..dataset.items import Dataset
from ..filters import boundary, mask


@dataclass
class QueryEval:
    recall: float | None
    n_results: int          # không tính vùng biên
    n_boundary_results: int
    violations: int
    unknown_ids: int
    short: bool
    hits: int
    g: int


def evaluate(ds: Dataset, qi: int, hits: list[tuple[str, float]], k: int, tie_eps: float, geo_tol: float) -> QueryEval:
    gt = ds.gt
    q = ds.queries[qi]
    f = q["filter"]
    nm = int(gt["n_match"][qi])
    g = min(k, nm)
    grows = gt["rows"][qi][:g]
    gset = set(int(r) for r in grows if r >= 0)
    s_last = float(gt["scores"][qi][g - 1]) if g > 0 else float("nan")

    rows, unknown = [], 0
    for pid, _ in hits[:k]:
        r = ds.row_of.get(pid)
        if r is None:
            unknown += 1
        else:
            rows.append(r)
    arr = np.array(rows, dtype=np.int64)
    if f is not None and len(arr):
        sub = ds.table.take(arr)
        ok = mask(f, sub)
        bnd = boundary(f, sub, geo_tol)
    else:
        ok = np.ones(len(arr), dtype=bool)
        bnd = np.zeros(len(arr), dtype=bool)
    keep = ~bnd
    viol = int((~ok & keep).sum()) + unknown
    n_res = int(keep.sum()) + unknown
    hit = 0
    n_bnd = int(bnd.sum())
    if g > 0:
        cand = arr[keep & ok]
        in_g = np.array([int(r) in gset for r in cand], dtype=bool)
        hit += int(in_g.sum())
        rest = cand[~in_g]
        if len(rest):
            qv = ds.query_vectors[qi].astype(np.float32)
            qv /= np.linalg.norm(qv) or 1.0
            v = np.asarray(ds.vectors[np.sort(rest)], dtype=np.float32)
            v /= np.linalg.norm(v, axis=1, keepdims=True)
            hit += int((v @ qv >= s_last - tie_eps).sum())
        # P3.1 #4: dòng vùng biên "không tính miss" — mỗi dòng vùng biên engine trả chiếm một chỗ trong top-k, nên không phạt
        # dòng chặt bị nó đẩy ra: mẫu số = min(|G|, k − số dòng vùng biên đã trả). Công thức chữ của P6.1 (min(trúng,|G|)/|G|)
        # phạt cả engine exact đúng (đã thấy: 6 query geo, exact vẫn 0,9) — mâu thuẫn Done "exact có A1 = 1,0".
        g_eff = min(g, k - n_bnd)
        recall = 1.0 if g_eff <= 0 else min(hit, g_eff) / g_eff
    else:
        recall = None
    return QueryEval(recall=recall, n_results=n_res, n_boundary_results=int(bnd.sum()), violations=viol, unknown_ids=unknown,
                     short=len(hits) < g, hits=hit, g=g)
