"""Câu trả lời cụt, "không có ngân sách", nút chọn nơi, ngày đi chung (chat thử 16 kiểu: M02, M09, M10, M16).

Kiểm phần luật cấu trúc; phần LLM hiểu câu chữ ("2 ng", "ko có ngân sách", "hn") đã kiểm bằng hội thoại thật.
"""
import unittest
from datetime import date

from src.backend.app.agents.models import ConversationalAnswer
from src.backend.app.agents.nodes import intake_node
from src.backend.app.agents.steps import conversation, exploration, guardrails
from src.backend.app.agents.steps.classification import trip_details_missing
from src.backend.app.domain.itinerary import flights


class ShortReplyTests(unittest.TestCase):
    def test_a_terse_reply_mid_conversation_goes_to_the_llm(self):
        self.assertEqual(guardrails.input_quality('2 ng'), (guardrails.UNCLEAR, 'gibberish'))
        self.assertIsNone(guardrails.input_quality('2 ng', replying=True))
        # Rác hiển nhiên vẫn bị chặn giữa hội thoại.
        self.assertEqual(guardrails.input_quality('!!!!!!', replying=True)[0], guardrails.UNCLEAR)


class SkippedDetailTests(unittest.TestCase):
    def test_a_declined_optional_detail_is_no_longer_missing(self):
        intent = {'startDate': None, 'party': None, 'budget': None, 'origin': None}
        self.assertEqual(trip_details_missing(intent, ['budget']), ['startDate', 'party', 'origin'])
        # Trường bắt buộc không bỏ qua được.
        self.assertIn('startDate', trip_details_missing(intent, ['startDate']))


class DestinationButtonTests(unittest.TestCase):
    def test_catalog_destinations_named_in_a_kind_question_become_buttons(self):
        state = {**intake_node({'query': 'muốn đi biển'}), 'conversation_id': 'c1', 'intent': {},
                 'clarification_reason': 'destination_kind', 'destination_kind': 'biển',
                 'supported_destinations': ['Đà Nẵng', 'Nha Trang', 'Phú Quốc', 'Quy Nhơn', 'Hà Nội']}
        update = conversation.conversational_update(state, ConversationalAnswer(
            title='Chọn điểm đến có biển', message='Bạn có thể chọn Phú Quốc, Nha Trang, Đà Nẵng hoặc Quy Nhơn.'))
        self.assertEqual(update['response']['suggestions'], ['Phú Quốc', 'Nha Trang', 'Đà Nẵng'])


class FallbackLineTests(unittest.TestCase):
    def test_a_card_without_description_uses_catalog_tags_or_address(self):
        state = intake_node({'query': 'chán, chỗ khác'})
        tagged = {'productId': 't', 'name': 'hòn Thơm', 'taxonomy': 'attraction', 'attributes': {'tags': ['Cảnh đêm']}}
        self.assertEqual(exploration.card_line(state, {'product': tagged, 'reasons': ['also_popular']}),
                         '[hòn Thơm](product:t): cảnh đêm, cũng được nhiều người ghé.')
        bare = {'productId': 'b', 'name': 'Bảo tàng Gấu Teddy', 'taxonomy': 'attraction',
                'attributes': {'address': 'Grand World, khu Bãi Dài, Gành Dầu, Phú Quốc'}}
        self.assertIn('ở Grand World, khu Bãi Dài',
                      exploration.card_line(state, {'product': bare, 'reasons': ['most_reviewed']}))


class JointDateTests(unittest.TestCase):
    def test_one_start_date_has_flights_hotels_and_tickets_together(self):
        chosen, today = date(2026, 11, 20), date(2026, 10, 11)
        flight_starts = [date(2026, 10, 28), date(2026, 10, 27), date(2026, 11, 10)]
        hotels = (date(2026, 10, 7), date(2026, 11, 5), 1)   # 3 ngày: đêm cuối = ngày đi + 1
        tickets = (None, date(2026, 11, 5), 2)                # ngày cuối = ngày đi + 2
        # 10/11 gần ngày đã chọn nhất nhưng khách sạn hết nhận khách: chọn 28/10, có đủ cả ba phần.
        self.assertEqual(flights.joint_start(chosen, 3, today, flight_starts, [hotels, tickets]), date(2026, 10, 28))
        self.assertIsNone(flights.joint_start(chosen, 3, today, None, []))


if __name__ == '__main__':
    unittest.main()
