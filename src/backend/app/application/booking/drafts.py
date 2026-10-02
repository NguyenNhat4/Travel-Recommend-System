"""Đơn nháp của "Đặt ngay" (FR-BKG-01; docs/spec/booking/dat-truc-tiep-theo-don-nhap.md §4, §5, §7).

Một đơn nháp chỉ chứa các mục của một lần đặt, có hiệu lực 30 phút, không giữ chỗ. Thanh toán một đơn nháp không bao giờ
kèm mục trong giỏ; ngược lại, mục vào giỏ được của đơn nháp được chép vào giỏ để còn lại đó khi khách không hoàn thành
thanh toán.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Callable, Sequence

from src.backend.app.application.auth.principal import AuthPrincipal
from src.backend.app.application.auth.errors import Unauthenticated
from src.backend.app.application.booking.errors import (
    BookingDraftExpired, BookingDraftNotFound, BookingError, BookingNotFound, CartItemNotFound, GuestStoreUnavailable,
    LineRejected, ProductNotFound, ValidationFailed,
)
from src.backend.app.application.booking.lines import ResolvedLine, resolve_line, stay_nights, vn_today
from src.backend.app.application.booking.owner import CartOwner, owner_of
from src.backend.app.application.booking.reconcile import ReconcileBookings
from src.backend.app.application.booking.views import draft_response
from src.backend.app.application.ports.booking_draft_repository import BookingDraftRepository
from src.backend.app.application.ports.booking_store import BookingStore
from src.backend.app.application.ports.cart_repository import CartRepository
from src.backend.app.application.ports.product_catalog import ProductCatalog
from src.backend.app.application.tracking.behaviour import BehaviourTracker, CatalogProduct
from src.backend.app.domain.booking import (
    MAX_DRAFT_ITEMS, MAX_LIVE_DRAFTS, Booking, BookingDraft, BookingItem, CartLine, DraftPolicy, TravelerType,
    is_cart_eligible,
)
from src.backend.app.domain.booking.party import Guests
from src.backend.app.domain.booking.party_rules import default_guests
from src.backend.app.domain.booking.status import BookingStatus

DRAFT_MESSAGE = "Thông tin đặt chỗ chưa hợp lệ."
_REBOOKABLE = (BookingStatus.PAYMENT_FAILED, BookingStatus.EXPIRED)
# Thông điệp cho mục bị bỏ khi allowPartial; cùng câu với bảng lỗi booking ở tầng API.
_REJECT_MESSAGES = {
    "PRODUCT_NOT_FOUND": "Không tìm thấy sản phẩm.",
    "PRODUCT_UNAVAILABLE": "Sản phẩm vừa hết chỗ.",
    "DATE_OUT_OF_RANGE": "Ngày sử dụng nằm ngoài thời gian mở bán.",
    "VALIDATION_ERROR": "Số khách của dịch vụ này chưa hợp lệ.",
}


@dataclass(frozen=True)
class DraftItemRequest:
    product_id: str
    using_date: date
    quantity: int | None = None
    nights: int | None = None
    guests: Guests | None = None


def _field_error(field: str, reason: str, message: str) -> ValidationFailed:
    error = ValidationFailed(message, {"fields": [{"field": field, "reason": reason, "message": message}]})
    error.user_message = message
    return error


def _rejected(item: DraftItemRequest, error: BookingError) -> dict:
    return {"productId": item.product_id, "usingDate": item.using_date.isoformat(), "code": error.code,
            "message": error.user_message or _REJECT_MESSAGES.get(error.code, "Sản phẩm này hiện không đặt được.")}


def _line_of(resolved: ResolvedLine, now: datetime) -> CartLine:
    return CartLine(
        cart_item_id=str(uuid.uuid4()), product_id=resolved.product_id, quantity=resolved.quantity,
        using_date=resolved.using_date, nights=resolved.nights, unit_price_snapshot=resolved.unit_price, added_at=now,
        adults=resolved.adults, children=resolved.children, child_unit_price_snapshot=resolved.child_unit_price)


def _guests_of(booking: Booking, item: BookingItem) -> Guests:
    """Số người lớn và trẻ em của một mục đơn cũ, suy từ đoàn khách đã khai; đơn kiểu cũ không có thì dùng mặc định."""
    refs = set(item.traveler_refs) | {ref for room in item.rooms for ref in room.traveler_refs}
    party = [t for t in booking.travelers if t.ref in refs]
    if not party:
        return default_guests(item.taxonomy, item.quantity)
    children = sum(1 for t in party if t.type is TravelerType.CHILD)
    return Guests(max(1, len(party) - children), children)


class BookingDraftService:
    def __init__(
        self, drafts: BookingDraftRepository, carts: CartRepository, catalog: ProductCatalog, tracker: BehaviourTracker,
        store: BookingStore, policy: DraftPolicy, *, guest_drafts: BookingDraftRepository | None = None,
        guest_carts: CartRepository | None = None, reconciler: ReconcileBookings | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ):
        self._drafts, self._carts, self._catalog, self._tracker, self._store, self._policy = (
            drafts, carts, catalog, tracker, store, policy)
        self._guest_drafts, self._guest_carts, self._reconciler, self._clock = (
            guest_drafts, guest_carts, reconciler, clock)

    def _repos(self, owner: CartOwner) -> tuple[BookingDraftRepository, CartRepository]:
        if not owner.is_guest:
            return self._drafts, self._carts
        if self._guest_drafts is None or self._guest_carts is None:
            raise GuestStoreUnavailable("kho đơn nháp của khách chưa được cấu hình")
        return self._guest_drafts, self._guest_carts

    # --- tạo -----------------------------------------------------------------------------------------------------------

    async def create(
        self, who: CartOwner | AuthPrincipal, *, items: Sequence[DraftItemRequest] | None = None,
        allow_partial: bool = False, from_booking: str | None = None,
    ) -> dict:
        owner = owner_of(who)
        if from_booking is not None:
            items, allow_partial = await self._items_of_booking(owner, from_booking), True
        items = list(items or [])
        self._check_shape(items)
        products = await self._catalog.get_products(list({item.product_id for item in items}))
        now = self._clock()
        accepted: list[tuple[DraftItemRequest, CartLine]] = []
        rejected: list[dict] = []
        for item in items:
            try:
                product = products.get(item.product_id)
                if product is None:
                    raise ProductNotFound("sản phẩm không tồn tại", {"productId": item.product_id})
                resolved = resolve_line(
                    product, using_date=item.using_date, quantity=item.quantity, nights=item.nights, guests=item.guests,
                    today=vn_today(now))
            except (ProductNotFound, LineRejected, ValidationFailed) as error:
                if not allow_partial:
                    raise
                rejected.append(_rejected(item, error))
                continue
            accepted.append((item, _line_of(resolved, now)))
        if not accepted:
            # Không mục nào đặt được: không tạo đơn nháp rỗng (R-DRF-04).
            raise LineRejected("PRODUCT_UNAVAILABLE", {"rejectedItems": rejected})

        lines = [line for _, line in accepted]
        draft = BookingDraft(str(uuid.uuid4()), owner.key, lines, now, self._policy.expires_at(now))
        drafts, _ = self._repos(owner)
        # Chép tour, trải nghiệm, tiện ích vào giỏ để chúng nằm lại khi khách không hoàn thành thanh toán (R-CPY-01).
        to_cart = [line for line in lines if is_cart_eligible(products[line.product_id].taxonomy)]
        await drafts.create(draft, copy_to_cart=to_cart, now=now, max_live=MAX_LIVE_DRAFTS)
        if owner.cdp_user_id is not None:
            for item, line in accepted:
                product = products[line.product_id]
                added = item.quantity if item.quantity is not None else (item.guests.total if item.guests else 1)
                self._tracker.track_add_to_cart(
                    owner.cdp_user_id, CatalogProduct(product.product_id, product.taxonomy, float(product.unit_price)),
                    added, line.using_date)
        return draft_response(draft, products, cdp_user_id=owner.cdp_user_id, rejected=rejected)

    @staticmethod
    def _check_shape(items: Sequence[DraftItemRequest]) -> None:
        if not items:
            raise _field_error("items", "REQUIRED", "Chưa có sản phẩm nào để đặt.")
        if len(items) > MAX_DRAFT_ITEMS:
            raise _field_error("items", "TOO_MANY_ITEMS", f"Mỗi lần đặt có tối đa {MAX_DRAFT_ITEMS} mục.")
        seen: set[tuple[str, date]] = set()
        for index, item in enumerate(items):
            key = (item.product_id, item.using_date)
            if key in seen:
                raise _field_error(f"items[{index}]", "DUPLICATE_ITEM", "Sản phẩm này đã có trong lần đặt với cùng ngày.")
            seen.add(key)

    async def _items_of_booking(self, owner: CartOwner, reference_code: str) -> list[DraftItemRequest]:
        """Đặt lại: lấy mục của đơn `PAYMENT_FAILED` hoặc `EXPIRED` của chính người gọi; giá sẽ tính lại (§7)."""
        if owner.cdp_user_id is None:
            raise Unauthenticated("cần đăng nhập")
        async with self._store.transaction() as tx:
            booking = await tx.get_by_reference(reference_code, owner.cdp_user_id)
        if booking is None:
            raise BookingNotFound("không tìm thấy đơn", {"referenceCode": reference_code})
        stale = (booking.status is BookingStatus.PENDING_PAYMENT and booking.hold_expires_at is not None
                 and self._clock() >= booking.hold_expires_at)
        if stale and self._reconciler is not None:
            # Hết hạn giữ chỗ mà webhook chưa tới: đối soát ngay để khách bấm Đặt lại được, như khi bấm Thanh toán lại.
            await self._reconciler.reconcile_one(booking.booking_id)
            async with self._store.transaction() as tx:
                booking = await tx.get_by_reference(reference_code, owner.cdp_user_id) or booking
        if booking.status not in _REBOOKABLE:
            raise _field_error("fromBooking", "NOT_REBOOKABLE", "Đơn này không đặt lại được.")
        return [
            DraftItemRequest(item.product_id, item.using_date, item.quantity, item.nights, _guests_of(booking, item))
            for item in booking.items
        ]

    # --- đọc, sửa ------------------------------------------------------------------------------------------------------

    async def _live(self, owner: CartOwner, draft_id: str) -> tuple[BookingDraft, BookingDraftRepository]:
        drafts, carts = self._repos(owner)
        draft = await drafts.get(owner.key, draft_id)
        if draft is None:
            raise BookingDraftNotFound("không tìm thấy đơn nháp", {"draftId": draft_id})
        if draft.is_expired(self._clock()):
            raise await self._expired(owner, draft, carts)
        return draft, drafts

    async def _expired(self, owner: CartOwner, draft: BookingDraft, carts: CartRepository) -> BookingDraftExpired:
        """`410` kèm từng mục và việc mục đó có đang nằm trong giỏ không, để Web dẫn khách về đúng chỗ (R-DRF-12)."""
        products = await self._catalog.get_products([line.product_id for line in draft.lines])
        in_cart = {(l.product_id, l.using_date) for l in (await carts.get(owner.key)).lines}
        return BookingDraftExpired("đơn nháp đã hết hạn", {
            "draftId": draft.draft_id,
            "items": [
                {"productId": line.product_id, "taxonomy": products[line.product_id].taxonomy,
                 "inCart": (line.product_id, line.using_date) in in_cart}
                for line in draft.lines if line.product_id in products
            ],
        })

    async def get(self, who: CartOwner | AuthPrincipal, draft_id: str) -> dict:
        owner = owner_of(who)
        draft, _ = await self._live(owner, draft_id)
        products = await self._catalog.get_products([line.product_id for line in draft.lines])
        return draft_response(draft, products, cdp_user_id=owner.cdp_user_id)

    async def update_item(
        self, who: CartOwner | AuthPrincipal, draft_id: str, cart_item_id: str, *, using_date: date | None,
        quantity: int | None, nights: int | None, nights_given: bool, guests: Guests | None = None,
    ) -> dict:
        owner = owner_of(who)
        draft, drafts = await self._live(owner, draft_id)
        line = next((l for l in draft.lines if l.cart_item_id == cart_item_id), None)
        if line is None:
            raise CartItemNotFound("mục không thuộc đơn nháp", {"cartItemId": cart_item_id})
        product = (await self._catalog.get_products([line.product_id])).get(line.product_id)
        if product is None:
            raise ProductNotFound("sản phẩm không tồn tại", {"productId": line.product_id})
        resolved = resolve_line(
            product, using_date=using_date or line.using_date, quantity=quantity, nights=nights, guests=guests,
            today=vn_today(self._clock()), mode="update", existing_quantity=line.quantity, existing_guests=line.guests)
        # Sửa mục nghĩa là khách đã thấy giá hiện tại: ghi lại snapshot. Mục giỏ đã chép không đổi (R-CPY-04).
        await drafts.update_item(
            owner.key, draft_id, cart_item_id, using_date=using_date, quantity=resolved.quantity,
            nights=stay_nights(product, nights) if nights_given else line.nights, unit_price=resolved.unit_price,
            adults=resolved.adults, children=resolved.children, child_unit_price=resolved.child_unit_price)
        return await self.get(owner, draft_id)

    async def remove_item(self, who: CartOwner | AuthPrincipal, draft_id: str, cart_item_id: str) -> dict:
        """Bỏ một mục khỏi lần đặt; mục giỏ đã chép không đổi. Bỏ mục cuối thì đơn nháp bị xoá, response có items rỗng."""
        owner = owner_of(who)
        draft, drafts = await self._live(owner, draft_id)
        if not await drafts.remove_item(owner.key, draft_id, cart_item_id):
            raise CartItemNotFound("mục không thuộc đơn nháp", {"cartItemId": cart_item_id})
        remaining = BookingDraft(draft.draft_id, draft.owner_key,
                                 [l for l in draft.lines if l.cart_item_id != cart_item_id], draft.created_at, draft.expires_at)
        products = await self._catalog.get_products([line.product_id for line in remaining.lines])
        return draft_response(remaining, products, cdp_user_id=owner.cdp_user_id)
