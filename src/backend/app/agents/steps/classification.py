"""Hai bước hiểu người dùng: `classify` phân luồng lượt chat, `extract` trích intent của lượt du lịch."""
from __future__ import annotations

from collections.abc import Iterable
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
import re

from src.backend.app.application.itinerary.contracts import bounds, valid
from src.backend.app.domain.itinerary import preferences
from src.backend.app.domain.itinerary.dates import explicit_dates, stated_days, this_year
from src.backend.app.domain.itinerary.normalization import fold
from src.backend.app.domain.itinerary.planning import merge_intent
from src.backend.app.domain.search.normalize import DESTINATION_ALIASES

from ..models import Extraction, TurnRoute
from .history import llm_context, prompt_yaml
from .messages import event, failure, message
from .prompts import CLASSIFY_PROMPT, EXTRACT_PROMPT


# Việt Nam không có giờ mùa hè, nên lệch cố định UTC+7 là đủ và không cần gói dữ liệu múi giờ (tzdata).
VIETNAM = timezone(timedelta(hours=7))
TRIP_FIELDS = ("destination", "days", "startDate", "party", "budget", "origin")
#: Trường phải đủ trước khi gọi tool (AC-AGT-01); ngân sách vẫn được hỏi nhưng không bắt buộc.
REQUIRED_FIELDS = ("destination", "days", "startDate", "party")
SWAP_CONSTRAINTS = ("exclude_products", "specific_hotel", "specific_activity", "require_hotel")
#: "lấy phương án 2", "phuong an so 2", "take option 2" (so trên chuỗi đã `fold`).
_OPTION_PICK = re.compile(r"\b(?:phuong an|option)\s*(?:so\s*)?(\d)\b")
#: Câu đồng ý ngắn khi trợ lý vừa mời lập lịch (FR-AGT-06), so trên chuỗi đã `fold`: nhận bằng luật, không đợi LLM.
_YES = re.compile(r"^(?:ok(?:e|ay|ie)?|oki|duoc|duoc roi|co|co chu|u|uh|uhm|um|vang|da|dong y|yes|yep|chot|nhat tri|"
                  r"lam di|lap di|len di|tien hanh)(?:\s+(?:ban|nhe|nha|luon|lun|di|a|nhe ban|lap di|lap lich di))*$")
#: Câu xin lập lịch: "lập lịch", "lên kế hoạch giúp mình", "xếp lịch trình", "plan a trip" (đã `fold`).
_PLAN = re.compile(r"\b(?:lap|len|xep|tao|soan)\b(?:\s+\w+){0,3}?\s+(?:lich|ke hoach)\b|\blich trinh\b|"
                   r"\bitinerary\b|\bplan\b")
#: Người dùng giao cho trợ lý chọn nơi ("cứ chọn đại", "tuỳ bạn", "đâu cũng được"), đã `fold`: bậc 2 của "không biết".
_DELEGATE = re.compile(r"\b(?:chon dai|chon giup|chon ho|chon bat ky|ban chon|tuy ban|"
                       r"(?:dau|cho nao|noi nao|sao) cung (?:duoc|dc|ok)|goi y dai|pick (?:a place )?for me|anywhere)\b")
#: Chê một nơi: "chán, Đà Nẵng đi rồi", "không thích Nha Trang", "chỗ khác đi" (đã `fold`). Tên nơi phải có trong câu,
#: trừ "chỗ khác", "nơi khác" (chê nơi trợ lý vừa mời).
_REJECT = re.compile(r"\b(?:chan|di roi|toi roi|khong thich|khong muon|khong hop|ghet|cho khac|noi khac|dia diem khac)\b")
_ELSEWHERE = re.compile(r"\b(?:cho khac|noi khac|dia diem khac)\b")
#: Câu có chữ số có thể mang số ngày, ngày đi, số người, ngân sách: luôn qua `extract`, không đi thẳng `explore`.
_DIGIT = re.compile(r"\d")
#: Thông tin chuyến ngoài điểm đến: nói một trong số này là người dùng đang lập lịch ("Hà Nội 3 ngày", "đi 3 ngày").
_PLANNING_DETAILS = ("days", "startDate", "party", "budget")


def asks_for_plan(text: str | None) -> bool:
    """Câu xin lập lịch hoặc tiếp tục lập lịch, nhận bằng luật (nút "Lên lịch Hà Nội cho mình" cũng khớp)."""
    return bool(_PLAN.search(fold(text)))


def says_yes(text: str | None) -> bool:
    return bool(_YES.match(fold(text)))


def planning_implied(intent: dict) -> bool:
    """Đã nói số ngày, ngày đi, số người hoặc ngân sách: coi như muốn lập lịch, không hỏi lại "có muốn không".

    Chỉ nêu điểm đến ("Hà Nội", "Hà Nội có gì?") thì chưa: trợ lý khám phá rồi mời lập lịch.
    """
    return any(intent.get(key) is not None for key in _PLANNING_DETAILS)


