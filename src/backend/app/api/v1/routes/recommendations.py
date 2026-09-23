from fastapi import APIRouter, Depends, Query

from src.backend.app.api.deps import get_recommend

router = APIRouter(tags=["recommendations"])


@router.get("/recommendations")
def recommendations(k: int = Query(5, ge=1, le=10), cdp_user_id: str | None = None, recommend=Depends(get_recommend)):
    # TODO: lấy cdp_user_id từ JWT (core/security) thay vì query param; None → popular cho khách vãng lai
    return recommend(cdp_user_id, k=k)


@router.get("/popular")
def popular(k: int = Query(4, ge=1, le=10), recommend=Depends(get_recommend)):
    return recommend(None, k=k)
