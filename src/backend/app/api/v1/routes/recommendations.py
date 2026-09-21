from fastapi import APIRouter, Query, Request

router = APIRouter(prefix="/api/v1", tags=["recommendations"])


@router.get("/recommendations")
def recommendations(request: Request, k: int = Query(5, ge=1, le=10), cdp_user_id: str | None = None):
    # TODO: lấy cdp_user_id từ JWT (core/security) thay vì query param; None → popular cho khách vãng lai
    return request.app.state.recommend(cdp_user_id, k=k)


@router.get("/popular")
def popular(request: Request, k: int = Query(4, ge=1, le=10)):
    return request.app.state.recommend(None, k=k)
