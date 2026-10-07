"""Node `narrate`: LLM viết lời diễn giải, backend kiểm grounding và điền tên/giá thật."""
import asyncio
import unittest
from copy import deepcopy
from types import SimpleNamespace

import yaml

from src.backend.app.agents import nodes
from src.backend.app.agents.models import ItineraryNarration
from src.backend.app.agents.steps import guardrails, narration, validation
from src.backend.app.agents.steps.messages import PRODUCT_LINK
from src.backend.app.agents.steps.history import llm_context
from src.backend.app.domain.itinerary.planning import empty_intent

TOUR = {'productId': 't1', 'name': 'Full-Day Ninh Binh Tour', 'taxonomy': 'attraction', 'destination': 'Hà Nội',
        'unitPrice': 850000, 'priceUnit': 'PER_PERSON', 'currency': 'VND', 'available': True,
        'attributes': {'durationMinutes': 600}}
PARK = {'productId': 'p1', 'name': 'Hồ Gươm', 'taxonomy': 'attraction', 'destination': 'Hà Nội', 'unitPrice': None,
        'priceUnit': 'UNKNOWN', 'currency': 'VND', 'available': True, 'attributes': {'ticketed': False}}
HOTEL = {'productId': 'h1', 'name': 'Old Quarter Hotel', 'taxonomy': 'hotel', 'destination': 'Hà Nội',
         'unitPrice': 600000, 'priceUnit': 'PER_NIGHT', 'currency': 'VND', 'available': True}
INTENT = {**empty_intent(), 'destination': 'Hà Nội', 'days': 1, 'startDate': '2026-10-15',
          'party': {'type': 'COUPLE', 'adults': 2, 'children': 0}, 'budget': 1000000}


def state(slots=None, stay=None, previous=None, total=1700000, status='OVER_BUDGET', language='vi'):
    itinerary = {'days': [{'day': 1, 'date': '2026-10-15', 'slots': slots if slots is not None else [
        {'time': 'MORNING', 'activityType': None, 'product': deepcopy(TOUR), 'note': 'Tham quan.', 'source': 'SEARCH',
         'because': []}]}], 'estimatedTotal': total, 'currency': 'VND', 'budgetStatus': status}
    if stay:
        itinerary['stay'] = {'product': deepcopy(stay), 'nights': 1, 'note': 'Nghỉ.', 'source': 'SEARCH', 'because': []}
    return {'query': 'à nhầm ngày 15 tháng 10', 'conversation_id': 'c1', 'language': language,
            'intent': dict(INTENT), 'previous_intent': previous if previous is not None else {**INTENT, 'startDate': '2026-10-14'},
            'constraints': {}, 'conversation_history': [], 'previous_selection': [], 'request_id': 'r1',
            'response': {'status': 'COMPLETED', 'conversationId': 'c1', 'intent': dict(INTENT), 'itinerary': itinerary,
                         'warnings': []}}


def narrated(current, text, title='Một ngày khám phá Ninh Bình'):
    return narration.narrated(current, ItineraryNarration(title=title, message=text))


class ChangesTests(unittest.TestCase):
    def test_a_changed_date_is_acknowledged_in_dd_mm_yyyy(self):
        self.assertEqual(narration.changes_sentence(state()),
                         'Mình ghi nhận đổi ngày đi thành 15/10/2026. Lịch trình mình gợi ý như sau:')

    def test_several_changes_are_listed_together(self):
        previous = {**INTENT, 'startDate': '2026-10-14', 'budget': 500000}
        self.assertIn('ngày đi thành 15/10/2026, ngân sách thành 1.000.000 ₫', narration.changes_sentence(state(previous=previous)))

    def test_a_field_that_was_empty_before_is_not_a_change(self):
        self.assertIsNone(narration.changes_sentence(state(previous={**INTENT, 'startDate': None})))

    def test_english_wording(self):
        self.assertTrue(narration.changes_sentence(state(language='en')).startswith('Noted: departure date changed to 15/10/2026'))


