"""Giả thuyết LLM của query plan — kiểm với catalog (`validate_hypothesis`) và trộn vào plan rule (`merge_hypothesis`), thuần.

Catalog giả: điểm đến Nha Trang / Phú Quốc, thành phố bay Hà Nội / Nha Trang, mã HAN → Hà Nội."""
from src.backend.app.domain.search import PlanFlags, PlanGazetteers, PlanParams, QueryNormalizer, build_query_plan
from src.backend.app.domain.search.hypothesis import (
    HypothesisVocab,
    QueryHypothesis,
    ValidHypothesis,
    merge_hypothesis,
    validate_hypothesis,
)

VOCAB = HypothesisVocab.build(["Nha Trang", "Phú Quốc"], ["Hà Nội", "Nha Trang"], {"HAN": "Hà Nội"})
NORMALIZER = QueryNormalizer(destinations={"Nha Trang", "Phú Quốc"},
                             names=["Vinpearl Resort Nha Trang", "VinWonders Nha Trang", "Vinpearl Golf Nha Trang"])
GAZ = PlanGazetteers(flight_cities=("Hà Nội", "Nha Trang"))
ALL = PlanFlags(destination=True, negation=True, taxonomy=True, route=True, numeric=True, party=True)


def _valid(q: str, **h):
    nq = NORMALIZER(q)
    return validate_hypothesis(QueryHypothesis(**h), VOCAB, query=nq.text, raw_query=q)


def _plan(q: str, params: PlanParams = PlanParams(), flags: PlanFlags = ALL):
    return build_query_plan(NORMALIZER(q), q, params, flags, GAZ)


# ------------------------------------------------------------------ validate
def test_from_mapping_tolerates_loose_json():
    h = QueryHypothesis.from_mapping({"taxonomy": "hotel", "must_not_amenities": "pool", "soft_preferences": None,
                                      "destination": "  ", "unknown": 1, "price_max": "2000000"})
    assert h.taxonomy == "hotel" and h.must_not_amenities == ("pool",) and h.soft_preferences == ()
    assert h.destination is None and h.price_max == "2000000"
    assert QueryHypothesis.from_mapping(None).empty and not h.empty
    assert QueryHypothesis.from_mapping(h.as_dict()) == h


def test_taxonomy_must_be_in_contract_enum():
    v, rej = _valid("chỗ ở Nha Trang", taxonomy="Hotel")
    assert v.taxonomy == "hotel" and rej == []
    v, rej = _valid("chỗ ở Nha Trang", taxonomy="resort")
    assert v.taxonomy is None and rej == [("taxonomy", "invalid_value")]


def test_places_must_exist_in_catalog_and_in_the_query():
    v, rej = _valid("biển đẹp ở Nha Trang", destination="nha trang")
    assert v.destination == "Nha Trang" and rej == []
    assert _valid("biển đẹp ở Đà Lạt", destination="Đà Lạt")[1] == [("destination", "not_in_catalog")]
    assert _valid("biển đẹp miền Trung", destination="Nha Trang")[1] == [("destination", "not_in_query")]
    assert _valid("du lịch nhatrang", destination="Nha Trang")[0].destination == "Nha Trang"   # so trên chuỗi bỏ khoảng trắng
    v, rej = _valid("vé HAN đi Nha Trang", origin="Hà Nội", destination_city="Nha Trang")
    assert (v.origin, v.destination_city, rej) == ("Hà Nội", "Nha Trang", [])                # mã sân bay trong câu gốc
    assert _valid("vé đi Nha Trang", origin=5)[1] == [("origin", "invalid_value")]


def test_negation_needs_vocab_key_and_a_negation_cue():
    v, rej = _valid("khách sạn Nha Trang không có hồ bơi", must_not_amenities=["pool", "jacuzzi_pool"])
    assert v.must_not_amenities == ("pool",) and rej == [("mustNotAmenities", "invalid_value")]
    v, rej = _valid("khách sạn Nha Trang có hồ bơi", must_not_amenities=["pool"])
    assert v.must_not_amenities == () and rej == [("mustNotAmenities", "no_cue")]
    v, rej = _valid("vé lẻ Nha Trang trừ combo", must_not_taxonomies=["combo"])
    assert v.must_not_taxonomies == ("combo",) and rej == []


def test_numbers_are_range_and_cue_checked():
    assert _valid("resort Nha Trang dưới 2 triệu", price_max=2_000_000)[0].price_max == 2_000_000
    assert _valid("resort Nha Trang giá rẻ", price_max=1_000_000)[1] == [("price", "no_cue")]
    assert _valid("resort 2 triệu", price_min=3_000_000, price_max=2_000_000)[1] == [("price", "out_of_range")]
    assert _valid("resort 2 triệu", price_max=-1)[1] == [("price", "out_of_range")]
    assert _valid("resort 2 triệu", price_max="hai triệu")[1] == [("price", "invalid_value")]
    assert _valid("resort 5 sao", star_min=5)[0].star_min == 5.0
    assert _valid("resort 5 sao", star_min=6)[1] == [("star", "out_of_range")]
    assert _valid("resort sang trọng", star_min=5)[1] == [("star", "no_cue")]
    assert _valid("phòng cho hai vợ chồng", party_total=2)[0].party_total == 2
    assert _valid("phòng cho 4 người", party_total=0)[1] == [("party", "out_of_range")]
    assert _valid("phòng cho 4 người", party_total=2.5)[1] == [("party", "invalid_value")]
    assert _valid("phòng đẹp", party_total=4)[1] == [("party", "no_cue")]


