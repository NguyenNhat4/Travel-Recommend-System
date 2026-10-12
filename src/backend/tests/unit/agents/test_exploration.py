"""Trò chuyện và khám phá trước khi lập lịch (FR-AGT-06, chốt 2026-10-10).

Luật chọn thẻ, nút gợi ý, luật đồng ý lập lịch, và luồng nhiều lượt qua graph với Search giả, LLM giả.
"""
import re
import unittest

from src.backend.app.agents.models import ExploreNarration, Extraction, TurnRoute
from src.backend.app.agents.nodes import intake_node
from src.backend.app.agents.steps import validation
from src.backend.app.agents.steps.classification import (asks_for_plan, extract_result, plan_consented, route_result,
                                                          says_yes)
from src.backend.app.agents.steps.exploration import checked_suggestions
from src.backend.app.domain.itinerary import exploration as rules
from src.backend.app.domain.itinerary.planning import empty_intent
from src.backend.app.infrastructure.persistence.conversation_store import InMemoryConversationStore

from . import test_itinerary_runtime as runtime
from .test_itinerary_runtime import Clients, ScriptedLlm, product


def place(pid, taxonomy='attraction', **fields):
    return product(pid, taxonomy=taxonomy, destination='Hà Nội', name=f'Nơi {pid}', **fields)


class PickCardsTests(unittest.TestCase):
    """Mỗi thẻ một lý do, và lý do đúng trên toàn bộ kết quả, không trên phần đã cắt."""

    def test_the_cheapest_is_the_cheapest_of_all_results_even_when_it_is_a_hostel(self):
        # Kịch bản bản 4 từng nói Solare "rẻ nhất" trong khi Little Charm Hostel rẻ hơn mà vẫn có hồ bơi.
        hotels = [place('solare', 'hotel', unitPrice=2_376_000, rating=4.7, reviewCount=3541),
                  place('classyc', 'hotel', unitPrice=4_688_250, rating=4.9, reviewCount=171),
                  place('charm', 'hotel', unitPrice=220_014, rating=4.5, reviewCount=4524)]
        cards = rules.pick_cards(hotels, 2, 'hotel')
        reasons = {card['product']['productId']: card['reasons'] for card in cards}
        self.assertIn(rules.CHEAPEST, reasons['charm'])
        self.assertEqual(reasons['classyc'], [rules.TOP_RATED])
        self.assertNotIn('solare', reasons)

    def test_a_reason_already_held_by_a_card_is_never_given_to_the_runner_up(self):
        # Rẻ nhất cũng là nhiều đánh giá nhất: không được gán "nhiều đánh giá nhất" cho khách sạn hạng hai.
        hotels = [place('a', 'hotel', unitPrice=100, reviewCount=900),
                  place('b', 'hotel', unitPrice=500, reviewCount=800)]
        cards = rules.pick_cards(hotels, 2, 'hotel')
        self.assertEqual(cards[0]['reasons'], [rules.CHEAPEST, rules.MOST_REVIEWED])
        self.assertEqual(cards[1]['reasons'], [rules.ALSO_POPULAR])

    def test_top_rated_needs_enough_reviews(self):
        attractions = [place('few', rating=5.0, reviewCount=3), place('many', rating=4.6, reviewCount=1139)]
        cards = rules.pick_cards(attractions, 4, 'attraction')
        top = next(card for card in cards if rules.TOP_RATED in card['reasons'])
        self.assertEqual(top['product']['productId'], 'many')

    def test_tickets_of_the_same_place_take_one_card(self):
        attractions = [product('v1', name='[VinWonders Phú Quốc] Vé Vào Cửa', reviewCount=50),
                       product('v2', name='[VinWonders Phú Quốc] Vé + Buffet', reviewCount=40),
                       product('h', name='Hòn Thơm', reviewCount=10)]
        ids = [card['product']['productId'] for card in rules.pick_cards(attractions, 4, 'attraction')]
        self.assertEqual(ids, ['v1', 'h'])

    def test_a_place_named_inside_another_takes_one_card(self):
        attractions = [product('cap', name='Cáp Treo Hòn Thơm', reviewCount=3969),
                       product('hon', name='hòn Thơm', reviewCount=200, rating=4.9),
                       product('vin', name='VinWonders Phú Quốc', reviewCount=100)]
        ids = [card['product']['productId'] for card in rules.pick_cards(attractions, 4, 'attraction')]
        self.assertEqual(sorted(ids), ['cap', 'vin'])

    def test_a_hotel_and_its_room_take_one_card(self):
        # LLM thật 10/10 (fixture): "VinHolidays Fiesta Phú Quốc" và "... - Phòng Tiêu Chuẩn Giường Đôi" hiện hai thẻ.
        hotels = [product('h', taxonomy='hotel', name='VinHolidays Fiesta Phú Quốc', unitPrice=1_844_192),
                  product('r', taxonomy='hotel', name='VinHolidays Fiesta Phú Quốc - Phòng Tiêu Chuẩn Giường Đôi',
                          unitPrice=1_900_000),
                  product('v', taxonomy='hotel', name='Vinpearl Resort', unitPrice=3_000_000)]
        ids = [card['product']['productId'] for card in rules.pick_cards(hotels, 4, 'hotel')]
        self.assertEqual(sorted(ids), ['h', 'v'])

    def test_free_entry_is_a_reason_of_its_own(self):
        attractions = [place('paid', reviewCount=500, unitPrice=900_000),
                       place('free', reviewCount=100, unitPrice=0, attributes={'ticketed': False})]
        cards = rules.pick_cards(attractions, 4, 'attraction')
        self.assertIn(rules.FREE_ENTRY, next(c for c in cards if c['product']['productId'] == 'free')['reasons'])


