"""Ngữ cảnh đã diễn giải cho LLM và các lỗi hiểu sai trong trace thật (LangSmith `nhat-10-1`, 01/10/2026).

Hội thoại: "đi hà nội" → "3 ngày" → "doi diem di" → "không đổi nữa" (lịch trình Hà Nội) → "mình muốn đi biển cơ"
→ "biển hà nội". Agent hỏi xác nhận như mâu thuẫn, từ chối "chỉ hỗ trợ trong nước", rồi lặp nguyên câu từ chối.
"""
import unittest

import yaml

from src.backend.app.agents import nodes
from src.backend.app.agents.models import Extraction
from src.backend.app.agents.nodes import intake_node
from src.backend.app.agents.steps.classification import extract_result
from src.backend.app.agents.steps.conversation import (
    clarification_fallback, conversation_input, conversational_update,
)
from src.backend.app.agents.models import ConversationalAnswer
from src.backend.app.agents.steps.history import llm_context
from src.backend.app.agents.steps.tool_planning import check_destination
from src.backend.app.agents.steps.turn_notes import question_note, trip_summary, turn_note
from src.backend.app.domain.itinerary.planning import empty_intent

HANOI = {**empty_intent(), 'destination': 'Hà Nội', 'days': 3}
SHOWN = [{'productId': 'h1', 'name': 'The Sun Ha Noi Hotel', 'taxonomy': 'hotel'},
         {'productId': 'a1', 'name': 'Hanoi Sightseeing Bus', 'taxonomy': 'attraction'}]
ITINERARY_TEXT = ('**Khám phá Hà Nội trong 3 ngày**\nMình đã lên kế hoạch cho bạn.\n\n**Nơi nghỉ**\n'
                  '• [The Sun Ha Noi Hotel](product:h1) (550.000 ₫/đêm): nơi nghỉ lý tưởng.\n' + 'x' * 600)


def itinerary_response():
    product = {'productId': 'h1', 'name': 'The Sun Ha Noi Hotel', 'taxonomy': 'hotel'}
    bus = {'productId': 'a1', 'name': 'Hanoi Sightseeing Bus', 'taxonomy': 'attraction'}
    return {'status': 'COMPLETED', 'itinerary': {'stay': {'product': product},
                                                 'days': [{'day': 1, 'slots': [{'product': bus}, {'product': None}]}]}}


def planned_state(query, **extra):
    """Sau lịch trình Hà Nội 3 ngày: đã hỏi chi tiết, có sản phẩm đã cho xem."""
    # Lập lịch cần đủ ngày đi và số người (AC-AGT-01), nên lịch đã gửi luôn có hai trường này.
    intent = {**HANOI, 'startDate': '2099-10-02', 'party': {'type': 'SOLO', 'adults': 1, 'children': 0}}
    return {**intake_node({'query': query}), 'intent': intent, 'start_date_asked': True,
            'clarification_rounds': 1, 'previous_selection': list(SHOWN), **extra}


