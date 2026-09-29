"""Giỏ hàng, giữ chỗ, webhook và huỷ đơn ở biên HTTP thật (spec booking §6–§10).

Mỗi response phải khớp schema contract gán cho status đó và status phải được khai báo trong
`paths/booking.yaml` / `paths/payments.yaml`. Use case chạy trên bản giả (`tests/fakes/booking.py`).
"""
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date

import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator, FormatChecker

from src.backend.app.api.deps import current_principal
from src.backend.app.application.auth.errors import Unauthenticated
from src.backend.app.domain.booking.status import BookingStatus
from src.backend.app.infrastructure.payments.fake_gateway import VALID_SIGNATURE
from src.backend.app.main import app
from src.backend.tests.fakes.booking import HOTEL, PRINCIPAL, TICKET, World
from src.shared.contracts.scripts.bundle_openapi import bundle

DOC = bundle()
CONTACT = {"fullName": "Nguyễn Minh Anh", "email": "minh@example.vn", "phone": "0912345678"}
CHECKOUT = {"contact": CONTACT, "itemDetails": []}


@pytest.fixture
def world():
    w = World()
    saved = {name: getattr(app.state, name, None) for name in w.state()}
    for name, value in w.state().items():
        setattr(app.state, name, value)
    app.dependency_overrides[current_principal] = lambda: PRINCIPAL
    try:
        yield w
    finally:
        app.dependency_overrides.clear()
        for name, value in saved.items():
            setattr(app.state, name, value)


@pytest.fixture
def client(world):
    return TestClient(app)


def assert_contract(response, path: str, method: str) -> dict | None:
    operation = DOC["paths"][path][method]
    status = str(response.status_code)
    assert status in operation["responses"], f"{method.upper()} {path} trả {status} chưa khai báo trong contract"
    declared = operation["responses"][status]
    if "$ref" in declared:
        declared = DOC["components"]["responses"][declared["$ref"].split("/")[-1]]
    if "content" not in declared:
        assert not response.content
        return None
    schema = declared["content"]["application/json"]["schema"]
    body = response.json()
    errors = [e.message for e in Draft202012Validator(dict(schema, components=DOC["components"]),
                                                      format_checker=FormatChecker()).iter_errors(body)]
    assert not errors, errors
    if response.status_code >= 400:
        assert body["error"]["code"] in DOC["components"]["schemas"]["ErrorCode"]["enum"]
    return body


def fill(client) -> dict:
    client.post("/api/v1/cart/items", json={"productId": HOTEL, "usingDate": "2026-10-15", "quantity": 1, "nights": 3})
    response = client.post("/api/v1/cart/items", json={"productId": TICKET, "usingDate": "2026-10-15", "quantity": 2})
    return assert_contract(response, "/cart/items", "post")


def checkout_body(client) -> dict:
    """Request kiểu cũ (không có `travelers`): mỗi mục giỏ một itemDetails; khách sạn 1 tên, vé máy bay đủ số tên."""
    details = []
    for item in client.get("/api/v1/cart").json()["items"]:
        taxonomy = item["product"]["taxonomy"]
        names = ["Nguyễn Minh Anh"] * (item["quantity"] if taxonomy == "flight" else 1 if taxonomy == "hotel" else 0)
        details.append({"cartItemId": item["cartItemId"], **({"guestNames": names} if names else {})})
    return {"contact": CONTACT, "itemDetails": details}


def webhook(client, event, signature=VALID_SIGNATURE):
    body = json.dumps({k: v for k, v in asdict(event).items() if v is not None})
    return client.post("/api/v1/payments/stripe/webhook", content=body,
                       headers={"Stripe-Signature": signature, "Content-Type": "application/json"})


# --- giỏ hàng -----------------------------------------------------------------------------------

def test_cart_crud_matches_contract(client):
    empty = assert_contract(client.get("/api/v1/cart"), "/cart", "get")
    assert empty["items"] == [] and empty["total"] == 0

    cart = fill(client)
    assert cart["itemCount"] == 2 and cart["total"] == 3_400_000 * 3 + 880_000 * 2
    hotel = next(i for i in cart["items"] if i["product"]["productId"] == HOTEL)

    patched = assert_contract(client.patch(f"/api/v1/cart/items/{hotel['cartItemId']}", json={"quantity": 2}),
                              "/cart/items/{cartItemId}", "patch")
    assert next(i for i in patched["items"] if i["cartItemId"] == hotel["cartItemId"])["lineTotal"] == 3_400_000 * 3 * 2

    removed = assert_contract(client.delete(f"/api/v1/cart/items/{hotel['cartItemId']}"),
                              "/cart/items/{cartItemId}", "delete")
    assert removed["itemCount"] == 1