class RenderTests(unittest.TestCase):
    def test_links_get_the_canonical_name_and_placeholders_the_real_price(self):
        update, reason = narrated(state(), '**Ngày 1 · 15/10/2026**\n• Cả ngày — [tour Ninh Bình](product:t1) '
                                           '([[price:t1]]), tổng [[total]] so với [[budget]].')
        text = update['response']['message']
        self.assertEqual(reason, 'llm')
        self.assertTrue(text.startswith('**Một ngày khám phá Ninh Bình**\nMình ghi nhận đổi ngày đi thành 15/10/2026.'))
        self.assertIn('[Full-Day Ninh Binh Tour](product:t1) (850.000 ₫/người)', text)
        self.assertIn('tổng 1.700.000 ₫ so với 1.000.000 ₫', text)
        self.assertEqual(update['response']['itinerary']['title'], 'Một ngày khám phá Ninh Bình')

    def test_a_leading_bold_title_from_the_model_is_not_duplicated(self):
        update, _ = narrated(state(), '**Tiêu đề lặp**\n[x](product:t1)')
        self.assertEqual(update['response']['message'].count('**Tiêu đề lặp**'), 0)

    def test_unknown_product_falls_back_to_rules(self):
        update, reason = narrated(state(), 'Đi [Khách sạn bịa](product:fake) nhé, [x](product:t1)')
        self.assertEqual(reason, 'unknown_product')
        self.assertNotIn('fake', update['response']['message'])
        self.assertIn('[Full-Day Ninh Binh Tour](product:t1)', update['response']['message'])

    def test_a_money_amount_written_by_the_model_falls_back(self):
        for text in ('[x](product:t1) giá 850.000đ', '[x](product:t1) chỉ 1 triệu', '[x](product:t1) tầm 500k'):
            with self.subTest(text=text):
                self.assertEqual(narrated(state(), text)[1], 'raw_money')

    def test_other_numbers_are_fine(self):
        self.assertEqual(narrated(state(), '[x](product:t1) cho 2 người lớn, 1 ngày, 10 tiếng')[1], 'llm')

    def test_unknown_placeholder_or_broken_link_falls_back(self):
        self.assertEqual(narrated(state(), '[x](product:t1) [[discount]]')[1], 'unknown_placeholder')
        self.assertEqual(narrated(state(), '[x](product:t1) xem product:t1')[1], 'malformed_link')

    def test_a_product_the_model_forgot_is_still_clickable(self):
        slots = [{'time': 'MORNING', 'activityType': None, 'product': deepcopy(PARK), 'note': None, 'source': 'SEARCH', 'because': []}]
        update, _ = narrated(state(slots=slots, stay=HOTEL, total=None, status='UNKNOWN'), 'Chỉ nói về [x](product:h1).')
        self.assertIn('[Hồ Gươm](product:p1)', update['response']['message'])

    def test_brackets_in_a_catalog_name_do_not_break_the_link(self):
        # Catalog thật có tên "[Grand World Phú Quốc] - Vé đi thuyền Venice (Water Taxi)": ngoặc vuông lồng trong nhãn
        # làm frontend không nhận ra link nên id hiện thô trong chat.
        boat = {**TOUR, 'productId': 'b1', 'name': '[Grand World Phú Quốc] - Vé đi thuyền Venice (Water Taxi)'}
        slots = [{'time': 'MORNING', 'activityType': None, 'product': boat, 'note': None, 'source': 'SEARCH', 'because': []}]
        current = state(slots=slots)
        update, reason = narrated(current, 'Sáng nay đi [Vé đi thuyền Venice](product:b1) nhé.')
        label = 'Grand World Phú Quốc - Vé đi thuyền Venice (Water Taxi)'
        self.assertEqual(reason, 'llm')
        self.assertIn(f'[{label}](product:b1)', update['response']['message'])
        self.assertEqual([m.group(2) for m in PRODUCT_LINK.finditer(update['response']['message'])], ['b1'])
        self.assertNotIn('[[', update['response']['message'])
        self.assertIn(f'[{label}](product:b1)', narration.fallback_message(current, current['response']))
        # Model nhận tên đã bỏ ngoặc nên không chép ngoặc vuông vào nhãn link của nó.
        self.assertIn(f'name: {label}', narration.narration_input(current)[1][1])
        self.assertEqual(narration.unknown_links(update['response']), [])

    def test_links_the_model_broke_around_a_bracketed_name_are_repaired(self):
        # Output thật của gpt-4o-mini (trace LangSmith 01/10 06:32): tên catalog có ngoặc vuông nên link sai cú pháp,
        # trước đây làm bỏ cả bài viết ("malformed_link") và giao diện chỉ còn bản dựng bằng luật.
        name = '[Grand World Phú Quốc] - Vé đi thuyền Venice (Water Taxi)'
        boat = {**TOUR, 'productId': 'b1', 'name': name}
        slots = [{'time': 'MORNING', 'activityType': None, 'product': boat, 'note': None, 'source': 'SEARCH', 'because': []},
                 {'time': 'AFTERNOON', 'activityType': None, 'product': deepcopy(PARK), 'note': None, 'source': 'SEARCH',
                  'because': []}]
        label = 'Grand World Phú Quốc - Vé đi thuyền Venice (Water Taxi)'
        for text in (f'Sáng đi {name} (product:b1). Chiều dạo [Hồ Gươm](product:p1).',
                     f'Sáng đi [{name}](product:b1). Chiều dạo [Hồ Gươm](product:p1).',
                     f'Sáng đi {label} (product:b1). Chiều dạo [Hồ Gươm](product:p1).'):
            with self.subTest(text=text):
                update, reason = narrated(state(slots=slots), text)
                self.assertEqual(reason, 'llm')
                self.assertIn(f'Sáng đi [{label}](product:b1).', update['response']['message'])
                self.assertNotIn('[[', update['response']['message'])

    def test_a_product_named_in_plain_text_is_linked_where_it_is_mentioned(self):
        # Trace thật: "Buổi chiều, chúng ta sẽ ghé thăm Cầu Hôn Phú Quốc" không có link, sản phẩm bị dồn xuống cuối.
        bridge = {**TOUR, 'productId': 'c1', 'name': 'Cầu Hôn Phú Quốc', 'attributes': {}}
        slots = [{'time': 'MORNING', 'activityType': None, 'product': deepcopy(TOUR), 'note': None, 'source': 'SEARCH',
                  'because': []},
                 {'time': 'AFTERNOON', 'activityType': None, 'product': bridge, 'note': None, 'source': 'SEARCH',
                  'because': []}]
        update, reason = narrated(state(slots=slots), 'Sáng đi [Cầu Hôn Phú Quốc tour](product:t1). '
                                                      'Chiều ghé thăm Cầu Hôn Phú Quốc, rất đẹp.')
        text = update['response']['message']
        self.assertEqual(reason, 'llm')
        self.assertIn('Chiều ghé thăm [Cầu Hôn Phú Quốc](product:c1), rất đẹp.', text)
        self.assertIn('[Full-Day Ninh Binh Tour](product:t1)', text)
        self.assertNotIn('Ngoài ra trong lịch trình', text)

    def test_a_stray_id_of_a_scheduled_product_is_dropped_but_the_product_stays_clickable(self):
        update, reason = narrated(state(), 'Đi tour Ninh Bình (product:t1) cả ngày.')
        self.assertEqual(reason, 'llm')
        self.assertIn('Đi tour Ninh Bình cả ngày.', update['response']['message'])
        self.assertIn('[Full-Day Ninh Binh Tour](product:t1)', update['response']['message'])

    def test_a_stray_unknown_id_still_falls_back(self):
        self.assertNotEqual(narrated(state(), '[x](product:t1) và Khách sạn bịa (product:fake)')[1], 'llm')

    def test_a_model_label_with_brackets_falls_back_to_rules(self):
        update, reason = narrated(state(), '[[Tên lạ] x](product:t1)')
        self.assertNotEqual(reason, 'llm')
        self.assertNotIn('[[', update['response']['message'])

    def test_unpriced_places_are_visited_freely_but_an_unpriced_hotel_is_not(self):
        current = state()
        self.assertEqual(narration._price(current, PARK), 'tham quan tự do')
        # Điểm tham quan không có giá là nơi đến chơi (người dùng chốt 01/10), không phải "giá đang cập nhật".
        sunset = {**PARK, 'name': 'Thị trấn Hoàng Hôn - Sunset Town', 'attributes': {}}
        self.assertEqual(narration._price(current, sunset), 'tham quan tự do')
        self.assertEqual(narration._price(current, {**HOTEL, 'unitPrice': None}), 'giá đang cập nhật')
        self.assertEqual(narration._price(current, HOTEL), '600.000 ₫/đêm')


