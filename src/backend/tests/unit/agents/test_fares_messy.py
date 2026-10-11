"""Câu hỏi vé gõ sai, viết tắt, nói vòng (chat thử 16 kiểu người dùng: M04, M05, M06, M11, M12, M15).

- "vé sg ra hn bao nhiu" từng không được nhận là hỏi vé: 5 lượt liền khám phá Sài Gòn.
- "tao ở sài gòn, đi đâu cũng đc miễn vé rẻ" từng hiểu Sài Gòn là nơi đến.
- Đã có lịch, "chuyến bay về mấy giờ", "có chuyến nào rẻ hơn ko" từng lập lại cả lịch.
- "how much is a flight from saigon" từng ra "chưa kiểm tra được giá vé".

Hiểu câu là việc của `classify` (LLM, `FareQuestion`); test giả lập phần LLM hiểu (`fare_llm`) và kiểm phần code: đối
chiếu tên với catalog, ghép với tuyến vừa báo, chiều về, ngày khác, ghi chú cho lượt sau.
"""
import unittest

from src.backend.app.agents.steps import turn_notes
from src.backend.app.infrastructure.persistence.conversation_store import InMemoryConversationStore

from . import test_itinerary_runtime as runtime
from .test_fares import fare_llm
from .test_fares_followups import MoreFlights
from .test_itinerary_runtime import START

PLAN = {'itinerary': {'days': []}, 'searchResults': {}}
INTENT = {'destination': 'Nha Trang', 'origin': 'Hà Nội', 'startDate': START, 'days': 3,
          'party': {'type': 'COUPLE', 'adults': 2, 'children': 0}, 'budget': None, 'interests': [], 'pace': None}


class MessyFlowTests(unittest.IsolatedAsyncioTestCase):
    run_graph = runtime.RuntimeTests.run_graph

    async def turn(self, clients, store, query, llm, conversation=None):
        return await self.run_graph(llm, clients, store=store, owner='u',
                                    state={'query': query, **({'conversation_id': conversation} if conversation else {})})

    async def test_follow_ups_reuse_the_route_just_answered(self):
        clients, store = MoreFlights(), InMemoryConversationStore()
        first = await self.turn(clients, store, 'vé hn ra nt bao nhiu', fare_llm(origin='hn', destination='nt'))
        self.assertIn('Vé một chiều Hà Nội → Nha Trang rẻ nhất mình thấy là 700.000 ₫', first['response']['question'])
        conversation = first['conversation_id']
        second = await self.turn(clients, store, 'rẻ hơn nữa ko', fare_llm(cheaper=True), conversation)
        self.assertIn('Đây đã là vé rẻ nhất mình thấy', second['response']['question'])
        other = await self.turn(clients, store, 'thế ngày khác thì sao', fare_llm(other_days=True), conversation)
        self.assertNotIn('Đây đã là vé rẻ nhất', other['response']['question'])
        third = await self.turn(clients, store, 'còn đi phú quốc thì sao', fare_llm(destination='phú quốc'), conversation)
        self.assertIn('Hà Nội → Phú Quốc', third['response']['question'])
        for result in (first, second, third):
            self.assertNotIn('compose', [item['node'] for item in result['events']])

    async def test_where_the_user_lives_and_anywhere_compares_routes_from_there(self):
        clients, store = MoreFlights(), InMemoryConversationStore()
        result = await self.turn(clients, store, 'tao ở hà nội, đi đâu cũng đc miễn vé rẻ',
                                 fare_llm(origin='hà nội', anywhere=True))
        self.assertIn('Từ Hà Nội, vé một chiều rẻ nhất mình thấy là đi Nha Trang: 700.000 ₫', result['response']['question'])
        self.assertIn('Nha Trang có gì chơi?', result['response']['suggestions'])
        self.assertEqual(result['pending_fare']['best'], 'Nha Trang')

    async def test_the_return_flight_of_an_itinerary_is_answered_without_replanning(self):
        clients, store = MoreFlights(), InMemoryConversationStore()
        await store.save('c-plan', {'intent': INTENT, 'previous_plan': PLAN, 'plan_consent': True}, 'u')
        # LLM có lúc tự đảo chiều (nơi đi Nha Trang, nơi đến Hà Nội): chiều về vẫn lấy từ chuyến, không đảo lần nữa.
        result = await self.turn(clients, store, 'chuyến bay về mấy giờ',
                                 fare_llm(return_leg=True, origin='Nha Trang', destination='Hà Nội'), 'c-plan')
        question = result['response']['question']
        # Chặng về Nha Trang → Hà Nội, ngày cuối của chuyến 3 ngày (START + 2): VJ2 19:00.
        self.assertIn('Nha Trang → Hà Nội', question)
        self.assertIn('VJ2 cất cánh 19:00', question)
        self.assertNotIn('compose', [item['node'] for item in result['events']])
        saved = await store.load('c-plan', 'u')
        self.assertEqual(saved['previous_plan'], PLAN)
        self.assertEqual(saved['intent']['origin'], 'Hà Nội')
        self.assertEqual(result['pending_fare'], {'origin': 'Hà Nội', 'destination': 'Nha Trang', 'answered': True})


class AnswerNoteTests(unittest.TestCase):
    def test_a_fare_answer_leaves_a_note_with_its_route_for_the_next_turn(self):
        state = {'fare_question': True, 'pending_fare': {'origin': 'Hà Nội', 'destination': 'Nha Trang', 'answered': True}}
        note = turn_notes.turn_note(state, {'status': 'NEEDS_CLARIFICATION'}, 200)
        self.assertEqual(note, 'báo giá vé máy bay một chiều Hà Nội → Nha Trang')

    def test_an_explore_answer_leaves_a_note_with_the_places_shown(self):
        state = {'intent': {'destination': 'Hà Nội'}}
        response = {'status': 'NEEDS_CLARIFICATION',
                    'searchResults': {'attraction': [{'name': 'Văn Miếu – Quốc Tử Giám'}]}}
        self.assertEqual(turn_notes.turn_note(state, response, 200), 'giới thiệu Hà Nội: Văn Miếu – Quốc Tử Giám')


if __name__ == '__main__':
    unittest.main()
