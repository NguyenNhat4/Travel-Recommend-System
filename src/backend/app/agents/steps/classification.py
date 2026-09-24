"""Đầu vào cho LLM trích intent, và luật biến kết quả trích được thành update cho state."""
from __future__ import annotations

from copy import deepcopy
from datetime import date
import json

from src.backend.app.application.itinerary.contracts import bounds, valid
from src.backend.app.domain.itinerary.planning import merge_intent

from ..models import Extraction
from .history import sanitize_conversation_history
from .messages import event, failure, message
from .prompts import EXTRACT_PROMPT


def extraction_input(state: dict) -> list:
    """Message hiện tại cộng lịch sử, intent/constraints và sản phẩm đã hiển thị ở các lượt trước."""
    language = "Vietnamese" if state.get("language", "vi") == "vi" else "English"
    payload = {"message": state.get("query", ""),
               "conversation_history": sanitize_conversation_history(state.get("conversation_history", [])),
               "previous_intent": state.get("intent", {}),
               "previous_constraints": state.get("constraints", {}),
               "previous_selection": state.get("previous_selection", []),
               "today": date.today().isoformat()}
    return [("system", EXTRACT_PROMPT + f"\nUse {language} for any natural-language content."),
            ("human", json.dumps(payload, ensure_ascii=False))]


def _merged_intent(state: dict, patch: dict) -> tuple[dict, dict | None]:
    """Intent mới = intent cũ + patch của LLM + chip người dùng sửa tay (chip là quyền cao nhất)."""
    intent = merge_intent(state.get("intent", {}), patch)
    override = state.get("intent_override", {})
    if override:
        # Chip changes are authoritative; preserve explicit null resets.
        if not valid("TripIntentPatch", override):
            return intent, {"route": "error",
                            **failure(state, "VALIDATION_ERROR", message(state, "invalid_override"), 422)}
        intent.update(deepcopy(override))
    return intent, None


def _merged_constraints(state: dict, result: Extraction, patch: dict, intent: dict) -> dict:
    """Ràng buộc mới; các luật dưới đây giữ cho `require_hotel` và `exclude_*` không tự mâu thuẫn."""
    constraints = deepcopy(state.get("constraints", {}))
    changes = result.constraints.model_dump(exclude_none=True)
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


def classify_result(state: dict, result: Extraction) -> dict:
    """Update của `classify`, gồm `route` quyết định nhánh đi tiếp (`routing.route_after_classify`)."""
    result = Extraction.model_validate(result)
    patch = result.patch.model_dump(mode="json", exclude_none=True)
    if result.patch.party is not None:
        patch["party"] = result.patch.party.model_dump(mode="json")
    intent, invalid_override = _merged_intent(state, patch)
    if invalid_override is not None:
        return invalid_override
    constraints = _merged_constraints(state, result, patch, intent)
    conflicting_days = _days_from_end_date(result, intent, patch, state.get("intent_override", {}))
    conflict = result.conflict or conflicting_days
    missing = [key for key in ("destination", "days") if not intent.get(key)]
    refusal = result.domain in {"out_of_domain", "side_effect"}
    # A message that states any trip detail is a travel request even when the model calls it conversation;
    # otherwise `converse` would answer it and the missing fields would never be asked for.
    domain = "travel" if result.domain == "conversation" and any(patch.values()) else result.domain
    update = {"intent": intent, "constraints": constraints, "llm_used": True,
              "interaction_type": domain, "refusal": refusal, "missing_fields": missing,
              "events": [event("classify", "intent extracted")]}
    if domain != "travel":
        return {**update, "route": "simple"}
    min_days, max_days = bounds("TripIntent", "days")
    if intent.get("days") is not None and not min_days <= intent["days"] <= max_days:
        return {**update, "route": "error",
                **failure(state, "INVALID_TRIP_DURATION", message(state, "invalid_duration"), 400)}
    if not valid("TripIntent", intent):
        return {**update, "route": "error",
                **failure(state, "VALIDATION_ERROR", message(state, "invalid_intent"), 422)}
    if conflict or constraints.get("unverified_requirements"):
        return {**update, "route": "missing_info", "clarification_reason": "conflict" if conflict else "unverified"}
    return {**update, "route": "missing_info" if missing else "tool", "clarification_reason": None}