def plan_consented(state: dict, label: str | None = None, llm_plan_request: bool = False) -> bool:
    """Người dùng đã đồng ý lập lịch chưa (FR-AGT-06). Chưa đồng ý thì không hỏi thông tin chuyến, không hiện form.

    Đồng ý khi: đã đồng ý ở lượt trước; sửa form/chip (`intent_override`); câu xin lập lịch; hoặc trợ lý vừa mời mà người
    dùng trả lời "ok". Trả lời lời mời bằng thông tin chuyến ("3 ngày thôi") được `extract_result` nhận qua
    `planning_implied`, không nhận ở đây: "Thôi, Hà Nội thì sao?" cũng là câu du lịch nhưng là đổi nơi, không phải đồng
    ý (LLM thật, 10/10/2026). LLM báo `plan_request` không được tin ở câu hỏi về một nơi (`explore`).
    """
    if state.get("plan_consent") or state.get("intent_override"):
        return True
    query = state.get("query", "")
    if asks_for_plan(query):
        return True
    if state.get("pending_offer") and says_yes(query):
        return True
    return llm_plan_request and label not in ("explore", "out_of_scope")


def _known_places(state: dict) -> list[str]:
    """Nơi trợ lý đã gợi ý hoặc chuyến đang nói tới: chỉ những nơi này mới chê được bằng tên."""
    offer = (state.get("pending_offer") or {}).get("destination")
    names = [*(state.get("offered_destinations") or []), offer, (state.get("intent") or {}).get("destination"),
             *(state.get("rejected_destinations") or [])]
    return list(dict.fromkeys(name for name in names if name))


def rejected_places(state: dict) -> list[str]:
    """Nơi người dùng vừa chê trong câu này. "Chỗ khác đi" không nêu tên thì là nơi trợ lý vừa mời."""
    text = fold(state.get("query", ""))
    if not _REJECT.search(text):
        return []
    named = [name for name in _known_places(state) if f" {fold(name)} " in f" {text} "]
    offer = (state.get("pending_offer") or {}).get("destination")
    if not named and offer and _ELSEWHERE.search(text):
        named = [offer]
    return named


def _rejection_update(state: dict, consent: bool) -> dict:
    """Ghi nơi bị chê; câu nhắc lại đúng tên một nơi đã chê mà không chê nữa ("Đà Nẵng có gì?") là đổi ý, bỏ khỏi danh sách.

    Chưa đồng ý lập lịch mà vừa chê: bỏ lời mời và điểm đến bị chê khỏi chuyến, trợ lý khám phá nơi khác (`explore_pick`);
    người dùng nêu luôn nơi khác ("chán Đà Nẵng rồi, Hà Nội thì sao") thì `explore` lấy nơi đó.
    """
    previous = list(state.get("rejected_destinations") or [])
    fresh = rejected_places(state)
    text = f" {fold(state.get('query', ''))} "
    if not fresh:
        kept = [name for name in previous if f" {fold(name)} " not in text]
        return {"rejected_destinations": kept} if kept != previous else {}
    rejected = list(dict.fromkeys([*previous, *fresh]))
    update = {"rejected_destinations": rejected}
    if consent:
        return update
    intent = dict(state.get("intent") or {})
    if fold(intent.get("destination")) in {fold(name) for name in rejected}:
        intent["destination"] = None
        update["intent"] = intent
    return {**update, "pending_offer": None, "explore_pick": True}


def _consent_update(state: dict) -> dict:
    """Đồng ý lập lịch: xoá lời mời; điểm đến trợ lý tự chọn mà chuyến chưa có thì ghi vào chuyến."""
    update = {"plan_consent": True, "pending_offer": None, "dont_know_count": 0}
    offer = state.get("pending_offer") or {}
    intent = state.get("intent") or {}
    if offer.get("destination") and not intent.get("destination"):
        update["intent"] = {**intent, "destination": offer["destination"]}
    return update


def vietnam_today(now: datetime | None = None) -> date:
    """Ngày hôm nay theo giờ Việt Nam, không theo giờ máy chạy backend.

    Đây là mốc để LLM đổi "ngày mai", "tuần sau" thành ngày cụ thể; server chạy giờ UTC thì từ 0h đến
    7h sáng ở Việt Nam `date.today()` vẫn là hôm qua và "ngày mai" bị lệch một ngày.
    """
    return (now or datetime.now(timezone.utc)).astimezone(VIETNAM).date()


def route_input(state: dict) -> list:
    """Message hiện tại cộng ngữ cảnh hội thoại chung; `classify` chỉ trả một nhãn."""
    payload = {"message": state.get("query", ""), **llm_context(state),
               "assistant_offered_plan": bool(state.get("pending_offer"))}
    return [("system", CLASSIFY_PROMPT), ("human", prompt_yaml(payload))]


def _vague_form(state: dict) -> dict | None:
    """Câu trả lời không thêm được thông tin (`vague`) khi còn thiếu trường bắt buộc: đi thẳng `clarify` kèm form.

    `None` (xử lý như `travel`) khi chuyến đi đã đủ trường bắt buộc hoặc chưa có lượt nào để câu này trả lời.
    """
    intent = state.get("intent") or {}
    if not state.get("conversation_history") or all(intent.get(key) is not None for key in REQUIRED_FIELDS):
        return None
    missing = [key for key in TRIP_FIELDS if intent.get(key) is None]
    update = {"decision": "missing_info", "clarification_reason": "suggest_form", "missing_fields": missing,
              "start_date_asked": True}
    if {"destination", "days"} & set(missing):
        update["clarification_rounds"] = int(state.get("clarification_rounds", 0) or 0) + 1
    return update


