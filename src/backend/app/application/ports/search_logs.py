"""Port cho `app.search_logs`: đọc câu truy vấn thật (prewarm cache vector truy vấn) và ghi một dòng mỗi lượt /search
(kiến trúc search §11 "Log query + query plan"; bật bằng SEARCH_LOG_QUERIES)."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol


class SearchLogReader(Protocol):
    def head_queries(self, *, days: int, limit: int) -> list[str]:
        """Câu được tìm nhiều nhất trong `days` ngày gần nhất, tối đa `limit` câu, phổ biến nhất trước. Lỗi kho thì trả
        rỗng (prewarm không được làm hỏng khởi động)."""
        ...


@dataclass(frozen=True)
class SearchLogEntry:
    """Một dòng `app.search_logs` (DDL `db/vota_schema.sql`); `search_id` / `created_at` do database sinh."""
    query: str                                        # câu gốc của request (không phải câu đã chuẩn hoá)
    result_count: int                                 # total của response (|R|)
    model_version: str
    result_product_ids: Sequence[str] = ()            # productId của trang trả về, đúng thứ tự
    filters: Mapping[str, Any] | None = None          # appliedFilters.hard (+ taxonomy/destination của request, confidence)
    latency_ms: int | None = None
    cdp_user_id: str | None = None                    # None = khách vãng lai / token không xác thực được
    session_id: str | None = None


class SearchLogWriter(Protocol):
    def write(self, entry: SearchLogEntry) -> None:
        """Ghi một dòng. Được phép ném lỗi — người gọi (`SearchLogRecorder`) chạy ngoài request và nuốt lỗi."""
        ...
