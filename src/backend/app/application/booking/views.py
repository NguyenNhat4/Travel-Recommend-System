"""Dựng response đúng contract (schemas/booking.yaml) từ thực thể domain. Trả dict thuần, không phụ thuộc web framework."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Mapping

from src.backend.app.domain.booking import Booking, Cart, cancellable_until, line_total
from src.backend.app.domain.booking.status import BookingStatus, PaymentStatus
from src.backend.app.domain.catalog.models import Product

_UNKNOWN_DESTINATION = "Khác"


def iso(value: datetime | None) -> str | None:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if value else None


def product_summary(product: Product, *, unit_price: int | None = None, name: str | None = None) -> dict:
    return {
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
    }


def cart_response(cart: Cart, products: Mapping[str, Product]) -> dict:
    items = []
    for line in cart.lines:
        product = products.get(line.product_id)
        if product is None:
            continue
        price = int(product.unit_price) if product.unit_price is not None else 0
        items.append({
            "cartItemId": line.cart_item_id,
            "product": product_summary(product),
            "usingDate": line.using_date.isoformat(),
            "quantity": line.quantity,
            "nights": line.nights if product.taxonomy == "hotel" else None,
            "lineTotal": line_total(product.taxonomy, price, line.quantity, line.nights),
        })
    total = sum(item["lineTotal"] for item in items)
    return {
        "cartId": cart.cart_id,
        "cdpUserId": cart.cdp_user_id,
        "items": items,
        "itemCount": len(items),
        "subtotal": total,
        "total": total,
        "currency": "VND",
        "updatedAt": iso(cart.updated_at),
    }


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


def booking_response(booking: Booking, products: Mapping[str, Product]) -> dict:
    groups: dict[str, list[dict]] = {}
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
