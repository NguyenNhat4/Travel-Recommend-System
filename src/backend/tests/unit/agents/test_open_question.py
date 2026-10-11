"""Nhớ câu hỏi còn dở khi trợ lý phải hỏi lại điểm đến (chat thử 10/10, lỗi G).

"có khách sạn nào có hồ bơi gần phố cổ không?" → trợ lý hỏi phố cổ ở đâu → "hà nội cha ơi" từng ra "Hà Nội có gì" chung
chung thay vì khách sạn có hồ bơi gần phố cổ Hà Nội như kịch bản cảnh 5. Hỏi lại khi tên nơi (LLM đọc ra) khớp nơi ở nhiều
thành phố của catalog, nút là tên các nơi đó; không còn luật riêng cho "phố cổ".
"""
import unittest

from src.backend.app.agents.models import Extraction, TurnRoute
from src.backend.app.agents.nodes import _fare_settled, intake_node
from src.backend.app.agents.steps.exploration import ask_which_place, near_phrase, resumed
from src.backend.app.domain.itinerary.planning import empty_intent
from src.backend.app.infrastructure.persistence.conversation_store import InMemoryConversationStore

from . import test_itinerary_runtime as runtime
from .test_exploration import HANOI, ExploringLlm
from .test_itinerary_runtime import Clients, product

SUPPORTED = ['Hà Nội', 'Hội An', 'Đà Nẵng']
QUESTION = 'có khách sạn nào có hồ bơi gần phố cổ không?'
OLD_QUARTERS = [product('pho-co-hn', destination='Hà Nội', name='Khu Phố Cổ Hà Nội', reviewCount=900),
                product('pho-co-ha', destination='Hội An', name='Phố cổ Hội An', reviewCount=800)]
#: LLM của `classify` hiểu câu hỏi: hỏi chỗ ở gần "phố cổ", không nêu thành phố.
UNDERSTOOD = TurnRoute(route='explore', place='phố cổ', focus='hotels')


def _state(query, **extra):
    return {**intake_node({'query': query}), 'intent': empty_intent(), 'conversation_id': 'c1', **extra}


