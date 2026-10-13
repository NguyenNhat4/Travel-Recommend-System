"""Người dùng đã đồng ý lập lịch chưa (FR-AGT-01, FR-AGT-06): mọi luật về việc này nằm ở đây.

Chưa đồng ý thì trợ lý chỉ trò chuyện và khám phá: không hỏi thông tin chuyến, không hiện form. Người dùng đồng ý khi:

- đã đồng ý ở lượt trước (`plan_consent` lưu trong hội thoại);
- sửa form hoặc chip (`intent_override`), bấm/gõ "phương án N", chọn chuyến bay khác (`steps/changes.py`);
- câu xin lập lịch (`asks_for_plan`), hoặc LLM báo `plan_request` ở câu không phải hỏi về một nơi;
- trợ lý vừa mời mà người dùng nói "ok" (`says_yes`);
- câu nêu thông tin chuyến ngoài điểm đến, như "Hà Nội 3 ngày" (`planning_implied`, xét sau `extract`);
- xin form ("cho mình cái form").

`precheck` xét các điều kiện trước `extract` qua `plan_consented`; `extract` xét `planning_implied` qua `implied_update`;
orchestrator khai lý do lập lịch và code kiểm bằng `structured_plan_allowed`.
"""
from __future__ import annotations

import re

from src.backend.app.domain.itinerary.normalization import fold

#: Câu đồng ý ngắn khi trợ lý vừa mời lập lịch (FR-AGT-06), so trên chuỗi đã `fold`: nhận bằng luật, không đợi LLM.
_YES = re.compile(r"^(?:ok(?:e|ay|ie)?|oki|duoc|duoc roi|co|co chu|u|uh|uhm|um|vang|da|dong y|yes|yep|chot|nhat tri|"
                  r"lam di|lap di|len di|tien hanh)(?:\s+(?:ban|nhe|nha|luon|lun|di|a|nhe ban|lap di|lap lich di))*$")
#: Câu xin lập lịch: "lập lịch", "lên kế hoạch giúp mình", "xếp lịch trình", "plan a trip" (đã `fold`).
_PLAN = re.compile(r"\b(?:lap|len|xep|tao|soan)\b(?:\s+\w+){0,3}?\s+(?:lich|ke hoach)\b|\blich trinh\b|"
                   r"\bitinerary\b|\bplan\b")
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
    """Người dùng đã đồng ý lập lịch chưa, xét ở `precheck` (trước `extract`).

    Đồng ý khi: đã đồng ý ở lượt trước; sửa form/chip (`intent_override`); câu xin lập lịch; hoặc trợ lý vừa mời mà người
    dùng trả lời "ok". Trả lời lời mời bằng thông tin chuyến ("3 ngày thôi") được `extract_result` nhận qua
    `planning_implied`, không nhận ở đây: "Thôi, Hà Nội thì sao?" cũng là câu du lịch nhưng là đổi nơi, không phải đồng
    ý (LLM thật, 10/10/2026). Cách nói khác do orchestrator khai lý do lập lịch (`structured_plan_allowed`).
    """
    if state.get("plan_consent") or state.get("intent_override"):
        return True
    query = state.get("query", "")
    if asks_for_plan(query):
        return True
    if state.get("pending_offer") and says_yes(query):
        return True
    return llm_plan_request and label not in ("explore", "out_of_scope")


def consent_update(state: dict) -> dict:
    """Đồng ý lập lịch: xoá lời mời; điểm đến trợ lý tự chọn mà chuyến chưa có thì ghi vào chuyến."""
    update = {"plan_consent": True, "pending_offer": None, "dont_know_count": 0}
    offer = state.get("pending_offer") or {}
    intent = state.get("intent") or {}
    if offer.get("destination") and not intent.get("destination"):
        update["intent"] = {**intent, "destination": offer["destination"]}
    return update


def newly_consented(state: dict) -> dict:
    """`consent_update` khi lượt này mới đồng ý; đã đồng ý từ trước thì không đổi gì."""
    return consent_update(state) if not state.get("plan_consent") else {}


def implied_update(state: dict, intent: dict) -> dict:
    """Đồng ý vì câu có thông tin chuyến (`planning_implied`), xét sau `extract`: giữ intent `extract` vừa trích."""
    return {**{key: value for key, value in consent_update({**state, "intent": intent}).items() if key != "intent"},
            "plan_consent": True}


def restored(previous: dict) -> bool:
    """`plan_consent` của hội thoại đã lưu. Bản lưu trước khi có giai đoạn khám phá (đã có lịch hoặc đang hỏi thông tin
    chuyến) không có khoá này: coi như đã đồng ý."""
    return previous.get("plan_consent", bool(previous.get("start_date_asked") or previous.get("previous_plan")))


def structured_plan_allowed(state: dict, reason: str | None) -> bool:
    """The orchestrator declares why; code verifies the applicable consent condition."""
    if state.get("plan_consent"):
        return True
    if state.get("turn_declines_offer") or state.get("turn_stop"):
        return False
    if reason == "accepts_offer":
        return bool(state.get("pending_offer"))
    return reason in ("asks_plan", "trip_details", "form")


def structured_offer_update(state: dict, *, destination: str | None, inserted: bool) -> dict:
    """Apply the PRD's ordered offer lifecycle. A button never creates a pending invitation."""
    pending = state.get("pending_offer")
    if state.get("turn_declines_offer") or state.get("turn_stop"):
        return {"pending_offer": None}
    if state.get("turn_plan_accepted"):
        return {"pending_offer": None}
    if inserted and destination:
        return {"pending_offer": {"destination": destination},
                "offered_destinations": list(dict.fromkeys([*(state.get("offered_destinations") or []), destination]))}
    current = (pending or {}).get("destination")
    if current and (current in (state.get("rejected_destinations") or []) or destination and destination != current):
        return {"pending_offer": None}
    return {"pending_offer": pending}
