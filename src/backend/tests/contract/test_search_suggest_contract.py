"""GET /search/suggestions ở biên HTTP thật: response khớp `paths/search.yaml`, không cần đăng nhập."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.backend.app.application.search import SuggestProducts
from src.backend.app.main import app
from src.backend.tests.contract.test_booking_contract import assert_contract

PATH = "/search/suggestions"


@pytest.fixture
def client(services):
    saved = getattr(app.state, "suggest", None)
    app.state.suggest = SuggestProducts(services["index"])
    try:
        yield TestClient(app)
    finally:
        app.state.suggest = saved


def test_suggestions_match_contract_and_are_cacheable(client):
    response = client.get("/api/v1/search/suggestions", params={"q": "nha", "limit": 8})
    body = assert_contract(response, PATH, "get")
    assert response.status_code == 200 and body["query"] == "nha"
    assert body["suggestions"][0] == {"type": "destination", "label": "Nha Trang",
                                      "productCount": body["suggestions"][0]["productCount"]}
    assert any(s["type"] == "product" for s in body["suggestions"])
    assert response.headers["cache-control"] == "public, max-age=300"


def test_short_query_is_200_with_no_suggestions(client):
    for q in ("n", "  ", "-"):
        body = assert_contract(client.get("/api/v1/search/suggestions", params={"q": q}), PATH, "get")
        assert body["suggestions"] == []


def test_invalid_parameters_are_422(client):
    for params in ({}, {"q": ""}, {"q": "x" * 101}, {"q": "nha", "limit": 0}, {"q": "nha", "limit": 11}):
        response = client.get("/api/v1/search/suggestions", params=params)
        body = assert_contract(response, PATH, "get")
        assert response.status_code == 422 and body["error"]["code"] == "VALIDATION_ERROR"


def test_empty_and_uncached_before_recsys_is_ready(client):
    app.state.suggest = None
    response = client.get("/api/v1/search/suggestions", params={"q": "nha  trang"})
    assert assert_contract(response, PATH, "get") == {"query": "nha trang", "suggestions": []}
    assert "cache-control" not in response.headers
