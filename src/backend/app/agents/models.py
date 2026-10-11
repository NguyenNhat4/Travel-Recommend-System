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
    origin: str | None = Field(default=None, max_length=150)


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
    require_flight: bool | None = Field(
        default=None, description="true khi người dùng hỏi rõ vé máy bay hoặc chuyến bay cho chuyến đi này.")
    unverified_requirements: list[str] | None = Field(default=None, max_length=20)
    exclude_products: list[str] | None = Field(
        default=None, max_length=20,
        description="productId của sản phẩm đã cho xem ở lượt trước mà người dùng muốn bỏ; "
                    "chỉ được copy nguyên văn từ previous_selection, không tự tạo id.")
    clear_fields: list[Literal["hotel_price_max", "hotel_price_unit", "price_strict", "star_rating_min",
                               "hotel_attributes", "specific_hotel", "specific_activity", "unverified_requirements",
                               "exclude_products"]] = Field(default_factory=list)


class FareQuestion(StrictModel):
    """Câu hỏi giá/giờ vé máy bay, đã hiểu từ câu chữ lộn xộn (gõ sai, viết tắt, tiếng Anh). Tên nơi là chữ LLM đọc ra;
    code đối chiếu với danh sách điểm đến và tuyến bay của catalog trước khi dùng (`fares.answer`)."""
    origin: str | None = Field(default=None, max_length=60,
                               description="Nơi bay đi, kể cả khi người dùng chỉ nói mình đang ở đó; null khi chưa rõ.")
    destination: str | None = Field(default=None, max_length=60, description="Nơi bay đến; null khi chưa rõ.")
    anywhere: bool = Field(default=False, description="Đi đâu cũng được, chỉ cần so giá giữa các nơi.")
    dearest: bool = Field(default=False, description="Hỏi vé đắt nhất thay cho rẻ nhất.")
    return_leg: bool = Field(default=False, description="Hỏi chuyến về của chuyến đi đang có (chiều ngược lại).")
    other_days: bool = Field(default=False, description="Hỏi ngày khác, chuyến khác của tuyến vừa báo.")
    cheaper: bool = Field(default=False, description="Hỏi còn vé rẻ hơn mức vừa báo không.")
    kind_unclear: bool = Field(default=False,
                               description="Hỏi giá 'vé' mà không rõ vé máy bay, phòng khách sạn hay vé tham quan.")


class TurnRoute(StrictModel):
    """Nhãn của `classify` và ý định đã hiểu của lượt này.

    `explore` (FR-AGT-06): hỏi một điểm đến có gì, khách sạn, điểm tham quan ở đó, khi chưa xin lập lịch.
    `fare`: hỏi giá hoặc giờ vé máy bay, trả lời bằng luật ở nhánh giá vé (`fare` chứa nơi đi, nơi đến…).
    `plan_request`: người dùng xin lập lịch hoặc đồng ý lời mời lập lịch; luật trong `classification.plan_consented`
    nhận các câu đồng ý ngắn trước, LLM chỉ bổ sung cho cách nói khác.
    Các trường còn lại chỉ là cách LLM hiểu câu chữ (tên nơi, thành phố, loại nơi, có hỏi giá không); code đối chiếu với
    catalog rồi mới dùng, không trường nào là dữ liệu sản phẩm.
    """
    route: Literal["travel", "explore", "fare", "vague", "conversation", "out_of_scope"]
    plan_request: bool = Field(
        default=False,
        description="true khi tin nhắn xin lập lịch trình/kế hoạch, hoặc đồng ý lời mời lập lịch của trợ lý.")
    fare: FareQuestion | None = None
    place: str | None = Field(
        default=None, max_length=120,
        description="Nơi cụ thể (điểm tham quan, chợ, khách sạn) mà tin nhắn hỏi tới, viết bằng tên đầy đủ thường dùng.")
    city: str | None = Field(
        default=None, max_length=60,
        description="Thành phố/điểm đến mà tin nhắn nói tới, kể cả khi chỉ nhắc lại qua ngữ cảnh ('ở đó', 'chỗ đó').")
    focus: Literal["hotels", "sights"] | None = Field(
        default=None, description="Tin nhắn chỉ hỏi về chỗ ở (hotels) hoặc chỉ về chỗ chơi (sights).")
    price: Literal["asks", "cheap"] | None = Field(
        default=None, description="asks: hỏi giá, phí, có mất tiền không; cheap: muốn lựa chọn giá rẻ.")
    other_questions: list[str] = Field(
        default_factory=list, max_length=3,
        description="Câu hỏi khác trong cùng tin nhắn chưa thuộc nhãn đã chọn, viết lại ngắn như lời người dùng.")


class Extraction(StrictModel):
    """Output của `extract`: chỉ chạy khi `classify` đã xếp lượt này là `travel`."""
    patch: IntentUpdate = Field(default_factory=IntentUpdate)
    constraints: ConstraintUpdate = Field(default_factory=ConstraintUpdate)
    end_date: date | None = None
    start_date_undecided: bool = Field(
        default=False,
        description="true khi người dùng nói rõ chưa chốt hoặc linh hoạt về ngày đi; không có ngày cũng không có lời này thì false.")
    conflict: bool = False
    change_without_value: list[Literal["destination", "days", "startDate", "party", "budget", "origin"]] = Field(
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
    #: Nút gợi ý LLM đề xuất (FR-AGT-06); code kiểm và cắt còn tối đa 3 (`exploration.checked_suggestions`).
    suggestions: list[str] = Field(default_factory=list, max_length=6)


class ExploreNarration(StrictModel):
    """Output của `explore`: lời dẫn cho các thẻ code đã chọn; số do code điền vào placeholder."""
    title: str | None = Field(default=None, max_length=200)
    message: str = Field(min_length=1, max_length=2000)
    suggestions: list[str] = Field(default_factory=list, max_length=6)


class ItineraryNarration(StrictModel):
    """Output của `narrate`: lời diễn giải lịch trình đã dựng; tên sản phẩm và giá do backend điền từ dữ liệu."""
    title: str | None = Field(default=None, max_length=200)
    message: str = Field(min_length=1, max_length=3000)


class DuplicatePair(StrictModel):
    """Hai mã điểm tham quan cùng một nơi hoặc cùng một trải nghiệm (node `filter`); mã phải có trong danh sách gửi đi.

    `duplicate` đứng sau `reason` để model kết luận sau khi nêu lý do: trace 08/10/2026 có cặp (hòn Thơm, Vinpearl Safari)
    với lý do "là hai địa điểm khác nhau". Chỉ cặp `duplicate=true` được áp.
    """
    ids: list[str] = Field(min_length=2, max_length=2)
    reason: str = Field(default="", max_length=200)
    duplicate: bool


class DuplicatePairs(StrictModel):
    """Output của `filter`: chỉ cặp mã trùng; giữ mã nào do luật (`domain/itinerary/dedupe.py`) quyết định."""
    pairs: list[DuplicatePair] = Field(default_factory=list, max_length=30)
