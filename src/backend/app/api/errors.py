"""Error Envelope cho lỗi phát sinh ở biên HTTP (docs/prd/api-contract.md)."""
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.backend.app.application.auth.errors import AuthError, RateLimited
from src.backend.app.application.booking.errors import BookingError
from src.backend.app.application.catalog.errors import CatalogError
from src.backend.app.application.errors import DatabaseUnavailableError
from src.backend.app.application.itinerary.contracts import error_response
from src.backend.app.application.ports.embedder import EmbeddingUnavailableError
from src.backend.app.application.tracking.behaviour import ProductNotFoundError
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


# Thông điệp booking (docs/spec/booking/so-do-luong-dat-cho-thanh-toan.md §10.1); tiếng Việt, hiển thị được cho người dùng.
_BOOKING_MESSAGES = {
    "CART_EMPTY": "Giỏ hàng đang trống.",
    "VALIDATION_ERROR": "Yêu cầu không hợp lệ.",
    "PRODUCT_NOT_FOUND": "Không tìm thấy sản phẩm.",
    "CART_ITEM_NOT_FOUND": "Không tìm thấy mục trong giỏ hàng.",
    "BOOKING_NOT_FOUND": "Không tìm thấy đơn đặt chỗ này.",
    "PRODUCT_UNAVAILABLE": "Sản phẩm vừa hết chỗ.",
    "PRICE_CHANGED": "Giá sản phẩm đã thay đổi.",
    "DATE_OUT_OF_RANGE": "Ngày sử dụng nằm ngoài thời gian mở bán.",
    "BOOKING_PENDING_PAYMENT": "Bạn đang có một đơn chờ thanh toán.",
    "BOOKING_ALREADY_PAID": "Đơn vừa được thanh toán.",
    "BOOKING_NOT_CANCELLABLE": "Đơn này không huỷ được.",
    "PAYMENT_PROVIDER_UNAVAILABLE": "Cổng thanh toán tạm thời không phản hồi. Vui lòng thử lại.",
    "INVALID_WEBHOOK_SIGNATURE": "Chữ ký không hợp lệ.",
    "DIRECT_BOOKING_ONLY": "Khách sạn và vé máy bay được đặt trực tiếp, không thêm vào giỏ hàng.",
    "BOOKING_DRAFT_NOT_FOUND": "Không tìm thấy phiên thanh toán này.",
    "BOOKING_DRAFT_EXPIRED": "Phiên thanh toán đã hết hạn.",
    "INTERNAL_ERROR": "Dịch vụ tạm thời không phản hồi. Vui lòng thử lại.",
}


async def booking_error(_: Request, exc: BookingError):
    body = error_response(
        exc.code, exc.user_message or _BOOKING_MESSAGES.get(exc.code, "Có lỗi xảy ra."),
        current_request_id() or "booking", exc.retryable)
    if exc.details:
        body["error"]["details"] = exc.details
    headers = {"Retry-After": "5"} if exc.http_status == 503 else None
    return JSONResponse(status_code=exc.http_status, content=body, headers=headers)


# Thông điệp catalog (backend §4.2, §8.2; frontend §8).
_CATALOG_MESSAGES = {
    "VALIDATION_ERROR": "Yêu cầu không hợp lệ.",
    "PRODUCT_NOT_FOUND": "Sản phẩm này không còn trên V-OTA.",
    "PRODUCT_NOT_INDEXED": "Chưa có gợi ý tương tự cho sản phẩm này.",
    "SEARCH_UNAVAILABLE": "Dịch vụ gợi ý tạm thời chưa sẵn sàng. Vui lòng thử lại.",
}


def _catalog_response(code: str, http_status: int, retryable: bool, details: dict | None) -> JSONResponse:
    body = error_response(code, _CATALOG_MESSAGES.get(code, "Có lỗi xảy ra."),
                          current_request_id() or "catalog", retryable)
    if details:
        body["error"]["details"] = details
    return JSONResponse(status_code=http_status, content=body)


async def catalog_error(_: Request, exc: CatalogError):
    return _catalog_response(exc.code, exc.http_status, exc.retryable, exc.details)


async def tracked_product_not_found(_: Request, exc: ProductNotFoundError):
    return _catalog_response("PRODUCT_NOT_FOUND", 404, False, {"productId": exc.product_id})


async def embedding_unavailable(_: Request, exc: EmbeddingUnavailableError):
    # Adapter embedding đã ghi log lỗi; ở đây chỉ đưa lý do (từ cố định) ra client thay cho 500 chung chung.
    return _catalog_response("SEARCH_UNAVAILABLE", 503, exc.retryable, {"reason": exc.reason})


async def database_unavailable(_: Request, __: Exception):
    """PostgreSQL không với tới được: 503 chuẩn, thử lại được, không lộ chi tiết kết nối."""
    body = error_response(
        "DATABASE_UNAVAILABLE", "Hệ thống dữ liệu tạm thời không phản hồi. Vui lòng thử lại sau ít phút.",
        current_request_id() or "database", True)
    return JSONResponse(status_code=503, content=body, headers={"Retry-After": "5"})


def install_error_handlers(app: FastAPI, database_driver_errors: tuple[type[Exception], ...] = ()) -> None:
    """`database_driver_errors`: lỗi của driver DB (ví dụ psycopg.OperationalError) cho lỗi rớt giữa chừng.
    Composition root truyền vào để lớp `api` không phải import driver (architecture.md §2, quy tắc 6)."""
    app.add_exception_handler(EmbeddingUnavailableError, embedding_unavailable)
    app.add_exception_handler(DatabaseUnavailableError, database_unavailable)
    for error_type in database_driver_errors:
        app.add_exception_handler(error_type, database_unavailable)
    app.add_exception_handler(BookingError, booking_error)
    app.add_exception_handler(CatalogError, catalog_error)
    app.add_exception_handler(ProductNotFoundError, tracked_product_not_found)
    app.add_exception_handler(RequestValidationError, request_validation_error)
    app.add_exception_handler(AuthError, auth_error)
