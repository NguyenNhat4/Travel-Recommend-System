"""Use case gợi ý tức thì trên index của conftest (11 dòng, có một route vé máy bay và một dòng không ticketed)."""
from src.backend.app.application.search import SuggestProducts


def test_suggests_destinations_then_products_by_taxonomy(services):
    result = SuggestProducts(services["index"])("nha", limit=10)
    assert result["query"] == "nha"
    first = result["suggestions"][0]
    assert first == {"type": "destination", "label": "Nha Trang", "productCount": first["productCount"]}
    assert first["productCount"] > 0
    products = [s for s in result["suggestions"] if s["type"] == "product"]
    assert products and all(set(s) == {"type", "label", "productId", "taxonomy", "destination"} for s in products)
    order = ["hotel", "attraction", "golf", "combo"]
    assert [s["taxonomy"] for s in products] == sorted((s["taxonomy"] for s in products), key=order.index)


def test_flights_and_child_units_are_never_suggested(services):
    suggest = SuggestProducts(services["index"])
    ids = {s.get("productId") for q in ("ve may bay", "ha noi", "vinpearl", "deluxe")
           for s in suggest(q, limit=10)["suggestions"]}
    assert not ids & {"F1", "FL1", "R1", "R3"}   # route, chuyến bay, hạng phòng
    assert "H1" in ids


def test_unavailable_units_are_skipped(services):
    index = services["index"]
    position = index.idx["G1"]
    saved = bool(index.available[position])
    index.available[position] = False
    try:
        labels = [s["label"] for s in SuggestProducts(index)("golf")["suggestions"]]
    finally:
        index.available[position] = saved
    assert "Vinpearl Golf Nha Trang" not in labels


def test_popularity_breaks_ties_within_a_group(services):
    by_default = [s["productId"] for s in SuggestProducts(services["index"])("nha trang", limit=10)["suggestions"]
                  if s.get("taxonomy") == "hotel"]
    boosted = [s["productId"] for s in SuggestProducts(services["index"], {"H2": 5.0})("nha trang", limit=10)["suggestions"]
               if s.get("taxonomy") == "hotel"]
    assert set(by_default) == set(boosted) == {"H1", "H2"} and boosted[0] == "H2"


def test_short_or_blank_query_returns_nothing_and_whitespace_is_collapsed(services):
    suggest = SuggestProducts(services["index"])
    assert suggest("n") == {"query": "n", "suggestions": []}
    assert suggest("   ") == {"query": "", "suggestions": []}
    assert suggest("  nha    trang ")["query"] == "nha trang"


def test_limit_is_clamped_and_results_are_cached_per_folded_query(services, monkeypatch):
    from src.backend.app.application.search import suggest as module

    calls = []
    real = module.suggest
    monkeypatch.setattr(module, "suggest", lambda entries, q, limit: calls.append((q, limit)) or real(entries, q, limit))
    suggest = SuggestProducts(services["index"], cache_size=2)
    first = suggest("Nha Trang", limit=99)
    assert len(first["suggestions"]) <= 10 and calls == [("Nha Trang", 10)]
    again = suggest("nha  trang", limit=10)          # khác hoa thường và khoảng trắng, cùng khoá đã fold
    assert again["suggestions"] == first["suggestions"] and len(calls) == 1
    again["suggestions"][0]["label"] = "đã sửa"       # người gọi sửa kết quả không làm bẩn bộ đệm
    assert suggest("nha trang", limit=10)["suggestions"][0]["label"] != "đã sửa"
    suggest("vin"); suggest("golf")                   # vượt cache_size: mục cũ nhất bị loại
    suggest("nha trang", limit=10)
    assert len(calls) == 4
