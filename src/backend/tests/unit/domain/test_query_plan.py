"""`build_query_plan` (domain/search/query_plan.py): ghép parser F3–F6 với luật điểm đến F1 — param thắng câu, cờ tắt chỉ khai,
không đổi text BM25; thuần, không catalog."""
import pytest

from src.backend.app.domain.search.lexical import fold

from src.backend.app.domain.search import (
    APPLIED_DURATION,
    APPLIED_ENTITY,
    APPLIED_MUST_NOT,
    APPLIED_PARTY,
    APPLIED_PRICE,
    APPLIED_ROUTE,
    APPLIED_STAR,
    APPLIED_TAXONOMY,
    ROLE_GATE,
    ROLE_LOCATION,
    PlanFlags,
    PlanGazetteers,
    PlanParams,
    QueryNormalizer,
    build_query_plan,
    place_table,
)

NORM = QueryNormalizer(destinations=["Nha Trang", "Phú Quốc", "Hà Nội", "Đà Nẵng"], names=[], spelling=False)
ALL_ON = PlanFlags(destination=True, negation=True, taxonomy=True, route=True, numeric=True)
ALL_OFF = PlanFlags()
#: ALL_ON + ba cờ 1.18.0 (duration / poi / entity) — các test "cờ mới không đổi confidence" so với ALL_ON.
ALL_ON118 = PlanFlags(destination=True, negation=True, taxonomy=True, route=True, numeric=True,
                      duration=True, poi=True, entity=True)
V118_KEYS = {"duration", "entity", "location"}


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


# ------------------------------------------------------------------------------------------------ mặc định ≡ hôm nay
NEW_FEATURE_QUERIES = [
    "vé lẻ VinWonders Nha Trang, không lấy combo",
    "combo Phú Quốc không gồm vé máy bay",
    "combo vé máy bay và khách sạn Đà Nẵng",
    "nơi ở Pleiku cho nhóm 4 người",
    "khách sạn 4 sao dưới 2 triệu cho 3 người",
    "khu nghỉ dưỡng Phú Quốc",
    "khách sạn, vé máy bay và vé tham quan ở Nha Trang",
    # 1.18.0: ba câu gốc của spec tong-hop-chinh-sua-luong-search-ota — cờ tắt thì KHÔNG parse duration / POI / entity
    "VinWonders 3 ngày 2 đêm",
    "khách sạn gần Hồ Hoàn Kiếm",
    "vé Safari Phú Quốc",
]


@pytest.mark.parametrize("q", NEW_FEATURE_QUERIES)
def test_default_flags_keep_mask_lexical_text_and_diagnostics_shape(q):
    p = plan(q, ALL_OFF)
    assert p.applied == () and p.lexical_text == NORM(q).text and p.applied_filters() is None
    assert p.mask_kwargs(destination=None) == {"taxonomy": None, "destination": None, "only_available": True}
    assert p.families_in_order() == ()
    d = p.as_diagnostics()                                 # khối 1.15.0: không khoá mới khi chưa bật `extended`
    assert not ({"party", "confidence", "fallbackReasons"} | V118_KEYS) & set(d)
    assert set(d.get("mustNot", {})) <= {"amenities", "brands"} and "strength" not in d.get("taxonomy", {})


@pytest.mark.parametrize("q", NEW_FEATURE_QUERIES)
def test_v118_families_are_not_parsed_when_their_flags_are_off(q):
    """Khác F1/F3–F6 (tắt vẫn parse để khai): duration / poi / entity tắt thì trường ở mặc định, không khai kể cả `extended`."""
    for flags in (ALL_OFF, ALL_ON):
        p = plan(q, flags)
        assert (p.duration_days, p.duration_nights, p.duration_source) == (None, None, None)
        assert p.entity_keys == () and p.entity_role is None and p.location is None and p.poi_destinations == ()
        assert not p.destination_via_poi
        assert not V118_KEYS & set(p.as_diagnostics(extended=True))
        kw = p.mask_kwargs(destination=p.destination.value)
        assert "require_entities" not in kw and APPLIED_ENTITY not in dict(p.families_in_order())
        hard = (p.applied_filters() or {}).get("hard", {})
        assert "entity" not in hard and hard.get("destinationSource") != "poi"