class FallbackTests(unittest.TestCase):
    def test_the_rule_based_reply_has_every_section(self):
        current = state(stay=HOTEL)
        text = narration.fallback_message(current, current['response'])
        for part in ('**Lịch trình 1 ngày ở Hà Nội**', 'Mình ghi nhận đổi ngày đi thành 15/10/2026',
                     '**Nơi nghỉ**', '[Old Quarter Hotel](product:h1) — 1 đêm · 600.000 ₫/đêm',
                     '**Ngày 1 · 15/10/2026**', '• Cả ngày — [Full-Day Ninh Binh Tour](product:t1) · 850.000 ₫/người',
                     '**Chi phí dự kiến**', 'vượt ngân sách 1.000.000 ₫', '**Lưu ý**', 'khung lịch trình bên phải'):
            self.assertIn(part, text)
        self.assertEqual(validation.answer_text({**current['response'], 'message': text}), text)

    def test_unknown_total_is_said_softly(self):
        current = state(total=None, status='UNKNOWN', previous=dict(INTENT))
        text = narration.fallback_message(current, current['response'])
        self.assertIn('Mình gợi ý lịch trình như sau:', text)
        self.assertIn('chưa cộng thành một con số tổng', text)

    def test_a_day_without_products_is_free_time(self):
        current = state(slots=[])
        self.assertIn('tự do nghỉ ngơi', narration.fallback_message(current, current['response']))

    def test_the_airport_transfer_lines_are_kept_in_slot_order(self):
        """Ngày đến/ngày về có dòng di chuyển theo giờ bay (AC-AGT-02); fallback in nó bằng ghi chú, đúng thứ tự buổi."""
        transfer = {'time': 'EVENING', 'activityType': 'TRANSFER', 'product': None, 'note': 'Ra sân bay.',
                    'source': None, 'because': []}
        park = {'time': 'MORNING', 'activityType': None, 'product': deepcopy(PARK), 'note': 'Tham quan.',
                'source': 'SEARCH', 'because': []}
        current = state(slots=[park, transfer])
        text = narration.fallback_message(current, current['response'])
        self.assertIn('[Hồ Gươm](product:p1)', text)
        self.assertIn('• Buổi tối — Ra sân bay.', text)
        self.assertLess(text.index('Hồ Gươm'), text.index('Ra sân bay.'))
        only_transfer = state(slots=[{**transfer, 'note': 'Di chuyển từ sân bay, nhận phòng.'}])
        text = narration.fallback_message(only_transfer, only_transfer['response'])
        self.assertIn('• Buổi tối — Di chuyển từ sân bay, nhận phòng.', text)
        self.assertNotIn('tự do nghỉ ngơi', text)