class RecordingClients(Clients):
    """Ghi lại câu tìm của từng lời gọi Search."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.queries = []

    async def search_products(self, args):
        self.queries.append((args.get('taxonomy'), args.get('query')))
        return await super().search_products(args)


class PendingQuestionRuleTests(unittest.TestCase):
    def test_a_short_reply_naming_a_destination_resumes_the_question(self):
        state, destination = resumed(_state('hà nội cha ơi', open_question=QUESTION,
                                            open_understood={'explore_focus': 'hotels', 'explore_price': 'cheap'},
                                            explore_price='asks'), SUPPORTED)
        self.assertEqual(destination, 'Hà Nội')
        self.assertEqual(state['query'], QUESTION)
        self.assertEqual(state['intent']['destination'], 'Hà Nội')
        # Ý định của câu hỏi gốc đi theo; lượt này đọc ra gì thì thắng.
        self.assertEqual(state['explore_focus'], 'hotels')
        self.assertEqual(state['explore_price'], 'asks')

    def test_a_new_question_or_no_destination_does_not_resume(self):
        long_reply = 'thôi cho mình hỏi Hà Nội có gì chơi vào buổi tối nhé'
        self.assertIsNone(resumed(_state(long_reply, open_question=QUESTION), SUPPORTED)[1])
        self.assertIsNone(resumed(_state('ok', open_question=QUESTION), SUPPORTED)[1])
        self.assertIsNone(resumed(_state('Hà Nội'), SUPPORTED)[1])

    def test_a_place_in_several_cities_is_asked_with_one_button_per_place(self):
        update = ask_which_place(_state(QUESTION, explore_place='phố cổ', explore_focus='hotels'), SUPPORTED,
                                 OLD_QUARTERS)
        self.assertEqual(update['response']['question'], 'Bạn muốn nói Khu Phố Cổ Hà Nội hay Phố cổ Hội An?')
        self.assertEqual(update['response']['suggestions'], ['Khu Phố Cổ Hà Nội', 'Phố cổ Hội An'])
        self.assertEqual(update['open_question'], QUESTION)
        self.assertEqual(update['open_understood'], {'explore_place': 'phố cổ', 'explore_focus': 'hotels'})

    def test_the_place_to_be_near_is_read_from_the_question(self):
        self.assertEqual(near_phrase(QUESTION), 'phố cổ')
        self.assertEqual(near_phrase('khách sạn gần biển Mỹ Khê nhé'), 'biển Mỹ Khê')
        self.assertIsNone(near_phrase('khách sạn có hồ bơi'))

    def test_a_turn_on_another_branch_drops_the_open_question(self):
        state = {'open_question': QUESTION}
        self.assertIsNone(_fare_settled(state, {'decision': 'simple'})['open_question'])
        self.assertNotIn('open_question', _fare_settled(state, {'decision': 'explore'}))


class NearLandmarkTests(unittest.TestCase):
    def test_hotels_near_the_old_quarter_are_those_within_the_radius_of_it(self):
        from src.backend.app.agents.steps.exploration import NEAR_CALL_ID, pick
        from src.backend.app.domain.itinerary import exploration as rules
        from .test_exploration import place
        quarter = {**place('pho-co', reviewCount=500, attributes={'latitude': 21.0340, 'longitude': 105.8506}),
                   'name': 'Khu Phố Cổ Hà Nội'}
        close = place('close', 'hotel', unitPrice=900_000, attributes={'pool': True, 'latitude': 21.0330,
                                                                        'longitude': 105.8520})
        far = place('far', 'hotel', unitPrice=500_000, attributes={'pool': True, 'latitude': 21.0700,
                                                                    'longitude': 105.8200})
        results = [{'tool_call_id': 'explore-0-hotel', 'data': {'results': [far, close]}},
                   {'tool_call_id': NEAR_CALL_ID, 'data': {'results': [quarter]}}]
        state = {**_state(QUESTION), 'intent': {**empty_intent(), 'destination': 'Hà Nội'}}
        cards, filtered_by = pick(state, 'Hà Nội', results)
        self.assertEqual([card['product']['productId'] for card in cards], ['close'])
        self.assertIn(rules.NEAR, cards[0]['reasons'])
        self.assertEqual(filtered_by, 'pool')
        from src.backend.app.agents.steps.exploration import explore_input
        self.assertIn('near_place: phố cổ', explore_input(state, 'Hà Nội', cards, filtered_by, ['Hà Nội'])[1][1])

    def test_bold_link_labels_are_unwrapped(self):
        from src.backend.app.agents.steps.exploration import _relinked
        self.assertEqual(_relinked('[**Nơi a**](product:a) đẹp.', {'a': {'name': 'Nơi a'}}), '[Nơi a](product:a) đẹp.')
        self.assertEqual(_relinked('[** Nơi a**](product:a)', {'a': {'name': 'Nơi a'}}), '[Nơi a](product:a)')


class PendingQuestionFlowTests(unittest.IsolatedAsyncioTestCase):
    run_graph = runtime.RuntimeTests.run_graph

    async def test_the_city_reply_answers_the_hotel_question_there(self):
        clients = RecordingClients(products=[dict(item) for item in HANOI + OLD_QUARTERS], destinations=SUPPORTED)
        store = InMemoryConversationStore()
        llm = ExploringLlm(turn=UNDERSTOOD, extraction=Extraction(patch={}))
        first = await self.run_graph(llm, clients, store=store, owner='u', state={'query': QUESTION})
        self.assertEqual(first['response']['suggestions'], ['Khu Phố Cổ Hà Nội', 'Phố cổ Hội An'])
        self.assertEqual(first['open_question'], QUESTION)
        # Lượt trả lời: LLM chỉ đọc ra thành phố; chỗ ở gần "phố cổ" lấy từ câu hỏi còn dở.
        reply = ExploringLlm(turn=TurnRoute(route='explore', city='Hà Nội'), extraction=Extraction(patch={}))
        second = await self.run_graph(reply, clients, store=store, owner='u',
                                      state={'query': 'hà nội cha ơi', 'conversation_id': first['conversation_id']})
        results = second['response']['searchResults']
        self.assertEqual(list(results), ['hotel'])
        self.assertEqual({item['productId'] for item in results['hotel']}, {'charm', 'solare'})  # có hồ bơi
        self.assertIn(('hotel', 'khách sạn có hồ bơi gần phố cổ'), clients.queries)
        self.assertEqual(second['intent']['destination'], 'Hà Nội')
        self.assertIsNone(second['open_question'])


if __name__ == '__main__':
    unittest.main()
