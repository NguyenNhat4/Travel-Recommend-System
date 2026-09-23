"""Error Envelope cho lỗi phát sinh ở biên HTTP (docs/prd/api-contract.md)."""
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.backend.app.application.itinerary.contracts import error_response
from src.backend.app.core.request_context import current_request_id


async def request_validation_error(_, __):
    request_id = current_request_id() or "validation"
    return JSONResponse(status_code=422, content=error_response(
        "VALIDATION_ERROR", "Yêu cầu không hợp lệ.", request_id
    ))


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(RequestValidationError, request_validation_error)
