"""P6.1 + P3.1 #4 — dòng vùng biên engine trả không tính vi phạm và không làm tụt recall của engine đúng."""
from __future__ import annotations

import json

import numpy as np

from evaluation.vector_bench.filters import EARTH_R_M, Table
from evaluation.vector_bench.runners.recall import evaluate


class FakeDS:
    def __init__(self, recs, vecs, q, filt, gt_rows, n_match):
        self.table = Table.from_records(recs)
        self.ids = [r["id"] for r in recs]
        self.row_of = {pid: i for i, pid in enumerate(self.ids)}
        self.vectors = vecs
        self.query_vectors = q[None, :]
        self.queries = [{"qid": "x", "filter": filt}]
        k = len(gt_rows)
        self.gt = {"rows": np.array([gt_rows]), "scores": np.array([[1.0 - 0.01 * i for i in range(k)]], dtype=np.float32),
                   "n_match": np.array([n_match]), "n_boundary": np.array([1])}


def _rec(i, dist_m):
    return {"id": f"id{i}", "variant": "hotel_property", "taxonomy": "hotel", "destination": "A", "available": True,
            "amenity_ids": [], "unit_price": 1.0, "star_rating": 4.0, "lat": 10.0 + np.degrees(dist_m / EARTH_R_M), "lon": 106.0}


def test_boundary_result_does_not_lower_recall_of_exact_engine():
    r = 5000.0
    recs = [_rec(i, 100.0 * i) for i in range(4)] + [_rec(4, r)]      # dòng 4 nằm đúng biên
    vecs = np.eye(5, 8, dtype=np.float16)
    f = {"geo": {"lat": 10.0, "lon": 106.0, "radius_m": r}}
    # GT chặt: 4 dòng (0..3); k = 3 → |G| = 3; engine exact trả [0, 4(biên), 1] — đúng thứ tự khoảng cách của engine
    ds = FakeDS(recs, vecs, np.ones(8, dtype=np.float16), f, [0, 1, 2], 4)
    ev = evaluate(ds, 0, [("id0", 1.0), ("id4", 0.99), ("id1", 0.98)], 3, 0.001, 0.005)
    assert ev.violations == 0 and ev.n_boundary_results == 1
    assert ev.recall == 1.0                      # mẫu số = min(|G|, k − số dòng biên) = 2, trúng 2
    ev2 = evaluate(ds, 0, [("id0", 1.0), ("id3", 0.9), ("id2", 0.8)], 3, 0.001, 0.005)
    assert abs(ev2.recall - 2 / 3) < 1e-9                        # không có dòng biên → mẫu số 3; bỏ sót id1 vẫn bị tính
