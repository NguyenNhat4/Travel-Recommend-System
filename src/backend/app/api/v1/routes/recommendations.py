from time import perf_counter

from fastapi import APIRouter, Depends, Query

from src.backend.app.api.deps import get_recommend, optional_principal, require_internal_api, require_service_token
from src.backend.app.application.auth.principal import AuthPrincipal

router = APIRouter(tags=["recommendations"])


def _run(recommend, cdp_user_id: str | None, k: int, destination: str | None) -> dict:
    started = perf_counter()
    result = recommend(cdp_user_id, k=k, destination=destination)
    result["cdpUserId"] = cdp_user_id
    result.setdefault("diagnostics", {})["latencyMs"] = max(0, round((perf_counter() - started) * 1000))
    return result


@router.get("/recommendations")
def recommendations(k: int = Query(5, ge=1, le=20), destination: str | None = None,
                    principal: AuthPrincipal | None = Depends(optional_principal),
                    recommend=Depends(get_recommend)):
    # Danh tính chỉ đến từ JWT đã kiểm (auth §3.5). Không nhận cdp_user_id qua query: đó là IDOR.
    # Không token → khách → popular. Token hỏng → 401 ở optional_principal, không hạ thành khách.
    return _run(recommend, principal.cdp_user_id if principal else None, k, destination)


@router.get("/internal/recommendations",
            dependencies=[Depends(require_internal_api), Depends(require_service_token)])
def internal_recommendations(cdp_user_id: str = Query(min_length=1), k: int = Query(5, ge=1, le=20),
                             destination: str | None = None, recommend=Depends(get_recommend)):
    """Gợi ý theo cdp_user_id tuỳ ý cho demo/eval (auth §14.4). Chỉ service nội bộ."""
    return _run(recommend, cdp_user_id, k, destination)