#: Câu hỏi khác trong cùng tin nhắn thành nút gợi ý; dài hơn thì không vừa một nút.
MAX_OTHER_QUESTION_CHARS = 60


def understood(route: TurnRoute) -> dict:
    """Những gì LLM hiểu từ câu chữ của lượt này (tên nơi, thành phố, loại nơi, câu hỏi giá vé), ghi vào state cho
    `explore` và nhánh giá vé đối chiếu với catalog. Câu gõ sai, viết tắt, tiếng Anh, "tao ở X" đều qua đây thay cho
    danh sách từ khoá (chat thử 16 kiểu người dùng)."""
    return {"fare_ask": route.fare.model_dump() if route.fare else {}, "explore_place": route.place,
            "explore_city": route.city, "explore_focus": route.focus, "explore_price": route.price,
            # Thành nút gợi ý: câu ngắn như lời người dùng, quá dài thì bỏ (khung chat hẹp).
            "other_questions": [" ".join(text.split()) for text in route.other_questions
                                if text and 0 < len(text.strip()) <= MAX_OTHER_QUESTION_CHARS]}


def route_result(state: dict, result: TurnRoute) -> dict:
    """Update của `classify` (FR-AGT-06, chốt 2026-10-10).

    Đã đồng ý lập lịch (`plan_consented`): như trước, `travel` đi `extract`, `vague` đi `clarify` kèm form khi còn thiếu
    trường bắt buộc, câu hỏi về một nơi (`explore`) đi thẳng `explore` và giữ nguyên chuyến.
    Chưa đồng ý: câu du lịch hay hỏi về một nơi đều qua `extract` để ghi lại điểm đến và thông tin đã nói, rồi
    `extract_result` đưa sang `explore` (không hỏi thông tin chuyến); "không biết" đi bậc gợi ý của `converse` (bậc 2
    tự chọn một điểm đến và khám phá luôn). Trò chuyện và ngoài phạm vi đi `converse`, trả lời thường kèm nút gợi ý.
    Không muốn đi hay lên lịch nữa (`stop`, AC-AGT-01 chốt 2026-10-12) đi `converse` cảm ơn, hẹn gặp lại ở cả hai giai đoạn.
    """
    route = TurnRoute.model_validate(result)
    label = route.route
    if label == "fare":
        # Hỏi giá/giờ vé máy bay: nhánh giá vé của `explore` tra chuyến bằng luật từ các trường LLM đã hiểu.
        return {**understood(route), "interaction_type": "conversation", "refusal": False, "decision": "explore",
                "fare_question": True, "missing_fields": [], "events": [event("classify", "route fare")]}
    if label == "stop":
        # Không hỏi gì, không form, không nút; bỏ lời mời lập lịch đang chờ. Chuyến và việc đã đồng ý lập lịch giữ nguyên
        # để "thôi đi tiếp" nối lại được. Không lấy `understood`: tên nơi LLM đọc ra sẽ làm `converse` trả lời về nơi đó.
        return {"interaction_type": "stop", "refusal": False, "decision": "simple", "missing_fields": [],
                "clarification_reason": None, "pending_offer": None, "events": [event("classify", "route stop")]}
    consent = plan_consented(state, label, route.plan_request)
    update = {"interaction_type": "travel" if label in ("vague", "explore") else label,
              "refusal": label == "out_of_scope", **understood(route),
              "events": [event("classify", f"route {label}" + (" (plan consent)" if consent else ""))]}
    if consent:
        update.update(_consent_update(state) if not state.get("plan_consent") else {})
    update.update(_rejection_update({**state, **update}, consent))
    if update.get("explore_pick") and label not in ("out_of_scope",):
        # Vừa chê một nơi khi chưa đồng ý lập lịch: câu có nêu nơi khác thì qua `extract` để ghi lại, không thì khám phá
        # luôn một nơi khác.
        decision = "travel" if label in ("travel", "explore") else "explore"
        return {**update, "interaction_type": "conversation", "decision": decision, "missing_fields": []}
    if _delegates_the_choice(state, label, consent):
        return {**update, "interaction_type": "conversation", "decision": "explore", "explore_pick": True,
                "dont_know_count": max(2, int(state.get("dont_know_count", 0) or 0) + 1), "missing_fields": []}
    if label == "vague" and consent and not state.get("plan_consent"):
        # Vừa đồng ý ("ok" sau lời mời): hỏi gộp một câu như AC-AGT-01, chưa đưa form.
        return {**update, "decision": "travel"}
    if label == "vague" and consent:
        return {**update, **(_vague_form({**state, **update}) or {"decision": "travel"})}
    if label == "vague":
        return {**update, **_not_knowing(state)}
    if label == "explore" and consent:
        return {**update, "decision": "explore"}
    if label == "explore" and not _DIGIT.search(state.get("query", "")):
        # Hỏi về một nơi, không kèm số ngày, ngày đi hay số người: `explore` tự tra tên nơi trong catalog, bớt một lượt gọi
        # LLM của `extract` (FR-AGT-06). Không tra được tên thì `explore` trả về `extract` (`route_after_explore`).
        return {**update, "decision": "explore", "explore_direct": True}
    if label in ("travel", "explore"):
        return {**update, "decision": "travel"}
    # `converse` dùng `missing_fields` để mời người dùng nói tiếp phần chuyến đi còn thiếu; chưa đồng ý lập lịch thì
    # chỉ mời nói điểm đến, không hỏi số ngày.
    intent = {**state.get("intent", {}), **update.get("intent", {})}
    keys = ("destination", "days") if consent else ("destination",)
    missing = [key for key in keys if not intent.get(key)]
    return {**update, "decision": "simple", "missing_fields": missing, "offer_suggestions": True}


