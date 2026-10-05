import uuid
from time import perf_counter

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from src.backend.app.api.deps import get_search, get_similar
from src.backend.app.application.itinerary.contracts import error_response
from src.backend.app.application.search.use_cases import ANN_DIAGNOSTICS
from src.backend.app.core.request_context import current_request_id

router = APIRouter(tags=["search"])


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
    limit: int | None = Field(20, ge=1, le=50)
    offset: int | None = Field(0, ge=0)


def _safe_search(search_products, query: str, taxonomy: str | None, destination: str | None,
                 limit: int, offset: int, *, origin: str | None = None, price_min: int | None = None,
                 price_max: int | None = None, star_min: float | None = None, available_only: bool = True):
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
        )
    result.setdefault("diagnostics", {})["latencyMs"] = max(
        0, round((perf_counter() - started) * 1000)
    )
    return result


@router.get("/search")
def search(q: str = "", taxonomy: str | None = None, destination: str | None = None, origin: str | None = None,
           priceMin: int | None = Query(None, ge=0), priceMax: int | None = Query(None, ge=0),
           starRatingMin: float | None = Query(None, ge=0, le=5), availableOnly: bool = True,
           limit: int = Query(20, ge=1, le=50), offset: int = Query(0, ge=0), search_products=Depends(get_search)):
    return _safe_search(search_products, q, taxonomy, destination, limit, offset, origin=origin, price_min=priceMin,
                        price_max=priceMax, star_min=starRatingMin, available_only=availableOnly)


@router.post("/search")
def search_post(body: SearchRequestPayload, search_products=Depends(get_search)):
    query = (body.query or body.q or "").strip()
    limit = body.limit if body.limit is not None else 20
    offset = body.offset if body.offset is not None else 0
    return _safe_search(search_products, query, body.taxonomy, body.destination, limit, offset, origin=body.origin,
                        price_min=body.priceMin, price_max=body.priceMax, star_min=body.starRatingMin,
                        available_only=body.availableOnly if body.availableOnly is not None else True)


@router.get("/similar/{product_id}")
def similar(product_id: str, k: int = Query(8, ge=1, le=20), similar_products=Depends(get_similar)):
    return {"results": similar_products(product_id, k=k)}
