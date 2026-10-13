"""Trò chuyện và khám phá trước khi lập lịch (FR-AGT-06, chốt 2026-10-10): luật chọn thẻ, nút gợi ý, luật đồng ý lập lịch.

Luồng khám phá chạy bằng orchestrator (`test_orchestrator_runtime.py`, `test_orchestrator_jobs.py`); các ca của node
`explore` cũ đã gỡ cùng node đó (13/10/2026).
"""
import unittest

from src.backend.app.agents.models import Extraction
from src.backend.app.agents.nodes import intake_node
from src.backend.app.agents.steps import validation
from src.backend.app.agents.steps.classification import extract_result
from src.backend.app.agents.steps.consent import asks_for_plan, plan_consented, says_yes
from src.backend.app.agents.steps.replies import checked_suggestions
from src.backend.app.domain.itinerary import exploration as rules
from src.backend.app.domain.itinerary.planning import empty_intent

from .test_itinerary_runtime import product


def place(pid, taxonomy='attraction', **fields):
    return product(pid, taxonomy=taxonomy, destination='Hà Nội', name=f'Nơi {pid}', **fields)


class PickCardsTests(unittest.TestCase):
    """Mỗi thẻ một lý do, và lý do đúng trên toàn bộ kết quả, không trên phần đã cắt."""

    def test_the_cheapest_is_the_cheapest_of_all_results_even_when_it_is_a_hostel(self):
        # Kịch bản bản 4 từng nói Solare "rẻ nhất" trong khi Little Charm Hostel rẻ hơn mà vẫn có hồ bơi.
        hotels = [place('solare', 'hotel', unitPrice=2_376_000, rating=4.7, reviewCount=3541),
                  place('classyc', 'hotel', unitPrice=4_688_250, rating=4.9, reviewCount=171),
                  place('charm', 'hotel', unitPrice=220_014, rating=4.5, reviewCount=4524)]
        cards = rules.pick_cards(hotels, 2, 'hotel')
        reasons = {card['product']['productId']: card['reasons'] for card in cards}
        self.assertIn(rules.CHEAPEST, reasons['charm'])
        self.assertEqual(reasons['classyc'], [rules.TOP_RATED])
        self.assertNotIn('solare', reasons)

    def test_a_reason_already_held_by_a_card_is_never_given_to_the_runner_up(self):
        # Rẻ nhất cũng là nhiều đánh giá nhất: không được gán "nhiều đánh giá nhất" cho khách sạn hạng hai.
        hotels = [place('a', 'hotel', unitPrice=100, reviewCount=900),
                  place('b', 'hotel', unitPrice=500, reviewCount=800)]
        cards = rules.pick_cards(hotels, 2, 'hotel')
        self.assertEqual(cards[0]['reasons'], [rules.CHEAPEST, rules.MOST_REVIEWED])
        self.assertEqual(cards[1]['reasons'], [rules.ALSO_POPULAR])

    def test_top_rated_needs_enough_reviews(self):
        attractions = [place('few', rating=5.0, reviewCount=3), place('many', rating=4.6, reviewCount=1139)]
        cards = rules.pick_cards(attractions, 4, 'attraction')
        top = next(card for card in cards if rules.TOP_RATED in card['reasons'])
        self.assertEqual(top['product']['productId'], 'many')

    def test_tickets_of_the_same_place_take_one_card(self):
        attractions = [product('v1', name='[VinWonders Phú Quốc] Vé Vào Cửa', reviewCount=50),
                       product('v2', name='[VinWonders Phú Quốc] Vé + Buffet', reviewCount=40),
                       product('h', name='Hòn Thơm', reviewCount=10)]
        ids = [card['product']['productId'] for card in rules.pick_cards(attractions, 4, 'attraction')]
        self.assertEqual(ids, ['v1', 'h'])

    def test_a_place_named_inside_another_takes_one_card(self):
        attractions = [product('cap', name='Cáp Treo Hòn Thơm', reviewCount=3969),
                       product('hon', name='hòn Thơm', reviewCount=200, rating=4.9),
                       product('vin', name='VinWonders Phú Quốc', reviewCount=100)]
        ids = [card['product']['productId'] for card in rules.pick_cards(attractions, 4, 'attraction')]
        self.assertEqual(sorted(ids), ['cap', 'vin'])

    def test_a_hotel_and_its_room_take_one_card(self):
        # LLM thật 10/10 (fixture): "VinHolidays Fiesta Phú Quốc" và "... - Phòng Tiêu Chuẩn Giường Đôi" hiện hai thẻ.
        hotels = [product('h', taxonomy='hotel', name='VinHolidays Fiesta Phú Quốc', unitPrice=1_844_192),
                  product('r', taxonomy='hotel', name='VinHolidays Fiesta Phú Quốc - Phòng Tiêu Chuẩn Giường Đôi',
                          unitPrice=1_900_000),
                  product('v', taxonomy='hotel', name='Vinpearl Resort', unitPrice=3_000_000)]
        ids = [card['product']['productId'] for card in rules.pick_cards(hotels, 4, 'hotel')]
        self.assertEqual(sorted(ids), ['h', 'v'])

    def test_free_entry_is_a_reason_of_its_own(self):
        attractions = [place('paid', reviewCount=500, unitPrice=900_000),
                       place('free', reviewCount=100, unitPrice=0, attributes={'ticketed': False})]
        cards = rules.pick_cards(attractions, 4, 'attraction')
        self.assertIn(rules.FREE_ENTRY, next(c for c in cards if c['product']['productId'] == 'free')['reasons'])