def _delegates_the_choice(state: dict, label: str, consent: bool) -> bool:
    """"Cứ chọn đại một nơi đi" khi chưa có điểm đến và chưa đồng ý: trợ lý chọn luôn (bậc 2), không hỏi thêm.

    Nhận bằng luật vì LLM hay xếp câu này là trò chuyện (LLM thật, 10/10/2026), và trợ lý lại bảo người dùng tự nhắn tên.
    """
    if consent or label == "out_of_scope" or state.get("pending_offer"):
        return False
    if (state.get("intent") or {}).get("destination"):
        return False
    return bool(_DELEGATE.search(fold(state.get("query", ""))))


def _not_knowing(state: dict) -> dict:
    """Người dùng chưa biết, chưa muốn ("không biết", "tuỳ bạn", "để sau") khi chưa đồng ý lập lịch: không form.

    Đang có lời mời thì coi như để sau, xoá lời mời. Chưa có điểm đến thì đếm bậc: bậc 1 hỏi kiểu chuyến, bậc 2 tự
    chọn điểm đến nhiều sản phẩm nhất và khám phá luôn (`explore_pick`), từ bậc 3 ngừng hỏi, chỉ giữ nút.
    """
    base = {"interaction_type": "conversation", "missing_fields": [], "offer_suggestions": True}
    if state.get("pending_offer") or (state.get("intent") or {}).get("destination"):
        return {**base, "decision": "simple", "pending_offer": None}
    count = int(state.get("dont_know_count", 0) or 0) + 1
    if count == 2:
        return {**base, "decision": "explore", "explore_pick": True, "dont_know_count": count}
    return {**base, "decision": "simple", "dont_know_count": count}


def extraction_input(state: dict) -> list:
    """Message hiện tại cộng ngữ cảnh hội thoại chung và mốc `today` để đổi ngày tương đối."""
    language = "Vietnamese" if state.get("language", "vi") == "vi" else "English"
    payload = {"message": state.get("query", ""), **llm_context(state), "today": vietnam_today().isoformat(),
               **_destination_names(state)}
    return [("system", EXTRACT_PROMPT + f"\nUse {language} for any natural-language content."),
            ("human", prompt_yaml(payload))]


def _destination_names(state: dict) -> dict:
    """Điểm đến của catalog và cách viết tắt đã biết (dữ liệu chuẩn hóa của Search), để LLM tự đổi "hn", "sg" ra tên
    catalog thay vì để trống (trace LangSmith 2026-10-11: "hn" trả lời câu hỏi điểm đến ra `destination: null`)."""
    supported = state.get("supported_destinations") or []
    allowed = set(supported) or set(DESTINATION_ALIASES.values())
    short_forms: dict[str, list[str]] = {}
    for alias, name in DESTINATION_ALIASES.items():
        if name in allowed:
            short_forms.setdefault(name, []).append(alias)
    return {"catalog_destinations": supported, "destination_short_forms": short_forms}


def _merged_intent(state: dict, patch: dict) -> tuple[dict, dict | None]:
    """Intent mới = intent cũ + patch của LLM + chip người dùng sửa tay (chip là quyền cao nhất)."""
    intent = merge_intent(state.get("intent", {}), patch)
    override = state.get("intent_override", {})
    if override:
        # Chip changes are authoritative; preserve explicit null resets.
        if not valid("TripIntentPatch", override):
            return intent, failure(state, "VALIDATION_ERROR", message(state, "invalid_override"), 422)
        intent.update(deepcopy(override))
    return intent, None


#: Từ chung trong tên sản phẩm; một mình chúng không chứng tỏ câu chat nhắc tới đúng sản phẩm đó.
_GENERIC_NAME_WORDS = {"khach", "san", "hotel", "resort", "tour", "the", "and", "day", "full", "half"}


def _named_in_message(state: dict, name: str) -> bool:
    """Câu chat có nhắc tới tên này không: trùng ít nhất một từ riêng (≥ 3 ký tự), không tính từ chung và từ của
    tên điểm đến ("Hà Nội" trong "The Sun Ha Noi Hotel" không chứng tỏ người dùng nhắc tới khách sạn đó)."""
    words = set(fold(state.get("query", "")).split())
    generic = _GENERIC_NAME_WORDS | set(fold((state.get("intent") or {}).get("destination")).split())
    return any(len(word) >= 3 and word not in generic and word in words for word in fold(name).split())


