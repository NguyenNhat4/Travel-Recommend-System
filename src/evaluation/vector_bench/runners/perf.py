"""Part 11 (lite, fasttrack §4): tải OPEN-LOOP, P50/P95/P99/P99.9 + CI bootstrap của P99; B1, B2 (ghi nhận), B3 từ load.json,
C1 từ sampler docker stats. B4–B6, C2, D: hoãn.

- Một process (process chính) lập lịch phát request theo tốc độ cố định (khoảng cách đều) vào hàng đợi chung; pool
  perf.workers process spawn, mỗi worker tự tạo adapter từ (tên engine + đường dẫn config) — spec §1.5.
- Latency = thời điểm nhận kết quả − thời điểm LẼ RA gửi theo lịch (không coordinated omission). Warm-up bỏ khỏi số liệu.
- Timeout (perf.timeout_ms, cũng là statement/request timeout của worker) tính vào phân vị với giá trị = timeout và vào tỷ lệ lỗi;
  lỗi khác tính như timeout (bảo thủ) và đếm riêng.
- `vb perf null`: engine giả trả ngay → P99 của harness phải < perf.harness_max_p99_ms, không thì số đo không dùng được.
- Không tính thời gian embed query — query vector đã tính sẵn.
"""
from __future__ import annotations

import json
import logging
import multiprocessing as mp
import queue
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .. import paths
from ..config import VBenchConfig
from ..engines.base import QueryTimeout, StoreOptions
from ..engines.registry import make_store
from ..results import dump_json, now_iso, read_result, write_result
from . import timing
from .resources import ResourceSampler

log = logging.getLogger("vbench.perf")
SEED_OFFSET_BOOT = 11000
START_DELAY_NS = 300_000_000        # lịch bắt đầu sau 0,3 s kể từ khi mọi worker sẵn sàng
DRAIN_PAUSE_S = 2.0                 # nghỉ giữa các mức tải
COLLECT_GRACE_S = 60.0              # chờ worker trả buffer sau lịch (ngoài timeout query)
STOP_GRACE_S = 15.0                 # tổng thời gian chờ worker thoát khi dừng pool


# ---------------------------------------------------------------- worker (top-level để spawn pickle được)
def _worker(wid: int, engine: str, config_path: str, dim: int, timeout_ms: float, qp: dict, k: int, state: dict,
            data_dir: str, task_q, result_q, ready_q, barrier) -> None:
    timing.tune_process()
    from ..config import load_config
    cfg = load_config(config_path)
    d = Path(data_dir)
    qv = np.load(d / paths.QUERY_VECTORS)
    with open(d / paths.QUERIES, encoding="utf-8") as fh:
        filters = [json.loads(line)["filter"] for line in fh if line.strip()]
    store = make_store(cfg, engine, dim, StoreOptions(timeout_ms=timeout_ms))
    store.connect()
    store.import_state(state)
    try:
        store.search(qv[wid % len(qv)], filters[wid % len(filters)], k, qp)     # làm nóng connection + GUC
    except Exception:  # noqa: BLE001
        pass
    ready_q.put(wid)
    timeout_ns = int(timeout_ms * 1e6)
    buf: list[tuple] = []
    while True:
        item = task_q.get()
        if item is None:
            break
        if item == "FLUSH":
            result_q.put((wid, buf))
            buf = []
            barrier.wait()
            continue
        i, sched_ns, qi = item
        start = time.perf_counter_ns()
        status, n = 0, 0
        if start - sched_ns > timeout_ns:
            # đã quá hạn khi tới lượt (engine quá tải): client có deadline sẽ không gửi → ghi timeout, không dồn thêm tải
            buf.append((i, sched_ns, start, start, 3, 0))
            continue
        try:
            n = len(store.search(qv[qi], filters[qi], k, qp))
        except QueryTimeout:
            status = 1
        except Exception:  # noqa: BLE001
            status = 2
            try:
                store.close()
                store.connect()
                store.import_state(state)
            except Exception:  # noqa: BLE001
                pass
        buf.append((i, sched_ns, start, time.perf_counter_ns(), status, n))
    store.close()