class TurnNoteTests(unittest.TestCase):
    def test_an_itinerary_is_noted_by_place_and_length_only(self):
        # Trace nhat-10-1 (02/10): tên sản phẩm lặp ở mỗi ghi chú lịch trình, ở `last_assistant_message` và ở
        # `previous_selection`; sản phẩm đã cho xem chỉ còn ở `previous_selection` (kèm id).
        note = turn_note({'intent': HANOI}, itinerary_response(), 200)
        self.assertEqual(note, 'gửi lịch trình Hà Nội 3 ngày')

    def test_a_rejected_value_keeps_its_real_reason(self):
        state = {'clarification_reason': 'invalid_input', 'missing_fields': ['destination'],
                 'invalid_inputs': [{'field': 'destination', 'value': 'biển', 'reason': 'unsupported_destination'}]}
        self.assertEqual(question_note(state),
                         'không dùng được điểm đến "biển": không có trong danh sách điểm đến; hỏi điểm đến')

    def test_a_change_question_names_the_current_value(self):
        state = {'clarification_reason': 'change_without_value', 'missing_fields': ['destination'], 'intent': HANOI}
        self.assertEqual(question_note(state), 'hỏi điểm đến mới (hiện là Hà Nội)')

    def test_other_reasons(self):
        cases = [({'clarification_reason': 'suggest_form', 'missing_fields': ['destination']},
                  'gửi form điền sẵn, còn thiếu điểm đến'),
                 ({'clarification_reason': 'destination_kind', 'destination_kind': 'biển'},
                  'hỏi chọn điểm đến kiểu "biển" trong danh sách điểm đến'),
                 ({'missing_fields': ['startDate', 'budget']}, 'hỏi ngày khởi hành, ngân sách'),
                 ({'refusal': True}, 'từ chối: yêu cầu ngoài phạm vi lập lịch trình')]
        for state, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(question_note(state), expected)

    def test_english(self):
        note = turn_note({'intent': HANOI, 'language': 'en'}, itinerary_response(), 200)
        self.assertTrue(note.startswith('sent a 3-day itinerary for Hà Nội'))

    def test_trip_summary_lists_what_is_missing(self):
        self.assertEqual(trip_summary({'intent': HANOI}), 'Hà Nội, 3 ngày; chưa có: ngày khởi hành, số người, ngân sách, nơi đi')
        self.assertEqual(trip_summary({'intent': empty_intent()}), 'chưa có thông tin chuyến đi')


class LlmContextTests(unittest.TestCase):
    def history(self, note=True):
        return [{'role': 'user', 'content': 'không đổi nữa'},
                {'role': 'assistant', 'content': ITINERARY_TEXT,
                 **({'note': 'gửi lịch trình Hà Nội 3 ngày'} if note else {})}]

    def test_an_itinerary_turn_reaches_the_model_as_a_note_without_prices(self):
        context = llm_context(planned_state('mình muốn đi biển cơ', conversation_history=self.history()))
        dumped = yaml.safe_dump(context, allow_unicode=True)
        self.assertNotIn('550.000', dumped)
        self.assertNotIn('₫', dumped)
        self.assertEqual(context['conversation_history'],
                         [{'user': 'không đổi nữa'}, {'assistant_did': 'gửi lịch trình Hà Nội 3 ngày'}])
        self.assertEqual(context['last_assistant_message'], 'gửi lịch trình Hà Nội 3 ngày')
        self.assertEqual(context['stage'], 'đã gửi lịch trình cho chuyến này')
        self.assertTrue(context['trip_so_far'].startswith('Hà Nội, 3 ngày'))
        self.assertNotIn('known_intent', context)

    def test_history_saved_before_notes_falls_back_to_the_title(self):
        context = llm_context(planned_state('x', conversation_history=self.history(note=False)))
        self.assertEqual(context['conversation_history'][1], {'assistant_did': 'Khám phá Hà Nội trong 3 ngày'})

    def test_a_short_question_stays_verbatim_for_short_answers(self):
        history = [{'role': 'user', 'content': 'đi Huế'},
                   {'role': 'assistant', 'content': '**Chuyến đi kéo dài mấy ngày?**\nBạn đi mấy ngày?',
                    'note': 'hỏi số ngày'}]
        context = llm_context({'query': '2', 'intent': empty_intent(), 'conversation_history': history})
        self.assertEqual(context['conversation_history'], [{'user': 'đi Huế'}, {'assistant_did': 'hỏi số ngày'}])
        self.assertEqual(context['last_assistant_message'], 'Bạn đi mấy ngày?')

    def test_each_entry_names_its_speaker_so_assistant_notes_never_read_as_the_user(self):
        dumped = yaml.dump(llm_context(planned_state('x', conversation_history=self.history())), allow_unicode=True)
        self.assertNotIn('role:', dumped)
        self.assertNotIn('content:', dumped)
        self.assertIn('- assistant_did: gửi lịch trình Hà Nội 3 ngày', dumped)


