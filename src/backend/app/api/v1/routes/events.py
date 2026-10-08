"""POST /events — ghi hành vi Backend không tự thấy được, hiện chỉ product_view (backend §7.5, FR-CDP-01)."""
from __future__ import annotations

from typing import Any

import logging

from fastapi import APIRouter, Body, Depends, Response, status

from src.backend.app.api.deps import current_principal, get_use_case
from src.backend.app.application.auth.principal import AuthPrincipal
from src.backend.app.application.catalog.errors import InvalidCatalogRequest

from src.backend.app.core.logging_config import log_event

router = APIRouter(tags=["events"])
logger = logging.getLogger(__name__)

_FIELDS = {"eventName", "productId"}


@router.post("/events", status_code=status.HTTP_202_ACCEPTED)
async def track_event(
    body: Any = Body(...), principal: AuthPrincipal = Depends(current_principal),
    tracker=Depends(get_use_case("behaviour_tracker")),
):
    # TrackEventRequest: additionalProperties false, eventName chỉ product_view → sai thì 400, không 422.
    if not isinstance(body, dict) or set(body) != _FIELDS or body["eventName"] != "product_view" \
            or not isinstance(body["productId"], str) or not body["productId"].strip():
        invalid = sorted(set(body) ^ _FIELDS) if isinstance(body, dict) else ["body"]
        raise InvalidCatalogRequest("sự kiện không hợp lệ", {"fields": invalid or ["eventName", "productId"]})
    await tracker.track_product_view(principal.cdp_user_id, body["productId"].strip())
    log_event(logger, "events.ingest", count=1, event_name=body["eventName"], cdp_ok=True)
    return Response(status_code=status.HTTP_202_ACCEPTED)
