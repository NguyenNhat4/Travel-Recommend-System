"""GET /products?parentProductId= và GET /products/{id} trả fareClasses khớp contract 1.9.0 (schemas/catalog.yaml FareClass)."""
from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator, FormatChecker

from src.backend.app.api.deps import current_principal
from src.backend.app.application.catalog.use_cases import GetProductDetail, ListProducts
from src.backend.app.domain.catalog import Product
from src.backend.app.domain.catalog.fares import fare_classes_by_product
from src.backend.app.main import app
from src.backend.tests.contract.test_booking_contract import DOC, assert_contract
from src.backend.tests.conftest import P
from src.backend.tests.fakes.booking import PRINCIPAL
from src.backend.tests.fakes.catalog import InMemoryProductQuery
from src.backend.tests.unit.domain.test_fare_classes import FLIGHTS

ROUTE = P("RT", "Vé máy bay Hà Nội - Hồ Chí Minh", "flight", "Hồ Chí Minh",
          {"level": "route", "originCity": "Hà Nội", "destinationCity": "Hồ Chí Minh"}, price=None)
HOTEL = P("H1", "Khách sạn", "hotel", "Nha Trang", {"level": "property"}, price=None)
ROOM = P("R1", "Phòng", "hotel", "Nha Trang", {"level": "room", "parentProductId": "H1"}, price=1_000_000)


@pytest.fixture
def client():
    products = InMemoryProductQuery([ROUTE, HOTEL, ROOM, *FLIGHTS])
    values = {"get_product_detail": GetProductDetail(products), "list_products": ListProducts(products)}
    saved = {name: getattr(app.state, name, None) for name in values}
    for name, value in values.items():
        setattr(app.state, name, value)
    app.dependency_overrides[current_principal] = lambda: PRINCIPAL
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
        for name, value in saved.items():
            setattr(app.state, name, value)


def test_flight_variants_carry_fare_classes_of_their_itinerary(client):
    page = assert_contract(client.get("/api/v1/products", params={"parentProductId": "RT", "limit": 50}),
                           "/products", "get")
    by_id = {r["productId"]: r for r in page["results"]}
    assert set(by_id) == {"ECO", "BUS", "TRIP", "OTHER", "RTRIP"}
    assert [f["productId"] for f in by_id["BUS"]["fareClasses"]] == ["ECO", "BUS", "TRIP"]
    assert by_id["BUS"]["fareClasses"] == by_id["TRIP"]["fareClasses"]
    assert [f["code"] for f in by_id["ECO"]["fareClasses"]] == ["ECO", "BUS", None]


def test_fare_classes_are_grouped_before_paging(client):
    # Mỗi trang chỉ một dòng vẫn thấy đủ hạng của hành trình: gom trên mọi chuyến của tuyến, không chỉ trang hiện tại.
    seen = set()
    for offset in range(5):
        page = assert_contract(client.get("/api/v1/products", params={"parentProductId": "RT", "limit": 1,
                                                                      "offset": offset}), "/products", "get")
        row = page["results"][0]
        seen.add(row["productId"])
        if row["productId"] in {"ECO", "BUS", "TRIP"}:
            assert [f["productId"] for f in row["fareClasses"]] == ["ECO", "BUS", "TRIP"]
    assert {"ECO", "BUS", "TRIP"} <= seen


def test_flight_detail_carries_fare_classes_and_other_products_do_not(client):
    detail = assert_contract(client.get("/api/v1/products/BUS"), "/products/{productId}", "get")
    assert [f["code"] for f in detail["fareClasses"]] == ["ECO", "BUS", None]
    trip = assert_contract(client.get("/api/v1/products/RTRIP"), "/products/{productId}", "get")
    assert [f["productId"] for f in trip["fareClasses"]] == ["RTRIP"]
    for pid in ("RT", "H1", "R1"):
        body = assert_contract(client.get(f"/api/v1/products/{pid}"), "/products/{productId}", "get")
        assert "fareClasses" not in body
    rooms = assert_contract(client.get("/api/v1/products", params={"parentProductId": "H1"}), "/products", "get")
    assert all("fareClasses" not in r for r in rooms["results"])


def test_fare_class_payload_validates_against_schema_directly():
    schema = dict(DOC["components"]["schemas"]["FareClass"], components=DOC["components"])
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    for today in (date(2026, 9, 29), date(2026, 10, 1)):  # còn hạn và đã hết hạn
        for fares in fare_classes_by_product([Product.from_cdp(r) for r in FLIGHTS], today).values():
            for fare in fares:
                assert not list(validator.iter_errors(fare)), fare
