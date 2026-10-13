"""Cờ hội thoại của giai đoạn trò chuyện, khám phá và hỏi vé (FR-AGT-06, FR-AGT-07): vòng đời của từng cờ ở một chỗ.

Ba nhóm:

| Nhóm | Sống | Ai đặt lại |
|---|---|---|
| `CARRIED` | Qua các lượt: `finalize` lưu cùng hội thoại, `intake` nạp lại (`carried`) | Luật của từng bước (đồng ý, chê, "không biết"…) và `settled` |
| `TURN_ONLY` | Chỉ trong lượt: `intake` đặt về giá trị đầu (`turn_defaults`) | `precheck`, orchestrator và job vé |
| — | `settled`: sau luật của `precheck`, bỏ câu hỏi vé còn treo khi người dùng chuyển chuyện | |

Ý nghĩa từng field: `agents/state.py`. Thêm cờ mới thì khai báo ở đây trước, để nó được lưu (hoặc được dọn) đúng nhóm.
"""
from __future__ import annotations

from copy import deepcopy

#: Lưu qua các lượt cùng intent; giá trị khi chưa có gì. Hội thoại lưu từ trước khi có cờ nào thì nhận giá trị này.
CARRIED = {"plan_consent": False, "pending_offer": None, "offered_destinations": [],
           "dont_know_count": 0, "last_suggestions": [], "rejected_destinations": [],
           "pending_fare": None,
           "skipped_details": [],
           # Sản phẩm đã cho xem trong hội thoại, mỗi cái một mã `#n` (`steps/shown.py`); `finalize` ghi.
           "shown": {"turn": 0, "seq": 0, "items": []}}

#: Chỉ trong lượt; `intake` đặt về các giá trị này mỗi lượt.
TURN_ONLY = {"offer_suggestions": False, "fare_question": False, "fare_ask": {}, "other_questions": [],
             "form_request": False}


def carried(source: dict) -> dict:
    """Bản sao các cờ `CARRIED` từ state hoặc bản ghi đã lưu; thiếu cờ nào (hoặc cờ là None) thì lấy giá trị đầu."""
    return {key: deepcopy(source.get(key, default)) if source.get(key) is not None else deepcopy(default)
            for key, default in CARRIED.items()}


def turn_defaults() -> dict:
    """Giá trị đầu lượt của các cờ `TURN_ONLY`."""
    return deepcopy(TURN_ONLY)


def settled(state: dict, update: dict) -> dict:
    """Sau luật của `precheck`: lượt không phải câu hỏi giá vé thì bỏ lần hỏi lại giá vé còn treo (`pending_fare`), để câu
    ngắn sau này không bị coi là nơi đi."""
    if state.get("pending_fare") and not update.get("fare_question"):
        update = {**update, "pending_fare": None}
    return update


# Riêng của orchestrator: `finalize` chỉ giữ `waiting_jobs` khi lượt này đi qua `gatekeep` (`orchestrator_prefill`).
ORCHESTRATOR_CARRIED = {"waiting_jobs": [], "rejected_refs": []}
ORCHESTRATOR_TURN = {"orchestrator_active": True, "orchestrator_turn": {}, "turn_jobs": [], "turn_codes": {},
                     "turn_seq": 0, "turn_pending": [], "turn_results": [], "turn_rounds": 0, "turn_tool_calls": 0,
                     "turn_signatures": [], "turn_unfinished": [], "turn_violations": [], "force_answer": False,
                     "gate_repairs": 0, "orchestrator_prefill": None, "orchestrator_fare_ids": [], "jobs_progress": False,
                     "turn_declines_offer": False, "turn_stop": False, "turn_plan_reason": None,
                     "turn_plan_accepted": False, "button_jobs": False, "button_pending_jobs": [],
                     "turn_limit_reason": None}


def orchestrator_carried(source: dict) -> dict:
    return {key: deepcopy(source.get(key, default)) for key, default in ORCHESTRATOR_CARRIED.items()}
