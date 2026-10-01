"""Câu chữ trả về người dùng, và ba helper mọi node dùng chung: message, event, failure."""
from __future__ import annotations

import re

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
        "invalid_reason_unsupported_destination": "Mình chưa có dịch vụ tại {value} trong danh sách điểm đến hiện có. "
                                                  "Các điểm đến mình đang hỗ trợ: {destinations}. Bạn muốn lên kế "
                                                  "hoạch cho điểm đến nào trong danh sách này?",
        "title_destination_kind": "Chọn điểm đến hợp ý bạn",
        "destination_kind": "Bạn muốn đi {kind} ở tỉnh hoặc thành phố nào? Cho mình biết tên nơi bạn thích nhé.",
        # Ngữ cảnh cho LLM (`history.llm_context`) và ghi chú từng lượt trợ lý (`turn_notes`): câu ngắn, không có giá.
        "trip_none": "chưa có thông tin chuyến đi",
        "trip_days": "{days} ngày",
        "trip_from": "khởi hành {date}",
        "trip_budget": "ngân sách {budget}",
        "trip_interests": "sở thích: {interests}",
        "trip_missing": "chưa có: {fields}",
        "stage_planned": "đã gửi lịch trình cho chuyến này",
        "stage_collecting": "đang hỏi thông tin chuyến đi, chưa lập lịch trình",
        "stage_start": "đầu hội thoại",
        "note_itinerary": "gửi lịch trình {destination} {days} ngày: {products}",
        "note_no_results": "không tìm thấy sản phẩm phù hợp ở {destination}",
        "note_fallback": "gửi vài sản phẩm tham khảo ở {destination}, chưa dựng được lịch trình",
        "note_unclear": "chưa hiểu tin nhắn, nhờ người dùng nói rõ hơn",
        "note_chat": "trò chuyện",
        "note_refusal": "từ chối: yêu cầu ngoài phạm vi lập lịch trình",
        "note_constraint": "không có sản phẩm đáp ứng yêu cầu bắt buộc, hỏi có nới yêu cầu không",
        "note_invalid": "không dùng được {field} \"{value}\": {reason}",
        "note_reason_past_date": "ngày đã qua",
        "note_reason_days_out_of_range": "ngoài khoảng {min_days}–{max_days} ngày",
        "note_reason_party_out_of_range": "số người không hợp lệ",
        "note_reason_budget_out_of_range": "ngân sách không hợp lệ",
        "note_reason_unsupported_destination": "không có trong danh sách điểm đến",
        "note_ask": "hỏi {fields}",
        "note_change": "hỏi {field} mới",
        "note_change_current": "hỏi {field} mới (hiện là {current})",
        "note_kind": "hỏi chọn điểm đến kiểu \"{kind}\" trong danh sách điểm đến",
        "note_form": "gửi form điền sẵn, còn thiếu {fields}",
        "note_conflict": "hỏi xác nhận vì thông tin chuyến đi chưa khớp",
        "note_unverified": "hỏi về yêu cầu chưa xác minh được",
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
        # Lời diễn giải lịch trình (`narrate`): câu ghi nhận thay đổi và bản dựng bằng luật khi LLM không dùng được.
        "narrate_title": "Lịch trình {days} ngày ở {destination}",
        "narrate_changes": "Mình ghi nhận đổi {changes}. Lịch trình mình gợi ý như sau:",
        "narrate_intro": "Mình gợi ý lịch trình như sau:",
        "change_to_startDate": "ngày đi thành {value}",
        "change_to_destination": "điểm đến thành {value}",
        "change_to_days": "số ngày thành {value} ngày",
        "change_to_party": "số người thành {value}",
        "change_to_budget": "ngân sách thành {value}",
        "party_adults": "{adults} người lớn",
        "party_children": "{children} trẻ em",
        "section_stay": "Nơi nghỉ",
        "section_day": "Ngày {day}",
        "section_cost": "Chi phí dự kiến",
        "section_notes": "Lưu ý",
        "section_more": "Ngoài ra trong lịch trình",
        "section_offers": "Gói nhiều ngày để bạn cân nhắc riêng",
        "offer_days": "dùng trong {days} ngày",
        "offers_question": "Các gói này kéo dài nhiều ngày nên mình chưa xếp vào lịch. Bạn muốn thêm gói nào thì nhắn "
                           "mình, mình sẽ sắp lại các ngày cho vừa nhé.",
        "time_MORNING": "Buổi sáng",
        "time_NOON": "Buổi trưa",
        "time_AFTERNOON": "Buổi chiều",
        "time_EVENING": "Buổi tối",
        "time_FULL_DAY": "Cả ngày",
        "stay_nights": "{nights} đêm",
        "free_day": "Ngày này để bạn tự do nghỉ ngơi hoặc khám phá theo ý thích.",
        "unit_PER_NIGHT": "/đêm",
        "unit_PER_PERSON": "/người",
        "unit_PER_PACKAGE": "/gói",
        "no_price": "giá đang cập nhật",
        "free_entry": "tham quan tự do",
        "no_total": "chưa cộng được tổng",
        "no_budget": "chưa có ngân sách",
        "cost_WITHIN_BUDGET": "Khoảng {total} cho các sản phẩm trong lịch trình, nằm trong ngân sách {budget}.",
        "cost_OVER_BUDGET": "Khoảng {total} cho các sản phẩm trong lịch trình, vượt ngân sách {budget}.",
        "cost_NO_BUDGET": "Khoảng {total} cho các sản phẩm trong lịch trình.",
        "cost_UNKNOWN": "Mình chưa cộng thành một con số tổng vì lịch có điểm tham quan tự do hoặc mục chưa có giá; "
                        "giá từng mục có vé bạn xem ở khung lịch trình bên phải nhé.",
        "narrate_notes": "Giá là giá tham khảo, chưa gồm ăn uống và đi lại; cần kiểm tra lại khi đặt.",
        "narrate_outro": "Bấm vào tên sản phẩm để xem chi tiết ở khung lịch trình bên phải, hoặc nhắn mình nếu muốn "
                         "đổi ngày, khách sạn hay hoạt động.",
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
        "invalid_reason_unsupported_destination": "Sorry, {value} is not among the destinations I can plan for yet. "
                                                  "The destinations I can plan for: {destinations}. Which one would "
                                                  "you like to plan a trip to?",
        "title_destination_kind": "Pick a destination that fits",
        "destination_kind": "Which city or province would you like to go to for {kind}? Tell me a place you like.",
        "trip_none": "no trip details yet",
        "trip_days": "{days} days",
        "trip_from": "departing {date}",
        "trip_budget": "budget {budget}",
        "trip_interests": "interests: {interests}",
        "trip_missing": "not given yet: {fields}",
        "stage_planned": "an itinerary has been sent for this trip",
        "stage_collecting": "still collecting trip details, no itinerary yet",
        "stage_start": "start of the conversation",
        "note_itinerary": "sent a {days}-day itinerary for {destination}: {products}",
        "note_no_results": "found no matching products in {destination}",
        "note_fallback": "sent a few candidate products in {destination}, no itinerary built",
        "note_unclear": "did not understand the message, asked the user to rephrase",
        "note_chat": "small talk",
        "note_refusal": "declined: outside itinerary planning",
        "note_constraint": "no product meets a required condition, asked whether to relax it",
        "note_invalid": "could not use {field} \"{value}\": {reason}",
        "note_reason_past_date": "the date has passed",
        "note_reason_days_out_of_range": "outside {min_days}–{max_days} days",
        "note_reason_party_out_of_range": "invalid number of travellers",
        "note_reason_budget_out_of_range": "invalid budget",
        "note_reason_unsupported_destination": "not in the destination list",
        "note_ask": "asked for {fields}",
        "note_change": "asked for the new value of {field}",
        "note_change_current": "asked for the new value of {field} (currently {current})",
        "note_kind": "asked which listed destination fits \"{kind}\"",
        "note_form": "sent a prefilled form, still missing {fields}",
        "note_conflict": "asked to confirm because the trip details did not match",
        "note_unverified": "asked about a requirement that could not be verified",
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
        "narrate_title": "{days}-day itinerary in {destination}",
        "narrate_changes": "Noted: {changes}. Here is the itinerary I suggest:",
        "narrate_intro": "Here is the itinerary I suggest:",
        "change_to_startDate": "departure date changed to {value}",
        "change_to_destination": "destination changed to {value}",
        "change_to_days": "trip length changed to {value} days",
        "change_to_party": "travellers changed to {value}",
        "change_to_budget": "budget changed to {value}",
        "party_adults": "{adults} adult(s)",
        "party_children": "{children} child(ren)",
        "section_stay": "Where to stay",
        "section_day": "Day {day}",
        "section_cost": "Estimated cost",
        "section_notes": "Good to know",
        "section_more": "Also in the itinerary",
        "section_offers": "Multi-day passes to consider separately",
        "offer_days": "valid for {days} days",
        "offers_question": "These cover several days, so I have not put them in the plan. Tell me if you want one and "
                           "I will rearrange the days around it.",
        "time_MORNING": "Morning",
        "time_NOON": "Midday",
        "time_AFTERNOON": "Afternoon",
        "time_EVENING": "Evening",
        "time_FULL_DAY": "Full day",
        "stay_nights": "{nights} night(s)",
        "free_day": "This day is free for you to rest or explore at your own pace.",
        "unit_PER_NIGHT": " per night",
        "unit_PER_PERSON": " per person",
        "unit_PER_PACKAGE": " per package",
        "no_price": "price being updated",
        "free_entry": "visit at your own pace",
        "no_total": "total not yet available",
        "no_budget": "no budget given",
        "cost_WITHIN_BUDGET": "About {total} for the products in the itinerary, within your budget of {budget}.",
        "cost_OVER_BUDGET": "About {total} for the products in the itinerary, over your budget of {budget}.",
        "cost_NO_BUDGET": "About {total} for the products in the itinerary.",
        "cost_UNKNOWN": "I haven't added a single total because the plan includes places you visit at your own pace "
                        "or items without a price; check the price of each ticketed item in the panel on the right.",
        "narrate_notes": "Prices are for reference only and exclude meals and transport; check them again when booking.",
        "narrate_outro": "Tap a product name to see its details in the itinerary panel on the right, or tell me if you "
                         "want to change the date, hotel or activities.",
    },
}

