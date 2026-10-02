"""FALLBACK nêu lý do thật và những gì đã tìm được, không chỉ câu cố định (trace 01a0fa0c, 2026-10-02)."""
import unittest

from src.backend.app.agents.steps import composition


def product(pid, taxonomy='hotel'):
    return {'productId': pid, 'name': f'Catalog {pid}', 'taxonomy': taxonomy, 'destination': 'Đà Nẵng',
            'unitPrice': 900_000, 'currency': 'VND', 'available': True, 'description': '', 'attributes': {},
            'availableFrom': None, 'availableTo': None, 'priceUnit': 'PER_NIGHT'}


def state(candidates, tool_results, language='vi'):
    return {'conversation_id': 'c1', 'decision': 'fallback', 'language': language, 'candidates': candidates,
            'sources': {pid: 'search' for pid in candidates}, 'warnings': [], 'constraints': {},
            'tool_results': tool_results,
            'intent': {'destination': 'Đà Nẵng', 'startDate': '2026-10-15', 'days': 3,
                       'party': {'type': 'COUPLE', 'adults': 2, 'children': 0}, 'budget': 5_000_000,
                       'interests': [], 'pace': None}}


SEARCH_HOTEL = {'name': 'search_products', 'arguments': {'taxonomy': 'hotel'}, 'data': {'results': []}}
RECOMMENDATIONS_BROKEN = {'name': 'get_recommendations', 'arguments': {'destination': 'Đà Nẵng'},
                          'error': {'code': 'INVALID_TOOL_RESPONSE', 'retryable': False}}


class FallbackReasonTests(unittest.TestCase):
    def test_names_the_failed_source_and_what_was_found(self):
        # Đúng ca của trace: Search ra 1 khách sạn, gợi ý cá nhân hoá trả dữ liệu lỗi → FALLBACK.
        response = composition.fallback(state({'h1': product('h1')}, [SEARCH_HOTEL, RECOMMENDATIONS_BROKEN]))['response']
        message = response['message']
        self.assertTrue(message.startswith('**Chưa dựng được lịch trình hoàn chỉnh**\n'))
        self.assertIn('gợi ý cá nhân hoá', message)
        self.assertIn('1 khách sạn', message)
        self.assertNotIn('Chưa thể dựng lịch trình đã kiểm tra', message)
        self.assertEqual([p['productId'] for p in response['searchResults']['hotel']], ['h1'])

    def test_explains_when_nothing_found_can_be_scheduled(self):
        message = composition.fallback(state({'c1': product('c1', 'combo'), 'f1': product('f1', 'flight')},
                                             [SEARCH_HOTEL]))['response']['message']
        self.assertIn('chưa có khách sạn hay điểm tham quan', message)
        self.assertIn('1 combo', message)
        self.assertIn('1 vé máy bay', message)

    def test_names_the_search_that_failed(self):
        failed = {'name': 'search_products', 'arguments': {'taxonomy': 'attraction'},
                  'error': {'code': 'SEARCH_UNAVAILABLE', 'retryable': True}}
        message = composition.fallback(state({'h1': product('h1')}, [SEARCH_HOTEL, failed]))['response']['message']
        self.assertIn('điểm tham quan ở Đà Nẵng', message)

    def test_english_conversation_gets_english_reason(self):
        message = composition.fallback(state({'h1': product('h1')}, [RECOMMENDATIONS_BROKEN], language='en'))['response']['message']
        self.assertTrue(message.startswith('**Could not build a complete itinerary**\n'))
        self.assertIn('personalised suggestions', message)


if __name__ == '__main__':
    unittest.main()
