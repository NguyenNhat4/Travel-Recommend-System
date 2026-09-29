"""/products, /products/{id}, /products/{id}/similar và POST /events ở biên HTTP thật.

Mỗi response phải khớp schema contract gán cho status đó (`paths/catalog.yaml`, `paths/events.yaml`).
Use case chạy trên catalog giả (`tests/fakes/catalog.py`) và engine Similar với vector giả của conftest.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.backend.app.api.deps import current_principal
from src.backend.app.application.auth.errors import Unauthenticated
from src.backend.app.application.catalog.use_cases import GetProductDetail, GetSimilarProducts, ListProducts
from src.backend.app.application.search import SimilarProducts
from src.backend.app.application.tracking.behaviour import BehaviourTracker, CatalogProduct
from src.backend.app.main import app
from src.backend.tests.contract.test_booking_contract import assert_contract
from src.backend.tests.fakes.booking import PRINCIPAL
from src.backend.tests.fakes.catalog import InMemoryProductQuery
from src.backend.tests.unit.application.test_catalog_use_cases import ROWS_WITH_ROOMS


class Recorder:
    def __init__(self):
        self.events = []

    def record(self, event):
        self.events.append(event)


class Lookup:
    def __init__(self, products: InMemoryProductQuery):
        self.products = products

    async def find_product(self, product_id):
        p = await self.products.get(product_id)
        return CatalogProduct(p.product_id, p.taxonomy, p.unit_price) if p else None


@pytest.fixture
def state(services):
    products = InMemoryProductQuery(ROWS_WITH_ROOMS)
    recorder = Recorder()
    values = {
        "get_product_detail": GetProductDetail(products),
        "list_products": ListProducts(products),
        "get_similar_products": GetSimilarProducts(products, SimilarProducts(services["index"], services["vectors"])),
        "behaviour_tracker": BehaviourTracker(recorder, Lookup(products)),
    }
    saved = {name: getattr(app.state, name, None) for name in values}
    for name, value in values.items():
        setattr(app.state, name, value)
    app.dependency_overrides[current_principal] = lambda: PRINCIPAL
    try:
        yield {"recorder": recorder, **values}
    finally:
        app.dependency_overrides.clear()
        for name, value in saved.items():
            setattr(app.state, name, value)


@pytest.fixture
def client(state):
    return TestClient(app)


def test_product_detail_matches_contract(client):
    body = assert_contract(client.get("/api/v1/products/H1"), "/products/{productId}", "get")
    assert body["productId"] == "H1" and body["variantSummary"]["count"] == 3


def test_unknown_product_is_404_product_not_found(client):
    body = assert_contract(client.get("/api/v1/products/khong-co"), "/products/{productId}", "get")
    assert body["error"]["code"] == "PRODUCT_NOT_FOUND"
    assert body["error"]["details"] == {"productId": "khong-co"}
    assert body["error"]["message"] == "Sản phẩm này không còn trên V-OTA."


def test_listing_and_variants_match_contract(client):
    page = assert_contract(client.get("/api/v1/products", params={"sort": "popular", "limit": 5}), "/products", "get")
    assert page["limit"] == 5 and page["requestId"]
    rooms = assert_contract(client.get("/api/v1/products", params={"parentProductId": "H1"}), "/products", "get")
    assert [r["productId"] for r in rooms["results"]] == ["R1b", "R1", "R1c"]


def test_bad_listing_query_is_400_validation_error(client):
    body = assert_contract(client.get("/api/v1/products", params={"limit": 99}), "/products", "get")
    assert body["error"]["code"] == "VALIDATION_ERROR" and body["error"]["details"] == {"fields": ["limit"]}


def test_similar_matches_contract(client):
    body = assert_contract(client.get("/api/v1/products/R1/similar", params={"limit": 4}),
                           "/products/{productId}/similar", "get")
    assert body["productId"] == "H1" and body["resolvedFrom"] == "R1"


def test_similar_of_unknown_product_is_404(client):
    response = client.get("/api/v1/products/khong-co/similar")
    assert_contract(response, "/products/{productId}/similar", "get")
    assert response.json()["error"]["code"] == "PRODUCT_NOT_FOUND"


@pytest.mark.parametrize("limit", [0, 21])
def test_similar_limit_out_of_range_is_400_validation_error(client, limit):
    response = client.get("/api/v1/products/R1/similar", params={"limit": limit})
    body = assert_contract(response, "/products/{productId}/similar", "get")
    assert response.status_code == 400
    assert body["error"]["code"] == "VALIDATION_ERROR" and body["error"]["details"] == {"fields": ["limit"]}


def test_similar_of_product_without_vector_is_409_product_not_indexed(client):
    # X1 có trong catalog nhưng không có trong vector index của conftest.
    response = client.get("/api/v1/products/X1/similar")
    body = assert_contract(response, "/products/{productId}/similar", "get")
    assert response.status_code == 409
    assert body["error"]["code"] == "PRODUCT_NOT_INDEXED"
    assert body["error"]["details"] == {"productId": "X1", "taxonomy": "hotel"}


def test_similar_when_engine_is_off_is_503_search_unavailable(client, state):
    # RecSys tắt: composition root gắn use case không có engine Similar.
    app.state.get_similar_products = GetSimilarProducts(state["get_similar_products"].products, None)
    response = client.get("/api/v1/products/R1/similar")
    body = assert_contract(response, "/products/{productId}/similar", "get")
    assert response.status_code == 503
    assert body["error"]["code"] == "SEARCH_UNAVAILABLE" and body["error"]["retryable"] is True


def test_product_view_is_accepted_and_recorded(client, state):
    response = client.post("/api/v1/events", json={"eventName": "product_view", "productId": "A1"})
    assert_contract(response, "/events", "post")
    assert response.status_code == 202
    [event] = state["recorder"].events
    assert (event.cdp_user_id, event.product_id, event.taxonomy) == (PRINCIPAL.cdp_user_id, "A1", "attraction")


@pytest.mark.parametrize("payload", [
    {"eventName": "purchase", "productId": "A1"},
    {"eventName": "product_view", "productId": "A1", "taxonomy": "hotel"},
    {"eventName": "product_view"},
    {"eventName": "product_view", "productId": "  "},
])
def test_invalid_event_is_400_and_not_recorded(client, state, payload):
    response = client.post("/api/v1/events", json=payload)
    assert_contract(response, "/events", "post")
    assert response.status_code == 400 and response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert state["recorder"].events == []


def test_product_view_of_unknown_product_is_404_and_not_recorded(client, state):
    response = client.post("/api/v1/events", json={"eventName": "product_view", "productId": "khong-co"})
    assert_contract(response, "/events", "post")
    assert response.status_code == 404 and response.json()["error"]["details"] == {"productId": "khong-co"}
    assert state["recorder"].events == []


def test_product_view_requires_login(client):
    def reject():
        raise Unauthenticated("cần đăng nhập")

    app.dependency_overrides[current_principal] = reject
    response = client.post("/api/v1/events", json={"eventName": "product_view", "productId": "A1"})
    assert_contract(response, "/events", "post")
    assert response.status_code == 401
