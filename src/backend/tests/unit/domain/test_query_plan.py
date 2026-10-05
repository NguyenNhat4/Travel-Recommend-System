"""`build_query_plan` (domain/search/query_plan.py): ghép parser F3–F6 với luật điểm đến F1 — param thắng câu, cờ tắt chỉ khai,
không đổi text BM25; thuần, không catalog."""
from src.backend.app.domain.search import (
    APPLIED_MUST_NOT,
    APPLIED_PRICE,
    APPLIED_ROUTE,
    APPLIED_STAR,
    APPLIED_TAXONOMY,
    PlanFlags,
    PlanGazetteers,
    PlanParams,
    QueryNormalizer,
    build_query_plan,
)

NORM = QueryNormalizer(destinations=["Nha Trang", "Phú Quốc", "Hà Nội", "Đà Nẵng"], names=[], spelling=False)
ALL_ON = PlanFlags(destination=True, negation=True, taxonomy=True, route=True, numeric=True)
ALL_OFF = PlanFlags()


def plan(q, flags=ALL_ON, **params):
    return build_query_plan(NORM(q), q, PlanParams(**params), flags, PlanGazetteers(iata={"HAN": "Hà Nội", "DAD": "Đà Nẵng"}))


def test_flags_off_only_declares_and_keeps_lexical_text():
    q = "khách sạn 4 sao Nha Trang không có hồ bơi dưới 2 triệu"
    p = plan(q, ALL_OFF)
    assert p.applied == () and p.lexical_text == NORM(q).text and p.mask_kwargs(destination=None) == \
        {"taxonomy": None, "destination": None, "only_available": True}
    d = p.as_diagnostics()
    assert d["mustNot"] == {"amenities": ["pool"], "brands": []}
    assert d["price"] == {"min": None, "max": 2000000, "source": "query"} and d["star"] == {"min": 4.0, "source": "query"}
    assert d["taxonomy"]["value"] == "hotel" and d["taxonomy"]["source"] == "query"
    assert "applied" not in d and "lexicalText" not in d
    assert p.applied_filters() is None


def test_flags_on_apply_and_strip_consumed_phrases_from_lexical_text():
    p = plan("khách sạn 4 sao Nha Trang không có hồ bơi dưới 2 triệu")
    assert set(p.applied) == {APPLIED_TAXONOMY, APPLIED_MUST_NOT, APPLIED_PRICE, APPLIED_STAR}
    kw = p.mask_kwargs(destination=p.destination.value)
    assert kw["taxonomy"] == "hotel" and kw["destination"] == "Nha Trang" and kw["price_max"] == 2000000
    assert kw["star_min"] == 4.0 and set(kw["exclude_amenities"]) == {"pool"}
    for gone in ("hồ bơi", "4 sao", "dưới 2 triệu", "khách sạn"):
        assert gone not in p.lexical_text
    assert "Nha Trang" in p.lexical_text
    af = p.applied_filters()
    assert af["hard"]["taxonomy"] == "hotel" and af["hard"]["taxonomySource"] == "query"
    assert af["hard"]["mustNotAmenities"] == ["pool"] and af["hard"]["priceMax"] == 2000000
    assert af["soft"] == {"starRatingMin": 4.0, "starRatingSource": "query"}


def test_request_params_always_win_and_apply_even_when_flags_off():
    p = plan("resort 5 sao dưới 1 triệu", ALL_OFF, taxonomy="golf", price_max=3000000, star_min=3)
    assert p.taxonomy == "golf" and p.taxonomy_source == "param" and p.mask_taxonomy == "golf"
    assert (p.price_max, p.price_source, p.star_min, p.star_source) == (3000000, "param", 3, "param")
    kw = p.mask_kwargs(destination=None)
    assert kw["taxonomy"] == "golf" and kw["price_max"] == 3000000 and kw["star_min"] == 3
    assert p.applied == ()                                       # không có họ suy từ câu nào áp
    hard = p.applied_filters()["hard"]
    assert hard == {"taxonomy": "golf", "priceMax": 3000000, "priceSource": "param"}   # param: không có taxonomySource


def test_cross_vertical_sentence_is_not_filtered_by_taxonomy():
    p = plan("khách sạn, vé máy bay và vé tham quan ở Nha Trang")
    assert p.taxonomy is None and p.taxonomy_skipped == "multi" and APPLIED_TAXONOMY not in p.applied
    assert set(p.taxonomy_candidates) >= {"hotel", "flight"}


def test_flight_roles_set_route_and_destination():
    p = plan("vé máy bay từ Hà Nội đến Nha Trang")
    assert (p.route_origin, p.route_destination, p.route_direction, p.route_source) == ("Hà Nội", "Nha Trang", "explicit", "query")
    assert APPLIED_ROUTE in p.applied and p.mask_origin == "Hà Nội"
    assert p.destination.value == "Nha Trang" and p.destination.source == "query"    # đích tuyến thay luật "skipped=flight"
    off = plan("vé máy bay từ Hà Nội đến Nha Trang", ALL_OFF)
    assert off.route_source == "query" and off.mask_origin is None and off.destination.value is None


def test_origin_param_wins_and_is_ignored_outside_flight_context():
    p = plan("Nha Trang", taxonomy="flight", origin="Đà Nẵng")
    assert p.mask_origin == "Đà Nẵng" and p.route_source == "param" and p.applied_filters()["hard"]["origin"] == "Đà Nẵng"
    p2 = plan("resort Nha Trang", origin="Hà Nội")
    assert p2.mask_origin is None and p2.ignored == ("origin",) and p2.route_skipped == "not_flight"
    assert p2.as_diagnostics()["ignored"] == ["origin"] and p2.as_diagnostics()["route"]["skipped"] == "not_flight"


def test_iata_codes_resolve_through_gazetteer():
    p = plan("vé máy bay HAN DAD")
    assert (p.route_origin, p.route_destination) == ("Hà Nội", "Đà Nẵng")


def test_without_normalizer_only_params_apply():
    p = build_query_plan(None, "khách sạn không có hồ bơi", PlanParams(taxonomy="hotel"), ALL_ON)
    assert p.taxonomy == "hotel" and p.applied == () and p.must_not_amenities == () and p.lexical_text == "khách sạn không có hồ bơi"


def test_families_in_order_follow_filter_pipeline():
    p = plan("khách sạn 4 sao Nha Trang không có hồ bơi dưới 2 triệu")
    assert [f for f, _ in p.families_in_order()] == [APPLIED_TAXONOMY, APPLIED_PRICE, APPLIED_STAR, APPLIED_MUST_NOT]


def test_brand_negation_is_filtered_with_amenities():
    p = plan("khách sạn Nha Trang không phải Vinpearl")
    assert p.must_not_brands == ("Vinpearl",) and APPLIED_MUST_NOT in p.applied
    assert p.mask_kwargs(destination=None)["exclude_brands"] == ("Vinpearl",)
    assert p.applied_filters()["hard"]["mustNotBrands"] == ["Vinpearl"] and "mustNotAmenities" not in p.applied_filters()["hard"]


def test_soft_negation_phrase_leaves_lexical_text_when_flag_on_only():
    q = "resort Nha Trang không nhất thiết phải có hồ bơi"
    on, off = plan(q), plan(q, ALL_OFF)
    assert on.must_not_amenities == () and APPLIED_MUST_NOT not in on.applied and "hồ bơi" not in on.lexical_text
    assert off.lexical_text == NORM(q).text and on.soft_dropped
