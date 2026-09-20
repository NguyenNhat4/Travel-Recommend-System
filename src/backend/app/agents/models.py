"""Restricted LLM outputs, distinct from the shared HTTP response contract."""
from datetime import date
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PartyUpdate(StrictModel):
    type: Literal["SOLO", "COUPLE", "FAMILY_WITH_KIDS", "FRIENDS"] | None = None
    adults: int = Field(ge=1, le=100)
    children: int = Field(ge=0, le=100)


class IntentUpdate(StrictModel):
    destination: str | None = Field(default=None, max_length=150)
    startDate: date | None = None
    days: int | None = None
    party: PartyUpdate | None = None
    budget: int | None = Field(default=None, ge=0)
    interests: list[str] | None = Field(default=None, max_length=20)
    pace: Literal["RELAXED", "BALANCED", "PACKED"] | None = None


class HotelAttributes(StrictModel):
    oceanView: bool | None = None
    familyFriendly: bool | None = None
    privateBeach: bool | None = None
    pool: bool | None = None
    kidsPool: bool | None = None
    kidsClub: bool | None = None
    spa: bool | None = None
    nearBeach: bool | None = None


class ConstraintUpdate(StrictModel):
    party_type_hint: Literal["SOLO", "COUPLE", "FAMILY_WITH_KIDS", "FRIENDS"] | None = None
    require_hotel: bool | None = None
    exclude_taxonomies: list[Literal["hotel", "flight", "attraction", "combo", "golf"]] | None = None
    hotel_price_max: int | None = Field(default=None, ge=0)
    hotel_price_unit: Literal["PER_NIGHT", "PER_PERSON", "PER_PACKAGE", "UNKNOWN"] | None = None
    price_strict: bool | None = None
    star_rating_min: float | None = Field(default=None, ge=0, le=5)
    hotel_attributes: HotelAttributes | None = None
    specific_hotel: str | None = Field(default=None, max_length=200)
    specific_activity: str | None = Field(default=None, max_length=200)
    children_ages: list[int] | None = Field(default=None, max_length=20)
    unverified_requirements: list[str] | None = Field(default=None, max_length=20)
    clear_fields: list[Literal["hotel_price_max", "hotel_price_unit", "price_strict", "star_rating_min",
                               "hotel_attributes", "specific_hotel", "specific_activity", "unverified_requirements"]] = Field(default_factory=list)


class Extraction(StrictModel):
    domain: Literal["travel", "conversation", "out_of_domain", "side_effect"]
    patch: IntentUpdate = Field(default_factory=IntentUpdate)
    constraints: ConstraintUpdate = Field(default_factory=ConstraintUpdate)
    end_date: date | None = None
    conflict: bool = False


class ConversationalAnswer(StrictModel):
    message: str = Field(min_length=1, max_length=500)


class ProposedSlot(StrictModel):
    day: int = Field(ge=1, le=7)
    time: Literal["MORNING", "NOON", "AFTERNOON", "EVENING"]
    product_id: str | None = None
    activity_type: Literal["MEAL", "REST", "FREE_TIME", "TRANSFER", "SIGHTSEEING"] | None = None
    note_kind: Literal["VISIT", "RELAX", "FAMILY", "REST", "MEAL", "TRANSFER"] = "VISIT"


class Composition(StrictModel):
    stay_id: str | None = None
    slots: list[ProposedSlot] = Field(default_factory=list, max_length=28)
