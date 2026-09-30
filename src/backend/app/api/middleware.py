"""Middleware HTTP: X-Request-ID, CORS và đo lần gọi web (docs/prd/deployment-plan.md §5)."""
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from src.backend.app.core.call_context import call_scope
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


def route_template(request: Request) -> str:
    """Đường dẫn thật với giá trị tham số thay bằng `{tên}` (không lộ id / mã đơn trong tên chỉ số).

    Không dựa vào `route.path`: route gắn qua `include_router(prefix=…)` có thể chỉ giữ phần sau prefix."""
    values = {str(v): k for k, v in (request.path_params or {}).items()}
    return "/".join("{%s}" % values[part] if part in values else part for part in request.url.path.split("/"))


def install_call_telemetry(app: FastAPI, prefix: str = "/api/v1") -> None:
    """Mỗi request dưới `prefix` là một lần gọi nguồn `web`: route mẫu (không có giá trị tham số), mã trạng thái, thời
    gian và chi tiết use case ghi vào (`application/telemetry.py`). Không ghi query string hay body."""

    @app.middleware("http")
    async def record_call(request: Request, call_next):
        telemetry = getattr(request.app.state, "call_telemetry", None)
        if telemetry is None or not request.url.path.startswith(prefix):
            return await call_next(request)
        started = time.perf_counter()
        status = 500
        with call_scope("web") as detail:
            try:
                response = await call_next(request)
                status = response.status_code
                return response
            finally:
                name = f"{request.method} {route_template(request)}" if request.scope.get("route") else \
                    f"{request.method} (không khớp route)"
                telemetry.record({"source": "web", "kind": "http", "name": name, "status": status,
                                  "ms": round((time.perf_counter() - started) * 1000, 1), **detail})
