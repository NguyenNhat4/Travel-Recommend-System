"""Ports to the CDP (system of record for user events and profiles).

Business logic depends on these interfaces only. Week 1 uses LocalCdpClient with the restricted
CDP_DATABASE_URL role; the HTTP adapter can replace it without touching use cases.
"""
from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal, Protocol, Sequence

BrowseEventName = Literal["product_view", "search", "add_to_cart"]


@dataclass(frozen=True)
class PurchaseEvent:
    """One booked item. booking_item_id makes the write idempotent and cancellable."""

    booking_item_id: str
    cdp_user_id: str
    product_id: str
    taxonomy: str
    event_group_id: str
    quantity: int
    unit_price: float
    using_date: date
    timestamp: datetime

    @property
    def event_id(self) -> str:
        return f"purchase:{self.booking_item_id}"


@dataclass(frozen=True)
class BrowseEvent:
    """Behaviour recorded best-effort: losing one is acceptable, blocking the user is not."""

    event_id: str
    cdp_user_id: str
    event_name: BrowseEventName
    timestamp: datetime
    product_id: str | None = None
    taxonomy: str | None = None
    quantity: int | None = None
    unit_price: float | None = None
    using_date: date | None = None
    search_query: str | None = None


@dataclass(frozen=True)
class UserEvent:
    event_id: str
    cdp_user_id: str
    event_name: str
    timestamp: datetime
    product_id: str | None
    taxonomy: str | None
    event_group_id: str | None
    quantity: int | None
    unit_price: float | None
    using_date: date | None
    search_query: str | None


@dataclass(frozen=True)
class CdpProfile:
    cdp_user_id: str
    lifecycle_stage: str | None
    days_since_last_booking: int | None
    lifetime_order_count: int | None
    vinclub_tier: str | None
    purchased_verticals: tuple[str, ...]
    home_city: str | None
    last_destination: str | None
    email_optin: bool | None
    sms_optin: bool | None
    push_optin: bool | None
    gdpr_optin: bool | None
    updated_at: datetime


class CdpUnavailableError(Exception):
    """CDP could not confirm the operation."""


class CdpClient(Protocol):
    async def record_purchases(self, events: Sequence[PurchaseEvent]) -> None:
        """Write purchase events; safe to retry. Raises CdpUnavailableError unless every event is stored."""
        ...

    async def cancel_purchases(self, events: Sequence[PurchaseEvent]) -> None:
        """Compensate purchases whose booking did not commit. Events already absent count as cancelled."""
        ...

    async def record_browse_events(self, events: Sequence[BrowseEvent], *, request_id: str | None = None) -> None:
        """Write browse events in one call. Raises CdpUnavailableError on any failure; callers decide to drop."""
        ...

    async def list_events(
        self,
        cdp_user_id: str,
        *,
        since: datetime | None = None,
        event_name: str | None = None,
        max_events: int = 500,
    ) -> list[UserEvent]:
        """Newest-first history, excluding cancelled events, capped at max_events."""
        ...

    async def get_profile(self, cdp_user_id: str) -> CdpProfile | None:
        ...

    async def ensure_profile(self, cdp_user_id: str, *, home_city: str | None = None) -> None:
        """Tạo hồ sơ CDP cho tài khoản vừa đăng ký; idempotent, đã có thì không lỗi.

        Cần vì app.users.cdp_user_id là NOT NULL REFERENCES cdp.profiles, mà role vota_app của
        backend KHÔNG ghi được cdp.profiles — chỉ cdp_writer ghi được. Đăng ký vì vậy bắt buộc
        đi CDP trước rồi mới INSERT app.users (auth §3.6.3).

        Raises CdpUnavailableError nếu không ghi được; caller không tạo user.
        """
        ...


class BrowseEventRecorder(Protocol):
    def record(self, event: BrowseEvent) -> None:
        """Hand off without waiting for CDP. Never raises because CDP is slow or down."""
        ...


#: Số event tối đa đọc cho một lần tính gợi ý (hop-dong-tich-hop-cdp.md §6, quy tắc 1).
HISTORY_MAX_EVENTS = 500


class CdpHistoryReader(Protocol):
    """Đường ĐỌC đồng bộ của RecSys: lịch sử một khách và purchase toàn hệ thống.

    Trả dict theo tên trường CDP (camelCase: `cdpUserId`, `eventName`, `usingDate`...), đúng hình dạng
    `domain/recommendation` đọc và `HttpCdpClient` sẽ trả khi lên CDP thật.

    Raises CdpUnavailableError khi không kết nối/đọc được kho CDP (sập, timeout); `RecommendForUser`
    bắt lỗi này ở `events_for_user` để lui về `popular`.
    """

    def events_for_user(self, cdp_user_id: str) -> list[dict]:
        """Lịch sử một khách, mới nhất trước (cùng thời điểm thì id nội bộ tăng dần), tối đa `HISTORY_MAX_EVENTS` event."""
        ...

    def purchase_events(self, since_days: int = 730) -> list[dict]: ...

    def all_events(self, until: datetime | None = None) -> list[dict]:
        """Toàn bộ event (mọi khách), chỉ cho đánh giá offline (`src/evaluation/recsys_bench`); không gọi trong request.

        `until` cắt ở kho: chỉ trả event có `timestamp < until`. Thứ tự tất định theo khách, thời điểm, id nội bộ.
        """
        ...

    def all_profiles(self) -> list[dict]:
        """Toàn bộ `cdp.profiles` (camelCase: `cdpUserId`, `lifecycleStage`, `daysSinceLastBooking`, `lifetimeOrderCount`,
        `vinclubTier`, `purchasedVerticals`, `homeCity`, `lastDestination`), chỉ cho đánh giá offline (sanity của harness);
        không gọi trong request. Thứ tự tất định theo `cdpUserId`."""
        ...
