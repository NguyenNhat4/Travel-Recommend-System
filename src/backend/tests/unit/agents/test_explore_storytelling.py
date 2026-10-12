"""Lời dẫn khám phá kể chuyện, đủ ý và không lặp cụm khen (chat thử 10/10).

Người dùng: mô tả thẻ ngắn, khô, lặp "được khen nhiều"/"nhiều người ghé" ở mọi dòng, không có câu chuyện.
"""
import unittest

from src.backend.app.agents.models import ExploreNarration
from src.backend.app.agents.nodes import intake_node
from src.backend.app.agents.steps.exploration import (ABOUT_CHARS, _card_input, about, explore_input, explored,
                                                      once_praise)
from src.backend.app.agents.steps.prompts import EXPLORE_PROMPT
from src.backend.app.domain.itinerary.planning import empty_intent

from .test_exploration import place


def _state(query='Hà Nội có gì chơi?'):
    return {**intake_node({'query': query}), 'intent': {**empty_intent(), 'destination': 'Hà Nội'},
            'conversation_id': 'c1'}


class PraiseOnceTests(unittest.TestCase):
    def test_each_praise_phrase_is_kept_only_the_first_time(self):
        text = ('[A](product:a) đẹp về đêm; nhiều người ghé.\n'
                '[B](product:b) cổ kính; nhiều người ghé.\n'
                '[C](product:c) yên tĩnh, được du khách khen nhiều.\n'
                '[D](product:d): khách sạn có hồ bơi, được khen nhiều.')
        self.assertEqual(once_praise(text), '[A](product:a) đẹp về đêm; nhiều người ghé.\n'
                                            '[B](product:b) cổ kính.\n'
                                            '[C](product:c) yên tĩnh, được du khách khen nhiều.\n'
                                            '[D](product:d): khách sạn có hồ bơi.')

    def test_variants_of_the_same_phrase_count_as_one(self):
        text = '[A](product:a) ngay gần đó, cũng nhiều người ghé nhất ở đây.\n[B](product:b) cổ kính, nhiều người ghé.'
        self.assertEqual(once_praise(text), '[A](product:a) ngay gần đó, cũng nhiều người ghé nhất ở đây.\n'
                                            '[B](product:b) cổ kính.')

    def test_text_without_repeats_is_unchanged(self):
        text = 'Hà Nội hợp đi bộ.\n[A](product:a) cổ kính, nhiều người ghé.\n[B](product:b) có hồ bơi, giá mềm.'
        self.assertEqual(once_praise(text), text)

    def test_the_reply_never_repeats_a_praise_line_after_line(self):
        cards = [{'product': place('a', reviewCount=10), 'reasons': ['most_reviewed']},
                 {'product': place('b', reviewCount=5), 'reasons': ['also_popular']}]
        narration = ExploreNarration(title='Hà Nội', message='Hà Nội hợp đi bộ.\n'
                                     '[Nơi a](product:a) cổ kính, được khen nhiều.\n'
                                     '[Nơi b](product:b) yên bình, được khen nhiều.', suggestions=[])
        question = explored(_state(), 'Hà Nội', cards, None, narration, ['Hà Nội'])['response']['question']
        self.assertEqual(question.count('khen nhiều'), 1)


    def test_blank_lines_between_paragraphs_are_removed(self):
        cards = [{'product': place('a'), 'reasons': ['most_reviewed']}]
        narration = ExploreNarration(title='Hà Nội', message='Hà Nội hợp đi bộ.\n\n[Nơi a](product:a) cổ kính.',
                                     suggestions=[])
        question = explored(_state(), 'Hà Nội', cards, None, narration, ['Hà Nội'])['response']['question']
        self.assertNotIn('\n\n', question)


class StoryInputTests(unittest.TestCase):
    def test_about_keeps_enough_of_the_description_for_a_short_story(self):
        sentences = [f'Câu mô tả thứ {index} kể một chi tiết đáng nhớ của nơi này cho người đọc.' for index in range(12)]
        text = about(place('a', description=' '.join(sentences)))
        self.assertGreater(len(text), 360)
        self.assertLessEqual(len(text), ABOUT_CHARS)

    def test_hotel_cards_carry_their_real_amenities_for_the_story(self):
        hotel = place('ks', 'hotel', attributes={'amenities': ['Hồ bơi ngoài trời', 'Spa', 'Bữa sáng', 42]})
        item = _card_input({'product': hotel, 'reasons': ['cheapest']})
        self.assertEqual(item['highlights'], ['Hồ bơi ngoài trời', 'Spa', 'Bữa sáng'])

    def test_the_prompt_asks_for_a_story_and_forbids_repeated_praise(self):
        self.assertIn('two or three sentences', EXPLORE_PROMPT)
        self.assertIn('at most ONCE in the whole message', EXPLORE_PROMPT)
        self.assertIn('set the mood', EXPLORE_PROMPT)
        self.assertIn('never doubt or question where a card is', EXPLORE_PROMPT)

    def test_a_description_that_only_repeats_the_name_is_not_used_as_the_line(self):
        from src.backend.app.agents.steps.exploration import card_line
        museum = {**place('teddy', description='Bảo tàng Gấu Teddy tại An Giang.'), 'name': 'Bảo tàng Gấu Teddy'}
        line = card_line(_state(), {'product': museum, 'reasons': ['most_reviewed']})
        self.assertNotIn('tại An Giang', line)

    def test_card_names_are_trimmed_for_the_llm(self):
        item = _card_input({'product': {**place('h'), 'name': ' hòn Thơm'}, 'reasons': ['also_popular']})
        self.assertEqual(item['name'], 'hòn Thơm')

    def test_the_payload_has_the_longer_description(self):
        long_text = ' '.join(f'Chi tiết số {index} của nơi này rất đáng để kể lại.' for index in range(15))
        cards = [{'product': place('a', description=long_text), 'reasons': ['most_reviewed']}]
        payload = explore_input(_state(), 'Hà Nội', cards, None, ['Hà Nội'])[1][1]
        self.assertIn('Chi tiết số 8', payload)


if __name__ == '__main__':
    unittest.main()