class NamedPlaceTests(unittest.TestCase):
    """Câu hỏi nêu tên một nơi trả đúng thẻ nơi đó (kịch bản cảnh 9, LLM thật 10/10 đã trả thẻ chung chung)."""

    def test_the_named_place_is_found_by_the_first_part_of_its_name(self):
        van_mieu = product('vm', destination='Hà Nội', name='Văn Miếu – Quốc Tử Giám',
                           attributes={'openingHours': '08:00–17:00, 18:00–22:00'})
        city = product('hn', destination='Hà Nội', name='Hà Nội')
        self.assertEqual(rules.named_in([city, van_mieu], 'Văn Miếu buổi tối có mở không?', ['Hà Nội'])['productId'], 'vm')
        self.assertIsNone(rules.named_in([city, van_mieu], 'Hà Nội có gì chơi?', ['Hà Nội']))


class SuggestionTests(unittest.TestCase):
    """Tối đa 3 nút, khác mẫu câu, không lặp lượt trước, có một nút đi tiếp (AC-AGT-07)."""

    destinations = ['Hà Nội', 'Đà Nẵng', 'Phú Quốc']

    def test_same_pattern_with_another_place_is_dropped(self):
        kept = checked_suggestions(['Hà Nội có gì?', 'Đà Nẵng có gì?', 'Khách sạn sát biển'], [], [],
                                   destinations=self.destinations)
        self.assertEqual(kept, ['Hà Nội có gì?', 'Khách sạn sát biển'])

    def test_buttons_of_the_previous_turn_are_not_repeated(self):
        kept = checked_suggestions(['Tìm chỗ đi biển', 'Tối ở Hà Nội đi đâu?'], ['Tìm chỗ đi biển'], [],
                                   destinations=self.destinations)
        self.assertEqual(kept, ['Tối ở Hà Nội đi đâu?'])

    def test_a_plan_button_is_always_offered_first_when_none_asks_to_plan(self):
        kept = checked_suggestions(['A', 'B', 'C'], [], [], destinations=self.destinations,
                                   plan_chip='Lên lịch Hà Nội cho mình')
        self.assertEqual(kept[0], 'Lên lịch Hà Nội cho mình')
        self.assertEqual(len(kept), 3)

    def test_too_few_buttons_are_filled_from_the_templates(self):
        kept = checked_suggestions([''], [], ['Khách sạn ở Hà Nội', 'Gợi ý nơi khác cho mình'],
                                   destinations=self.destinations)
        self.assertEqual(kept, ['Khách sạn ở Hà Nội', 'Gợi ý nơi khác cho mình'])


