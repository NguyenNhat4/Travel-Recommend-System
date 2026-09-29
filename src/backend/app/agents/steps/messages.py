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
        "invalid_duration": "Lịch trình hỗ trợ từ {min_days} đến {max_days} ngày.",
        "llm_understand": "Chưa thể hiểu yêu cầu lúc này. Vui lòng thử lại.",
        "missing_both": "Bạn muốn đi đâu và dự định đi trong mấy ngày (từ {min_days} đến {max_days} ngày)?",
        "missing_destination": "Bạn muốn đi du lịch ở tỉnh hoặc thành phố nào?",
        "missing_days": "Bạn dự định đi trong mấy ngày, hoặc từ ngày nào đến ngày nào?",
        "suggest_form": "Mình đã điền sẵn một vài gợi ý cho chuyến đi bên dưới. "
                        "Bạn chỉnh lại theo nhu cầu rồi bấm xác nhận giúp mình nhé.",
        "missing_trip_details": "Để lên lịch sát hơn, bạn cho mình biết thêm {details} nhé. "
                                "Mục nào chưa rõ thì cứ nói, mình vẫn lên lịch được.",
        "detail_startDate": "ngày khởi hành",
        "detail_party": "số người lớn và trẻ em",
        "detail_budget": "ngân sách tổng",
        "detail_joiner": ", ",
        "unsupported": "Rất tiếc, hiện mình chưa có dịch vụ tại {destination}. Các điểm đến mình đang hỗ trợ: "
                       "{destinations}. Bạn muốn lên kế hoạch cho điểm đến nào trong danh sách này?",
        "suggestion_hotel": "Thử bỏ yêu cầu khách sạn cụ thể",
        "suggestion_price": "Thử tăng ngân sách khách sạn tối đa",
        "suggestion_star_rating": "Thử giảm yêu cầu số sao khách sạn",
        "suggestion_activity": "Thử bỏ yêu cầu hoạt động cụ thể",
        "suggestion_taxonomy": "Thử bỏ bớt loại dịch vụ đã loại trừ",
        "suggestion_generic": "Thử đổi điểm đến hoặc điều chỉnh thời gian chuyến đi",
        "no_results": "Chưa tìm thấy sản phẩm phù hợp trong dữ liệu hiện có. Bạn có thể điều chỉnh yêu cầu.",
        "no_results_date": "Hiện chưa có sản phẩm ở {destination} mở bán cho ngày {date}. "
                           "Bạn có thể chọn một trong các gợi ý bên dưới.",
        # Các câu dưới đây được gửi lại làm lượt chat kế tiếp khi người dùng bấm gợi ý: phải là câu yêu cầu đủ ý.
        "suggestion_trip": "Đi {destination} {days} ngày",
        "suggestion_trip_date": "Đi {destination} {days} ngày từ ngày {date}",
    },
    "en": {
        "conversation_not_found": "The conversation does not exist or has expired.",
        "invalid_override": "The itinerary update is invalid.",
        "invalid_intent": "The trip information could not be validated.",
        "invalid_duration": "Itineraries support trips from {min_days} to {max_days} days.",
        "llm_understand": "I cannot understand the request right now. Please try again.",
        "missing_both": "Where would you like to go, and for how many days ({min_days} to {max_days})?",
        "missing_destination": "Which city or province would you like to visit?",
        "missing_days": "How many days will your trip last, or what are your start and end dates?",
        "suggest_form": "I have filled in a few suggestions for your trip below. "
                        "Adjust anything you like, then confirm.",
        "missing_trip_details": "To plan this better, could you tell me {details}? "
                                "If any of it is not decided yet, just say so and I will still plan the trip.",
        "detail_startDate": "your departure date",
        "detail_party": "how many adults and children are going",
        "detail_budget": "your total budget",
        "detail_joiner": ", ",
        "unsupported": "Sorry, I don't have any services in {destination} yet. The destinations I can plan for: "
                       "{destinations}. Which one would you like to plan a trip to?",
        "suggestion_hotel": "Try dropping the specific hotel requirement",
        "suggestion_price": "Try raising the maximum hotel budget",
        "suggestion_star_rating": "Try lowering the minimum hotel star rating",
        "suggestion_activity": "Try dropping the specific activity requirement",
        "suggestion_taxonomy": "Try removing some of the excluded service types",
        "suggestion_generic": "Try a different destination or adjust the trip dates",
        "no_results": "I could not find matching products in the current data. You can adjust your request.",
        "no_results_date": "There are no products in {destination} on sale for {date} yet. "
                           "You can pick one of the suggestions below.",
        "suggestion_trip": "A {days}-day trip to {destination}",
        "suggestion_trip_date": "A {days}-day trip to {destination} starting on {date}",
    },
}

# Câu cố định dùng khi LLM không khả dụng hoặc khi luật không được để LLM tự diễn đạt.
CLARIFY_CONFLICT = ("Thông tin chuyến đi đang chưa rõ hoặc mâu thuẫn. "
                    "Bạn xác nhận lại điểm đến và thời gian giúp tôi nhé?")
CLARIFY_UNVERIFIED = ("Điều kiện bắt buộc bạn yêu cầu chưa có dữ liệu để xác minh. "
                      "Bạn có muốn bỏ điều kiện đó hoặc cung cấp thêm thông tin không?")
CLARIFY_CONSTRAINT = ("Không tìm thấy sản phẩm đáp ứng điều kiện bắt buộc trong dữ liệu hiện có. "
                      "Bạn có muốn điều chỉnh điều kiện hoặc chọn phương án thay thế không?")
REFUSAL = "Tôi hỗ trợ tư vấn lịch trình du lịch. Bạn muốn lên kế hoạch chuyến đi nào?"
FALLBACK = ("Chưa thể dựng lịch trình đã kiểm tra. Các sản phẩm dưới đây là ứng viên tham khảo; "
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
