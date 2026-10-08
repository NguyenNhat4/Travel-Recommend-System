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
import hashlib
import inspect
import json
from datetime import datetime, timedelta

from src.backend.app.application.ports import CdpHistoryReader, UnitIndex, VectorSearchPort
from src.backend.app.application.recommendation import BuildPopularity, RecommendForUser
from src.backend.app.domain.recommendation import Popularity

from .events import parse_ts


#: Cửa sổ đếm purchase của thành phần pop trong engine và của hai baseline popularity = mặc định
#: `Popularity.unit_scores(window_days=…)` — đọc từ chữ ký production để `configHash` đổi khi production đổi, không chép số.
POPULARITY_WINDOW_DAYS: int = inspect.signature(Popularity.unit_scores).parameters["window_days"].default
#: Cửa sổ purchase dựng bảng phổ biến = mặc định `CdpHistoryReader.purchase_events(since_days=…)` của port backend.
PURCHASE_LOOKBACK_DAYS: int = inspect.signature(CdpHistoryReader.purchase_events).parameters["since_days"].default


class LeakageError(AssertionError):
    """Dữ liệu từ mốc đánh giá trở đi sắp lọt vào engine."""


class OfflineCdpReader:
    """`CdpHistoryReader` chỉ biết purchase trước `as_of`; không cho engine đọc lịch sử theo khách."""

    def __init__(self, purchases_before: list[dict], as_of: datetime):
        self._rows, self.as_of = purchases_before, as_of

    def purchase_events(self, since_days: int = PURCHASE_LOOKBACK_DAYS) -> list[dict]:
        lo = self.as_of - timedelta(days=since_days)   # cửa sổ tính từ as_of, không theo giờ thật
        return [dict(e) for e in self._rows if parse_ts(e["timestamp"]) >= lo]

    def events_for_user(self, cdp_user_id: str) -> list[dict]:
        raise LeakageError("harness phải truyền events= đã cắt theo as_of; engine không được tự đọc CDP khi offline")

    def all_events(self, until: datetime | None = None) -> list[dict]:
        raise LeakageError("engine không được đọc toàn bộ CDP khi offline")

    def all_profiles(self) -> list[dict]:
        raise LeakageError("engine không được đọc cdp.profiles khi offline (lifecycle tính tại as_of DB, có purchase bị giấu)")


class OfflineEngine:
    """`mode="eval"` (mặc định, kế hoạch Day 3 B / quyết định 30/09): bỏ cap `MAX_PER_VERTICAL` để k = 20 có đủ 20 món —
    5 taxonomy × 2 chỉ được ≤ 10, thực tế 4,8 món, nên Recall@20 = Recall@10. `mode="prod"`: đúng list production
    (cap 2 mỗi taxonomy) — dùng cho arm `engine_prod` và lệnh `user`."""

    def __init__(self, index: UnitIndex, vectors: VectorSearchPort, purchases: list[dict], *,
                 candidate_k: int = 200, popular_k: int = 50, popularity_cache: int = 8, mode: str = "eval",
                 explore_fill: bool = True):
        """`explore_fill`: ô khám phá khi có chuyến mở (FR-REC-02, 09/10) — mặc định như production (`Settings` bật);
        False = tắt như `RECOMMEND_EXPLORE_FILL=false`, để đo riêng phần ô B (ghi vào `engine_config`)."""
        if mode not in ("eval", "prod"):
            raise ValueError(f"mode phải là eval | prod, gặp {mode!r}")
        self.explore_fill = explore_fill
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

    def recommend(self, cdp_user_id: str, as_of: datetime, k: int, events: list[dict],
                  popularity_as_of: datetime | None = None) -> dict:
        """`popularity_as_of`: mốc dựng bảng phổ biến khi khác `as_of` — production neo bảng này ở lúc khởi động / nạp lại
        (900 s), không ở lúc request; parity truyền mốc khởi động backend để trung hoà (mặc định = as_of)."""
        late = [e for e in events if parse_ts(e["timestamp"]) >= as_of]
        if late:
            raise LeakageError(f"{len(late)} event của {cdp_user_id} ở hoặc sau as_of {as_of.isoformat()} "
                               f"(đầu tiên {late[0].get('eventName')} {late[0]['timestamp']})")
        from src.backend.app.domain.recommendation.profile import MAX_PER_VERTICAL
        engine = RecommendForUser(self.index, self.vectors, self.reader_at(as_of), self.popularity_at(popularity_as_of or as_of),
                                  candidate_k=self.candidate_k, popular_k=self.popular_k,
                                  max_per_vertical=None if self.mode == "eval" else MAX_PER_VERTICAL,
                                  explore_fill=self.explore_fill)
        return engine(cdp_user_id, k=k, now=as_of, events=[dict(e) for e in events])


def engine_config(engine: OfflineEngine) -> dict:
    """Ảnh chụp mọi hằng số quyết định xếp hạng (B3, 01/10): mọi hằng viết hoa của `domain/recommendation/profile.py`
    (trọng số loại event, cửa sổ ngắn/dài, tuổi trip mở, dormant, cap lặp, λ MMR, cap taxonomy…) + tham số của harness.
    `summary.json` ghi cùng `configHash` để hai run chỉ so được khi cùng hash (quy ước tuning:
    `docs/spec/bench/recsys-offline-eval.md` §3.1)."""
    from src.backend.app.domain.recommendation import profile
    consts = {name: value for name, value in sorted(vars(profile).items())
              if name.isupper() and isinstance(value, (int, float, str, dict, tuple, list)) and not isinstance(value, bool)}
    return {"mode": engine.mode, "candidateK": engine.candidate_k, "popularK": engine.popular_k,
            "maxPerVertical": None if engine.mode == "eval" else profile.MAX_PER_VERTICAL,
            "exploreFill": engine.explore_fill,
            "popularityWindowDays": POPULARITY_WINDOW_DAYS, "purchaseLookbackDays": PURCHASE_LOOKBACK_DAYS,
            "profile": consts}


def config_hash(config: dict) -> str:
    """sha256 của JSON chuẩn hoá (khoá sắp xếp), 8 ký tự đầu."""
    return hashlib.sha256(json.dumps(config, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")).hexdigest()[:8]
