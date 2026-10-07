"""Bản giả cho test booking: kho đơn/giỏ/catalog trong bộ nhớ, CDP giả, đồng hồ điều khiển được. Không gọi mạng, không cần DB."""
from __future__ import annotations

import copy
import uuid
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone

from src.backend.app.application.auth.principal import AuthPrincipal
from src.backend.app.application.booking import (
    BookingDraftService, CancelBooking, CartService, CreateBookingHold, DraftItemRequest, GetBooking, ItemDetail,
    ListBookings, MergeGuestBooking, PaymentEventHandler, ReconcileBookings, Settlement,
)
from src.backend.app.application.ports.booking_store import PendingBookingExists
from src.backend.app.application.ports.cdp_client import CdpUnavailableError
from src.backend.app.application.tracking.behaviour import BehaviourTracker
from src.backend.app.domain.booking import (
    Booking, BookingDraft, BookingOverview, Cart, CartLine, DraftPolicy, HoldPolicy, item_end_date,
)
from src.backend.app.domain.booking.status import BookingStatus, PaymentStatus
from src.backend.app.domain.catalog.models import Product
from src.backend.app.infrastructure.payments.fake_gateway import FakeGateway

NOW = datetime(2026, 9, 16, 3, 0, tzinfo=timezone.utc)
USER = "VP0000001"
GUEST = "g_" + "a" * 22
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

    async def upsert(self, user, *, product_id, using_date, quantity, nights, unit_price, adults, children,
                     child_unit_price):
        lines = self.lines.setdefault(user, [])
        for i, line in enumerate(lines):
            if line.product_id == product_id and line.using_date == using_date:
                lines[i] = CartLine(line.cart_item_id, product_id, quantity, using_date, nights, unit_price,
                                    adults=adults, children=children, child_unit_price_snapshot=child_unit_price)
                return
        lines.append(CartLine(str(uuid.uuid4()), product_id, quantity, using_date, nights, unit_price,
                              adults=adults, children=children, child_unit_price_snapshot=child_unit_price))

    async def update(self, user, cart_item_id, *, using_date, quantity, nights, nights_given, unit_price, adults,
                     children, child_unit_price):
        lines = self.lines.get(user, [])
        for i, l in enumerate(lines):
            if l.cart_item_id == cart_item_id:
                lines[i] = CartLine(l.cart_item_id, l.product_id, quantity, using_date or l.using_date, nights,
                                    unit_price, adults=adults, children=children,
                                    child_unit_price_snapshot=child_unit_price)
                return True
        return False

    async def remove(self, user, cart_item_id):
        before = len(self.lines.get(user, []))
        self.lines[user] = [l for l in self.lines.get(user, []) if l.cart_item_id != cart_item_id]
        return len(self.lines[user]) < before


class InMemoryDrafts:
    """Kho đơn nháp trong bộ nhớ; chép mục vào `carts` như adapter thật (spec dat-truc-tiep-theo-don-nhap.md §5)."""

    def __init__(self, carts: InMemoryCarts):
        self.carts, self.drafts = carts, {}

    async def create(self, draft, *, copy_to_cart, now, max_live):
        mine = [d for d in self.drafts.values() if d.owner_key == draft.owner_key]
        live = sorted((d for d in mine if not d.is_expired(now)), key=lambda d: d.created_at)
        for stale in [d for d in mine if d.is_expired(now)] + live[:max(0, len(live) + 1 - max_live)]:
            del self.drafts[stale.draft_id]
        self.drafts[draft.draft_id] = draft
        lines = self.carts.lines.setdefault(draft.owner_key, [])
        for line in copy_to_cart:
            if not any(l.product_id == line.product_id and l.using_date == line.using_date for l in lines):
                lines.append(CartLine(str(uuid.uuid4()), line.product_id, line.quantity, line.using_date, line.nights,
                                      line.unit_price_snapshot, adults=line.adults, children=line.children,
                                      child_unit_price_snapshot=line.child_unit_price_snapshot))

    async def get(self, owner_key, draft_id):
        draft = self.drafts.get(draft_id)
        return draft if draft is not None and draft.owner_key == owner_key else None

    async def update_item(self, owner_key, draft_id, cart_item_id, *, using_date, quantity, nights, unit_price, adults,
                          children, child_unit_price):
        draft = await self.get(owner_key, draft_id)
        if draft is None:
            return False
        for i, l in enumerate(draft.lines):
            if l.cart_item_id == cart_item_id:
                draft.lines[i] = CartLine(l.cart_item_id, l.product_id, quantity, using_date or l.using_date, nights,
                                          unit_price, adults=adults, children=children,
                                          child_unit_price_snapshot=child_unit_price)
                return True
        return False

    async def remove_item(self, owner_key, draft_id, cart_item_id):
        draft = await self.get(owner_key, draft_id)
        if draft is None or not any(l.cart_item_id == cart_item_id for l in draft.lines):
            return False
        draft.lines[:] = [l for l in draft.lines if l.cart_item_id != cart_item_id]
        if not draft.lines:
            del self.drafts[draft_id]
        return True

    async def adopt(self, draft):
        if draft.draft_id in self.drafts:
            return False
        self.drafts[draft.draft_id] = draft
        return True


