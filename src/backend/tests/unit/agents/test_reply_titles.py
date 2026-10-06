"""Mọi câu trả lời của trợ lý có dòng đầu `**Tiêu đề**` tóm tắt phần chi tiết bên dưới (chào hỏi, cảm ơn thì không)."""
import unittest

from src.backend.app.agents.models import ConversationalAnswer
from src.backend.app.agents.steps import composition, conversation, messages
from src.backend.app.agents.steps.history import llm_context
from src.backend.app.agents.steps.messages import strip_title, titled


def state(**fields):
    return {'conversation_id': 'c1', 'intent': {}, 'missing_fields': [], 'language': 'vi', **fields}


class TitledTests(unittest.TestCase):
    def test_joins_a_bold_first_line_and_the_body(self):
        self.assertEqual(titled('Chuyến đi mấy ngày?', 'Bạn đi mấy ngày?'), '**Chuyến đi mấy ngày?**\nBạn đi mấy ngày?')

    def test_cleans_markdown_and_extra_spaces_from_a_model_title(self):
        self.assertEqual(titled('  **Ngoài  phạm vi** ', 'x'), '**Ngoài phạm vi**\nx')

    def test_a_missing_or_empty_title_keeps_the_body_as_is(self):
        for title in (None, '', '   ', '**'):
            with self.subTest(title=title):
                self.assertEqual(titled(title, 'chỉ thân'), 'chỉ thân')

    def test_a_long_title_is_cut_instead_of_failing(self):
        first = titled('a' * 300, 'x').split('\n')[0]
        self.assertEqual(first, '**' + 'a' * messages.MAX_TITLE_CHARS + '**')

    def test_strip_title_removes_only_a_bold_first_line(self):
        self.assertEqual(strip_title('**Tiêu đề**\nThân câu'), 'Thân câu')
        self.assertEqual(strip_title('Xin chào **bạn**\nđi đâu?'), 'Xin chào **bạn**\nđi đâu?')
        self.assertEqual(strip_title('Không có tiêu đề'), 'Không có tiêu đề')
        self.assertEqual(strip_title('**Chỉ tiêu đề**'), '**Chỉ tiêu đề**')


class ReplyTitleTests(unittest.TestCase):
    def test_each_clarification_case_has_its_fixed_title(self):
        cases = [
            (state(missing_fields=['destination', 'days']), 'Cần biết điểm đến và số ngày'),
            (state(missing_fields=['destination']), 'Bạn muốn đi đâu?'),
            (state(missing_fields=['days']), 'Chuyến đi kéo dài mấy ngày?'),
            (state(missing_fields=['startDate', 'party', 'budget']), 'Thêm vài chi tiết cho chuyến đi'),
            (state(missing_fields=['days'], clarification_reason='suggest_form'), 'Điền nhanh thông tin chuyến đi'),
            (state(clarification_reason='conflict'), 'Thông tin chuyến đi chưa khớp nhau'),
            (state(clarification_reason='unverified'), 'Chưa xác minh được yêu cầu của bạn'),
            (state(refusal=True), 'Ngoài phạm vi hỗ trợ'),
            (state(missing_fields=['startDate'], clarification_reason='change_without_value'), 'Bạn muốn đổi thành gì?'),
        ]
        for case, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(conversation.reply_title(case), expected)

    def test_english_titles_exist_for_every_case(self):
        for key in ('title_missing_both', 'title_missing_destination', 'title_missing_days', 'title_trip_details',
                    'title_form', 'title_conflict', 'title_unverified', 'title_out_of_scope',
                    'title_change_without_value'):
            with self.subTest(key=key):
                self.assertNotEqual(messages.message({'language': 'en'}, key), messages.message({'language': 'vi'}, key))

    def test_greetings_and_thanks_have_no_title(self):
        self.assertIsNone(conversation.reply_title(state(interaction_type='conversation', missing_fields=['days'])))


