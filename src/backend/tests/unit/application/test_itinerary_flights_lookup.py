"""Tra chuyến bay cho chặng bay của lịch trình (`application/itinerary/flights.py`, AC-AGT-02) qua `list_products`."""
import asyncio

from src.backend.app.application.itinerary.flights import canonical_city, flight_options
from src.backend.app.application.ports.itinerary_tools import ToolError

INTENT = {"destination": "Nha Trang", "origin": "Sài Gòn", "startDate": "2026-10-15", "days": 3,
          "party": {"type": "COUPLE", "adults": 2, "children": 0}}


def route(pid, destination, origin):
    return {"productId": pid, "name": f"Vé máy bay {origin} - {destination}", "taxonomy": "flight",
            "destination": destination, "attributes": {"level": "route", "originCity": origin}}


def child(pid, parent, destination):
    return {"productId": pid, "taxonomy": "flight", "destination": destination,
            "attributes": {"level": "flight", "parentProductId": parent}}


class Catalog:
    supports_catalog = True

    def __init__(self, products, error=None):
        self.products, self.error, self.calls = products, error, []

    async def list_products(self, params):
        self.calls.append(params)
        if self.error:
            raise self.error
        parent = params.get("parentProductId")
        rows = [p for p in self.products
                if (p["attributes"].get("parentProductId") == parent if parent
                    else p["attributes"]["level"] == "route" and p["destination"] == params.get("destination"))]
        page = rows[params["offset"]:params["offset"] + params["limit"]]
        return {"results": page, "total": len(rows), "limit": params["limit"], "offset": params["offset"]}


def run(catalog, intent=INTENT, constraints=None):
    return asyncio.run(flight_options(catalog, intent, constraints or {}, 1))


def test_alias_is_resolved_and_both_directions_are_looked_up():
    catalog = Catalog([route("out", "Nha Trang", "TP. Hồ Chí Minh"), route("other", "Nha Trang", "Hà Nội"),
                       route("back", "TP. Hồ Chí Minh", "Nha Trang"),
                       child("o1", "out", "Nha Trang"), child("b1", "back", "TP. Hồ Chí Minh")])
    result = run(catalog)
    assert canonical_city("Sài Gòn") == "TP. Hồ Chí Minh"
    assert result["status"] is None and result["origin"] == "TP. Hồ Chí Minh"
    assert [p["productId"] for p in result["outbound"]] == ["o1"]
    assert [p["productId"] for p in result["return"]] == ["b1"]
    assert {"parentProductId": "out", "availableOnly": True, "limit": 50, "offset": 0} in catalog.calls


def test_children_are_read_page_by_page():
    flights = [child(f"o{i}", "out", "Nha Trang") for i in range(60)]
    result = run(Catalog([route("out", "Nha Trang", "TP. Hồ Chí Minh"), *flights]))
    assert len(result["outbound"]) == 60 and result["return"] == []


def test_no_route_between_the_two_cities():
    assert run(Catalog([route("other", "Nha Trang", "Hà Nội")])) == {"status": "NO_ROUTE", "origin": "TP. Hồ Chí Minh"}


def test_lookup_failure_only_loses_the_flights():
    assert run(Catalog([], error=ToolError("SEARCH_UNAVAILABLE", retryable=True))) == {"status": "UNAVAILABLE"}
    assert asyncio.run(flight_options(None, INTENT, {}, 1)) == {"status": "UNAVAILABLE"}


def test_nothing_is_looked_up_when_flights_are_not_needed():
    catalog = Catalog([])
    assert run(catalog, {**INTENT, "origin": None}) == {"status": "NO_ORIGIN"}
    assert run(catalog, constraints={"exclude_taxonomies": ["flight"]}) == {"status": "EXCLUDED"}
    assert run(catalog, {**INTENT, "days": 1}) == {"status": "DAY_TRIP"}
    assert catalog.calls == []
