"""retrieval.hydrate/collect với kết quả Similar ở lượt đổi món (FR-AGT-05, itinerary spec §2.5)."""
import asyncio

from src.backend.app.application.itinerary.retrieval import DETAIL_FIELDS, collect, hydrate

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