def test_low_self_confidence_rejects_the_whole_hypothesis():
    v, rej = _valid("khách sạn Nha Trang", taxonomy="hotel", confidence=0.2)
    assert v == ValidHypothesis() and rej == [("hypothesis", "low_confidence")]


# ------------------------------------------------------------------ merge
def test_fills_only_empty_slots_and_obeys_family_flags():
    q = "đi chơi Nha Trang hoặc Phú Quốc cuối tuần cho cả nhà"     # hai nơi → rule không lọc điểm đến (skipped multi)
    plan = _plan(q)
    assert plan.destination.value is None and plan.taxonomy is None and plan.party_total is None
    valid = ValidHypothesis(taxonomy="attraction", destination="Phú Quốc", party_total=4)
    on, acc, rej = merge_hypothesis(plan, valid, ALL, raw_query=q)
    assert acc == ["taxonomy", "destination", "party"] and rej == []
    assert on.mask_kwargs(destination=on.destination.value) == {
        "taxonomy": "attraction", "destination": "Phú Quốc", "only_available": True, "min_occupancy": 4}
    assert on.destination.source == "query" and on.drop_tokens == {"phu", "quoc"}
    assert on.as_diagnostics(extended=True)["taxonomy"]["source"] == "query"
    assert on.confidence == plan.confidence and on.lexical_text == plan.lexical_text   # router + BM25 text giữ của rule
    flags_off = PlanFlags()
    off, acc, rej = merge_hypothesis(_plan(q, flags=flags_off), valid, flags_off, raw_query=q)
    assert acc == ["taxonomy", "party"] and rej == [("destination", "flag_off")]
    assert off.taxonomy == "attraction" and off.applied == () and off.mask_taxonomy is None   # khai, không lọc


def test_rule_and_params_always_win():
    q = "khách sạn Nha Trang dưới 3 triệu"
    plan = _plan(q, PlanParams(star_min=4))
    merged, acc, rej = merge_hypothesis(plan, ValidHypothesis(taxonomy="combo", price_max=5_000_000, star_min=5,
                                                              destination="Phú Quốc"), ALL, raw_query=q)
    assert acc == [] and merged is plan
    assert ("taxonomy", "rule_set") in rej and ("price", "rule_set") in rej and ("star", "param_set") in rej
    assert ("destination", "rule_set") in rej
    same, acc, rej = merge_hypothesis(plan, ValidHypothesis(taxonomy="hotel", price_max=3_000_000), ALL, raw_query=q)
    assert acc == [] and rej == [] and same is plan                            # trùng giá trị rule → lặng lẽ


def test_multi_vertical_is_never_narrowed_and_asked_type_never_excluded():
    q = "khách sạn, vé máy bay và vé tham quan ở Nha Trang"
    merged, acc, rej = merge_hypothesis(_plan(q), ValidHypothesis(taxonomy="hotel", must_not_taxonomies=("flight", "combo")),
                                        ALL, raw_query=q)
    assert ("taxonomy", "multi_vertical") in rej and ("mustNotTaxonomies", "conflict") in rej
    assert acc == ["mustNotTaxonomies"] and merged.must_not_taxonomies == ("combo",) and "mustNot" in merged.applied


def test_route_only_for_flight_queries_and_feeds_destination():
    q = "vé máy bay giá tốt cuối tuần"
    merged, acc, rej = merge_hypothesis(_plan(q), ValidHypothesis(origin="Hà Nội", destination_city="Nha Trang",
                                                                  destination="Nha Trang"), ALL, raw_query=q)
    assert acc == ["origin", "destinationCity"] and rej == [("destination", "not_flight")]
    assert merged.mask_origin == "Hà Nội" and merged.route_direction == "explicit" and "route" in merged.applied
    assert merged.destination.value == "Nha Trang" and merged.destination.source == "query"
    q2 = "resort Nha Trang cho gia đình"
    _, acc, rej = merge_hypothesis(_plan(q2), ValidHypothesis(origin="Hà Nội"), ALL, raw_query=q2)
    assert acc == [] and rej == [("origin", "not_flight")]
    q3 = "vé máy bay đi Nha Trang"
    p3 = _plan(q3, PlanParams(origin="Hà Nội"))
    _, acc, rej = merge_hypothesis(p3, ValidHypothesis(origin="Nha Trang"), ALL, raw_query=q3)
    assert rej == [("origin", "param_set")]


def test_negation_adds_new_keys_only():
    q = "khách sạn Nha Trang không có hồ bơi và không spa"
    plan = _plan(q)
    merged, acc, _ = merge_hypothesis(plan, ValidHypothesis(must_not_amenities=("pool", "spa")), ALL, raw_query=q)
    assert set(merged.must_not_amenities) == {"pool", "spa"}
    assert (acc == ["mustNotAmenities"]) == ("spa" not in plan.must_not_amenities)
