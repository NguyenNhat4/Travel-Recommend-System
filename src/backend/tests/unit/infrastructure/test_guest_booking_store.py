"""Kho giỏ và đơn nháp của khách chưa đăng nhập (spec dat-truc-tiep-theo-don-nhap.md §8.2) trên `InMemoryKeyValue`."""
import asyncio
from datetime import date, datetime, timedelta, timezone

import pytest

from src.backend.app.application.booking.errors import GuestStoreUnavailable, ValidationFailed
from src.backend.app.domain.booking import GUEST_CART_MAX_ITEMS, BookingDraft, CartLine
from src.backend.app.infrastructure.persistence.guest_booking_store import (
    GuestBookingRedisStore, GuestDraftRepository, InMemoryKeyValue, RedisKeyValue,
)

GUEST, OTHER = "g_" + "a" * 22, "g_" + "b" * 22
DAY = date(2026, 10, 15)
TTL = 3 * 86_400
run = asyncio.run


class Time:
    def __init__(self):
        self.now = datetime(2026, 9, 16, 3, 0, tzinfo=timezone.utc)

    def seconds(self) -> float:
        return self.now.timestamp()

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kw):
        self.now += timedelta(**kw)


def build():
    t = Time()
    kv = InMemoryKeyValue(clock=t.seconds)
    store = GuestBookingRedisStore(kv, ttl_seconds=TTL, clock=t)
    return t, kv, store, GuestDraftRepository(store)


def line(product="p-1", day=DAY, item_id="line-1", **kw) -> CartLine:
    return CartLine(item_id, product, kw.get("quantity", 2), day, kw.get("nights"), kw.get("price", 880_000),
                    adults=kw.get("adults", 2), children=kw.get("children", 0), child_unit_price_snapshot=kw.get("child"))


def draft(t: Time, draft_id="d-1", owner=GUEST, lines=None, minutes=30) -> BookingDraft:
    return BookingDraft(draft_id, owner, lines or [line()], t.now, t.now + timedelta(minutes=minutes))


async def add(store, guest=GUEST, product="p-1", day=DAY, **kw):
    await store.upsert(guest, product_id=product, using_date=day, quantity=kw.get("quantity", 2), nights=kw.get("nights"),
                       unit_price=kw.get("price", 880_000), adults=kw.get("adults", 2), children=kw.get("children", 1),
                       child_unit_price=kw.get("child", 504_000))


def test_cart_round_trips_every_field_and_is_scoped_to_the_guest():
    async def go():
        t, kv, store, _ = build()
        assert (await store.get(GUEST)).lines == []
        await add(store, nights=None)
        await add(store, product="p-2", day=date(2026, 10, 16), nights=2, child=None)
        cart = await store.get(GUEST)
        assert cart.cdp_user_id == GUEST and len(cart.lines) == 2
        first = cart.lines[0]
        assert (first.product_id, first.using_date, first.quantity, first.unit_price_snapshot, first.adults,
                first.children, first.child_unit_price_snapshot, first.nights) == ("p-1", DAY, 2, 880_000, 2, 1, 504_000, None)
        assert cart.lines[1].nights == 2 and cart.lines[1].child_unit_price_snapshot is None
        assert (await store.get(OTHER)).lines == []
        # Ghi trùng sản phẩm và ngày: ghi đè giá trị tuyệt đối, giữ mã mục (use case tự cộng dồn trước khi gọi).
        await add(store, quantity=5, adults=4)
        again = await store.get(GUEST)
        assert len(again.lines) == 2 and again.lines[0].quantity == 5 and again.lines[0].cart_item_id == first.cart_item_id
    run(go())


