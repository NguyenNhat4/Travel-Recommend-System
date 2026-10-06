"""X-Request-ID của request đang xử lý (hop-dong-tich-hop-backend.md §8.4).

Chỉ giữ `ContextVar`, không import FastAPI: `application` và `infrastructure` đọc ID từ đây để mọi lời gọi
downstream mang cùng một ID. Middleware gán ID nằm ở `api/middleware.py` (docs/prd/architecture.md §2, quy tắc 9).
"""
from contextvars import ContextVar, Token

REQUEST_ID_HEADER = "X-Request-ID"
_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)


def current_request_id() -> str | None:
    return _request_id.get()


def bind_request_id(request_id: str) -> Token:
    return _request_id.set(request_id)


def reset_request_id(token: Token) -> None:
    _request_id.reset(token)


# Người gọi của request đang xử lý, chỉ để ghi log (`http.request`: user_kind, user_id_hash). Một dict dùng chung để
# dependency chạy trong threadpool cũng ghi ngược lại được cho middleware ở ngoài (cùng cách với call_context).
_actor: ContextVar[dict | None] = ContextVar("log_actor", default=None)


def open_actor() -> tuple[dict, Token]:
    holder: dict = {"kind": "anon", "id": None}
    return holder, _actor.set(holder)


def close_actor(token: Token) -> None:
    _actor.reset(token)


def note_actor(kind: str, user_id: str | None = None) -> None:
    """`kind`: anon | user | guest | service. Ngoài request thì bỏ qua; `service` không đè user/guest đã biết."""
    holder = _actor.get()
    if holder is None or (kind == "service" and holder["kind"] != "anon"):
        return
    holder["kind"] = kind
    if user_id:
        holder["id"] = user_id
