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
