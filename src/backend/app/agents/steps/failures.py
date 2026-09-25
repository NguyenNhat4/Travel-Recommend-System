"""Gom lỗi của lượt truy xuất thành đúng một Error Envelope cho `dead_letter`."""
from __future__ import annotations

from . import messages
from .evaluation import tool_errors
from .messages import failure

PLAN_ERRORS = {"INVALID_TOOL_PLAN", "INVALID_ARGUMENTS", "TOOL_NOT_ALLOWED"}


def terminal_failure(state: dict) -> dict:
    """Lỗi auth đi trước, rồi lỗi lập plan, còn lại là upstream; không che lỗi thành thành công."""
    errors = tool_errors(state)
    auth = next((e for e in errors if e.get("httpStatus") == 401), None)
    if auth:
        code = auth["code"] if auth["code"] in {"INVALID_TOKEN", "TOKEN_EXPIRED"} else "INVALID_TOKEN"
        return failure(state, code, messages.INVALID_CREDENTIALS, 401)
    if any(e.get("code") in PLAN_ERRORS for e in errors):
        return failure(state, "LLM_UNAVAILABLE", messages.PLAN_UNAVAILABLE, retryable=True)
    return failure(state, "SEARCH_UNAVAILABLE", messages.SEARCH_UNAVAILABLE,
                   retryable=any(e["retryable"] for e in errors))