class InMemoryGuestStore:
    """Dữ liệu của khách chưa đăng nhập để gộp: giỏ và đơn nháp khoá theo guestId."""

    def __init__(self, carts: InMemoryCarts, drafts: InMemoryDrafts):
        self.carts, self.drafts = carts, drafts

    async def export(self, guest_id):
        return await self.carts.get(guest_id), [d for d in self.drafts.drafts.values() if d.owner_key == guest_id]

    async def purge(self, guest_id):
        self.carts.lines.pop(guest_id, None)
        for draft_id in [k for k, d in self.drafts.drafts.items() if d.owner_key == guest_id]:
            del self.drafts.drafts[draft_id]


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

    async def list_overviews(self, cdp_user_id, since):
        mine = [b for b in self.s.bookings.values()
                if b.cdp_user_id == cdp_user_id and (since is None or b.created_at >= since)]
        mine.sort(key=lambda b: (b.created_at, b.booking_id), reverse=True)
        return [BookingOverview(b.booking_id, b.status, b.created_at, b.hold_expires_at,
                                max(item_end_date(i) for i in b.items), tuple(sorted({i.taxonomy for i in b.items})))
                for b in mine]

    async def get_many(self, booking_ids):
        return [copy.deepcopy(self.s.bookings[i]) for i in booking_ids if i in self.s.bookings]

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

    async def delete_draft(self, cdp_user_id, draft_id):
        draft = self.s.drafts.drafts.get(draft_id)
        if draft is not None and draft.owner_key == cdp_user_id:
            del self.s.drafts.drafts[draft_id]

    async def purge_expired_drafts(self, before):
        stale = [k for k, d in self.s.drafts.drafts.items() if d.expires_at < before]
        for draft_id in stale:
            del self.s.drafts.drafts[draft_id]
        return len(stale)

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
    def __init__(self, carts: InMemoryCarts, drafts: "InMemoryDrafts | None" = None):
        self.carts, self.bookings, self.fail_insert = carts, {}, False
        self.drafts = drafts or InMemoryDrafts(carts)

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


class Basket:
    """Một lần Đặt ngay nhiều mục (như "Thanh toán tất cả" của một lịch trình): mỗi lần `add` tạo lại đơn nháp.

    Cùng chữ ký với `CartService` để test luật thanh toán dùng được cho khách sạn và vé máy bay, hai loại không còn vào giỏ.
    """

    def __init__(self, world: "World"):
        self.w, self.items, self.draft_id = world, [], None

    async def add(self, who, *, product_id, using_date, quantity, nights, guests=None):
        items = [*self.items, DraftItemRequest(product_id, using_date, quantity, nights, guests)]
        res = await self.w.drafts.create(who, items=items)  # mục bị từ chối thì không giữ lại
        self.items, self.draft_id = items, res["draftId"]
        return res

    async def get(self, who):
        return await self.w.drafts.get(who, self.draft_id)

    async def update(self, who, cart_item_id, **kw):
        return await self.w.drafts.update_item(who, self.draft_id, cart_item_id, **kw)

    def lines(self):
        return list(self.w.draft_repo.drafts[self.draft_id].lines)


_AUTO = object()


