from time import perf_counter

from fastapi import APIRouter, Depends, Header, Query
from fastapi.responses import JSONResponse

from src.backend.app.api.deps import get_recommend
from src.backend.app.application.itinerary.contracts import error_response
from src.backend.app.core.config import Settings, get_settings
from src.backend.app.core.request_context import current_request_id
from src.backend.app.core.security import JwtError, optional_cdp_user_id

router = APIRouter(tags=["recommendations"])


@router.get("/recommendations")
def recommendations(k: int = Query(5, ge=1, le=20), destination: str | None = None,
                    authorization: str | None = Header(default=None),
                    recommend=Depends(get_recommend), settings: Settings = Depends(get_settings)):
    # cdp_user_id lấy từ JWT; không có token → None → popular cho khách vãng lai.
    try:
        cdp_user_id = optional_cdp_user_id(
            authorization, secret=settings.jwt_secret, algorithm=settings.jwt_algorithm
        )
    except JwtError as exc:
        request_id = current_request_id() or "recommendations"
        message = "Phiên đăng nhập không hợp lệ."
        if exc.code == "TOKEN_EXPIRED":
            message = "Phiên đăng nhập đã hết hạn."
        elif exc.code == "INTERNAL_ERROR":
            message = "Dịch vụ xác thực chưa được cấu hình."
        return JSONResponse(status_code=exc.status_code, content=error_response(exc.code, message, request_id))

    started = perf_counter()
    result = recommend(cdp_user_id, k=k, destination=destination)
    result["cdpUserId"] = cdp_user_id
    result.setdefault("diagnostics", {})["latencyMs"] = max(0, round((perf_counter() - started) * 1000))
    return result
