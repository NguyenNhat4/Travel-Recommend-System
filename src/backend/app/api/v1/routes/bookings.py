"""Checkout và đọc lại đơn (backend §7.2–7.3). Purchase được ghi sang CDP trước khi trả 201."""
from typing import Any

from fastapi import APIRouter, Depends, status

from src.backend.app.api.deps import current_principal, get_booking_reader, get_checkout
from src.backend.app.api.v1.schemas.booking import CheckoutRequest
from src.backend.app.application.auth.principal import AuthPrincipal

router = APIRouter(tags=["booking"])


@router.post("/bookings", status_code=status.HTTP_201_CREATED)
async def create_booking(body: CheckoutRequest, principal: AuthPrincipal = Depends(current_principal),
                         checkout: Any = Depends(get_checkout)):
    return await checkout(principal.cdp_user_id, body.contact.model_dump(),
                          [detail.model_dump() for detail in body.itemDetails])


@router.get("/bookings/{reference_code}")
async def get_booking(reference_code: str, principal: AuthPrincipal = Depends(current_principal),
                      reader: Any = Depends(get_booking_reader)):
    return await reader(principal.cdp_user_id, reference_code)
