"""Giỏ, checkout và vòng K1 trên bản giả (backend §7, cdp §5; FR-BKG-01…04, FR-REC-02, AC-REC-02)."""
import asyncio
from datetime import date, datetime, timedelta, timezone

import pytest

from src.backend.app.application.booking import CartService, Checkout, GetBooking
from src.backend.app.application.catalog.use_cases import GetProductDetail
from src.backend.app.application.itinerary.contracts import valid
from src.backend.app.application.recommendation import BuildPopularity, RecommendForUser
from src.backend.app.application.tracking.behaviour import BehaviourTracker
from src.backend.app.domain.booking import (
    BookingNotFound,
    CartEmpty,
    CartItemNotFound,
    CheckoutFailed,
    InvalidField,
    NotBookable,
    PriceChanged,
    ProductNotFound,
)
from src.backend.tests.fakes.booking import (
    InMemoryBookings,
    InMemoryCarts,
    InMemoryProductCatalog,
    RecordingCdp,
    RecordingEventRecorder,
)

NOW = datetime(2026, 9, 21, 9, 0, tzinfo=timezone.utc)
CONTACT = {"fullName": "Khách Test", "email": "khach@example.com", "phone": "0912345678"}


class World:
    def __init__(self, data_dir, *, cdp: RecordingCdp | None = None, fail_save: Exception | None = None):
        self.catalog = InMemoryProductCatalog.from_jsonl(data_dir / "products.jsonl")
        self.carts = InMemoryCarts()
        self.bookings = InMemoryBookings(self.carts, fail_save=fail_save)
        self.cdp = cdp or RecordingCdp()
        self.recorder = RecordingEventRecorder()
        self.cart = CartService(self.carts, self.catalog, BehaviourTracker(self.recorder, self.catalog))
        self.checkout = Checkout(self.carts, self.bookings, self.catalog, self.cdp, clock=lambda: NOW)
        self.get_booking = GetBooking(self.bookings, self.catalog)


def run(coro):
    return asyncio.run(coro)


# ---- chi tiết sản phẩm: property/route trả tầng con đặt được (FR-CAT-02) ----

def test_property_detail_lists_bookable_rooms(data_dir):
    catalog = InMemoryProductCatalog.from_jsonl(data_dir / "products.jsonl")
    detail = run(GetProductDetail(catalog, today=lambda: date(2026, 9, 21))("H1"))
    assert valid("ProductDetail", detail)
    assert detail["bookable"] is False
    assert [variant["productId"] for variant in detail["variants"]] == ["R1"]
    assert detail["variants"][0]["priceUnit"] == "PER_NIGHT"


def test_route_detail_lists_flights_and_bookable_products_have_no_variants(data_dir):
    catalog = InMemoryProductCatalog.from_jsonl(data_dir / "products.jsonl")
    detail = GetProductDetail(catalog, today=lambda: date(2026, 9, 21))
    assert [variant["productId"] for variant in run(detail("F1"))["variants"]] == ["FL1"]
    attraction = run(detail("A1"))
    assert attraction["variants"] == [] and attraction["bookable"] is None
    with pytest.raises(ProductNotFound):
        run(detail("không-có"))


# ---- giỏ ----

def test_add_room_prices_by_nights_and_records_add_to_cart(data_dir):
    world = World(data_dir)
    cart = run(world.cart.add("U1", "R1", date(2026, 10, 5), 2, nights=3))
    assert valid("CartResponse", cart)
    [item] = cart["items"]
    assert item["nights"] == 3 and item["lineTotal"] == 3_400_000 * 3 * 2 and cart["total"] == item["lineTotal"]
    [event] = world.recorder.events
    assert (event.event_name, event.product_id, event.taxonomy, event.quantity) == ("add_to_cart", "R1", "hotel", 2)


def test_property_cannot_go_into_the_cart(data_dir):
    world = World(data_dir)
    with pytest.raises(NotBookable):
        run(world.cart.add("U1", "H1", date(2026, 10, 5), 1, nights=1))
    assert world.recorder.events == []  # thêm thất bại không ghi event


def test_hotel_requires_nights_and_same_date_merges(data_dir):
    world = World(data_dir)
    with pytest.raises(InvalidField):
        run(world.cart.add("U1", "R1", date(2026, 10, 5), 1))
    run(world.cart.add("U1", "A1", date(2026, 10, 6), 1))
    cart = run(world.cart.add("U1", "A1", date(2026, 10, 6), 2))
    assert [(item["product"]["productId"], item["quantity"]) for item in cart["items"]] == [("A1", 3)]


def test_update_and_remove_only_touch_the_owners_items(data_dir):
    world = World(data_dir)
    cart = run(world.cart.add("U1", "R1", date(2026, 10, 5), 1, nights=1))
    item_id = cart["items"][0]["cartItemId"]
    cart = run(world.cart.update("U1", item_id, nights=2, quantity=2))
    assert cart["items"][0]["lineTotal"] == 3_400_000 * 2 * 2
    with pytest.raises(CartItemNotFound):
        run(world.cart.remove("U2", item_id))
    assert run(world.cart.remove("U1", item_id))["items"] == []