class AmenityTests(unittest.TestCase):
    def test_a_pool_written_only_in_the_amenity_strings_counts(self):
        # LLM thật 10/10: catalog không có cờ `pool`, chỉ có chuỗi tiện ích; lọc theo cờ thì ra "không có chỗ nào".
        hotel = place('h', 'hotel', attributes={'amenities': ['Wi-Fi miễn phí', 'Hồ bơi ngoài trời']})
        dry = place('d', 'hotel', attributes={'amenities': ['Wi-Fi miễn phí', 'Không có hồ bơi']})
        self.assertEqual([p['productId'] for p in rules.with_amenity([hotel, dry], 'pool')], ['h'])


class NamedPlaceTests(unittest.TestCase):
    """Câu hỏi nêu tên một nơi trả đúng thẻ nơi đó (kịch bản cảnh 9, LLM thật 10/10 đã trả thẻ chung chung)."""

    def test_the_named_place_is_found_by_the_first_part_of_its_name(self):
        van_mieu = product('vm', destination='Hà Nội', name='Văn Miếu – Quốc Tử Giám',
                           attributes={'openingHours': '08:00–17:00, 18:00–22:00'})
        city = product('hn', destination='Hà Nội', name='Hà Nội')
        self.assertEqual(rules.named_in([city, van_mieu], 'Văn Miếu buổi tối có mở không?', ['Hà Nội'])['productId'], 'vm')
        self.assertIsNone(rules.named_in([city, van_mieu], 'Hà Nội có gì chơi?', ['Hà Nội']))

    def test_the_named_place_comes_first_with_its_opening_hours_for_the_llm(self):
        from src.backend.app.agents.steps.exploration import NAMED_CALL_ID, explore_input, pick
        van_mieu = product('vm', destination='Hà Nội', name='Văn Miếu – Quốc Tử Giám', reviewCount=361,
                           attributes={'openingHours': '08:00–17:00, 18:00–22:00'})
        results = [{'tool_call_id': 'explore-1-attraction', 'data': {'results': [place('ho', reviewCount=1139)]}},
                   {'tool_call_id': NAMED_CALL_ID, 'data': {'results': [van_mieu]}}]
        state = {**intake_node({'query': 'Văn Miếu buổi tối có mở không?'}), 'intent': empty_intent()}
        cards, _ = pick(state, 'Hà Nội', results)
        self.assertEqual((cards[0]['product']['productId'], cards[0]['reasons']), ('vm', [rules.ASKED]))
        payload = explore_input(state, 'Hà Nội', cards, None, ['Hà Nội'])[1][1]
        self.assertIn('08:00–17:00, 18:00–22:00', payload)


class ChatTextTests(unittest.TestCase):
    """Câu chat nói nơi đó có gì hay; điểm, lượt đánh giá, giờ mở cửa và giá để trên thẻ (góp ý người dùng 2026-10-10)."""

    def test_about_keeps_what_the_place_is_and_drops_data_sentences(self):
        from src.backend.app.agents.steps.exploration import about
        lang = product('lang', name='Lăng Chủ tịch Hồ Chí Minh', description=(
            'Lăng Chủ tịch Hồ Chí Minh. Loại hình: Thắng cảnh lịch sử. Địa chỉ: 1 Hùng Vương, Ba Đình. '
            'Giờ mở cửa: 08:00–11:00. Thời gian tham quan đề xuất: 1–2 tiếng đồng hồ'))
        self.assertEqual(about(lang), '')
        van_mieu = product('vm', name='Văn Miếu – Quốc Tử Giám', description=(
            'Văn Miếu – Quốc Tử Giám là công trình kiến trúc từ thế kỷ 11 được bảo tồn tốt. '
            'Đồng thời là trường đại học đầu tiên của đất nước. Giờ mở cửa: 08:00–17:00.'))
        self.assertEqual(about(van_mieu), 'Văn Miếu – Quốc Tử Giám là công trình kiến trúc từ thế kỷ 11 được bảo tồn '
                                          'tốt. Đồng thời là trường đại học đầu tiên của đất nước.')

    def test_opening_hours_go_to_the_llm_only_for_the_place_the_user_asked_about(self):
        from src.backend.app.agents.steps.exploration import _card_input
        hours = {'openingHours': '08:00–17:00', 'tags': ['Thắng cảnh lịch sử']}
        plain = _card_input({'product': place('ho', attributes=hours), 'reasons': [rules.MOST_REVIEWED]})
        asked = _card_input({'product': place('vm', attributes=hours), 'reasons': [rules.ASKED]})
        self.assertNotIn('facts', plain)
        self.assertEqual(plain['tags'], ['Thắng cảnh lịch sử'])
        self.assertEqual(asked['facts']['openingHours'], '08:00–17:00')

    def test_the_fallback_line_describes_the_place_without_numbers(self):
        from src.backend.app.agents.steps.exploration import card_line
        state = {'query': 'Hà Nội có gì?', 'language': 'vi'}
        van_mieu = place('vm', rating=4.6, reviewCount=361, description=(
            'Văn Miếu là công trình kiến trúc từ thế kỷ 11 được bảo tồn tốt. Giờ mở cửa: 08:00–17:00.'))
        self.assertEqual(card_line(state, {'product': van_mieu, 'reasons': [rules.TOP_RATED]}),
                         '[Nơi vm](product:vm): Văn Miếu là công trình kiến trúc từ thế kỷ 11 được bảo tồn tốt.')
        bare = place('ho', rating=4.6, reviewCount=1139, description='')
        line = card_line(state, {'product': bare, 'reasons': [rules.MOST_REVIEWED]})
        self.assertEqual(line, '[Nơi ho](product:ho): nhiều người ghé nhất ở đây.')

    def test_price_and_rating_placeholders_are_dropped_unless_the_user_asked_about_price(self):
        from src.backend.app.agents.steps.exploration import _fill, price_asked
        products = {'ks': place('ks', 'hotel', unitPrice=500_000, rating=4.7, reviewCount=3541)}
        text = '[KS](product:ks) ([[rating:ks]], [[reviews:ks]]) [[price:ks]]'
        quiet = {'query': 'Hà Nội có khách sạn nào gia đình ở được?', 'language': 'vi'}
        self.assertFalse(price_asked(quiet))
        self.assertEqual(_fill(quiet, text, products), '[KS](product:ks)')
        asked = {'query': 'khách sạn nào rẻ?', 'language': 'vi'}
        self.assertTrue(price_asked(asked))
        filled = _fill(asked, text, products)
        self.assertIn('500', filled)
        self.assertNotIn('4,7', filled)
        self.assertNotIn('3.541', filled)


