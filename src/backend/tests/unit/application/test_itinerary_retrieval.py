"""retrieval.hydrate/collect với kết quả Similar ở lượt đổi món (FR-AGT-05, itinerary spec §2.5)."""
import asyncio
from datetime import date

from src.backend.app.application.itinerary.retrieval import DETAIL_FIELDS, collect, hydrate, nearest_open_date

INTENT = {"destination": "Nha Trang", "days": 2}


def product(product_id, destination="Nha Trang", **updates):
    return {"productId": product_id, "name": f"Catalog {product_id}", "taxonomy": "hotel",
            "destination": destination, "unitPrice": 1000000, "currency": "VND", "priceUnit": "PER_NIGHT",
            "available": True, "score": 0.8, "description": "Source text", "attributes": {},
            "availableFrom": None, "availableTo": None, **updates}


def similar_result(*products):
    return {"tool_call_id": "call-0", "name": "get_similar_products",
            "data": {"productId": "H0", "strategy": "same_taxonomy", "results": list(products), "requestId": "r"}}


def search_result(*products):
    return {"tool_call_id": "call-1", "name": "search_products",
            "data": {"results": list(products), "total": len(products)}}


def test_off_destination_similar_results_are_skipped_silently():
    # Similar không lọc điểm đến; sản phẩm nơi khác không phải "bị loại" nên không thành cảnh báo, kể cả khi
    # nó nằm trong exclude_products.
    results = [similar_result(product("H1", destination="Đà Nẵng"), product("H2"),
                              product("H3", destination="Phú Quốc"))]
    candidates, sources, dropped = collect(results, {}, INTENT, {"exclude_products": ["H3"]})
    assert list(candidates) == ["H2"]
    assert sources == {"H2": "search"}
    assert dropped == {}


def test_same_destination_similar_results_become_search_candidates():
    results = [similar_result(product("H2"), product("H3", destination=" nha  TRANG "))]
    candidates, sources, dropped = collect(results, {}, INTENT, {})
    assert sources == {"H2": "search", "H3": "search"}  # ItemSource.SEARCH, không có nguồn riêng cho Similar
    assert candidates["H2"]["name"] == "Catalog H2"
    assert dropped == {}


def test_similar_results_still_obey_the_other_drop_rules():
    results = [similar_result(product("H2"), product("H3", available=False), product("H4"))]
    candidates, _, dropped = collect(results, {}, INTENT, {"exclude_products": ["H2"]})
    assert dropped == {"H2": "PRODUCT_DROPPED_EXCLUDED", "H3": "PRODUCT_DROPPED_UNAVAILABLE"}
    assert list(candidates) == ["H4"]


def test_off_destination_search_results_are_still_reported():
    _, _, dropped = collect([search_result(product("H1", destination="Đà Nẵng"))], {}, INTENT, {})
    assert dropped == {"H1": "PRODUCT_DROPPED_DESTINATION"}


def test_similar_projection_without_detail_fields_is_hydrated_then_collected():
    class Catalog:
        def __init__(self):
            self.calls = []

        async def get_product_detail(self, product_id):
            self.calls.append(product_id)
            return product(product_id)

    partial = {key: value for key, value in product("H5").items() if key not in DETAIL_FIELDS}
    results = [similar_result(partial, product("H6"))]
    catalog = Catalog()
    details, errors = asyncio.run(hydrate(results, catalog, {}, 1))
    assert catalog.calls == ["H5"]  # H6 đã đủ trường chi tiết
    assert errors == {}
    candidates, sources, _ = collect(results, details, INTENT, {})
    assert candidates["H5"]["description"] == "Source text"
    assert sources == {"H5": "search", "H6": "search"}


TODAY = date(2026, 9, 29)


def dated_intent(start):
    return {**INTENT, "startDate": start}


def test_nearest_open_date_is_the_first_open_day_when_the_trip_starts_too_early():
    results = [search_result(product("H1", availableFrom="2026-10-10", availableTo="2026-10-24"))]
    assert nearest_open_date(results, {}, dated_intent("2026-10-01"), {}, TODAY) == "2026-10-10"


def test_nearest_open_date_is_the_last_open_day_when_the_trip_starts_too_late():
    results = [search_result(product("H1", availableFrom="2026-09-24", availableTo="2026-10-24"))]
    assert nearest_open_date(results, {}, dated_intent("2026-12-01"), {}, TODAY) == "2026-10-24"


def test_nearest_open_date_never_suggests_a_past_day_or_a_closed_window():
    open_window = search_result(product("H1", availableFrom="2026-09-01", availableTo="2026-10-24"))
    assert nearest_open_date([open_window], {}, dated_intent("2026-08-01"), {}, TODAY) == "2026-09-29"
    closed_window = search_result(product("H2", availableFrom="2026-08-01", availableTo="2026-09-10"))
    assert nearest_open_date([closed_window], {}, dated_intent("2026-12-01"), {}, TODAY) is None


def test_nearest_open_date_picks_the_window_closest_to_the_requested_day():
    results = [search_result(product("H1", availableFrom="2026-10-01", availableTo="2026-10-05"),
                             product("H2", availableFrom="2026-10-20", availableTo="2026-10-24"))]
    assert nearest_open_date(results, {}, dated_intent("2026-10-15"), {}, TODAY) == "2026-10-20"


def test_nearest_open_date_ignores_products_dropped_for_other_reasons_and_needs_a_start_date():
    window = {"availableFrom": "2026-10-10", "availableTo": "2026-10-24"}
    results = [search_result(product("H1", destination="Đà Nẵng", **window), product("H2", available=False, **window))]
    assert nearest_open_date(results, {}, dated_intent("2026-10-01"), {}, TODAY) is None
    results = [search_result(product("H3", **window))]
    assert nearest_open_date(results, {}, INTENT, {}, TODAY) is None