# ------------------------------------------------------------------------------------------------ 1.18.0 — F7 thời lượng
def test_duration_only_behind_flag_and_only_touches_lexical_text():
    q = "VinWonders 3 ngày 2 đêm"
    off = plan(q, ALL_OFF)
    assert off.duration_source is None and "3 ngày 2 đêm" in off.lexical_text
    assert "duration" not in off.as_diagnostics(extended=True)
    on = plan(q, PlanFlags(duration=True))
    assert (on.duration_days, on.duration_nights, on.duration_source) == (3, 2, "query")
    assert on.applied == (APPLIED_DURATION,) and on.lexical_text == "VinWonders"
    d = on.as_diagnostics(extended=True)
    assert d["duration"] == {"days": 3, "nights": 2, "source": "query"}
    assert d["lexicalText"] == "VinWonders" and d["applied"] == ["duration"]
    assert on.as_diagnostics()["duration"] == d["duration"]          # khối 1.18.0 khai khi cờ bật, không cần `extended`
    # không vào mask, không có bước họ → câu chỉ có thời lượng KHÔNG có appliedFilters (emptyReason=duration không bao giờ phát)
    assert on.applied_filters() is None
    assert on.mask_kwargs(destination=None) == {"taxonomy": None, "destination": None, "only_available": True}
    assert on.families_in_order() == ()


def test_duration_composes_with_other_families_without_entering_mask():
    p = plan("khách sạn Nha Trang 2 đêm", PlanFlags(duration=True, taxonomy=True, destination=True))
    assert (p.duration_days, p.duration_nights) == (None, 2) and p.applied == (APPLIED_DURATION, APPLIED_TAXONOMY)
    assert p.lexical_text == "Nha Trang" and p.destination.value == "Nha Trang"
    assert [f for f, _ in p.families_in_order()] == [APPLIED_TAXONOMY]
    hard = p.applied_filters()["hard"]
    assert hard == {"taxonomy": "hotel", "taxonomySource": "query", "destination": "Nha Trang", "destinationSource": "query"}
    assert p.mask_kwargs(destination="Nha Trang") == {"taxonomy": "hotel", "destination": "Nha Trang", "only_available": True}


def test_duration_ignores_numbers_already_taken_by_price():
    p = plan("resort 2 triệu/đêm Phú Quốc", PlanFlags(duration=True, numeric=True))   # "/đêm" nằm trong span giá (không mốc)
    assert p.duration_source is None and APPLIED_DURATION not in p.applied and "duration" not in p.as_diagnostics(extended=True)
    assert "unresolved_constraint" in p.fallback_reasons and "2 triệu/đêm" in p.lexical_text
    q = plan("resort dưới 2 triệu/đêm Phú Quốc", PlanFlags(duration=True, numeric=True))
    assert q.duration_source is None and q.price_max == 2_000_000 and q.applied == (APPLIED_PRICE,)


# ------------------------------------------------------------------------------------------------ 1.18.0 — entity gate / location
ENTITY_ON = PlanFlags(entity=True)


@pytest.mark.parametrize("q, keys", [
    ("VinWonders 3 ngày 2 đêm", ("vinwonders",)),          # câu chỉ nêu entity (cue yếu attraction)
    ("combo VinWonders Phú Quốc", ("vinwonders",)),        # cue combo → vẫn gate
    ("Grand World Phú Quốc", ("grand_world",)),            # entity trần
    ("vé Safari Phú Quốc", ("safari",)),
])
def test_entity_role_gate_enters_mask_and_applied_filters(q, keys):
    p = plan(q, ENTITY_ON)
    assert p.entity_keys == keys and p.entity_role == ROLE_GATE and p.applied == (APPLIED_ENTITY,)
    assert p.taxonomy in (None, "attraction", "combo")
    assert p.mask_kwargs(destination=None)["require_entities"] == keys
    assert p.families_in_order() == ((APPLIED_ENTITY, {"require_entities": keys}),)
    assert p.applied_filters() == {"hard": {"entity": list(keys)}, "soft": {}}
    assert p.as_diagnostics()["entity"] == {"keys": list(keys), "role": "gate"}
    assert p.lexical_text == NORM(q).text                   # cụm entity là tên sản phẩm → không tiêu khỏi câu BM25