NO_STAY = {'code': 'NO_STAY_AVAILABLE', 'message': 'Khách sạn ở Hà Nội trong dữ liệu hiện chỉ nhận đặt từ 15/10/2026.'}


class NoStayTests(unittest.TestCase):
    """`compose` thêm `NO_STAY_AVAILABLE`; lời diễn giải nêu lý do ở mục riêng ngay trước mục chi phí."""

    def test_the_reason_sits_before_the_cost_section_in_the_llm_reply(self):
        current = state()
        current['response']['warnings'].append(NO_STAY)
        text = narrated(current, 'Một ngày ở Hà Nội.\n\n**Ngày 1 · 15/10/2026**\n'
                                 '• Cả ngày — [Tour](product:t1) ([[price:t1]]): đi sớm.\n\n'
                                 '**Chi phí dự kiến**\n• [[total]]')[0]['response']['message']
        self.assertIn(f"**Chưa có khách sạn**\n{NO_STAY['message']}\n\n**Chi phí dự kiến**", text)

    def test_the_rule_based_reply_has_the_reason_too(self):
        current = state()
        current['response']['warnings'].append(NO_STAY)
        text = narration.fallback_message(current, current['response'])
        self.assertIn(f"**Chưa có khách sạn**\n{NO_STAY['message']}\n\n**Chi phí dự kiến**", text)

    def test_the_llm_is_told_the_system_explains_the_missing_stay(self):
        current = state()
        self.assertIn('no_stay_explained: false', narration.narration_input(current)[1][1])
        current['response']['warnings'].append(NO_STAY)
        self.assertIn('no_stay_explained: true', narration.narration_input(current)[1][1])


CRITERIA = {'code': 'PLAN_CRITERIA', 'message': 'Mình gom các điểm gần nhau vào cùng một ngày.'}


