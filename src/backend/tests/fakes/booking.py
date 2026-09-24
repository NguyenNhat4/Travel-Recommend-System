"""Bản giả in-memory cho catalog, giỏ, booking và CDP, để test giỏ, checkout và vòng K1 không cần database.

`RecordingCdp` đóng cả hai vai trên cùng một kho event, giống `LocalCdpClient` (ghi) và `PostgresCdpReader`
(đọc) cùng trỏ vào `cdp.events`: purchase vừa ghi phải thấy ngay ở lần đọc lịch sử kế tiếp.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import replace
from datetime import datetime, timezone

from src.backend.app.application.ports.booking_repository import Booking
from src.backend.app.application.ports.cart_repository import Cart, CartLine
from src.backend.app.application.ports.cdp_client import CdpUnavailableError, PurchaseEvent
from src.backend.app.domain.catalog import Product


class InMemoryProductCatalog:
    def __init__(self, products: list[Product]):
        self.by_id = {product.product_id: product for product in products}

    @classmethod
    def from_jsonl(cls, path) -> "InMemoryProductCatalog":
        with open(path, encoding="utf-8") as handle:
            return cls([Product.from_cdp(json.loads(line)) for line in handle if line.strip()])

    async def get(self, product_id):
        return self.by_id.get(product_id)

    async def get_many(self, product_ids):
        return {product_id: self.by_id[product_id] for product_id in product_ids if product_id in self.by_id}

    async def children(self, parent_id):
        return [product for product in self.by_id.values() if product.parent_id == parent_id]


class InMemoryCarts:
    def __init__(self):
        self.carts: dict[str, Cart] = {}

    def _cart(self, cdp_user_id: str) -> Cart:
        return self.carts.setdefault(cdp_user_id, Cart(
            cart_id=f"cart-{cdp_user_id}", cdp_user_id=cdp_user_id,
            updated_at=datetime(2026, 9, 21, tzinfo=timezone.utc), lines=()))

    def _save(self, cart: Cart, lines) -> None:
        self.carts[cart.cdp_user_id] = replace(cart, lines=tuple(lines), updated_at=datetime.now(timezone.utc))

    def clear(self, cdp_user_id: str) -> None:
        self._save(self._cart(cdp_user_id), ())

    async def load(self, cdp_user_id):
        return self._cart(cdp_user_id)

    async def add(self, cdp_user_id, product_id, using_date, using_date_to, quantity, unit_price):
        cart = self._cart(cdp_user_id)
        lines = list(cart.lines)
        for i, line in enumerate(lines):
            if line.product_id == product_id and line.using_date == using_date:
                lines[i] = replace(line, quantity=line.quantity + quantity)
                break
        else:
            lines.append(CartLine(cart_item_id=str(uuid.uuid4()), product_id=product_id, quantity=quantity,
                                  using_date=using_date, using_date_to=using_date_to,
                                  unit_price_snapshot=unit_price, added_at=datetime.now(timezone.utc)))
        self._save(cart, lines)

    async def update(self, cdp_user_id, cart_item_id, using_date, using_date_to, quantity):
        cart = self._cart(cdp_user_id)
        if not any(line.cart_item_id == cart_item_id for line in cart.lines):
            return False
        self._save(cart, [replace(line, using_date=using_date, using_date_to=using_date_to, quantity=quantity)
                          if line.cart_item_id == cart_item_id else line for line in cart.lines])
        return True

    async def remove(self, cdp_user_id, cart_item_id):
        cart = self._cart(cdp_user_id)
        kept = [line for line in cart.lines if line.cart_item_id != cart_item_id]
        if len(kept) == len(cart.lines):
            return False
        self._save(cart, kept)
        return True


class InMemoryBookings:
    """Lưu booking và xoá giỏ cùng lúc, như transaction của `PostgresBookingRepository.save`."""

    def __init__(self, carts: InMemoryCarts, fail_save: Exception | None = None):
        self.carts = carts
        self.fail_save = fail_save
        self.saved: dict[str, Booking] = {}

    async def reference_taken(self, reference_code):
        return reference_code in self.saved

    async def save(self, booking):
        if self.fail_save is not None:
            raise self.fail_save
        self.saved[booking.reference_code] = booking
        self.carts.clear(booking.cdp_user_id)

    async def find(self, reference_code, cdp_user_id):
        booking = self.saved.get(reference_code)
        return booking if booking is not None and booking.cdp_user_id == cdp_user_id else None


def _iso(value) -> str:
    return value.isoformat().replace("+00:00", "Z") if isinstance(value, datetime) else value.isoformat()


class RecordingCdp:
    """Port `CdpClient` (ghi purchase, huỷ bù trừ) và `CdpHistoryReader` (đọc lịch sử) trên cùng một kho."""

    def __init__(self, base_events: list[dict] | None = None, *, fail_record: bool = False,
                 fail_cancel: bool = False):
        self.base_events = list(base_events or [])
        self.fail_record = fail_record
        self.fail_cancel = fail_cancel
        self.purchases: dict[str, PurchaseEvent] = {}
        self.cancelled: set[str] = set()

    async def record_purchases(self, events):
        if self.fail_record:
            raise CdpUnavailableError("cdp down")
        for event in events:
            self.purchases.setdefault(event.event_id, event)  # gửi lại cùng eventId không sinh event thứ hai

    async def cancel_purchases(self, events):
        if self.fail_cancel:
            raise CdpUnavailableError("cdp down")
        self.cancelled.update(event.event_id for event in events)

    def active_purchases(self) -> list[PurchaseEvent]:
        return [event for event_id, event in self.purchases.items() if event_id not in self.cancelled]

    def _as_cdp(self, event: PurchaseEvent) -> dict:
        return {"cdpUserId": event.cdp_user_id, "eventName": "purchase", "timestamp": _iso(event.timestamp),
                "productId": event.product_id, "taxonomy": event.taxonomy, "eventGroupId": event.event_group_id,
                "quantity": event.quantity, "unitPrice": event.unit_price, "usingDate": event.using_date.isoformat()}

    def events_for_user(self, cdp_user_id):
        events = [event for event in self.base_events if event["cdpUserId"] == cdp_user_id]
        events += [self._as_cdp(event) for event in self.active_purchases() if event.cdp_user_id == cdp_user_id]
        return sorted(events, key=lambda event: event["timestamp"], reverse=True)

    def purchase_events(self, since_days: int = 730):
        events = [event for event in self.base_events if event["eventName"] == "purchase"]
        return events + [self._as_cdp(event) for event in self.active_purchases()]


class RecordingEventRecorder:
    """Port `BrowseEventRecorder`: giữ event duyệt web để test kiểm, không gọi CDP."""

    def __init__(self):
        self.events = []

    def record(self, event):
        self.events.append(event)
