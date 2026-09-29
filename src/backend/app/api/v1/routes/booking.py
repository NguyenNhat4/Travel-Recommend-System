"""Giỏ hàng, giữ chỗ, đọc và huỷ đơn (docs/spec/hop-dong-tich-hop-backend.md §7; spec booking).

Số tiền luôn do Backend tính từ catalog; body không có trường tiền nào.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, status

from src.backend.app.api.deps import current_principal, get_use_case
from src.backend.app.api.v1.schemas.booking import (
    AddCartItemRequest,
    CancelBookingBody,
    CheckoutRequestBody,
    UpdateCartItemRequest,
)
from src.backend.app.application.auth.principal import AuthPrincipal
from src.backend.app.application.booking import Contact, ItemDetail, RoomInput, TravelerInput
from src.backend.app.application.booking.errors import ValidationFailed
from src.backend.app.domain.booking import Guests

router = APIRouter(tags=["booking"])


def _guests(body) -> Guests | None:
    return Guests(body.adults, body.children) if body is not None else None


@router.get("/cart")
async def get_cart(principal: AuthPrincipal = Depends(current_principal), cart=Depends(get_use_case("cart_service"))):
    return await cart.get(principal)


@router.post("/cart/items")
async def add_cart_item(
    body: AddCartItemRequest, principal: AuthPrincipal = Depends(current_principal),
    cart=Depends(get_use_case("cart_service")),
):
    return await cart.add(
        principal, product_id=body.productId, using_date=body.usingDate, quantity=body.quantity, nights=body.nights,
        guests=_guests(body.guests))


@router.patch("/cart/items/{cart_item_id}")
async def update_cart_item(
    cart_item_id: str, body: UpdateCartItemRequest, principal: AuthPrincipal = Depends(current_principal),
    cart=Depends(get_use_case("cart_service")),
):
    if not body.has_changes():
        raise ValidationFailed("cần ít nhất một trường")
    return await cart.update(
        principal, cart_item_id, using_date=body.usingDate, quantity=body.quantity, nights=body.nights,
        nights_given="nights" in body.model_fields_set, guests=_guests(body.guests))


@router.delete("/cart/items/{cart_item_id}")
async def remove_cart_item(
    cart_item_id: str, principal: AuthPrincipal = Depends(current_principal),
    cart=Depends(get_use_case("cart_service")),
):
    return await cart.remove(principal, cart_item_id)


@router.post("/bookings", status_code=status.HTTP_201_CREATED)
async def create_booking(
    body: CheckoutRequestBody, principal: AuthPrincipal = Depends(current_principal),
    create=Depends(get_use_case("create_booking_hold")),
):
    contact = Contact(body.contact.fullName, body.contact.email, body.contact.phone)
    details = [
        ItemDetail(
            d.cartItemId, list(d.guestNames), d.specialRequest,
            list(d.travelerRefs) if d.travelerRefs is not None else None,
            [RoomInput(tuple(r.travelerRefs), r.leadTravelerRef) for r in d.rooms] if d.rooms is not None else None)
        for d in body.itemDetails
    ]
    travelers = ([TravelerInput(t.travelerRef, t.type, t.surname, t.givenNames, t.birthDate) for t in body.travelers]
                 if body.travelers is not None else None)
    return await create(principal, contact, details, travelers)


@router.get("/bookings/{reference_code}")
async def get_booking(
    reference_code: str, principal: AuthPrincipal = Depends(current_principal),
    get=Depends(get_use_case("get_booking")),
):
    return await get(principal, reference_code)


@router.post("/bookings/{reference_code}/cancel")
async def cancel_booking(
    reference_code: str, body: CancelBookingBody | None = None, principal: AuthPrincipal = Depends(current_principal),
    cancel=Depends(get_use_case("cancel_booking")),
):
    return await cancel(principal, reference_code, body.reason if body else None)
