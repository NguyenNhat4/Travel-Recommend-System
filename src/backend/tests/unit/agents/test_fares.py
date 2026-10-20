"""Hỏi giá vé máy bay trước khi lập lịch (kịch bản bản 5 cảnh 6, người dùng chốt 2026-10-10).

Orchestrator (LLM) nhận câu hỏi vé và khai một job `fare` với nơi đi, nơi đến (`FareQuestion`); test giả lập phần LLM
hiểu đó, phần còn lại (đối chiếu tên với catalog, hỏi lại chỗ thiếu, tra chuyến, câu trả lời do code viết) chạy thật.
"""

import unittest

from src.backend.app.agents.models import FareQuestion, Job, OrchestratorTurn
from src.backend.app.infrastructure.persistence.conversation_store import InMemoryConversationStore

from . import test_itinerary_runtime as runtime
from .test_itinerary_runtime import START, FlightClients, ScriptedLlm


def fare_llm(**slots):
    """Orchestrator hiểu lượt này chỉ hỏi vé máy bay với các trường `slots`: một job `fare`, đi đường tắt câu vé."""
    return ScriptedLlm(turn=OrchestratorTurn(action='execute', fare_only=True,
                                             jobs=[Job(kind='fare', fare=FareQuestion(**slots))]))


class FareFlowTests(unittest.IsolatedAsyncioTestCase):
    # Mượn cách chạy graph, không kế thừa (kế thừa thì chạy lại toàn bộ test runtime).
    run_graph = runtime.RuntimeTests.run_graph

    def clients(self):
        return FlightClients(destinations=['Nha Trang', 'Hà Nội'])

    async def test_a_missing_origin_is_asked_with_the_cities_that_fly_there_then_answered(self):
        clients, store = self.clients(), InMemoryConversationStore()
        first = await self.run_graph(fare_llm(destination='Nha Trang'), clients, store=store, owner='u',
                                     state={'query': 'Vé máy bay ra Nha Trang bao nhiêu?'})
        response = first['response']
        self.assertEqual(response['status'], 'NEEDS_CLARIFICATION')
        self.assertIn('Bạn bay từ đâu ra Nha Trang? Mình có chuyến từ Hà Nội.', response['question'])
        self.assertIn('Từ Hà Nội', response['suggestions'])
        self.assertNotIn('clarificationForm', response)
        self.assertEqual(first['pending_fare'], {'destination': 'Nha Trang',
                                                 'chips': {'tu ha noi': {'origin': 'Hà Nội', 'destination': 'Nha Trang'}}})

        # Trả lời bằng một tên nơi: LLM chỉ đọc ra nơi đi, điểm đến lấy từ lần hỏi lại còn treo.
        second = await self.run_graph(fare_llm(origin='Hà Nội'), clients, store=store, owner='u',
                                      state={'query': 'Hà Nội', 'conversation_id': first['conversation_id']})
        answer = second['response']['question']
        day = f'{START[8:10]}/{START[5:7]}'
        self.assertIn(f'Vé một chiều Hà Nội → Nha Trang rẻ nhất mình thấy là 1.000.000 ₫/khách, bay ngày {day}', answer)
        self.assertIn('[VietJet Air VJ1](product:VJ1), cất cánh 08:00', answer)
        self.assertEqual(second['response']['searchResults']['flight'][0]['productId'], 'VJ1')
        pending = second['pending_fare']
        self.assertEqual((pending['origin'], pending['destination'], pending['answered'], pending['shown']),
                         ('Hà Nội', 'Nha Trang', True, ['VJ1']))
        self.assertEqual(second['intent']['origin'], 'Hà Nội')
        self.assertTrue(any('Nha Trang' in chip for chip in second['response']['suggestions']))

    async def test_pressing_the_origin_button_answers_the_fare_without_the_llm(self):
        # Chat thử 11/10: "Từ TP. Hồ Chí Minh" (nút) bị LLM hiểu là hỏi về Sài Gòn. Nút của chính trợ lý đi thẳng nhánh vé.
        clients, store = self.clients(), InMemoryConversationStore()
        first = await self.run_graph(fare_llm(destination='Nha Trang'), clients, store=store, owner='u',
                                     state={'query': 'Vé máy bay ra Nha Trang bao nhiêu?'})
        llm = ScriptedLlm(route='nút vé không gọi LLM')  # gọi LLM là test fail
        second = await self.run_graph(llm, clients, store=store, owner='u',
                                      state={'query': 'Từ Hà Nội', 'conversation_id': first['conversation_id']})
        self.assertIn('Vé một chiều Hà Nội → Nha Trang rẻ nhất', second['response']['question'])
        self.assertIn('route fare (button)', [item['message'] for item in second['events']])

    async def test_both_ends_in_one_message_are_answered_at_once(self):
        result = await self.run_graph(fare_llm(origin='Hà Nội', destination='Nha Trang'), self.clients(),
                                      state={'query': 'vé từ Hà Nội ra Nha Trang giá bao nhiêu'})
        self.assertIn('1.000.000 ₫/khách', result['response']['question'])
        self.assertNotIn('converse', [item['node'] for item in result['events']])

    async def test_short_city_names_are_matched_to_the_catalog(self):
        # "vé hn ra nt bao nhiu": LLM chép nguyên chữ viết tắt, code đối chiếu với tên điểm đến của catalog.
        result = await self.run_graph(fare_llm(origin='hn', destination='nt'), self.clients(),
                                      state={'query': 'vé hn ra nt bao nhiu'})
        self.assertIn('Vé một chiều Hà Nội → Nha Trang', result['response']['question'])

    async def test_a_missing_destination_is_asked_first(self):
        result = await self.run_graph(fare_llm(), self.clients(), state={'query': 'vé máy bay bao nhiêu vậy?'})
        self.assertIn('Bạn muốn bay đến đâu', result['response']['question'])
        self.assertIn('Vé ra Nha Trang bao nhiêu?', result['response']['suggestions'])

    async def test_a_route_without_flights_says_so(self):
        result = await self.run_graph(fare_llm(origin='Cần Thơ', destination='Nha Trang'), self.clients(),
                                      state={'query': 'vé từ Cần Thơ ra Nha Trang bao nhiêu'})
        self.assertIn('Mình chưa thấy chuyến bay còn vé từ Cần Thơ đến Nha Trang', result['response']['question'])


if __name__ == '__main__':
    unittest.main()
