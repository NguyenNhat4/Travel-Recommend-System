"""Câu chữ dùng chung của câu trả lời khám phá (`steps/replies.py`): cụm khen chỉ một lần, phần mô tả catalog.

Chuyển từ `test_explore_storytelling.py` khi gỡ node `explore` cũ (13/10/2026); hai hàm này orchestrator và `narrate`
vẫn dùng.
"""
import unittest

from src.backend.app.agents.steps.replies import ABOUT_CHARS, about, once_praise


def place(pid, description="", name=None):
    return {"productId": pid, "name": name or f"Nơi {pid}", "taxonomy": "attraction", "destination": "Hà Nội",
            "description": description}


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


class AboutTests(unittest.TestCase):
    def test_keeps_enough_of_the_description_for_a_short_story(self):
        sentences = [f'Câu mô tả thứ {index} kể một chi tiết đáng nhớ của nơi này cho người đọc.' for index in range(12)]
        text = about(place('a', description=' '.join(sentences)))
        self.assertGreater(len(text), 360)
        self.assertLessEqual(len(text), ABOUT_CHARS)

    def test_drops_sentences_that_repeat_the_name_or_only_carry_data(self):
        museum = place('teddy', name='Bảo tàng Gấu Teddy',
                       description='Bảo tàng Gấu Teddy. Giờ mở cửa: 8:00–17:00. Nơi trưng bày gấu bông từ nhiều nước.')
        self.assertEqual(about(museum), 'Nơi trưng bày gấu bông từ nhiều nước.')


if __name__ == '__main__':
    unittest.main()