class SuggestionTests(unittest.TestCase):
    """Tối đa 3 nút, khác mẫu câu, không lặp lượt trước, có một nút đi tiếp (AC-AGT-07)."""

    destinations = ['Hà Nội', 'Đà Nẵng', 'Phú Quốc']

    def test_same_pattern_with_another_place_is_dropped(self):
        kept = checked_suggestions(['Hà Nội có gì?', 'Đà Nẵng có gì?', 'Khách sạn sát biển'], [], [],
                                   destinations=self.destinations)
        self.assertEqual(kept, ['Hà Nội có gì?', 'Khách sạn sát biển'])

    def test_buttons_of_the_previous_turn_are_not_repeated(self):
        kept = checked_suggestions(['Tìm chỗ đi biển', 'Tối ở Hà Nội đi đâu?'], ['Tìm chỗ đi biển'], [],
                                   destinations=self.destinations)
        self.assertEqual(kept, ['Tối ở Hà Nội đi đâu?'])

    def test_a_plan_button_is_always_offered_first_when_none_asks_to_plan(self):
        kept = checked_suggestions(['A', 'B', 'C'], [], [], destinations=self.destinations,
                                   plan_chip='Lên lịch Hà Nội cho mình')
        self.assertEqual(kept[0], 'Lên lịch Hà Nội cho mình')
        self.assertEqual(len(kept), 3)

    def test_too_few_buttons_are_filled_from_the_templates(self):
        kept = checked_suggestions([''], [], ['Khách sạn ở Hà Nội', 'Gợi ý nơi khác cho mình'],
                                   destinations=self.destinations)
        self.assertEqual(kept, ['Khách sạn ở Hà Nội', 'Gợi ý nơi khác cho mình'])


class ConsentTests(unittest.TestCase):
    """Đồng ý lập lịch nhận bằng luật; chưa đồng ý thì không hỏi thông tin chuyến."""

    def test_short_yes_and_plan_requests_are_read_without_the_llm(self):
        for text in ('ok', 'được', 'có', 'oke nhé', 'lập đi'):
            self.assertTrue(says_yes(text), text)
        for text in ('Lên lịch Hà Nội cho mình', 'lập lịch Đà Nẵng 3 ngày', 'Tiếp tục lập lịch'):
            self.assertTrue(asks_for_plan(text), text)
        for text in ('Hà Nội có gì?', 'có khách sạn nào không', 'lên Đà Lạt chơi'):
            self.assertFalse(says_yes(text) or asks_for_plan(text), text)

    def test_yes_counts_only_after_an_offer(self):
        state = intake_node({'query': 'ok'})
        self.assertFalse(plan_consented(state, 'vague'))
        self.assertTrue(plan_consented({**state, 'pending_offer': {'destination': 'Hà Nội'}}, 'vague'))

    def test_switching_place_after_an_offer_is_not_agreeing_to_plan(self):
        # LLM thật 10/10: "Thôi, Hà Nội thì sao?" sau lời mời Nha Trang bị coi là đồng ý và hỏi số ngày luôn.
        state = {**intake_node({'query': 'Thôi, Hà Nội thì sao?'}), 'pending_offer': {'destination': 'Nha Trang'}}
        self.assertFalse(plan_consented(state, 'travel'))
        result = extract_result(state, Extraction(patch={'destination': 'Hà Nội'}))
        self.assertEqual(result['decision'], 'explore')
        # Trả lời lời mời bằng thông tin chuyến vẫn là đồng ý.
        days = extract_result({**state, 'query': '3 ngày thôi'}, Extraction(patch={'days': 3}))
        self.assertTrue(days['plan_consent'])

    def test_the_llm_plan_flag_is_ignored_for_a_question_about_a_place(self):
        state = intake_node({'query': 'Hà Nội có gì?'})
        self.assertFalse(plan_consented(state, 'explore', llm_plan_request=True))

    def test_agreeing_to_an_offer_for_a_place_the_assistant_picked_records_that_place(self):
        state = {**intake_node({'query': 'ok'}), 'pending_offer': {'destination': 'Đà Nẵng'}}
        result = route_result(state, TurnRoute(route='vague'))
        self.assertTrue(result['plan_consent'])
        self.assertEqual(result['intent']['destination'], 'Đà Nẵng')
        self.assertIsNone(result['pending_offer'])

    def test_leaving_the_choice_to_the_assistant_explores_a_picked_place_at_once(self):
        # LLM thật 10/10 xếp "Cứ chọn đại một nơi đi" là trò chuyện, nên trợ lý bảo người dùng tự nhắn tên nơi.
        for text in ('Cứ chọn đại một nơi đi', 'tuỳ bạn', 'đi đâu cũng được', 'Bạn chọn giúp mình một nơi', 'đi đâu cũng đc vl'):
            with self.subTest(text=text):
                result = route_result(intake_node({'query': text}), TurnRoute(route='conversation'))
                self.assertEqual((result['decision'], result['explore_pick']), ('explore', True))
        known = {**intake_node({'query': 'tuỳ bạn'}), 'intent': {**empty_intent(), 'destination': 'Hà Nội'}}
        self.assertNotEqual(route_result(known, TurnRoute(route='conversation'))['decision'], 'explore')

    def test_a_question_about_a_place_skips_extract_unless_it_carries_numbers(self):
        # Bớt một lượt gọi LLM: "Hà Nội có gì?" không cần `extract`; câu có chữ số có thể mang số ngày nên vẫn qua `extract`.
        plain = route_result(intake_node({'query': 'Hà Nội có gì?'}), TurnRoute(route='explore'))
        self.assertEqual((plain['decision'], plain['explore_direct']), ('explore', True))
        numbered = route_result(intake_node({'query': 'Hà Nội 3 ngày có gì?'}), TurnRoute(route='explore'))
        self.assertEqual(numbered['decision'], 'travel')

    def test_known_nicknames_of_a_place_are_recognised(self):
        from src.backend.app.agents.steps.exploration import destination_for
        for text, place in (('hn có gì vui', 'Hà Nội'), ('Sài Gòn có gì chơi?', 'TP. Hồ Chí Minh')):
            with self.subTest(text=text):
                state = {**intake_node({'query': text}), 'intent': empty_intent()}
                self.assertEqual(destination_for(state, ['Hà Nội', 'TP. Hồ Chí Minh']), place)

    def test_a_bare_destination_explores_instead_of_asking_for_days(self):
        result = extract_result(intake_node({'query': 'Hà Nội'}), Extraction(patch={'destination': 'Hà Nội'}))
        self.assertEqual(result['decision'], 'explore')
        self.assertEqual(result['intent']['destination'], 'Hà Nội')
        self.assertEqual(result['clarification_rounds'], 0)
        self.assertFalse(result['start_date_asked'])

    def test_a_trip_detail_means_the_user_is_planning(self):
        result = extract_result(intake_node({'query': 'Hà Nội 3 ngày'}),
                                Extraction(patch={'destination': 'Hà Nội', 'days': 3}))
        self.assertTrue(result['plan_consent'])
        self.assertEqual(result['decision'], 'missing_info')


