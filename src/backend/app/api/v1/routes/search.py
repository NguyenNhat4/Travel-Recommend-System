from fastapi import APIRouter, Query, Request

router = APIRouter(prefix="/api/v1", tags=["search"])


@router.get("/search")
def search(request: Request, q: str, taxonomy: str | None = None, destination: str | None = None,
           limit: int = Query(20, ge=1, le=50), offset: int = Query(0, ge=0)):
    return request.app.state.search(q, taxonomy=taxonomy, destination=destination, limit=limit, offset=offset)


@router.get("/similar/{product_id}")
def similar(request: Request, product_id: str, k: int = Query(8, ge=1, le=20)):
    return {"results": request.app.state.similar(product_id, k=k)}
