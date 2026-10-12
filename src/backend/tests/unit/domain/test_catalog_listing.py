from collections import Counter

import pytest

from src.backend.app.domain.catalog import (
    DIVERSIFY_GROUPS,
    TAXONOMIES,
    ListingItem,
    Product,
    filter_items,
    interleave_by_taxonomy,
    sort_items,
    summarize_variants,
)


def product(pid, price=100_000, *, taxonomy="attraction", destination="Nha Trang", available=True, **attrs):
    return Product(product_id=pid, name=pid, taxonomy=taxonomy, destination=destination, description="",
                   attributes=attrs, unit_price=price, available=available)


def ids(items):
    return [i.product.product_id for i in items]


def test_rating_is_review_score_scaled_to_five():
    assert product("a", reviewScore=8.4, reviewScoreScale=10).rating == 4.2
    assert product("a", reviewScore=9, reviewScoreScale=0).rating is None
    assert product("a", reviewScore=9).rating is None  # thiếu thang điểm → null, không đoán


def test_rating_falls_back_to_tripadvisor_then_the_attraction_rating_in_schema_order():
    # schema.md §8.1: reviewScore trước, rồi tripAdvisorRating (thang 5), rồi rating/ratingScale của điểm tham quan.
    hotel = product("h", reviewScore=8.5, reviewScoreScale=10, reviewCount=1016,
                    tripAdvisorRating=4.7, tripAdvisorReviewCount=1941)
    assert (hotel.rating, hotel.review_count) == (4.2, 1016)
    tripadvisor_only = product("t", tripAdvisorRating=4.7, tripAdvisorReviewCount=1941)
    assert (tripadvisor_only.rating, tripadvisor_only.review_count) == (4.7, 1941)
    attraction = product("a", rating=4.6, ratingScale=5, reviewCount=44)
    assert (attraction.rating, attraction.review_count) == (4.6, 44)


def test_review_count_belongs_to_the_rating_and_ignores_non_numbers():
    assert product("a", reviewScore=8, reviewScoreScale=10, reviewCount=1206).review_count == 1206
    assert product("a", reviewScore=8, reviewScoreScale=10, reviewCount="nhiều").review_count is None
    # Có số lượt mà không có điểm → cả hai null (hop-dong-tich-hop-backend.md §2.2).
    assert product("a", reviewCount=1206).review_count is None
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


# --- diversify=taxonomy (contract 1.25.0) ----------------------------------------------------

TAX = {"h": "hotel", "a": "attraction", "g": "golf", "c": "combo", "f": "flight", "x": "cruise"}


def items_of(*pids):
    """`h1` là khách sạn, `a1` vé tham quan, `g1` golf, `c1` combo, `f1` tuyến bay; `x1` là loại ngoài bảng nhóm."""
    return [ListingItem(product(pid, taxonomy=TAX[pid[0]])) for pid in pids]


def test_filter_accepts_several_taxonomies():
    items = items_of("h1", "a1", "g1", "c1")
    assert ids(filter_items(items, taxonomy={"attraction", "golf"})) == ["a1", "g1"]
    assert ids(filter_items(items, taxonomy=["golf"])) == ["g1"]


def test_diversify_groups_cover_every_taxonomy_once():
    members = [t for _, group in DIVERSIFY_GROUPS for t in group]
    assert sorted(members) == sorted(TAXONOMIES) and len(members) == len(set(members))
    assert [name for name, _ in DIVERSIFY_GROUPS] == ["hotel", "experience", "combo", "flight"]


def test_interleave_round_robins_groups_in_fixed_order():
    # Đầu vào đã xếp popular: vé bay đứng đầu như kệ Phổ biến trên prod.
    ordered = items_of("f1", "f2", "f3", "c1", "g1", "h1", "a1", "h2", "c2", "f4")
    assert ids(interleave_by_taxonomy(ordered)) == ["h1", "g1", "c1", "f1", "h2", "a1", "c2", "f2", "f3", "f4"]


def test_interleave_puts_golf_in_the_attraction_group():
    assert ids(interleave_by_taxonomy(items_of("g1", "g2", "a1", "c1", "c2"))) == ["g1", "c1", "g2", "c2", "a1"]


def test_interleave_is_a_permutation_keeping_order_inside_groups():
    ordered = items_of("f1", "h1", "a1", "f2", "g1", "c1", "h2", "a2", "c2", "f3", "h3")
    mixed = interleave_by_taxonomy(ordered)
    assert Counter(ids(mixed)) == Counter(ids(ordered))
    for _, group in DIVERSIFY_GROUPS:
        inside = lambda xs: [i for i in ids(xs) if TAX[i[0]] in group]  # noqa: E731
        assert inside(mixed) == inside(ordered)


def test_interleave_of_one_group_is_identity():
    ordered = items_of("a2", "g1", "a1", "g2")
    assert ids(interleave_by_taxonomy(ordered)) == ids(ordered)


def test_interleave_keeps_unknown_taxonomy_last():
    assert ids(interleave_by_taxonomy(items_of("x1", "h1", "x2", "f1"))) == ["h1", "f1", "x1", "x2"]