class ExploreValidationTests(unittest.TestCase):
    def test_a_link_to_a_product_without_a_card_fails_grounding(self):
        card = place('a')
        state = {'candidates': {'a': card}}
        from src.backend.app.domain.itinerary.planning import summary
        response = {'status': 'NEEDS_CLARIFICATION', 'conversationId': 'c', 'knownIntent': empty_intent(),
                    'question': '[Nơi a](product:a) và [Nơi lạ](product:x)', 'searchResults': {'attraction': [summary(card)]}}
        self.assertIn('message_grounding', validation.response_issues(state, response, 200))
        response['question'] = '[Nơi a](product:a)'
        self.assertEqual(validation.response_issues(state, response, 200), [])


class ExploringLlm(ScriptedLlm):
    """LLM giả viết lời dẫn khám phá; `explore_message` có thể nhắc id lạ để kiểm chốt chặn."""

    def __init__(self, explore_message=None, explore_suggestions=(), **kwargs):
        super().__init__(**kwargs)
        self.explore_message = explore_message
        self.explore_suggestions = list(explore_suggestions)

    def with_structured_output(self, schema):
        if schema is not ExploreNarration:
            return super().with_structured_output(schema)

        async def invoke(prompt):
            self.calls.append('ExploreNarration')
            self.prompts['ExploreNarration'] = str(prompt)
            if self.explore_message is None:
                raise RuntimeError('provider error')
            return ExploreNarration(title='Hà Nội có gì', message=self.explore_message,
                                    suggestions=self.explore_suggestions)
        from types import SimpleNamespace
        return SimpleNamespace(ainvoke=invoke)


HANOI = [place('lang', reviewCount=363, rating=4.4, unitPrice=0, attributes={'ticketed': False}),
         place('ho', reviewCount=1139, rating=4.6, unitPrice=0, attributes={'ticketed': False}),
         place('charm', 'hotel', unitPrice=220_014, rating=4.5, reviewCount=4524, attributes={'pool': True}),
         place('solare', 'hotel', unitPrice=2_376_000, rating=4.7, reviewCount=3541, attributes={'pool': True}),
         place('plain', 'hotel', unitPrice=150_000, rating=4.0, reviewCount=50, attributes={'pool': False})]


