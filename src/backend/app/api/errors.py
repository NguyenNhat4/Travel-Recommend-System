"""Error Envelope cho lỗi phát sinh ở biên HTTP (docs/prd/api-contract.md)."""
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.backend.app.application.auth.errors import AuthError, RateLimited
from src.backend.app.application.itinerary.contracts import error_response
from src.backend.app.core.request_context import current_request_id

# Thông điệp cho người dùng theo mã (auth §17). Sai email và sai mật khẩu dùng CHUNG một câu.
_AUTH_MESSAGES = {
    "INVALID_CREDENTIALS": "Email hoặc mật khẩu không đúng.",
    "INVALID_TOKEN": "Phiên đăng nhập không hợp lệ.",
    "TOKEN_EXPIRED": "Phiên đăng nhập đã hết hạn.",
    "UNAUTHENTICATED": "Vui lòng đăng nhập để tiếp tục.",
    "EMAIL_ALREADY_EXISTS": "Email này đã được đăng ký.",
    "WEAK_PASSWORD": "Mật khẩu chưa đủ an toàn.",
    "TOO_MANY_ATTEMPTS": "Quá nhiều lần thử. Vui lòng thử lại sau 15 phút.",
    "CDP_UNAVAILABLE": "Không tạo được tài khoản lúc này. Vui lòng thử lại.",
    "NOT_FOUND": "Không tìm thấy.",
}


async def request_validation_error(_, __):
    request_id = current_request_id() or "validation"
    return JSONResponse(status_code=422, content=error_response(
        "VALIDATION_ERROR", "Yêu cầu không hợp lệ.", request_id
    ))


async def auth_error(_: Request, exc: AuthError):
    body = error_response(
        exc.code, _AUTH_MESSAGES.get(exc.code, "Có lỗi xảy ra."), current_request_id() or "auth", exc.retryable
    )
    if exc.details:
        body["error"]["details"] = exc.details
    headers = {"Retry-After": str(exc.retry_after_seconds)} if isinstance(exc, RateLimited) else None
    if exc.http_status == 401:
        headers = {**(headers or {}), "WWW-Authenticate": "Bearer"}
    return JSONResponse(status_code=exc.http_status, content=body, headers=headers)


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(RequestValidationError, request_validation_error)
    app.add_exception_handler(AuthError, auth_error)
