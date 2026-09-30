"""Hiện thực `CallTelemetry` trong bộ nhớ tiến trình (docs/prd/deployment-plan.md §5).

Vòng đệm N sự kiện gần nhất (seq tăng dần để monitor lấy phần mới) cộng tổng hợp theo (source, kind, name): số lần,
lỗi, thời gian (p50 / p95 trên 500 lần gần nhất). Mất khi restart — đủ cho giám sát trực tiếp, không phải lưu trữ.
"""
from __future__ import annotations

import threading
import time
from collections import deque
from datetime import datetime, timezone
from typing import Any

WINDOW = 500


def _percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return round(ordered[min(len(ordered) - 1, int(q * len(ordered)))], 1)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class InMemoryCallTelemetry:
    def __init__(self, capacity: int = 2000):
        self._events: deque[dict] = deque(maxlen=capacity)
        self._stats: dict[tuple, dict] = {}
        self._seq = 0
        self._lock = threading.Lock()
        self._catalog: dict[str, Any] = {"loadedAt": None, "products": None, "reloads": 0}
        self._started = time.time()

    def record(self, event: dict[str, Any]) -> None:
        with self._lock:
            self._seq += 1
            item = {"seq": self._seq, "at": _now(), **event}
            self._events.append(item)
            key = (item.get("source") or "unknown", item.get("kind") or "?", item.get("name") or "?")
            stat = self._stats.setdefault(key, {"count": 0, "errors": 0, "ms": deque(maxlen=WINDOW), "last": None})
            stat["count"] += 1
            if item.get("status") not in ("ok", None) and not (isinstance(item.get("status"), int)
                                                                and item["status"] < 500):
                stat["errors"] += 1
            if isinstance(item.get("ms"), (int, float)):
                stat["ms"].append(float(item["ms"]))
            stat["last"] = item["at"]

    def set_catalog(self, products: int | None) -> None:
        with self._lock:
            self._catalog = {"loadedAt": _now(), "products": products, "reloads": self._catalog["reloads"] + 1}

    def _summary(self) -> list[dict]:
        rows = []
        for (source, kind, name), s in sorted(self._stats.items()):
            ms = list(s["ms"])
            rows.append({"source": source, "kind": kind, "name": name, "count": s["count"], "errors": s["errors"],
                         "p50Ms": _percentile(ms, 0.5), "p95Ms": _percentile(ms, 0.95),
                         "avgMs": round(sum(ms) / len(ms), 1) if ms else None, "lastAt": s["last"]})
        return rows

    def snapshot(self, after: int = 0, limit: int = 200) -> dict[str, Any]:
        limit = max(1, min(int(limit), 1000))
        with self._lock:
            events = [e for e in self._events if e["seq"] > after][-limit:]
            return {"lastSeq": self._seq, "startedAt": datetime.fromtimestamp(self._started, timezone.utc).isoformat(),
                    "catalog": dict(self._catalog), "summary": self._summary(), "events": events}

    def prometheus(self) -> str:
        """`GET /metrics` dạng text của Prometheus."""
        with self._lock:
            summary, catalog = self._summary(), dict(self._catalog)
        lines = ["# HELP vota_calls_total Số lần gọi theo nguồn (web/agent), loại (http/tool) và tên.",
                 "# TYPE vota_calls_total counter"]
        esc = lambda v: str(v).replace("\\", "\\\\").replace('"', '\\"')  # noqa: E731
        for r in summary:
            labels = f'source="{esc(r["source"])}",kind="{esc(r["kind"])}",name="{esc(r["name"])}"'
            lines.append(f"vota_calls_total{{{labels}}} {r['count']}")
        lines += ["# HELP vota_call_errors_total Lần gọi lỗi (HTTP 5xx hoặc công cụ agent lỗi).",
                  "# TYPE vota_call_errors_total counter"]
        for r in summary:
            labels = f'source="{esc(r["source"])}",kind="{esc(r["kind"])}",name="{esc(r["name"])}"'
            lines.append(f"vota_call_errors_total{{{labels}}} {r['errors']}")
        lines += ["# HELP vota_call_duration_ms Thời gian xử lý (ms) trên 500 lần gần nhất.",
                  "# TYPE vota_call_duration_ms summary"]
        for r in summary:
            labels = f'source="{esc(r["source"])}",kind="{esc(r["kind"])}",name="{esc(r["name"])}"'
            for q, key in (("0.5", "p50Ms"), ("0.95", "p95Ms")):
                if r[key] is not None:
                    lines.append(f'vota_call_duration_ms{{{labels},quantile="{q}"}} {r[key]}')
        lines += ["# HELP vota_catalog_products Số sản phẩm của bản recsys/catalog đang nạp trong bộ nhớ.",
                  "# TYPE vota_catalog_products gauge",
                  f"vota_catalog_products {catalog['products'] if catalog['products'] is not None else 'NaN'}",
                  "# TYPE vota_catalog_reloads_total counter", f"vota_catalog_reloads_total {catalog['reloads']}"]
        return "\n".join(lines) + "\n"