# Câu cố định dùng khi LLM không khả dụng hoặc khi luật không được để LLM tự diễn đạt. Câu nào có tiêu đề
# thì dòng đầu là `**Tiêu đề**`; câu hỏi lại dự phòng (xung đột, không xác minh được) thêm tiêu đề ở `titled()`.
CLARIFY_CONFLICT = ("Thông tin chuyến đi đang chưa rõ hoặc mâu thuẫn. "
                    "Bạn xác nhận lại điểm đến và thời gian giúp mình nhé?")
CLARIFY_UNVERIFIED = ("Điều kiện bắt buộc bạn yêu cầu chưa có dữ liệu để xác minh. "
                      "Bạn có muốn bỏ điều kiện đó hoặc cung cấp thêm thông tin không?")
CLARIFY_CONSTRAINT = ("**Chưa có sản phẩm đáp ứng yêu cầu bắt buộc**\n"
                      "Không tìm thấy sản phẩm đáp ứng điều kiện bắt buộc trong dữ liệu hiện có. "
                      "Bạn có muốn điều chỉnh điều kiện hoặc chọn phương án thay thế không?")
REFUSAL = ("**Ngoài phạm vi hỗ trợ**\n"
           "Mình hỗ trợ tư vấn lịch trình du lịch. Bạn muốn lên kế hoạch chuyến đi nào?")