def _copied_from_selection(state: dict, changes: dict) -> None:
    """Lưới an toàn: bỏ `specific_hotel`/`specific_activity` LLM chép từ sản phẩm đã cho xem mà câu chat không nhắc.

    Trace thật (gpt-4o-mini, "mình muốn đi biển cơ" sau lịch trình Hà Nội): `specific_hotel = "The Sun Ha Noi Hotel"`
    lấy từ lịch trình cũ, biến khách sạn Hà Nội thành điều kiện bắt buộc cho chuyến đi biển.
    """
    shown = {fold(item.get("name")) for item in state.get("previous_selection", [])}
    for key in ("specific_hotel", "specific_activity"):
        value = changes.get(key)
        if value and fold(value) in shown and not _named_in_message(state, value):
            changes.pop(key)


def picked_option(state: dict) -> dict | None:
    """Phương án khác người dùng chọn ở lượt này ("lấy phương án N"), chỉ trong các phương án đã hiện ở lượt trước
    (`previous_options`, AC-AGT-04 chốt 2026-10-08); số không có trong đó thì None."""
    match = _OPTION_PICK.search(fold(state.get("query", "")))
    if match is None:
        return None
    return next((option for option in state.get("previous_options", [])
                 if option.get("index") == int(match.group(1)) and option.get("stays")), None)


def _merged_constraints(state: dict, result: Extraction, patch: dict, intent: dict) -> dict:
    """Ràng buộc mới; các luật dưới đây giữ cho `require_hotel` và `exclude_*` không tự mâu thuẫn."""
    constraints = deepcopy(state.get("constraints", {}))
    changes = result.constraints.model_dump(exclude_none=True)
    _copied_from_selection(state, changes)
    option = picked_option(state)
    if option is not None:
        # Tên lấy từ phương án đã hiện (grounding), không từ LLM; phương án hai khách sạn giữ khách sạn đêm 1.
        changes["specific_hotel"] = option["stays"][0]["name"]
    for key in changes.pop("clear_fields", []):
        constraints.pop(key, None)
    if "hotel_attributes" in changes:
        changes["hotel_attributes"] = {**constraints.get("hotel_attributes", {}), **changes["hotel_attributes"]}
    if "exclude_products" in changes:
        # LLM may only exclude a productId it was actually shown; anything else is a hallucinated id.
        known_ids = {item["productId"] for item in state.get("previous_selection", [])}
        valid_new = [pid for pid in changes["exclude_products"] if pid in known_ids]
        changes["exclude_products"] = sorted(set(constraints.get("exclude_products", [])) | set(valid_new))
    constraints.update(changes)
    if changes.get("require_hotel") is False or "hotel" in changes.get("exclude_taxonomies", []):
        constraints["require_hotel"] = False
        constraints.pop("specific_hotel", None)
    elif constraints.get("specific_hotel"):
        constraints["require_hotel"] = True
    if "party" in patch or "party" in state.get("intent_override", {}):
        party = intent.get("party")
        if party is not None:
            constraints.pop("party_type_hint", None)
            if not party["children"]:
                constraints.pop("children_ages", None)
    if constraints.get("require_hotel"):
        constraints["exclude_taxonomies"] = [x for x in constraints.get("exclude_taxonomies", []) if x != "hotel"]
    if changes.get("require_flight"):
        constraints["exclude_taxonomies"] = [x for x in constraints.get("exclude_taxonomies", []) if x != "flight"]
    elif "flight" in changes.get("exclude_taxonomies", []):
        constraints.pop("require_flight", None)
    return constraints


def _supplies_a_change(state: dict, intent: dict, constraints: dict) -> bool:
    """Lưới an toàn cho LLM tự mâu thuẫn khi nó báo `change_without_value`: lượt này có thật sự đổi gì không.

    LLM hay chép lại cả intent đang có vào `patch`, nên "có giá trị trong patch" không đủ: chỉ giá trị KHÁC intent
    đã lưu mới tính ('đổi sang 5/10'). Đổi món (thay khách sạn, loại một sản phẩm đã xem) đổi ràng buộc chứ không
    đổi intent, nên cũng tính. Các ràng buộc khác (`party_type_hint`...) hay bị LLM đặt lung tung, không tính.
    """
    before, before_constraints = state.get("intent", {}), state.get("constraints", {})
    # Giá trị rỗng (`[]`, `False`) coi như chưa có: LLM hay trả `exclude_products: []` khi chẳng loại gì.
    return (any(intent.get(field) != before.get(field) for field in TRIP_FIELDS)
            or any((constraints.get(key) or None) != (before_constraints.get(key) or None) for key in SWAP_CONSTRAINTS))


