"""`vb fast` — điều phối fast-track (spec-fasttrack §4), chặn thời gian mỗi engine.

Với mỗi engine lần lượt:
1. Cất kết quả cũ của engine trong run (runs/<run>/<engine> → <engine>.prev-<thời điểm>) để report không đọc nhầm số cũ.
2. down --volumes (sạch) → up với fast.engine_limits (+ fast.pg_env cho Postgres) → wait_healthy.
3. catalog: load (fast.index) → G3 → A1 / A3 / count.
4. 1m: load (B3) → sweep A1 / A3 → chọn (b) → tải open-loop fast.perf.rates_qps (100 rồi 200 QPS) với (b) (B1, B2).
   Sampler C1 (docker stats) chạy suốt.
5. down --volumes (trừ khi --keep).
Chặn thời gian fast.max_minutes_per_engine: vượt → ghi kết quả dở dang (status partial) và sang engine tiếp.
Lỗi ở một engine (kể cả lúc up) không chặn các engine sau.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any

from .. import lifecycle, paths
from ..config import VBenchConfig
from ..results import dump_json, now_iso, read_result
from .gates import run_gates
from .load import run_load
from .perf import run_perf
from .quality import run_quality
from .resources import ResourceSampler

log = logging.getLogger("vbench.fast")
PG_ENGINES = ("pgvector", "pgvectorscale")
HEALTH_TIMEOUT_S = 300


def _require_data(scales: list[str]) -> None:
    for s in scales:
        d = paths.data_dir(s, create=False)
        for f in (paths.ITEMS, paths.VECTORS, paths.QUERIES, paths.QUERY_VECTORS, paths.GT):
            if not (d / f).exists():
                hint = "vb dataset catalog / embed / queries / embed --target queries / gt" if s == "catalog" else \
                    f"vb scale-data {s} --vectors amplify"
                raise FileNotFoundError(f"thiếu {d / f} — chạy `{hint}` trước")


def _archive_previous(run_id: str, engine: str) -> str | None:
    d = paths.run_dir(run_id) / engine
    if not d.exists():
        return None
    dst = d.with_name(f"{engine}.prev-{datetime.now().strftime('%Y%m%d-%H%M%S')}")
    d.rename(dst)
    return dst.name


def run_engine(cfg: VBenchConfig, engine: str, run_id: str, scales: list[str], keep: bool,
               perf_duration: float | None, perf_warmup: float | None) -> dict[str, Any]:
    t_start = time.perf_counter()
    started_at = now_iso()
    deadline = t_start + cfg.fast.max_minutes_per_engine * 60
    lim = cfg.fast.engine_limits
    limits = {"cpus": lim.cpus, "mem": lim.mem}
    extra = dict(cfg.fast.pg_env) if engine in PG_ENGINES else {}
    env = lifecycle.compose_env(cfg, limits=(lim.cpus, lim.mem), extra=extra)
    idx = cfg.fast.index[engine]
    archived = _archive_previous(run_id, engine)
    steps: list[dict] = []
    status = "ok"

    def step(name: str, fn, *a, **kw) -> int:
        nonlocal status
        if time.perf_counter() > deadline:
            steps.append({"step": name, "status": "skipped", "reason": "hết thời gian"})
            status = "partial"
            return -1
        t0 = time.perf_counter()
        log.info("[fast] %s — %s", engine, name)
        try:
            rc = fn(*a, **kw)
        except Exception as e:  # noqa: BLE001
            log.exception("[fast] %s — %s lỗi", engine, name)
            steps.append({"step": name, "status": "error", "error": repr(e), "seconds": round(time.perf_counter() - t0, 1)})
            status = "partial"
            return 1
        steps.append({"step": name, "rc": rc, "seconds": round(time.perf_counter() - t0, 1),
                      "status": "ok" if rc in (0, 2) else "error"})
        if rc not in (0, 2):
            status = "partial"
        return rc

    sampler: ResourceSampler | None = None
    try:
        lifecycle.down(cfg, engine, volumes=True, env=env)
        lifecycle.up(cfg, engine, env=env)
        up_s = lifecycle.wait_healthy(cfg, engine, HEALTH_TIMEOUT_S)
        steps.append({"step": "up", "seconds": round(up_s, 1), "status": "ok", "env": {**limits, **extra}})
        sampler = ResourceSampler(engine).start()
        for scale in scales:
            sampler.mark(f"load@{scale}")
            rc = step(f"load {scale}", run_load, cfg, engine=engine, scale=scale, index_name=None, run_id=run_id, index=idx,
                      deadline=deadline, engine_limits=limits)
            if rc != 0:
                break
            if scale == "catalog":
                sampler.mark("gate@catalog")
                step("G3 catalog", run_gates, cfg, engine=engine, run_id=run_id, only="g3", scale="catalog", index=idx,
                     engine_limits=limits)
            sampler.mark(f"quality@{scale}")
            rq = step(f"quality {scale}", run_quality, cfg, engine=engine, scale=scale, run_id=run_id,
                      only="A1,A3,A4" if scale == "catalog" else "A1,A3", sweep="fast", deadline=deadline, index=idx,
                      engine_limits=limits)
            if scale != "catalog":
                q = read_result(run_id, engine, scale, "quality") if rq in (0, 2) else None   # chỉ tin file vừa ghi ở lần này
                if q and q["metrics"].get("config_b"):
                    step(f"perf {scale}", run_perf, cfg, engine=engine, scale=scale, run_id=run_id, rates=list(cfg.fast.perf.rates_qps),
                         duration_s=perf_duration if perf_duration is not None else cfg.fast.perf.duration_s,
                         warmup_s=perf_warmup, reps=cfg.fast.perf.reps, sampler=sampler, engine_limits=limits, deadline=deadline)
                    p = read_result(run_id, engine, scale, "perf")
                    if p and p.get("status") == "partial":
                        status = "partial"
                else:
                    steps.append({"step": f"perf {scale}", "status": "skipped", "reason": "không có cấu hình (b) mới"})
                    status = "partial"
            phases = {f"load@{scale}", f"quality@{scale}"} | (
                {f"perf@{r:g}" for r in cfg.fast.perf.rates_qps} if scale != "catalog" else {"gate@catalog"})
            dump_json(paths.step_dir(run_id, engine, scale) / "resources.json",
                      {"C1": sampler.summary(phases), "phases": sorted({s[4] for s in sampler.samples})})
    except Exception as e:  # noqa: BLE001   (up / wait_healthy / sampler)
        log.exception("[fast] %s lỗi ngoài các bước đo", engine)
        steps.append({"step": "engine", "status": "error", "error": repr(e)})
        status = "error"
    finally:
        if sampler is not None:
            sampler.stop()
        if not keep:
            try:
                lifecycle.down(cfg, engine, volumes=True, env=env)
            except Exception:  # noqa: BLE001
                log.exception("[fast] %s — down lỗi", engine)
    minutes = (time.perf_counter() - t_start) / 60
    doc = {"engine": engine, "run_id": run_id, "status": status, "minutes": round(minutes, 1),
           "max_minutes": cfg.fast.max_minutes_per_engine, "scales": scales, "steps": steps, "engine_limits": limits,
           "pg_env": extra, "index_config": idx.model_dump(), "started_at": started_at, "finished_at": now_iso(),
           "archived_previous": archived}
    dump_json(paths.run_dir(run_id) / engine / "fast.json", doc)
    print(f"[fast] {engine}: {status} · {minutes:.1f} phút")
    return doc


def run_fast(cfg: VBenchConfig, *, run_id: str, engines: list[str] | None, scales: list[str] | None, keep: bool,
             perf_duration: float | None = None, perf_warmup: float | None = None) -> int:
    engines = engines or list(cfg.fast.engines)
    scales = scales or list(cfg.fast.scales)
    _require_data(scales)
    docs = []
    for e in engines:
        try:
            docs.append(run_engine(cfg, e, run_id, scales, keep, perf_duration, perf_warmup))
        except Exception as ex:  # noqa: BLE001
            log.exception("[fast] %s lỗi", e)
            doc = {"engine": e, "run_id": run_id, "status": "error", "error": repr(ex), "finished_at": now_iso()}
            dump_json(paths.run_dir(run_id) / e / "fast.json", doc)
            docs.append(doc)
    return 0 if all(d["status"] == "ok" for d in docs) else 1