# ---------------------------------------------------------------- thống kê
def latency_stats(lat_ms: np.ndarray, timeout_ms: float, n_timeout: int, n_error: int, boot: int, seed: int) -> dict:
    n = len(lat_ms)
    if n == 0:
        return {"n": 0}
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, n, size=(boot, n))
    p99s = np.percentile(lat_ms[idx], 99, axis=1)
    return {"n": int(n), "mean": float(lat_ms.mean()), "p50": float(np.percentile(lat_ms, 50)),
            "p95": float(np.percentile(lat_ms, 95)), "p99": float(np.percentile(lat_ms, 99)),
            "p99_9": float(np.percentile(lat_ms, 99.9)), "max": float(lat_ms.max()),
            "p99_ci95": [float(np.percentile(p99s, 2.5)), float(np.percentile(p99s, 97.5))],
            "timeouts": int(n_timeout), "errors": int(n_error), "timeout_rate": n_timeout / n, "error_rate": (n_timeout + n_error) / n,
            "timeout_ms": timeout_ms}


def ci_overlap(a: list[float] | None, b: list[float] | None) -> bool | None:
    if not a or not b:
        return None
    return not (a[1] < b[0] or b[1] < a[0])


class OpenLoopPool:
    def __init__(self, cfg: VBenchConfig, engine: str, dim: int, qp: dict, k: int, state: dict, data_dir: Path, workers: int):
        timing.limit_blas_threads()
        self.ctx = mp.get_context("spawn")
        # SimpleQueue: put() ghi pipe ngay trong thread gọi — không có feeder thread tranh GIL với vòng spin của bộ lập lịch
        self.task_q = self.ctx.SimpleQueue()
        self.result_q = self.ctx.Queue()
        self.ready_q = self.ctx.Queue()
        self.barrier = self.ctx.Barrier(workers + 1)
        self.n = workers
        self.procs = [self.ctx.Process(target=_worker, daemon=True,
                                       args=(w, engine, cfg.source_path, dim, cfg.perf.timeout_ms, qp, k, state, str(data_dir),
                                             self.task_q, self.result_q, self.ready_q, self.barrier))
                      for w in range(workers)]
        self.nq = len(np.load(data_dir / paths.QUERY_VECTORS, mmap_mode="r"))
        self.timeout_s = cfg.perf.timeout_ms / 1000
        self.gidx = 0

    def start(self, timeout_s: float = 300) -> float:
        t0 = time.perf_counter()
        for p in self.procs:
            p.start()
        got = 0
        while got < self.n:
            self.ready_q.get(timeout=timeout_s)
            got += 1
        return time.perf_counter() - t0

    def run_level(self, rate: float, warmup_s: float, duration_s: float) -> tuple[list[tuple], int, dict]:
        period = 1e9 / rate
        n = int(round((warmup_s + duration_s) * rate))
        t0 = time.perf_counter_ns() + START_DELAY_NS
        late = []
        for j in range(n):
            sched = t0 + int(round(j * period))
            timing.sleep_until_ns(sched)
            late.append(time.perf_counter_ns() - sched)
            self.task_q.put((self.gidx, sched, self.gidx % self.nq))
            self.gidx += 1
        for _ in range(self.n):
            self.task_q.put("FLUSH")
        rows: list[tuple] = []
        limit = time.monotonic() + self.timeout_s + COLLECT_GRACE_S
        got = 0
        while got < self.n:              # chờ có giới hạn + kiểm worker còn sống (worker chết → lỗi, không treo cả `vb fast`)
            try:
                _, buf = self.result_q.get(timeout=1.0)
            except queue.Empty:
                dead = [p.pid for p in self.procs if not p.is_alive()]
                if dead or time.monotonic() > limit:
                    raise RuntimeError(f"worker không trả kết quả (chết: {dead}, quá hạn: {time.monotonic() > limit})")
                continue
            rows += buf
            got += 1
        self.barrier.wait(timeout=COLLECT_GRACE_S)
        lat = np.array(late) / 1e6
        sched_info = {"scheduler_late_p50_ms": float(np.percentile(lat, 50)), "scheduler_late_p99_ms": float(np.percentile(lat, 99)),
                      "scheduler_late_max_ms": float(lat.max())}
        return rows, t0 + int(warmup_s * 1e9), sched_info

    def stop(self) -> None:
        try:
            self.barrier.abort()         # giải phóng worker đang kẹt ở barrier
        except Exception:  # noqa: BLE001
            pass
        for _ in range(self.n):
            self.task_q.put(None)
        end = time.monotonic() + STOP_GRACE_S
        for p in self.procs:
            p.join(max(0.0, end - time.monotonic()))
        for p in self.procs:
            if p.is_alive():
                p.terminate()


