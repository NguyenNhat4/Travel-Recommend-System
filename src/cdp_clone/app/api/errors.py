import logging
import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger("cdp_clone")


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, details: dict | None = None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.details = details


def request_id(request: Request) -> str:
    return request.state.request_id


def error_response(request: Request, status: int, code: str, message: str, details: dict | None = None) -> JSONResponse:
    body = {
        "code": code,
        "message": message,
        "retryable": code == "INTERNAL_ERROR",
        "requestId": request_id(request),
    }
    if details is not None:
        body["details"] = details
    return JSONResponse(status_code=status, content={"error": body}, headers={"X-Request-ID": request_id(request)})


def install_error_handling(app: FastAPI) -> None:
    @app.middleware("http")
    async def assign_request_id(request: Request, call_next):
        incoming = request.headers.get("X-Request-ID", "")
        request.state.request_id = incoming[:64] if incoming else f"cdp-{uuid.uuid4().hex[:12]}"
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response

    @app.exception_handler(ApiError)
    async def handle_api_error(request: Request, exc: ApiError):
        return error_response(request, exc.status, exc.code, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError):
        fields = sorted({".".join(str(p) for p in err["loc"][1:]) or str(err["loc"][0]) for err in exc.errors()})
        return error_response(request, 400, "VALIDATION_ERROR", "Dữ liệu gửi lên không hợp lệ.", {"fields": fields})

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception):
        logger.exception("Unhandled error requestId=%s", request_id(request))
        return error_response(request, 500, "INTERNAL_ERROR", "Hệ thống đang gặp sự cố, vui lòng thử lại.")
