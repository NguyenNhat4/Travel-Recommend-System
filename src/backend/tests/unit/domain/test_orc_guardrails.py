"""Kiểm câu trả lời orc (AC-AGT-06/07, §14 plan): trần 10 mỗi loại, mã có nguồn, số qua fact, công bố cảnh báo."""
from src.backend.app.domain.itinerary.orc_guardrails import final_issues
from src.backend.tests.fakes.orc_tools import product, respond


def products(count, taxonomy="hotel", start=0):
    return {f"p{i}": product(f"x{i}", taxonomy) for i in range(start, start + count)}


def issues(decision, *, catalog=None, plans=None, consent=False, free_only=False, facts=None):
    return [issue["code"] for issue in final_issues(
        decision, products=catalog or {}, plans=plans or {}, consent=consent, free_only=free_only,
        fact=lambda ref, field: (facts or {}).get((ref, field)))]


def test_g06_thirty_cards_across_taxonomies_pass_but_eleven_of_one_type_repairs():
    catalog = {**products(10), **products(10, "attraction", 10), **products(10, "combo", 20)}
    decision = respond(hotel=[f"p{i}" for i in range(10)], attraction=[f"p{i}" for i in range(10, 20)],
                       combo=[f"p{i}" for i in range(20, 30)])
    assert issues(decision, catalog=catalog) == []
    eleven = respond(hotel=[f"p{i}" for i in range(10)],
                     alternatives=[{"product_ref": "p10", "violates": [], "disclosure": "Gần biển hơn",
                                    "plan_result_id": None}])
    assert "TAXONOMY_CARD_LIMIT" in issues(eleven, catalog={**products(11)})


def test_g07_ref_without_current_turn_source_is_rejected_not_replaced():
    assert issues(respond(hotel=["p9"]), catalog=products(1)) == ["UNGROUNDED_REF"]
    assert issues(respond(hotel=["p0", "p0"]), catalog=products(1)) == ["DUPLICATE_CARD"]
    assert issues(respond(attraction=["p0"]), catalog=products(1)) == ["TAXONOMY_MISMATCH"]


def test_numbers_need_fact_segments_and_booking_claims_are_blocked():
    assert issues(respond("Giá chỉ 1.200.000 đ một đêm")) == ["NUMBER_WITHOUT_FACT"]
    assert issues(respond("Chuyến bay lúc 8:30 sáng")) == ["NUMBER_WITHOUT_FACT"]
    assert issues(respond("Mình đã đặt phòng cho bạn")) == ["FALSE_BOOKING_CLAIM"]
    assert issues(respond("Đi 3 ngày 2 đêm, 2 người lớn")) == []
    cited = respond(answer=[{"type": "text", "text": "Giá"}, {"type": "fact", "ref": "p0", "field": "unitPrice"}])
    assert issues(cited, facts={("p0", "unitPrice"): 100_000}) == []
    assert issues(cited) == ["UNSUPPORTED_FACT"]
    assert issues(respond("key sk-abcdefghijklmnop")) == ["SECRET_EXPOSURE"]


def test_g02_plan_replace_needs_every_warning_disclosed_and_consent():
    plan = {"feasibility": "provisional", "warnings": [{"code": "OVER_TRIP_BUDGET", "refs": []},
                                                       {"code": "TIMING_ESTIMATED", "refs": ["p0"]}]}
    decision = respond(turn_kind="itinerary", plan_effect="replace", plan_result_id="c3",
                       disclosures=["TIMING_ESTIMATED"])
    assert issues(decision, plans={"c3": plan}, consent=True) == ["MISSING_BUDGET_DISCLOSURE"]
    decision["disclosures"].append("OVER_TRIP_BUDGET")
    assert issues(decision, plans={"c3": plan}, consent=True) == []
    assert issues(decision, plans={"c3": plan}) == ["PLAN_CONSENT_REQUIRED"]
    assert issues(decision, plans={"c3": {**plan, "feasibility": "infeasible"}}, consent=True) == \
        ["INVALID_PLAN_RESULT"]
    assert issues(respond(plan_effect="replace", plan_result_id="c3"), plans={"c3": plan}, consent=True) == \
        ["TURN_KIND_MISMATCH", "MISSING_BUDGET_DISCLOSURE", "MISSING_DISCLOSURE"]


def test_g05_free_only_paid_card_must_be_a_disclosed_alternative():
    catalog = {"p0": product("paid", "attraction"), "p1": product("free", "attraction", price=0)}
    assert issues(respond(attraction=["p0"]), catalog=catalog, free_only=True) == ["NOT_FREE"]
    alternative = {"product_ref": "p0", "violates": ["free_only"], "disclosure": "Có phí vào cửa",
                   "plan_result_id": None}
    assert issues(respond(attraction=["p1"], alternatives=[alternative]), catalog=catalog, free_only=True) == []
    hidden = {**alternative, "violates": []}
    assert issues(respond(alternatives=[hidden]), catalog=catalog, free_only=True) == ["UNDISCLOSED_NOT_FREE"]


def test_duplicate_suggestions_are_returned_for_repair():
    buttons = [{"label": "Lên lịch Huế", "fare_query": None}, {"label": "lên lịch huế", "fare_query": None}]
    assert issues(respond(suggestions=buttons)) == ["DUPLICATE_SUGGESTION"]
