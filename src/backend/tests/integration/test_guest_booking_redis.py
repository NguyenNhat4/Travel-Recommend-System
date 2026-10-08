"""Kho giỏ và đơn nháp của khách trên Redis thật (spec dat-truc-tiep-theo-don-nhap.md §8.2).

Chạy: RUN_REDIS_INTEGRATION=1 (docker compose up -d redis). Dùng DB index riêng và guestId ngẫu nhiên, tự dọn.
"""
import asyncio
import os
import secrets
from datetime import date, datetime, timedelta, timezone

import pytest

from src.backend.app.domain.booking import BookingDraft, CartLine
from src.backend.app.infrastructure.persistence.guest_booking_store import (
    GuestBookingRedisStore, GuestDraftRepository, RedisKeyValue,
)

REDIS_URL = os.getenv("BOOKING_REDIS_URL", "redis://:devpass@localhost:6379/3")
TTL = 3 * 86_400

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_REDIS_INTEGRATION") != "1", reason="set RUN_REDIS_INTEGRATION=1 to test against local Redis"
)


def test_guest_cart_and_draft_keys_ttl_and_purge_on_real_redis():
    import redis.asyncio as redis_asyncio

    async def scenario():
        client = redis_asyncio.from_url(REDIS_URL)
        guest = "g_" + secrets.token_urlsafe(16)
        store = GuestBookingRedisStore(RedisKeyValue(client), ttl_seconds=TTL)
        drafts = GuestDraftRepository(store)
        now = datetime.now(timezone.utc).replace(microsecond=0)
        day = date.today() + timedelta(days=5)
        try:
            await store.upsert(guest, product_id="p-1", using_date=day, quantity=2, nights=None, unit_price=880_000,
                               adults=2, children=0, child_unit_price=None)
            cart = await store.get(guest)
            assert [(l.product_id, l.quantity, l.using_date) for l in cart.lines] == [("p-1", 2, day)]
            assert TTL - 5 <= await client.ttl(f"guest:cart:{guest}") <= TTL

            line = CartLine("item-1", "p-2", 1, day, 2, 3_400_000, adults=2, children=1, child_unit_price_snapshot=None)
            draft = BookingDraft("draft-" + secrets.token_hex(6), guest, [line], now, now + timedelta(minutes=30))
            await drafts.create(draft, copy_to_cart=[line], now=now, max_live=5)
            assert await drafts.get(guest, draft.draft_id) == draft
            assert await drafts.get("g_" + "x" * 22, draft.draft_id) is None
            assert TTL - 5 <= await client.ttl(f"guest:draft:{draft.draft_id}") <= TTL
            assert {l.product_id for l in (await store.get(guest)).lines} == {"p-1", "p-2"}

            exported_cart, exported_drafts = await store.export(guest)
            assert len(exported_cart.lines) == 2 and [d.draft_id for d in exported_drafts] == [draft.draft_id]
            await store.purge(guest)
            assert not [k async for k in client.scan_iter(match=f"guest:*{guest}*")]
            assert await client.exists(f"guest:draft:{draft.draft_id}") == 0
        finally:
            await store.purge(guest)
            await client.aclose()
    asyncio.run(scenario())
