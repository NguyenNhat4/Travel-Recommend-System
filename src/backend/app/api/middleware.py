"""Middleware HTTP: X-Request-ID và CORS."""
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from src.backend.app.core.request_context import REQUEST_ID_HEADER, bind_request_id, reset_request_id


def install_request_id(app: FastAPI) -> None:
    """Dùng lại ID của caller hoặc tạo mới, rồi trả lại trong response header."""

    @app.middleware("http")
    async def assign_request_id(request: Request, call_next):
        incoming = request.headers.get(REQUEST_ID_HEADER, "")
        request_id = incoming[:64] if incoming else f"api-{uuid.uuid4().hex[:12]}"
        token = bind_request_id(request_id)
        try:
            response = await call_next(request)
        finally:
            reset_request_id(token)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response


def install_cors(app: FastAPI, origins: str) -> None:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins.split(","),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=[REQUEST_ID_HEADER],
    )
