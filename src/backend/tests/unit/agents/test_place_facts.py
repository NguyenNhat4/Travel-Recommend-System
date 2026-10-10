"""Không bịa giờ, giá, quy định; nhận tên gọi khác của điểm nổi tiếng (chat thử 16 kiểu người dùng, M03).

"văn miếu tối mở ko b" từng ra "Văn Miếu không mở cửa buổi tối" (sai: catalog ghi 18:00–22:00): Search hiểu "ko" là phủ
định nên câu tìm nơi ra 0 kết quả, rồi `converse` (LLM) tự trả lời. "lăng bác", "hồ gươm" không khớp tên catalog.
"""
import unittest

from src.backend.app.agents.models import ConversationalAnswer
from src.backend.app.agents.nodes import intake_node
from src.backend.app.agents.steps import conversation
from src.backend.app.agents.steps import exploration
from src.backend.app.agents.steps.exploration import NAMED_CALL_ID, pick, place_query
from src.backend.app.domain.itinerary import exploration as rules
from src.backend.app.domain.itinerary.place_aliases import place_named, with_catalog_names
from src.backend.app.domain.itinerary.planning import empty_intent

from .test_itinerary_runtime import product

LANG = product('lang', destination='Hà Nội', name='Lăng Chủ tịch Hồ Chí Minh', reviewCount=900, unitPrice=None,
               attributes={'openingHours': '08:00–11:00'})
HO = product('ho', destination='Hà Nội', name='Hồ Hoàn Kiếm', reviewCount=1139, unitPrice=None)


def _state(query):
    return {**intake_node({'query': query}), 'intent': {**empty_intent(), 'destination': 'Hà Nội'},
            'conversation_id': 'c1'}


class AliasTests(unittest.TestCase):
    def test_folk_names_map_to_catalog_names(self):
        self.assertEqual(place_named('lăng bác mấy giờ mở cửa vậy'), 'Lăng Chủ tịch Hồ Chí Minh')
        self.assertEqual(place_named('HO GUOM co mat ve ko'), 'Hồ Hoàn Kiếm')
        self.assertEqual(place_named('văn miếu tối mở ko b'), 'Văn Miếu – Quốc Tử Giám')
        self.assertIsNone(place_named('Hà Nội có gì chơi?'))
        # Chỉ khớp trọn từ: "bà nà" không khớp trong "bà nàng".
        self.assertIsNone(place_named('bà nàng hay đi đâu'))

    def test_the_question_carries_the_catalog_name_for_name_matching(self):
        self.assertTrue(with_catalog_names('lăng bác mở mấy giờ').endswith('Lăng Chủ tịch Hồ Chí Minh'))
        self.assertEqual(with_catalog_names('Hà Nội có gì?'), 'Hà Nội có gì?')

    def test_the_place_search_uses_the_catalog_name_or_drops_the_question_tail(self):
        self.assertEqual(place_query('lăng bác mấy giờ mở cửa vậy'), 'Lăng Chủ tịch')
        # "ko" làm Search hiểu là phủ định và trả 0 kết quả; tên nơi phải còn nguyên.
        self.assertEqual(place_query('chùa một cột mở ko b'), 'chùa một cột mở')
        self.assertEqual(place_query('Nha Trang có gì không'), 'Nha Trang có gì')

    def test_a_folk_name_question_picks_only_that_place(self):
        results = [{'tool_call_id': 'explore-1-attraction', 'data': {'results': [HO]}},
                   {'tool_call_id': NAMED_CALL_ID, 'data': {'results': [LANG, HO]}}]
        cards, _ = pick(_state('lăng bác mấy giờ mở cửa vậy'), 'Hà Nội', results)
        self.assertEqual([(card['product']['productId'], card['reasons']) for card in cards], [('lang', [rules.ASKED])])
        cards, _ = pick(_state('hồ gươm có mất vé ko'), 'Hà Nội', results)
        self.assertEqual([card['product']['productId'] for card in cards], ['ho'])


