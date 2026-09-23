"""Integration (pytest -m integration): catalog fake N=2.000, mọi loại filter, trên engine ĐANG CHẠY.

Mỗi engine: precision = 1,0 cho mọi loại filter (mọi mode); mode exact recall = 1; count = evaluator (lệch tối đa n_boundary với geo).
Bỏ engine chưa bật (`vb engine up <engine>`). Dữ liệu dựng trong VBENCH_HOME tạm, không đụng bench_out thật.
"""
from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def fake_home(tmp_path_factory, cfg):
    home = tmp_path_factory.mktemp("vbench_home")
    old = os.environ.get("VBENCH_HOME")
    os.environ["VBENCH_HOME"] = str(home)
    from evaluation.vector_bench.dataset.catalog import build_catalog
    from evaluation.vector_bench.embed import embed_items, embed_queries
    from evaluation.vector_bench.groundtruth import compute_gt
    from evaluation.vector_bench.querygen import run_queries
    build_catalog(cfg, source="fake", n=2000)
    embed_items(cfg, "catalog", "fake")
    run_queries(cfg, scale="catalog")
    embed_queries(cfg, "catalog", "fake")
    compute_gt(cfg, "catalog")
    yield home
    if old is None:
        os.environ.pop("VBENCH_HOME", None)
    else:
        os.environ["VBENCH_HOME"] = old


def _alive(cfg, engine) -> bool:
    from evaluation.vector_bench import lifecycle
    try:
        return lifecycle.is_healthy(cfg, engine)
    except Exception:
        return False


@pytest.mark.parametrize("engine", ["pgvector", "pgvectorscale", "qdrant"])
def test_engine_filters_precision_and_count(engine, cfg, fake_home):
    if not _alive(cfg, engine):
        pytest.skip(f"{engine} chưa chạy")
    from evaluation.vector_bench.config import sweep_for
    from evaluation.vector_bench.dataset.items import Dataset
    from evaluation.vector_bench.engines.base import StoreOptions
    from evaluation.vector_bench.engines.registry import make_store
    from evaluation.vector_bench.runners.load import load_engine
    from evaluation.vector_bench.runners.recall import evaluate

    idx = cfg.fast.index[engine]
    m = load_engine(cfg, engine, "catalog", idx, progress=False)
    assert m["count_after"] == 2000
    ds = Dataset("catalog")
    store = make_store(cfg, engine, ds.dim, StoreOptions(timeout_ms=cfg.perf.timeout_ms))
    store.connect()
    try:
        types = {}
        for i, q in enumerate(ds.queries):
            types.setdefault(q["filter_type"], []).append(i)
        configs = sweep_for(cfg, engine, "fast")
        if store.capabilities().exact_search:
            configs = [{"mode": "exact"}] + configs
        for qp in configs:
            ok, _ = store.supports_query_config(qp)
            if not ok:
                continue
            for ft, idxs in types.items():
                for i in idxs[:8]:
                    q = ds.queries[i]
                    hits = store.search(ds.query_vectors[i], q["filter"], 10, qp)
                    ev = evaluate(ds, i, hits, 10, cfg.groundtruth.tie_eps, cfg.groundtruth.geo_boundary_tol)
                    assert ev.violations == 0, (engine, qp, ft, q["qid"])
                    if qp.get("mode") == "exact" and ev.recall is not None:
                        assert ev.recall == 1.0, (engine, ft, q["qid"])
        for i, q in enumerate(ds.queries[:200]):
            if q["filter"] is None:
                continue
            c, exact = store.count(q["filter"])
            assert exact
            nm, nb = int(ds.gt["n_match"][i]), int(ds.gt["n_boundary"][i])
            assert nm <= c <= nm + nb, (engine, q["qid"], c, nm, nb)
    finally:
        store.close()
