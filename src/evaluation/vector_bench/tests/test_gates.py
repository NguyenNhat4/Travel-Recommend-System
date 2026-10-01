"""Part 9 — G3: engine bị ép thiếu toán tử (raise UnsupportedFilter) → fail kèm tên toán tử; engine trả sai → fail."""
from __future__ import annotations

import os

import pytest

from evaluation.vector_bench.engines.base import UnsupportedFilter
from evaluation.vector_bench.engines.null import NullStore


class NoGeoStore(NullStore):
    """Engine giả không biểu diễn được geo — phải raise, không tự lọc phía client."""

    def search(self, q, filt, k, qp):
        if filt is not None and '"geo"' in __import__("json").dumps(filt):
            raise UnsupportedFilter("geo")
        return []


class WrongStore(NullStore):
    """Engine giả trả toàn bộ top theo thứ tự id, bỏ qua filter → phải có vi phạm."""

    def __init__(self, ds):
        super().__init__()
        self.ds = ds

    def search(self, q, filt, k, qp):
        return [(self.ds.ids[i], 1.0) for i in range(k)]


@pytest.fixture(scope="module")
def ds(tmp_path_factory, cfg):
    home = tmp_path_factory.mktemp("vb_gate")
    old = os.environ.get("VBENCH_HOME")
    os.environ["VBENCH_HOME"] = str(home)
    from evaluation.vector_bench.dataset.catalog import build_catalog
    from evaluation.vector_bench.dataset.items import Dataset
    from evaluation.vector_bench.embed import embed_items, embed_queries
    from evaluation.vector_bench.groundtruth import compute_gt
    from evaluation.vector_bench.querygen import run_queries
    build_catalog(cfg, source="fake", n=1500)
    embed_items(cfg, "catalog", "fake")
    run_queries(cfg, scale="catalog")
    embed_queries(cfg, "catalog", "fake")
    compute_gt(cfg, "catalog")
    yield Dataset("catalog")
    if old is None:
        os.environ.pop("VBENCH_HOME", None)
    else:
        os.environ["VBENCH_HOME"] = old


def test_g3_fails_with_op_name_when_unsupported(ds, cfg):
    from evaluation.vector_bench.runners.gates import g3_check
    r = g3_check(ds, NoGeoStore(), cfg, {"mode": "ann"})
    assert r["status"] == "fail" and r["unsupported_ops"] == ["geo"]
    assert set(r["per_type"]) == set(cfg.gates.g3.types)
    assert all(v["n"] == cfg.gates.g3.per_type for v in r["per_type"].values())      # thiếu query → sinh thêm cho đủ


def test_g3_fails_on_violations(ds, cfg):
    from evaluation.vector_bench.runners.gates import g3_check
    r = g3_check(ds, WrongStore(ds), cfg, {"mode": "ann"})
    assert r["status"] == "fail" and r["violations"] > 0 and not r["unsupported_ops"]


def test_g3_passes_on_empty_results(ds, cfg):
    from evaluation.vector_bench.runners.gates import g3_check
    assert g3_check(ds, NullStore(), cfg, {"mode": "ann"})["status"] == "pass"