def test_cart_ttl_is_three_days_and_resets_on_every_write():
    async def go():
        t, kv, store, _ = build()
        await add(store)
        key = "guest:cart:" + GUEST
        assert kv.ttl(key) == TTL
        t.advance(days=2)
        await store.get(GUEST)                                   # đọc không gia hạn
        assert kv.ttl(key) == TTL - 2 * 86_400
        await add(store, product="p-2")
        assert kv.ttl(key) == TTL
        t.advance(days=3, seconds=1)
        assert (await store.get(GUEST)).lines == []              # hết TTL thì giỏ biến mất
    run(go())


def test_update_and_remove_report_missing_items_and_reject_a_duplicate_date():
    async def go():
        t, kv, store, _ = build()
        await add(store)
        await add(store, day=date(2026, 10, 16))
        a, b = (await store.get(GUEST)).lines
        changes = dict(quantity=3, nights=None, nights_given=True, unit_price=900_000, adults=3, children=0, child_unit_price=None)
        assert await store.update(GUEST, a.cart_item_id, using_date=None, **changes) is True
        assert (await store.get(GUEST)).lines[0].unit_price_snapshot == 900_000
        assert await store.update(GUEST, "không-có", using_date=None, **changes) is False
        assert await store.update(OTHER, a.cart_item_id, using_date=None, **changes) is False
        with pytest.raises(ValidationFailed):
            await store.update(GUEST, a.cart_item_id, using_date=b.using_date, **changes)
        assert await store.remove(GUEST, a.cart_item_id) is True and await store.remove(GUEST, a.cart_item_id) is False
        assert len((await store.get(GUEST)).lines) == 1
    run(go())


def test_draft_is_stored_with_the_guest_ttl_and_only_its_owner_reads_it():
    async def go():
        t, kv, store, drafts = build()
        d = draft(t)
        await drafts.create(d, copy_to_cart=[], now=t.now, max_live=5)
        assert await drafts.get(GUEST, "d-1") == d and await drafts.get(OTHER, "d-1") is None
        assert await drafts.get(GUEST, "d-x") is None
        assert kv.ttl("guest:draft:d-1") == TTL and kv.ttl("guest:drafts:" + GUEST) == TTL
        t.advance(minutes=31)                                    # hết hiệu lực 30 phút nhưng bản ghi còn (R-GST-11)
        kept = await drafts.get(GUEST, "d-1")
        assert kept is not None and kept.is_expired(t.now)
        with pytest.raises(NotImplementedError):
            await drafts.adopt(d)
    run(go())


def test_create_copies_cart_eligible_lines_once_and_never_overwrites_or_overflows():
    async def go():
        t, kv, store, drafts = build()
        await add(store, product="p-1", quantity=9, adults=9, children=0)
        copy = [line("p-1", item_id="x"), line("p-2", item_id="y", quantity=1, adults=1)]
        await drafts.create(draft(t, lines=copy), copy_to_cart=copy, now=t.now, max_live=5)
        await drafts.create(draft(t, "d-2", lines=copy), copy_to_cart=copy, now=t.now, max_live=5)
        cart = {l.product_id: l for l in (await store.get(GUEST)).lines}
        assert set(cart) == {"p-1", "p-2"} and cart["p-1"].quantity == 9      # mục có sẵn giữ nguyên, không trùng
        assert cart["p-2"].cart_item_id != "y"                                 # mục giỏ có mã riêng
        for i in range(GUEST_CART_MAX_ITEMS):
            await add(store, product=f"fill-{i}")
        overflow = [line("p-late", item_id="z")]
        await drafts.create(draft(t, "d-3", lines=overflow), copy_to_cart=overflow, now=t.now, max_live=5)
        assert "p-late" not in {l.product_id for l in (await store.get(GUEST)).lines}   # giỏ đầy: bỏ qua, không lỗi
        assert await drafts.get(GUEST, "d-3") is not None
    run(go())


