"""Giỏ hàng, đơn nháp của Đặt ngay, giữ chỗ, đọc và huỷ đơn (docs/spec/hop-dong-tich-hop-backend.md §7; spec booking).

Giỏ và đơn nháp nhận cả khách chưa đăng nhập (dependency `cart_owner`); đơn luôn cần đăng nhập
(docs/spec/booking/dat-truc-tiep-theo-don-nhap.md §8).

Số tiền luôn do Backend tính từ catalog; body không có trường tiền nào.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, status

from src.backend.app.api.deps import cart_owner, current_principal, get_use_case, require_service_token
from src.backend.app.api.v1.schemas.booking import (
    AddCartItemRequest,
    CancelBookingBody,
    CheckoutRequestBody,
    CreateBookingDraftBody,
    GuestMergeBody,
    UpdateCartItemRequest,
)
from src.backend.app.application.auth.principal import AuthPrincipal
from src.backend.app.application.booking import (
    CartOwner, Contact, DocumentsInput, DraftItemRequest, ItemDetail, RoomInput, TravelerInput,
)
from src.backend.app.application.booking.errors import ValidationFailed
from src.backend.app.core.logging_config import log_event
from src.backend.app.domain.booking import Guests

router = APIRouter(tags=["booking"])
logger = logging.getLogger(__name__)


def _kind(owner: CartOwner) -> str:
    return "guest" if owner.is_guest else "user"


def _documents(body) -> DocumentsInput | None:
    if body is None:
        return None
    return DocumentsInput(body.title, body.nationality, body.docType, body.docNumber, body.docExpiry, body.escortTravelerRef)


def _guests(body) -> Guests | None:
    return Guests(body.adults, body.children) if body is not None else None


@router.get("/cart")
async def get_cart(owner: CartOwner = Depends(cart_owner), cart=Depends(get_use_case("cart_service"))):
    return await cart.get(owner)


@router.post("/cart/items")
async def add_cart_item(
    body: AddCartItemRequest, owner: CartOwner = Depends(cart_owner),
    cart=Depends(get_use_case("cart_service")),
):
    result = await cart.add(
        owner, product_id=body.productId, using_date=body.usingDate, quantity=body.quantity, nights=body.nights,
        guests=_guests(body.guests))
    log_event(logger, "cart.item.add", product_id=body.productId, quantity=body.quantity,
              using_date=str(body.usingDate), owner_kind=_kind(owner))
    return result


@router.patch("/cart/items/{cart_item_id}")
async def update_cart_item(
    cart_item_id: str, body: UpdateCartItemRequest, owner: CartOwner = Depends(cart_owner),
    cart=Depends(get_use_case("cart_service")),
):
    if not body.has_changes():
        raise ValidationFailed("cần ít nhất một trường")
    return await cart.update(
        owner, cart_item_id, using_date=body.usingDate, quantity=body.quantity, nights=body.nights,
        nights_given="nights" in body.model_fields_set, guests=_guests(body.guests))


@router.delete("/cart/items/{cart_item_id}")
async def remove_cart_item(
    cart_item_id: str, owner: CartOwner = Depends(cart_owner),
    cart=Depends(get_use_case("cart_service")),
):
    result = await cart.remove(owner, cart_item_id)
    log_event(logger, "cart.item.remove", cart_item_id=cart_item_id, owner_kind=_kind(owner))
    return result


def _draft_shape_error(message: str) -> ValidationFailed:
    error = ValidationFailed(message, {"fields": [{"field": "items", "reason": "REQUIRED", "message": message}]})
    error.user_message = message
    return error


@router.post("/booking-drafts", status_code=status.HTTP_201_CREATED)
async def create_booking_draft(
    body: CreateBookingDraftBody, owner: CartOwner = Depends(cart_owner),
    drafts=Depends(get_use_case("booking_draft_service")),
):
    """Đặt ngay: đơn nháp chỉ gồm các mục của lần đặt này (spec dat-truc-tiep-theo-don-nhap.md §4.1)."""
    if (body.items is None) == (body.fromBooking is None):
        raise _draft_shape_error("Gửi đúng một trong hai: danh sách sản phẩm cần đặt, hoặc mã đơn cần đặt lại.")
    if body.fromBooking is not None:
        result = await drafts.create(owner, from_booking=body.fromBooking)
        log_event(logger, "draft.create", owner_kind=_kind(owner), draft_id=result.get("draftId"))
        return result
    items = [DraftItemRequest(i.productId, i.usingDate, i.quantity, i.nights, _guests(i.guests)) for i in body.items]
    result = await drafts.create(owner, items=items, allow_partial=body.allowPartial)
    log_event(logger, "draft.create", owner_kind=_kind(owner), draft_id=result.get("draftId"), item_count=len(items))
    return result


@router.get("/booking-drafts/{draft_id}")
async def get_booking_draft(
    draft_id: str, owner: CartOwner = Depends(cart_owner), drafts=Depends(get_use_case("booking_draft_service")),
):
    return await drafts.get(owner, draft_id)


@router.patch("/booking-drafts/{draft_id}/items/{cart_item_id}")
async def update_booking_draft_item(
    draft_id: str, cart_item_id: str, body: UpdateCartItemRequest, owner: CartOwner = Depends(cart_owner),
    drafts=Depends(get_use_case("booking_draft_service")),
):
    if not body.has_changes():
        raise ValidationFailed("cần ít nhất một trường")
    result = await drafts.update_item(
        owner, draft_id, cart_item_id, using_date=body.usingDate, quantity=body.quantity, nights=body.nights,
        nights_given="nights" in body.model_fields_set, guests=_guests(body.guests))
    log_event(logger, "draft.update", draft_id=draft_id, owner_kind=_kind(owner))
    return result


@router.delete("/booking-drafts/{draft_id}/items/{cart_item_id}")
async def remove_booking_draft_item(
    draft_id: str, cart_item_id: str, owner: CartOwner = Depends(cart_owner),
    drafts=Depends(get_use_case("booking_draft_service")),
):
    result = await drafts.remove_item(owner, draft_id, cart_item_id)
    log_event(logger, "draft.update", draft_id=draft_id, owner_kind=_kind(owner))
    return result


@router.post("/guest-bookings/merge", dependencies=[Depends(require_service_token)])
async def merge_guest_booking(
    body: GuestMergeBody, principal: AuthPrincipal = Depends(current_principal),
    merge=Depends(get_use_case("merge_guest_booking")),
):
    """Chỉ BFF gọi (service token + Bearer của tài khoản vừa đăng nhập): gộp giỏ và đơn nháp của khách (spec §8.3)."""
    return await merge(principal, body.guestId)


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
    travelers = ([TravelerInput(t.travelerRef, t.type, t.surname, t.givenNames, t.birthDate, _documents(t.documents))
                  for t in body.travelers] if body.travelers is not None else None)
    return await create(principal, contact, details, travelers, draft_id=body.draftId)


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
