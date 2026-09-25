"""Wire models for src/shared/contracts/cdp-clone.openapi.yaml. Field-level rules only; cross-field rules live in domain."""
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel

Taxonomy = Literal["hotel", "flight", "attraction", "combo", "golf"]
EventName = Literal["purchase", "add_to_cart", "product_view", "search"]
LifecycleStage = Literal["new", "active", "dormant", "churned"]


class WireModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")


class UserEventInput(WireModel):
    cdp_user_id: Annotated[str, Field(min_length=1, max_length=64)]
    event_name: EventName
    event_id: Annotated[str, Field(min_length=1, max_length=128)] | None = None
    timestamp: AwareDatetime | None = None
    product_id: Annotated[str, Field(min_length=1, max_length=128)] | None = None
    taxonomy: Taxonomy | None = None
    event_group_id: Annotated[str, Field(min_length=1, max_length=64)] | None = None
    quantity: Annotated[int, Field(ge=1)] | None = None
    unit_price: Annotated[float, Field(ge=0)] | None = None
    using_date: date | None = None
    search_query: Annotated[str, Field(min_length=1, max_length=500)] | None = None


class RecordEventsRequest(WireModel):
    events: Annotated[list[UserEventInput], Field(min_length=1, max_length=100)]


class RecordedEvent(WireModel):
    event_id: str
    status: Literal["created", "duplicate"]


class RecordEventsResponse(WireModel):
    results: list[RecordedEvent]


class UserEvent(WireModel):
    event_id: str
    cdp_user_id: str
    event_name: EventName
    timestamp: datetime
    product_id: str | None
    taxonomy: Taxonomy | None
    event_group_id: str | None
    quantity: int | None
    unit_price: float | None
    using_date: date | None
    search_query: str | None
    cancelled_at: datetime | None


class EventListResponse(WireModel):
    events: list[UserEvent]
    total: int
    limit: int
    offset: int


class ProfileAttributes(WireModel):
    lifecycle_stage: LifecycleStage | None = None
    days_since_last_booking: Annotated[int, Field(ge=0)] | None = None
    lifetime_order_count: Annotated[int, Field(ge=0)] | None = None
    vinclub_tier: Annotated[str, Field(max_length=32)] | None = None
    purchased_verticals: list[Taxonomy] = Field(default_factory=list)
    home_city: Annotated[str, Field(max_length=128)] | None = None
    last_destination: Annotated[str, Field(max_length=128)] | None = None
    email_optin: bool | None = None
    sms_optin: bool | None = None
    push_optin: bool | None = None
    gdpr_optin: bool | None = None

    @field_validator("purchased_verticals")
    @classmethod
    def unique_verticals(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("purchasedVerticals must not repeat")
        return value


class Profile(WireModel):
    cdp_user_id: str
    attributes: ProfileAttributes
    updated_at: datetime
