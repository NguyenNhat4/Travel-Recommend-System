"""Route /search (contract 1.15.0, 1.16.0 travelContext.guests + log tìm kiếm ở cuối file): GET và POST chuyển đủ tham số lọc tường minh xuống engine (trước 06/10 route bỏ qua
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


# --- contract 1.16.0: travelContext.guests (POST) và log tìm kiếm (SEARCH_LOG_QUERIES) ----------------------------------
from src.backend.app.application.auth.errors import TokenInvalid  # noqa: E402
from src.backend.app.application.auth.principal import AuthPrincipal  # noqa: E402


def test_post_travel_context_guests_reach_the_engine_only_when_present():
    client, spy = _client(SpySearch())
    r = client.post("/api/v1/search", json={"query": "resort", "travelContext": {
        "checkIn": "2026-10-10", "checkOut": "2026-10-12", "guests": {"adults": 2, "children": 1}, "rooms": 1}})
    assert r.status_code == 200
    _, kw = spy.calls[-1]
    assert kw["adults"] == 2 and kw["children"] == 1
    client.post("/api/v1/search", json={"query": "resort", "travelContext": {"guests": {"adults": 3}}})
    assert spy.calls[-1][1]["adults"] == 3 and "children" not in spy.calls[-1][1]
    for body in ({"query": "resort"}, {"query": "resort", "travelContext": None},
                 {"query": "resort", "travelContext": {"checkIn": "2026-10-10"}}, {"query": "resort", "travelContext": {"guests": {}}}):
        client.post("/api/v1/search", json=body)
        assert "adults" not in spy.calls[-1][1] and "children" not in spy.calls[-1][1], body


def test_post_guests_out_of_contract_range_is_rejected_before_the_engine():
    client, spy = _client(SpySearch())
    assert client.post("/api/v1/search", json={"query": "resort", "travelContext": {"guests": {"adults": 0}}}).status_code != 200
    assert client.post("/api/v1/search", json={"query": "resort", "travelContext": {"guests": {"children": -1}}}).status_code != 200
    assert spy.calls == []


class FakeRecorder:
    def __init__(self, fail=False):
        self.entries, self.fail = [], fail

    def record(self, entry):
        if self.fail:
            raise RuntimeError("queue broken")
        self.entries.append(entry)
        return True


class FakeVerifier:
    def verify(self, token):
        if token != "good":
            raise TokenInvalid("bad token")
        return AuthPrincipal(user_id="u1", cdp_user_id="cdp-1", email="a@example.vn", session_id="sid-1")


def _logged_client(recorder, *, verifier=None, search=None):
    client, spy = _client(search or SpySearch())
    client.app.state.search_log = recorder
    client.app.state.token_verifier = verifier
    return client, spy


def test_search_is_logged_only_when_enabled_first_page_and_real_query():
    rec = FakeRecorder()
    client, _ = _logged_client(rec)
    assert client.get("/api/v1/search", params={"q": " resort Nha Trang ", "taxonomy": "hotel"}).status_code == 200
    (entry,) = rec.entries
    assert entry.query == "resort Nha Trang" and entry.filters == {"taxonomy": "hotel"} and entry.model_version == "x"
    assert entry.cdp_user_id is None and entry.latency_ms is not None
    client.get("/api/v1/search", params={"q": "resort", "offset": 20})        # đổi trang không ghi thêm
    client.get("/api/v1/search", params={"q": ""})                            # câu rỗng không phải lượt tìm
    client.post("/api/v1/search", json={"query": "resort", "priceMin": 5, "priceMax": 1})   # 400
    assert len(rec.entries) == 1
    client.post("/api/v1/search", json={"query": "villa", "destination": "Phú Quốc"})
    assert rec.entries[-1].query == "villa" and rec.entries[-1].filters == {"destination": "Phú Quốc"}
    no_engine, _ = _logged_client(rec, search=None)
    no_engine.app.state.search = None
    no_engine.get("/api/v1/search", params={"q": "resort"})
    assert len(rec.entries) == 2
    off, _ = _client(SpySearch())                                             # tắt: app.state.search_log vắng
    assert off.get("/api/v1/search", params={"q": "resort"}, headers={"Authorization": "Bearer junk"}).status_code == 200


def test_log_identity_from_valid_bearer_and_never_401_on_bad_token():
    rec = FakeRecorder()
    client, _ = _logged_client(rec, verifier=FakeVerifier())
    assert client.get("/api/v1/search", params={"q": "resort"}, headers={"Authorization": "Bearer good"}).status_code == 200
    assert (rec.entries[-1].cdp_user_id, rec.entries[-1].session_id) == ("cdp-1", "sid-1")
    for header in ("Bearer bad", "Basic abc", "Bearer "):
        r = client.get("/api/v1/search", params={"q": "resort"}, headers={"Authorization": header})
        assert r.status_code == 200 and rec.entries[-1].cdp_user_id is None, header


def test_log_failure_never_reaches_the_response():
    client, _ = _logged_client(FakeRecorder(fail=True))
    r = client.get("/api/v1/search", params={"q": "resort"})
    assert r.status_code == 200 and r.json()["results"] == []


def test_get_query_constraints_still_validated_and_route_callable_directly():
    client, spy = _client(SpySearch())
    for bad in ({"q": "x", "limit": 0}, {"q": "x", "limit": 51}, {"q": "x", "offset": -1}, {"q": "x", "priceMin": -1},
                {"q": "x", "starRatingMin": 6}):
        assert client.get("/api/v1/search", params=bad).status_code != 200, bad
    assert spy.calls == []
    # gọi thẳng hàm route (test agent dựng backend giả): mặc định là giá trị thật, không phải đối tượng Query
    body = search_routes.search(q="resort", search_products=spy)
    assert body["results"] == [] and spy.calls[-1][1] == {
        "taxonomy": None, "destination": None, "origin": None, "price_min": None, "price_max": None, "star_min": None,
        "available_only": True, "limit": 20, "offset": 0}