class ExploreFlowTests(unittest.IsolatedAsyncioTestCase):
    """Luồng nhiều lượt: khám phá → mời lập lịch → "ok" → hỏi thông tin chuyến, không form trước khi đồng ý."""

    # Dùng lại cách chạy graph của test runtime, không kế thừa lớp đó (kế thừa thì chạy lặp lại toàn bộ test của nó).
    run_graph = runtime.RuntimeTests.run_graph

    def clients(self):
        return Clients(products=[dict(item) for item in HANOI], destinations=['Hà Nội', 'Đà Nẵng'])

    async def test_asking_about_a_place_answers_with_real_cards_and_offers_to_plan(self):
        clients = self.clients()
        llm = ExploringLlm(route='explore', extraction=Extraction(patch={'destination': 'Hà Nội'}),
                           explore_message='Hà Nội hợp đi bộ.\n[Nơi ho](product:ho) có [[reviews:ho]].\n'
                                           '[Khách sạn bịa](product:invented) rất đẹp.')
        result = await self.run_graph(llm, clients, state={'query': 'Hà Nội có gì?'})
        response = result['response']
        self.assertEqual(response['status'], 'NEEDS_CLARIFICATION')
        self.assertNotIn('clarificationForm', response)
        self.assertNotIn('missingFields', response)
        shown = {p['productId'] for products in response['searchResults'].values() for p in products}
        self.assertLessEqual(len(shown), 4)
        self.assertLessEqual(shown, {p['productId'] for p in HANOI})
        # Id lạ chỉ còn chữ; mọi link trỏ tới thẻ thật; số do code điền.
        self.assertNotIn('product:invented', response['question'])
        self.assertTrue(all(pid in shown for pid in re.findall(r'\(product:([^)]+)\)', response['question'])))
        # Điểm, lượt đánh giá và giá nằm trên thẻ, không vào câu chat (người dùng không hỏi giá).
        self.assertNotIn('1.139', response['question'])
        self.assertNotIn('[[', response['question'])
        self.assertNotIn('đ', ''.join(re.findall(r'\d[\d.]*\s*đ', response['question'])))
        self.assertTrue(response['question'].rstrip().endswith('Bạn có muốn mình lên lịch Hà Nội không?'))
        self.assertTrue(any('Lên lịch Hà Nội' in chip for chip in response['suggestions']))
        self.assertEqual(result['pending_offer'], {'destination': 'Hà Nội'})
        self.assertEqual(result['validation_issues'], [])
        # Không gọi `extract`: tên nơi tra thẳng trong catalog, và điểm đến vẫn được ghi cho chuyến.
        self.assertNotIn('Extraction', llm.calls)
        self.assertEqual(result['intent']['destination'], 'Hà Nội')
        self.assertEqual(response['knownIntent']['destination'], 'Hà Nội')

    async def test_a_named_place_without_a_city_takes_its_destination_from_the_catalog(self):
        # LLM thật 4/4 lần không suy ra Hà Nội từ "Văn Miếu" ở `extract` (2026-10-10): điểm đến lấy từ sản phẩm khớp tên.
        van_mieu = product('vm', destination='Hà Nội', name='Văn Miếu – Quốc Tử Giám',
                           attributes={'openingHours': '08:00–17:00, 18:00–22:00'})
        clients = Clients(products=[dict(item) for item in HANOI] + [van_mieu], destinations=['Hà Nội', 'Đà Nẵng'])
        llm = ExploringLlm(route='explore', explore_message='[Văn Miếu – Quốc Tử Giám](product:vm) mở 08:00–17:00.')
        result = await self.run_graph(llm, clients, state={'query': 'Văn Miếu buổi tối có mở không?'})
        path = [event['node'] for event in result['events']]
        self.assertNotIn('extract', path)
        self.assertEqual(result['intent']['destination'], 'Hà Nội')
        self.assertEqual(result['response']['searchResults']['attraction'][0]['productId'], 'vm')
        self.assertIn('18:00–22:00', llm.prompts['ExploreNarration'])

    async def test_the_catalog_city_of_a_named_place_wins_over_the_city_the_llm_guessed(self):
        # LLM thật gán "văn miếu vé vào cửa nhiu" cho Đà Nẵng vì lượt trước nói về Bà Nà (2026-10-11).
        van_mieu = product('vm', destination='Hà Nội', name='Văn Miếu – Quốc Tử Giám', unitPrice=30_000)
        clients = Clients(products=[dict(item) for item in HANOI] + [van_mieu], destinations=['Hà Nội', 'Đà Nẵng'])
        llm = ExploringLlm(turn=TurnRoute(route='explore', place='Văn Miếu – Quốc Tử Giám', city='Đà Nẵng',
                                          price='asks'),
                           explore_message='[Văn Miếu – Quốc Tử Giám](product:vm) là quần thể di tích.')
        result = await self.run_graph(llm, clients, state={'query': 'văn miếu vé vào cửa nhiu'})
        self.assertEqual(result['intent']['destination'], 'Hà Nội')
        self.assertEqual([p['productId'] for p in result['response']['searchResults']['attraction']], ['vm'])
        self.assertIn('Giá vé từ 30.000 ₫.', result['response']['question'])

    async def test_a_link_with_another_cards_id_is_pointed_back_to_the_card_it_names(self):
        clients = self.clients()
        llm = ExploringLlm(route='explore', explore_message='Hà Nội hợp đi bộ.\n[Nơi ho](product:ho) đẹp về đêm.\n'
                                                            '[Nơi solare](product:ho) hợp nghỉ ngơi.')
        result = await self.run_graph(llm, clients, state={'query': 'Hà Nội có gì?'})
        question = result['response']['question']
        self.assertIn('[Nơi solare](product:solare) hợp nghỉ ngơi.', question)
        self.assertEqual(question.count('product:solare'), 1)

    async def test_a_skipped_card_is_inserted_in_card_order_and_a_spaced_link_still_counts(self):
        clients = self.clients()
        llm = ExploringLlm(route='explore', explore_message='Hà Nội hợp đi bộ.\n[Nơi lang](product: lang) cổ kính.\n'
                                                            '[Nơi solare](product:solare) hợp nghỉ ngơi.')
        result = await self.run_graph(llm, clients, state={'query': 'Hà Nội có gì?'})
        lines = result['response']['question'].split('\n')
        ids = [re.search(r'\(product:([^)]+)\)', line).group(1) for line in lines if '(product:' in line]
        self.assertEqual(ids, [card['productId'] for products in result['response']['searchResults'].values()
                               for card in products])
        self.assertEqual(len(ids), len(set(ids)))

    async def test_a_bare_link_line_gets_the_code_line(self):
        clients = self.clients()
        llm = ExploringLlm(route='explore', explore_message='Hà Nội hợp đi bộ.\n[Nơi solare](product:solare)')
        result = await self.run_graph(llm, clients, state={'query': 'Hà Nội có gì?'})
        line = next(line for line in result['response']['question'].split('\n') if 'product:solare' in line)
        self.assertEqual(line, '[Nơi solare](product:solare): khách sạn có hồ bơi, được du khách khen nhiều.')

    def test_hotel_features_read_naturally(self):
        from src.backend.app.agents.steps.exploration import _hotel_features
        hotel = place('ks', 'hotel', attributes={'amenities': ['Hồ bơi ngoài trời', 'Bữa sáng', 'Phòng gia đình']})
        self.assertEqual(_hotel_features(hotel, 'giá mềm'),
                         'khách sạn có hồ bơi, bữa sáng, hợp gia đình có trẻ nhỏ, giá mềm')

    async def test_an_unknown_place_goes_back_to_extract_and_is_asked_again(self):
        clients = self.clients()
        llm = ExploringLlm(route='explore', extraction=Extraction(patch={'destination': 'Bangkok'}))
        result = await self.run_graph(llm, clients, state={'query': 'Bangkok có gì vui?'})
        path = [event['node'] for event in result['events']]
        self.assertEqual(path[:4], ['intake', 'classify', 'explore', 'extract'])
        self.assertIn('clarify', path)
        self.assertEqual(result['response']['missingFields'], ['destination'])
        self.assertIsNone(result['intent']['destination'])

    async def test_a_failed_narration_still_answers_with_a_code_written_line_per_card(self):
        clients = self.clients()
        llm = ExploringLlm(route='explore', extraction=Extraction(patch={'destination': 'Hà Nội'}))
        result = await self.run_graph(llm, clients, state={'query': 'Hà Nội có gì?'})
        question = result['response']['question']
        shown = [p['productId'] for products in result['response']['searchResults'].values() for p in products]
        for pid in shown:
            self.assertIn(f'(product:{pid})', question)
        self.assertEqual(result['validation_issues'], [])

    async def test_a_pool_question_only_counts_hotels_with_a_pool_and_says_so(self):
        clients = self.clients()
        llm = ExploringLlm(route='explore', extraction=Extraction(patch={'destination': 'Hà Nội'}))
        result = await self.run_graph(llm, clients, state={'query': 'khách sạn nào ở Hà Nội có hồ bơi?'})
        hotels = result['response']['searchResults']['hotel']
        self.assertEqual({p['productId'] for p in hotels}, {'charm', 'solare'})
        self.assertNotIn('attraction', result['response']['searchResults'])
        self.assertIn('hồ bơi', result['response']['question'])

    async def test_yes_after_the_offer_starts_planning_with_one_question_and_no_form(self):
        store = InMemoryConversationStore()
        clients = self.clients()
        first = await self.run_graph(ExploringLlm(route='explore', extraction=Extraction(patch={'destination': 'Hà Nội'})),
                                     clients, store=store, owner='u', state={'query': 'Hà Nội có gì?',
                                                                             'start_date_asked': False})
        cid = first['conversation_id']
        again = await self.run_graph(ExploringLlm(route='explore', extraction=Extraction()), clients, store=store,
                                     owner='u', state={'query': 'tối ở Hà Nội đi đâu?', 'conversation_id': cid})
        # Lượt khám phá sau cùng điểm đến: không hỏi lại bằng câu, chỉ giữ nút, và không lặp nút lượt trước.
        self.assertNotIn('Bạn có muốn mình lên lịch', again['response']['question'])
        self.assertFalse(set(again['response']['suggestions']) & set(first['response']['suggestions'])
                         - {chip for chip in first['response']['suggestions'] if 'Lên lịch' in chip})
        yes = await self.run_graph(ExploringLlm(route='vague', extraction=Extraction()), clients, store=store,
                                   owner='u', state={'query': 'ok', 'conversation_id': cid})
        self.assertTrue(yes['plan_consent'])
        self.assertEqual(yes['response']['status'], 'NEEDS_CLARIFICATION')
        self.assertNotIn('clarificationForm', yes['response'])
        self.assertIn('days', yes['response']['missingFields'])

    async def test_not_knowing_twice_lets_the_assistant_pick_and_explore_a_place(self):
        clients = Clients(products=[dict(item, destination='Đà Nẵng') for item in HANOI], destinations=['Đà Nẵng'])
        result = await self.run_graph(ExploringLlm(route='vague'), clients,
                                      state={'query': 'không biết', 'dont_know_count': 1})
        self.assertIn('searchResults', result['response'])
        self.assertEqual(result['pending_offer'], {'destination': 'Đà Nẵng'})
        self.assertIsNone(result['intent']['destination'])  # trợ lý tự chọn: chưa ghi vào chuyến

    async def test_a_question_about_a_place_while_planning_keeps_the_trip_and_offers_to_continue(self):
        clients = self.clients()
        intent = {**empty_intent(), 'destination': 'Hà Nội', 'days': 3}
        llm = ExploringLlm(route='explore', explore_message='[Nơi ho](product:ho) vui.',
                           explore_suggestions=['Lên lịch Hà Nội 3 ngày', 'Tối ở Hà Nội đi đâu?'])
        result = await self.run_graph(llm, clients,
                                      state={'query': 'Hà Nội có gì vui?', 'plan_consent': True, 'intent': intent})
        self.assertEqual(result['intent'], intent)
        self.assertIn('Tiếp tục lập lịch', result['response']['suggestions'])
        self.assertNotIn('Lên lịch Hà Nội 3 ngày', result['response']['suggestions'])
        self.assertIn('Tiếp tục lập lịch', result['response']['question'])
        self.assertNotIn('clarificationForm', result['response'])


