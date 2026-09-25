import pytest

from src.backend.app.domain.catalog import ListingItem, Product, filter_items, sort_items, summarize_variants


def product(pid, price=100_000, *, taxonomy="attraction", destination="Nha Trang", available=True, **attrs):
    return Product(product_id=pid, name=pid, taxonomy=taxonomy, destination=destination, description="",
                   attributes=attrs, unit_price=price, available=available)


def ids(items):
    return [i.product.product_id for i in items]


def test_rating_is_review_score_scaled_to_five():
    assert product("a", reviewScore=8.4, reviewScoreScale=10).rating == 4.2
    assert product("a", reviewScore=9, reviewScoreScale=0).rating is None
    assert product("a", reviewScore=9).rating is None  # thiếu thang điểm → null, không đoán


def test_review_count_and_occupancy_ignore_non_numbers():
    assert product("a", reviewCount=1206).review_count == 1206
    assert product("a", reviewCount="nhiều").review_count is None
    assert product("a", maxOccupancy=0).max_occupancy is None


def test_only_property_and_route_have_variants():
    assert product("h", level="property").has_variants
    assert product("f", level="route").has_variants
    assert not product("r", level="room").has_variants
    assert not product("a").has_variants


def test_variant_summary_counts_all_children_but_prices_only_open_ones():
    summary = summarize_variants([
        product("r1", 2_000_000, maxOccupancy=2),
        product("r2", 3_500_000, maxOccupancy=4),
        product("r3", 900_000, available=False),
        product("r4", None),
    ])
    assert (summary.count, summary.min_price, summary.max_price, summary.max_occupancy) == (4, 2_000_000, 3_500_000, 4)


def test_variant_summary_of_no_children():
    summary = summarize_variants([])
    assert (summary.count, summary.min_price, summary.max_price, summary.max_occupancy) == (0, None, None, None)


def test_filter_by_destination_taxonomy_and_availability():
    items = [ListingItem(product("a1")), ListingItem(product("a2", destination="Đà Nẵng")),
             ListingItem(product("g1", taxonomy="golf")), ListingItem(product("a3", available=False))]
    assert ids(filter_items(items, destination="Nha Trang", taxonomy="attraction", available_only=True)) == ["a1"]
    assert ids(filter_items(items)) == ["a1", "a2", "g1", "a3"]


def test_price_sorts_put_unpriced_last_both_ways():
    items = [ListingItem(product("free", None)), ListingItem(product("cheap", 1)), ListingItem(product("dear", 9))]
    assert ids(sort_items(items, "price_asc")) == ["cheap", "dear", "free"]
    assert ids(sort_items(items, "price_desc")) == ["dear", "cheap", "free"]


def test_popular_ranks_purchases_then_recommendable_then_priced():
    items = [ListingItem(product("plain")), ListingItem(product("display"), False),
             ListingItem(product("hit")), ListingItem(product("unpriced", None))]
    order = ids(sort_items(items, "popular", {"hit": 1.0}))
    assert order[0] == "hit"
    assert order.index("plain") < order.index("unpriced") < order.index("display")


def test_variants_have_no_popularity_so_popular_means_cheapest_first():
    items = [ListingItem(product("suite", 5)), ListingItem(product("deluxe", 2))]
    assert ids(sort_items(items, "popular", {"suite": 1.0}, variants=True)) == ["deluxe", "suite"]


def test_unknown_sort_is_rejected():
    with pytest.raises(ValueError):
        sort_items([], "newest")
