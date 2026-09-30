"""Bọc engine Recommendation production thành `recommend(cdp_user_id, as_of, k)` gọi trực tiếp, không qua HTTP.

Dùng đúng `RecommendForUser` và `BuildPopularity` của backend (`application/recommendation/use_cases.py`), chỉ thay
nguồn dữ liệu để engine không nhìn thấy gì từ `as_of` trở đi:

- Lịch sử của khách được truyền qua `events=`; harness chặn event `timestamp >= as_of` trước khi gọi vì engine không
  tự loại mà kẹp `days_ago` về 0 (tính như vừa xảy ra).
- Bảng phổ biến dựng từ purchase có `timestamp < as_of` với `now=as_of`. Đường production (`main.py`) dựng popularity
  theo giờ thật và `PostgresCdpReader.purchase_events` không có cận trên — không dùng được cho đánh giá theo mốc.
- `OfflineCdpReader` ném lỗi nếu engine định tự đọc CDP (`events_for_user`), để lỗi nối dây lộ ra ngay.
"""
from __future__ import annotations

import bisect
from datetime import datetime, timedelta

from src.backend.app.application.ports import UnitIndex, VectorSearchPort
from src.backend.app.application.recommendation import BuildPopularity, RecommendForUser
from src.backend.app.domain.recommendation import Popularity

from .events import parse_ts


class LeakageError(AssertionError):
    """Dữ liệu từ mốc đánh giá trở đi sắp lọt vào engine."""


class OfflineCdpReader:
    """`CdpHistoryReader` chỉ biết purchase trước `as_of`; không cho engine đọc lịch sử theo khách."""

    def __init__(self, purchases_before: list[dict], as_of: datetime):
        self._rows, self.as_of = purchases_before, as_of

    def purchase_events(self, since_days: int = 730) -> list[dict]:
        lo = self.as_of - timedelta(days=since_days)   # cửa sổ tính từ as_of, không theo giờ thật
        return [dict(e) for e in self._rows if parse_ts(e["timestamp"]) >= lo]

    def events_for_user(self, cdp_user_id: str) -> list[dict]:
        raise LeakageError("harness phải truyền events= đã cắt theo as_of; engine không được tự đọc CDP khi offline")

    def all_events(self, until: datetime | None = None) -> list[dict]:
        raise LeakageError("engine không được đọc toàn bộ CDP khi offline")


class OfflineEngine:
    """`mode="eval"` (mặc định, kế hoạch Day 3 B / quyết định 30/09): bỏ cap `MAX_PER_VERTICAL` để k = 20 có đủ 20 món —
    5 taxonomy × 2 chỉ được ≤ 10, thực tế 4,8 món, nên Recall@20 = Recall@10. `mode="prod"`: đúng list production
    (cap 2 mỗi taxonomy) — dùng cho arm `engine_prod` và lệnh `user`."""

    def __init__(self, index: UnitIndex, vectors: VectorSearchPort, purchases: list[dict], *,
                 candidate_k: int = 200, popular_k: int = 50, popularity_cache: int = 8, mode: str = "eval"):
        if mode not in ("eval", "prod"):
            raise ValueError(f"mode phải là eval | prod, gặp {mode!r}")
        rows = sorted((e for e in purchases if e.get("eventName") == "purchase"), key=lambda e: parse_ts(e["timestamp"]))
        self.index, self.vectors = index, vectors
        self.candidate_k, self.popular_k, self.mode = candidate_k, popular_k, mode
        self._rows, self._stamps = rows, [parse_ts(e["timestamp"]) for e in rows]
        self._popularity: dict[datetime, Popularity] = {}
        self._cache_size = popularity_cache

    def reader_at(self, as_of: datetime) -> OfflineCdpReader:
        return OfflineCdpReader(self._rows[: bisect.bisect_left(self._stamps, as_of)], as_of)

    def popularity_at(self, as_of: datetime) -> Popularity:
        if as_of not in self._popularity:
            if len(self._popularity) >= self._cache_size:
                self._popularity.pop(next(iter(self._popularity)))
            self._popularity[as_of] = BuildPopularity(self.index, self.reader_at(as_of))(now=as_of)
        return self._popularity[as_of]

    def recommend(self, cdp_user_id: str, as_of: datetime, k: int, events: list[dict]) -> dict:
        late = [e for e in events if parse_ts(e["timestamp"]) >= as_of]
        if late:
            raise LeakageError(f"{len(late)} event của {cdp_user_id} ở hoặc sau as_of {as_of.isoformat()} "
                               f"(đầu tiên {late[0].get('eventName')} {late[0]['timestamp']})")
        from src.backend.app.domain.recommendation.profile import MAX_PER_VERTICAL
        engine = RecommendForUser(self.index, self.vectors, self.reader_at(as_of), self.popularity_at(as_of),
                                  candidate_k=self.candidate_k, popular_k=self.popular_k,
                                  max_per_vertical=None if self.mode == "eval" else MAX_PER_VERTICAL)
        return engine(cdp_user_id, k=k, now=as_of, events=[dict(e) for e in events])