@pytest.mark.parametrize("q, keys", [
    ("khách sạn ở Grand World Phú Quốc", ("grand_world",)),   # c0697: cue hotel mạnh
    ("phòng gần Grand World", ("grand_world",)),               # cue hotel YẾU vẫn là location (không bỏ phòng người dùng hỏi)
    ("khách sạn gần biển và vé VinWonders", ("vinwonders",)),  # ≥ 2 loại (multi)
])
def test_entity_role_location_only_declares(q, keys):
    p = plan(q, ENTITY_ON)
    assert p.entity_keys == keys and p.entity_role == ROLE_LOCATION and APPLIED_ENTITY not in p.applied
    assert "require_entities" not in p.mask_kwargs(destination=None) and p.families_in_order() == ()
    assert p.applied_filters() is None
    assert p.as_diagnostics()["entity"] == {"keys": list(keys), "role": "location"}


def test_entity_inside_negation_scope_is_skipped():
    p = plan("không lấy VinWonders, vé Safari", ENTITY_ON)
    assert p.entity_keys == ("safari",) and p.entity_role == ROLE_GATE
    assert p.mask_kwargs(destination=None)["require_entities"] == ("safari",)


def test_entity_gate_ands_with_must_not_taxonomy():
    """c0703 "vé lẻ VinWonders Nam Hội An, không lấy combo": gate vinwonders ∧ loại combo → còn attraction tên VinWonders."""
    p = plan("vé lẻ VinWonders Nam Hội An, không lấy combo", PlanFlags(entity=True, negation=True))
    assert p.entity_keys == ("vinwonders",) and p.entity_role == ROLE_GATE
    assert set(p.applied) == {APPLIED_MUST_NOT, APPLIED_ENTITY}
    kw = p.mask_kwargs(destination=None)
    assert kw["require_entities"] == ("vinwonders",) and kw["exclude_taxonomies"] == ("combo",)
    assert [f for f, _ in p.families_in_order()] == [APPLIED_ENTITY, APPLIED_MUST_NOT]
    hard = p.applied_filters()["hard"]
    assert hard["entity"] == ["vinwonders"] and hard["mustNotTaxonomies"] == ["combo"]
    assert "vinwonders" in fold(p.lexical_text) and "combo" not in p.lexical_text


def test_hotel_brand_is_not_an_entity():
    p = plan("khách sạn Vinpearl ở Nha Trang", ENTITY_ON)                                 # c0709
    assert p.entity_keys == () and p.entity_role is None and APPLIED_ENTITY not in p.applied
    assert "entity" not in p.as_diagnostics(extended=True) and p.applied_filters() is None


def test_entity_gate_ands_with_taxonomy_filter_when_f4_on():
    p = plan("vé VinWonders Nha Trang", PlanFlags(taxonomy=True, entity=True))
    assert p.applied == (APPLIED_TAXONOMY, APPLIED_ENTITY) and p.entity_role == ROLE_GATE
    kw = p.mask_kwargs(destination=None)
    assert kw["taxonomy"] == "attraction" and kw["require_entities"] == ("vinwonders",)
    assert [f for f, _ in p.families_in_order()] == [APPLIED_TAXONOMY, APPLIED_ENTITY]
    hard = p.applied_filters()["hard"]
    assert hard == {"taxonomy": "attraction", "taxonomySource": "query", "entity": ["vinwonders"]}


def test_entity_step_comes_right_after_query_taxonomy_step():
    p = plan("vé VinWonders Nha Trang dưới 1 triệu", ALL_ON118)
    fam = p.families_in_order()
    assert [f for f, _ in fam] == [APPLIED_TAXONOMY, APPLIED_ENTITY, APPLIED_PRICE]
    assert dict(fam)[APPLIED_ENTITY] == {"require_entities": ("vinwonders",)}
    # tham số taxonomy của request (tab Web) không đổi vai trò: vẫn gate, chỉ giao với mask; không có bước taxonomy (param)
    tab = plan("VinWonders Nha Trang", ALL_ON118, taxonomy="hotel")
    assert tab.entity_role == ROLE_GATE and APPLIED_ENTITY in tab.applied
    assert [f for f, _ in tab.families_in_order()] == [APPLIED_ENTITY]
    assert tab.mask_kwargs(destination=None)["taxonomy"] == "hotel"


