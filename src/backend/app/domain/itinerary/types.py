"""Named shapes for the itinerary agent's internal working data.

Some of these mirror a contract schema in `src/shared/contracts/schemas/itinerary-agent.yaml`
(`TripIntent`, `Party`, `ItineraryPlan` -> `Plan`, `ItineraryDay` -> `DayPlan`, `ItineraryStay` ->
`Stay`, `ItinerarySlot` -> `SlotItem`, `ItineraryWarning` -> `PlanWarning`) because the domain layer
builds exactly that wire shape field-by-field — there is no separate domain model plus serializer
step, so a mismatch here already breaks `application/itinerary/contracts.py`'s runtime
`valid("ItineraryResponse", ...)` check and the grounding tests, not just this file. These are worth
keeping in sync by hand: few fields, stable, one small schema each.

What is deliberately left `dict[str, Any]` instead: `ProductSummary`, `ProductDetail`,
`SearchResponse`, `RecommendationResponse`, `DestinationListResponse` and the top-level
`ItineraryResponse` envelope (a discriminated union of completed/clarification/no-results/fallback
variants). Those are larger, change on the Search/Recommendation/Catalog side of the contract, not
this one, and are already validated at the same boundary — hand-modeling them here would be a
second copy of someone else's contract, the exact duplication AGENTS.md §2 warns against. Call sites
that pass those payloads around keep `dict[str, Any]`, with a comment naming the contract schema.

`Any` is also still used inside modeled shapes for `attributes` (arbitrary per-taxonomy JSON, same
reason `docs/prd/architecture.md` keeps `cdp.products.attributes` as open JSONB) and for `because`
(`BecauseItem[]`, contract-owned).
"""

from __future__ import annotations

from typing import Any, TypedDict


class Party(TypedDict, total=False):
    adults: int
    children: int


class TripIntent(TypedDict, total=False):
    """`state["intent"]`; see `planning.empty_intent`/`merge_intent`."""

    destination: str | None
    startDate: str | None
    days: int | None
    party: Party | None
    budget: int | None
    interests: list[str]
    pace: str | None


class HotelAttributes(TypedDict, total=False):
    """Mirrors `agents/models.py`'s `HotelAttributes` (the LLM structured-output schema validated in
    `classification.py`) — a fixed set of named flags, not an open bag, so unlike `Product.attributes`
    it does not stay `dict[str, Any]`. Domain can't import the `agents`-layer Pydantic model directly
    (would invert the dependency direction), so this is hand-mirrored the same way `Party`/`TripIntent`
    mirror the contract schema above."""

    oceanView: bool | None
    familyFriendly: bool | None
    privateBeach: bool | None
    pool: bool | None
    kidsPool: bool | None
    kidsClub: bool | None
    spa: bool | None
    nearBeach: bool | None


class Constraints(TypedDict, total=False):
    """Retrieval/composition constraints kept across turns in `state["constraints"]`.

    Not part of the public API contract — derived from the conversation, consumed only by
    `retrieval.collect` and `planning.compose_plan`/`validate_plan`.
    """

    require_hotel: bool
    exclude_products: list[str]
    exclude_taxonomies: list[str]
    specific_hotel: str
    specific_activity: str
    hotel_price_max: float
    hotel_price_unit: str
    price_strict: bool
    star_rating_min: float
    hotel_attributes: HotelAttributes


class Product(TypedDict, total=False):
    """A catalog hit as carried in `state["candidates"]`/`state["details"]`: `ProductSummary`
    (search/recommendation projection) merged with `ProductDetail` fields once hydrated. `attributes`
    stays an open bag — see module docstring."""

    productId: str
    name: str
    taxonomy: str
    destination: str
    unitPrice: float | None
    currency: str
    priceUnit: str
    available: bool
    availableFrom: str
    availableTo: str
    imageUrl: str
    rating: float
    reviewCount: int
    attributes: dict[str, Any]
    because: list[dict[str, Any]]
    description: str


