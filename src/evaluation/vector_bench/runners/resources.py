"""C1 — sampler `docker stats` cho mọi container của profile (Part 11), chạy nền trong lúc load và perf.

Docker Desktop: stats(stream=False) mất 1–2 s/lần → dùng API streaming, một thread mỗi container, daemon đẩy ~1 frame/s
(nên sampler_interval_s = 1 là tối thiểu). RAM = usage − inactive_file (giống docker CLI, cgroup v2); CPU% như docker CLI.
Đỉnh RAM tính trên TỔNG các container (giá trị gần nhất của từng container).
"""
from __future__ import annotations

import threading
import time
from typing import Any

from .. import lifecycle


class ResourceSampler:
    def __init__(self, engine: str):
        self.engine = engine
        self.samples: list[tuple[float, str, int, float | None, str]] = []   # (t, container, mem, cpu%, phase)
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._threads: list[threading.Thread] = []
        self.phase = "idle"

    def mark(self, phase: str) -> None:
        with self._lock:
            self.phase = phase

    def _run(self, cid: str, name: str) -> None:
        cli = lifecycle.docker_client()
        while not self._stop.is_set():
            try:
                gen = cli.api.stats(cid, stream=True, decode=True)
                try:
                    for fr in gen:
                        if self._stop.is_set():
                            break
                        ms = fr.get("memory_stats") or {}
                        if "usage" not in ms:
                            continue
                        mem = lifecycle.mem_usage_bytes(fr)
                        cpu: float | None = None
                        pre, cur = fr.get("precpu_stats") or {}, fr.get("cpu_stats") or {}
                        if pre.get("system_cpu_usage") and cur.get("system_cpu_usage"):
                            c = lifecycle.cpu_percent(fr)
                            cpu = c if c >= 0 else None
                        with self._lock:
                            self.samples.append((time.time(), name, mem, cpu, self.phase))
                finally:
                    gen.close()
            except Exception:  # noqa: BLE001
                pass
            self._stop.wait(0.5)

    def start(self) -> "ResourceSampler":
        for c in lifecycle.containers(self.engine):
            t = threading.Thread(target=self._run, args=(c.id, c.name), daemon=True, name=f"stats-{c.name}")
            t.start()
            self._threads.append(t)
        return self

    def stop(self) -> None:
        self._stop.set()
        for t in self._threads:
            t.join(3.0)

    def summary(self, phases: set[str] | None = None) -> dict[str, Any]:
        with self._lock:
            ss = sorted(s for s in self.samples if phases is None or s[4] in phases)
        last: dict[str, int] = {}
        peak = 0
        cpu_by_sec: dict[int, float] = {}
        for t, name, mem, cpu, _ in ss:
            last[name] = mem
            peak = max(peak, sum(last.values()))
            if cpu is not None:
                cpu_by_sec[int(t)] = cpu_by_sec.get(int(t), 0.0) + cpu
        return {"n_samples": len(ss), "mem_peak_gb": round(peak / 2**30, 3),
                "cpu_pct_mean": round(sum(cpu_by_sec.values()) / len(cpu_by_sec), 1) if cpu_by_sec else None,
                "cpu_pct_max": round(max(cpu_by_sec.values()), 1) if cpu_by_sec else None,
                "containers": sorted(last)}