if __name__ == '__main__':
    unittest.main()


class NearestFlightDateTests(unittest.TestCase):
    """Ngày đã chọn không có chuyến bay: gợi ý ngày gần nhất có vé, giữ số ngày (kịch bản bản 5, cảnh 10)."""

    @staticmethod
    def flight(pid, day, trip='oneWay', back=None, price=700_000):
        attributes = {'departureAt': f'{day}T21:00:00+07:00', 'tripType': trip}
        if back:
            attributes['returnDate'] = back
        return product(pid, taxonomy='flight', unitPrice=price, attributes=attributes)

    def test_complete_pairs_come_before_closer_one_way_dates(self):
        from datetime import date
        from src.backend.app.domain.itinerary.flights import nearest_dates
        # Như dữ liệu thật tháng 10: 17/10 không có chuyến; 14/10 chỉ có chiều đi; 20/10 có vé khứ hồi về 24/10.
        options = {'status': None, 'outbound': [self.flight('o14', '2026-10-14', price=705_000),
                                                self.flight('rt20', '2026-10-20', 'roundTrip', '2026-10-22', 1_663_000)],
                   'return': [self.flight('r21', '2026-10-21')]}
        intent = {**empty_intent(), 'startDate': '2026-10-17', 'days': 3}
        found = nearest_dates(options, intent, date(2026, 10, 10))
        self.assertEqual([(item['startDate'], item['complete']) for item in found],
                         [('2026-10-20', True), ('2026-10-14', False)])

    def test_past_dates_and_the_chosen_date_are_never_suggested(self):
        from datetime import date
        from src.backend.app.domain.itinerary.flights import nearest_dates
        options = {'status': None, 'outbound': [self.flight('old', '2026-10-09'), self.flight('same', '2026-10-17')],
                   'return': []}
        intent = {**empty_intent(), 'startDate': '2026-10-17', 'days': 3}
        self.assertEqual(nearest_dates(options, intent, date(2026, 10, 10)), [])

    def test_the_flight_warning_names_the_nearest_dates(self):
        from src.backend.app.agents.steps import composition
        options = {'status': None, 'origin': 'TP. Hồ Chí Minh',
                   'outbound': [self.flight('rt', '2999-10-20', 'roundTrip', '2999-10-22')], 'return': []}
        state = {'language': 'vi', 'flight_options': options,
                 'intent': {**empty_intent(), 'destination': 'Hà Nội', 'origin': 'TP. Hồ Chí Minh',
                            'startDate': '2999-10-17', 'days': 3}}
        warning = composition._flight_warning(state, 'NO_FLIGHT_ON_DATES', [])
        self.assertIn('Ngày gần nhất có vé: đi 20/10/2999, về 22/10/2999 (đủ hai chiều).', warning['message'])
        self.assertIn('"đổi sang 20/10"', warning['message'])


