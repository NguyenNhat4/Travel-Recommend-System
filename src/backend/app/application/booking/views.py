"""Dựng response đúng contract (schemas/booking.yaml) từ thực thể domain. Trả dict thuần, không phụ thuộc web framework."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Mapping, Sequence

from src.backend.app.domain.booking import (
    Booking, BookingDraft, BookingItem, Cart, CartLine, FareLine, Traveler, cancellable_until, fare_lines, lines_total,
)
from src.backend.app.domain.booking.status import BookingStatus, PaymentStatus
from src.backend.app.domain.catalog.models import Product

_UNKNOWN_DESTINATION = "Khác"


def iso(value: datetime | None) -> str | None:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if value else None


def product_summary(
    product: Product, *, unit_price: int | None = None, name: str | None = None, with_capacity: bool = False,
) -> dict:
    summary = {
        "productId": product.product_id,
        "name": name or product.name,
        "taxonomy": product.taxonomy,
        "destination": product.destination,
        "unitPrice": unit_price if unit_price is not None else (
            int(product.unit_price) if product.unit_price is not None else None),
        "currency": product.currency,
        "priceUnit": product.price_unit,
        "available": product.available,
        "availableFrom": product.available_from.isoformat() if product.available_from else None,
        "availableTo": product.available_to.isoformat() if product.available_to else None,
        "imageUrl": product.image_url,
        **({"attributes": product.attributes} if product.taxonomy == "flight" else {}),
    }
    # Sức chứa hạng phòng để Web hiện "Tối đa n khách/phòng" ở bước xếp phòng; không có thì không gửi trường attributes.
    if with_capacity and product.max_occupancy:
        summary["attributes"] = {"maxOccupancy": product.max_occupancy}
    return summary


def _fares(fares: list[FareLine]) -> list[dict]:
    return [fare.to_json() for fare in fares]


_KEEP = object()


def _line_items(lines: Sequence[CartLine], products: Mapping[str, Product]) -> list[dict]:
    """Mục của giỏ hoặc của đơn nháp theo schema `CartItem`; giá và dòng giá tính theo catalog tại lúc đọc."""
    items = []
    for line in lines:
        product = products.get(line.product_id)
        if product is None:
            continue
        price = int(product.unit_price) if product.unit_price is not None else 0
        fares = fare_lines(product.taxonomy, price, product.attributes, quantity=line.quantity, nights=line.nights,
                           adults=line.adults, children=line.children)
        items.append({
            "cartItemId": line.cart_item_id,
            "product": product_summary(product, with_capacity=True),
            "usingDate": line.using_date.isoformat(),
            "quantity": line.quantity,
            "nights": line.nights if product.taxonomy == "hotel" else None,
            "guests": {"adults": line.adults, "children": line.children},
            "fares": _fares(fares),
            "lineTotal": lines_total(fares),
        })
    return items


def cart_response(cart: Cart, products: Mapping[str, Product], *, cdp_user_id: object = _KEEP) -> dict:
    """`cdp_user_id=None` cho giỏ của khách chưa đăng nhập (R-GST-13); mặc định lấy theo giỏ."""
    items = _line_items(cart.lines, products)
    total = sum(item["lineTotal"] for item in items)
    return {
        "cartId": cart.cart_id,
        "cdpUserId": cart.cdp_user_id if cdp_user_id is _KEEP else cdp_user_id,
        "items": items,
        "itemCount": len(items),
        "subtotal": total,
        "total": total,
        "currency": "VND",
        "updatedAt": iso(cart.updated_at),
    }


def draft_response(
    draft: BookingDraft, products: Mapping[str, Product], *, cdp_user_id: str | None,
    rejected: Sequence[dict] | None = None,
) -> dict:
    """`BookingDraft` của contract: mục dùng chung schema với mục giỏ (`cartItemId` là mã mục của đơn nháp)."""
    items = _line_items(draft.lines, products)
    total = sum(item["lineTotal"] for item in items)
    body = {
        "draftId": draft.draft_id,
        "cdpUserId": cdp_user_id,
        "expiresAt": iso(draft.expires_at),
        "items": items,
        "itemCount": len(items),
        "subtotal": total,
        "total": total,
        "currency": "VND",
    }
    if rejected:
        body["rejectedItems"] = list(rejected)
    return body


_MISMATCH_REASONS = {"AMOUNT_MISMATCH"}
_KNOWN_REASONS = {"CARD_DECLINED", "INSUFFICIENT_FUNDS", "EXPIRED_CARD", "INCORRECT_CVC", "AUTHENTICATION_FAILED",
                  "PROCESSING_ERROR", "TOO_MANY_ATTEMPTS", "AMOUNT_MISMATCH"}


def _failure_reason(booking: Booking) -> str | None:
    payment = booking.payment
    if payment is None or not payment.last_failure_code:
        return None
    code = payment.last_failure_code
    return code if code in _KNOWN_REASONS else "PROCESSING_ERROR"


def _payment(booking: Booking) -> dict | None:
    payment = booking.payment
    if payment is None:
        return None
    return {
        "status": payment.status.value.upper(),
        "amount": payment.amount,
        "currency": payment.currency,
        "checkoutUrl": payment.checkout_url if payment.status is PaymentStatus.OPEN else None,
        "failedAttempts": payment.failed_attempts,
        "failureReason": _failure_reason(booking),
        "refundedAmount": payment.amount if payment.status is PaymentStatus.REFUNDED else 0,
    }


def _cancellation(booking: Booking) -> dict | None:
    if booking.status is not BookingStatus.CANCELLED or booking.cancelled_at is None:
        return None
    refunding = booking.payment is not None and booking.payment.status in (
        PaymentStatus.REFUND_PENDING, PaymentStatus.REFUNDED, PaymentStatus.REFUND_FAILED)
    return {
        "cancelledAt": iso(booking.cancelled_at),
        "reason": booking.cancel_reason,
        "refundAmount": booking.payment.amount if refunding else 0,
    }


def _item_fares(item: BookingItem) -> list[FareLine]:
    """Dòng giá của mục; đơn tạo trước khi có dòng giá thì dựng lại theo công thức không có trẻ em."""
    if item.fares:
        return item.fares
    return fare_lines(item.taxonomy, item.unit_price, {}, quantity=item.quantity, nights=item.nights,
                      adults=item.quantity, children=0)


def _traveler_entry(traveler: Traveler, *, room_no: int | None, is_lead: bool) -> dict:
    entry = {"fullName": traveler.full_name, "type": traveler.type.value.upper(), "roomNo": room_no, "isLead": is_lead}
    docs = traveler.documents
    if docs is not None:
        # Số giấy tờ đầy đủ và ngày hết hạn không ra khỏi Backend (FR-BKG-13, NFR-SEC-01).
        entry["documents"] = {"title": docs.title, "nationality": docs.nationality, "docType": docs.doc_type,
                              "docNumberLast4": docs.doc_number[-4:] if docs.doc_number else None}
    return entry


def _item_travelers(item: BookingItem, party: Mapping[str, Traveler]) -> list[dict]:
    """Hành khách của một mục, không có ngày sinh (NFR-SEC-01, spec §8.6). Khách sạn kèm số phòng và người đại diện."""
    out: list[dict] = []
    if item.rooms:
        for room_no, room in enumerate(item.rooms, start=1):
            for ref in room.traveler_refs:
                if ref in party:
                    out.append(_traveler_entry(party[ref], room_no=room_no, is_lead=ref == room.lead_traveler_ref))
    else:
        for ref in item.traveler_refs:
            if ref in party:
                out.append(_traveler_entry(party[ref], room_no=None, is_lead=False))
    return out


def booking_response(booking: Booking, products: Mapping[str, Product]) -> dict:
    groups: dict[str, list[dict]] = {}
    party = {traveler.ref: traveler for traveler in booking.travelers}
    for item in booking.items:
        product = products.get(item.product_id)
        destination = product.destination if product else _UNKNOWN_DESTINATION
        summary = (product_summary(product, unit_price=item.unit_price, name=item.product_name) if product else {
            "productId": item.product_id, "name": item.product_name, "taxonomy": item.taxonomy,
            "destination": destination, "unitPrice": item.unit_price, "currency": booking.currency,
            "priceUnit": "PER_NIGHT" if item.taxonomy == "hotel" else "PER_PERSON", "available": False})
        groups.setdefault(destination, []).append({
            "bookingItemId": item.booking_item_id,
            "product": summary,
            "usingDate": item.using_date.isoformat(),
            "quantity": item.quantity,
            "nights": item.nights if item.taxonomy == "hotel" else None,
            "lineTotal": item.line_total,
            "fares": _fares(_item_fares(item)),
            "travelers": _item_travelers(item, party),
            "guestNames": list(item.guest_names),
            "specialRequest": item.special_request,
        })
    confirmed = booking.status is BookingStatus.CONFIRMED
    return {
        "referenceCode": booking.reference_code,
        "createdAt": iso(booking.created_at),
        "status": booking.status.value.upper(),
        "holdExpiresAt": iso(booking.hold_expires_at) if booking.status is BookingStatus.PENDING_PAYMENT else None,
        "cancellableUntil": iso(cancellable_until(booking.items)) if confirmed else None,
        "payment": _payment(booking),
        "cancellation": _cancellation(booking),
        "contact": {"fullName": booking.contact_name, "email": booking.contact_email, "phone": booking.contact_phone},
        "groups": [
            {
                "destination": destination,
                "eventGroupId": booking.event_group_id,
                "items": items,
                "groupTotal": sum(item["lineTotal"] for item in items),
            }
            for destination, items in groups.items()
        ],
        "total": booking.total_amount,
        "currency": booking.currency,
    }