class PlanCriteriaTests(unittest.TestCase):
    """`compose` thêm `PLAN_CRITERIA` (AC-AGT-04); lời diễn giải nêu tiêu chí ở mục riêng ngay trước mục chi phí."""

    def test_the_criteria_sits_before_the_cost_section_in_the_llm_reply(self):
        current = state()
        current['response']['warnings'].append(CRITERIA)
        text = narrated(current, 'Một ngày ở Hà Nội.\n\n**Ngày 1 · 15/10/2026**\n'
                                 '• Cả ngày — [Tour](product:t1) ([[price:t1]]): đi sớm.\n\n'
                                 '**Chi phí dự kiến**\n• [[total]]')[0]['response']['message']
        self.assertIn(f"**Cách mình xếp lịch**\n{CRITERIA['message']}\n\n**Chi phí dự kiến**", text)

    def test_the_rule_based_reply_has_the_criteria_too(self):
        current = state()
        current['response']['warnings'].append(CRITERIA)
        text = narration.fallback_message(current, current['response'])
        self.assertIn(f"**Cách mình xếp lịch**\n{CRITERIA['message']}\n\n**Chi phí dự kiến**", text)

    def test_the_llm_is_told_the_system_states_the_criteria(self):
        current = state()
        self.assertIn('criteria_shown_separately: false', narration.narration_input(current)[1][1])
        current['response']['warnings'].append(CRITERIA)
        self.assertIn('criteria_shown_separately: true', narration.narration_input(current)[1][1])


class NodeTests(unittest.TestCase):
    def llm(self, result=None, error=None):
        def with_structured_output(schema):
            def invoke(prompt):
                self.prompt = prompt
                if error:
                    raise error
                return result
            async def ainvoke(prompt):
                return invoke(prompt)
            return SimpleNamespace(invoke=invoke, ainvoke=ainvoke)
        return SimpleNamespace(with_structured_output=with_structured_output)

    def test_other_statuses_pass_through(self):
        current = {**state(), 'response': {'status': 'NO_RESULTS', 'message': 'x'}}
        self.assertNotIn('response', nodes.narrate_node(current, llm=self.llm(error=AssertionError('no call'))))

    def test_model_failure_uses_the_rule_based_reply(self):
        update = nodes.narrate_node(state(), llm=self.llm(error=RuntimeError('provider down')))
        self.assertIn('**Chi phí dự kiến**', update['response']['message'])
        self.assertEqual(update['events'][0]['metadata']['reason'], 'llm_failed')

    def test_async_timeout_uses_the_rule_based_reply(self):
        async def slow(prompt):
            await asyncio.sleep(1)
        llm = SimpleNamespace(with_structured_output=lambda schema: SimpleNamespace(ainvoke=slow))
        update = asyncio.run(nodes.narrate_node_async(state(), llm=llm, timeout_seconds=0.01))
        self.assertIn('**Lưu ý**', update['response']['message'])

    def test_payload_has_the_itinerary_without_prices(self):
        nodes.narrate_node(state(stay=HOTEL), llm=self.llm(ItineraryNarration(message='[x](product:t1)')))
        payload = yaml.safe_load(self.prompt[1][1])
        self.assertEqual(payload['itinerary']['days'][0]['items'][0]['productId'], 't1')
        self.assertEqual(payload['changes'], [{'field': 'startDate', 'from': '14/10/2026', 'to': '15/10/2026'}])
        self.assertNotIn('850000', self.prompt[1][1])


class GroundingAndGuardrailTests(unittest.TestCase):
    def test_finalize_rejects_a_message_linking_a_product_outside_the_itinerary(self):
        response = {**state()['response'], 'message': '**T**\n[x](product:fake)'}
        self.assertEqual(narration.unknown_links(response), ['fake'])

    def test_a_booking_claim_in_the_narration_is_caught(self):
        response = {**state()['response'], 'message': 'Mình đã đặt [x](product:t1) cho bạn.'}
        self.assertTrue(guardrails.output_violations(response))

    def test_history_shows_plain_names_to_the_model(self):
        current = {**state(), 'conversation_history': [
            {'role': 'user', 'content': 'Hà Nội'}, {'role': 'assistant', 'content': '**T**\nĐi [Tour A](product:t1) nhé'}]}
        self.assertEqual(llm_context(current)['last_assistant_message'], 'Đi Tour A nhé')


if __name__ == '__main__':
    unittest.main()
