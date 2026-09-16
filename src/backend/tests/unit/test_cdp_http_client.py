import asyncio
import json
from datetime import date, datetime, timezone
from pathlib import Path

import httpx
import pytest

from src.backend.app.application.ports.cdp_client import BrowseEvent, CdpUnavailableError, PurchaseEvent
from src.backend.app.core import request_context
from src.backend.app.infrastructure.clients.cdp_http_client import CdpHttpClient

MOCKS = Path(__file__).resolve().parents[3] / "shared/mocks/cdp-clone"
TOKEN = "service-token-for-tests"


def purchase(item: str) -> PurchaseEvent:
    return PurchaseEvent(
        booking_item_id=item, cdp_user_id="VP0092381", product_id="5febedf3-74ba-5200-a5ec-2a6ab5162acb",
        taxonomy="attraction", event_group_id="OFF20260916001", quantity=2, unit_price=1050000,
        using_date=date(2026, 10, 3), timestamp=datetime(2026, 9, 16, 10, 22, tzinfo=timezone.utc),
    )


def run(handler, call, request_id=None):
    async def main():
        token = request_context._request_id.set(request_id)
        try:
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://cdp") as http:
                return await call(CdpHttpClient(http, TOKEN))
        finally:
            request_context._request_id.reset(token)
    return asyncio.run(main())


def created(request):
    events = json.loads(request.content)["events"]
    return httpx.Response(201, json={"results": [{"eventId": e["eventId"], "status": "created"} for e in events]})


def test_record_purchases_sends_idempotent_events_in_chunks_with_request_id():
    requests = []

    def handler(request):
        requests.append(request)
        return created(request)

    run(handler, lambda cdp: cdp.record_purchases([purchase(f"bi-{i}") for i in range(150)]), request_id="req-1")

    assert [len(json.loads(r.content)["events"]) for r in requests] == [100, 50]
    assert all(r.headers["X-Service-Token"] == TOKEN and r.headers["X-Request-ID"] == "req-1" for r in requests)
    first = json.loads(requests[0].content)["events"][0]
    expected = json.loads((MOCKS / "backend-purchase.request.json").read_text())["events"][0]
    assert first == dict(expected, eventId="purchase:bi-0", timestamp="2026-09-16T10:22:00+00:00")


def test_browse_events_use_explicit_request_id_and_omit_nulls():
    requests = []

    def handler(request):
        requests.append(request)
        return created(request)

    event = BrowseEvent(event_id="search:1", cdp_user_id="VP1", event_name="search",
                        timestamp=datetime(2026, 9, 16, tzinfo=timezone.utc), search_query="Nha Trang")
    run(handler, lambda cdp: cdp.record_browse_events([event], request_id="req-queued"), request_id="req-other")

    assert requests[0].headers["X-Request-ID"] == "req-queued"
    assert json.loads(requests[0].content)["events"] == [{
        "eventId": "search:1", "cdpUserId": "VP1", "eventName": "search",
        "timestamp": "2026-09-16T00:00:00+00:00", "searchQuery": "Nha Trang"}]


@pytest.mark.parametrize("handler", [
    lambda request: httpx.Response(503, json={}),
    lambda request: (_ for _ in ()).throw(httpx.ConnectTimeout("timeout")),
])
def test_record_purchases_raises_when_cdp_does_not_confirm(handler):
    with pytest.raises(CdpUnavailableError):
        run(handler, lambda cdp: cdp.record_purchases([purchase("bi-1")]))


def test_cancel_purchases_puts_cancellation_and_accepts_missing_event():
    seen = []

    def handler(request):
        seen.append((request.method, request.url.raw_path.decode()))
        return httpx.Response(404 if "bi-2" in request.url.raw_path.decode() else 200, json={})

    run(handler, lambda cdp: cdp.cancel_purchases([purchase("bi-1"), purchase("bi-2")]))
    assert seen == [
        ("PUT", "/cdp/v1/users/VP0092381/events/purchase%3Abi-1/cancellation"),
        ("PUT", "/cdp/v1/users/VP0092381/events/purchase%3Abi-2/cancellation"),
    ]
    with pytest.raises(CdpUnavailableError):
        run(lambda request: httpx.Response(500, json={}), lambda cdp: cdp.cancel_purchases([purchase("bi-1")]))


def test_list_events_follows_pages_until_total():
    fixture = json.loads((MOCKS / "user-events.200.json").read_text())
    seen = []

    def handler(request):
        offset = int(request.url.params["offset"])
        seen.append((offset, request.url.params["limit"]))
        page = fixture["events"][offset:offset + 1]
        return httpx.Response(200, json={"events": page, "total": 2, "limit": 1, "offset": offset})

    events = run(handler, lambda cdp: cdp.list_events("VP0092381"))

    assert [offset for offset, _ in seen] == [0, 1]
    assert [e.event_name for e in events] == ["purchase", "search"]
    assert events[0].using_date == date(2026, 10, 3)


def test_list_events_stops_at_max_events():
    event = json.loads((MOCKS / "user-events.200.json").read_text())["events"][0]
    limits = []

    def handler(request):
        limit = int(request.url.params["limit"])
        limits.append(limit)
        return httpx.Response(200, json={"events": [event] * limit, "total": 10_000, "limit": limit, "offset": 0})

    events = run(handler, lambda cdp: cdp.list_events("VP1", max_events=700))
    assert len(events) == 700
    assert limits == [500, 200]


def test_get_profile_maps_fields_and_missing_profile():
    fixture = json.loads((MOCKS / "profile.200.json").read_text())

    def handler(request):
        if request.url.path.endswith("/VP404"):
            return httpx.Response(404, json={})
        return httpx.Response(200, json=fixture)

    profile = run(handler, lambda cdp: cdp.get_profile("VP0092381"))
    assert profile.purchased_verticals == ("hotel", "attraction")
    assert profile.gdpr_optin is True
    assert run(handler, lambda cdp: cdp.get_profile("VP404")) is None
