"""Bỏ điểm tham quan trùng trước khi xếp lịch (AC-AGT-04, node `filter`, chốt 2026-10-08).

Dữ liệu theo trace LangSmith 08/10/2026, câu "Lên lịch trình 3 ngày tại Phú Quốc…": ba sản phẩm Hòn Thơm và hai vé Water Taxi
cùng tên đều vào lịch.
"""
import unittest

from src.backend.app.domain.itinerary.dedupe import apply_pairs, filterable, same_name_pairs

WATER_TAXI = '[Grand World Phú Quốc] - Vé đi thuyền Venice (Water Taxi)'


def product(pid, name, price=None, taxonomy='attraction', ticketed=True):
    return {'productId': pid, 'name': name, 'taxonomy': taxonomy, 'unitPrice': price, 'available': True,
            'attributes': {'ticketed': ticketed}}


def catalog(*products):
    return {item['productId']: item for item in products}


class SameNameTests(unittest.TestCase):
    def test_names_equal_ignoring_accents_case_and_punctuation_pair_up(self):
        items = [product('b', WATER_TAXI, 182000), product('a', WATER_TAXI.upper(), 188000),
                 product('c', 'Sun World Hòn Thơm', 850000)]
        self.assertEqual(same_name_pairs(items), [('a', 'b')])

    def test_three_products_with_one_name_pair_up_in_every_way(self):
        items = [product(pid, WATER_TAXI) for pid in 'abc']
        self.assertEqual(same_name_pairs(items), [('a', 'b'), ('a', 'c'), ('b', 'c')])

    def test_two_water_taxi_tickets_keep_the_cheaper_one(self):
        candidates = catalog(product('e35d', WATER_TAXI, 188000), product('f540', WATER_TAXI, 182000))
        kept, dropped = apply_pairs(candidates, {}, same_name_pairs(candidates.values()), 'rule')
        self.assertEqual(list(kept), ['f540'])
        self.assertEqual(dropped, [{'productId': 'e35d', 'name': WATER_TAXI, 'duplicateOf': 'f540',
                                    'duplicateOfName': WATER_TAXI, 'by': 'rule'}])


class ApplyPairsTests(unittest.TestCase):
    def setUp(self):
        self.candidates = catalog(
            product('hon', 'hòn Thơm', None, ticketed=False),
            product('sun', 'Sun World Hòn Thơm', 850000),
            product('cap', 'Cáp Treo Hòn Thơm', 850000),
            product('kiss', 'Show diễn Kiss Of The Sea', 700000),
            product('hotel', 'Sunset Bridge Hotel', 732000, taxonomy='hotel'),
        )

    def test_every_pair_of_one_place_leaves_one_product(self):
        pairs = [('cap', 'hon'), ('sun', 'cap'), ('hon', 'sun')]
        kept, dropped = apply_pairs(self.candidates, {}, pairs, 'llm')
        self.assertEqual(sorted(kept), ['hon', 'hotel', 'kiss'])  # tham quan tự do tính 0 đ nên rẻ nhất
        self.assertEqual({item['productId'] for item in dropped}, {'sun', 'cap'})
        self.assertTrue(all(item['duplicateOf'] == 'hon' and item['by'] == 'llm' for item in dropped))
        self.assertEqual(apply_pairs(self.candidates, {}, list(reversed(pairs)), 'llm'), (kept, dropped))

    def test_a_bundle_does_not_join_the_two_tickets_it_contains(self):
        # Trace 08/10/2026: (Bảo tàng Gấu, combo) và (combo, Water Taxi) từng làm Bảo tàng Gấu bị bỏ vì "trùng" Water Taxi.
        candidates = catalog(product('bear', 'Bảo Tàng Gấu Teddy', 200000), product('taxi', 'Water Taxi', 182000),
                             product('combo', 'Water Taxi + Bảo Tàng Gấu', 300000))
        kept, dropped = apply_pairs(candidates, {}, [('bear', 'combo'), ('combo', 'taxi')], 'llm')
        self.assertEqual(sorted(kept), ['bear', 'taxi'])
        self.assertEqual([(item['productId'], item['duplicateOf']) for item in dropped], [('combo', 'taxi')])

    def test_search_is_kept_over_recommendation_even_when_dearer(self):
        kept, _ = apply_pairs(self.candidates, {'cap': 'recommendation'}, [('sun', 'cap')], 'llm')
        self.assertIn('sun', kept)
        self.assertNotIn('cap', kept)

    def test_unknown_ids_self_pairs_and_non_attractions_are_ignored(self):
        pairs = [('sun', 'made-up'), ('kiss', 'kiss'), ('kiss', 'hotel')]
        kept, dropped = apply_pairs(self.candidates, {}, pairs, 'llm')
        self.assertEqual(kept, self.candidates)
        self.assertEqual(dropped, [])

    def test_the_input_candidates_are_not_mutated(self):
        before = dict(self.candidates)
        apply_pairs(self.candidates, {}, [('sun', 'cap')], 'llm')
        self.assertEqual(self.candidates, before)

    def test_multi_day_passes_are_not_filterable(self):
        candidates = catalog(product('pass', '[03 ngày không giới hạn] - VinWonders', 2000000), *self.candidates.values())
        self.assertNotIn('pass', {item['productId'] for item in filterable(candidates)})
        self.assertNotIn('hotel', {item['productId'] for item in filterable(candidates)})


if __name__ == '__main__':
    unittest.main()
