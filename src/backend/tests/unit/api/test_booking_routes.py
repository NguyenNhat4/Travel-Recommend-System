"""HTTP của chi tiết sản phẩm, giỏ và checkout: status, Error Envelope và payload theo contract (backend §4.2, §7, §8)."""
import re

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.backend.app.api.errors import install_error_handlers
from src.backend.app.api.middleware import install_request_id
from src.backend.app.api.v1.routes import bookings as booking_routes
from src.backend.app.api.v1.routes import cart as cart_routes
from src.backend.app.api.v1.routes import catalog as catalog_routes
from src.backend.app.application.auth.principal import AuthenticatedUser
from src.backend.app.application.booking import CartService, Checkout, GetBooking
from src.backend.app.application.catalog.use_cases import GetProductDetail
from src.backend.app.application.itinerary.contracts import valid
from src.backend.tests.fakes.auth import jwt_issuer
from src.backend.tests.fakes.booking import InMemoryBookings, InMemoryCarts, InMemoryProductCatalog, RecordingCdp

CONTACT = {"fullName": "Khách Test", "email": "khach@example.com", "phone": "0912345678"}


@pytest.fixture
def api(data_dir):
    issuer = jwt_issuer()
    catalog = InMemoryProductCatalog.from_jsonl(data_dir / "products.jsonl")
    carts = InMemoryCarts()
    bookings = InMemoryBookings(carts)
    cdp = RecordingCdp()
    app = FastAPI()
    install_request_id(app)
    install_error_handlers(app)
    for routes in (catalog_routes, cart_routes, booking_routes):
        app.include_router(routes.router, prefix="/api/v1")
    app.state.token_verifier = issuer
    app.state.product_detail = GetProductDetail(catalog)
    app.state.cart_service = CartService(carts, catalog)
    app.state.checkout = Checkout(carts, bookings, catalog, cdp)
    app.state.get_booking = GetBooking(bookings, catalog)

    def auth(n: int) -> dict:
        user = AuthenticatedUser(f"u-{n}", f"khach{n}@example.com", "x", "Khách", f"VP{n:07d}")
        token, _ = issuer.issue_access_token(user, session_id=None, amr=("pwd",))
        return {"Authorization": f"Bearer {token}"}

    return TestClient(app), auth, cdp


def test_product_detail_is_public_and_lists_rooms(api):
    client, _, _ = api
    response = client.get("/api/v1/products/H1")
    assert response.status_code == 200 and valid("ProductDetail", response.json())
    assert [variant["productId"] for variant in response.json()["variants"]] == ["R1"]
    missing = client.get("/api/v1/products/khong-co")
    assert missing.status_code == 404 and missing.json()["error"]["code"] == "PRODUCT_NOT_FOUND"


def test_cart_requires_login(api):
    client, _, _ = api
    response = client.get("/api/v1/cart")
    assert response.status_code == 401 and response.json()["error"]["code"] == "UNAUTHENTICATED"


def test_adding_a_property_asks_for_a_room(api):
    client, auth, _ = api
    response = client.post("/api/v1/cart/items", headers=auth(1),
                           json={"productId": "H1", "usingDate": "2026-10-05", "quantity": 1, "nights": 1})
    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR" and error["details"]["fields"] == ["productId"]
    assert "hạng phòng" in error["message"] and error["retryable"] is False


def test_checkout_round_trip_follows_the_contract(api):
    client, auth, cdp = api
    added = client.post("/api/v1/cart/items", headers=auth(1),
                        json={"productId": "R1", "usingDate": "2026-10-05", "quantity": 1, "nights": 2})
    assert added.status_code == 200 and valid("CartResponse", added.json())
    item_id = added.json()["items"][0]["cartItemId"]

    created = client.post("/api/v1/bookings", headers=auth(1),
                          json={"contact": CONTACT, "itemDetails": [{"cartItemId": item_id, "guestNames": ["Khách"]}]})
    assert created.status_code == 201 and valid("BookingResponse", created.json())
    reference = created.json()["referenceCode"]
    assert re.fullmatch(r"VOTA-\d{8}-[A-Z0-9]{4}", reference)
    assert len(cdp.active_purchases()) == 1  # event có trước khi trả 201 (backend §7.4 cam kết 5)

    assert client.get(f"/api/v1/bookings/{reference}", headers=auth(1)).json() == created.json()
    other = client.get(f"/api/v1/bookings/{reference}", headers=auth(2))
    assert other.status_code == 404 and other.json()["error"]["code"] == "BOOKING_NOT_FOUND"
    again = client.post("/api/v1/bookings", headers=auth(1), json={"contact": CONTACT, "itemDetails": []})
    assert again.status_code == 400 and again.json()["error"]["code"] == "CART_EMPTY"


def test_cdp_outage_is_a_retryable_500_and_keeps_the_cart(api):
    client, auth, cdp = api
    cdp.fail_record = True
    client.post("/api/v1/cart/items", headers=auth(1), json={"productId": "A1", "usingDate": "2026-10-06", "quantity": 1})
    response = client.post("/api/v1/bookings", headers=auth(1), json={"contact": CONTACT, "itemDetails": []})
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR" and response.json()["error"]["retryable"] is True
    assert client.get("/api/v1/cart", headers=auth(1)).json()["itemCount"] == 1


def test_invalid_contact_is_rejected_before_touching_the_cart(api):
    client, auth, cdp = api
    client.post("/api/v1/cart/items", headers=auth(1), json={"productId": "A1", "usingDate": "2026-10-06", "quantity": 1})
    response = client.post("/api/v1/bookings", headers=auth(1),
                           json={"contact": {**CONTACT, "phone": "12345"}, "itemDetails": []})
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert cdp.purchases == {}
