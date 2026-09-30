"""Câu chữ trả về người dùng, và ba helper mọi node dùng chung: message, event, failure."""
from __future__ import annotations

from src.backend.app.application.itinerary.contracts import bounds, error_response
from src.backend.app.application.ports.llm import ChatModelPort

from ..state import make_event

MESSAGES = {
    "vi": {
        "conversation_not_found": "Hội thoại không tồn tại hoặc đã hết hạn.",
        "invalid_override": "Thông tin chỉnh sửa không hợp lệ.",
        "invalid_intent": "Không thể xác nhận thông tin chuyến đi.",
        "llm_understand": "Chưa thể hiểu yêu cầu lúc này. Vui lòng thử lại.",
        "missing_both": "Bạn muốn đi đâu và dự định đi trong mấy ngày (từ {min_days} đến {max_days} ngày)?",
        "missing_destination": "Bạn muốn đi du lịch ở tỉnh hoặc thành phố nào?",
        "missing_days": "Bạn dự định đi trong mấy ngày, hoặc từ ngày nào đến ngày nào?",
        "suggest_form": "Mình đã điền sẵn một vài gợi ý cho chuyến đi bên dưới. "
                        "Bạn chỉnh lại theo nhu cầu rồi bấm xác nhận giúp mình nhé.",
        "missing_trip_details": "Để lên lịch sát hơn, bạn cho mình biết thêm {details} nhé. "
                                "Mục nào chưa rõ thì cứ nói, mình vẫn lên lịch được.",
        # Tiêu đề (dòng in đậm) tóm tắt cả câu; dùng khi LLM không đặt tiêu đề hoặc không viết được câu.
        "title_missing_both": "Cần biết điểm đến và số ngày",
        "title_missing_destination": "Bạn muốn đi đâu?",
        "title_missing_days": "Chuyến đi kéo dài mấy ngày?",
        "title_trip_details": "Thêm vài chi tiết cho chuyến đi",
        "title_form": "Điền nhanh thông tin chuyến đi",
        "title_conflict": "Thông tin chuyến đi chưa khớp nhau",
        "title_unverified": "Chưa xác minh được yêu cầu của bạn",
        "title_out_of_scope": "Ngoài phạm vi hỗ trợ",
        # Lý do của từng giá trị không hợp lệ.
        "invalid_title_many": "Thông tin chuyến đi chưa hợp lệ",
        "invalid_title_past_date": "Ngày khởi hành không hợp lệ",
        "invalid_title_days_out_of_range": "Số ngày không hợp lệ",
        "invalid_title_party_out_of_range": "Số người không hợp lệ",
        "invalid_title_budget_out_of_range": "Ngân sách không hợp lệ",
        "invalid_title_unsupported_destination": "Điểm đến chưa được hỗ trợ",
        "invalid_reason_past_date": "Ngày {value} đã qua rồi nên mình chưa thể lên lịch cho ngày đó. "
                                    "Bạn chọn giúp mình một ngày khởi hành từ hôm nay ({today}) trở đi nhé, "
                                    "ví dụ \"đi từ ngày {today}\".",
        "invalid_reason_days_out_of_range": "Mình lên lịch được cho chuyến đi từ {min_days} đến {max_days} ngày, "
                                            "còn {value} ngày thì nằm ngoài khoảng này. "
                                            "Bạn cho mình biết số ngày trong khoảng đó nhé.",
        "invalid_reason_party_out_of_range": "Chuyến đi cần ít nhất {min_adults} người lớn và số trẻ em không được âm. "
                                             "Bạn cho mình biết lại số người lớn và trẻ em đi cùng nhé.",
        "invalid_reason_budget_out_of_range": "Ngân sách không thể là số âm. Bạn nhập lại tổng ngân sách (VND), "
                                              "hoặc cứ bỏ qua nếu chưa quyết định, mình vẫn lên lịch được.",
        "invalid_reason_unsupported_destination": "Hiện mình chỉ lên kế hoạch cho các chuyến đi trong Việt Nam nên "
                                                  "chưa có dịch vụ tại {value}. Các điểm đến mình đang hỗ trợ: "
                                                  "{destinations}. Bạn muốn lên kế hoạch cho điểm đến nào trong "
                                                  "danh sách này?",
        "detail_startDate": "ngày khởi hành",
        "detail_party": "số người lớn và trẻ em",
        "detail_budget": "ngân sách tổng",
        "detail_joiner": ", ",
        "title_change_without_value": "Bạn muốn đổi thành gì?",
        "change_without_value": "Bạn muốn đổi {fields} thành gì? Ví dụ: \"đổi sang ngày 05/10\" hoặc "
                                "\"đổi sang Đà Nẵng\".",
        "change_field_destination": "điểm đến",
        "change_field_days": "số ngày",
        "change_field_startDate": "ngày khởi hành",
        "change_field_party": "số người",
        "change_field_budget": "ngân sách",
        "suggestion_hotel": "Thử bỏ yêu cầu khách sạn cụ thể",
        "suggestion_price": "Thử tăng ngân sách khách sạn tối đa",
        "suggestion_star_rating": "Thử giảm yêu cầu số sao khách sạn",
        "suggestion_activity": "Thử bỏ yêu cầu hoạt động cụ thể",
        "suggestion_taxonomy": "Thử bỏ bớt loại dịch vụ đã loại trừ",
        "suggestion_generic": "Thử đổi điểm đến hoặc điều chỉnh thời gian chuyến đi",
        "no_results": "**Chưa tìm thấy sản phẩm phù hợp**\nMình chưa tìm thấy sản phẩm phù hợp trong dữ liệu hiện có. "
                      "Bạn có thể điều chỉnh yêu cầu.",
        "no_results_date": "**Chưa có sản phẩm mở bán cho ngày này**\nHiện chưa có sản phẩm ở {destination} mở bán "
                           "cho ngày {date}. Bạn có thể chọn một trong các gợi ý bên dưới.",
        # Các câu dưới đây được gửi lại làm lượt chat kế tiếp khi người dùng bấm gợi ý: phải là câu yêu cầu đủ ý.
        "suggestion_trip": "Đi {destination} {days} ngày",
        "suggestion_trip_date": "Đi {destination} {days} ngày từ ngày {date}",
    },
    "en": {
        "conversation_not_found": "The conversation does not exist or has expired.",
        "invalid_override": "The itinerary update is invalid.",
        "invalid_intent": "The trip information could not be validated.",
        "llm_understand": "I cannot understand the request right now. Please try again.",
        "missing_both": "Where would you like to go, and for how many days ({min_days} to {max_days})?",
        "missing_destination": "Which city or province would you like to visit?",
        "missing_days": "How many days will your trip last, or what are your start and end dates?",
        "suggest_form": "I have filled in a few suggestions for your trip below. "
                        "Adjust anything you like, then confirm.",
        "missing_trip_details": "To plan this better, could you tell me {details}? "
                                "If any of it is not decided yet, just say so and I will still plan the trip.",
        "title_missing_both": "I need your destination and trip length",
        "title_missing_destination": "Where would you like to go?",
        "title_missing_days": "How many days is the trip?",
        "title_trip_details": "A few more trip details",
        "title_form": "Quick trip details form",
        "title_conflict": "Your trip details do not match",
        "title_unverified": "I could not verify your requirement",
        "title_out_of_scope": "Outside what I can help with",
        "title_change_without_value": "What would you like to change it to?",
        "change_without_value": "What would you like to change {fields} to? For example: \"change to 5 Oct\" or "
                                "\"change to Da Nang\".",
        "change_field_destination": "the destination",
        "change_field_days": "the number of days",
        "change_field_startDate": "the departure date",
        "change_field_party": "the number of travellers",
        "change_field_budget": "the budget",
        "invalid_title_many": "Some trip details are not valid",
        "invalid_title_past_date": "Invalid departure date",
        "invalid_title_days_out_of_range": "Invalid number of days",
        "invalid_title_party_out_of_range": "Invalid number of travellers",
        "invalid_title_budget_out_of_range": "Invalid budget",
        "invalid_title_unsupported_destination": "Destination not supported yet",
        "invalid_reason_past_date": "{value} has already passed, so I cannot plan a trip for that day. "
                                    "Please pick a departure date from today ({today}) onward, "
                                    "for example \"leaving on {today}\".",
        "invalid_reason_days_out_of_range": "I can plan trips from {min_days} to {max_days} days, and {value} days "
                                            "is outside that range. Please tell me a number of days within it.",
        "invalid_reason_party_out_of_range": "A trip needs at least {min_adults} adult and a non-negative number of "
                                             "children. Please tell me again how many adults and children are going.",
        "invalid_reason_budget_out_of_range": "The budget cannot be negative. Please enter your total budget (VND), "
                                              "or skip it if it is not decided, and I can still plan the trip.",
        "invalid_reason_unsupported_destination": "Sorry, I only plan trips within Vietnam, so I don't have any "
                                                  "services in {value}. The destinations I can plan for: "
                                                  "{destinations}. Which one would you like to plan a trip to?",
        "detail_startDate": "your departure date",
        "detail_party": "how many adults and children are going",
        "detail_budget": "your total budget",
        "detail_joiner": ", ",
        "suggestion_hotel": "Try dropping the specific hotel requirement",
        "suggestion_price": "Try raising the maximum hotel budget",
        "suggestion_star_rating": "Try lowering the minimum hotel star rating",
        "suggestion_activity": "Try dropping the specific activity requirement",
        "suggestion_taxonomy": "Try removing some of the excluded service types",
        "suggestion_generic": "Try a different destination or adjust the trip dates",
        "no_results": "**No matching products found**\nI could not find matching products in the current data. "
                      "You can adjust your request.",
        "no_results_date": "**No products on sale for this date**\nThere are no products in {destination} on sale "
                           "for {date} yet. You can pick one of the suggestions below.",
        "suggestion_trip": "A {days}-day trip to {destination}",
        "suggestion_trip_date": "A {days}-day trip to {destination} starting on {date}",
    },
}

