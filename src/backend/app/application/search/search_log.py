"""Ghi `app.search_logs` cho /search (kiến trúc search §11 "Log query + query plan"; bật bằng SEARCH_LOG_QUERIES, mặc định tắt).

Ghi log là việc phụ: request chỉ đưa một dòng vào hàng đợi có trần (không chặn, không ném lỗi); một luồng nền ghi qua port
`SearchLogWriter`. Hàng đợi đầy hoặc kho lỗi thì bỏ dòng đó và đếm — không thử lại, không làm chậm hay hỏng response.
Log ứng dụng không chứa câu truy vấn hay danh tính (hop-dong-tich-hop-backend.md §8.6)."""
from __future__ import annotations

import logging
import threading
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from src.backend.app.application.ports.search_logs import SearchLogEntry, SearchLogWriter

logger = logging.getLogger("uvicorn.error")

#: Số dòng tối đa đang chờ ghi; quá thì bỏ (như hàng đợi browse event của CDP).
MAX_PENDING = 1000


def search_log_entry(query: str, response: Mapping[str, Any], *, request_filters: Mapping[str, Any] | None = None,
                     cdp_user_id: str | None = None, session_id: str | None = None) -> SearchLogEntry:
    """Dòng log từ response /search. `filters` = `appliedFilters.hard` của response, cộng `queryPlan.confidence` và các
    tham số lọc của request (`request_filters`, ví dụ taxonomy / destination) mà response không echo — [C6] không phát
    `appliedFilters` cho request web chỉ có taxonomy/destination khi cờ suy luận tắt. Không có gì → NULL."""
    diagnostics = response.get("diagnostics") or {}
    filters: dict[str, Any] = {k: v for k, v in (request_filters or {}).items() if v is not None}
    filters.update((response.get("appliedFilters") or {}).get("hard") or {})
    confidence = (diagnostics.get("queryPlan") or {}).get("confidence")
    if confidence is not None:
        filters["confidence"] = confidence
    latency = diagnostics.get("latencyMs")
    return SearchLogEntry(
        query=query,
        result_count=int(response.get("total") or 0),
        model_version=str(diagnostics.get("modelVersion") or "none"),
        result_product_ids=tuple(str(r["productId"]) for r in response.get("results") or () if r.get("productId")),
        filters=filters or None,
        latency_ms=int(latency) if isinstance(latency, (int, float)) else None,
        cdp_user_id=cdp_user_id,
        session_id=session_id,
    )


class SearchLogRecorder:
    """Hàng đợi có trần `max_pending` + một luồng ghi. `record` không bao giờ chặn hay ném lỗi."""

    def __init__(self, writer: SearchLogWriter, *, max_pending: int = MAX_PENDING):
        self._writer = writer
        self._slots = threading.BoundedSemaphore(max(1, max_pending))
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="search-log")
        self._lock = threading.Lock()
        self.written = self.failed = self.dropped = 0

    def record(self, entry: SearchLogEntry) -> bool:
        """True khi dòng đã vào hàng đợi; False khi bị bỏ (hàng đợi đầy hoặc đã đóng)."""
        if not self._slots.acquire(blocking=False):
            self._count("dropped", "queue_full")
            return False
        try:
            self._pool.submit(self._write, entry)
        except Exception:  # noqa: BLE001 — executor đã shutdown
            self._slots.release()
            self._count("dropped", "closed")
            return False
        return True

    def _write(self, entry: SearchLogEntry) -> None:
        try:
            self._writer.write(entry)
        except Exception as exc:  # noqa: BLE001 — chỉ ghi tên lỗi: thông điệp của kho có thể chứa cdp_user_id
            self._count("failed", type(exc).__name__)
        else:
            with self._lock:
                self.written += 1
        finally:
            self._slots.release()

    def _count(self, kind: str, reason: str) -> None:
        with self._lock:
            setattr(self, kind, getattr(self, kind) + 1)
            n = getattr(self, kind)
        logger.warning("search.log.%s reason=%s total=%d", kind, reason, n)

    def stats(self) -> dict[str, int]:
        with self._lock:
            return {"written": self.written, "failed": self.failed, "dropped": self.dropped}

    def close(self, *, wait: bool = False) -> None:
        """Shutdown: `wait=True` ghi nốt hàng đợi (test); mặc định bỏ phần chưa ghi để không giữ tiến trình."""
        self._pool.shutdown(wait=wait, cancel_futures=not wait)
