import json
from pathlib import Path

from fastapi.testclient import TestClient

MOCKS = Path(__file__).resolve().parents[3] / "shared/mocks/cdp-clone"


def fixture(name):
    return json.loads((MOCKS / name).read_text())


def test_backend_records_behaviour_then_reads_it(client):
    response = client.post("/cdp/v1/events", json=fixture("backend-browse-events.request.json"))
    assert response.status_code == 201, response.text
    assert [r["status"] for r in response.json()["results"]] == ["created"] * 3

    listed = client.get("/cdp/v1/users/VP0092381/events").json()
    assert listed["total"] == 3
    assert [e["eventName"] for e in listed["events"]] == ["add_to_cart", "product_view", "search"]
    assert listed["events"][2]["timestamp"] == "2026-09-16T10:05:12Z"


def test_resending_same_event_is_idempotent(client):
    body = fixture("backend-purchase.request.json")
    assert client.post("/cdp/v1/events", json=body).json()["results"][0]["status"] == "created"
    second = client.post("/cdp/v1/events", json=body)
    assert second.status_code == 201
    assert second.json()["results"][0]["status"] == "duplicate"
    assert client.get("/cdp/v1/users/VP0092381/events").json()["total"] == 1


def test_cancelled_purchase_is_hidden_by_default_and_stays_cancelled(client):
    body = fixture("backend-purchase.request.json")
    client.post("/cdp/v1/events", json=body)

    first = client.put("/cdp/v1/users/VP0092381/events/purchase:bi-01/cancellation")
    assert first.status_code == 200, first.text
    assert first.json()["cancelledAt"] is not None
    again = client.put("/cdp/v1/users/VP0092381/events/purchase:bi-01/cancellation")
    assert again.json()["cancelledAt"] == first.json()["cancelledAt"]

    assert client.get("/cdp/v1/users/VP0092381/events").json()["total"] == 0
    all_events = client.get("/cdp/v1/users/VP0092381/events", params={"includeCancelled": "true"}).json()
    assert [e["eventId"] for e in all_events["events"]] == ["purchase:bi-01"]

    # Re-sending the same eventId must not resurrect it.
    assert client.post("/cdp/v1/events", json=body).json()["results"][0]["status"] == "duplicate"
    assert client.get("/cdp/v1/users/VP0092381/events").json()["total"] == 0


def test_cancel_unknown_event_or_other_users_event_returns_404(client):
    client.post("/cdp/v1/events", json=fixture("backend-purchase.request.json"))
    assert client.put("/cdp/v1/users/VP0092381/events/nope/cancellation").status_code == 404
    response = client.put("/cdp/v1/users/VP999/events/purchase:bi-01/cancellation")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_invalid_event_in_batch_writes_nothing(client):
    body = {"events": [{"cdpUserId": "VP1", "eventName": "search", "searchQuery": "Hội An"},
                       {"cdpUserId": "VP1", "eventName": "search"}]}
    response = client.post("/cdp/v1/events", json=body)
    assert response.status_code == 400
    assert response.json()["error"]["details"] == {"eventIndex": 1, "fields": ["searchQuery"]}
    assert client.get("/cdp/v1/users/VP1/events").json()["total"] == 0


def test_schema_errors_use_error_envelope_and_echo_request_id(client):
    response = client.post("/cdp/v1/events", json={"events": [{"eventName": "search", "searchQuery": "x"}]},
                           headers={"X-Request-ID": "req-123"})
    body = response.json()
    assert response.status_code == 400
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert "events.0.cdpUserId" in body["error"]["details"]["fields"]
    assert body["error"]["requestId"] == "req-123" == response.headers["X-Request-ID"]


def test_every_endpoint_requires_service_token(engine, client):
    anonymous = TestClient(client.app, raise_server_exceptions=False)
    calls = [
        ("post", "/cdp/v1/events", {"json": {"events": []}}),
        ("get", "/cdp/v1/users/VP1/events", {}),
        ("put", "/cdp/v1/users/VP1/events/e1/cancellation", {}),
        ("get", "/cdp/v1/profiles/VP1", {}),
        ("put", "/cdp/v1/profiles/VP1", {"json": {}}),
    ]
    for headers in ({}, {"X-Service-Token": "wrong"}, {"Authorization": "Bearer something"}):
        for method, url, kwargs in calls:
            response = getattr(anonymous, method)(url, headers=headers, **kwargs)
            assert (response.status_code, response.json()["error"]["code"]) == (401, "INVALID_TOKEN"), (url, headers)


def test_no_cors_for_browsers(client):
    response = client.options("/cdp/v1/events", headers={
        "Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST"})
    assert "access-control-allow-origin" not in response.headers


def test_event_filters_and_order(client):
    events = [
        {"cdpUserId": "VP1", "eventName": "search", "searchQuery": q, "timestamp": ts}
        for q, ts in [("a", "2026-01-01T00:00:00Z"), ("b", "2026-03-01T07:00:00+07:00"), ("c", "2026-06-01T00:00:00Z")]
    ]
    client.post("/cdp/v1/events", json={"events": events})
    response = client.get("/cdp/v1/users/VP1/events", params={"since": "2026-02-01T00:00:00Z", "limit": 1}).json()
    assert response["total"] == 2
    assert [e["searchQuery"] for e in response["events"]] == ["c"]
    older = client.get("/cdp/v1/users/VP1/events", params={"until": "2026-06-01T00:00:00Z"}).json()
    assert [e["searchQuery"] for e in older["events"]] == ["b", "a"]
    assert older["events"][0]["timestamp"] == "2026-03-01T00:00:00Z"


def test_profile_upsert_and_read(client):
    attributes = fixture("profile.200.json")["attributes"]
    assert client.get("/cdp/v1/profiles/VP0092381").status_code == 404

    saved = client.put("/cdp/v1/profiles/VP0092381", json=attributes)
    assert saved.status_code == 200, saved.text
    assert saved.json()["attributes"] == attributes

    replaced = client.put("/cdp/v1/profiles/VP0092381", json={"lifecycleStage": "dormant"})
    assert replaced.json()["attributes"]["homeCity"] is None
    read = client.get("/cdp/v1/profiles/VP0092381").json()
    assert read["attributes"]["lifecycleStage"] == "dormant"
    assert read["attributes"]["purchasedVerticals"] == []