class ExtractionTests(unittest.TestCase):
    def test_a_change_request_is_not_a_conflict(self):
        # Trace: "doi diem di" → conflict=true và change_without_value=['destination'].
        result = extract_result(planned_state('doi diem di'),
                                Extraction(conflict=True, change_without_value=['destination']))
        self.assertEqual(result['clarification_reason'], 'change_without_value')
        self.assertEqual(result['missing_fields'], ['destination'])

    def test_a_new_date_that_differs_from_the_trip_is_a_change_not_a_conflict(self):
        # Trace nhat-10-1: chip "Đi Hà Nội 3 ngày từ ngày 15/10/2026" sau lịch đi 02/10 ra conflict=true kèm
        # change_without_value=['startDate'] dù patch đã có ngày mới; trước đây bị hỏi "Xác nhận ngày khởi hành".
        current = planned_state('Đi Hà Nội 3 ngày từ ngày 15/10/2099')
        current['intent'] = {**current['intent'], 'startDate': '2099-10-02'}
        result = extract_result(current, Extraction(conflict=True, change_without_value=['startDate'],
                                                    patch={'startDate': '2099-10-15', 'days': 3}))
        self.assertNotIn('clarification_reason', {k: v for k, v in result.items() if v})
        self.assertEqual(result['intent']['startDate'], '2099-10-15')
        self.assertEqual(result['decision'], 'tool')

    def test_a_real_conflict_is_still_asked(self):
        result = extract_result(planned_state('đi 3 ngày từ 10/10 đến 20/10'), Extraction(conflict=True))
        self.assertEqual(result['clarification_reason'], 'conflict')

    def test_a_kind_of_place_asks_which_destination_without_counting_a_round(self):
        result = extract_result(planned_state('mình muốn đi biển cơ'), Extraction(destination_kind='biển'))
        self.assertEqual(result['decision'], 'missing_info')
        self.assertEqual(result['clarification_reason'], 'destination_kind')
        self.assertEqual(result['destination_kind'], 'biển')
        self.assertEqual(result['missing_fields'], ['destination'])
        self.assertEqual(result['clarification_rounds'], 1)
        self.assertEqual(result['intent']['destination'], 'Hà Nội')

    def test_a_kind_also_written_as_the_destination_is_not_matched_against_the_catalog(self):
        result = extract_result(planned_state('mình muốn đi biển cơ'),
                                Extraction(patch={'destination': 'biển'}, destination_kind='Biển'))
        self.assertEqual(result['clarification_reason'], 'destination_kind')
        self.assertEqual(result['intent']['destination'], 'Hà Nội')

    def test_a_named_destination_wins_over_the_kind(self):
        result = extract_result(planned_state('biển Đà Nẵng'),
                                Extraction(patch={'destination': 'Đà Nẵng'}, destination_kind='biển'))
        self.assertEqual(result['decision'], 'tool')
        self.assertEqual(result['intent']['destination'], 'Đà Nẵng')

    def test_a_first_message_with_only_a_kind_asks_destination_and_days(self):
        state = intake_node({'query': 'đi biển'})
        result = extract_result(state, Extraction(destination_kind='biển'))
        self.assertEqual(result['missing_fields'], ['destination', 'days'])
        self.assertEqual(result['clarification_rounds'], 0)

    def test_a_hotel_copied_from_the_last_itinerary_is_dropped(self):
        # Trace: "mình muốn đi biển cơ" → specific_hotel = khách sạn của lịch trình Hà Nội.
        result = extract_result(planned_state('mình muốn đi biển cơ'),
                                Extraction(constraints={'specific_hotel': 'The Sun Ha Noi Hotel'}))
        self.assertNotIn('specific_hotel', result['constraints'])

    def test_a_shown_hotel_named_in_the_message_is_kept(self):
        result = extract_result(planned_state('giữ khách sạn The Sun nhé'),
                                Extraction(constraints={'specific_hotel': 'The Sun Ha Noi Hotel'}))
        self.assertEqual(result['constraints']['specific_hotel'], 'The Sun Ha Noi Hotel')

    def test_a_new_hotel_not_shown_before_is_kept(self):
        result = extract_result(planned_state('ở Mường Thanh'),
                                Extraction(constraints={'specific_hotel': 'Mường Thanh Grand'}))
        self.assertEqual(result['constraints']['specific_hotel'], 'Mường Thanh Grand')