def test_cart_errors_match_contract(client):
    unknown = assert_contract(client.post("/api/v1/cart/items", json={
        "productId": "33333333-3333-3333-3333-333333333333", "usingDate": "2026-10-15", "quantity": 1}),
        "/cart/items", "post")
    assert unknown["error"]["code"] == "PRODUCT_NOT_FOUND"

    out_of_range = assert_contract(client.post("/api/v1/cart/items", json={
        "productId": HOTEL, "usingDate": "2027-03-01", "quantity": 1}), "/cart/items", "post")
    assert out_of_range["error"]["code"] == "DATE_OUT_OF_RANGE" and out_of_range["error"]["details"]["availableTo"]

    missing = assert_contract(client.delete("/api/v1/cart/items/not-a-uuid"), "/cart/items/{cartItemId}", "delete")
    assert missing["error"]["code"] == "CART_ITEM_NOT_FOUND"

    no_change = client.patch("/api/v1/cart/items/x", json={})
    assert no_change.status_code == 400 and no_change.json()["error"]["code"] == "VALIDATION_ERROR"


def test_booking_routes_require_login(client):
    def reject():
        raise Unauthenticated("cần đăng nhập")

    app.dependency_overrides[current_principal] = reject
    for method, path in [("get", "/api/v1/cart"), ("post", "/api/v1/bookings"),
                         ("get", "/api/v1/bookings/VOTA-20260916-AB12")]:
        response = getattr(client, method)(path, **({"json": CHECKOUT} if method == "post" else {}))
        assert response.status_code == 401


# --- giữ chỗ và thanh toán ----------------------------------------------------------------------

def test_create_hold_then_second_attempt_conflicts(client, world):
    assert assert_contract(client.post("/api/v1/bookings", json=CHECKOUT), "/bookings", "post")["error"]["code"] \
        == "CART_EMPTY"
    fill(client)
    held = assert_contract(client.post("/api/v1/bookings", json=checkout_body(client)), "/bookings", "post")
    assert held["status"] == "PENDING_PAYMENT" and held["payment"]["status"] == "OPEN"
    assert held["payment"]["checkoutUrl"].startswith("https://checkout.fake/") and held["holdExpiresAt"]
    assert held["cancellableUntil"] is None and held["cancellation"] is None

    again = assert_contract(client.post("/api/v1/bookings", json=checkout_body(client)), "/bookings", "post")
    assert again["error"]["code"] == "BOOKING_PENDING_PAYMENT"
    assert again["error"]["details"]["referenceCode"] == held["referenceCode"]

    read = assert_contract(client.get(f"/api/v1/bookings/{held['referenceCode']}"), "/bookings/{referenceCode}", "get")
    assert read["referenceCode"] == held["referenceCode"]
    missing = assert_contract(client.get("/api/v1/bookings/VOTA-20260916-ZZZZ"), "/bookings/{referenceCode}", "get")
    assert missing["error"]["code"] == "BOOKING_NOT_FOUND"


def test_provider_timeout_is_503_retryable_with_retry_after(client, world):
    fill(client)
    world.gateway.mode = "timeout"
    response = client.post("/api/v1/bookings", json=checkout_body(client))
    body = assert_contract(response, "/bookings", "post")
    assert response.status_code == 503 and response.headers["Retry-After"]
    assert body["error"]["code"] == "PAYMENT_PROVIDER_UNAVAILABLE" and body["error"]["retryable"] is True
    assert world.store.bookings == {}


def test_signed_webhook_confirms_and_bad_signature_is_rejected(client, world):
    fill(client)
    ref = client.post("/api/v1/bookings", json=checkout_body(client)).json()["referenceCode"]
    session = world.booking(ref).payment.checkout_session_id

    bad = webhook(client, world.gateway.pay(session), signature="forged")
    assert assert_contract(bad, "/payments/stripe/webhook", "post")["error"]["code"] == "INVALID_WEBHOOK_SIGNATURE"
    assert world.booking(ref).status is BookingStatus.PENDING_PAYMENT

    ok = webhook(client, world.gateway.pay(session))
    assert_contract(ok, "/payments/stripe/webhook", "post")
    confirmed = assert_contract(client.get(f"/api/v1/bookings/{ref}"), "/bookings/{referenceCode}", "get")
    assert confirmed["status"] == "CONFIRMED" and confirmed["payment"]["checkoutUrl"] is None
    assert confirmed["cancellableUntil"] and confirmed["holdExpiresAt"] is None
    assert len(world.cdp.recorded) == 1
    assert assert_contract(client.get("/api/v1/cart"), "/cart", "get")["items"] == []   # mục đã đặt rời giỏ


