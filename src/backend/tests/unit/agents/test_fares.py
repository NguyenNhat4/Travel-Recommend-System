"""Hỏi giá vé máy bay trước khi lập lịch (kịch bản bản 5 cảnh 6, người dùng chốt 2026-10-10)."""

import unittest

from src.backend.app.agents.steps import fares
from src.backend.app.infrastructure.persistence.conversation_store import InMemoryConversationStore

from . import test_itinerary_runtime as runtime
from .test_itinerary_runtime import START, FlightClients, ScriptedLlm


class AskedTests(unittest.TestCase):
    def test_a_fare_question_needs_both_a_flight_word_and_a_price_word(self):
        self.assertTrue(fares.asked({'query': 'Vé máy bay ra Hà Nội bao nhiêu?'}))
        self.assertTrue(fares.asked({'query': 've bay tu sg ra ha noi gia sao'}))
        self.assertFalse(fares.asked({'query': 'Bây giờ giá phòng bao nhiêu?'}))
        self.assertFalse(fares.asked({'query': 'Hà Nội có gì chơi?'}))
        self.assertFalse(fares.asked({'query': 'Khách sạn cho gia đình ở Hà Nội'}))

    def test_a_short_reply_counts_only_while_a_fare_question_is_pending(self):
        pending = {'pending_fare': {'destination': 'Hà Nội'}}
        self.assertTrue(fares.asked({**pending, 'query': 'Sài Gòn'}))
        self.assertTrue(fares.asked({**pending, 'query': 'từ Hải Phòng nhé'}))
        self.assertFalse(fares.asked({**pending, 'query': 'Đà Lạt có gì?'}))
        self.assertFalse(fares.asked({**pending, 'query': 'thôi'}))
        self.assertFalse(fares.asked({'query': 'Sài Gòn'}))

    def test_an_existing_itinerary_keeps_fare_talk_out_of_this_branch(self):
        self.assertIsNone(fares.detected({'query': 'vé máy bay bao nhiêu?', 'previous_plan': {'days': []}}))


class FareFlowTests(unittest.IsolatedAsyncioTestCase):
    # Mượn cách chạy graph, không kế thừa (kế thừa thì chạy lại toàn bộ test runtime).
    run_graph = runtime.RuntimeTests.run_graph

    def clients(self):
        return FlightClients(destinations=['Nha Trang', 'Hà Nội'])

    async def test_a_missing_origin_is_asked_with_the_cities_that_fly_there_then_answered(self):
        clients, store = self.clients(), InMemoryConversationStore()
        first = await self.run_graph(ScriptedLlm(), clients, store=store, owner='u',
                                     state={'query': 'Vé máy bay ra Nha Trang bao nhiêu?'})
        response = first['response']
        self.assertEqual(response['status'], 'NEEDS_CLARIFICATION')
        self.assertIn('Bạn bay từ đâu ra Nha Trang? Mình có chuyến từ Hà Nội.', response['question'])
        self.assertIn('Từ Hà Nội', response['suggestions'])
        self.assertNotIn('clarificationForm', response)
        self.assertEqual(first['pending_fare'], {'destination': 'Nha Trang'})

        second = await self.run_graph(ScriptedLlm(), clients, store=store, owner='u',
                                      state={'query': 'Hà Nội', 'conversation_id': first['conversation_id']})
        answer = second['response']['question']
        day = f'{START[8:10]}/{START[5:7]}'
        self.assertIn(f'Vé một chiều Hà Nội → Nha Trang rẻ nhất mình thấy là 1.000.000 ₫/khách, bay ngày {day}', answer)
        self.assertIn('VietJet Air VJ1 cất cánh 08:00', answer)
        self.assertIsNone(second['pending_fare'])
        self.assertEqual(second['intent']['origin'], 'Hà Nội')
        self.assertTrue(any('Nha Trang' in chip for chip in second['response']['suggestions']))

    async def test_both_ends_in_one_message_are_answered_at_once(self):
        result = await self.run_graph(ScriptedLlm(), self.clients(),
                                      state={'query': 'vé từ Hà Nội ra Nha Trang giá bao nhiêu'})
        self.assertIn('1.000.000 ₫/khách', result['response']['question'])
        self.assertNotIn('converse', [item['node'] for item in result['events']])

    async def test_a_missing_destination_is_asked_first(self):
        result = await self.run_graph(ScriptedLlm(), self.clients(), state={'query': 'vé máy bay bao nhiêu vậy?'})
        self.assertIn('Bạn muốn bay đến đâu', result['response']['question'])
        self.assertIn('Vé ra Nha Trang bao nhiêu?', result['response']['suggestions'])

    async def test_a_route_without_flights_says_so(self):
        result = await self.run_graph(ScriptedLlm(), self.clients(),
                                      state={'query': 'vé từ Cần Thơ ra Nha Trang bao nhiêu'})
        self.assertIn('Mình chưa thấy chuyến bay còn vé từ Cần Thơ đến Nha Trang', result['response']['question'])

    async def test_a_bare_reply_with_a_city_without_flights_is_taken_as_the_origin(self):
        clients, store = self.clients(), InMemoryConversationStore()
        first = await self.run_graph(ScriptedLlm(), clients, store=store, owner='u',
                                     state={'query': 'vé ra Nha Trang bao nhiêu'})
        second = await self.run_graph(ScriptedLlm(), clients, store=store, owner='u',
                                      state={'query': 'Cần Thơ', 'conversation_id': first['conversation_id']})
        self.assertIn('từ Cần Thơ đến Nha Trang', second['response']['question'])


if __name__ == '__main__':
    unittest.main()
