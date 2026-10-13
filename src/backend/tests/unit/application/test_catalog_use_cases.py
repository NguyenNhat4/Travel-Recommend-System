"""GET /products, /products/{id}, /products/{id}/similar ở tầng use case (backend §4, search-recommendation §3.6)."""
import asyncio

import pytest

from src.backend.app.application.catalog.errors import (
    CatalogUnavailable,
    InvalidCatalogRequest,
    ProductNotFound,
    ProductNotIndexed,
)
from src.backend.app.application.catalog.use_cases import GetProductDetail, GetSimilarProducts, ListProducts
from src.backend.app.application.search import SimilarProducts
from src.backend.app.domain.catalog import ListingItem
from src.backend.tests.conftest import ROWS, P
from src.backend.tests.fakes.catalog import InMemoryProductQuery

# Hạng phòng thứ hai của H1, rẻ hơn R1, và một hạng phòng hết chỗ.
ROWS_WITH_ROOMS = ROWS + [
    P("R1b", "Vinpearl Resort Nha Trang - Standard", "hotel", "Nha Trang",
      {"level": "room", "parentProductId": "H1", "maxOccupancy": 2}, price=2_100_000),
    P("R1c", "Vinpearl Resort Nha Trang - Suite", "hotel", "Nha Trang",
      {"level": "room", "parentProductId": "H1", "maxOccupancy": 4}, price=8_000_000, avail=False),
    P("X1", "Phòng chưa gắn cha", "hotel", "Nha Trang", {"level": "room"}, price=1_000_000),
]


def run(coro):
    return asyncio.run(coro)


@pytest.fixture
def products():
    return InMemoryProductQuery(ROWS_WITH_ROOMS)


def ids(page):
    return [r["productId"] for r in page["results"]]


# --- chi tiết ---------------------------------------------------------------------------------

def test_property_detail_summarises_its_rooms(products):
    detail = run(GetProductDetail(products)("H1"))
    assert detail["variantSummary"] == {"count": 3, "minPrice": 2_100_000, "maxPrice": 3_400_000, "maxOccupancy": 4}
    assert detail["description"] and detail["priceUnit"] == "UNKNOWN" and detail["unitPrice"] is None


def test_room_and_attraction_detail_have_no_variant_summary(products):
    assert run(GetProductDetail(products)("R1"))["variantSummary"] is None
    ticket = run(GetProductDetail(products)("A1"))
    assert ticket["variantSummary"] is None and ticket["unitPrice"] == 880000 and ticket["priceUnit"] == "PER_PERSON"


def test_detail_strips_false_attributes(products):
    assert "ticketed" not in run(GetProductDetail(products)("A2"))["attributes"]


def test_unknown_product_is_404_with_product_id(products):
    with pytest.raises(ProductNotFound) as err:
        run(GetProductDetail(products)("khong-co"))
    assert err.value.details == {"productId": "khong-co"}


# --- danh sách --------------------------------------------------------------------------------

def test_without_parent_lists_only_search_units(products):
    page = run(ListProducts(products)(limit=50))
    assert not {"R1", "R1b", "R3", "FL1", "X1"} & set(ids(page))
    assert set(ids(page)) == {"H1", "H2", "H3", "F1", "A1", "A2", "C1", "G1"} and page["total"] == 8
    assert products.search_unit_calls == 1  # RecSys tắt → đọc database


def test_units_from_recsys_are_used_without_touching_the_database(products):
    units = [ListingItem(products.by_id["A1"]), ListingItem(products.by_id["G1"])]
    page = run(ListProducts(products, units)())
    assert ids(page) == ["A1", "G1"] and products.search_unit_calls == 0


def test_popular_follows_purchases(products):
    page = run(ListProducts(products, popularity={"C1": 1.0, "G1": 0.5})(limit=3))
    assert ids(page)[:2] == ["C1", "G1"]


def test_parent_lists_its_rooms_cheapest_first(products):
    page = run(ListProducts(products)(parent_product_id="H1"))
    assert ids(page) == ["R1b", "R1", "R1c"]
    assert run(ListProducts(products)(parent_product_id="H1", available_only=True))["total"] == 2


def test_parent_without_children_or_unknown_is_empty(products):
    assert run(ListProducts(products)(parent_product_id="H2"))["results"] == []
    assert run(ListProducts(products)(parent_product_id="khong-co"))["total"] == 0


def test_filters_and_pagination(products):
    listing = ListProducts(products)
    nha_trang_hotels = run(listing(destination="Nha Trang", taxonomy="hotel"))
    assert set(ids(nha_trang_hotels)) == {"H1", "H2"}
    first, second = run(listing(sort="price_asc", limit=2)), run(listing(sort="price_asc", limit=2, offset=2))
    assert first["total"] == second["total"] and not set(ids(first)) & set(ids(second))


