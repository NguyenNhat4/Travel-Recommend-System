from fastapi import APIRouter, Query, Request

from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/v1", tags=["search"])


class SearchRequestPayload(BaseModel):
    query: str | None = None
    q: str | None = None
    taxonomy: str | None = None
    destination: str | None = None
    limit: int | None = Field(20, ge=1, le=50)
    offset: int | None = Field(0, ge=0)


def _safe_search(request: Request, query: str, taxonomy: str | None, destination: str | None, limit: int, offset: int):
    search_fn = getattr(request.app.state, "search", None)
    if search_fn is None or not query.strip():
        return {
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
    return search_fn(query.strip(), taxonomy=taxonomy, destination=destination, limit=limit, offset=offset)


@router.get("/search")
def search(request: Request, q: str = "", taxonomy: str | None = None, destination: str | None = None,
           limit: int = Query(20, ge=1, le=50), offset: int = Query(0, ge=0)):
    return _safe_search(request, q, taxonomy, destination, limit, offset)


@router.post("/search")
def search_post(request: Request, body: SearchRequestPayload):
    query = (body.query or body.q or "").strip()
    limit = body.limit if body.limit is not None else 20
    offset = body.offset if body.offset is not None else 0
    return _safe_search(request, query, body.taxonomy, body.destination, limit, offset)


@router.get("/similar/{product_id}")
def similar(request: Request, product_id: str, k: int = Query(8, ge=1, le=20)):
    return {"results": request.app.state.similar(product_id, k=k)}
