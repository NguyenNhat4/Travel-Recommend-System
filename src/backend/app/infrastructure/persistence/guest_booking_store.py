"""Giỏ và đơn nháp của khách chưa đăng nhập, lưu ở Redis (spec dat-truc-tiep-theo-don-nhap.md §8.2).

`GuestBookingRedisStore` hiện thực port `CartRepository` (khoá theo `guestId`) và `GuestBookingStore` (đọc và xoá toàn bộ
khi gộp vào tài khoản); `GuestDraftRepository` bọc nó để hiện thực port `BookingDraftRepository`. `guestId` không bao giờ
được ghi xuống PostgreSQL (R-GST-04).

| Key                      | Kiểu          | TTL                          |
|--------------------------|---------------|------------------------------|
| `guest:cart:{guestId}`   | string (JSON) | ttl_seconds, đặt lại khi ghi |
| `guest:draft:{draftId}`  | string (JSON) | ttl_seconds                  |
| `guest:drafts:{guestId}` | set           | ttl_seconds                  |

`InMemoryKeyValue` chỉ cho dev chạy không Redis và cho test: dữ liệu nằm trong một tiến trình. Composition root từ chối
dùng nó khi APP_ENV=production, cùng quy ước với rate limiter của auth.
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from datetime import date, datetime, timezone
from typing import Callable, Protocol, Sequence

from src.backend.app.application.booking.errors import GuestStoreUnavailable, ValidationFailed
from src.backend.app.domain.booking import GUEST_CART_MAX_ITEMS, BookingDraft, Cart, CartLine


class KeyValue(Protocol):
    async def get(self, key: str) -> str | None: ...
    async def set(self, key: str, value: str, ttl_seconds: int) -> None: ...
    async def delete(self, *keys: str) -> None: ...
    async def sadd(self, key: str, member: str, ttl_seconds: int) -> None: ...
    async def srem(self, key: str, member: str) -> None: ...
    async def smembers(self, key: str) -> set[str]: ...


class RedisKeyValue:
    def __init__(self, redis):
        self._r = redis

    async def _call(self, operation):
        try:
            return await operation
        except Exception as exc:  # redis.exceptions.RedisError, lỗi kết nối: khách nhận 503, người đã đăng nhập không ảnh hưởng
            raise GuestStoreUnavailable("kho giỏ của khách không phản hồi") from exc

    async def get(self, key: str) -> str | None:
        value = await self._call(self._r.get(key))
        return value.decode("utf-8") if isinstance(value, bytes) else value

    async def set(self, key: str, value: str, ttl_seconds: int) -> None:
        await self._call(self._r.set(key, value, ex=ttl_seconds))

    async def delete(self, *keys: str) -> None:
        if keys:
            await self._call(self._r.delete(*keys))

    async def sadd(self, key: str, member: str, ttl_seconds: int) -> None:
        await self._call(self._r.sadd(key, member))
        await self._call(self._r.expire(key, ttl_seconds))

    async def srem(self, key: str, member: str) -> None:
        await self._call(self._r.srem(key, member))

    async def smembers(self, key: str) -> set[str]:
        members = await self._call(self._r.smembers(key))
        return {m.decode("utf-8") if isinstance(m, bytes) else m for m in members}


class InMemoryKeyValue:
    def __init__(self, *, clock: Callable[[], float] = time.time):
        self._data: dict[str, tuple[object, float]] = {}
        self._clock = clock

    def _live(self, key: str):
        entry = self._data.get(key)
        if entry is None:
            return None
        if entry[1] <= self._clock():
            del self._data[key]
            return None
        return entry[0]

    async def get(self, key: str) -> str | None:
        return self._live(key)

    async def set(self, key: str, value: str, ttl_seconds: int) -> None:
        self._data[key] = (value, self._clock() + ttl_seconds)

    async def delete(self, *keys: str) -> None:
        for key in keys:
            self._data.pop(key, None)

    async def sadd(self, key: str, member: str, ttl_seconds: int) -> None:
        members = set(self._live(key) or ())
        members.add(member)
        self._data[key] = (members, self._clock() + ttl_seconds)

    async def srem(self, key: str, member: str) -> None:
        members = self._live(key)
        if members:
            members.discard(member)

    async def smembers(self, key: str) -> set[str]:
        return set(self._live(key) or ())

    def ttl(self, key: str) -> float | None:
        """Chỉ cho test: số giây còn lại của key."""
        entry = self._data.get(key)
        return entry[1] - self._clock() if entry else None


def _line_to_json(line: CartLine) -> dict:
    return {
        "cartItemId": line.cart_item_id, "productId": line.product_id, "quantity": line.quantity,
        "usingDate": line.using_date.isoformat(), "nights": line.nights, "unitPrice": line.unit_price_snapshot,
        "addedAt": line.added_at.isoformat() if line.added_at else None, "adults": line.adults,
        "children": line.children, "childUnitPrice": line.child_unit_price_snapshot,
    }


def _line_from_json(raw: dict) -> CartLine:
    return CartLine(
        cart_item_id=raw["cartItemId"], product_id=raw["productId"], quantity=raw["quantity"],
        using_date=date.fromisoformat(raw["usingDate"]), nights=raw.get("nights"),
        unit_price_snapshot=raw.get("unitPrice"),
        added_at=datetime.fromisoformat(raw["addedAt"]) if raw.get("addedAt") else None,
        adults=raw.get("adults", 1), children=raw.get("children", 0),
        child_unit_price_snapshot=raw.get("childUnitPrice"))


class GuestBookingRedisStore:
    def __init__(self, kv: KeyValue, *, ttl_seconds: int,
                 clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc)):
        self._kv, self._ttl, self._clock = kv, ttl_seconds, clock

    @staticmethod
    def _cart_key(guest_id: str) -> str:
        return f"guest:cart:{guest_id}"

    @staticmethod
    def _draft_key(draft_id: str) -> str:
        return f"guest:draft:{draft_id}"

    @staticmethod
    def _index_key(guest_id: str) -> str:
        return f"guest:drafts:{guest_id}"

    # --- giỏ (CartRepository) ------------------------------------------------------------------------------

    async def _load_cart(self, guest_id: str) -> dict:
        raw = await self._kv.get(self._cart_key(guest_id))
        if raw:
            return json.loads(raw)
        # Mã giỏ ổn định theo khách nhưng không để lộ guestId (R-GST-04).
        cart_id = "guest-" + hashlib.sha256(guest_id.encode("utf-8")).hexdigest()[:12]
        return {"cartId": cart_id, "updatedAt": None, "items": []}

    async def _save_cart(self, guest_id: str, cart: dict) -> None:
        cart["updatedAt"] = self._clock().isoformat()
        await self._kv.set(self._cart_key(guest_id), json.dumps(cart), self._ttl)  # mỗi lần ghi đặt lại TTL (R-GST-01)

    async def get(self, guest_id: str) -> Cart:
        cart = await self._load_cart(guest_id)
        updated = datetime.fromisoformat(cart["updatedAt"]) if cart["updatedAt"] else self._clock()
        return Cart(cart["cartId"], guest_id, [_line_from_json(i) for i in cart["items"]], updated)

    async def upsert(
        self, guest_id: str, *, product_id: str, using_date: date, quantity: int, nights: int | None,
        unit_price: int, adults: int, children: int, child_unit_price: int | None,
    ) -> None:
        cart = await self._load_cart(guest_id)
        existing = next((i for i in cart["items"]
                         if i["productId"] == product_id and i["usingDate"] == using_date.isoformat()), None)
        line = CartLine(existing["cartItemId"] if existing else str(uuid.uuid4()), product_id, quantity, using_date,
                        nights, unit_price, added_at=self._clock(), adults=adults, children=children,
                        child_unit_price_snapshot=child_unit_price)
        if existing:
            cart["items"][cart["items"].index(existing)] = _line_to_json(line)
        else:
            cart["items"].append(_line_to_json(line))
        await self._save_cart(guest_id, cart)

    async def update(
        self, guest_id: str, cart_item_id: str, *, using_date: date | None, quantity: int, nights: int | None,
        nights_given: bool, unit_price: int, adults: int, children: int, child_unit_price: int | None,
    ) -> bool:
        cart = await self._load_cart(guest_id)
        for index, item in enumerate(cart["items"]):
            if item["cartItemId"] != cart_item_id:
                continue
            new_date = using_date.isoformat() if using_date else item["usingDate"]
            if any(o is not item and o["productId"] == item["productId"] and o["usingDate"] == new_date
                   for o in cart["items"]):
                raise ValidationFailed("đã có mục cùng sản phẩm và ngày này trong giỏ")
            cart["items"][index] = {**item, "usingDate": new_date, "quantity": quantity, "nights": nights,
                                    "unitPrice": unit_price, "adults": adults, "children": children,
                                    "childUnitPrice": child_unit_price}
            await self._save_cart(guest_id, cart)
            return True
        return False

    async def remove(self, guest_id: str, cart_item_id: str) -> bool:
        cart = await self._load_cart(guest_id)
        kept = [i for i in cart["items"] if i["cartItemId"] != cart_item_id]
        if len(kept) == len(cart["items"]):
            return False
        cart["items"] = kept
        await self._save_cart(guest_id, cart)
        return True

    # --- đơn nháp (qua GuestDraftRepository) -----------------------------------------------------------------

    async def _read_draft(self, draft_id: str) -> BookingDraft | None:
        raw = await self._kv.get(self._draft_key(draft_id))
        if not raw:
            return None
        data = json.loads(raw)
        return BookingDraft(data["draftId"], data["guestId"], [_line_from_json(i) for i in data["items"]],
                            datetime.fromisoformat(data["createdAt"]), datetime.fromisoformat(data["expiresAt"]))

    async def _write_draft(self, draft: BookingDraft) -> None:
        await self._kv.set(self._draft_key(draft.draft_id), json.dumps({
            "draftId": draft.draft_id, "guestId": draft.owner_key, "createdAt": draft.created_at.isoformat(),
            "expiresAt": draft.expires_at.isoformat(), "items": [_line_to_json(l) for l in draft.lines]}), self._ttl)

    async def get_draft(self, guest_id: str, draft_id: str) -> BookingDraft | None:
        draft = await self._read_draft(draft_id)
        return draft if draft is not None and draft.owner_key == guest_id else None

    async def _drafts_of(self, guest_id: str) -> list[BookingDraft]:
        drafts = []
        for draft_id in await self._kv.smembers(self._index_key(guest_id)):
            draft = await self._read_draft(draft_id)
            if draft is None:
                await self._kv.srem(self._index_key(guest_id), draft_id)  # key đã hết TTL
            elif draft.owner_key == guest_id:
                drafts.append(draft)
        return drafts

    async def create_draft(
        self, draft: BookingDraft, *, copy_to_cart: Sequence[CartLine], now: datetime, max_live: int,
    ) -> None:
        guest_id = draft.owner_key
        mine = await self._drafts_of(guest_id)
        live = sorted((d for d in mine if not d.is_expired(now)), key=lambda d: d.created_at)
        for stale in [d for d in mine if d.is_expired(now)] + live[:max(0, len(live) + 1 - max_live)]:
            await self._kv.delete(self._draft_key(stale.draft_id))
            await self._kv.srem(self._index_key(guest_id), stale.draft_id)
        await self._write_draft(draft)
        await self._kv.sadd(self._index_key(guest_id), draft.draft_id, self._ttl)
        if copy_to_cart:
            cart = await self._load_cart(guest_id)
            keys = {(i["productId"], i["usingDate"]) for i in cart["items"]}
            for line in copy_to_cart:
                key = (line.product_id, line.using_date.isoformat())
                # Đã có thì giữ nguyên; giỏ khách đầy thì bỏ qua, không làm lỗi việc tạo đơn nháp (R-CPY-02, R-CPY-06).
                if key in keys or len(cart["items"]) >= GUEST_CART_MAX_ITEMS:
                    continue
                cart["items"].append(_line_to_json(CartLine(
                    str(uuid.uuid4()), line.product_id, line.quantity, line.using_date, line.nights,
                    line.unit_price_snapshot, added_at=now, adults=line.adults, children=line.children,
                    child_unit_price_snapshot=line.child_unit_price_snapshot)))
                keys.add(key)
            await self._save_cart(guest_id, cart)

    async def update_draft_item(
        self, guest_id: str, draft_id: str, cart_item_id: str, *, using_date: date | None, quantity: int,
        nights: int | None, unit_price: int, adults: int, children: int, child_unit_price: int | None,
    ) -> bool:
        draft = await self.get_draft(guest_id, draft_id)
        if draft is None:
            return False
        for index, line in enumerate(draft.lines):
            if line.cart_item_id != cart_item_id:
                continue
            new_date = using_date or line.using_date
            if any(o is not line and o.product_id == line.product_id and o.using_date == new_date for o in draft.lines):
                raise ValidationFailed("đã có mục cùng sản phẩm và ngày này trong lần đặt")
            draft.lines[index] = CartLine(line.cart_item_id, line.product_id, quantity, new_date, nights, unit_price,
                                          added_at=line.added_at, adults=adults, children=children,
                                          child_unit_price_snapshot=child_unit_price)
            await self._write_draft(draft)
            return True
        return False

    async def remove_draft_item(self, guest_id: str, draft_id: str, cart_item_id: str) -> bool:
        draft = await self.get_draft(guest_id, draft_id)
        if draft is None or not any(l.cart_item_id == cart_item_id for l in draft.lines):
            return False
        kept = [l for l in draft.lines if l.cart_item_id != cart_item_id]
        if kept:
            await self._write_draft(BookingDraft(draft.draft_id, guest_id, kept, draft.created_at, draft.expires_at))
        else:  # không để lại đơn nháp rỗng (R-DRF-14)
            await self._kv.delete(self._draft_key(draft_id))
            await self._kv.srem(self._index_key(guest_id), draft_id)
        return True

    # --- gộp (GuestBookingStore) ------------------------------------------------------------------------------

    async def export(self, guest_id: str) -> tuple[Cart, list[BookingDraft]]:
        return await self.get(guest_id), await self._drafts_of(guest_id)

    async def purge(self, guest_id: str) -> None:
        draft_ids = await self._kv.smembers(self._index_key(guest_id))
        await self._kv.delete(self._cart_key(guest_id), self._index_key(guest_id),
                              *(self._draft_key(d) for d in draft_ids))


class GuestDraftRepository:
    """Port `BookingDraftRepository` cho khách chưa đăng nhập, trên cùng kho với giỏ của khách."""

    def __init__(self, store: GuestBookingRedisStore):
        self._store = store

    async def create(self, draft: BookingDraft, *, copy_to_cart: Sequence[CartLine], now: datetime, max_live: int) -> None:
        await self._store.create_draft(draft, copy_to_cart=copy_to_cart, now=now, max_live=max_live)

    async def get(self, owner_key: str, draft_id: str) -> BookingDraft | None:
        return await self._store.get_draft(owner_key, draft_id)

    async def update_item(self, owner_key: str, draft_id: str, cart_item_id: str, **changes) -> bool:
        return await self._store.update_draft_item(owner_key, draft_id, cart_item_id, **changes)

    async def remove_item(self, owner_key: str, draft_id: str, cart_item_id: str) -> bool:
        return await self._store.remove_draft_item(owner_key, draft_id, cart_item_id)

    async def adopt(self, draft: BookingDraft) -> bool:
        """Không dùng cho khách: chỉ tài khoản mới nhận đơn nháp được gộp (R-MRG-02)."""
        raise NotImplementedError("đơn nháp của khách không nhận gộp")