class ConsentTests(unittest.TestCase):
    """Đồng ý lập lịch nhận bằng luật; chưa đồng ý thì không hỏi thông tin chuyến."""

    def test_short_yes_and_plan_requests_are_read_without_the_llm(self):
        for text in ('ok', 'được', 'có', 'oke nhé', 'lập đi'):
            self.assertTrue(says_yes(text), text)
        for text in ('Lên lịch Hà Nội cho mình', 'lập lịch Đà Nẵng 3 ngày', 'Tiếp tục lập lịch'):
            self.assertTrue(asks_for_plan(text), text)
        for text in ('Hà Nội có gì?', 'có khách sạn nào không', 'lên Đà Lạt chơi'):
            self.assertFalse(says_yes(text) or asks_for_plan(text), text)

    def test_yes_counts_only_after_an_offer(self):
        state = intake_node({'query': 'ok'})
        self.assertFalse(plan_consented(state, 'vague'))
        self.assertTrue(plan_consented({**state, 'pending_offer': {'destination': 'Hà Nội'}}, 'vague'))


    def test_the_llm_plan_flag_is_ignored_for_a_question_about_a_place(self):
        state = intake_node({'query': 'Hà Nội có gì?'})
        self.assertFalse(plan_consented(state, 'explore', llm_plan_request=True))


    def test_a_trip_detail_means_the_user_is_planning(self):
        result = extract_result(intake_node({'query': 'Hà Nội 3 ngày'}),
                                Extraction(patch={'destination': 'Hà Nội', 'days': 3}))
        self.assertTrue(result['plan_consent'])
        self.assertEqual(result['decision'], 'missing_info')


class ExploreValidationTests(unittest.TestCase):
    def test_a_link_to_a_product_without_a_card_fails_grounding(self):
        card = place('a')
        state = {'candidates': {'a': card}}
        from src.backend.app.domain.itinerary.planning import summary
        response = {'status': 'NEEDS_CLARIFICATION', 'conversationId': 'c', 'knownIntent': empty_intent(),
                    'question': '[Nơi a](product:a) và [Nơi lạ](product:x)', 'searchResults': {'attraction': [summary(card)]}}
        self.assertIn('message_grounding', validation.response_issues(state, response, 200))
        response['question'] = '[Nơi a](product:a)'
        self.assertEqual(validation.response_issues(state, response, 200), [])


HANOI = [place('lang', reviewCount=363, rating=4.4, unitPrice=0, attributes={'ticketed': False}),
         place('ho', reviewCount=1139, rating=4.6, unitPrice=0, attributes={'ticketed': False}),
         place('charm', 'hotel', unitPrice=220_014, rating=4.5, reviewCount=4524, attributes={'pool': True}),
         place('solare', 'hotel', unitPrice=2_376_000, rating=4.7, reviewCount=3541, attributes={'pool': True}),
         place('plain', 'hotel', unitPrice=150_000, rating=4.0, reviewCount=50, attributes={'pool': False})]


if __name__ == '__main__':
    unittest.main()


class NearestFlightDateTests(unittest.TestCase):
    """Ngày đã chọn không có chuyến bay: gợi ý ngày gần nhất có vé, giữ số ngày (kịch bản bản 5, cảnh 10)."""

    @staticmethod
    def flight(pid, day, trip='oneWay', back=None, price=700_000):
        attributes = {'departureAt': f'{day}T21:00:00+07:00', 'tripType': trip}
        if back:
            attributes['returnDate'] = back
        return product(pid, taxonomy='flight', unitPrice=price, attributes=attributes)

    def test_complete_pairs_come_before_closer_one_way_dates(self):
        from datetime import date
        from src.backend.app.domain.itinerary.flights import nearest_dates
        # Như dữ liệu thật tháng 10: 17/10 không có chuyến; 14/10 chỉ có chiều đi; 20/10 có vé khứ hồi về 24/10.
        options = {'status': None, 'outbound': [self.flight('o14', '2026-10-14', price=705_000),
                                                self.flight('rt20', '2026-10-20', 'roundTrip', '2026-10-22', 1_663_000)],
                   'return': [self.flight('r21', '2026-10-21')]}
        intent = {**empty_intent(), 'startDate': '2026-10-17', 'days': 3}
        found = nearest_dates(options, intent, date(2026, 10, 10))
        self.assertEqual([(item['startDate'], item['complete']) for item in found],
                         [('2026-10-20', True), ('2026-10-14', False)])

    def test_past_dates_and_the_chosen_date_are_never_suggested(self):
        from datetime import date
        from src.backend.app.domain.itinerary.flights import nearest_dates
        options = {'status': None, 'outbound': [self.flight('old', '2026-10-09'), self.flight('same', '2026-10-17')],
                   'return': []}
        intent = {**empty_intent(), 'startDate': '2026-10-17', 'days': 3}
        self.assertEqual(nearest_dates(options, intent, date(2026, 10, 10)), [])

    def test_the_flight_warning_names_the_nearest_dates(self):
        from src.backend.app.agents.steps import composition
        options = {'status': None, 'origin': 'TP. Hồ Chí Minh',
                   'outbound': [self.flight('rt', '2999-10-20', 'roundTrip', '2999-10-22')], 'return': []}
        state = {'language': 'vi', 'flight_options': options,
                 'intent': {**empty_intent(), 'destination': 'Hà Nội', 'origin': 'TP. Hồ Chí Minh',
                            'startDate': '2999-10-17', 'days': 3}}
        warning = composition._flight_warning(state, 'NO_FLIGHT_ON_DATES', [])
        self.assertIn('Ngày gần nhất có vé: đi 20/10/2999, về 22/10/2999 (đủ hai chiều).', warning['message'])
        self.assertIn('"đổi sang 20/10"', warning['message'])


