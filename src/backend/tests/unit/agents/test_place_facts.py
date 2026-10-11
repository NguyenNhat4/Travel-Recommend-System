"""Hỏi về một nơi bằng tên dân gian, gõ sai: tra đúng nơi trong catalog, không bịa giờ, giá (chat thử 16 kiểu, M03).

"văn miếu tối mở ko b" từng ra "Văn Miếu không mở cửa buổi tối" (sai: catalog ghi 18:00–22:00): Search bằng nguyên câu
ra 0 kết quả (chữ "ko" bị hiểu là phủ định), rồi `converse` (LLM) tự trả lời. "lăng bác", "hồ gươm" không khớp tên
catalog. Nay `classify` (LLM) đọc ra tên nơi thường dùng và thành phố (`explore_place`, `explore_city`); code tìm nơi đó
và đối chiếu tên với catalog. Test giả lập phần LLM hiểu.
"""
import unittest

from src.backend.app.agents.models import ConversationalAnswer
from src.backend.app.agents.nodes import intake_node
from src.backend.app.agents.steps import conversation, exploration
from src.backend.app.agents.steps.exploration import NAMED_CALL_ID, pick, place_query
from src.backend.app.domain.itinerary import exploration as rules
from src.backend.app.domain.itinerary.planning import empty_intent

from .test_itinerary_runtime import product

LANG = product('lang', destination='Hà Nội', name='Lăng Chủ tịch Hồ Chí Minh', reviewCount=900, unitPrice=None,
               attributes={'openingHours': '08:00–11:00'})
HO = product('ho', destination='Hà Nội', name='Hồ Hoàn Kiếm', reviewCount=1139, unitPrice=None)
CITIES = ['Hà Nội', 'TP. Hồ Chí Minh', 'Hội An']


def _state(query, **understood):
    return {**intake_node({'query': query}), 'intent': {**empty_intent(), 'destination': 'Hà Nội'},
            'conversation_id': 'c1', **understood}


class PlaceSearchTests(unittest.TestCase):
    def test_the_place_search_uses_the_understood_name_without_city_names(self):
        # Search hiểu "Hồ Chí Minh" trong tên là điểm đến TP. Hồ Chí Minh: bỏ tên thành phố khỏi câu tìm.
        state = _state('lăng bác mấy giờ mở cửa vậy', explore_place='Lăng Chủ tịch Hồ Chí Minh')
        self.assertEqual(place_query(state, CITIES), 'Lăng Chủ tịch')
        self.assertEqual(place_query(_state('x', explore_place='Khu Phố Cổ Hà Nội'), CITIES), 'Khu Phố Cổ')
        self.assertEqual(place_query(_state('x', explore_place='Bưu điện trung tâm Sài Gòn'), CITIES),
                         'Bưu điện trung tâm')
        self.assertEqual(place_query(_state('x', explore_place='Văn Miếu – Quốc Tử Giám'), CITIES),
                         'Văn Miếu – Quốc Tử Giám')
        # Không đọc ra nơi nào thì tìm bằng nguyên câu.
        self.assertEqual(place_query(_state('Văn Miếu buổi tối có mở không?'), CITIES), 'Văn Miếu buổi tối có mở không?')

    def test_the_understood_name_picks_only_that_place(self):
        results = [{'tool_call_id': 'explore-1-attraction', 'data': {'results': [HO]}},
                   {'tool_call_id': NAMED_CALL_ID, 'data': {'results': [LANG, HO]}}]
        state = _state('lăng bác mấy giờ mở cửa vậy', explore_place='Lăng Chủ tịch Hồ Chí Minh')
        cards, _ = pick(state, 'Hà Nội', results)
        self.assertEqual([(card['product']['productId'], card['reasons']) for card in cards], [('lang', [rules.ASKED])])
        cards, _ = pick(_state('hồ gươm có mất vé ko', explore_place='Hồ Hoàn Kiếm'), 'Hà Nội', results)
        self.assertEqual([card['product']['productId'] for card in cards], ['ho'])

    def test_a_close_but_not_exact_name_still_finds_the_place(self):
        self.assertEqual(rules.closest_named([HO, LANG], 'Lăng Bác Hồ')['productId'], 'lang')
        # Một từ chung ("lăng") không đủ.
        self.assertIsNone(rules.closest_named([LANG], 'Lăng Dục Đức'))
        self.assertIsNone(rules.closest_named([LANG], 'Lăng'))


class UnderstoodCityTests(unittest.TestCase):
    def test_the_city_of_the_asked_place_wins_over_the_city_being_discussed(self):
        state = _state('chợ bến thành mở tới mấy giờ', explore_city='Sài Gòn')
        self.assertEqual(exploration.destination_for(state, CITIES), 'TP. Hồ Chí Minh')

    def test_a_city_outside_the_catalog_is_ignored(self):
        state = _state('tokyo có gì chơi', explore_city='Tokyo')
        self.assertEqual(exploration.destination_for(state, CITIES), 'Hà Nội')

    def test_focus_and_price_come_from_what_the_llm_understood(self):
        self.assertTrue(exploration.hotel_focus(_state('khách sạn', explore_focus='hotels')))
        self.assertTrue(exploration.hotel_focus(_state('rẻ nhất là chỗ nào', explore_focus='hotels')))
        self.assertFalse(exploration.hotel_focus(_state('chỗ nào đi chơi được', explore_focus='sights')))
        self.assertTrue(exploration.price_asked(_state('hồ gươm có mất vé ko', explore_price='asks')))
        self.assertFalse(exploration.price_asked(_state('hồ gươm có gì đẹp')))