def test_webhook_failure_answers_500_so_stripe_retries(client, world):
    fill(client)
    ref = client.post("/api/v1/bookings", json=checkout_body(client)).json()["referenceCode"]
    world.cdp.down = True
    response = webhook(client, world.gateway.pay(world.booking(ref).payment.checkout_session_id))
    assert response.status_code == 500 and "bookingId" not in response.text


# --- huỷ --------------------------------------------------------------------------------------

def test_cancel_paid_booking_refunds_and_cancel_again_is_idempotent(client, world):
    fill(client)
    ref = client.post("/api/v1/bookings", json=checkout_body(client)).json()["referenceCode"]
    webhook(client, world.gateway.pay(world.booking(ref).payment.checkout_session_id))

    path = "/bookings/{referenceCode}/cancel"
    cancelled = assert_contract(client.post(f"/api/v1/bookings/{ref}/cancel", json={"reason": "Đổi kế hoạch"}),
                                path, "post")
    assert cancelled["status"] == "CANCELLED" and cancelled["payment"]["status"] == "REFUNDED"
    assert cancelled["cancellation"]["refundAmount"] == cancelled["total"] == cancelled["payment"]["refundedAmount"]
    again = assert_contract(client.post(f"/api/v1/bookings/{ref}/cancel"), path, "post")
    assert again == cancelled and len(world.gateway.refunds) == 1


def test_cancel_expired_booking_is_not_cancellable(client, world):
    fill(client)
    ref = client.post("/api/v1/bookings", json=checkout_body(client)).json()["referenceCode"]
    webhook(client, world.gateway.expire_event(world.booking(ref).payment.checkout_session_id))
    expired = assert_contract(client.get(f"/api/v1/bookings/{ref}"), "/bookings/{referenceCode}", "get")
    assert expired["status"] == "EXPIRED" and expired["payment"]["checkoutUrl"] is None
    rejected = assert_contract(client.post(f"/api/v1/bookings/{ref}/cancel"), "/bookings/{referenceCode}/cancel",
                               "post")
    assert rejected["error"]["code"] == "BOOKING_NOT_CANCELLABLE" and rejected["error"]["details"]["reason"] == \
        "NOT_ACTIVE"


def test_cancel_too_late_reports_deadline(client, world):
    world.clock.now = world.clock.now.replace(year=2026, month=10, day=14, hour=1)   # 08:00 giờ VN ngày 14/10
    client.post("/api/v1/cart/items", json={"productId": TICKET, "usingDate": date(2026, 10, 15).isoformat(),
                                            "quantity": 1})
    ref = client.post("/api/v1/bookings", json=checkout_body(client)).json()["referenceCode"]
    webhook(client, world.gateway.pay(world.booking(ref).payment.checkout_session_id))
    rejected = assert_contract(client.post(f"/api/v1/bookings/{ref}/cancel"), "/bookings/{referenceCode}/cancel",
                               "post")
    assert rejected["error"]["details"] == {"referenceCode": ref, "reason": "TOO_LATE",
                                            "cancellableUntil": "2026-10-13T17:00:00Z"}


# --- checkout nhiều bước: đoàn khách, giá theo loại khách, mọi vi phạm trong một lần (contract 1.10.0) -------------

def _family_cart(client) -> dict:
    """Giỏ của ví dụ gia đình: khách sạn 1 phòng + vé tham quan, cho 2 người lớn và 1 trẻ em."""
    guests = {"adults": 2, "children": 1}
    client.post("/api/v1/cart/items", json={"productId": HOTEL, "usingDate": "2026-10-15", "quantity": 1, "nights": 2,
                                            "guests": guests})
    return assert_contract(client.post("/api/v1/cart/items", json={
        "productId": TICKET, "usingDate": "2026-10-16", "guests": guests}), "/cart/items", "post")


def _family_body(cart: dict) -> dict:
    by = {i["product"]["productId"]: i["cartItemId"] for i in cart["items"]}
    return {
        "contact": CONTACT,
        "travelers": [
            {"travelerRef": "t1", "type": "ADULT", "surname": "Nguyễn", "givenNames": "Minh Anh"},
            {"travelerRef": "t2", "type": "ADULT", "surname": "Trần", "givenNames": "Thu Hà"},
            {"travelerRef": "t3", "type": "CHILD", "surname": "Nguyễn", "givenNames": "Gia Bảo", "birthDate": "2019-05-12"}],
        "itemDetails": [
            {"cartItemId": by[HOTEL], "rooms": [{"travelerRefs": ["t1", "t2", "t3"], "leadTravelerRef": "t1"}]},
            {"cartItemId": by[TICKET], "travelerRefs": ["t1", "t2", "t3"]}],
    }


