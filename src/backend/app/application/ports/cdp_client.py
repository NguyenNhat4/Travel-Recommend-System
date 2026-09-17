"""Ports to the CDP (system of record for user events and profiles).

Business logic depends on these interfaces only. Today they are backed by src/cdp_clone over HTTP;
a production adapter replaces them without touching use cases (handbook §3, ARCHITECTURE.md §9).
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


class BrowseEventRecorder(Protocol):
    def record(self, event: BrowseEvent) -> None:
        """Hand off without waiting for CDP. Never raises because CDP is slow or down."""
        ...
