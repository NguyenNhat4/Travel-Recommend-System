"""Node `filter`: bỏ điểm tham quan trùng trước `compose` (AC-AGT-04, chốt 2026-10-08)."""
import asyncio
import unittest
from types import SimpleNamespace

from src.backend.app.agents import nodes
from src.backend.app.agents.models import DuplicatePair, DuplicatePairs

WATER_TAXI = '[Grand World Phú Quốc] - Vé đi thuyền Venice (Water Taxi)'


def product(pid, name, price, taxonomy='attraction'):
    return {'productId': pid, 'name': name, 'taxonomy': taxonomy, 'unitPrice': price, 'available': True,
            'attributes': {'ticketed': True}}


def state(decision='compose'):
    """Ứng viên của trace Phú Quốc 08/10/2026 (rút gọn)."""
    items = [product('sun', 'Sun World Hòn Thơm', 850000), product('cap', 'Cáp Treo Hòn Thơm', 850000),
             product('kiss', 'Show diễn Kiss Of The Sea', 700000), product('e35d', WATER_TAXI, 188000),
             product('f540', WATER_TAXI, 182000), product('hotel', 'Sunset Bridge Hotel', 732000, 'hotel')]
    return {'decision': decision, 'candidates': {item['productId']: item for item in items}, 'sources': {},
            'intent': {'destination': 'Phú Quốc'}, 'warnings': [{'code': 'SNAPSHOT_ONLY', 'message': 'x'}],
            'request_id': 'test'}


class FakeLLM:
    def __init__(self, pairs=(), error=None, not_duplicates=()):
        self.result = DuplicatePairs(pairs=[
            *(DuplicatePair(ids=list(pair), reason='cùng nơi', duplicate=True) for pair in pairs),
            *(DuplicatePair(ids=list(pair), reason='hai nơi khác nhau', duplicate=False) for pair in not_duplicates)])
        self.error = error
        self.prompts = []

    def with_structured_output(self, schema):
        assert schema is DuplicatePairs

        def invoke(prompt):
            self.prompts.append(prompt)
            if self.error:
                raise self.error
            return self.result

        async def ainvoke(prompt):
            return invoke(prompt)
        return SimpleNamespace(invoke=invoke, ainvoke=ainvoke)


class FilterNodeTests(unittest.TestCase):
    def test_rule_and_llm_pairs_leave_one_product_per_place(self):
        llm = FakeLLM(pairs=[('sun', 'cap'), ('kiss', 'made-up')])
        update = nodes.filter_node(state(), llm=llm)
        self.assertEqual(sorted(update['candidates']), ['cap', 'f540', 'hotel', 'kiss'])
        dropped = {item['productId']: item['by'] for item in update['dropped_duplicates']}
        self.assertEqual(dropped, {'e35d': 'rule', 'sun': 'llm'})
        codes = [(w['code'], w.get('productId')) for w in update['warnings']]
        self.assertEqual(codes, [('SNAPSHOT_ONLY', None), ('PRODUCT_DROPPED_DUPLICATE', 'e35d'),
                                 ('PRODUCT_DROPPED_DUPLICATE', 'sun')])
        self.assertIn('Bỏ "Sun World Hòn Thơm" vì trùng với "Cáp Treo Hòn Thơm".',
                      [w['message'] for w in update['warnings']])
        self.assertEqual(update['events'][0]['metadata'], {'reason': 'llm', 'by_rule': 1, 'by_llm': 1})

    def test_a_pair_the_llm_marks_as_not_duplicate_is_ignored(self):
        # Trace 08/10/2026: cặp (hòn Thơm, Vinpearl Safari) với lý do "là hai địa điểm khác nhau" từng làm Safari bị bỏ.
        update = nodes.filter_node(state(), llm=FakeLLM(not_duplicates=[('sun', 'kiss')]))
        self.assertIn('sun', update['candidates'])
        self.assertIn('kiss', update['candidates'])

    def test_the_llm_sees_only_ids_and_names_left_after_the_rule(self):
        llm = FakeLLM()
        nodes.filter_node(state(), llm=llm)
        human = llm.prompts[0][1][1]
        self.assertIn('id: f540', human)
        self.assertNotIn('e35d', human)  # đã bỏ bằng luật cùng tên
        self.assertNotIn('hotel', human)
        self.assertNotIn('850000', human)

    def test_a_failing_llm_keeps_the_rule_result(self):
        update = asyncio.run(nodes.filter_node_async(state(), llm=FakeLLM(error=RuntimeError('provider error'))))
        self.assertEqual(sorted(update['candidates']), ['cap', 'f540', 'hotel', 'kiss', 'sun'])
        self.assertEqual(update['events'][0]['metadata']['reason'], 'llm_failed')

    def test_turns_that_do_not_reach_an_itinerary_pass_through_without_the_llm(self):
        llm = FakeLLM()
        update = nodes.filter_node(state(decision='no_results'), llm=llm)
        self.assertEqual(list(update), ['events'])
        self.assertEqual(llm.prompts, [])

    def test_a_single_attraction_needs_no_llm(self):
        llm = FakeLLM()
        current = state()
        current['candidates'] = {pid: item for pid, item in current['candidates'].items() if pid in {'kiss', 'hotel'}}
        update = nodes.filter_node(current, llm=llm)
        self.assertEqual(llm.prompts, [])
        self.assertEqual(update['events'][0]['metadata']['reason'], 'rule_only')


if __name__ == '__main__':
    unittest.main()
