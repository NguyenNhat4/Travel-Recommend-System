"""Tạo đơn giữ chỗ và phiên thanh toán Stripe (spec booking §6.2, FR-BKG-02, FR-BKG-05, FR-BKG-06).

Hai nguồn mục, không bao giờ trộn (spec dat-truc-tiep-theo-don-nhap.md §6): có `draft_id` thì thanh toán đúng đơn nháp đó
(Đặt ngay), không có thì thanh toán toàn bộ giỏ.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable

from src.backend.app.application.auth.principal import AuthPrincipal
from src.backend.app.application.booking.errors import (
    BookingDraftExpired,
    BookingDraftNotFound,
    CartEmpty,
    LineRejected,
    PaymentUnavailable,
    PendingPaymentExists,
    ProductNotFound,
    ValidationFailed,
)
from src.backend.app.application.booking.messages import validation_failed
from src.backend.app.application.booking.reconcile import ReconcileBookings
from src.backend.app.application.booking.views import booking_response, iso
from src.backend.app.application.ports.booking_draft_repository import BookingDraftRepository
from src.backend.app.application.ports.booking_store import BookingStore, PendingBookingExists, ReferenceCodeTaken
from src.backend.app.application.ports.cart_repository import CartRepository
from src.backend.app.application.ports.payment_gateway import (
    CheckoutLine,
    PaymentGateway,
    PaymentProviderError,
    PaymentProviderUnavailable,
)
from src.backend.app.application.ports.product_catalog import ProductCatalog
from src.backend.app.core.request_context import current_request_id
from src.backend.app.domain.booking import (
    Booking,
    BookingItem,
    FareLine,
    FareType,
    HoldPolicy,
    Payment,
    RoomAllocation,
    Traveler,
    check_child_price,
    check_product,
    fare_lines,
    new_reference_code,
)
from src.backend.app.domain.booking.cancellation import VN_TZ
from src.backend.app.domain.booking.fares import CHILD_PRICED_TAXONOMIES
from src.backend.app.domain.booking.party_rules import (
    CartFacts,
    ContactInput,
    ItemInput,
    RoomInput,
    TravelerInput,
    check_checkout,
    check_contact,
    check_legacy,
    normalize_name,
)
from src.backend.app.domain.booking.status import BookingStatus

logger = logging.getLogger(__name__)
_REFERENCE_RETRIES = 5


@dataclass(frozen=True)
class ItemDetail:
    cart_item_id: str  # mã mục của nguồn đang thanh toán: mục giỏ, hoặc mục đơn nháp khi có draft_id
    guest_names: list[str] = field(default_factory=list)  # chỉ request cũ không có `travelers` (spec §7.6)
    special_request: str | None = None
    traveler_refs: list[str] | None = None  # dịch vụ tính theo người, combo
    rooms: list[RoomInput] | None = None    # khách sạn


@dataclass(frozen=True)
class Contact:
    full_name: str
    email: str
    phone: str


_STRIPE_NAME_MAX = 180  # Stripe giới hạn độ dài tên dòng; cắt phần tên sản phẩm, giữ nhãn loại giá


def _fare_label(fare: FareLine) -> str:
    return {FareType.ADULT: "Người lớn", FareType.CHILD: "Trẻ em", FareType.PACKAGE: "Gói"}.get(
        fare.fare_type, f"{fare.nights} đêm")


def _checkout_lines(items: list[BookingItem]) -> list[CheckoutLine]:
    """Mỗi dòng giá một line item Stripe (spec §8.4). Không gửi họ tên, ngày sinh hay bất kỳ dữ liệu hành khách nào."""
    lines: list[CheckoutLine] = []
    for item in items:
        name = item.product_name if len(item.product_name) <= _STRIPE_NAME_MAX else item.product_name[:_STRIPE_NAME_MAX - 1] + "…"
        for fare in item.fares:
            # Khách sạn: nhân số đêm vào đơn giá để tổng dòng khớp thành tiền của dòng giá.
            lines.append(CheckoutLine(name=f"{name} · {_fare_label(fare)}", unit_amount=fare.unit_price * (fare.nights or 1),
                                      quantity=fare.count))
    return lines


class CreateBookingHold:
    def __init__(
        self, store: BookingStore, carts: CartRepository, catalog: ProductCatalog, gateway: PaymentGateway,
        reconciler: ReconcileBookings, hold: HoldPolicy, *, public_web_url: str, provider: str,
        clock: Callable[[], datetime], drafts: BookingDraftRepository | None = None,
    ):
        self._store, self._carts, self._catalog, self._gateway = store, carts, catalog, gateway
        self._drafts = drafts
        self._reconciler, self._hold, self._web, self._provider, self._clock = (
            reconciler, hold, public_web_url.rstrip("/"), provider, clock)

    async def __call__(
        self, principal: AuthPrincipal, contact: Contact, details: list[ItemDetail],
        travelers: list[TravelerInput] | None = None, draft_id: str | None = None,
    ) -> dict:
        """Trình tự kiểm theo spec checkout-nhieu-buoc-hanh-khach.md §8.3. `travelers=None` là request cũ (§7.6)."""
        user = principal.cdp_user_id
        await self._release_stale_hold(user)

        now = self._clock()
        lines = await self._source_lines(user, draft_id, now)
        products = await self._catalog.get_products([line.product_id for line in lines])
        for line in lines:
            if products.get(line.product_id) is None:
                raise ProductNotFound("sản phẩm không tồn tại", {"productId": line.product_id})

        party, violations = self._check_rules(contact, details, travelers, lines, products, now)
        if violations:
            # Mọi vi phạm trong một lần; chưa gọi Stripe, chưa ghi gì.
            raise validation_failed(violations)

        detail_by_id = {d.cart_item_id: d for d in details}
        items: list[BookingItem] = []
        for line in lines:
            product = products[line.product_id]
            issue = check_product(product, line.using_date, snapshot_price=line.unit_price_snapshot)
            if issue is None and line.children and product.taxonomy in CHILD_PRICED_TAXONOMIES:
                issue = check_child_price(
                    product, snapshot_child=line.child_unit_price_snapshot, snapshot_adult=line.unit_price_snapshot)
            if issue:
                raise LineRejected(issue.code, issue.details)
            items.append(self._build_item(line, product, detail_by_id[line.cart_item_id], party))

        booking_id = str(uuid.uuid4())
        booking = Booking(
            booking_id=booking_id, reference_code=new_reference_code(now.date()), cdp_user_id=user,
            event_group_id=f"OFF{now:%Y%m%d}{uuid.uuid4().hex[:6].upper()}",
            contact_name=normalize_name(contact.full_name), contact_email=contact.email.strip(),
            contact_phone=contact.phone.strip(), created_at=now, items=items, hold_expires_at=self._hold.expires_at(now),
            travelers=party,
        )
        booking.payment = Payment(payment_id=str(uuid.uuid4()), provider=self._provider, amount=booking.total_amount)
        stripe_lines = _checkout_lines(items)
        if sum(l.unit_amount * l.quantity for l in stripe_lines) != booking.total_amount:
            # Chỉ xảy ra khi code sai: không gửi số tiền lệch sang Stripe.
            logger.error("booking.create.total_mismatch requestId=%s", current_request_id())
            raise RuntimeError("tổng các dòng thanh toán lệch tổng đơn")
        # Chỉ ghi số lượng, không ghi họ tên, ngày sinh hay số điện thoại (NFR-SEC-01, spec §8.6).
        logger.info("booking.create adults=%d children=%d items=%d requestId=%s",
                    sum(1 for t in party if t.type.value == "adult"), sum(1 for t in party if t.type.value == "child"),
                    len(items), current_request_id())

        # Gọi Stripe TRƯỚC khi ghi database: Stripe lỗi thì chưa có gì để dọn (spec booking §6.1).
        try:
            session = await self._gateway.create_checkout_session(
                booking_id=booking_id, reference_code=booking.reference_code, cdp_user_id=user,
                customer_email=booking.contact_email,
                lines=stripe_lines,
                expires_at=booking.hold_expires_at,
                success_url=f"{self._web}/booking/{booking.reference_code}?payment=return",
                cancel_url=f"{self._web}/booking/{booking.reference_code}?payment=cancelled",
                idempotency_key=f"booking:{booking_id}",
            )
        except PaymentProviderUnavailable as exc:
            logger.warning("booking.create.provider_unavailable requestId=%s", current_request_id())
            raise PaymentUnavailable("cổng thanh toán không phản hồi") from exc
        except PaymentProviderError:
            logger.exception("booking.create.provider_rejected requestId=%s", current_request_id())
            raise
        payment = booking.payment
        payment.checkout_session_id, payment.checkout_url = session.session_id, session.url

        try:
            await self._insert(booking, draft_id)
        except PendingBookingExists:
            await self._close_session(session.session_id)
            raise await self._pending_error(user)
        except BaseException:
            # Commit lỗi sau khi Stripe đã tạo phiên: đóng phiên để bù trừ (spec §6.2 F12).
            await self._close_session(session.session_id)
            raise
        return booking_response(booking, products)

    def _check_rules(self, contact, details, travelers, lines, products, now):
        """Luật dữ liệu của §5: trả đoàn khách đã chuẩn hoá và mọi vi phạm (không dừng ở vi phạm đầu tiên)."""
        facts = [
            CartFacts(line.cart_item_id, products[line.product_id].name, products[line.product_id].taxonomy,
                      line.using_date, line.quantity, line.adults, line.children,
                      products[line.product_id].max_occupancy)
            for line in lines
        ]
        contact_input = ContactInput(contact.full_name, contact.email, contact.phone)
        inputs = [ItemInput(d.cart_item_id, d.traveler_refs, d.rooms, d.guest_names) for d in details]
        if travelers is None:
            return [], [*check_contact(contact_input), *check_legacy(inputs, facts)]
        return check_checkout(contact_input, travelers, inputs, facts, today=now.astimezone(VN_TZ).date())

    @staticmethod
    def _build_item(line, product, detail: ItemDetail, party: list[Traveler]) -> BookingItem:
        unit = int(product.unit_price)
        nights = line.nights if product.taxonomy == "hotel" else None
        fares = fare_lines(product.taxonomy, unit, product.attributes, quantity=line.quantity, nights=nights,
                           adults=line.adults, children=line.children)
        rooms: list[RoomAllocation] = []
        if product.taxonomy == "hotel" and detail.rooms:
            rooms = [RoomAllocation(tuple(r.traveler_refs), r.lead_traveler_ref or "") for r in detail.rooms]
            wanted = {ref for room in rooms for ref in room.traveler_refs}
        else:
            wanted = set(detail.traveler_refs or [])
        by_party_order = [t for t in party if t.ref in wanted]
        # Request có `travelers`: họ tên lấy từ đoàn khách, `guestNames` của client bị bỏ qua (spec §7.3).
        guest_names = ([t.full_name for t in by_party_order] if party
                       else [n for n in (normalize_name(n) for n in detail.guest_names) if n])
        return BookingItem(
            booking_item_id=str(uuid.uuid4()), product_id=product.product_id, taxonomy=product.taxonomy,
            product_name=product.name, unit_price=unit, quantity=line.quantity, using_date=line.using_date,
            nights=nights, guest_names=guest_names, special_request=detail.special_request, fares=fares,
            traveler_refs=[t.ref for t in by_party_order], rooms=rooms,
        )

    async def _source_lines(self, cdp_user_id: str, draft_id: str | None, now: datetime) -> list:
        """Mục cần thanh toán: của đơn nháp (Đặt ngay) hoặc của giỏ. Hai nguồn không trộn (R-CHK-01)."""
        if draft_id is None:
            cart = await self._carts.get(cdp_user_id)
            if not cart.lines:
                raise CartEmpty("giỏ hàng trống")
            return cart.lines
        draft = await self._drafts.get(cdp_user_id, draft_id) if self._drafts is not None else None
        if draft is None or not draft.lines:
            raise BookingDraftNotFound("không tìm thấy đơn nháp", {"draftId": draft_id})
        if draft.is_expired(now):
            raise BookingDraftExpired("đơn nháp đã hết hạn", {"draftId": draft_id, "items": []})
        return draft.lines

    async def _insert(self, booking: Booking, draft_id: str | None = None) -> None:
        for attempt in range(_REFERENCE_RETRIES):
            try:
                async with self._store.transaction() as tx:
                    await tx.insert(booking)
                    if draft_id is not None:
                        # Đơn nháp đã thành đơn giữ chỗ: xoá trong cùng transaction (R-CHK-05). Mục tour, tiện ích đã
                        # chép vào giỏ vẫn ở lại giỏ cho tới khi đơn CONFIRMED.
                        await tx.delete_draft(booking.cdp_user_id, draft_id)
                return
            except ReferenceCodeTaken:
                booking.reference_code = new_reference_code(booking.created_at.date())
        raise RuntimeError("không sinh được mã đặt chỗ duy nhất")

    async def _release_stale_hold(self, cdp_user_id: str) -> None:
        """Có đơn giữ chỗ còn hạn thì báo 409; quá hạn mà webhook chưa tới thì đối soát ngay để giải phóng."""
        async with self._store.transaction() as tx:
            existing = await tx.get_pending_for_user(cdp_user_id)
        if existing is None:
            return
        if HoldPolicy.is_active(existing.hold_expires_at, self._clock()):
            raise PendingPaymentExists("đang có đơn chờ thanh toán", {
                "referenceCode": existing.reference_code, "holdExpiresAt": iso(existing.hold_expires_at)})
        await self._reconciler.reconcile_one(existing.booking_id)
        async with self._store.transaction() as tx:
            still = await tx.get_pending_for_user(cdp_user_id)
        if still is not None:
            raise PendingPaymentExists("đang có đơn chờ thanh toán", {
                "referenceCode": still.reference_code, "holdExpiresAt": iso(still.hold_expires_at)})

    async def _pending_error(self, cdp_user_id: str) -> PendingPaymentExists:
        async with self._store.transaction() as tx:
            existing = await tx.get_pending_for_user(cdp_user_id)
        details = ({"referenceCode": existing.reference_code, "holdExpiresAt": iso(existing.hold_expires_at)}
                   if existing else None)
        return PendingPaymentExists("đang có đơn chờ thanh toán", details)

    async def _close_session(self, session_id: str) -> None:
        try:
            await self._gateway.expire_checkout_session(session_id)
        except Exception:
            logger.error("booking.create.compensation_failed sessionId=%s requestId=%s",
                         session_id, current_request_id())