def transport_floor(store, n: int = 200) -> dict | None:
    """Sàn transport: n request rỗng tuần tự (pg: SELECT 1; qdrant: collection_exists) — tách chi phí mạng Docker khỏi engine."""
    if not hasattr(store, "ping"):
        return None
    ts = []
    for _ in range(n):
        t = time.perf_counter_ns()
        store.ping()
        ts.append((time.perf_counter_ns() - t) / 1e6)
    return {"n": n, "p50_ms": float(np.percentile(ts, 50)), "p99_ms": float(np.percentile(ts, 99))}


def run_perf(cfg: VBenchConfig, *, engine: str, scale: str, run_id: str, only: str = "B1,B2,B3,C1", rates: list[float] | None = None,
             duration_s: float | None = None, warmup_s: float | None = None, reps: int | None = None, index_name: str | None = None,
             sampler: ResourceSampler | None = None, engine_limits: dict | None = None, deadline: float | None = None) -> int:
    started = now_iso()
    pc = cfg.perf
    rates = rates or list(pc.rates_qps)
    duration_s = pc.duration_s if duration_s is None else duration_s
    warmup_s = pc.warmup_s if warmup_s is None else warmup_s
    reps = pc.reps if reps is None else reps
    d = paths.data_dir(scale, create=False)
    qv_p = d / paths.QUERY_VECTORS
    if not qv_p.exists():
        raise FileNotFoundError(f"thiếu {qv_p}")
    dim = int(np.load(qv_p, mmap_mode="r").shape[1])
    tuning = timing.tune_process()

    if engine == "null":
        qp: dict = {"mode": "null"}
        qname = "null"
        state: dict = {}
        tf = None
        ev = cv = "null"
    else:
        q = read_result(run_id, engine, scale, "quality")
        if not q or not q.get("metrics", {}).get("config_b"):
            raise RuntimeError(f"thiếu quality.json (cấu hình b) cho {engine}/{scale} trong run {run_id} — chạy `vb quality` trước")
        qname = q["metrics"]["config_b"]
        qp = next(c["query_params"] for c in q["metrics"]["configs"] if c["name"] == qname)
        parent = make_store(cfg, engine, dim, StoreOptions(timeout_ms=pc.timeout_ms))
        parent.connect()
        state = parent.export_state() if qp.get("mode") == "auto" else {}
        tf = transport_floor(parent)
        ev, cv = parent.server_version(), parent.client_version()
        parent.close()

    own_sampler = sampler is None and engine != "null"
    if own_sampler:
        sampler = ResourceSampler(engine).start()
    pool = OpenLoopPool(cfg, engine, dim, qp, pc.k, state, d, pc.workers)
    levels: list[dict] = []
    samples: list[pd.DataFrame] = []
    partial = False
    spawn_s = float("nan")
    try:
        spawn_s = pool.start()
        log.info("perf %s %s: %d worker sẵn sàng sau %.1f s · cấu hình (b) %s", engine, scale, pc.workers, spawn_s, qname)
        for rate in rates:
            for rep in range(reps):
                if deadline is not None and time.perf_counter() + warmup_s + duration_s > deadline:
                    partial = True
                    break
                if sampler:
                    sampler.mark(f"perf@{rate:g}")
                t_start = time.perf_counter()
                rows, measure_from, sched_info = pool.run_level(rate, warmup_s, duration_s)
                arr = np.array(rows, dtype=np.int64).reshape(-1, 6)
                arr = arr[np.argsort(arr[:, 0])]
                meas = arr[arr[:, 1] >= measure_from]
                lat = (meas[:, 3] - meas[:, 1]) / 1e6
                st = meas[:, 4]              # 0 ok · 1 timeout engine · 2 lỗi · 3 quá hạn khi tới lượt (không gửi)
                n_to = int(((st == 1) | (st == 3) | ((st == 0) & (lat > pc.timeout_ms))).sum())
                n_err = int((st == 2).sum())
                lat = np.where((st != 0) | (lat > pc.timeout_ms), pc.timeout_ms, lat)
                raw = (meas[:, 3] - meas[:, 1]) / 1e6      # latency THẬT, chưa kẹp về timeout
                s = latency_stats(lat, pc.timeout_ms, n_to, n_err, pc.bootstrap, cfg.run.seed + SEED_OFFSET_BOOT + int(rate) + rep)
                # Tách "timeout" thành ba thứ khác nhau — đọc gộp sẽ hiểu sai (engine timeout vs chờ trong hàng đợi client):
                #   engine_timeout: statement/request timeout của engine nổ · skipped_late: quá hạn khi tới lượt, KHÔNG gửi
                #   ok_but_late: engine trả kết quả ĐÚNG nhưng tổng thời gian từ lúc lẽ ra gửi đã vượt timeout
                s["status_split"] = {"ok_in_budget": int(((st == 0) & (raw <= pc.timeout_ms)).sum()),
                                     "ok_but_late": int(((st == 0) & (raw > pc.timeout_ms)).sum()),
                                     "engine_timeout": int((st == 1).sum()), "error": int((st == 2).sum()),
                                     "skipped_late": int((st == 3).sum())}
                done = raw[st == 0]
                s["uncapped_ms"] = {"p50": float(np.percentile(raw, 50)), "p99": float(np.percentile(raw, 99)),
                                    "max": float(raw.max()),
                                    "engine_service_p50": float(np.percentile(meas[st == 0][:, 3] - meas[st == 0][:, 2], 50) / 1e6)
                                    if len(done) else None}
                span = (meas[:, 1].max() - meas[:, 1].min()) / 1e9 if len(meas) > 1 else 0.0
                win = (meas[:, 3].max() - meas[:, 1].min()) / 1e9 if len(meas) else 0.0
                good = int(((st == 0) & ((meas[:, 3] - meas[:, 1]) / 1e6 <= pc.timeout_ms)).sum())
                disp = (meas[:, 2] - meas[:, 1]) / 1e6
                s.update({"rate_qps": rate, "rep": rep, "offered_qps": (len(meas) - 1) / span if span else None,
                          "achieved_qps": good / win if win > 0 else None,
                          "duration_s": duration_s, "warmup_s": warmup_s, "dispatch_delay_p99_ms": float(np.percentile(disp, 99)),
                          "short_results": int(((st == 0) & (meas[:, 5] < pc.k)).sum()), "wall_s": round(time.perf_counter() - t_start, 1),
                          **sched_info})
                levels.append(s)
                df = pd.DataFrame(meas, columns=["i", "sched_ns", "start_ns", "end_ns", "status", "n_results"])
                df["rate_qps"], df["rep"] = rate, rep
                samples.append(df)
                print(f"  {engine} {scale} @{rate:g} QPS rep {rep}: n={s['n']} P50={s['p50']:.2f} P95={s['p95']:.2f} "
                      f"P99={s['p99']:.2f} [{s['p99_ci95'][0]:.2f}, {s['p99_ci95'][1]:.2f}] P99.9={s['p99_9']:.2f} ms · "
                      f"timeout {s['timeouts']} · lỗi {s['errors']} · lịch trễ p99 {sched_info['scheduler_late_p99_ms']:.2f} ms")
                time.sleep(DRAIN_PAUSE_S)
            if partial:
                break
    finally:
        pool.stop()
        if sampler:
            sampler.mark("idle")
        if own_sampler:
            sampler.stop()

    def med_level(rate: float) -> dict | None:
        ls = [x for x in levels if x["rate_qps"] == rate]
        if not ls:
            return None
        return sorted(ls, key=lambda x: x["p99"])[len(ls) // 2]          # median theo P99 các lần lặp
    b1 = med_level(pc.b1_rate_qps)
    thr = (cfg.scoring.model_extra or {}).get("metrics", {}).get("B1", {}).get("pass", {}).get(scale)
    ok_rates = [r for r in sorted(set(x["rate_qps"] for x in levels)) if thr is not None and med_level(r)["p99"] <= thr]
    metrics: dict[str, Any] = {
        "query_config": qname, "query_params": qp, "k": pc.k, "workers": pc.workers, "spawn_s": round(spawn_s, 1),
        "load_model": pc.load_model, "levels": levels, "harness": tuning, "transport_floor": tf,
        "B1": {"rate_qps": pc.b1_rate_qps, "p99_ms": b1["p99"], "p99_ci95": b1["p99_ci95"], "p50_ms": b1["p50"],
               "p95_ms": b1["p95"], "p99_9_ms": b1["p99_9"], "timeout_rate": b1["timeout_rate"], "threshold_ms": thr,
               "pass": (b1["p99"] <= thr) if thr is not None else None} if b1 else None,
        "B2_curve": [{"rate_qps": x["rate_qps"], "p50_ms": x["p50"], "p99_ms": x["p99"], "rep": x["rep"]} for x in levels],
        "B2_max_qps_under_B1": max(ok_rates) if ok_rates else None,
    }
    if engine != "null":
        ld = read_result(run_id, engine, scale, "load")
        if ld and ld.get("status") == "ok":
            lm = ld["metrics"]
            metrics["B3"] = {"minutes": lm["b3_minutes"], "load_s": lm["load_s"], "index_s": lm["index_s"],
                             "vectors_per_s": lm["vectors_per_s"], "index_config": lm["index_config"]}
    status = "partial" if partial else "ok"
    if levels and any(x["error_rate"] > 0.01 for x in levels) and engine != "null":
        metrics["note_error_rate"] = "có mức tải tỷ lệ lỗi/timeout > 1%"
    if engine == "null":
        worst = max((x["p99"] for x in levels), default=float("inf"))
        metrics["harness_check"] = {"p99_ms": worst, "max_p99_ms": pc.harness_max_p99_ms, "pass": worst < pc.harness_max_p99_ms}
        status = "ok" if metrics["harness_check"]["pass"] else "fail"
    p = write_result(run_id, engine, scale, "perf", status=status, metrics=metrics, started_at=started, engine_version=ev,
                     client_version=cv, engine_limits=engine_limits)
    if samples:
        pd.concat(samples).to_parquet(p.with_name("perf_queries.parquet"), index=False)
    if own_sampler:
        dump_json(p.with_name("resources.json"), {"C1": sampler.summary(), "phases": sorted({s[4] for s in sampler.samples})})
    if engine == "null":
        hc = metrics["harness_check"]
        print(f"harness null: P99 {hc['p99_ms']:.3f} ms (< {hc['max_p99_ms']} ms: {'PASS' if hc['pass'] else 'FAIL'})")
        return 0 if hc["pass"] else 2
    return 0
