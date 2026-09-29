"""Part 10 (amplify) — LID MLE, láng giềng ưu tiên cùng destination, metadata kế thừa."""
from __future__ import annotations

import numpy as np
import pyarrow as pa

from evaluation.vector_bench.dataset.scale import _gen_block, _inherit_meta, _neighbors, lid_mle


def test_lid_mle_recovers_intrinsic_dim():
    rng = np.random.default_rng(0)
    for true_d in (4, 12):
        basis = np.linalg.qr(rng.normal(size=(256, true_d)))[0]          # tập con tuyến tính true_d chiều trong 256-d
        x = rng.normal(size=(3000, true_d)) @ basis.T + 5.0 * rng.normal(size=256) / 16   # dời khỏi gốc để chuẩn hoá ít méo
        med = float(np.median(lid_mle(x, k=20)))
        assert 0.6 * true_d < med < 1.6 * true_d, (true_d, med)


def test_neighbors_prefer_same_destination():
    rng = np.random.default_rng(1)
    v = rng.normal(size=(60, 16)).astype(np.float32)
    v /= np.linalg.norm(v, axis=1, keepdims=True)
    dest = np.array([0] * 30 + [1] * 25 + [2] * 5)                        # dest 2 có < k+1 seed → láng giềng toàn cục
    nb = _neighbors(v, dest, k=10)
    assert all(set(dest[nb[i]]) == {0} for i in range(30))
    assert all(set(dest[nb[i]]) == {1} for i in range(30, 55))
    assert all(i not in nb[i] for i in range(60))


def test_gen_block_normalized_and_near_seed():
    rng = np.random.default_rng(2)
    v0 = rng.normal(size=(50, 64)).astype(np.float32)
    v0 /= np.linalg.norm(v0, axis=1, keepdims=True)
    nb = _neighbors(v0, np.zeros(50, int), k=5)
    v, cs = _gen_block(rng, v0, nb, np.arange(500), 0.1, (0.1, 0.5))
    assert np.allclose(np.linalg.norm(v, axis=1), 1.0, atol=1e-5)
    assert np.allclose(cs, np.einsum("ij,ij->i", v, v0[np.arange(500) % 50]), atol=1e-5)


def test_inherit_meta_invariants(cfg):
    items = pa.table({
        "variant": ["hotel_property", "attraction"], "taxonomy": ["hotel", "attraction"], "destination": ["A", "B"],
        "province": ["P", "Q"], "name": ["h", "a"], "star_rating": pa.array([5.0, None], pa.float32()),
        "unit_price": pa.array([1000.0, None]), "lat": [10.0, 11.0], "lon": [106.0, 107.0], "available": [True, True],
        "amenity_ids": pa.array([[1, 2, 3, 4, 5, 6, 7, 8, 9, 10], []], pa.list_(pa.int16())),
    })
    seeds = np.array([0, 1] * 5000)
    t = _inherit_meta(items, seeds, cfg, np.random.default_rng(3), "t", 0)
    am = t.column("amenity_ids").to_pylist()
    assert all(x == sorted(set(x)) for x in am)                           # sắp tăng, không trùng
    hotel_lens = np.array([len(x) for x, s in zip(am, seeds) if s == 0])
    assert 8.0 < hotel_lens.mean() < 10.0                                   # bỏ ~10%, thêm ~10% (có thể trùng)
    assert all(len(x) == 0 for x, s in zip(am, seeds) if s == 1)           # attraction không có amenity phổ biến để thêm
    price = np.array(t.column("unit_price").to_pylist(), dtype=float)
    assert np.isnan(price[seeds == 1]).all()                                # null giữ null
    lr = np.log(price[seeds == 0] / 1000.0)
    assert abs(lr.std() - cfg.fast.amplify.price_log_sd) < 0.02
    assert t.column("destination").to_pylist()[:2] == ["A", "B"] and t.column("star_rating").to_pylist()[1] is None
    dlat_m = (np.array(t.column("lat").to_pylist())[seeds == 0] - 10.0) * 111_320
    assert abs(dlat_m.std() - cfg.fast.amplify.geo_jitter_m) < 100
