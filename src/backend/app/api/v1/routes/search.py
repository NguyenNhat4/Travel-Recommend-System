import logging
import uuid
from time import perf_counter
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from src.backend.app.api.deps import get_revoked_tokens, get_search, get_similar, get_suggest
from src.backend.app.application.auth.bearer import principal_from_header
from src.backend.app.application.itinerary.contracts import error_response
from src.backend.app.application.search.search_log import search_log_entry
from src.backend.app.application.search.use_cases import ANN_DIAGNOSTICS, canonical_query
from src.backend.app.core.logging_config import log_event
from src.backend.app.core.request_context import current_request_id

router = APIRouter(tags=["search"])
logger = logging.getLogger(__name__)


class GuestsPayload(BaseModel):
    adults: int | None = Field(None, ge=1)
    children: int | None = Field(None, ge=0)


class TravelContextPayload(BaseModel):
    """contract `TravelContext`: route chỉ dùng `guests` (1.16.0 — filter sức chứa); checkIn/checkOut/rooms bỏ qua."""
    guests: GuestsPayload | None = None


class SearchRequestPayload(BaseModel):
    query: str | None = None
    q: str | None = None
    taxonomy: str | None = None
    destination: str | None = None
    # contract 1.15.0 (FR-SRC-03): các bộ lọc tường minh của SearchRequest — trước đây route bỏ qua priceMin/Max, starRatingMin,
    # availableOnly dù contract đã khai; `origin` chỉ có hiệu lực với câu vé máy bay (xem schemas/search.yaml).
    origin: str | None = None
    priceMin: int | None = Field(None, ge=0)
    priceMax: int | None = Field(None, ge=0)
    starRatingMin: float | None = Field(None, ge=0, le=5)
    availableOnly: bool | None = True
    travelContext: TravelContextPayload | None = None
    limit: int | None = Field(20, ge=1, le=50)
    offset: int | None = Field(0, ge=0)


def _safe_search(search_products, query: str, taxonomy: str | None, destination: str | None,
                 limit: int, offset: int, *, origin: str | None = None, price_min: int | None = None,
                 price_max: int | None = None, star_min: float | None = None, available_only: bool = True,
                 guests: dict | None = None):
    started = perf_counter()
    if price_min is not None and price_max is not None and price_min > price_max:
        return JSONResponse(status_code=400, content=error_response(
            "VALIDATION_ERROR", "priceMin phải nhỏ hơn hoặc bằng priceMax.", current_request_id() or uuid.uuid4().hex
        ))
    if search_products is None or not query.strip():
        result = {
            "results": [],
            "total": 0,
            "limit": limit,
            "offset": offset,
            "topScore": None,
            # cutoff đang cấu hình (trước 05/10 hard-code 0.62 trong khi core/config.py mặc định khác)
            "cutoff": getattr(search_products, "cutoff", 0.62),
            "facets": {"taxonomy": {}, "destination": {}},
            "diagnostics": {
                **ANN_DIAGNOSTICS,
                "filteredCount": 0,
                "relevantCount": 0,
                "modelVersion": "none",
            },
        }
    else:
        result = search_products(
            query.strip(), taxonomy=taxonomy, destination=destination, origin=origin, price_min=price_min,
            price_max=price_max, star_min=star_min, available_only=available_only, limit=limit, offset=offset,
            **(guests or {}),   # travelContext.guests (1.16.0) — chỉ truyền khi request có, engine cũ không cần biết
        )
    result.setdefault("diagnostics", {})["latencyMs"] = max(
        0, round((perf_counter() - started) * 1000)
    )
    diagnostics = result["diagnostics"]
    log_event(logger, "search.run", mode=diagnostics.get("searchMode"), query_text=query[:200],
              result_count=len(result.get("results") or []), total=result.get("total"),
              engine_ms=diagnostics.get("latencyMs"), degraded=search_products is None)
    return result


def _guests(body: "SearchRequestPayload") -> dict | None:
    g = body.travelContext.guests if body.travelContext is not None else None
    if g is None:
        return None
    out = {k: v for k, v in (("adults", g.adults), ("children", g.children)) if v is not None}
    return out or None


# --- log tìm kiếm (SEARCH_LOG_QUERIES; composition root gắn `app.state.search_log` khi bật) ---------------------------------

def _search_log(request: Request | None):
    app = getattr(request, "app", None)
    return getattr(getattr(app, "state", None), "search_log", None)


