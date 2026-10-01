"""Port đọc câu truy vấn thật (`app.search_logs`) cho prewarm cache vector truy vấn."""
from __future__ import annotations

from typing import Protocol


class SearchLogReader(Protocol):
    def head_queries(self, *, days: int, limit: int) -> list[str]:
        """Câu được tìm nhiều nhất trong `days` ngày gần nhất, tối đa `limit` câu, phổ biến nhất trước. Lỗi kho thì trả
        rỗng (prewarm không được làm hỏng khởi động)."""
        ...
