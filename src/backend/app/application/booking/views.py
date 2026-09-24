"""Chiếu giỏ và đơn sang payload contract `CartResponse` / `BookingResponse` (schemas/booking.yaml)."""
from __future__ import annotations

from datetime import date, datetime, timezone

from src.backend.app.application.catalog.views import product_summary
from src.backend.app.application.ports.booking_repository import Booking, BookingLine
from src.backend.app.application.ports.cart_repository import Cart
from src.backend.app.domain.booking import line_total
from src.backend.app.domain.catalog import Product, price_unit


def utc_iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def stay_length(taxonomy: str, using_date: date, using_date_to: date | None) -> int | None:
    """Số đêm lưu trong DB dưới dạng ngày trả phòng; chỉ hotel có."""
    return (using_date_to - using_date).days if taxonomy == "hotel" and using_date_to else None


def cart_view(cart: Cart, products: dict[str, Product]) -> dict:
    """`product` là snapshot lúc đọc: giá và tình trạng luôn tải lại (backend §7.1 cam kết 2)."""
    items = []
    for line in cart.lines:
        product = products.get(line.product_id)
        if product is None:  # FK RESTRICT tới cdp.products nên không xảy ra; bỏ qua cho an toàn
            continue
        nights = stay_length(product.taxonomy, line.using_date, line.using_date_to)
        unit_price = product.unit_price if product.unit_price is not None else line.unit_price_snapshot
        items.append({
            "cartItemId": line.cart_item_id,
            "product": product_summary(product),
            "usingDate": line.using_date.isoformat(),
            "quantity": line.quantity,
            "nights": nights,
            "lineTotal": line_total(unit_price, product.price_unit, line.quantity, nights),
        })
    total = sum(item["lineTotal"] for item in items)
    return {"cartId": cart.cart_id, "cdpUserId": cart.cdp_user_id, "items": items, "itemCount": len(items),
            "subtotal": total, "total": total, "currency": "VND", "updatedAt": utc_iso(cart.updated_at)}


def booking_line_total(line: BookingLine) -> int:
    nights = stay_length(line.taxonomy, line.using_date, line.using_date_to)
    return line_total(line.unit_price, price_unit(line.taxonomy, line.unit_price), line.quantity, nights)


def _booked_summary(line: BookingLine, product: Product | None) -> dict:
    if product is not None:
        return product_summary(product)
    return {"productId": line.product_id, "name": line.product_name, "taxonomy": line.taxonomy,
            "destination": "UNKNOWN", "unitPrice": line.unit_price, "currency": "VND",
            "priceUnit": price_unit(line.taxonomy, line.unit_price), "available": False}


def booking_view(booking: Booking, products: dict[str, Product]) -> dict:
    """Gom theo điểm đến (backend §7.2). Mọi nhóm mang chung `eventGroupId` của checkout (DDL: một booking
    một `event_group_id`). `specialRequest` là cột của cả đơn nên lặp lại trên từng mục."""
    groups: dict[str, dict] = {}
    for line in booking.lines:
        summary = _booked_summary(line, products.get(line.product_id))
        group = groups.setdefault(summary["destination"], {
            "destination": summary["destination"], "eventGroupId": booking.event_group_id,
            "items": [], "groupTotal": 0})
        total = booking_line_total(line)
        group["items"].append({
            "bookingItemId": line.booking_item_id,
            "product": summary,
            "usingDate": line.using_date.isoformat(),
            "quantity": line.quantity,
            "nights": stay_length(line.taxonomy, line.using_date, line.using_date_to),
            "lineTotal": total,
            "guestNames": list(line.guest_names),
            "specialRequest": booking.special_request,
        })
        group["groupTotal"] += total
    return {
        "referenceCode": booking.reference_code,
        "createdAt": utc_iso(booking.created_at),
        "status": "CONFIRMED",
        "contact": {"fullName": booking.contact_name, "email": booking.contact_email, "phone": booking.contact_phone},
        "groups": list(groups.values()),
        "total": sum(group["groupTotal"] for group in groups.values()),
        "currency": booking.currency,
    }