# Câu cố định dùng khi LLM không khả dụng hoặc khi luật không được để LLM tự diễn đạt. Câu nào có tiêu đề
# thì dòng đầu là `**Tiêu đề**`; câu hỏi lại dự phòng (xung đột, không xác minh được) thêm tiêu đề ở `titled()`.
CLARIFY_CONFLICT = ("Thông tin chuyến đi đang chưa rõ hoặc mâu thuẫn. "
                    "Bạn xác nhận lại điểm đến và thời gian giúp tôi nhé?")
CLARIFY_UNVERIFIED = ("Điều kiện bắt buộc bạn yêu cầu chưa có dữ liệu để xác minh. "
                      "Bạn có muốn bỏ điều kiện đó hoặc cung cấp thêm thông tin không?")
CLARIFY_CONSTRAINT = ("**Chưa có sản phẩm đáp ứng yêu cầu bắt buộc**\n"
                      "Không tìm thấy sản phẩm đáp ứng điều kiện bắt buộc trong dữ liệu hiện có. "
                      "Bạn có muốn điều chỉnh điều kiện hoặc chọn phương án thay thế không?")
REFUSAL = ("**Ngoài phạm vi hỗ trợ**\n"
           "Tôi hỗ trợ tư vấn lịch trình du lịch. Bạn muốn lên kế hoạch chuyến đi nào?")
