from fastapi import APIRouter, Depends, Query

from src.backend.app.api.deps import get_search, get_similar

router = APIRouter(tags=["search"])


@router.get("/search")
def search(q: str, taxonomy: str | None = None, destination: str | None = None,
           limit: int = Query(20, ge=1, le=50), offset: int = Query(0, ge=0), search_products=Depends(get_search)):
    return search_products(q, taxonomy=taxonomy, destination=destination, limit=limit, offset=offset)


@router.get("/similar/{product_id}")
def similar(product_id: str, k: int = Query(8, ge=1, le=20), similar_products=Depends(get_similar)):
    return {"results": similar_products(product_id, k=k)}
