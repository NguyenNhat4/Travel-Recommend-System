"""Restricted LLM outputs, distinct from the shared HTTP response contract."""
from datetime import date
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

from src.backend.app.application.itinerary.contracts import bounds, enum_values

# Enums and numeric bounds come from the OpenAPI contract so the model output can never drift from it.
PartyType = Literal[enum_values("PartyType")]
Pace = Literal[enum_values("Pace")]
Taxonomy = Literal[enum_values("Taxonomy")]
PriceUnit = Literal[enum_values("ProductSummary", "priceUnit")]
ADULTS_MIN, ADULTS_MAX = bounds("Party", "adults")
CHILDREN_MIN, CHILDREN_MAX = bounds("Party", "children")
BUDGET_MIN, BUDGET_MAX = bounds("TripIntent", "budget")
STAR_MIN, STAR_MAX = bounds("SearchRequest", "starRatingMin")


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PartyUpdate(StrictModel):
    type: PartyType | None = None
    adults: int = Field(ge=ADULTS_MIN, le=ADULTS_MAX)
    children: int = Field(ge=CHILDREN_MIN, le=CHILDREN_MAX)


class IntentUpdate(StrictModel):
    destination: str | None = Field(default=None, max_length=150)
    startDate: date | None = None
    days: int | None = None
    party: PartyUpdate | None = None
    budget: int | None = Field(default=None, ge=BUDGET_MIN, le=BUDGET_MAX)
    interests: list[str] | None = Field(default=None, max_length=20)
    pace: Pace | None = None


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
    party_type_hint: PartyType | None = None
    require_hotel: bool | None = None
    exclude_taxonomies: list[Taxonomy] | None = None
    hotel_price_max: int | None = Field(default=None, ge=0)
    hotel_price_unit: PriceUnit | None = None
    price_strict: bool | None = None
    star_rating_min: float | None = Field(default=None, ge=STAR_MIN, le=STAR_MAX)
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


class DestinationChoice(StrictModel):
    destination: str | None = Field(default=None, max_length=150)


class ConversationalAnswer(StrictModel):
    message: str = Field(min_length=1, max_length=500)
