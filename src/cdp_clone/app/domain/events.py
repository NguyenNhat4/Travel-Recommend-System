"""Business rules for accepting user events. No FastAPI, database or auth imports here."""
from dataclasses import dataclass
from datetime import date, datetime
from typing import Callable, Literal

REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "product_view": ("product_id", "taxonomy"),
    "add_to_cart": ("product_id", "taxonomy", "quantity"),
    "search": ("search_query",),
    "purchase": ("event_id", "product_id", "taxonomy", "event_group_id", "quantity", "unit_price", "using_date"),
}

# Wire names used in error details, so callers see the same names they sent.
WIRE_NAMES = {
    "event_id": "eventId",
    "product_id": "productId",
    "taxonomy": "taxonomy",
    "event_group_id": "eventGroupId",
    "quantity": "quantity",
    "unit_price": "unitPrice",
    "using_date": "usingDate",
    "search_query": "searchQuery",
}


@dataclass(frozen=True)
class EventDraft:
    cdp_user_id: str
    event_name: str
    event_id: str | None = None
    timestamp: datetime | None = None
    product_id: str | None = None
    taxonomy: str | None = None
    event_group_id: str | None = None
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
    cancelled_at: datetime | None = None


class EventRuleError(Exception):
    def __init__(self, code: Literal["VALIDATION_ERROR"], message: str, details: dict):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details


def prepare_events(drafts: list[EventDraft], now: datetime, new_event_id: Callable[[], str]) -> list[UserEvent]:
    """Validate a whole batch and fill eventId/timestamp. Raises on the first bad event so nothing is written."""
    events: list[UserEvent] = []
    seen: set[tuple[str, str]] = set()
    for index, draft in enumerate(drafts):
        missing = [WIRE_NAMES[f] for f in REQUIRED_FIELDS[draft.event_name] if getattr(draft, f) is None]
        if missing:
            raise EventRuleError(
                "VALIDATION_ERROR",
                f"Sự kiện {draft.event_name} thiếu trường bắt buộc.",
                {"eventIndex": index, "fields": missing},
            )
        event_id = draft.event_id or new_event_id()
        key = (draft.cdp_user_id, event_id)
        if key in seen:
            raise EventRuleError(
                "VALIDATION_ERROR",
                "Một eventId xuất hiện hai lần trong cùng request.",
                {"eventIndex": index, "fields": ["eventId"]},
            )
        seen.add(key)
        events.append(
            UserEvent(
                event_id=event_id,
                cdp_user_id=draft.cdp_user_id,
                event_name=draft.event_name,
                timestamp=draft.timestamp or now,
                product_id=draft.product_id,
                taxonomy=draft.taxonomy,
                event_group_id=draft.event_group_id,
                quantity=draft.quantity,
                unit_price=draft.unit_price,
                using_date=draft.using_date,
                search_query=draft.search_query,
            )
        )
    return events
