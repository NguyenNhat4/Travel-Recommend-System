"""Gói/tour nhiều ngày không vào slot của một buổi: trả kèm để người dùng cân nhắc riêng."""
import unittest

from src.backend.app.agents.models import ItineraryNarration
from src.backend.app.agents.steps import composition, narration, validation
from src.backend.app.domain.itinerary.planning import compose_plan, empty_intent, multi_day_span

PASS = {'productId': 'pass3', 'name': '[03 ngày không giới hạn] - VinWonders + Vinpearl Safari + Tour Grand World',
        'taxonomy': 'attraction', 'destination': 'Phú Quốc', 'unitPrice': 2300000, 'priceUnit': 'PER_PERSON',
        'currency': 'VND', 'available': True, 'attributes': {}}
PARK = {'productId': 'park', 'name': 'VinWonders Phú Quốc', 'taxonomy': 'attraction', 'destination': 'Phú Quốc',
        'unitPrice': 950000, 'priceUnit': 'PER_PERSON', 'currency': 'VND', 'available': True, 'attributes': {}}
INTENT = {**empty_intent(), 'destination': 'Phú Quốc', 'days': 5, 'startDate': '2026-10-10',
          'party': {'type': 'FRIENDS', 'adults': 50, 'children': 0}}


def state():
    candidates = {'pass3': dict(PASS), 'park': dict(PARK)}
    return {'conversation_id': 'c1', 'request_id': 'r1', 'language': 'vi', 'query': 'đi Phú Quốc',
            'intent': dict(INTENT), 'previous_intent': dict(INTENT), 'constraints': {}, 'warnings': [],
            'candidates': candidates, 'sources': {'pass3': 'search', 'park': 'search'},
            'conversation_history': [], 'previous_selection': []}


class SpanTests(unittest.TestCase):
    def test_reads_the_span_from_the_name_or_the_duration(self):
        cases = {('[03 ngày không giới hạn] - VinWonders', None): 3, ('[01 ngày] - Tour', 180): None,
                 ('[Tour 2 Đảo] - Vé (2 ngày)', 180): 2, ('4-Day Hanoi to Ninh Binh', None): 4,
                 ('Mai Chau 4D3N from Hanoi', None): 4, ('Tour 3N2Đ Hạ Long', None): 3,
                 ('Halong cruise', 4320): 3, ('Private Ninh Binh Full Day', 1440): None,
                 ('Thị trấn Hoàng Hôn - Sunset Town', None): None}
        for (name, minutes), expected in cases.items():
            with self.subTest(name=name):
                attributes = {'durationMinutes': minutes} if minutes else {}
                self.assertEqual(multi_day_span({'name': name, 'attributes': attributes}), expected)


class ComposeTests(unittest.TestCase):
    def test_a_multi_day_pass_is_never_put_in_a_slot(self):
        current = state()
        proposal = compose_plan(current['candidates'], current['sources'], current['intent'])
        self.assertEqual([slot['product_id'] for slot in proposal['slots']], ['park'])

    def test_it_is_returned_beside_the_itinerary_and_passes_grounding(self):
        current = state()
        response = composition.composed(current)['response']
        self.assertEqual([p['productId'] for p in response['searchResults']['attraction']], ['pass3'])
        self.assertEqual(validation.response_issues(current, response, 200), [])

    def test_a_tampered_offer_fails_grounding(self):
        current = state()
        response = composition.composed(current)['response']
        response['searchResults']['attraction'][0]['unitPrice'] = 1
        self.assertIn('fallback_grounding', validation.response_issues(current, response, 200))


class NarrationTests(unittest.TestCase):
    def narrated_state(self):
        current = state()
        current['response'] = composition.composed(current)['response']
        return current

    def test_the_rule_based_reply_asks_about_the_pass_separately(self):
        current = self.narrated_state()
        text = narration.fallback_message(current, current['response'])
        self.assertIn('**Gói nhiều ngày để bạn cân nhắc riêng**', text)
        self.assertIn('[03 ngày không giới hạn - VinWonders + Vinpearl Safari + Tour Grand World](product:pass3) — '
                      'dùng trong 3 ngày · 2.300.000 ₫/người', text)
        self.assertIn('Bạn muốn thêm gói nào', text)
        self.assertLess(text.index('Gói nhiều ngày'), text.index('Chi phí dự kiến'))

    def test_the_model_may_link_the_pass_and_a_forgotten_one_is_still_asked(self):
        current = self.narrated_state()
        update, reason = narration.narrated(current, ItineraryNarration(
            title='5 ngày Phú Quốc', message='Sáng ngày 1 chơi [x](product:park) ([[price:park]]).'))
        self.assertEqual(reason, 'llm')
        self.assertIn('**Gói nhiều ngày để bạn cân nhắc riêng**', update['response']['message'])
        update, reason = narration.narrated(current, ItineraryNarration(
            message='[x](product:park).\n\n**Chi phí dự kiến**\nChưa cộng được tổng.'))
        text = update['response']['message']
        self.assertEqual(reason, 'llm')
        self.assertLess(text.index('Gói nhiều ngày'), text.index('**Chi phí dự kiến**'))
        self.assertIn('Bạn muốn thêm gói nào', text)
        self.assertEqual(narration.unknown_links(update['response']), [])

    def test_the_payload_lists_the_pass_apart_from_the_days(self):
        payload = narration.narration_input(self.narrated_state())[1][1]
        self.assertIn('consider_separately:', payload)
        self.assertIn('days_covered: 3', payload)


if __name__ == '__main__':
    unittest.main()