class AskedPlaceAnswerTests(unittest.TestCase):
    def test_a_public_place_tells_the_llm_there_is_no_ticket_to_buy(self):
        item = exploration._card_input({'product': HO, 'reasons': [rules.ASKED]})
        self.assertEqual(item['facts'].get('entry'), 'free_no_ticket_sold')
        lang = exploration._card_input({'product': LANG, 'reasons': [rules.ASKED]})
        self.assertEqual(lang['facts']['openingHours'], '08:00–11:00')
        priced = exploration._card_input({'product': {**LANG, 'unitPrice': 30_000}, 'reasons': [rules.ASKED]})
        self.assertNotIn('entry', priced['facts'])
        self.assertEqual(priced['facts']['ticketPrice'], '[[price:lang]]')

    def test_a_ticket_question_counts_as_a_price_question_and_a_priceless_sight_is_free(self):
        state = _state('hồ gươm có mất vé ko')
        self.assertTrue(exploration.price_asked(state))
        self.assertEqual(exploration._price_text(state, HO), 'tham quan tự do')

    def test_a_ticket_price_question_gets_the_price_even_when_the_llm_leaves_it_out(self):
        vm = product('vm', destination='Hà Nội', name='Văn Miếu – Quốc Tử Giám', unitPrice=299_000)
        cards = [{'product': vm, 'reasons': [rules.ASKED]}]
        text = exploration._with_asked_price(_state('văn miếu vé vào cửa bao nhiêu'),
                                             '[Văn Miếu – Quốc Tử Giám](product:vm) là quần thể lịch sử.', cards)
        filled = exploration._fill(_state('văn miếu vé vào cửa bao nhiêu'), text, {'vm': vm})
        self.assertEqual(filled, '[Văn Miếu – Quốc Tử Giám](product:vm) là quần thể lịch sử. Giá vé từ 299.000 ₫.')
        # Không hỏi giá thì không thêm.
        self.assertNotIn('[[price', exploration._with_asked_price(_state('văn miếu tối mở ko'), 'x (product:vm)', cards))

    def test_a_card_named_without_a_link_is_linked_in_place_not_repeated(self):
        vm = product('vm', destination='Hà Nội', name='Văn Miếu – Quốc Tử Giám')
        body = 'Có, Văn Miếu – Quốc Tử Giám mở buổi tối 18:00–22:00. Không gian cổ kính.'
        text = exploration._ensure_cards(_state('văn miếu tối mở ko'), body, [{'product': vm, 'reasons': [rules.ASKED]}])
        self.assertEqual(text, 'Có, [Văn Miếu – Quốc Tử Giám](product:vm) mở buổi tối 18:00–22:00. Không gian cổ kính.')


class PlaceDestinationTests(unittest.TestCase):
    def test_a_famous_place_sets_its_city_even_mid_conversation_about_another(self):
        state = {**_state('chợ bến thành mở tới mấy giờ')}
        self.assertEqual(exploration.destination_for(state, ['Hà Nội', 'TP. Hồ Chí Minh']), 'TP. Hồ Chí Minh')

    def test_a_ticket_question_about_a_famous_place_is_not_vague(self):
        from src.backend.app.agents.steps import fares
        self.assertFalse(fares.vague({'query': 'bà nà vé bao nhiêu'}))
        self.assertTrue(fares.vague({'query': 'có vé nào rẻ đi hn ko bạn'}))
        self.assertFalse(fares.asked({'query': 'văn miếu vé vào cửa bao nhiêu'}))
        self.assertTrue(fares.asked({'query': 'vé máy bay ra Hà Nội bao nhiêu'}))


class InventedFactTests(unittest.TestCase):
    def test_claims_about_hours_prices_or_rules_are_caught(self):
        for text in ('Văn Miếu – Quốc Tử Giám thường mở cửa ban ngày, không mở cửa tham quan buổi tối.',
                     'Tham quan khu vực Hồ Gươm thường không mất vé.', 'Lăng Bác mở từ 7:30 đến 10:30.',
                     'Vé vào cửa khoảng 30.000 đồng.'):
            self.assertTrue(conversation.invents_fact(text), text)
        for text in ('Bạn đi mấy ngày? Ví dụ: 3 ngày, đi 18/10, 2 người lớn, 5 triệu.', 'Chào bạn! Bạn muốn đi đâu?'):
            self.assertFalse(conversation.invents_fact(text), text)

    def test_an_invented_fact_is_replaced_by_the_fixed_cannot_check_reply(self):
        state = {**_state('văn miếu tối mở ko b'), 'interaction_type': 'travel'}
        update = conversation.conversational_update(state, ConversationalAnswer(
            title='Giờ mở cửa Văn Miếu', message='Văn Miếu không mở cửa buổi tối.'))
        question = update['response']['question']
        self.assertNotIn('không mở cửa buổi tối', question)
        self.assertIn('Mình chưa kiểm được giờ mở cửa', question)
        self.assertTrue(question.startswith('**Chưa kiểm được thông tin này**'))


if __name__ == '__main__':
    unittest.main()
