"""Dựng response v2: đúng thẻ orc chọn, số điền từ dữ kiện, câu cảnh báo do code viết, nút có lệnh server cấp."""
import pytest

from src.backend.app.application.itinerary.product_registry import ProductRegistry
from src.backend.app.application.itinerary.v2_final import render_final
from src.backend.app.domain.itinerary.draft_validation import check_draft
from src.backend.tests.fakes.orc_tools import arguments, product, respond


def plan(registry, *, budget=2_000_000, price=1_150_000):
    ref = registry.add(product("dai-noi", price=price))
    draft = arguments("build_itinerary", destination="Huế", start_date="2026-10-24", days=1, adults=2, children=0,
                      trip_budget_vnd=budget, plan_days=[{"day_index": 1, "activities": [
                          {"product_ref": ref, "start_minute": 480, "end_minute": 600, "timing_source": "estimate",
                           "assumption": "Tham quan khoảng 2 giờ"}]}])
    return ref, {"c3": {"plan_result_id": "c3", "draft": draft, "products": {ref: registry.product(ref)},
                        **check_draft(draft, {ref: registry.product(ref)})}}


def render(decision, registry, plans=None, results=None):
    return render_final(decision, registry=registry, plans=plans or {}, results=results or {},
                        conversation_id="conv", run_id="run")


def test_cards_are_exactly_the_selected_refs_in_order():
    registry = ProductRegistry()
    refs = [registry.add(product(f"h{i}", "hotel", score=0.5)) for i in range(3)]
    final, memory = render(respond(hotel=[refs[2], refs[0]]), registry)
    assert [card["productId"] for card in final["recommendations"]["hotel"]] == ["h2", "h0"]
    assert "score" not in final["recommendations"]["hotel"][0]
    assert final["itinerary"] is None and final["planEffect"] == "keep"
    assert memory["shown"] == {refs[2]: {"productId": "h2", "name": "Sản phẩm h2", "taxonomy": "hotel"},
                               refs[0]: {"productId": "h0", "name": "Sản phẩm h0", "taxonomy": "hotel"}}


def test_public_place_assumption_is_visible_without_changing_source_price():
    registry = ProductRegistry()
    ref = registry.add(product("market", price=None))
    final, _ = render(respond("Bạn có thể ghé tham quan tự do.", attraction=[ref],
                              disclosures=["FREE_ENTRY_ASSUMED"]), registry)
    assert final["recommendations"]["attraction"][0]["unitPrice"] is None
    assert final["warnings"][0]["productIds"] == ["market"]
    assert "phí vào cửa" in final["message"] and "catalog" not in final["message"]


def test_fact_segments_are_filled_from_current_data():
    registry = ProductRegistry()
    ref = registry.add(product("h", "hotel", price=1_500_000))
    decision = respond(answer=[{"type": "text", "text": "Giá từ"}, {"type": "fact", "ref": ref, "field": "unitPrice"},
                               {"type": "text", "text": "mỗi đêm, rẻ nhất đợt là"},
                               {"type": "fact", "ref": "c2", "field": "period.cheapest_price_vnd"}])
    final, _ = render(decision, registry, results={"c2": {"data": {"period": {"cheapest_price_vnd": 900_000}}}})
    assert final["message"] == "Giá từ 1.500.000 ₫ mỗi đêm, rẻ nhất đợt là 900.000 ₫"


def test_sentence_naming_a_product_ends_its_paragraph():
    """Một đoạn liền làm mọi thẻ dồn xuống cuối như danh sách; widget đặt thẻ sau dòng đầu nhắc sản phẩm."""
    registry = ProductRegistry()
    hotel, beach, bridge = (registry.add(product(i)) for i in ("dao-ngoc", "my-khe", "cau-rong"))
    decision = respond(answer=[
        {"type": "text", "text": "Khách sạn nổi bật là"}, {"type": "product", "ref": hotel},
        {"type": "text", "text": "Nơi này có hồ bơi. Bạn đi ngày nào?"},
        {"type": "product", "ref": beach},
        {"type": "text", "text": "là bãi biển dài. Tối có thể ghé"}, {"type": "product", "ref": bridge},
        {"type": "text", "text": "xem cầu phun lửa."}])
    final, _ = render(decision, registry)
    assert final["message"].split("\n\n") == [
        "Khách sạn nổi bật là [Sản phẩm dao-ngoc](product:dao-ngoc)",
        "Nơi này có hồ bơi. Bạn đi ngày nào?",
        "[Sản phẩm my-khe](product:my-khe) là bãi biển dài.",
        "Tối có thể ghé [Sản phẩm cau-rong](product:cau-rong) xem cầu phun lửa."]


def test_sentence_end_split_across_segments_still_ends_the_paragraph():
    registry = ProductRegistry()
    bridge, park = registry.add(product("cau-rong")), registry.add(product("ba-na"))
    decision = respond(answer=[{"type": "text", "text": "Ngày đầu: tối ghé"}, {"type": "product", "ref": bridge},
                               {"type": "text", "text": "."}, {"type": "text", "text": "Ngày thứ hai: trọn ngày ở"},
                               {"type": "product", "ref": park}, {"type": "text", "text": "."}])
    final, _ = render(decision, registry)
    assert final["message"].split("\n\n") == ["Ngày đầu: tối ghé [Sản phẩm cau-rong](product:cau-rong).",
                                               "Ngày thứ hai: trọn ngày ở [Sản phẩm ba-na](product:ba-na)."]