def test_entity_table_restricted_to_catalog_disables_gate():
    gaz = PlanGazetteers(entities={}, places=place_table({"Nha Trang", "Phú Quốc"}))
    p = build_query_plan(NORM("vé VinWonders Nha Trang"), "vé VinWonders Nha Trang", PlanParams(), ALL_ON118, gaz)
    assert p.entity_keys == () and p.entity_role is None and APPLIED_ENTITY not in p.applied
    q = "khách sạn gần Hồ Hoàn Kiếm"                       # Hà Nội không có trong catalog → địa danh bị bỏ lúc dựng bảng
    r = build_query_plan(NORM(q), q, PlanParams(), ALL_ON118, gaz)
    assert r.location is None and r.destination.value is None and not r.destination_via_poi


# ------------------------------------------------------------------------------------------------ 1.18.0 — POI → điểm đến (F1)
POI_ON = PlanFlags(poi=True, destination=True)


def test_poi_resolves_to_catalog_destination_through_f1():
    p = plan("khách sạn gần Hồ Hoàn Kiếm", POI_ON)
    assert (p.destination.value, p.destination.source, p.destination.skipped) == ("Hà Nội", "query", None)
    assert p.destination.candidates == ("Hà Nội",) and p.poi_destinations == ("Hà Nội",) and p.destination_via_poi
    assert (p.location.key, p.location.name, p.location.kind, p.location.destination) == \
        ("ho_hoan_kiem", "Hồ Hoàn Kiếm", "landmark", "Hà Nội")
    assert p.applied_filters()["hard"] == {"destination": "Hà Nội", "destinationSource": "poi"}
    assert p.mask_kwargs(destination=p.destination.value)["destination"] == "Hà Nội"
    d = p.as_diagnostics()
    assert d["location"] == {"key": "ho_hoan_kiem", "name": "Hồ Hoàn Kiếm", "kind": "landmark", "destination": "Hà Nội"}
    assert "applied" not in d                                # POI không phải họ `applied`; đi qua F1 như địa danh thường
    assert "Hồ Hoàn Kiếm" in p.lexical_text and p.drop_tokens == frozenset(fold("Hà Nội").split())
    assert p.applied_filters(destination_fallback=True) is None     # FR-SRC-04: nới điểm đến thì không khai đã lọc


def test_poi_off_declares_nothing_even_with_destination_flag():
    p = plan("khách sạn gần Hồ Hoàn Kiếm", PlanFlags(destination=True))
    assert p.destination.value is None and p.location is None and p.poi_destinations == ()
    assert p.applied_filters() is None and "location" not in p.as_diagnostics(extended=True)


def test_poi_does_not_claim_a_destination_the_normalizer_already_found():
    p = plan("khách sạn Hà Nội gần Hồ Gươm", POI_ON)
    assert p.destination.value == "Hà Nội" and p.destination.source == "query"
    assert p.location is not None and p.location.key == "ho_hoan_kiem"
    assert p.poi_destinations == () and not p.destination_via_poi
    assert p.applied_filters()["hard"]["destinationSource"] == "query"


def test_two_pois_of_different_cities_skip_as_multi():
    for q in ("khách sạn gần Hồ Gươm hoặc Cầu Rồng", "khách sạn Hà Nội gần Cầu Rồng"):
        p = plan(q, POI_ON)
        assert p.destination.value is None and p.destination.skipped == "multi"
        assert set(p.destination.candidates) == {"Hà Nội", "Đà Nẵng"} and not p.destination_via_poi
        assert p.location is not None and p.applied_filters() is None
    assert plan("khách sạn gần Hồ Gươm hoặc Cầu Rồng", POI_ON).location.key == "ho_hoan_kiem"   # địa danh đầu tiên
    assert plan("khách sạn Hà Nội gần Cầu Rồng", POI_ON).location.key == "cau_rong"


def test_two_pois_of_the_same_city_resolve_to_it():
    p = plan("khách sạn gần Hồ Gươm hoặc Hồ Tây", POI_ON)
    assert p.destination.value == "Hà Nội" and p.poi_destinations == ("Hà Nội",) and p.destination_via_poi
    assert p.location.key == "ho_hoan_kiem" and p.applied_filters()["hard"]["destinationSource"] == "poi"


