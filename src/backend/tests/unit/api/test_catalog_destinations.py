"""GET /destinations là nguồn tên điểm đến cho `match_destination`; sai nó thì agent lọc rỗng."""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.backend.app.api.v1.routes import catalog as catalog_routes
from src.backend.app.application.itinerary.contracts import valid
from src.backend.app.domain.itinerary.normalization import match_destination


def _client(index) -> TestClient:
    app = FastAPI()
    app.include_router(catalog_routes.router, prefix="/api/v1")
    app.state.index = index
    return TestClient(app)


def test_response_matches_contract(services):
    body = _client(services["index"]).get("/api/v1/destinations").json()
    assert valid("DestinationListResponse", body)
    assert body["destinations"]


def test_counts_match_the_index(services):
    body = _client(services["index"]).get("/api/v1/destinations").json()
    total = sum(item["productCount"] for item in body["destinations"])
    assert total == len(services["index"].units)


def test_every_searchable_destination_is_listed(services):
    body = _client(services["index"]).get("/api/v1/destinations").json()
    listed = {item["destination"] for item in body["destinations"]}
    assert {product.destination for product in services["index"].units} == listed


def test_listed_names_canonicalize_accent_and_case_variants(services):
    supported = [item["destination"] for item in
                 _client(services["index"]).get("/api/v1/destinations").json()["destinations"]]
    assert match_destination("nha trang", supported) == "Nha Trang"
    assert match_destination("NHA TRANG", supported) == "Nha Trang"
    assert match_destination("Tokyo", supported) is None


def test_empty_before_recsys_is_ready():
    assert _client(None).get("/api/v1/destinations").json() == {"destinations": []}
