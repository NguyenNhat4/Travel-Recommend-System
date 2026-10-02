"""Booking domain: giỏ hàng, đơn giữ chỗ, thanh toán, huỷ, đoàn khách và giá theo loại khách (docs/prd/requirements.md FR-BKG-01…08)."""
from .cancellation import CancelDecision, cancellable_until, decide_cancellation
from .fares import FareLine, FareType, child_unit_price, fare_lines, lines_total
from .hold import HoldPolicy
from .models import Booking, BookingItem, Cart, CartLine, Payment
from .party import Guests, RoomAllocation, Traveler, TravelerType, adult_from, age_on, fare_type_on, is_infant_on
from .payment_failure import MAX_FAILED_ATTEMPTS, failure_reason_from_stripe
from .pricing import LineIssue, check_child_price, check_product, effective_child_price, line_total
from .reference_code import new_reference_code
from .status import BookingStatus, InvalidTransition, PaymentStatus

__all__ = [
    "Booking", "BookingItem", "BookingStatus", "CancelDecision", "Cart", "CartLine", "FareLine", "FareType", "Guests",
    "HoldPolicy", "InvalidTransition", "LineIssue", "MAX_FAILED_ATTEMPTS", "Payment", "PaymentStatus", "RoomAllocation",
    "Traveler", "TravelerType", "adult_from", "age_on", "cancellable_until", "check_child_price", "check_product",
    "child_unit_price", "decide_cancellation", "effective_child_price", "failure_reason_from_stripe", "fare_lines",
    "fare_type_on", "is_infant_on", "line_total", "lines_total", "new_reference_code",
]