def test_route_destination_from_iata_is_not_marked_poi():
    gaz = PlanGazetteers(iata={"HAN": "Hà Nội", "DAD": "Đà Nẵng"}, flight_cities=("Hà Nội", "Đà Nẵng"))
    q = "vé máy bay HAN DAD"
    p = build_query_plan(NORM(q), q, PlanParams(), PlanFlags(destination=True, route=True, poi=True), gaz)
    assert (p.route_origin, p.route_destination) == ("Hà Nội", "Đà Nẵng") and APPLIED_ROUTE in p.applied
    assert p.destination.value == "Đà Nẵng" and p.destination.source == "query" and p.destination.candidates == ()
    assert p.poi_destinations == () and p.location is None and not p.destination_via_poi
    assert p.applied_filters()["hard"]["destinationSource"] == "query"


def test_poi_with_entity_in_one_sentence():
    p = plan("khách sạn ở Grand World Phú Quốc", ALL_ON118)                       # c0697: entity định vị, site → Phú Quốc
    assert p.entity_role == ROLE_LOCATION and p.destination.value == "Phú Quốc"
    assert not p.destination_via_poi                      # "Phú Quốc" do normalizer nhận, không phải POI
    assert p.applied_filters()["hard"]["destinationSource"] == "query"
    assert p.mask_kwargs(destination="Phú Quốc")["taxonomy"] == "hotel" and "require_entities" not in p.mask_kwargs(destination=None)


# ------------------------------------------------------------------------------------------------ 1.18.0 — không đổi router confidence
@pytest.mark.parametrize("q, params", [
    ("VinWonders 3 ngày 2 đêm", {}),
    ("khách sạn gần Hồ Hoàn Kiếm", {}),
    ("vé Safari Phú Quốc", {}),
    ("khách sạn gần biển và vé VinWonders", {}),
    ("không lấy VinWonders, vé Safari", {}),
    ("khách sạn gần Hồ Gươm hoặc Cầu Rồng", {}),
    ("khách sạn gần Hồ Hoàn Kiếm", {"destination": "Đà Nẵng"}),
    ("resort Nha Trang 3 ngày 2 đêm", {"taxonomy": "golf"}),
])
def test_v118_flags_do_not_change_confidence_or_fallback_reasons(q, params):
    base, on = plan(q, ALL_ON, **params), plan(q, ALL_ON118, **params)
    assert on.fallback_reasons == base.fallback_reasons and on.confidence == base.confidence
    assert on.taxonomy == base.taxonomy and on.taxonomy_skipped == base.taxonomy_skipped


# ------------------------------------------------------------------------------------------------ mustNot loại sản phẩm / thành phần
def test_must_not_taxonomy_joins_must_not_family():
    p = plan("vé lẻ VinWonders Nha Trang, không lấy combo")
    assert p.taxonomy == "attraction" and p.must_not_taxonomies == ("combo",) and p.must_not_flags == ()
    assert APPLIED_MUST_NOT in p.applied and "combo" not in p.lexical_text
    kw = p.mask_kwargs(destination=None)
    assert kw["exclude_taxonomies"] == ("combo",) and "exclude_flags" not in kw and kw["exclude_amenities"] == ()
    assert dict(p.families_in_order())[APPLIED_MUST_NOT] == {"exclude_amenities": (), "exclude_brands": (),
                                                            "exclude_taxonomies": ("combo",)}
    hard = p.applied_filters()["hard"]
    assert hard["mustNotTaxonomies"] == ["combo"] and "mustNotAmenities" not in hard and "mustNotFlags" not in hard
    assert p.as_diagnostics(extended=True)["mustNot"] == {"amenities": [], "brands": [], "taxonomies": ["combo"]}
    assert "mustNot" not in p.as_diagnostics()


def test_must_not_composition_flag_for_combo():
    p = plan("combo Phú Quốc không gồm vé máy bay")
    assert p.taxonomy == "combo" and p.must_not_flags == ("includesFlight",) and p.must_not_taxonomies == ()
    kw = p.mask_kwargs(destination=None)
    assert kw["exclude_flags"] == ("includesFlight",) and "exclude_taxonomies" not in kw
    assert p.applied_filters()["hard"]["mustNotFlags"] == ["includesFlight"]
    assert p.as_diagnostics(extended=True)["mustNot"] == {"amenities": [], "brands": [], "flags": ["includesFlight"]}


