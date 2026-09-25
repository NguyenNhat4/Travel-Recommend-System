"""Bản giả cho test booking: kho đơn/giỏ/catalog trong bộ nhớ, CDP giả, đồng hồ điều khiển được. Không gọi mạng, không cần DB."""
from __future__ import annotations

import copy
import uuid
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone

from src.backend.app.application.auth.principal import AuthPrincipal
from src.backend.app.application.booking import (
    CancelBooking, CartService, CreateBookingHold, GetBooking, PaymentEventHandler, ReconcileBookings, Settlement,
)
from src.backend.app.application.ports.booking_store import PendingBookingExists
from src.backend.app.application.ports.cdp_client import CdpUnavailableError
from src.backend.app.application.tracking.behaviour import BehaviourTracker
from src.backend.app.domain.booking import Booking, Cart, CartLine, HoldPolicy
from src.backend.app.domain.booking.status import BookingStatus, PaymentStatus
from src.backend.app.domain.catalog.models import Product
from src.backend.app.infrastructure.payments.fake_gateway import FakeGateway

NOW = datetime(2026, 9, 16, 3, 0, tzinfo=timezone.utc)
USER = "VP0000001"
PRINCIPAL = AuthPrincipal(user_id="u-1", cdp_user_id=USER, email="minh@example.vn")
HOTEL, TICKET = "11111111-1111-1111-1111-111111111111", "22222222-2222-2222-2222-222222222222"


def product(pid=HOTEL, taxonomy="hotel", price=3_400_000, **kw) -> Product:
    attrs = {"level": "room"} if taxonomy == "hotel" else {}
    base = dict(product_id=pid, name=f"SP {pid[:2]}", taxonomy=taxonomy, destination="Nha Trang", description="",
                attributes=attrs, unit_price=price, available=True,
                available_from=date(2026, 9, 1), available_to=date(2026, 12, 31))
    base.update(kw)
    return Product(**base)


class Clock:
    def __init__(self, now=NOW):
        self.now = now

    def __call__(self):
        return self.now

    def advance(self, **kw):
        self.now += timedelta(**kw)


class InMemoryCatalog:
    def __init__(self, *products: Product):
        self.products = {p.product_id: p for p in products}

    async def get_products(self, ids):
        return {i: self.products[i] for i in ids if i in self.products}


class InMemoryCarts:
    def __init__(self):
        self.lines: dict[str, list[CartLine]] = {}

    async def get(self, user):
        return Cart(f"cart-{user}", user, list(self.lines.get(user, [])), NOW)

    async def add(self, user, *, product_id, using_date, quantity, nights, unit_price):
        lines = self.lines.setdefault(user, [])
        for i, line in enumerate(lines):
            if line.product_id == product_id and line.using_date == using_date:
                lines[i] = CartLine(line.cart_item_id, product_id, line.quantity + quantity, using_date, nights, unit_price)
                return
        lines.append(CartLine(str(uuid.uuid4()), product_id, quantity, using_date, nights, unit_price))

    async def update(self, user, cart_item_id, *, using_date, quantity, nights, nights_given, unit_price):
        lines = self.lines.get(user, [])
        for i, l in enumerate(lines):
            if l.cart_item_id == cart_item_id:
                lines[i] = CartLine(l.cart_item_id, l.product_id, quantity or l.quantity, using_date or l.using_date,
                                    nights, unit_price)
                return True
        return False

    async def remove(self, user, cart_item_id):
        before = len(self.lines.get(user, []))
        self.lines[user] = [l for l in self.lines.get(user, []) if l.cart_item_id != cart_item_id]
        return len(self.lines[user]) < before


