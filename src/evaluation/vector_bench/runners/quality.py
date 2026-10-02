"""Part 6 (lite, fasttrack §4): A1, A3 (+ count exact ở catalog = A4 phần count). A2, A5, facet: hoãn.

Mỗi cấu hình (default_query + sweep khai triển): 1.000 query MỘT client, tuần tự, k = quality.k, ghi latency.
Bỏ mode exact khi N > quality.exact_max_rows. Timeout mỗi query = perf.timeout_ms (query vượt → không kết quả, recall 0, tính lỗi).
Cấu hình (a) = default_query. Cấu hình (b) = P99 một client thấp nhất (hoà → latency trung bình) trong các cấu hình đạt
a1_min ≥ quality.a1_pass; không cấu hình nào đạt → a1_min cao nhất + a1_fail. A1, A3 lấy theo (b).
"""
from __future__ import annotations

import logging
import time
from collections import defaultdict
from typing import Any

import numpy as np
import pandas as pd

from ..config import IndexConfig, VBenchConfig, query_config_name, sweep_for
from ..dataset.items import Dataset
from ..engines.base import QueryTimeout, StoreOptions, UnsupportedFilter
from ..engines.registry import make_store
from ..results import now_iso, write_result
from .recall import evaluate

log = logging.getLogger("vbench.quality")
ERROR_RATE_MAX = 0.01          # spec §1.5: tỷ lệ lỗi > 1% → status error


def _pct(x: list[float], p: float) -> float | None:
    return float(np.percentile(x, p)) if x else None


def run_config(ds: Dataset, store, qp: dict, cfg: VBenchConfig, deadline: float | None) -> tuple[dict, list[dict]]:
    k = cfg.quality.k
    rows: list[dict] = []
    lat: list[float] = []
    by_bucket, by_type, by_slice = defaultdict(list), defaultdict(list), defaultdict(list)
    viol = nres = short = timeouts = errors = 0
    routed: dict[str, int] = defaultdict(int)
    partial = False
    err_samples: list[str] = []
    for i, q in enumerate(ds.queries):
        if deadline is not None and time.perf_counter() > deadline:
            partial = True
            break
        status = "ok"
        t0 = time.perf_counter_ns()
        try:
            hits = store.search(ds.query_vectors[i], q["filter"], k, qp)
        except QueryTimeout:
            hits, status = [], "timeout"
            timeouts += 1
        except UnsupportedFilter:
            raise
        except Exception as e:  # noqa: BLE001
            hits, status = [], "error"
            errors += 1
            if len(err_samples) < 5:
                err_samples.append(f"{q['qid']}: {e!r}"[:300])
            _recover(store)
        ms = (time.perf_counter_ns() - t0) / 1e6
        lat.append(ms)
        if hasattr(store, "routed_mode"):
            try:
                routed[store.routed_mode(q["filter"], qp)] += 1
            except Exception:  # noqa: BLE001
                routed["unknown"] += 1
        ev = evaluate(ds, i, hits, k, cfg.groundtruth.tie_eps, cfg.groundtruth.geo_boundary_tol)
        viol += ev.violations
        nres += ev.n_results
        short += int(ev.short)
        if ev.recall is not None:
            by_bucket[q["bucket"]].append(ev.recall)
            by_type[q["filter_type"]].append(ev.recall)
            by_slice[str(q.get("slice"))].append(ev.recall)
        rows.append({"qid": q["qid"], "config": query_config_name(qp), "bucket": q["bucket"], "filter_type": q["filter_type"],
                     "slice": q.get("slice"), "n_match": int(ds.gt["n_match"][i]), "recall": ev.recall,
                     "violations": ev.violations, "n_results": ev.n_results, "short": ev.short, "latency_ms": ms,
                     "status": status})
    n = len(rows)
    a1_bucket = {b: float(np.mean(v)) for b, v in sorted(by_bucket.items())}
    err_rate = (timeouts + errors) / n if n else 1.0
    m = {
        "name": query_config_name(qp), "query_params": qp, "n_queries": n, "partial": partial,
        "a1_by_bucket": a1_bucket, "a1_min": min(a1_bucket.values()) if a1_bucket else None,
        "a1_by_type": {t: float(np.mean(v)) for t, v in sorted(by_type.items())},
        "a1_by_slice": {s: float(np.mean(v)) for s, v in sorted(by_slice.items())},
        "A3": (1.0 - viol / nres) if nres else 1.0, "violations": viol, "n_results": nres, "n_short": short,
        "n_timeout": timeouts, "n_error": errors, "error_rate": err_rate, "error_samples": err_samples,
        "status": "error" if err_rate > ERROR_RATE_MAX else ("partial" if partial else "ok"),
        "latency_ms": {"mean": float(np.mean(lat)) if lat else None, "p50": _pct(lat, 50), "p95": _pct(lat, 95), "p99": _pct(lat, 99)},
        "routed": dict(routed) if routed else None,
    }
    return m, rows


