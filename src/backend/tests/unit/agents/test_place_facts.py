"""Tên gõ khác của một nơi khớp nơi trong catalog (`domain/itinerary/exploration.closest_matches`, chat thử 16 kiểu, M03).

Job khám phá của orchestrator dùng luật này để tìm mốc "gần <nơi>" (`steps/jobs.py`): khớp gần đúng khi đủ từ chung,
không đoán khi tên quá chung. Tên không chung đủ từ với catalog ("Hồ Gươm" và "Hồ Hoàn Kiếm") thì không khớp; lỗi
D1-01 của kịch bản demo nằm ở đây (plan gỡ luồng cũ, D5).
"""
import unittest

from src.backend.app.domain.itinerary import exploration as rules

from .test_itinerary_runtime import product

LANG = product('lang', destination='Hà Nội', name='Lăng Chủ tịch Hồ Chí Minh', reviewCount=900, unitPrice=None,
               attributes={'openingHours': '08:00–11:00'})
HO = product('ho', destination='Hà Nội', name='Hồ Hoàn Kiếm', reviewCount=1139, unitPrice=None)


class PlaceSearchTests(unittest.TestCase):
    def test_a_close_but_not_exact_name_still_finds_the_place(self):
        self.assertEqual([p['productId'] for p in rules.closest_matches([HO, LANG], 'Lăng Bác Hồ')], ['lang'])
        # Một từ chung ("lăng") không đủ.
        self.assertEqual(rules.closest_matches([LANG], 'Lăng Dục Đức'), [])
        self.assertEqual(rules.closest_matches([LANG], 'Lăng'), [])

    def test_equally_close_places_are_all_returned_so_the_job_does_not_guess(self):
        ha_noi = product('hn', destination='Hà Nội', name='Khu Phố Cổ Hà Nội')
        hoi_an = product('ha', destination='Hội An', name='Phố cổ Hội An')
        self.assertEqual(len(rules.closest_matches([ha_noi, hoi_an], 'Phố cổ')), 2)
        self.assertEqual([p['productId'] for p in rules.closest_matches([ha_noi, hoi_an], 'Phố cổ Hội An')], ['ha'])


if __name__ == '__main__':
    unittest.main()