async def search_log_identity(request: Request, authorization: str | None = Header(default=None)) -> tuple:
    """(cdp_user_id, session_id) cho dòng log tìm kiếm. Chỉ xác thực Bearer khi log đang bật; token thiếu / hỏng / lỗi kho
    thu hồi → (None, None), KHÔNG 401: ghi log không bao giờ được đổi response của /search."""
    if _search_log(request) is None or not authorization:
        return None, None
    verifier = getattr(request.app.state, "token_verifier", None)
    if verifier is None:
        return None, None
    try:
        principal = await principal_from_header(authorization, verifier, get_revoked_tokens(request))
    except Exception:  # noqa: BLE001 — AuthError hay lỗi Redis đều chỉ làm mất gán danh tính của dòng log
        return None, None
    return (principal.cdp_user_id, principal.session_id) if principal is not None else (None, None)


def _log_search(request: Request | None, search_products, query: str, offset: int, result, identity,
                request_filters: dict) -> None:
    """Đưa một dòng vào hàng đợi log (không chặn). Chỉ trang đầu của lượt tìm thật (như event `search` sang CDP)."""
    recorder = _search_log(request)
    if recorder is None or search_products is None or offset or not query.strip() or not isinstance(result, dict):
        return
    cdp_user_id, session_id = identity if isinstance(identity, tuple) else (None, None)
    try:
        recorder.record(search_log_entry(query.strip(), result, request_filters=request_filters,
                                         cdp_user_id=cdp_user_id, session_id=session_id))
    except Exception as exc:  # noqa: BLE001
        logger.warning("search.log.enqueue.failed error=%s", type(exc).__name__)


# Ràng buộc qua `Annotated[..., Query(...)]` để mặc định là giá trị thật: code gọi thẳng hàm route (test agent dựng backend
# giả) nhận None/20/0 thay vì đối tượng Query. `request` / `identity` đứng cuối, có mặc định: FastAPI vẫn tiêm (nhận
# `Request` theo kiểu), gọi thẳng thì không phải truyền — khi đó không ghi log.
@router.get("/search")
def search(q: str = "", taxonomy: str | None = None, destination: str | None = None, origin: str | None = None,
           priceMin: Annotated[int | None, Query(ge=0)] = None, priceMax: Annotated[int | None, Query(ge=0)] = None,
           starRatingMin: Annotated[float | None, Query(ge=0, le=5)] = None, availableOnly: bool = True,
           limit: Annotated[int, Query(ge=1, le=50)] = 20, offset: Annotated[int, Query(ge=0)] = 0,
           search_products=Depends(get_search), request: Request = None,
           identity: tuple = Depends(search_log_identity)):
    result = _safe_search(search_products, q, taxonomy, destination, limit, offset, origin=origin, price_min=priceMin,
                          price_max=priceMax, star_min=starRatingMin, available_only=availableOnly)
    _log_search(request, search_products, q, offset, result, identity, {"taxonomy": taxonomy, "destination": destination})
    return result


@router.post("/search")
def search_post(body: SearchRequestPayload, search_products=Depends(get_search), request: Request = None,
                identity: tuple = Depends(search_log_identity)):
    query = (body.query or body.q or "").strip()
    limit = body.limit if body.limit is not None else 20
    offset = body.offset if body.offset is not None else 0
    result = _safe_search(search_products, query, body.taxonomy, body.destination, limit, offset, origin=body.origin,
                          price_min=body.priceMin, price_max=body.priceMax, star_min=body.starRatingMin,
                          available_only=body.availableOnly if body.availableOnly is not None else True,
                          guests=_guests(body))
    _log_search(request, search_products, query, offset, result, identity,
                {"taxonomy": body.taxonomy, "destination": body.destination})
    return result


# Gợi ý tức thì khi gõ (FR-SRC-05): dữ liệu công khai, giống nhau cho mọi người nên trình duyệt được giữ lại 5 phút.
@router.get("/search/suggestions")
def search_suggestions(response: Response, q: str = Query(..., min_length=1, max_length=100),
                       limit: int = Query(8, ge=1, le=10), suggest_products=Depends(get_suggest)):
    if suggest_products is None:   # recsys chưa sẵn sàng: không cho cache, lần gõ sau thử lại
        return {"query": canonical_query(q), "suggestions": []}
    response.headers["Cache-Control"] = "public, max-age=300"
    return suggest_products(q, limit=limit)


@router.get("/similar/{product_id}")
def similar(product_id: str, k: int = Query(8, ge=1, le=20), similar_products=Depends(get_similar)):
    return {"results": similar_products(product_id, k=k)}