def test_create_keeps_five_live_drafts_and_sweeps_expired_ones():
    async def go():
        t, kv, store, drafts = build()
        for i in range(6):
            await drafts.create(draft(t, f"d-{i}"), copy_to_cart=[], now=t.now, max_live=5)
            t.advance(seconds=1)
        assert await drafts.get(GUEST, "d-0") is None and await drafts.get(GUEST, "d-5") is not None
        t.advance(minutes=31)
        await drafts.create(draft(t, "d-new"), copy_to_cart=[], now=t.now, max_live=5)
        assert await kv.smembers("guest:drafts:" + GUEST) == {"d-new"}
    run(go())


def test_update_draft_item_rewrites_the_snapshot_and_checks_owner_and_duplicates():
    async def go():
        t, kv, store, drafts = build()
        d = draft(t, lines=[line(item_id="a"), line(day=date(2026, 10, 16), item_id="b")])
        await drafts.create(d, copy_to_cart=[], now=t.now, max_live=5)
        changes = dict(using_date=None, quantity=4, nights=None, unit_price=900_000, adults=3, children=1, child_unit_price=500_000)
        assert await drafts.update_item(GUEST, "d-1", "a", **changes) is True
        got = (await drafts.get(GUEST, "d-1")).lines[0]
        assert (got.quantity, got.unit_price_snapshot, got.adults, got.children, got.child_unit_price_snapshot) == (
            4, 900_000, 3, 1, 500_000)
        assert await drafts.update_item(GUEST, "d-1", "zzz", **changes) is False
        assert await drafts.update_item(OTHER, "d-1", "a", **changes) is False
        with pytest.raises(ValidationFailed):
            await drafts.update_item(GUEST, "d-1", "a", **{**changes, "using_date": date(2026, 10, 16)})
    run(go())


def test_remove_draft_item_keeps_the_rest_and_drops_an_emptied_draft():
    async def go():
        t, kv, store, drafts = build()
        d = draft(t, lines=[line(item_id="a"), line(day=date(2026, 10, 16), item_id="b")])
        await drafts.create(d, copy_to_cart=[], now=t.now, max_live=5)
        assert await drafts.remove_item(OTHER, "d-1", "a") is False and await drafts.remove_item(GUEST, "d-1", "x") is False
        assert await drafts.remove_item(GUEST, "d-1", "a") is True
        assert [l.cart_item_id for l in (await drafts.get(GUEST, "d-1")).lines] == ["b"]
        assert await drafts.remove_item(GUEST, "d-1", "b") is True
        assert await drafts.get(GUEST, "d-1") is None and await kv.smembers("guest:drafts:" + GUEST) == set()
    run(go())


def test_export_returns_cart_and_all_drafts_and_purge_removes_every_key():
    async def go():
        t, kv, store, drafts = build()
        await add(store)
        await drafts.create(draft(t, "d-1"), copy_to_cart=[], now=t.now, max_live=5)
        await drafts.create(draft(t, "d-2"), copy_to_cart=[], now=t.now, max_live=5)
        await drafts.create(draft(t, "o-1", owner=OTHER), copy_to_cart=[], now=t.now, max_live=5)
        cart, found = await store.export(GUEST)
        assert len(cart.lines) == 1 and {d.draft_id for d in found} == {"d-1", "d-2"}
        await store.purge(GUEST)
        cart, found = await store.export(GUEST)
        assert cart.lines == [] and found == [] and await drafts.get(GUEST, "d-1") is None
        assert GUEST not in cart.cart_id                         # mã giỏ không để lộ guestId
        assert await drafts.get(OTHER, "o-1") is not None        # khách khác không bị đụng
        await store.purge(GUEST)                                 # gọi lại không lỗi (R-MRG-04)
    run(go())


def test_redis_errors_surface_as_guest_store_unavailable():
    class Broken:
        def get(self, key):
            async def boom():
                raise ConnectionError("redis down")
            return boom()

    async def go():
        store = GuestBookingRedisStore(RedisKeyValue(Broken()), ttl_seconds=TTL)
        with pytest.raises(GuestStoreUnavailable) as e:
            await store.get(GUEST)
        assert e.value.http_status == 503 and e.value.retryable
    run(go())