class AskedPlaceAnswerTests(unittest.TestCase):
    def test_a_public_place_tells_the_llm_there_is_no_ticket_to_buy(self):
        item = exploration._card_input({'product': HO, 'reasons': [rules.ASKED]})
        self.assertEqual(item['facts'].get('entry'), 'free_no_ticket_sold')
        lang = exploration._card_input({'product': LANG, 'reasons': [rules.ASKED]})
        self.assertEqual(lang['facts']['openingHours'], '08:00–11:00')
        priced = exploration._card_input({'product': {**LANG, 'unitPrice': 30_000}, 'reasons': [rules.ASKED]})
        self.assertNotIn('entry', priced['facts'])
        self.assertEqual(priced['facts']['ticketPrice'], 'từ 30.000 ₫')

    def test_a_priceless_sight_is_free_to_visit(self):
        self.assertEqual(exploration._price_text(_state('x'), HO), 'tham quan tự do')

    def test_a_ticket_price_question_gets_the_price_even_when_the_llm_leaves_it_out(self):
        vm = product('vm', destination='Hà Nội', name='Văn Miếu – Quốc Tử Giám', unitPrice=299_000)
        cards = [{'product': vm, 'reasons': [rules.ASKED]}]
        state = _state('văn miếu vé vào cửa bao nhiêu', explore_price='asks')
        text = exploration._with_asked_price(state, '[Văn Miếu – Quốc Tử Giám](product:vm) là quần thể lịch sử.', cards)
        filled = exploration._fill(state, text, {'vm': vm})
        self.assertEqual(filled, '[Văn Miếu – Quốc Tử Giám](product:vm) là quần thể lịch sử. Giá vé từ 299.000 ₫.')
        # Không hỏi giá thì không thêm.
        self.assertNotIn('[[price', exploration._with_asked_price(_state('văn miếu tối mở ko'), 'x (product:vm)', cards))

    def test_a_card_named_without_a_link_is_linked_in_place_not_repeated(self):
        vm = product('vm', destination='Hà Nội', name='Văn Miếu – Quốc Tử Giám')
        body = 'Có, Văn Miếu – Quốc Tử Giám mở buổi tối 18:00–22:00. Không gian cổ kính.'
        text = exploration._ensure_cards(_state('văn miếu tối mở ko'), body, [{'product': vm, 'reasons': [rules.ASKED]}])
        self.assertEqual(text, 'Có, [Văn Miếu – Quốc Tử Giám](product:vm) mở buổi tối 18:00–22:00. Không gian cổ kính.')


class CheapFirstTests(unittest.TestCase):
    def test_wanting_cheap_places_lists_the_cheapest_hotels_first(self):
        hotels = [product(name, taxonomy='hotel', destination='Hà Nội', unitPrice=price, reviewCount=reviews)
                  for name, price, reviews in (('dear', 2_998_800, 5000), ('mid', 448_875, 10), ('low', 261_000, 3))]
        cards = exploration._hotel_cards(_state('khách sạn gần phố cổ giá rẻ', explore_price='cheap'), hotels, 2)
        self.assertEqual([(card['product']['productId'], card['reasons']) for card in cards],
                         [('low', [rules.CHEAPEST]), ('mid', [rules.LOW_PRICE])])
        # Không đòi rẻ: mỗi thẻ một lý do như trước.
        plain = exploration._hotel_cards(_state('khách sạn gần phố cổ'), hotels, 2)
        self.assertEqual(plain[0]['reasons'], [rules.CHEAPEST])
        self.assertEqual(plain[1]['product']['productId'], 'dear')

    def test_a_price_after_a_full_stop_is_joined_to_the_sentence(self):
        hotel = product('a', taxonomy='hotel', unitPrice=213_000)
        state = _state('rẻ nhất là chỗ nào', explore_price='cheap')
        self.assertEqual(exploration._fill(state, '[A](product:a) hợp đi xe đạp. [[price:a]]', {'a': hotel}),
                         '[A](product:a) hợp đi xe đạp, từ 213.000 ₫.')


class NameTieTests(unittest.TestCase):
    def test_a_name_matching_places_in_two_cities_equally_is_not_decided(self):
        ha_noi = product('hn', destination='Hà Nội', name='Khu Phố Cổ Hà Nội')
        hoi_an = product('ha', destination='Hội An', name='Phố cổ Hội An')
        self.assertIsNone(rules.closest_named([ha_noi, hoi_an], 'Phố cổ'))
        self.assertEqual(rules.closest_named([ha_noi, hoi_an], 'Phố cổ Hội An')['productId'], 'ha')


class UnfoundPlaceTests(unittest.TestCase):
    def test_a_place_question_that_reaches_converse_gets_the_fixed_cannot_check_reply(self):
        state = {**_state('văn miếu tối mở ko b', explore_place='Văn Miếu – Quốc Tử Giám'), 'interaction_type': 'travel'}
        update = conversation.conversational_update(state, ConversationalAnswer(
            title='Giờ mở cửa Văn Miếu', message='Văn Miếu không mở cửa buổi tối.'))
        question = update['response']['question']
        self.assertNotIn('không mở cửa buổi tối', question)
        self.assertIn('Mình chưa tìm thấy Văn Miếu – Quốc Tử Giám trong dữ liệu hiện có', question)
        self.assertTrue(question.startswith('**Chưa kiểm được thông tin này**'))

    def test_other_conversation_replies_are_kept(self):
        state = {**_state('chào bạn'), 'interaction_type': 'conversation'}
        update = conversation.conversational_update(state, ConversationalAnswer(message='Chào bạn!'))
        self.assertEqual(update['response']['question'], 'Chào bạn!')


if __name__ == '__main__':
    unittest.main()