# ---- checkout ----

def test_checkout_writes_one_purchase_per_item_then_clears_the_cart(data_dir):
    world = World(data_dir)
    cart = run(world.cart.add("U1", "R1", date(2026, 10, 5), 1, nights=2))
    run(world.cart.add("U1", "A1", date(2026, 10, 6), 2))
    item_id = cart["items"][0]["cartItemId"]
    booking = run(world.checkout("U1", CONTACT, [{"cartItemId": item_id, "guestNames": ["Khách Test"],
                                                  "specialRequest": "Phòng tầng cao"}]))
    assert valid("BookingResponse", booking)
    [group] = booking["groups"]
    assert group["destination"] == "Nha Trang" and booking["total"] == group["groupTotal"] == 3_400_000 * 2 + 880_000 * 2
    purchases = world.cdp.active_purchases()
    assert len(purchases) == 2 and {event.event_group_id for event in purchases} == {group["eventGroupId"]}
    assert {event.event_id for event in purchases} == {f"purchase:{item['bookingItemId']}" for item in group["items"]}
    assert run(world.cart.get("U1"))["items"] == []
    # Tải lại trang xác nhận trả đúng payload; đơn của người khác như không tồn tại (backend §7.3).
    assert run(world.get_booking("U1", booking["referenceCode"])) == booking
    with pytest.raises(BookingNotFound):
        run(world.get_booking("U2", booking["referenceCode"]))


def test_checkout_rejects_empty_cart_unknown_detail_and_changed_price(data_dir):
    world = World(data_dir)
    with pytest.raises(CartEmpty):
        run(world.checkout("U1", CONTACT, []))
    run(world.cart.add("U1", "A1", date(2026, 10, 6), 1))
    with pytest.raises(InvalidField):
        run(world.checkout("U1", CONTACT, [{"cartItemId": "lạ"}]))
    world.catalog.by_id["A1"].unit_price = 990_000
    with pytest.raises(PriceChanged) as changed:
        run(world.checkout("U1", CONTACT, []))
    assert changed.value.details == {"productId": "A1", "oldPrice": 880_000, "newPrice": 990_000}
    assert world.cdp.purchases == {} and len(run(world.cart.get("U1"))["items"]) == 1


def test_cdp_down_means_no_booking_and_the_cart_is_kept(data_dir):
    world = World(data_dir, cdp=RecordingCdp(fail_record=True))
    run(world.cart.add("U1", "A1", date(2026, 10, 6), 1))
    with pytest.raises(CheckoutFailed) as failed:
        run(world.checkout("U1", CONTACT, []))
    assert failed.value.retryable
    assert world.bookings.saved == {} and len(run(world.cart.get("U1"))["items"]) == 1


def test_commit_failure_cancels_the_purchases(data_dir):
    world = World(data_dir, fail_save=RuntimeError("db down"))
    run(world.cart.add("U1", "A1", date(2026, 10, 6), 1))
    with pytest.raises(CheckoutFailed):
        run(world.checkout("U1", CONTACT, []))
    assert world.cdp.purchases and world.cdp.active_purchases() == []  # booking không được tồn tại thiếu event


# ---- K1: đặt xong thì gợi ý đổi sang đúng chuyến vừa đặt ----

def test_booking_a_room_turns_recommendations_to_the_rest_of_that_trip(data_dir, services):
    """AC-REC-02: đặt phòng ở X → gợi ý vé máy bay và hoạt động ở X, không lặp khách sạn, kèm because."""
    world = World(data_dir)
    recommend = RecommendForUser(services["index"], services["vectors"], world.cdp,
                                 BuildPopularity(services["index"], world.cdp)(now=NOW))
    before = recommend("NEW", k=4, now=NOW)
    assert before["strategy"] == "popular" and before["diagnostics"]["coldStart"]

    run(world.cart.add("NEW", "R1", date(2026, 10, 5), 1, nights=2))
    booking = run(world.checkout("NEW", CONTACT, []))

    after = recommend("NEW", k=4, now=NOW + timedelta(seconds=1))
    assert after["strategy"] == "cross_vertical"
    assert after["destination"] == booking["groups"][0]["destination"] == "Nha Trang"
    assert after["nextVertical"] is not None and after["diagnostics"]["excludedVerticals"] == ["hotel"]
    assert after["recommendations"]
    assert all(item["taxonomy"] != "hotel" and item["destination"] == "Nha Trang"
               for item in after["recommendations"])
    because = after["recommendations"][0]["because"][0]
    assert (because["productId"], because["event"], because["daysAgo"]) == ("R1", "purchase", 0)
