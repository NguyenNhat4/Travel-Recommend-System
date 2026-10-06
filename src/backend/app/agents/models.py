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
STAR_MIN, STAR_MAX = bounds("SearchRequest", "starRatingMin")


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PartyUpdate(StrictModel):
    type: PartyType | None = None
    # Không chặn giới hạn ở đây: giá trị ngoài giới hạn contract được `extract` báo lại cho người dùng
    # (`invalid_inputs`) thay vì làm hỏng cả lượt trích xuất thành `LLM_UNAVAILABLE`.
    adults: int
    children: int


class IntentUpdate(StrictModel):
    destination: str | None = Field(default=None, max_length=150)
    startDate: date | None = None
    days: int | None = None
    party: PartyUpdate | None = None
    budget: int | None = None
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
    exclude_products: list[str] | None = Field(
        default=None, max_length=20,
        description="productId của sản phẩm đã cho xem ở lượt trước mà người dùng muốn bỏ; "
                    "chỉ được copy nguyên văn từ previous_selection, không tự tạo id.")
    clear_fields: list[Literal["hotel_price_max", "hotel_price_unit", "price_strict", "star_rating_min",
                               "hotel_attributes", "specific_hotel", "specific_activity", "unverified_requirements",
                               "exclude_products"]] = Field(default_factory=list)


class TurnRoute(StrictModel):
    """Nhãn của `classify`: chỉ phân luồng, không trích gì khác."""
    route: Literal["travel", "vague", "conversation", "out_of_scope"]


class Extraction(StrictModel):
    """Output của `extract`: chỉ chạy khi `classify` đã xếp lượt này là `travel`."""
    patch: IntentUpdate = Field(default_factory=IntentUpdate)
    constraints: ConstraintUpdate = Field(default_factory=ConstraintUpdate)
    end_date: date | None = None
    start_date_undecided: bool = Field(
        default=False,
        description="true khi người dùng nói rõ chưa chốt hoặc linh hoạt về ngày đi; không có ngày cũng không có lời này thì false.")
    conflict: bool = False
    change_without_value: list[Literal["destination", "days", "startDate", "party", "budget"]] = Field(
        default_factory=list,
        description="Trường người dùng muốn đổi nhưng chưa nói giá trị mới ('đổi ngày', 'đổi địa điểm'). "
                    "Đã có giá trị mới thì điền patch, không liệt kê ở đây.")
    destination_kind: str | None = Field(
        default=None, max_length=60,
        description="Loại nơi người dùng muốn thay cho tên một địa danh ('biển', 'núi', 'chỗ mát'); null khi "
                    "tin nhắn không nói loại nơi nào hoặc đã nêu một điểm đến hợp với loại đó.")


class DestinationChoice(StrictModel):
    destination: str | None = Field(default=None, max_length=150)


class ConversationalAnswer(StrictModel):
    #: Bản tóm tắt một dòng của `message` (in đậm ở dòng đầu); để trống với chào hỏi, cảm ơn.
    #: Cho phép dài hơn mức hiển thị một chút: `titled()` cắt, không để tiêu đề dài làm hỏng cả câu.
    title: str | None = Field(default=None, max_length=200)
    message: str = Field(min_length=1, max_length=1000)


class ItineraryNarration(StrictModel):
    """Output của `narrate`: lời diễn giải lịch trình đã dựng; tên sản phẩm và giá do backend điền từ dữ liệu."""
    title: str | None = Field(default=None, max_length=200)
    message: str = Field(min_length=1, max_length=3000)