class CatalogTools:
    supports_catalog = True

    async def list_destinations(self):
        return {'destinations': [{'destination': name, 'productCount': count}
                                 for name, count in (('Hà Nội', 30), ('Đà Nẵng', 20), ('Nha Trang', 10))]}


class DestinationKindFlowTests(unittest.IsolatedAsyncioTestCase):
    async def test_the_catalog_list_is_loaded_even_without_a_destination(self):
        state = intake_node({'query': 'đi biển'})
        update = extract_result(state, Extraction(destination_kind='biển'))
        checked = await check_destination(state, update, tools=CatalogTools(), timeout_seconds=1, llm=None,
                                          llm_timeout_seconds=1)
        self.assertEqual(checked['supported_destinations'], ['Hà Nội', 'Đà Nẵng', 'Nha Trang'])
        self.assertEqual(checked['clarification_reason'], 'destination_kind')

    def kind_state(self, **extra):
        return {**planned_state('biển hà nội'), 'decision': 'missing_info', 'clarification_reason': 'destination_kind',
                'destination_kind': 'biển', 'missing_fields': ['destination'],
                'supported_destinations': ['Hà Nội', 'Đà Nẵng', 'Nha Trang'], **extra}

    def test_the_reply_model_gets_the_kind_the_list_and_what_this_turn_does(self):
        payload = yaml.safe_load(conversation_input(self.kind_state())[1][1])
        self.assertEqual(payload['destination_kind'], 'biển')
        self.assertEqual(payload['supported_destinations'], ['Hà Nội', 'Đà Nẵng', 'Nha Trang'])
        self.assertEqual(payload['this_turn'], 'hỏi chọn điểm đến kiểu "biển" trong danh sách điểm đến')

    def test_no_prefilled_form_even_after_several_rounds(self):
        update = conversational_update(self.kind_state(clarification_rounds=3),
                                       ConversationalAnswer(title='Chọn điểm đến có biển', message='Đà Nẵng nhé?'))
        self.assertNotIn('clarificationForm', update['response'])
        self.assertEqual(update['response']['suggestedValues']['destination'], ['Hà Nội', 'Đà Nẵng', 'Nha Trang'])

    def test_the_fixed_fallback_has_a_title_and_lists_no_place(self):
        question = clarification_fallback(self.kind_state())['response']['question']
        self.assertTrue(question.startswith('**Chọn điểm đến hợp ý bạn**\n'))
        self.assertNotIn('Hà Nội', question.split('\n', 1)[1])


class FinalizeNoteTests(unittest.TestCase):
    def test_finalize_stores_the_note_with_the_reply(self):
        state = {**planned_state('mình muốn đi biển cơ'), 'conversation_id': 'c1', 'http_status': 200,
                 'clarification_reason': 'destination_kind', 'destination_kind': 'biển',
                 'missing_fields': ['destination'],
                 'response': {'status': 'NEEDS_CLARIFICATION', 'conversationId': 'c1', 'question': '**T**\nĐi đâu?',
                              'knownIntent': HANOI, 'missingFields': ['destination']}}
        update = nodes.finalize_node(state)
        self.assertEqual(update['conversation_history'][-1]['note'],
                         'hỏi chọn điểm đến kiểu "biển" trong danh sách điểm đến')


if __name__ == '__main__':
    unittest.main()