@pytest.mark.parametrize("kwargs, field", [
    ({"sort": "newest"}, "sort"), ({"taxonomy": "cruise"}, "taxonomy"),
    ({"limit": 0}, "limit"), ({"limit": 51}, "limit"), ({"offset": -1}, "offset"),
    ({"taxonomy": ["attraction", "cruise"]}, "taxonomy"), ({"taxonomy": ["attraction", ""]}, "taxonomy"),
    ({"taxonomy": []}, "taxonomy"),
    ({"diversify": "random"}, "diversify"), ({"diversify": ""}, "diversify"),
    ({"diversify": "taxonomy", "sort": "price_asc"}, "diversify"),
    ({"diversify": "taxonomy", "parent_product_id": "H1"}, "diversify"),
])
def test_invalid_listing_arguments_are_validation_errors(products, kwargs, field):
    with pytest.raises(InvalidCatalogRequest) as err:
        run(ListProducts(products)(**kwargs))
    assert err.value.details == {"fields": [field]}


def test_unknown_sort_with_diversify_reports_both_fields(products):
    with pytest.raises(InvalidCatalogRequest) as err:
        run(ListProducts(products)(sort="newest", diversify="taxonomy"))
    assert err.value.details == {"fields": ["sort", "diversify"]}


# --- nhiều taxonomy và diversify=taxonomy (contract 1.27.0) -----------------------------------

def test_several_taxonomies_filter_as_union_and_ignore_duplicates(products):
    page = run(ListProducts(products)(taxonomy=["attraction", "golf", "golf"], limit=50))
    assert set(ids(page)) == {"A1", "A2", "G1"} and page["total"] == 3


# Popular xếp vé bay đầu, như kệ Phổ biến trên prod; A2 không có lượt mua nên đứng cuối.
POPULARITY = {"F1": 1.0, "C1": 0.9, "G1": 0.8, "A1": 0.7, "H3": 0.6, "H1": 0.5, "H2": 0.4}


def test_diversify_interleaves_groups_before_paging(products):
    listing = ListProducts(products, popularity=POPULARITY)
    full = run(listing(diversify="taxonomy", limit=50))
    assert ids(full) == ["H3", "G1", "C1", "F1", "H1", "A1", "H2", "A2"] and full["total"] == 8
    first, second = run(listing(diversify="taxonomy", limit=4)), run(listing(diversify="taxonomy", limit=4, offset=4))
    assert ids(first) + ids(second) == ids(full) and first["total"] == second["total"] == 8


def test_diversify_with_one_group_keeps_popular_order(products):
    listing = ListProducts(products, popularity=POPULARITY)
    plain = run(listing(taxonomy=["attraction", "golf"], limit=50))
    assert ids(run(listing(taxonomy=["attraction", "golf"], diversify="taxonomy", limit=50))) == ids(plain)
    assert ids(plain) == ["G1", "A1", "A2"]


# --- tương tự ---------------------------------------------------------------------------------

def similar_use_case(services, products):
    return GetSimilarProducts(products, SimilarProducts(services["index"], services["vectors"]))


def test_similar_of_a_room_resolves_to_its_property(services, products):
    result = run(similar_use_case(services, products)("R1", limit=5))
    assert (result["productId"], result["resolvedFrom"], result["strategy"]) == ("H1", "R1", "same_taxonomy")
    assert "H1" not in {r["productId"] for r in result["results"]}
    assert {r["taxonomy"] for r in result["results"]} <= {"hotel"}


def test_similar_of_a_search_unit_has_no_resolved_from(services, products):
    result = run(similar_use_case(services, products)("A1"))
    assert result["productId"] == "A1" and result["resolvedFrom"] is None


def test_similar_unknown_is_404_and_unindexed_is_409(services, products):
    use_case = similar_use_case(services, products)
    with pytest.raises(ProductNotFound):
        run(use_case("khong-co"))
    with pytest.raises(ProductNotIndexed) as err:
        run(use_case("X1"))  # có trong catalog, không phải search unit, không có cha
    assert err.value.details == {"productId": "X1", "taxonomy": "hotel"}


def test_similar_without_vector_is_409(services, products):
    class NoVectors:
        def vectors(self, ids):
            return {}

    use_case = GetSimilarProducts(products, SimilarProducts(services["index"], NoVectors()))
    with pytest.raises(ProductNotIndexed):
        run(use_case("A1"))


def test_similar_when_recsys_is_down_is_retryable_503(products):
    with pytest.raises(CatalogUnavailable) as err:
        run(GetSimilarProducts(products, None)("A1"))
    assert err.value.retryable and err.value.http_status == 503


def test_similar_limit_is_bounded(services, products):
    with pytest.raises(InvalidCatalogRequest):
        run(similar_use_case(services, products)("A1", limit=21))
