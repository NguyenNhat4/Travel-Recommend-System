"""Part 5 P5.4 — `vb smoke <engine>`: 10 query (2–3 mỗi bucket) với cấu hình ĐẦU TIÊN của query_sweep.

In: qid · bucket · filter_type · n_match · recall@10 · vi_phạm · top-3 tên (engine | GT).
Thoát mã 2 nếu có vi phạm filter, hoặc mode=exact mà recall < 1.
"""
from __future__ import annotations

from collections import defaultdict

from ..config import VBenchConfig, expand_query_configs, query_config_name
from ..dataset.items import Dataset
from ..engines.base import StoreOptions
from ..engines.registry import make_store
from .recall import evaluate

N_SMOKE = 10


def run_smoke(cfg: VBenchConfig, *, engine: str, scale: str, index_name: str | None, run_id: str) -> int:
    from rich.console import Console
    from rich.table import Table as RTable

    ds = Dataset(scale)
    ec = cfg.engine(engine)
    qp = expand_query_configs(ec.query_sweep[0])[0]
    k = cfg.quality.k
    by_bucket: dict[str, list[int]] = defaultdict(list)
    for i, q in enumerate(ds.queries):
        by_bucket[q["bucket"]].append(i)
    buckets = sorted(by_bucket)
    pick: list[int] = []
    j = 0
    while len(pick) < N_SMOKE and any(by_bucket[b] for b in buckets):
        b = buckets[j % len(buckets)]
        if by_bucket[b]:
            pick.append(by_bucket[b].pop(0))
        j += 1

    store = make_store(cfg, engine, ds.dim, StoreOptions(timeout_ms=cfg.perf.timeout_ms))
    store.connect()
    t = RTable(title=f"smoke {engine} {scale} · {query_config_name(qp)}")
    for c in ("qid", "bucket", "filter_type", "n_match", "recall@10", "vi_phạm", "top-3 engine", "top-3 GT"):
        t.add_column(c, overflow="fold")
    bad = False
    try:
        for i in pick:
            q = ds.queries[i]
            hits = store.search(ds.query_vectors[i], q["filter"], k, qp)
            ev = evaluate(ds, i, hits, k, cfg.groundtruth.tie_eps, cfg.groundtruth.geo_boundary_tol)
            top_e = [ds.names[ds.row_of[h[0]]] if h[0] in ds.row_of else f"? {h[0]}" for h in hits[:3]]
            top_g = [ds.names[r] for r in ds.gt["rows"][i][:3] if r >= 0]
            rec = "—" if ev.recall is None else f"{ev.recall:.2f}"
            t.add_row(q["qid"], q["bucket"], q["filter_type"], str(int(ds.gt["n_match"][i])), rec, str(ev.violations),
                      " | ".join(top_e), " | ".join(top_g))
            if ev.violations or (qp.get("mode") == "exact" and ev.recall is not None and ev.recall < 1.0):
                bad = True
    finally:
        store.close()
    Console(width=200).print(t)
    return 2 if bad else 0