def _date_from_message(state: dict, result: Extraction, patch: dict, today: date) -> Extraction:
    """Lưới an toàn khi LLM bỏ sót hoặc chép lại ngày cũ dù câu chat viết rõ một ngày mới.

    Trace thật (gpt-4o-mini, "à nhầm Ngày 15 tháng 10" khi chuyến đang đi 14/10): `patch` chép nguyên intent đã lưu,
    `startDate` vẫn là 14/10 và `change_without_value = ["startDate"]`, nên lượt này bị hỏi lại. Câu có đúng một ngày
    tường minh (không phải ngày kết thúc) mà `patch.startDate` trống hoặc bằng ngày đã lưu thì dùng ngày đọc được.
    Ghi thẳng vào `patch` (đổi tại chỗ), trả lại `result` đã bỏ `startDate` khỏi `change_without_value`.
    """
    dates = explicit_dates(state.get("query", ""), today)
    if len(dates) != 1 or dates[0] == result.end_date or state.get("intent_override", {}).get("startDate"):
        return result
    stated, saved = dates[0].isoformat(), state.get("intent", {}).get("startDate")
    if patch.get("startDate") not in (None, saved) or stated == saved:
        return result
    patch["startDate"] = stated
    remaining = [field for field in result.change_without_value if field != "startDate"]
    return result.model_copy(update={"change_without_value": remaining, "start_date_undecided": False})


def _days_from_message(state: dict, result: Extraction, patch: dict) -> None:
    """Lưới an toàn khi LLM bỏ trống số ngày dù câu chat viết thời lượng dạng gói ("1 ngày 2 đêm", "3n2d").

    Trace thật (golden TC-03, 05/10): "nghỉ dưỡng ... 1 ngày 2 đêm" ra `days = null` nên agent hỏi lại số ngày, trong khi
    hội thoại gốc chỉ hỏi điểm đến. Chỉ điền khi LLM không đưa số ngày, lượt này không có ngày kết thúc và không có chip
    số ngày; ghi thẳng vào `patch`. Số ngày ngoài 1–7 vẫn bị `_invalid_inputs` hỏi lại như mọi giá trị khác.
    """
    if patch.get("days") is not None or result.end_date or "days" in state.get("intent_override", {}):
        return
    days = stated_days(state.get("query", ""))
    if days is not None:
        patch["days"] = days


def _default_year(result: Extraction, intent: dict, patch: dict, today: date) -> Extraction:
    """Năm mặc định là năm hiện tại: ngày đi và ngày kết thúc LLM vừa trích mà mang năm cũ được sửa về năm nay.

    Chỉ xét ngày có trong patch lượt này; ngày đã lưu từ lượt trước thì người dùng đã chốt rồi.
    """
    if "startDate" in patch and intent.get("startDate"):
        intent["startDate"] = this_year(date.fromisoformat(intent["startDate"]), today).isoformat()
    if result.end_date is not None:
        result = result.model_copy(update={"end_date": this_year(result.end_date, today)})
    return result


def _days_from_end_date(result: Extraction, intent: dict, patch: dict, override: dict) -> bool:
    """Suy `days` từ `end_date`; trả về True khi `days` LLM trích được mâu thuẫn với ngày kết thúc."""
    if not (result.end_date and intent.get("startDate")):
        return False
    derived = (result.end_date - date.fromisoformat(intent["startDate"])).days + 1
    if "days" in patch and patch["days"] != derived and "days" not in override:
        return True
    if "days" not in override:
        intent["days"] = derived
    return False


def _invalid_inputs(intent: dict, today: date) -> list[dict]:
    """Giá trị ngoài giới hạn: ngày đi đã qua, số ngày, số người, ngân sách. Xoá từng trường sai khỏi `intent`.

    Giới hạn số lấy từ contract (`bounds`), ngày đi so với hôm nay theo giờ Việt Nam. Điểm đến ngoài catalog
    không kiểm ở đây vì cần danh sách điểm đến của catalog (node `tool`).
    """
    found = []

    def reject(field: str, reason: str) -> None:
        found.append({"field": field, "value": intent[field], "reason": reason})
        intent[field] = None

    if intent.get("startDate") and date.fromisoformat(intent["startDate"]) < today:
        reject("startDate", "past_date")
    min_days, max_days = bounds("TripIntent", "days")
    if intent.get("days") is not None and not min_days <= intent["days"] <= max_days:
        reject("days", "days_out_of_range")
    party = intent.get("party")
    if party is not None and (party["adults"] < bounds("Party", "adults")[0]
                              or party["children"] < bounds("Party", "children")[0]):
        reject("party", "party_out_of_range")
    if intent.get("budget") is not None and intent["budget"] < bounds("TripIntent", "budget")[0]:
        reject("budget", "budget_out_of_range")
    return found


#: Chi tiết chuyến đi hỏi gộp bằng câu chữ một lần sau điểm đến và số ngày; từ lượt sau còn thiếu ngày đi hoặc số
#: người thì hiện form (AC-AGT-01).
TRIP_DETAILS = ("startDate", "party", "budget", "origin")  # nơi đi: không bắt buộc, như ngân sách (AC-AGT-02)


def trip_details_missing(intent: dict, skipped: Iterable[str] = ()) -> list[str]:
    """Chi tiết còn thiếu; "chưa chốt ngày" vẫn tính ngày đi là thiếu, vì ngày đi là trường bắt buộc. Chi tiết không bắt
    buộc mà người dùng đã nói là không có (`skipped`: "không có ngân sách") không còn thiếu."""
    left_out = set(skipped) - set(REQUIRED_FIELDS)
    return [key for key in TRIP_DETAILS if intent.get(key) is None and key not in left_out]