class ConversationalUpdateTests(unittest.TestCase):
    def test_the_model_title_is_used_when_given(self):
        update = conversation.conversational_update(
            state(missing_fields=['days']), ConversationalAnswer(title='Mấy ngày nhỉ', message='Bạn đi mấy ngày?'))
        self.assertEqual(update['response']['question'], '**Mấy ngày nhỉ**\nBạn đi mấy ngày?')

    def test_the_fixed_title_fills_in_when_the_model_gives_none(self):
        update = conversation.conversational_update(
            state(missing_fields=['days']), ConversationalAnswer(message='Bạn đi mấy ngày?'))
        self.assertEqual(update['response']['question'], '**Chuyến đi kéo dài mấy ngày?**\nBạn đi mấy ngày?')

    def test_a_greeting_reply_is_left_without_a_title(self):
        update = conversation.conversational_update(
            state(interaction_type='conversation', missing_fields=['destination', 'days']),
            ConversationalAnswer(title='Chào bạn', message='Xin chào! Bạn muốn đi đâu?'))
        self.assertEqual(update['response']['question'], 'Xin chào! Bạn muốn đi đâu?')

    def test_an_out_of_scope_refusal_carries_the_title_in_the_error_message(self):
        update = conversation.conversational_update(
            state(refusal=True), ConversationalAnswer(message='Mình chỉ hỗ trợ lên lịch du lịch.'))
        self.assertEqual(update['response']['error']['code'], 'VALIDATION_ERROR')
        self.assertEqual(update['response']['error']['message'],
                         '**Ngoài phạm vi hỗ trợ**\nMình chỉ hỗ trợ lên lịch du lịch.')


class FixedTextTests(unittest.TestCase):
    def test_fallback_questions_are_titled_in_both_languages(self):
        for language, title in (('vi', 'Cần biết điểm đến và số ngày'), ('en', 'I need your destination and trip length')):
            with self.subTest(language=language):
                question = conversation.clarification_fallback(
                    state(language=language, missing_fields=['destination', 'days']))['response']['question']
                self.assertTrue(question.startswith(f'**{title}**\n'))

    def test_change_without_value_fallback_names_the_fields_in_both_languages(self):
        cases = (('vi', 'Bạn muốn đổi thành gì?', 'ngày khởi hành, ngân sách'),
                 ('en', 'What would you like to change it to?', 'the departure date, the budget'))
        for language, title, fields in cases:
            with self.subTest(language=language):
                question = conversation.clarification_fallback(
                    state(language=language, missing_fields=['startDate', 'budget'],
                          clarification_reason='change_without_value'))['response']['question']
                self.assertTrue(question.startswith(f'**{title}**\n'))
                self.assertIn(fields, question)

    def test_a_greeting_fallback_has_no_title(self):
        question = conversation.clarification_fallback(
            state(interaction_type='conversation', missing_fields=['destination', 'days']))['response']['question']
        self.assertFalse(question.startswith('**'))

    def test_guardrail_block_and_out_of_scope_have_different_titles(self):
        blocked = conversation.conversational_fallback(state(refusal=True, blocked_by_guardrail='x'))
        scoped = conversation.conversational_fallback(state(refusal=True))
        self.assertTrue(blocked['response']['error']['message'].startswith('**Mình chưa thể hỗ trợ yêu cầu này**\n'))
        self.assertTrue(scoped['response']['error']['message'].startswith('**Ngoài phạm vi hỗ trợ**\n'))

    def test_required_condition_without_products_is_titled(self):
        question = conversation.constraint_clarification(state())['response']['question']
        self.assertTrue(question.startswith('**Chưa có sản phẩm đáp ứng yêu cầu bắt buộc**\n'))

    def test_no_results_and_fallback_messages_are_titled(self):
        for language, title in (('vi', 'Chưa dựng được lịch trình hoàn chỉnh'), ('en', 'Could not build a complete itinerary')):
            self.assertEqual(messages.message({'language': language}, 'fallback_title'), title)
        for language in ('vi', 'en'):
            for key in ('no_results', 'no_results_date'):
                with self.subTest(language=language, key=key):
                    text = messages.message({'language': language}, key, destination='Hà Nội', date='01/12/2026')
                    self.assertTrue(text.startswith('**') and '**\n' in text)


class HistoryTests(unittest.TestCase):
    def test_the_title_line_is_not_fed_back_to_the_model(self):
        history = [{'role': 'user', 'content': 'đi Huế'},
                   {'role': 'assistant', 'content': '**Chuyến đi kéo dài mấy ngày?**\nBạn đi mấy ngày?'}]
        context = llm_context(state(conversation_history=history))
        self.assertEqual(context['last_assistant_message'], 'Bạn đi mấy ngày?')
        self.assertEqual(context['conversation_history'][1], {'assistant_did': 'Bạn đi mấy ngày?'})
        self.assertEqual(history[1]['content'], '**Chuyến đi kéo dài mấy ngày?**\nBạn đi mấy ngày?')  # bản lưu giữ nguyên


if __name__ == '__main__':
    unittest.main()