class _Tx:
    def __init__(self, store):
        self.s = store

    def _find(self, pred):
        return next((copy.deepcopy(b) for b in self.s.bookings.values() if pred(b)), None)

    async def get_by_id(self, booking_id, *, lock=False):
        return self._find(lambda b: b.booking_id == booking_id)

    async def get_by_reference(self, reference_code, cdp_user_id, *, lock=False):
        return self._find(lambda b: b.reference_code == reference_code and b.cdp_user_id == cdp_user_id)

    async def get_by_session(self, session_id, *, lock=False):
        return self._find(lambda b: b.payment and b.payment.checkout_session_id == session_id)

    async def get_pending_for_user(self, cdp_user_id, *, lock=False):
        return self._find(lambda b: b.cdp_user_id == cdp_user_id and b.status is BookingStatus.PENDING_PAYMENT)

    async def insert(self, booking):
        if self.s.fail_insert:
            raise RuntimeError("db down")
        if any(b.cdp_user_id == booking.cdp_user_id and b.status is BookingStatus.PENDING_PAYMENT
               for b in self.s.bookings.values()):
            raise PendingBookingExists(booking.cdp_user_id)
        self.s.bookings[booking.booking_id] = copy.deepcopy(booking)

    async def save(self, booking):
        self.s.bookings[booking.booking_id] = copy.deepcopy(booking)

    async def clear_cart_items(self, cdp_user_id, keys):
        wanted = set(keys)
        lines = self.s.carts.lines.get(cdp_user_id, [])
        self.s.carts.lines[cdp_user_id] = [l for l in lines if (l.product_id, l.using_date) not in wanted]

    async def find_reconcile_ids(self, now, limit):
        out = []
        for b in self.s.bookings.values():
            p = b.payment
            if (b.status is BookingStatus.PENDING_PAYMENT and (p.status is PaymentStatus.SUCCEEDED or (
                    p.status is PaymentStatus.OPEN and b.hold_expires_at < now))
                    or p.status is PaymentStatus.REFUND_PENDING and not p.refund_id
                    or b.status is BookingStatus.CANCELLED and b.confirmed_at and not b.purchase_events_cancelled_at):
                out.append(b.booking_id)
        return out[:limit]


class InMemoryBookingStore:
    def __init__(self, carts: InMemoryCarts):
        self.carts, self.bookings, self.fail_insert = carts, {}, False

    @asynccontextmanager
    async def transaction(self):
        yield _Tx(self)


class FakeCdp:
    def __init__(self):
        self.recorded, self.cancelled, self.down = [], [], False

    async def record_purchases(self, events):
        if self.down:
            raise CdpUnavailableError("down")
        self.recorded.append(list(events))

    async def cancel_purchases(self, events):
        if self.down:
            raise CdpUnavailableError("down")
        self.cancelled.append(list(events))


class Recorder:
    def __init__(self):
        self.events = []

    def record(self, event):
        self.events.append(event)


class World:
    """Ghép mọi use case booking trên bản giả, giống cách main.build_booking ghép trên bản thật."""

    def __init__(self, *, products=None, max_attempts=3):
        self.clock, self.gateway, self.cdp = Clock(), FakeGateway(), FakeCdp()
        self.catalog = InMemoryCatalog(*(products or [product(), product(TICKET, "attraction", 880_000)]))
        self.carts = InMemoryCarts()
        self.store = InMemoryBookingStore(self.carts)
        self.recorder = Recorder()
        self.settlement = Settlement(self.store, self.gateway, self.cdp, self.clock)
        self.handler = PaymentEventHandler(
            self.store, self.gateway, self.settlement, max_failed_attempts=max_attempts, clock=self.clock)
        self.reconciler = ReconcileBookings(self.store, self.gateway, self.settlement, self.handler, self.clock)
        self.cart = CartService(self.carts, self.catalog, BehaviourTracker(self.recorder, _Lookup()), clock=self.clock)
        self.create = CreateBookingHold(
            self.store, self.carts, self.catalog, self.gateway, self.reconciler, HoldPolicy(30),
            public_web_url="http://web.test", provider="fake", clock=self.clock)
        self.get = GetBooking(self.store, self.catalog)
        self.cancel = CancelBooking(self.store, self.gateway, self.settlement, self.catalog, self.clock)

    def state(self) -> dict:
        return {"cart_service": self.cart, "create_booking_hold": self.create, "get_booking": self.get,
                "cancel_booking": self.cancel, "payment_event_handler": self.handler, "payment_gateway": self.gateway}

    def booking(self, reference_code: str) -> Booking:
        return next(b for b in self.store.bookings.values() if b.reference_code == reference_code)

    async def fill_cart(self, using=date(2026, 10, 15), nights=3):
        await self.cart.add(PRINCIPAL, product_id=HOTEL, using_date=using, quantity=1, nights=nights)
        await self.cart.add(PRINCIPAL, product_id=TICKET, using_date=using, quantity=2, nights=None)


class _Lookup:
    async def find_product(self, product_id):
        return None