def _ask_invalid(state: dict, result: Extraction, intent: dict, invalid: list[dict], missing: list[str],
                 asked: bool, rounds: int) -> dict:
    """Hỏi lại vì có giá trị không hợp lệ (câu chat, chip hay giá trị lưu từ lượt trước), không gọi tool.

    `missing_fields` gồm điểm đến/số ngày còn thiếu, các trường vừa bị xoá và, nếu chưa từng hỏi, chi tiết
    ngày đi/số người/ngân sách còn trống. Vẫn thiếu điểm đến/số ngày thì đếm vòng để `clarify` gửi form đúng lúc.
    """
    fields = [*missing, *(item["field"] for item in invalid if item["field"] not in missing)]
    asks_details = not missing and not asked and not state.get("intent_override")
    if asks_details:
        fields += [key for key in trip_details_missing(intent, state.get("skipped_details") or []) if key not in fields]
    update = {"decision": "missing_info", "missing_fields": fields, "clarification_reason": "invalid_input",
              "start_date_asked": asked or asks_details or any(item["field"] == "startDate" for item in invalid)}
    if missing:
        update["clarification_rounds"] = rounds + 1
    return update


def _extract_update(state: dict, result: Extraction) -> dict:
    """Update của `extract` khi đã đồng ý lập lịch: hỏi lại phần thiếu hoặc gọi tool (AC-AGT-01)."""
    result = Extraction.model_validate(result)
    patch = result.patch.model_dump(mode="json", exclude_none=True)
    if result.patch.party is not None:
        patch["party"] = result.patch.party.model_dump(mode="json")
    if result.destination_kind and fold(patch.get("destination")) == fold(result.destination_kind):
        # Loại nơi bị điền nhầm vào cả `destination` ("biển"): không phải tên điểm đến, đừng đem đi khớp catalog.
        patch.pop("destination")
    result = _date_from_message(state, result, patch, vietnam_today())
    _days_from_message(state, result, patch)
    intent, invalid_override = _merged_intent(state, patch)
    if invalid_override is not None:
        return invalid_override
    constraints = _merged_constraints(state, result, patch, intent)
    today = vietnam_today()
    result = _default_year(result, intent, patch, today)
    conflicting_days = _days_from_end_date(result, intent, patch, state.get("intent_override", {}))
    # LLM báo người dùng muốn đổi mà chưa nói đổi thành gì ('đổi ngày'): hỏi lại, giữ intent cũ, không gọi tool.
    asks_change = bool(result.change_without_value) and not _supplies_a_change(state, intent, constraints) \
        and not state.get("intent_override")
    # Xin đổi không phải mâu thuẫn: trace thật "doi diem di" ra cả `conflict` lẫn `change_without_value`, và hỏi
    # "xác nhận lại điểm đến và số ngày" thay vì "đổi sang đâu". Câu đã có giá trị mới cũng vậy: chip "Đi Hà Nội 3 ngày
    # từ ngày 15/10/2026" ra `conflict` + `change_without_value=['startDate']` vì ngày mới khác ngày cũ. LLM đã tự xếp
    # lượt này là đổi nên bỏ cờ `conflict`; mâu thuẫn ngay trong câu (ngày đi/về lệch số ngày) vẫn do `conflicting_days`.
    conflict = (result.conflict and not result.change_without_value) or conflicting_days
    invalid = _invalid_inputs(intent, today)
    missing = [key for key in ("destination", "days") if not intent.get(key)]
    # Ngày đi, số người, ngân sách: hỏi gộp một câu, một lần mỗi hội thoại và chỉ trước lần lập lịch đầu tiên.
    asked = bool(state.get("start_date_asked"))
    rounds = int(state.get("clarification_rounds", 0) or 0)
    # "không có ngân sách": LLM ghi chi tiết đó là đã trả lời; nhớ qua các lượt để không hỏi lại (chat thử M10).
    skipped = sorted({*(state.get("skipped_details") or []), *result.skipped_details})
    update = {"intent": intent, "constraints": constraints,
              "missing_fields": missing, "start_date_asked": asked,
              "clarification_rounds": rounds, "invalid_inputs": invalid, "skipped_details": skipped,
              "events": [event("extract", "intent extracted")]}
    if invalid:
        return {**update, **_ask_invalid(state, result, intent, invalid, missing, asked, rounds)}
    if not valid("TripIntent", intent):
        return {**update, **failure(state, "VALIDATION_ERROR", message(state, "invalid_intent"), 422)}
    # Người dùng nói loại nơi ("đi biển") thay vì tên một điểm đến: hỏi chọn điểm đến hợp loại đó trong catalog.
    # Không đếm vào `clarification_rounds`: form gợi ý điền sẵn điểm đến đầu catalog, có thể không hợp loại.
    if result.destination_kind and not patch.get("destination") and "destination" not in state.get("intent_override", {}):
        return {**update, "decision": "missing_info", "destination_kind": result.destination_kind,
                "missing_fields": ["destination", *(key for key in missing if key != "destination")],
                "clarification_reason": "destination_kind"}
    if conflict or constraints.get("unverified_requirements"):
        return {**update, "decision": "missing_info",
                "clarification_reason": "conflict" if conflict else "unverified"}
    if missing == ["days"] and not rounds and not asked and not state.get("intent_override"):
        # Đã có điểm đến (vừa đồng ý lập lịch: "Ok, lên lịch Hà Nội luôn"): hỏi gộp số ngày cùng ngày đi, số người, ngân
        # sách, nơi đi trong một câu (AC-AGT-01, kịch bản bản 5 cảnh 7); trước đây chỉ hỏi số ngày rồi lượt sau hỏi tiếp.
        return {**update, "decision": "missing_info",
                "missing_fields": ["days", *trip_details_missing(intent, skipped)],
                "start_date_asked": True, "clarification_reason": None, "clarification_rounds": rounds + 1}
    if missing:
        # Hỏi bằng câu chữ một lượt; từ lượt sau `clarify` gửi kèm form đã điền sẵn thay vì hỏi lại y hệt.
        asked_once = rounds + 1 >= 2
        return {**update, "decision": "missing_info",
                "clarification_reason": "suggest_form" if asked_once else None,
                "clarification_rounds": rounds + 1}
    if asks_change:
        return {**update, "decision": "missing_info",
                "missing_fields": list(dict.fromkeys(result.change_without_value)),
                "clarification_reason": "change_without_value"}
    details = trip_details_missing(intent, skipped)
    # Chip sửa tay là chỉnh có chủ ý trên hội thoại đã có, không hỏi thêm bằng câu chữ ở đó.
    if details and not asked and not state.get("intent_override"):
        return {**update, "decision": "missing_info", "missing_fields": details,
                "start_date_asked": True, "clarification_reason": None}
    # Đã hỏi một lần mà vẫn thiếu ngày đi hoặc số người (kể cả trả lời một phần): form ở mỗi lượt cho tới khi đủ.
    if any(intent.get(key) is None for key in REQUIRED_FIELDS):
        return {**update, "decision": "missing_info", "missing_fields": details,
                "start_date_asked": True, "clarification_reason": "suggest_form"}
    return {**update, "decision": "tool", "start_date_asked": True, "clarification_reason": None}


