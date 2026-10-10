"""Hỏi về một nơi cụ thể chỉ trả lời nơi đó (chat thử 10/10, kịch bản bản 5 cảnh 9).

"Văn Miếu buổi tối có mở không?" từng ra thẻ Văn Miếu kèm Hồ Hoàn Kiếm và hai khách sạn: thẻ chung làm lệch câu trả lời.
"""
import unittest

from src.backend.app.agents.nodes import intake_node
from src.backend.app.agents.steps.exploration import NAMED_CALL_ID, asked_only, explore_input, explored, pick
from src.backend.app.agents.models import ExploreNarration
from src.backend.app.domain.itinerary import exploration as rules
from src.backend.app.domain.itinerary.planning import empty_intent

from . import test_itinerary_runtime as runtime
from .test_exploration import HANOI, ExploringLlm, place
from .test_itinerary_runtime import Clients, product

VAN_MIEU = product('vm', destination='Hà Nội', name='Văn Miếu – Quốc Tử Giám', reviewCount=361,
                   attributes={'openingHours': '08:00–17:00, 18:00–22:00', 'ticketed': False})


def _results():
    return [{'tool_call_id': 'explore-0-hotel', 'data': {'results': [place('charm', 'hotel', unitPrice=220_014)]}},
            {'tool_call_id': 'explore-1-attraction', 'data': {'results': [place('ho', reviewCount=1139)]}},
            {'tool_call_id': NAMED_CALL_ID, 'data': {'results': [VAN_MIEU]}}]


def _state(query, **extra):
    return {**intake_node({'query': query}), 'intent': {**empty_intent(), 'destination': 'Hà Nội'},
            'conversation_id': 'c1', **extra}


class AskedPlaceCardsTests(unittest.TestCase):
    def test_a_question_about_one_place_returns_only_that_place(self):
        cards, filtered_by = pick(_state('Văn Miếu buổi tối có mở không?'), 'Hà Nội', _results())
        self.assertEqual([(card['product']['productId'], card['reasons']) for card in cards], [('vm', [rules.ASKED])])
        self.assertIsNone(filtered_by)

    def test_asking_around_a_place_still_suggests_other_places(self):
        cards, _ = pick(_state('gần Văn Miếu có gì chơi?'), 'Hà Nội', _results())
        self.assertEqual(cards[0]['product']['productId'], 'vm')
        self.assertGreater(len(cards), 1)

    def test_asking_around_a_place_lists_the_nearest_sights_without_it_or_hotels(self):
        anchor = {**VAN_MIEU, 'attributes': {**VAN_MIEU['attributes'], 'latitude': 21.0277, 'longitude': 105.8355}}
        near = place('hoang-thanh', reviewCount=200, attributes={'latitude': 21.0353, 'longitude': 105.8400})
        far = place('far', reviewCount=900, attributes={'latitude': 21.2000, 'longitude': 105.9000})
        results = [{'tool_call_id': 'explore-0-hotel', 'data': {'results': [place('charm', 'hotel', unitPrice=1)]}},
                   {'tool_call_id': 'explore-1-attraction', 'data': {'results': [near, far]}},
                   {'tool_call_id': NAMED_CALL_ID, 'data': {'results': [anchor]}}]
        cards, _ = pick(_state('Gần Văn Miếu có gì nữa?'), 'Hà Nội', results)
        self.assertEqual([(card['product']['productId'], card['reasons']) for card in cards],
                         [('hoang-thanh', [rules.NEAR])])

    def test_a_hotel_question_naming_a_place_still_lists_hotels(self):
        cards, _ = pick(_state('khách sạn gần Văn Miếu'), 'Hà Nội', _results())
        self.assertIn('hotel', {card['product']['taxonomy'] for card in cards})

    def test_the_llm_is_told_to_answer_the_question_first(self):
        state = _state('Văn Miếu buổi tối có mở không?')
        cards, _ = pick(state, 'Hà Nội', _results())
        self.assertTrue(asked_only(state, cards))
        payload = explore_input(state, 'Hà Nội', cards, None, ['Hà Nội'])[1][1]
        self.assertIn('asked_only: true', payload)
        self.assertIn('08:00–17:00, 18:00–22:00', payload)

    def test_buttons_lead_on_around_the_place_and_the_city_not_to_hotels(self):
        state = _state('Văn Miếu buổi tối có mở không?')
        cards, _ = pick(state, 'Hà Nội', _results())
        narration = ExploreNarration(title='Văn Miếu buổi tối',
                                     message='Có, [Văn Miếu – Quốc Tử Giám](product:vm) mở buổi tối 18:00–22:00.',
                                     suggestions=[])
        response = explored(state, 'Hà Nội', cards, None, narration, ['Hà Nội'])['response']
        self.assertEqual(list(response['searchResults']), ['attraction'])
        self.assertIn('Gần Văn Miếu có gì nữa?', response['suggestions'])
        self.assertFalse(any('Khách sạn' in chip for chip in response['suggestions']))

    def test_short_name_is_the_part_people_say(self):
        self.assertEqual(rules.short_name(VAN_MIEU), 'Văn Miếu')


class AskedPlaceFlowTests(unittest.IsolatedAsyncioTestCase):
    run_graph = runtime.RuntimeTests.run_graph

    async def test_the_reply_shows_only_the_asked_place(self):
        clients = Clients(products=[dict(item) for item in HANOI] + [dict(VAN_MIEU)], destinations=['Hà Nội'])
        llm = ExploringLlm(route='explore',
                           explore_message='Có, [Văn Miếu – Quốc Tử Giám](product:vm) mở buổi tối 18:00–22:00.')
        result = await self.run_graph(llm, clients, state={'query': 'Văn Miếu buổi tối có mở không?'})
        response = result['response']
        shown = [p['productId'] for products in response['searchResults'].values() for p in products]
        self.assertEqual(shown, ['vm'])
        self.assertNotIn('product:ho', response['question'])
        self.assertEqual(result['validation_issues'], [])


if __name__ == '__main__':
    unittest.main()