class RejectedPlaceTests(unittest.TestCase):
    """Nơi bị chê không được gợi ý lại; trợ lý chọn nơi khác thay vì hỏi lại (kịch bản, luật 7)."""

    def offered(self, query, **fields):
        return {**intake_node({'query': query}), 'pending_offer': {'destination': 'Đà Nẵng'},
                'offered_destinations': ['Đà Nẵng'], 'intent': {**empty_intent(), 'destination': 'Đà Nẵng'}, **fields}

    def test_naming_a_suggested_place_with_a_complaint_rejects_it_and_explores_another(self):
        result = route_result(self.offered('chán, Đà Nẵng đi rồi'), TurnRoute(route='conversation'))
        self.assertEqual(result['rejected_destinations'], ['Đà Nẵng'])
        self.assertEqual((result['decision'], result['explore_pick']), ('explore', True))
        self.assertIsNone(result['pending_offer'])
        self.assertIsNone(result['intent']['destination'])

    def test_asking_for_somewhere_else_rejects_the_offered_place(self):
        result = route_result(self.offered('chỗ khác đi'), TurnRoute(route='conversation'))
        self.assertEqual(result['rejected_destinations'], ['Đà Nẵng'])

    def test_switching_place_is_not_a_complaint(self):
        result = route_result(self.offered('Thôi, Hà Nội thì sao?'), TurnRoute(route='travel'))
        self.assertNotIn('rejected_destinations', result)

    def test_asking_again_about_a_rejected_place_means_the_user_changed_their_mind(self):
        state = {**intake_node({'query': 'Đà Nẵng có gì?'}), 'rejected_destinations': ['Đà Nẵng']}
        self.assertEqual(route_result(state, TurnRoute(route='explore'))['rejected_destinations'], [])

    def test_a_rejected_place_is_skipped_when_choosing_and_in_the_buttons(self):
        from src.backend.app.agents.steps.exploration import destination_for
        state = {**intake_node({'query': 'chán, Đà Nẵng đi rồi'}), 'explore_pick': True,
                 'rejected_destinations': ['Đà Nẵng']}
        self.assertEqual(destination_for(state, ['Đà Nẵng', 'Hà Nội']), 'Hà Nội')
        kept = checked_suggestions(['Đà Nẵng có biển đẹp không?', 'Sa Pa còn gì nữa?'], [], [],
                                   destinations=['Đà Nẵng', 'Sa Pa'], avoid=['Đà Nẵng'])
        self.assertEqual(kept, ['Sa Pa còn gì nữa?'])