#: Đầu vào bị guardrail chặn (chèn lệnh, đòi lộ khoá bí mật...): tiêu đề khác với câu hỏi ngoài phạm vi.
REFUSAL_BLOCKED = ("**Mình chưa thể hỗ trợ yêu cầu này**\n"
                   "Tôi hỗ trợ tư vấn lịch trình du lịch. Bạn muốn lên kế hoạch chuyến đi nào?")
FALLBACK = ("**Chưa dựng được lịch trình hoàn chỉnh**\n"
            "Chưa thể dựng lịch trình đã kiểm tra. Các sản phẩm dưới đây là ứng viên tham khảo; "
            "cần kiểm tra lại giá, điều kiện và ngày sử dụng.")
COMPOSE_UNAVAILABLE = "Chưa thể dựng lịch trình lúc này. Vui lòng thử lại."
INVALID_CREDENTIALS = "Thông tin đăng nhập không hợp lệ hoặc đã hết hạn."
PLAN_UNAVAILABLE = "Chưa thể lập kế hoạch truy vấn hợp lệ. Vui lòng thử lại."
SEARCH_UNAVAILABLE = "Chưa thể lấy dữ liệu sản phẩm. Vui lòng thử lại sau."
VALIDATION_FAILED = "Lịch trình chưa vượt qua kiểm tra dữ liệu. Vui lòng thử lại."


def message(state: dict, key: str, **values) -> str:
    """Câu theo ngôn ngữ của hội thoại; `min_days`/`max_days` lấy thẳng từ contract."""
    min_days, max_days = bounds("TripIntent", "days")
    return MESSAGES.get(state.get("language", "vi"), MESSAGES["vi"])[key].format(
        min_days=min_days, max_days=max_days, **values)


#: Tiêu đề dài hơn mức này bị cắt: tiêu đề là bản tóm tắt một dòng, không phải một câu.
MAX_TITLE_CHARS = 80


def titled(title: str | None, body: str) -> str:
    """`**Tiêu đề**` xuống dòng rồi phần chi tiết; không có tiêu đề (rỗng hoặc chỉ dấu `*`) thì giữ nguyên `body`."""
    clean = " ".join((title or "").replace("*", " ").split())[:MAX_TITLE_CHARS].strip()
    return f"**{clean}**\n{body}" if clean else body


def strip_title(text: str) -> str:
    """Bỏ dòng đầu `**Tiêu đề**` khỏi câu của trợ lý; dùng khi đưa lịch sử lại cho LLM."""
    first, sep, rest = text.partition("\n")
    if sep and first.startswith("**") and first.rstrip().endswith("**") and len(first.strip()) > 4:
        return rest.lstrip("\n")
    return text


def display_date(iso: str) -> str:
    """Ngày ISO `yyyy-mm-dd` thành `dd/mm/yyyy` để hiện cho người dùng."""
    year, month, day = iso.split("-")
    return f"{day}/{month}/{year}"


def event(node: str, text: str, **metadata) -> dict:
    """Một dòng trace của node, append vào `state["events"]`."""
    return make_event(node, "completed", text, **metadata)


def failure(state: dict, code: str, text: str, status: int = 503, retryable: bool = False) -> dict:
    """Error Envelope theo contract cộng `http_status`; `decision="error"` chặn các node sau soạn lại."""
    return {"response": error_response(code, text, state.get("request_id", ""), retryable),
            "http_status": status, "decision": "error"}


def chat_model(llm: ChatModelPort | None) -> ChatModelPort:
    """Model do composition root truyền vào; thiếu thì node ghi LLM_UNAVAILABLE như khi provider lỗi."""
    if llm is None:
        raise RuntimeError("LLM chưa được cấu hình cho graph")
    return llm