def _recover(store) -> None:
    """Sau lỗi giữa chừng (vd. connection hỏng) — thử kết nối lại để các query sau vẫn chạy."""
    try:
        store.close()
        store.connect()
    except Exception:  # noqa: BLE001
        pass


def explain_rate(ds: Dataset, store, qp: dict, n: int) -> float | None:
    """EXPLAIN (FORMAT JSON) của n query mẫu có filter → tỷ lệ plan dùng index vector (chỉ engine Postgres)."""
    picks = [i for i, q in enumerate(ds.queries) if q["filter"] is not None][:n]
    got = []
    for i in picks:
        try:
            r = store.plan_uses_index(ds.query_vectors[i], ds.queries[i]["filter"], 10, qp)
        except Exception:  # noqa: BLE001
            r = None
        if r is not None:
            got.append(bool(r))
    return float(np.mean(got)) if got else None


def choose_b(configs: list[dict], a1_pass: float) -> tuple[dict | None, bool]:
    ok = [c for c in configs if c["status"] != "error" and c["a1_min"] is not None and c["a1_min"] >= a1_pass]
    if ok:
        return min(ok, key=lambda c: (c["latency_ms"]["p99"], c["latency_ms"]["mean"])), False
    cand = [c for c in configs if c["a1_min"] is not None]
    if not cand:
        return None, True
    return max(cand, key=lambda c: (c["a1_min"], -(c["latency_ms"]["p99"] or 0))), True


def count_check(ds: Dataset, store, n: int) -> dict:
    """A4 (phần count): n query có filter đầu tiên — count so với n_match, cho lệch tối đa n_boundary."""
    picks = [i for i, q in enumerate(ds.queries) if q["filter"] is not None][:n]
    exact_ok, errs, flags = 0, [], set()
    for i in picks:
        c, is_exact = store.count(ds.queries[i]["filter"])
        flags.add(bool(is_exact))
        nm, nb = int(ds.gt["n_match"][i]), int(ds.gt["n_boundary"][i])
        if nm <= c <= nm + nb:
            exact_ok += 1
            errs.append(0)
        else:
            errs.append(min(abs(c - nm), abs(c - nm - nb)))
    return {"n_filters": len(picks), "count_exact_rate": exact_ok / len(picks) if picks else None,
            "count_mae": float(np.mean(errs)) if errs else None, "capability_count_exact": all(flags) if flags else None,
            "facet": "skipped (fast-track)"}