def test_amenity_only_negation_keeps_must_not_kwargs_unchanged():
    kw = plan("khách sạn Nha Trang không có hồ bơi").mask_kwargs(destination=None)
    assert kw["exclude_amenities"] == ("pool",) and kw["exclude_brands"] == ()
    assert "exclude_taxonomies" not in kw and "exclude_flags" not in kw and "min_occupancy" not in kw


def test_must_not_never_excludes_the_requested_taxonomy():
    p = plan("resort không phải khách sạn")                 # cả hai cue đều là hotel → không tự loại chính mình
    assert p.taxonomy == "hotel" and p.must_not_taxonomies == () and APPLIED_MUST_NOT not in p.applied
    assert "unresolved_constraint" in p.fallback_reasons
    q = plan("vé lẻ VinWonders Nha Trang", taxonomy="combo")  # tham số thắng: không loại combo
    assert q.mask_taxonomy == "combo" and q.must_not_taxonomies == ()


# ------------------------------------------------------------------------------------------------ số khách
def test_party_from_query_only_behind_flag():
    q = "nơi ở Pleiku cho nhóm 4 người"
    off = plan(q)                                            # ALL_ON không gồm cờ party
    assert (off.party_total, off.party_source) == (4, "query") and not off.party_active and APPLIED_PARTY not in off.applied
    assert "min_occupancy" not in off.mask_kwargs(destination=None) and "4 người" in off.lexical_text
    on = plan(q, PlanFlags(party=True))
    assert on.applied == (APPLIED_PARTY,) and on.mask_kwargs(destination=None)["min_occupancy"] == 4
    assert "4 người" not in on.lexical_text and "nhóm" in on.lexical_text
    assert on.applied_filters()["hard"] == {"minOccupancy": 4, "partySource": "query"}
    assert on.families_in_order() == ((APPLIED_PARTY, {"min_occupancy": 4}),)
    assert on.as_diagnostics(extended=True)["party"] == {"adults": None, "children": None, "total": 4, "source": "query"}


def test_party_params_always_win_and_apply():
    p = plan("nơi ở Pleiku cho nhóm 4 người", ALL_OFF, adults=2, children=1)
    assert (p.party_adults, p.party_children, p.party_total, p.party_source) == (2, 1, 3, "param")
    assert p.party_active and p.applied == () and p.mask_kwargs(destination=None)["min_occupancy"] == 3
    assert p.lexical_text == NORM("nơi ở Pleiku cho nhóm 4 người").text
    assert p.applied_filters()["hard"] == {"minOccupancy": 3, "partySource": "param"}
    only_children = plan("resort Nha Trang", ALL_OFF, children=2)       # không biết người lớn → không có tổng, không lọc
    assert only_children.party_total is None and not only_children.party_active


def test_party_with_price_and_star_does_not_mix_numbers():
    p = plan("khách sạn 4 sao dưới 2 triệu cho 3 người", PlanFlags(numeric=True, taxonomy=True, party=True))
    assert (p.star_min, p.price_max, p.party_total) == (4, 2_000_000, 3)
    assert [f for f, _ in p.families_in_order()] == [APPLIED_TAXONOMY, APPLIED_PRICE, APPLIED_STAR, APPLIED_PARTY]
    assert p.lexical_text == "cho"


# ------------------------------------------------------------------------------------------------ F4 chỉ cue mạnh
def test_taxonomy_strong_only_skips_weak_cues():
    strong_only = PlanFlags(taxonomy=True, taxonomy_strong_only=True)
    weak = plan("nghỉ dưỡng Phú Quốc", strong_only)
    assert weak.taxonomy == "hotel" and weak.taxonomy_strength == "weak" and weak.mask_taxonomy is None
    assert APPLIED_TAXONOMY not in weak.applied and weak.lexical_text == NORM("nghỉ dưỡng Phú Quốc").text
    assert weak.as_diagnostics(extended=True)["taxonomy"]["strength"] == "weak"
    strong = plan("resort Phú Quốc", strong_only)
    assert strong.mask_taxonomy == "hotel" and strong.taxonomy_strength == "strong" and APPLIED_TAXONOMY in strong.applied
    assert plan("nghỉ dưỡng Phú Quốc", PlanFlags(taxonomy=True)).mask_taxonomy == "hotel"       # cờ tắt: như cũ
    assert plan("resort Phú Quốc", taxonomy="golf").taxonomy_strength is None                      # param: không khai cue