class HotelPreferenceTests(unittest.TestCase):
    """Sở thích khách sạn là ưu tiên, không bắt buộc (FR-AGT-06): kéo khách sạn hợp lên, không loại hết."""

    @staticmethod
    def hotel(pid, *amenities):
        return place(pid, 'hotel', attributes={'amenities': list(amenities)})

    def test_stated_preferences_read_only_what_follows_the_word_prefer(self):
        from src.backend.app.domain.itinerary import preferences
        keys = [p.key for p in preferences.stated_preferences(
            'Lên lịch 3 ngày tại Hà Nội, cho 2 người lớn và 1 trẻ em, ưu tiên khách sạn có Hồ bơi, Spa.')]
        self.assertEqual(keys, ['pool', 'spa'])
        self.assertEqual(preferences.stated_preferences('không cần hồ bơi'), [])


    def test_a_preference_in_the_form_sentence_stays_soft_even_when_the_llm_makes_it_required(self):
        state = {**intake_node({'query': 'Lên lịch trình 3 ngày tại Hà Nội, ưu tiên khách sạn có Hồ bơi.'}),
                 'plan_consent': True}
        result = extract_result(state, Extraction(patch={'destination': 'Hà Nội', 'days': 3},
                                                  constraints={'hotel_attributes': {'pool': True}}))
        self.assertIn('Hồ bơi', result['intent']['interests'])
        self.assertNotIn('pool', (result['constraints'].get('hotel_attributes') or {}))

    def test_preferences_go_into_the_hotel_query_but_not_the_attraction_query(self):
        from src.backend.app.domain.itinerary.search_hints import retrieval_hints
        hints = retrieval_hints({**empty_intent(), 'interests': ['Hồ bơi', 'ẩm thực']}, {})
        self.assertIn('hồ bơi', hints['hotel'])
        self.assertEqual(hints['attraction'], ['ẩm thực'])

    def test_evaluate_drops_non_matching_hotels_only_when_enough_matching_ones_exist(self):
        from src.backend.app.agents.steps.evaluation import _preferred_stays
        hotels = [self.hotel(f'p{i}', 'Hồ bơi ngoài trời') for i in range(3)] + [self.hotel('dry', 'Wi-Fi')]
        candidates = {h['productId']: h for h in hotels + [place('sight')]}
        sources = {pid: 'SEARCH' for pid in candidates}
        state = {'intent': {**empty_intent(), 'interests': ['Hồ bơi']}}
        kept, kept_sources = _preferred_stays(state, candidates, sources)
        self.assertEqual(sorted(kept), ['p0', 'p1', 'p2', 'sight'])
        self.assertEqual(sorted(kept_sources), sorted(kept))

    def test_the_form_offers_the_preferences_and_ticks_kid_friendly_for_children(self):
        from src.backend.app.agents.steps.conversation import clarification_form
        state = {'intent': {**empty_intent(), 'destination': 'Hà Nội', 'interests': ['Hồ bơi', 'ẩm thực'],
                            'party': {'type': 'FAMILY_WITH_KIDS', 'adults': 2, 'children': 1}}}
        form = clarification_form(state)
        self.assertEqual(form['fields'][-1], 'interests')
        self.assertIn('Spa', form['interestOptions'])
        self.assertEqual(form['defaults']['interests'], ['ẩm thực', 'Hồ bơi', 'Phù hợp trẻ nhỏ'])
