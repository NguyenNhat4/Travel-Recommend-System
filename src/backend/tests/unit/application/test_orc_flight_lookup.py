"""lookup_flights (AC-AGT-08): dữ kiện cả đợt của một tuyến một chiều; không soạn câu trả lời, không tự chọn vé."""
import asyncio
from datetime import datetime
from time import monotonic

from src.backend.app.application.itinerary.orc_dispatch import VIETNAM, OrcToolDispatcher, SourceBudget
from src.backend.app.application.itinerary.product_registry import ProductRegistry
from src.backend.tests.fakes.orc_tools import FakeTools, call, product

NOW = datetime(2026, 10, 20, 10, 0, tzinfo=VIETNAM)


def flight(pid, day, clock, price, **attributes):
    """Dạng chuyến bay của catalog thật: ngày giờ ở departureAt (+07:00), availableFrom = ngày bay."""
    return {**product(pid, "flight", destination="Hà Nội", price=price, departureAt=f"{day}T{clock}:00+07:00",
                      originCity="TP. Hồ Chí Minh", destinationCity="Hà Nội", **attributes),
            "availableFrom": day, "availableTo": day}


ROUTE = product("route", "flight", destination="Hà Nội", price=None, originCity="TP. Hồ Chí Minh")
FLIGHTS = [flight("today-early", "2026-10-20", "06:00", 500_000), flight("a", "2026-10-21", "07:00", 1_200_000),
           flight("b", "2026-10-21", "19:00", 900_000), flight("c", "2026-10-24", "08:30", 2_000_000),
           flight("sim", "2026-10-22", "10:00", 300_000, simulated=True)]


def lookup(flights=FLIGHTS, failures=0, **args):
    tools = FakeTools(listing={"Hà Nội": [ROUTE], "route": flights}, failures=failures)
    d = OrcToolDispatcher(tools, ProductRegistry(), SourceBudget(deadline=monotonic() + 30), timeout_seconds=1,
                          now=lambda: NOW)
    result = asyncio.run(d.run(call("lookup_flights", **args)))
    return result, d, tools


def test_missing_origin_asks_for_input_without_any_request():
    result, _, tools = lookup(destination="Hà Nội")
    assert result["status"] == "needs_input" and result["data"] == {"missing": ["origin"]} and tools.calls == []


def test_period_statistics_cover_every_future_real_fare():
    result, d, _ = lookup(origin="sg", destination="Hà Nội")
    period = result["data"]["period"]
    assert period["from"] == "2026-10-21" and period["to"] == "2026-10-24" and period["flights"] == 3
    assert period["days_without_flights"] == ["2026-10-22", "2026-10-23"]
    assert period["cheapest_price_vnd"] == 900_000 and period["priciest_price_vnd"] == 2_000_000
    assert d.registry.product(period["cheapest_ref"])["productId"] == "b"
    assert [d.registry.identify(ref) for ref in result["refs"]] == ["b", "a", "c"]
    assert result["data"]["simulated_prices"] is False


def test_specific_day_without_flights_reports_nearest_days_and_time_window_fallback():
    result, _, _ = lookup(origin="TP. Hồ Chí Minh", destination="Hà Nội", date="2026-10-23")
    assert result["status"] == "empty" and result["data"]["nearest_dates_with_flights"] == ["2026-10-24",
                                                                                              "2026-10-21"]
    early, d, _ = lookup(origin="TP. Hồ Chí Minh", destination="Hà Nội", time_of_day="early")
    assert early["data"]["time_of_day_matched"] is True
    assert [d.registry.identify(ref) for ref in early["refs"]] == ["a", "c"]
    none, _, _ = lookup(flights=FLIGHTS[1:3], origin="TP. Hồ Chí Minh", destination="Hà Nội", time_of_day="afternoon")
    assert none["data"]["time_of_day_matched"] is False and len(none["refs"]) == 2


def test_simulated_fares_only_when_no_real_fare_remains():
    result, d, _ = lookup(flights=[FLIGHTS[4]], origin="TP. Hồ Chí Minh", destination="Hà Nội")
    assert result["data"]["simulated_prices"] is True and [d.registry.identify(r) for r in result["refs"]] == ["sim"]


def test_unknown_route_is_empty_and_source_failure_is_an_error():
    result, _, _ = lookup(origin="Đà Lạt", destination="Hà Nội")
    assert result["status"] == "empty" and result["data"]["route_found"] is False
    failed, _, _ = lookup(failures=5, origin="TP. Hồ Chí Minh", destination="Hà Nội")
    assert failed["status"] == "error" and failed["refs"] == []