def test_cart_response_carries_guests_and_fares_and_derives_quantity(client):
    cart = _family_cart(client)
    ticket = next(i for i in cart["items"] if i["product"]["productId"] == TICKET)
    assert ticket["quantity"] == 3 and ticket["guests"] == {"adults": 2, "children": 1}
    assert [f["fareType"] for f in ticket["fares"]] == ["ADULT", "CHILD"]
    assert ticket["lineTotal"] == sum(f["amount"] for f in ticket["fares"])
    assert cart["total"] == sum(i["lineTotal"] for i in cart["items"])


def test_family_checkout_returns_travelers_and_fares_and_never_the_birth_date(client, world):
    cart = _family_cart(client)
    held = assert_contract(client.post("/api/v1/bookings", json=_family_body(cart)), "/bookings", "post")
    assert held["status"] == "PENDING_PAYMENT" and held["total"] == held["payment"]["amount"] == cart["total"]
    items = {i["product"]["taxonomy"]: i for i in held["groups"][0]["items"]}
    assert items["hotel"]["travelers"][0] == {"fullName": "Nguyễn Minh Anh", "type": "ADULT", "roomNo": 1, "isLead": True}
    assert [f["fareType"] for f in items["attraction"]["fares"]] == ["ADULT", "CHILD"]
    assert "2019-05-12" not in json.dumps(held) and "birthDate" not in json.dumps(held)


def test_validation_error_lists_every_violation_with_field_reason_and_message(client, world):
    cart = _family_cart(client)
    body = _family_body(cart)
    body["travelers"][2]["birthDate"] = "2014-10-15"                       # đã đủ 12 tuổi vào 15/10/2026
    body["travelers"][0]["surname"] = ""
    body["itemDetails"][1]["travelerRefs"] = ["t1", "t2"]                  # khác số khách đã thấy giá
    response = client.post("/api/v1/bookings", json=body)
    error = assert_contract(response, "/bookings", "post")["error"]
    assert response.status_code == 400 and error["code"] == "VALIDATION_ERROR"
    assert {(f["field"], f["reason"]) for f in error["details"]["fields"]} == {
        ("travelers[0].surname", "REQUIRED"), ("travelers[2].birthDate", "CHILD_AGE_INVALID"),
        ("itemDetails[1]", "GUEST_COUNT_MISMATCH")}
    assert world.store.bookings == {} and world.gateway.sessions == {}


def test_shape_errors_stay_422_and_rule_errors_are_400(client):
    cart = _family_cart(client)
    body = _family_body(cart)
    body["travelers"][0]["type"] = "SENIOR"                                # sai kiểu dữ liệu, không phải luật nghiệp vụ
    assert client.post("/api/v1/bookings", json=body).status_code == 422
    empty_party = _family_body(cart)
    empty_party["travelers"] = []
    response = client.post("/api/v1/bookings", json=empty_party)
    assert response.status_code == 400
    assert "ADULT_REQUIRED" in {f["reason"] for f in response.json()["error"]["details"]["fields"]}


def test_cart_guest_rules_are_validation_errors_with_reasons(client):
    client.post("/api/v1/cart/items", json={"productId": TICKET, "usingDate": "2026-10-16", "guests": {"adults": 2, "children": 1}})
    too_many = client.post("/api/v1/cart/items", json={"productId": TICKET, "usingDate": "2026-10-16",
                                                       "guests": {"adults": 9, "children": 0}})
    error = assert_contract(too_many, "/cart/items", "post")["error"]
    assert too_many.status_code == 400 and error["details"]["fields"][0]["reason"] == "PARTY_TOO_LARGE"
    neither = client.post("/api/v1/cart/items", json={"productId": TICKET, "usingDate": "2026-10-16"})
    assert neither.status_code == 400 and neither.json()["error"]["details"]["fields"][0]["field"] == "quantity"


def test_patching_guests_recomputes_quantity_and_fares(client):
    cart = _family_cart(client)
    ticket = next(i for i in cart["items"] if i["product"]["productId"] == TICKET)
    patched = assert_contract(
        client.patch(f"/api/v1/cart/items/{ticket['cartItemId']}", json={"guests": {"adults": 2, "children": 2}}),
        "/cart/items/{cartItemId}", "patch")
    item = next(i for i in patched["items"] if i["cartItemId"] == ticket["cartItemId"])
    assert item["quantity"] == 4 and item["guests"] == {"adults": 2, "children": 2}
    assert next(f for f in item["fares"] if f["fareType"] == "CHILD")["count"] == 2
