"""Thực thể booking và các bước chuyển trạng thái hợp lệ (spec booking §5)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

from .fares import FareLine, lines_total
from .party import Guests, RoomAllocation, Traveler
from .pricing import line_total
from .status import BookingStatus, InvalidTransition, PaymentStatus


@dataclass(frozen=True)
class CartLine:
    cart_item_id: str
    product_id: str
    quantity: int
    using_date: date
    nights: int | None
    unit_price_snapshot: int | None
    added_at: datetime | None = None
    adults: int = 1
    children: int = 0
    # None = sản phẩm không có giá trẻ em hợp lệ lúc thêm hoặc sửa (trẻ em trả giá người lớn); xem `fares.child_unit_price`.
    child_unit_price_snapshot: int | None = None

    @property
    def guests(self) -> Guests:
        return Guests(self.adults, self.children)


@dataclass(frozen=True)
class Cart:
    cart_id: str
    cdp_user_id: str
    lines: list[CartLine]
    updated_at: datetime


@dataclass
class BookingItem:
    booking_item_id: str
    product_id: str
    taxonomy: str
    product_name: str
    unit_price: int
    quantity: int
    using_date: date
    nights: int | None = None
    guest_names: list[str] = field(default_factory=list)
    special_request: str | None = None
    fares: list[FareLine] = field(default_factory=list)          # rỗng với đơn tạo trước khi có dòng giá
    traveler_refs: list[str] = field(default_factory=list)       # dịch vụ tính theo người, combo
    rooms: list[RoomAllocation] = field(default_factory=list)    # khách sạn

    @property
    def line_total(self) -> int:
        """Tổng các dòng giá; đơn cũ chưa có dòng giá thì dùng công thức không có trẻ em."""
        if self.fares:
            return lines_total(self.fares)
        return line_total(self.taxonomy, self.unit_price, self.quantity, self.nights)


@dataclass
class Payment:
    payment_id: str
    provider: str
    amount: int
    currency: str = "VND"
    status: PaymentStatus = PaymentStatus.OPEN
    checkout_session_id: str | None = None
    payment_intent_id: str | None = None
    checkout_url: str | None = None
    failed_attempts: int = 0
    last_failure_code: str | None = None
    refund_id: str | None = None
    updated_at: datetime | None = None


@dataclass
class Booking:
    booking_id: str
    reference_code: str
    cdp_user_id: str
    event_group_id: str
    contact_name: str
    contact_email: str
    contact_phone: str
    created_at: datetime
    items: list[BookingItem]
    status: BookingStatus = BookingStatus.PENDING_PAYMENT
    currency: str = "VND"
    hold_expires_at: datetime | None = None
    confirmed_at: datetime | None = None
    cancelled_at: datetime | None = None
    cancel_reason: str | None = None
    purchase_events_cancelled_at: datetime | None = None
    payment: Payment | None = None
    travelers: list[Traveler] = field(default_factory=list)  # đoàn khách của đơn, theo thứ tự khai báo

    @property
    def total_amount(self) -> int:
        return sum(item.line_total for item in self.items)

    # --- chuyển trạng thái -----------------------------------------------------------------------

    def _need(self, *allowed: BookingStatus) -> None:
        if self.status not in allowed:
            raise InvalidTransition(f"đơn {self.reference_code} đang {self.status.value}")

    def _pay(self) -> Payment:
        if self.payment is None:
            raise InvalidTransition(f"đơn {self.reference_code} chưa có thanh toán")
        return self.payment

    def record_payment_received(self, payment_intent_id: str | None) -> None:
        """Stripe đã thu tiền. Đơn vẫn PENDING_PAYMENT cho tới khi ghi xong purchase sang CDP."""
        self._need(BookingStatus.PENDING_PAYMENT)
        payment = self._pay()
        if payment.status not in (PaymentStatus.OPEN, PaymentStatus.SUCCEEDED):
            raise InvalidTransition(f"thanh toán đang {payment.status.value}")
        payment.status = PaymentStatus.SUCCEEDED
        payment.payment_intent_id = payment_intent_id or payment.payment_intent_id
        payment.checkout_url = None

    def confirm(self, now: datetime) -> None:
        self._need(BookingStatus.PENDING_PAYMENT)
        if self._pay().status is not PaymentStatus.SUCCEEDED:
            raise InvalidTransition("chỉ xác nhận đơn khi Stripe đã thu tiền")
        self.status = BookingStatus.CONFIRMED
        self.confirmed_at = now
        self.hold_expires_at = None

    def register_card_failure(self, reason: str, max_attempts: int) -> bool:
        """Ghi một lần thẻ bị từ chối. True nghĩa là đã đủ số lần và đơn chuyển PAYMENT_FAILED."""
        self._need(BookingStatus.PENDING_PAYMENT)
        payment = self._pay()
        if payment.status is not PaymentStatus.OPEN:
            raise InvalidTransition(f"thanh toán đang {payment.status.value}")
        payment.failed_attempts += 1
        payment.last_failure_code = reason
        if payment.failed_attempts < max_attempts:
            return False
        payment.status = PaymentStatus.FAILED
        payment.last_failure_code = "TOO_MANY_ATTEMPTS"
        payment.checkout_url = None
        self.status = BookingStatus.PAYMENT_FAILED
        self.hold_expires_at = None
        return True

    def expire(self) -> None:
        self._need(BookingStatus.PENDING_PAYMENT)
        payment = self._pay()
        if payment.status is not PaymentStatus.OPEN:
            raise InvalidTransition(f"thanh toán đang {payment.status.value}")
        payment.status = PaymentStatus.EXPIRED
        payment.checkout_url = None
        self.status = BookingStatus.EXPIRED
        self.hold_expires_at = None

    def cancel_unpaid(self, now: datetime, reason: str | None) -> None:
        self._need(BookingStatus.PENDING_PAYMENT)
        payment = self._pay()
        if payment.status is not PaymentStatus.OPEN:
            raise InvalidTransition(f"thanh toán đang {payment.status.value}")
        payment.status = PaymentStatus.EXPIRED
        payment.checkout_url = None
        self.status = BookingStatus.CANCELLED
        self.cancelled_at, self.cancel_reason, self.hold_expires_at = now, reason, None

    def cancel_paid(self, now: datetime, reason: str | None) -> None:
        """Khách huỷ đơn đã trả tiền trong hạn: đơn CANCELLED, thanh toán chờ hoàn."""
        self._need(BookingStatus.CONFIRMED)
        self._pay().status = PaymentStatus.REFUND_PENDING
        self.status = BookingStatus.CANCELLED
        self.cancelled_at, self.cancel_reason = now, reason

    def reject_paid(self, reason: str) -> None:
        """Tiền đã thu nhưng đơn không nhận được (số tiền lệch, đơn đã đóng): hoàn lại toàn bộ."""
        payment = self._pay()
        payment.status = PaymentStatus.REFUND_PENDING
        payment.last_failure_code = reason
        if self.status is BookingStatus.PENDING_PAYMENT:
            self.status = BookingStatus.PAYMENT_FAILED
            self.hold_expires_at = None

    def start_refund(self, refund_id: str | None) -> None:
        payment = self._pay()
        if payment.status is not PaymentStatus.REFUND_PENDING:
            raise InvalidTransition(f"thanh toán đang {payment.status.value}")
        payment.refund_id = refund_id or payment.refund_id

    def finish_refund(self, succeeded: bool) -> None:
        payment = self._pay()
        if payment.status is not PaymentStatus.REFUND_PENDING:
            raise InvalidTransition(f"thanh toán đang {payment.status.value}")
        payment.status = PaymentStatus.REFUNDED if succeeded else PaymentStatus.REFUND_FAILED