def test_facts_and_lowercase_text_stay_in_the_product_sentence():
    registry = ProductRegistry()
    ref = registry.add(product("h", "hotel", price=563_333))
    decision = respond(answer=[{"type": "product", "ref": ref}, {"type": "text", "text": "giá từ"},
                               {"type": "fact", "ref": ref, "field": "unitPrice"},
                               {"type": "text", "text": "mỗi đêm."}])
    final, _ = render(decision, registry)
    assert final["message"] == "[Sản phẩm h](product:h) giá từ 563.333 ₫ mỗi đêm."


def test_g01_over_budget_plan_shows_exact_amounts_and_zero_nights():
    registry = ProductRegistry()
    _, plans = plan(registry)
    decision = respond("Lịch một ngày ở Huế.", turn_kind="itinerary", plan_effect="replace", plan_result_id="c3",
                       disclosures=["OVER_TRIP_BUDGET", "TIMING_ESTIMATED", "OPENING_HOURS_UNKNOWN"])
    final, memory = render(decision, registry, plans)
    assert final["itinerary"]["nights"] == 0 and final["itinerary"]["stays"] == []
    assert final["itinerary"]["costs"]["overByVnd"] == 300_000
    assert "vượt ngân sách 2.000.000 ₫ là 300.000 ₫" in final["message"]
    assert {w["code"] for w in final["warnings"]} == {"OVER_TRIP_BUDGET", "TIMING_ESTIMATED", "OPENING_HOURS_UNKNOWN"}
    assert list(memory["shown"]) == ["p1"]


def test_buttons_and_alternatives_carry_server_issued_actions():
    registry = ProductRegistry()
    hotel = registry.add(product("h", "hotel"))
    fare = arguments("lookup_flights", origin="Hà Nội", destination="Huế", sort="price_desc")
    decision = respond(suggestions=[{"label": "Vé đắt nhất thì sao?", "fare_query": fare},
                                    {"label": "Lên lịch Huế", "fare_query": None}],
                       alternatives=[{"product_ref": hotel, "violates": ["trip_budget"], "disclosure": "Đắt hơn",
                                      "plan_result_id": None}])
    final, memory = render(decision, registry)
    fare_button, plain = final["suggestions"]
    assert plain == {"label": "Lên lịch Huế", "message": "Lên lịch Huế", "uiAction": None}
    assert memory["actions"][fare_button["uiAction"]["actionId"]]["query"] == fare
    action = final["alternatives"][0]["uiAction"]
    assert memory["actions"][action["actionId"]]["product_ref"] == hotel
    assert action["alternativeId"] == final["alternatives"][0]["alternativeId"]


def test_response_outside_the_contract_is_an_error_not_trimmed():
    registry = ProductRegistry()
    refs = [registry.add(product(f"h{i}", "hotel")) for i in range(11)]
    with pytest.raises(ValueError):
        render(respond(hotel=refs), registry)


@pytest.mark.parametrize('basis,expected_rooms', [(2, 1), (8, 1), (None, None)])
def test_stay_rooms_and_totals_are_consistent_with_the_price_basis(basis, expected_rooms):
    registry = ProductRegistry()
    room = registry.add(product('room', 'hotel', price=1_000_000, unit='PER_NIGHT',
                                priceAdults=basis, maxOccupancy=8))
    adults = 8 if basis == 8 else 2
    draft = arguments('build_itinerary', destination='Huế', start_date='2026-10-24', days=2,
                      adults=adults, children=0, plan_days=[{'day_index': i, 'activities': []} for i in [1, 2]],
                      stays=[{'product_ref': room, 'check_in': '2026-10-24', 'check_out': '2026-10-25'}])
    products = {room: registry.product(room)}
    checked = check_draft(draft, products)
    plans = {'c1': {'plan_result_id': 'c1', 'draft': draft, 'products': products, **checked}}
    decision = respond(turn_kind='itinerary', plan_effect='replace', plan_result_id='c1',
                       disclosures=[warning['code'] for warning in checked['warnings']])
    final, _ = render(decision, registry, plans)
    assert final['itinerary']['stays'][0]['rooms'] == expected_rooms
    assert final['itinerary']['costs']['estimatedTotalVnd'] == (None if basis is None else 1_000_000)
    if basis is None:
        assert 'Chưa rõ giá phòng' in final['message'] and 'tạm cho 1 phòng' not in final['message']


def test_plan_array_facts_and_computed_minutes_are_rendered_from_source():
    from src.backend.app.application.itinerary.v2_final import _fact_text, fact
    registry = ProductRegistry()
    results = {'c1': {'data': {'days': [{'activities': [{'start_minute': 780}]}], 'stays': [{'nights': 2}]}}}
    assert fact(registry, results, 'c1', 'stays.0.nights') == 2
    assert fact(registry, results, 'c1', 'days.0.activities.0.start_minute') == 780
    assert _fact_text('days.0.activities.0.start_minute', 780, 'vi') == '13:00'
    assert fact(registry, results, 'c1', 'stays.9.nights') is None
    assert fact(registry, results, 'c1', 'stays.-1.nights') is None
