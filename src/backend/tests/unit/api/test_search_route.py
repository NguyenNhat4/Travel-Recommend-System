"""Route /search (contract 1.15.0): GET và POST chuyển đủ tham số lọc tường minh xuống engine (trước 06/10 route bỏ qua
priceMin/priceMax/starRatingMin/availableOnly dù contract đã khai); priceMin > priceMax → 400 VALIDATION_ERROR."""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.backend.app.api.v1.routes import search as search_routes


class SpySearch:
    cutoff = 0.52

    def __init__(self):
        self.calls = []

    def __call__(self, q, **kw):
        self.calls.append((q, kw))
        return {"results": [], "total": 0, "limit": kw["limit"], "offset": kw["offset"], "topScore": None,
                "cutoff": self.cutoff, "facets": {"taxonomy": {}, "destination": {}},
                "diagnostics": {"searchMode": "ANN_CANDIDATE_SCORE", "approximate": True, "totalExact": False,
                                "facetsExact": False, "filteredCount": 0, "relevantCount": 0, "modelVersion": "x"}}


def _client(search=None) -> tuple[TestClient, SpySearch | None]:
    app = FastAPI()
    app.include_router(search_routes.router, prefix="/api/v1")
    app.state.search = search
    return TestClient(app), search


def test_get_passes_every_filter_param_to_the_engine():
    client, spy = _client(SpySearch())
    r = client.get("/api/v1/search", params={"q": "vé máy bay Nha Trang", "taxonomy": "flight", "origin": "Hà Nội",
                                             "priceMin": 1000000, "priceMax": 3000000, "starRatingMin": 4, "availableOnly": "false",
                                             "limit": 5, "offset": 10})
    assert r.status_code == 200
    q, kw = spy.calls[0]
    assert q == "vé máy bay Nha Trang"
    assert kw == {"taxonomy": "flight", "destination": None, "origin": "Hà Nội", "price_min": 1000000, "price_max": 3000000,
                  "star_min": 4.0, "available_only": False, "limit": 5, "offset": 10}


def test_post_body_fields_map_to_engine_kwargs_with_defaults():
    client, spy = _client(SpySearch())
    r = client.post("/api/v1/search", json={"query": "resort Nha Trang", "priceMax": 2000000, "starRatingMin": 4.5})
    assert r.status_code == 200
    _, kw = spy.calls[0]
    assert kw["price_max"] == 2000000 and kw["price_min"] is None and kw["star_min"] == 4.5
    assert kw["origin"] is None and kw["available_only"] is True and (kw["limit"], kw["offset"]) == (20, 0)


def test_price_range_inverted_is_400_validation_error():
    client, spy = _client(SpySearch())
    r = client.post("/api/v1/search", json={"query": "resort", "priceMin": 5000000, "priceMax": 1000000})
    assert r.status_code == 400 and r.json()["error"]["code"] == "VALIDATION_ERROR" and spy.calls == []


def test_empty_query_reports_configured_cutoff_not_hardcoded():
    client, _ = _client(SpySearch())
    r = client.get("/api/v1/search", params={"q": ""})
    assert r.status_code == 200 and r.json()["cutoff"] == 0.52 and r.json()["results"] == []
    no_engine, _ = _client(None)
    assert no_engine.get("/api/v1/search", params={"q": "resort"}).json()["cutoff"] == 0.62