def test_combo_head_is_one_taxonomy_and_keeps_components_in_lexical_text():
    p = plan("combo vé máy bay và khách sạn Đà Nẵng")
    assert p.mask_taxonomy == "combo" and p.taxonomy_skipped is None and p.taxonomy_candidates == ("combo", "flight", "hotel")
    assert "vé máy bay" in p.lexical_text and "khách sạn" in p.lexical_text and "combo" not in p.lexical_text


# ------------------------------------------------------------------------------------------------ router confidence
@pytest.mark.parametrize("q, params, reasons", [
    ("resort Nha Trang", {}, ()),
    ("resort Nha Trang", {"destination": "Nha Trang", "taxonomy": "hotel"}, ()),
    ("khách sạn không có view đẹp", {}, ("unresolved_constraint",)),
    ("khách sạn 2 triệu", {}, ("unresolved_constraint",)),
    ("vé máy bay Hà Nội Đà Nẵng Nha Trang", {}, ("ambiguous_route",)),
    ("khách sạn và vé máy bay Nha Trang", {}, ("multi_vertical",)),
    ("khách sạn, vé máy bay và vé tham quan ở Nha Trang", {}, ("multi_vertical", "long_multi_constraint")),   # 12 token
    ("nghỉ dưỡng Phú Quốc", {}, ("weak_taxonomy_cue",)),
    ("resort Nha Trang", {"destination": "Phú Quốc"}, ("param_conflict",)),
    ("resort Nha Trang", {"taxonomy": "golf"}, ("param_conflict",)),
    ("mình cần tìm khách sạn ở Nha Trang gần biển có hồ bơi cho cả gia đình đi chơi", {}, ("long_multi_constraint",)),
    ("khách sạn và vé máy bay Nha Trang", {"destination": "Phú Quốc"}, ("multi_vertical", "param_conflict")),
])
def test_router_confidence_reasons(q, params, reasons):
    p = plan(q, **params)
    assert p.fallback_reasons == reasons and p.confidence == round(1.0 - 0.25 * len(reasons), 2)


def test_confidence_diagnostics_only_when_block_exists():
    clean = plan("resort Nha Trang")
    assert clean.as_diagnostics(extended=True)["confidence"] == 1.0
    assert "fallbackReasons" not in clean.as_diagnostics(extended=True) and "confidence" not in clean.as_diagnostics()
    assert plan("gì cũng được").as_diagnostics(extended=True) == {}               # không parse ra gì → không có khối
    conflict = plan("Nha Trang", destination="Phú Quốc")                            # chỉ có tín hiệu router → vẫn khai
    assert conflict.as_diagnostics(extended=True) == {"confidence": 0.75, "fallbackReasons": ["param_conflict"]}
    assert conflict.as_diagnostics() == {}
    multi = plan("khách sạn và vé máy bay Nha Trang").as_diagnostics(extended=True)
    assert multi["confidence"] == 0.75 and multi["fallbackReasons"] == ["multi_vertical"]


# ------------------------------------------------------------------------------------------------ 06/10: combo đứng đầu, tên POI
def test_combo_head_is_not_a_flight_query():
    """c0706 "combo vé máy bay và khách sạn Đà Lạt" (fixture: Nha Trang): combo là loại chính → không parse tuyến, điểm đến lọc như câu thường."""
    p = plan("combo vé máy bay và khách sạn Nha Trang", PlanFlags(destination=True, taxonomy=True, route=True))
    assert p.taxonomy == "combo" and p.destination.value == "Nha Trang" and p.destination.skipped is None
    assert p.route_origin is None and p.route_destination is None and APPLIED_ROUTE not in p.applied
    flight = plan("vé máy bay đi Nha Trang", PlanFlags(destination=True, taxonomy=True, route=True))
    assert flight.route_destination == "Nha Trang" and APPLIED_ROUTE in flight.applied     # câu bay giữ luật cũ


def test_poi_brand_cue_stays_in_lexical_text_when_taxonomy_filters():
    p = plan("vé lẻ VinWonders Nam Hội An, không lấy combo", PlanFlags(taxonomy=True, negation=True))
    assert p.mask_taxonomy == "attraction" and "vinwonders" in fold(p.lexical_text)
    q = plan("vé vui chơi Nha Trang", PlanFlags(taxonomy=True))
    assert "vui choi" not in fold(q.lexical_text)                                        # cue thường vẫn cắt
