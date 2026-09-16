"""X-Request-ID handling (hop-dong-tich-hop-backend.md §8.4): reuse the caller's ID or create one, and expose it
to outbound clients so every downstream call carries the same ID."""
import uuid
from contextvars import ContextVar

from fastapi import FastAPI, Request

REQUEST_ID_HEADER = "X-Request-ID"
_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)


def current_request_id() -> str | None:
    return _request_id.get()


def install_request_id(app: FastAPI) -> None:
    @app.middleware("http")
    async def assign_request_id(request: Request, call_next):
        incoming = request.headers.get(REQUEST_ID_HEADER, "")
        request_id = incoming[:64] if incoming else f"api-{uuid.uuid4().hex[:12]}"
        token = _request_id.set(request_id)
        try:
            response = await call_next(request)
        finally:
            _request_id.reset(token)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response
