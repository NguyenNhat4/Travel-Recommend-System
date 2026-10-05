"""Hai bước hiểu người dùng: `classify` phân luồng lượt chat, `extract` trích intent của lượt du lịch."""
from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timedelta, timezone

from src.backend.app.application.itinerary.contracts import bounds, valid
from src.backend.app.domain.itinerary.dates import explicit_dates, stated_days, this_year
from src.backend.app.domain.itinerary.normalization import fold
from src.backend.app.domain.itinerary.planning import merge_intent

from ..models import Extraction, TurnRoute
from .history import llm_context, prompt_yaml
from .messages import event, failure, message
from .prompts import CLASSIFY_PROMPT, EXTRACT_PROMPT


# Việt Nam không có giờ mùa hè, nên lệch cố định UTC+7 là đủ và không cần gói dữ liệu múi giờ (tzdata).
VIETNAM = timezone(timedelta(hours=7))
TRIP_FIELDS = ("destination", "days", "startDate", "party", "budget")
#: Trường phải đủ trước khi gọi tool (AC-AGT-01); ngân sách vẫn được hỏi nhưng không bắt buộc.
REQUIRED_FIELDS = ("destination", "days", "startDate", "party")
SWAP_CONSTRAINTS = ("exclude_products", "specific_hotel", "specific_activity", "require_hotel")


def vietnam_today(now: datetime | None = None) -> date:
    """Ngày hôm nay theo giờ Việt Nam, không theo giờ máy chạy backend.

    Đây là mốc để LLM đổi "ngày mai", "tuần sau" thành ngày cụ thể; server chạy giờ UTC thì từ 0h đến
    7h sáng ở Việt Nam `date.today()` vẫn là hôm qua và "ngày mai" bị lệch một ngày.
    """
    return (now or datetime.now(timezone.utc)).astimezone(VIETNAM).date()


def route_input(state: dict) -> list:
    """Message hiện tại cộng ngữ cảnh hội thoại chung; `classify` chỉ trả một nhãn."""
    payload = {"message": state.get("query", ""), **llm_context(state)}
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


def route_result(state: dict, result: TurnRoute) -> dict:
    """Update của `classify`: `travel` đi tiếp `extract`; `vague` đi `clarify` kèm form khi còn thiếu trường bắt
    buộc, không thì như `travel`; trò chuyện và ngoài phạm vi đi `converse`."""
    label = TurnRoute.model_validate(result).route
    update = {"interaction_type": "travel" if label == "vague" else label, "refusal": label == "out_of_scope",
              "events": [event("classify", f"route {label}")]}
    if label == "vague":
        return {**update, **(_vague_form(state) or {"decision": "travel"})}
    if label == "travel":
        return {**update, "decision": "travel"}
    # `converse` dùng `missing_fields` để mời người dùng nói tiếp phần chuyến đi còn thiếu.
    missing = [key for key in ("destination", "days") if not state.get("intent", {}).get(key)]
    return {**update, "decision": "simple", "missing_fields": missing}


def extraction_input(state: dict) -> list:
    """Message hiện tại cộng ngữ cảnh hội thoại chung và mốc `today` để đổi ngày tương đối."""
    language = "Vietnamese" if state.get("language", "vi") == "vi" else "English"
    payload = {"message": state.get("query", ""), **llm_context(state), "today": vietnam_today().isoformat()}
    return [("system", EXTRACT_PROMPT + f"\nUse {language} for any natural-language content."),
            ("human", prompt_yaml(payload))]


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


def _merged_constraints(state: dict, result: Extraction, patch: dict, intent: dict) -> dict:
    """Ràng buộc mới; các luật dưới đây giữ cho `require_hotel` và `exclude_*` không tự mâu thuẫn."""
    constraints = deepcopy(state.get("constraints", {}))
    changes = result.constraints.model_dump(exclude_none=True)
    _copied_from_selection(state, changes)
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
TRIP_DETAILS = ("startDate", "party", "budget")


def trip_details_missing(intent: dict) -> list[str]:
    """Chi tiết còn thiếu; "chưa chốt ngày" vẫn tính ngày đi là thiếu, vì ngày đi là trường bắt buộc."""
    return [key for key in TRIP_DETAILS if intent.get(key) is None]


def _ask_invalid(state: dict, result: Extraction, intent: dict, invalid: list[dict], missing: list[str],
                 asked: bool, rounds: int) -> dict:
    """Hỏi lại vì có giá trị không hợp lệ (câu chat, chip hay giá trị lưu từ lượt trước), không gọi tool.

    `missing_fields` gồm điểm đến/số ngày còn thiếu, các trường vừa bị xoá và, nếu chưa từng hỏi, chi tiết
    ngày đi/số người/ngân sách còn trống. Vẫn thiếu điểm đến/số ngày thì đếm vòng để `clarify` gửi form đúng lúc.
    """
    fields = [*missing, *(item["field"] for item in invalid if item["field"] not in missing)]
    asks_details = not missing and not asked and not state.get("intent_override")
    if asks_details:
        fields += [key for key in trip_details_missing(intent) if key not in fields]
    update = {"decision": "missing_info", "missing_fields": fields, "clarification_reason": "invalid_input",
              "start_date_asked": asked or asks_details or any(item["field"] == "startDate" for item in invalid)}
    if missing:
        update["clarification_rounds"] = rounds + 1
    return update


def extract_result(state: dict, result: Extraction) -> dict:
    """Update của `extract`, gồm `route` quyết định nhánh đi tiếp (`routing.route_after_extract`)."""
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
    update = {"intent": intent, "constraints": constraints,
              "missing_fields": missing, "start_date_asked": asked,
              "clarification_rounds": rounds, "invalid_inputs": invalid,
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
    details = trip_details_missing(intent)
    # Chip sửa tay là chỉnh có chủ ý trên hội thoại đã có, không hỏi thêm bằng câu chữ ở đó.
    if details and not asked and not state.get("intent_override"):
        return {**update, "decision": "missing_info", "missing_fields": details,
                "start_date_asked": True, "clarification_reason": None}
    # Đã hỏi một lần mà vẫn thiếu ngày đi hoặc số người (kể cả trả lời một phần): form ở mỗi lượt cho tới khi đủ.
    if any(intent.get(key) is None for key in REQUIRED_FIELDS):
        return {**update, "decision": "missing_info", "missing_fields": details,
                "start_date_asked": True, "clarification_reason": "suggest_form"}
    return {**update, "decision": "tool", "start_date_asked": True, "clarification_reason": None}
