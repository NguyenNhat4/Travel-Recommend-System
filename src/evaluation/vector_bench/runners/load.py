"""Part 5 P5.2 — load(engine, scale, index): create → upsert theo lô `load.batch_size` (thứ tự xáo bằng seed) → finalize.

Ghi load.json: n, load_s, index_s, vectors_per_s, index_config. Ở 1M, load_s + index_s chính là B3.
"""
from __future__ import annotations

import logging
import time
from typing import Any

import numpy as np

from ..config import IndexConfig, VBenchConfig
from ..dataset.items import Dataset
from ..engines.base import StoreOptions
from ..engines.registry import make_store
from ..results import now_iso, write_result

log = logging.getLogger("vbench.load")
SEED_OFFSET_LOAD = 5000


def load_engine(cfg: VBenchConfig, engine: str, scale: str, index: IndexConfig, *, seed_offset: int = 0,
                deadline: float | None = None, progress: bool = True) -> dict[str, Any]:
    ds = Dataset(scale)
    store = make_store(cfg, engine, ds.dim, StoreOptions(extra={"deadline": deadline}))
    store.connect()
    try:
        t0 = time.perf_counter()
        store.create(index)
        n = ds.n
        order = np.arange(n)
        if cfg.load.shuffle:
            order = np.random.default_rng(cfg.run.seed + SEED_OFFSET_LOAD + seed_offset).permutation(n)
        bs = cfg.load.batch_size
        last_log = t0
        for a in range(0, n, bs):
            ids, vecs, pls = ds.batch(order[a:a + bs])
            store.upsert(ids, vecs, pls)
            now = time.perf_counter()
            if progress and now - last_log > 10:
                log.info("%s load %s: %d/%d (%.0f vec/s)", engine, scale, a + len(ids), n, (a + len(ids)) / (now - t0))
                last_log = now
            if deadline is not None and now > deadline:
                raise TimeoutError(f"vượt chặn thời gian khi nạp ({a + len(ids)}/{n})")
        load_s = time.perf_counter() - t0
        index_s = store.finalize()
        cnt, exact = store.count(None)
        meta: dict[str, Any] = {}
        if hasattr(store, "index_meta"):
            try:
                meta = store.index_meta()
            except Exception as e:  # noqa: BLE001
                meta = {"index_meta_error": str(e)}
        return {"n": n, "count_after": cnt, "count_exact": exact, "load_s": round(load_s, 3), "index_s": round(index_s, 3),
                "b3_minutes": round((load_s + index_s) / 60, 3), "vectors_per_s": round(n / load_s, 1) if load_s > 0 else None,
                "batch_size": bs, "shuffle": cfg.load.shuffle, "index_config": index.model_dump(), **meta,
                "engine_version": store.server_version(), "client_version": store.client_version(),
                "capabilities": store.capabilities().to_json()}
    finally:
        store.close()


def run_load(cfg: VBenchConfig, *, engine: str, scale: str, index_name: str | None, run_id: str,
             index: IndexConfig | None = None, deadline: float | None = None, engine_limits: dict | None = None) -> int:
    started = now_iso()
    idx = index or cfg.engine_index(engine, index_name)
    try:
        m = load_engine(cfg, engine, scale, idx, deadline=deadline)
    except Exception as e:  # noqa: BLE001
        log.exception("load %s %s lỗi", engine, scale)
        write_result(run_id, engine, scale, "load", status="error", metrics={}, started_at=started, error=repr(e),
                     index_config=idx.model_dump(), engine_limits=engine_limits)
        return 1
    status = "ok" if m["count_after"] == m["n"] else "error"
    write_result(run_id, engine, scale, "load", status=status, metrics=m, started_at=started,
                 error=None if status == "ok" else f"count sau nạp {m['count_after']} ≠ {m['n']}",
                 engine_version=m["engine_version"], client_version=m["client_version"], index_config=idx.model_dump(),
                 engine_limits=engine_limits)
    print(f"load {engine} {scale} [{idx.name}]: n={m['n']} · load_s={m['load_s']:.1f} · index_s={m['index_s']:.1f} · "
          f"{m['vectors_per_s']} vec/s · B3={m['b3_minutes']:.2f} phút · count={m['count_after']}")
    return 0 if status == "ok" else 1