Candidates = dict[str, Product]
"""`state["candidates"]`: productId -> `Product`."""

Sources = dict[str, str]
"""`state["sources"]`: productId -> `"search"` | `"recommendation"` (which tool call grounded it)."""


class SlotItem(TypedDict, total=False):
    """One rendered day slot in `Plan.days[].slots`, as built by `render_proposal`."""

    time: str
    activityType: str | None
    product: Product | None
    note: str
    source: str | None
    because: list[dict[str, Any]]


class DayPlan(TypedDict, total=False):
    day: int
    date: str
    slots: list[SlotItem]


class Stay(TypedDict, total=False):
    product: Product
    nights: int
    note: str
    source: str
    because: list[dict[str, Any]]


class Plan(TypedDict, total=False):
    """The itinerary proposal built by `render_proposal`, checked by `validate_plan`."""

    stay: Stay
    days: list[DayPlan]
    bookableCount: int
    estimatedTotal: int | None
    currency: str
    budgetStatus: str
    priceAsOf: str | None


class ProposedSlot(TypedDict, total=False):
    """One entry of `compose_plan`'s internal proposal, before `render_proposal` groundtruths it
    against `candidates` and turns it into a `SlotItem`."""

    day: int
    note_kind: str
    activity_type: str | None
    product_id: str | None
    time: str


class Proposal(TypedDict, total=False):
    """Return value of `compose_plan`; input to `render_proposal`."""

    stay_id: str | None
    slots: list[ProposedSlot]


class ToolErrorPayload(TypedDict):
    """`ToolError.as_dict()` / product-detail hydration failure, as kept in `state["detail_errors"]`
    and inside `ToolResult["error"]`."""

    code: str
    retryable: bool
    httpStatus: int | None


class ToolCall(TypedDict, total=False):
    """One entry of `state["tool_plan"]`, and `ToolExecutorPort.execute`'s argument — the LLM
    tool-call shape (`id`/`name`/`args`), not to be confused with `ToolResult`'s
    `tool_call_id`/`arguments`. `args` shape is the contract's per-tool schema
    (`tool_contracts.contracts()[name]["arguments"]`), left as `dict[str, Any]` here."""

    id: str
    name: str
    args: dict[str, Any]


class ToolResult(TypedDict, total=False):
    """One entry of `state["tool_results"]`, and `ToolExecutorPort.execute`'s return value.
    `data`/`error` shapes are contract-owned (`SearchResponse` / `RecommendationResponse` /
    `ErrorResponse`), left as `dict[str, Any]`."""

    tool_call_id: str
    name: str
    arguments: dict[str, Any]
    data: dict[str, Any]
    error: ToolErrorPayload
    duration_ms: int


class PlanWarning(TypedDict, total=False):
    """`ItineraryWarning`; entries of `state["warnings"]` / `Plan`'s enclosing response."""

    code: str
    message: str
    productId: str | None


class DropSummary(TypedDict, total=False):
    """Vì sao một taxonomy không còn candidate nào ở lượt này; giá trị của `state["drop_summary"]`.

    `count` là số sản phẩm đúng điểm đến đã tìm thấy rồi bị loại (0 = tìm mà không thấy sản phẩm nào);
    `reason` là mã `PRODUCT_DROPPED_*` phổ biến nhất (None khi `count = 0`); `openFrom`/`openTo` là ngày mở bán
    sớm nhất/muộn nhất của các sản phẩm bị loại vì ngày; `nearestOpenDate` là ngày khởi hành gần nhất có sản phẩm.
    """

    count: int
    reason: str | None
    openFrom: str | None
    openTo: str | None
    nearestOpenDate: str | None


class ToolDefinition(TypedDict):
    """LLM function-calling definition, as returned by `ToolExecutorPort.definitions()`."""

    name: str
    description: str
    parameters: dict[str, Any]
