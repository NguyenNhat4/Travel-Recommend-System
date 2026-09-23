from time import perf_counter

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from src.backend.app.api.deps import get_search, get_similar

router = APIRouter(tags=["search"])


class SearchRequestPayload(BaseModel):
    query: str | None = None
    q: str | None = None
    taxonomy: str | None = None
    destination: str | None = None
    limit: int | None = Field(20, ge=1, le=50)
    offset: int | None = Field(0, ge=0)


def _safe_search(search_products, query: str, taxonomy: str | None, destination: str | None,
                 limit: int, offset: int):
    started = perf_counter()
    if search_products is None or not query.strip():
        result = {
            "results": [],
            "total": 0,
            "limit": limit,
            "offset": offset,
            "topScore": None,
            "cutoff": 0.62,
            "facets": {"taxonomy": {}, "destination": {}},
            "diagnostics": {
                "searchMode": "EXACT_FILTER_SCORE",
                "approximate": False,
                "totalExact": True,
                "facetsExact": True,
                "filteredCount": 0,
                "relevantCount": 0,
                "modelVersion": "none",
            },
        }
    else:
        result = search_products(
            query.strip(), taxonomy=taxonomy, destination=destination, limit=limit, offset=offset
        )
    result.setdefault("diagnostics", {})["latencyMs"] = max(
        0, round((perf_counter() - started) * 1000)
    )
    return result


@router.get("/search")
def search(q: str = "", taxonomy: str | None = None, destination: str | None = None,
           limit: int = Query(20, ge=1, le=50), offset: int = Query(0, ge=0), search_products=Depends(get_search)):
    return _safe_search(search_products, q, taxonomy, destination, limit, offset)


@router.post("/search")
def search_post(body: SearchRequestPayload, search_products=Depends(get_search)):
    query = (body.query or body.q or "").strip()
    limit = body.limit if body.limit is not None else 20
    offset = body.offset if body.offset is not None else 0
    return _safe_search(search_products, query, body.taxonomy, body.destination, limit, offset)


@router.get("/similar/{product_id}")
def similar(product_id: str, k: int = Query(8, ge=1, le=20), similar_products=Depends(get_similar)):
    return {"results": similar_products(product_id, k=k)}