class World:
    """Ghép mọi use case booking trên bản giả, giống cách main.build_booking ghép trên bản thật."""

    def __init__(self, *, products=None, max_attempts=3):
        self.clock, self.gateway, self.cdp = Clock(), FakeGateway(), FakeCdp()
        self.catalog = InMemoryCatalog(*(products or [product(), product(TICKET, "attraction", 880_000)]))
        self.carts = InMemoryCarts()
        self.draft_repo = InMemoryDrafts(self.carts)
        self.guest_carts = InMemoryCarts()
        self.guest_draft_repo = InMemoryDrafts(self.guest_carts)
        self.guest_store = InMemoryGuestStore(self.guest_carts, self.guest_draft_repo)
        self.store = InMemoryBookingStore(self.carts, self.draft_repo)
        self.recorder = Recorder()
        self.settlement = Settlement(self.store, self.gateway, self.cdp, self.clock)
        self.handler = PaymentEventHandler(
            self.store, self.gateway, self.settlement, max_failed_attempts=max_attempts, clock=self.clock)
        self.reconciler = ReconcileBookings(self.store, self.gateway, self.settlement, self.handler, self.clock)
        tracker = BehaviourTracker(self.recorder, _Lookup())
        self.cart = CartService(self.carts, self.catalog, tracker, guest_carts=self.guest_carts, clock=self.clock)
        self.drafts = BookingDraftService(
            self.draft_repo, self.carts, self.catalog, tracker, self.store, DraftPolicy(30),
            guest_drafts=self.guest_draft_repo, guest_carts=self.guest_carts, reconciler=self.reconciler,
            clock=self.clock)
        self.merge = MergeGuestBooking(
            self.guest_store, self.carts, self.draft_repo, self.catalog, tracker, clock=self.clock)
        self.create_hold = CreateBookingHold(
            self.store, self.carts, self.catalog, self.gateway, self.reconciler, HoldPolicy(30),
            public_web_url="http://web.test", provider="fake", clock=self.clock, drafts=self.draft_repo)
        self.basket = Basket(self)
        self.get = GetBooking(self.store, self.catalog)
        self.list = ListBookings(self.store, self.clock)
        self.cancel = CancelBooking(self.store, self.gateway, self.settlement, self.catalog, self.clock)

    async def create(self, principal, contact, details, travelers=None, draft_id=_AUTO):
        """Thanh toán đơn nháp của `basket` nếu test đã dựng một cái, ngược lại thanh toán giỏ."""
        draft_id = self.basket.draft_id if draft_id is _AUTO else draft_id
        return await self.create_hold(principal, contact, details, travelers, draft_id=draft_id)

    def state(self) -> dict:
        return {"cart_service": self.cart, "booking_draft_service": self.drafts, "merge_guest_booking": self.merge,
                "create_booking_hold": self.create_hold, "get_booking": self.get, "list_bookings": self.list,
                "cancel_booking": self.cancel, "payment_event_handler": self.handler, "payment_gateway": self.gateway}

    def booking(self, reference_code: str) -> Booking:
        return next(b for b in self.store.bookings.values() if b.reference_code == reference_code)

    async def fill_cart(self, using=date(2026, 10, 15), nights=3):
        """Một lần đặt gồm phòng khách sạn và vé tham quan (như một lịch trình), qua đơn nháp."""
        await self.basket.add(PRINCIPAL, product_id=HOTEL, using_date=using, quantity=1, nights=nights)
        await self.basket.add(PRINCIPAL, product_id=TICKET, using_date=using, quantity=2, nights=None)

    async def lines(self) -> list[CartLine]:
        """Mục của nguồn đang thanh toán: đơn nháp của `basket` nếu có, ngược lại giỏ."""
        return self.basket.lines() if self.basket.draft_id else (await self.carts.get(USER)).lines

    async def details(self) -> list[ItemDetail]:
        """`itemDetails` kiểu cũ (không có `travelers`) đủ để qua luật kiểm của request cũ (spec checkout §7.6)."""
        out = []
        for line in await self.lines():
            taxonomy = self.catalog.products[line.product_id].taxonomy
            names = ["Nguyễn Minh Anh"] * (line.quantity if taxonomy == "flight" else 1 if taxonomy == "hotel" else 0)
            out.append(ItemDetail(line.cart_item_id, names))
        return out


class _Lookup:
    async def find_product(self, product_id):
        return None