#: Đầu vào bị guardrail chặn (chèn lệnh, đòi lộ khoá bí mật...): tiêu đề khác với câu hỏi ngoài phạm vi.
REFUSAL_BLOCKED = ("**Mình chưa thể hỗ trợ yêu cầu này**\n"
                   "Mình hỗ trợ tư vấn lịch trình du lịch. Bạn muốn lên kế hoạch chuyến đi nào?")
#: Tin nhắn rác (gõ bậy, ký tự lặp, toàn ký hiệu) bị guardrail tầng 1 chặn trước LLM; hỏi lại, không từ chối.
UNCLEAR_INPUT = ("**Mình chưa hiểu ý bạn**\n"
                 "Bạn nói rõ hơn giúp mình nhé, ví dụ: \"Đi Đà Nẵng 3 ngày, 2 người, ngân sách 10 triệu\".")
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


#: Link sản phẩm trong lời diễn giải lịch trình: `[Tên](product:<productId>)`; frontend biến nó thành nút focus panel.
PRODUCT_LINK = re.compile(r"\[([^\[\]\n]{1,200})\]\(product:([^()\s]{1,200})\)")


def plain_links(text: str) -> str:
    """`[Tên](product:id)` thành `Tên`; dùng khi đưa lịch sử lại cho LLM để tiết kiệm giới hạn ký tự."""
    return PRODUCT_LINK.sub(lambda match: match.group(1), text)


def display_date(iso: str) -> str:
    """Ngày ISO `yyyy-mm-dd` thành `dd/mm/yyyy` để hiện cho người dùng."""
    year, month, day = iso.split("-")
    return f"{day}/{month}/{year}"


def money(value: int, language: str) -> str:
    grouped = f"{int(value):,}"
    return f"{grouped.replace(',', '.')} ₫" if language == "vi" else f"{grouped} VND"


def party_text(state: dict, party: dict) -> str:
    text = message(state, "party_adults", adults=party.get("adults", 0))
    if party.get("children"):
        text += ", " + message(state, "party_children", children=party["children"])
    return text


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