class HotelPreferenceTests(unittest.TestCase):
    """Sở thích khách sạn là ưu tiên, không bắt buộc (FR-AGT-06): kéo khách sạn hợp lên, không loại hết."""

    @staticmethod
    def hotel(pid, *amenities):
        return place(pid, 'hotel', attributes={'amenities': list(amenities)})

    def test_stated_preferences_read_only_what_follows_the_word_prefer(self):
        from src.backend.app.domain.itinerary import preferences
        keys = [p.key for p in preferences.stated_preferences(
            'Lên lịch 3 ngày tại Hà Nội, cho 2 người lớn và 1 trẻ em, ưu tiên khách sạn có Hồ bơi, Spa.')]
        self.assertEqual(keys, ['pool', 'spa'])
        self.assertEqual(preferences.stated_preferences('không cần hồ bơi'), [])

    def test_the_soft_filter_keeps_matching_hotels_only_when_enough_remain(self):
        from src.backend.app.domain.itinerary import preferences
        pool = [preferences.by_key('pool')]
        many = [self.hotel(f'p{i}', 'Hồ bơi ngoài trời') for i in range(3)] + [self.hotel('dry', 'Wi-Fi')]
        self.assertEqual([h['productId'] for h in preferences.preferred(many, pool)], ['p0', 'p1', 'p2'])
        few = [self.hotel('p0', 'Hồ bơi ngoài trời'), self.hotel('dry', 'Wi-Fi'), self.hotel('dry2', 'Wi-Fi')]
        self.assertEqual(len(preferences.preferred(few, pool)), 3)

    def test_a_preference_in_the_form_sentence_stays_soft_even_when_the_llm_makes_it_required(self):
        state = {**intake_node({'query': 'Lên lịch trình 3 ngày tại Hà Nội, ưu tiên khách sạn có Hồ bơi.'}),
                 'plan_consent': True}
        result = extract_result(state, Extraction(patch={'destination': 'Hà Nội', 'days': 3},
                                                  constraints={'hotel_attributes': {'pool': True}}))
        self.assertIn('Hồ bơi', result['intent']['interests'])
        self.assertNotIn('pool', (result['constraints'].get('hotel_attributes') or {}))

    def test_preferences_go_into_the_hotel_query_but_not_the_attraction_query(self):
        from src.backend.app.domain.itinerary.search_hints import retrieval_hints
        hints = retrieval_hints({**empty_intent(), 'interests': ['Hồ bơi', 'ẩm thực']}, {})
        self.assertIn('hồ bơi', hints['hotel'])
        self.assertEqual(hints['attraction'], ['ẩm thực'])

    def test_evaluate_drops_non_matching_hotels_only_when_enough_matching_ones_exist(self):
        from src.backend.app.agents.steps.evaluation import _preferred_stays
        hotels = [self.hotel(f'p{i}', 'Hồ bơi ngoài trời') for i in range(3)] + [self.hotel('dry', 'Wi-Fi')]
        candidates = {h['productId']: h for h in hotels + [place('sight')]}
        sources = {pid: 'SEARCH' for pid in candidates}
        state = {'intent': {**empty_intent(), 'interests': ['Hồ bơi']}}
        kept, kept_sources = _preferred_stays(state, candidates, sources)
        self.assertEqual(sorted(kept), ['p0', 'p1', 'p2', 'sight'])
        self.assertEqual(sorted(kept_sources), sorted(kept))

    def test_the_form_offers_the_preferences_and_ticks_kid_friendly_for_children(self):
        from src.backend.app.agents.steps.conversation import clarification_form
        state = {'intent': {**empty_intent(), 'destination': 'Hà Nội', 'interests': ['Hồ bơi', 'ẩm thực'],
                            'party': {'type': 'FAMILY_WITH_KIDS', 'adults': 2, 'children': 1}}}
        form = clarification_form(state)
        self.assertEqual(form['fields'][-1], 'interests')
        self.assertIn('Spa', form['interestOptions'])
        self.assertEqual(form['defaults']['interests'], ['ẩm thực', 'Hồ bơi', 'Phù hợp trẻ nhỏ'])


class PlanChipTests(unittest.TestCase):
    def test_a_complete_trip_gets_no_forced_continue_button(self):
        from src.backend.app.agents.steps.exploration import _plan_chip
        complete = {**empty_intent(), 'destination': 'Hà Nội', 'days': 3, 'startDate': '2999-10-10',
                    'party': {'type': 'COUPLE', 'adults': 2, 'children': 0}}
        self.assertIsNone(_plan_chip({'plan_consent': True, 'intent': complete, 'language': 'vi'}, 'Hà Nội'))
        partial = {**complete, 'startDate': None}
        self.assertEqual(_plan_chip({'plan_consent': True, 'intent': partial, 'language': 'vi'}, 'Hà Nội'),
                         'Tiếp tục lập lịch')
        self.assertEqual(_plan_chip({'intent': partial, 'language': 'vi'}, 'Hà Nội'), 'Lên lịch Hà Nội cho mình')


class ExploreSearchFailureTests(unittest.IsolatedAsyncioTestCase):
    run_graph = runtime.RuntimeTests.run_graph

    async def test_a_failed_search_says_it_could_not_load_not_that_nothing_exists(self):
        # LLM thật 10/10: Search quá giờ lúc backend mới khởi động, trợ lý nói "chưa tìm thấy chỗ nào trong dữ liệu".
        from src.backend.app.application.ports.itinerary_tools import ToolError
        clients = Clients(products=[dict(item) for item in HANOI], destinations=['Hà Nội'],
                          search_error=ToolError('SEARCH_UNAVAILABLE', retryable=True))
        result = await self.run_graph(ExploringLlm(route='explore', extraction=Extraction(patch={'destination': 'Hà Nội'})),
                                      clients, state={'query': 'Hà Nội có gì?'})
        self.assertIn('chưa tải được', result['response']['question'])
        self.assertNotIn('searchResults', result['response'])