def run_quality(cfg: VBenchConfig, *, engine: str, scale: str, run_id: str, only: str = "A1,A3,A4", index_name: str | None = None,
                sweep: str = "full", deadline: float | None = None, index: IndexConfig | None = None,
                engine_limits: dict | None = None) -> int:
    started = now_iso()
    want = {x.strip().upper() for x in only.split(",") if x.strip()}
    ds = Dataset(scale)
    idx = index or cfg.engine_index(engine, index_name)
    store = make_store(cfg, engine, ds.dim, StoreOptions(timeout_ms=cfg.perf.timeout_ms))
    store.connect()
    configs: list[dict] = []
    all_rows: list[dict] = []
    skipped: list[dict] = []
    status = "ok"
    try:
        qps = sweep_for(cfg, engine, sweep)
        if hasattr(store, "needs_state") and store.needs_state(qps):
            store.export_state()          # thống kê cache cho mode auto: dựng MỘT lần, ngoài vòng đo và không bị timeout query
        for qp in qps:
            ok, why = store.supports_query_config(qp)
            if not ok:
                skipped.append({"name": query_config_name(qp), "reason": why})
                continue
            if qp.get("mode") == "exact" and ds.n > cfg.quality.exact_max_rows:
                skipped.append({"name": query_config_name(qp), "reason": f"N={ds.n} > quality.exact_max_rows"})
                continue
            if deadline is not None and time.perf_counter() > deadline:
                skipped.append({"name": query_config_name(qp), "reason": "hết thời gian (fast.max_minutes_per_engine)"})
                status = "partial"
                continue
            log.info("quality %s %s: %s", engine, scale, query_config_name(qp))
            m, rows = run_config(ds, store, qp, cfg, deadline)
            m["plan_uses_index_rate"] = explain_rate(ds, store, qp, cfg.quality.explain_sample)
            configs.append(m)
            all_rows += rows
            if m["partial"]:
                status = "partial"
            print(f"  {m['name']:<70} A1min={m['a1_min'] if m['a1_min'] is None else round(m['a1_min'], 4)} "
                  f"A3={m['A3']:.4f} p99={m['latency_ms']['p99']:.1f}ms short={m['n_short']} timeout={m['n_timeout']}"
                  + (f" routed={m['routed']}" if m.get("routed") else ""))
        a_name = query_config_name(qps[0])
        config_a = next((c for c in configs if c["name"] == a_name), None)
        config_b, a1_fail = choose_b(configs, cfg.quality.a1_pass)
        metrics: dict[str, Any] = {"configs": configs, "skipped_configs": skipped, "config_a": a_name,
                                   "config_b": config_b["name"] if config_b else None, "a1_fail": a1_fail,
                                   "A1": config_b["a1_min"] if config_b else None, "A3": config_b["A3"] if config_b else None,
                                   "A1_config_a": config_a["a1_min"] if config_a else None,
                                   "capabilities": store.capabilities().to_json(), "n": ds.n, "k": cfg.quality.k,
                                   "query_timeout_ms": cfg.perf.timeout_ms}
        if "A4" in want:
            metrics["A4"] = count_check(ds, store, cfg.quality.a4_n_filters)
        ev, cv = store.server_version(), store.client_version()
    except UnsupportedFilter as e:
        store.close()
        write_result(run_id, engine, scale, "quality", status="unsupported", metrics={"unsupported_op": e.op}, started_at=started,
                     error=str(e), index_config=idx.model_dump(), engine_limits=engine_limits)
        return 2
    except Exception as e:  # noqa: BLE001
        log.exception("quality %s %s lỗi", engine, scale)
        store.close()
        write_result(run_id, engine, scale, "quality", status="error", metrics={"configs": configs}, started_at=started,
                     error=repr(e), index_config=idx.model_dump(), engine_limits=engine_limits)
        return 1
    store.close()
    p = write_result(run_id, engine, scale, "quality", status=status, metrics=metrics, started_at=started, engine_version=ev,
                     client_version=cv, index_config=idx.model_dump(), engine_limits=engine_limits)
    pd.DataFrame(all_rows).to_parquet(p.with_name("quality_queries.parquet"), index=False)
    b = metrics["config_b"]
    print(f"quality {engine} {scale}: (a) {metrics['config_a']} A1={metrics['A1_config_a']} · (b) {b} A1={metrics['A1']} "
          f"A3={metrics['A3']} a1_fail={metrics['a1_fail']}" + (f" · count exact {metrics['A4']['count_exact_rate']}" if "A4" in metrics else ""))
    bad = metrics["a1_fail"] or (metrics["A3"] is not None and metrics["A3"] < 1.0)
    return 2 if bad else 0