def _soft_preferences(state: dict, update: dict) -> dict:
    """Sở thích nói là ưu tiên ("ưu tiên khách sạn có hồ bơi", câu xác nhận form): ghi nhãn vào `intent.interests`, và bỏ
    cờ bắt buộc LLM vừa đặt cho đúng tiện ích đó trong `hotel_attributes` (FR-AGT-06, `domain/itinerary/preferences.py`).
    """
    stated = preferences.stated_preferences(state.get("query", ""))
    if not stated or "intent" not in update:
        return update
    intent = dict(update["intent"])
    interests = list(intent.get("interests") or [])
    for item in stated:
        if not any(preferences.from_interests([value]) == [item] for value in interests):
            interests.append(item.label)
    intent["interests"] = interests
    constraints = dict(update.get("constraints") or {})
    before = (state.get("constraints") or {}).get("hotel_attributes") or {}
    attributes = dict(constraints.get("hotel_attributes") or {})
    for item in stated:
        if item.attribute and attributes.get(item.attribute) is True and before.get(item.attribute) is not True:
            attributes.pop(item.attribute)
    if attributes:
        constraints["hotel_attributes"] = attributes
    else:
        constraints.pop("hotel_attributes", None)
    return {**update, "intent": intent, "constraints": constraints}


def extract_result(state: dict, result: Extraction) -> dict:
    """Update của `extract`, gồm `decision` quyết định nhánh đi tiếp (`routing.route_after_extract`).

    Chưa đồng ý lập lịch (FR-AGT-06): thông tin chuyến vẫn được ghi, nhưng thay cho hỏi lại hay gọi tool thì sang
    `explore` (đã có điểm đến) hoặc `converse` (chưa có). Câu có thông tin chuyến ngoài điểm đến ("Hà Nội 3 ngày",
    "đi 3 ngày") coi như đồng ý (`planning_implied`). Giá trị không hợp lệ và hỏi chọn điểm đến theo loại ("đi biển")
    giữ như cũ.
    """
    update = _soft_preferences(state, _extract_update(state, result))
    if state.get("plan_consent") or update.get("decision") in ("error", None):
        return update
    if update.get("clarification_reason") in ("invalid_input", "destination_kind"):
        return update
    intent = update.get("intent") or {}
    if planning_implied(intent):
        return {**update, **{key: value for key, value in _consent_update({**state, "intent": intent}).items()
                             if key != "intent"}, "plan_consent": True}
    calm = {"clarification_rounds": int(state.get("clarification_rounds", 0) or 0),
            "start_date_asked": bool(state.get("start_date_asked")), "clarification_reason": None}
    rejected = {fold(name) for name in state.get("rejected_destinations") or []}
    if fold(intent.get("destination")) in rejected:
        # LLM chép tên nơi vừa bị chê vào patch ("chán Đà Nẵng rồi"): không ghi lại nơi đó vào chuyến.
        intent = {**intent, "destination": None}
        update = {**update, "intent": intent}
    if intent.get("destination") or state.get("explore_pick"):
        return {**update, **calm, "decision": "explore", "missing_fields": []}
    return {**update, **calm, "decision": "simple", "interaction_type": "conversation",
            "missing_fields": ["destination"], "offer_suggestions": True}
