"""Chọn phương án bằng hàng thẻ (AC-AGT-04, chốt 2026-10-08): `compose` dựng sẵn lịch của từng phương án, lượt chọn
lấy lịch đó ra qua `apply_option`, không phân luồng, không tìm lại, không gọi LLM."""
import unittest
from copy import deepcopy

from src.backend.app.agents import nodes, routing
from src.backend.app.agents.steps import composition, option_swap
from src.backend.app.application.itinerary.contracts import valid
from src.backend.tests.unit.agents.test_composition_plan_criteria import square_trip


def first_turn(**kwargs):
    """Lượt lập lịch: lịch ở khách sạn gần (h-close), phương án 1 là khách sạn rẻ ở xa (h-far)."""
    current = square_trip(**kwargs)
    return current, composition.composed(current)


def next_turn(previous_state: dict, composed: dict, *, query: str = '', pick: dict | None = None) -> dict:
    """State đầu lượt sau, như `intake` nạp từ hội thoại đã lưu."""
    stored = {'conversation_id': 'c1', 'query': query, 'select_stay_option': pick,
              'intent': previous_state['intent'], 'constraints': previous_state['constraints'],
              'language': previous_state['language'], 'previous_options': composed['stay_options'],
              'previous_plan': composed['current_plan'], 'conversation_history': []}
    return {**stored, **nodes.intake_node(deepcopy(stored))}


def hotel(itinerary: dict) -> str:
    return itinerary['stay']['product']['productId']


class ComposeStoresEveryOptionTests(unittest.TestCase):
    def test_each_option_is_a_full_checked_itinerary_in_the_response(self):
        _, result = first_turn()
        response = result['response']
        self.assertTrue(valid('ItineraryResponse', response))
        [option] = response['stayOptions']['options']
        self.assertEqual((option['index'], hotel(option['itinerary'])), (1, 'h-far'))
        self.assertEqual(option['moneyDelta'], -5_000_000)
        self.assertEqual(option['itinerary']['estimatedTotal'] - response['itinerary']['estimatedTotal'], -5_000_000)
        self.assertGreater(option['kmDelta'], 0)
        [stored] = result['stay_options']
        self.assertAlmostEqual(stored['distanceKm'], response['stayOptions']['distanceKm'] + option['kmDelta'],
                               places=1)
        self.assertEqual(hotel(result['current_plan']['itinerary']), 'h-close')
        self.assertNotIn('STAY_OPTIONS', {w['code'] for w in stored['warnings']})

    def test_no_options_no_field_and_nothing_to_store(self):
        current = square_trip()
        del current['candidates']['h-far']
        result = composition.composed(current)
        self.assertNotIn('stayOptions', result['response'])
        self.assertIsNone(result['current_plan'])


class FinalizeChecksOptionsTests(unittest.TestCase):
    def test_an_option_with_a_product_not_from_the_tools_is_rejected(self):
        previous, composed = first_turn()
        state = {**previous, 'response': deepcopy(composed['response']), 'http_status': 200, 'query': 'x',
                 'conversation_history': [], 'started_at': 0, 'request_id': 'r'}
        self.assertEqual(nodes.finalize_node(state)['validation_issues'], [])
        stay = state['response']['stayOptions']['options'][0]['itinerary']['stays'][0]
        stay['product'] = {**stay['product'], 'unitPrice': 1}   # giá không khớp kết quả tool
        state['response']['stayOptions']['options'][0]['itinerary']['stay'] = stay
        final = nodes.finalize_node(state)
        self.assertEqual((final['http_status'], final['validation_issues']), (500, ['option_grounding']))


class ApplyOptionTests(unittest.TestCase):
    def test_tapping_an_option_swaps_the_plan_without_any_other_node(self):
        previous, composed = first_turn()
        state = next_turn(previous, composed, pick={'index': 1})
        self.assertEqual(state['query'], 'lấy phương án 1')
        self.assertEqual(routing.route_after_intake(state), 'apply_option')
        update = nodes.apply_option_node(state)
        response = update['response']
        self.assertTrue(valid('ItineraryResponse', response))
        self.assertEqual(hotel(response['itinerary']), 'h-far')
        # Đúng lịch đã báo ở lượt trước: cùng khách sạn, cùng tổng tiền.
        self.assertEqual({**response['itinerary'], 'title': None},
                         {**composed['stay_options'][0]['itinerary'], 'title': None})
        self.assertEqual(response['itinerary']['title'], 'Lịch trình đã đổi khách sạn')
        # Bấm thẻ: không có tin nhắn mới, client giữ lời diễn giải cũ (chốt 2026-10-08).
        self.assertNotIn('message', response)
        # Lịch vừa bỏ thành phương án để quay lại; chênh đổi dấu.
        [back] = response['stayOptions']['options']
        old = composed['response']['stayOptions']['options'][0]
        self.assertEqual((back['index'], hotel(back['itinerary'])), (1, 'h-close'))
        self.assertEqual((back['moneyDelta'], back['kmDelta']), (5_000_000, -old['kmDelta']))
        self.assertEqual(update['constraints']['specific_hotel'], 'Catalog h-far')
        history = [{'role': 'user', 'content': 'đi Phú Quốc'}, {'role': 'assistant', 'content': 'Lịch ...'}]
        final = nodes.finalize_node({**state, **update, 'conversation_history': history})
        self.assertEqual((final['http_status'], final['validation_issues']), (200, []))
        self.assertEqual(final['conversation_history'], history)   # không thêm lượt hội thoại

    def test_going_back_restores_the_first_plan_and_its_numbers(self):
        previous, composed = first_turn()
        swapped = nodes.apply_option_node(next_turn(previous, composed, pick={'index': 1}))
        again = next_turn(previous, {'stay_options': swapped['stay_options'], 'current_plan': swapped['current_plan']},
                          pick={'index': 1})
        back = nodes.apply_option_node(again)['response']
        self.assertEqual(hotel(back['itinerary']), 'h-close')
        self.assertEqual(back['itinerary']['estimatedTotal'], composed['response']['itinerary']['estimatedTotal'])
        untitled = lambda payload: [{**o, 'itinerary': {**o['itinerary'], 'title': None}} for o in payload['options']]
        self.assertEqual(untitled(back['stayOptions']), untitled(composed['response']['stayOptions']))
        self.assertEqual(back['stayOptions']['distanceKm'], composed['response']['stayOptions']['distanceKm'])

    def test_typed_pick_takes_the_same_path_and_gets_a_short_reply(self):
        previous, composed = first_turn()
        state = next_turn(previous, composed, query='lấy phương án 1')
        self.assertEqual(routing.route_after_intake(state), 'apply_option')
        update = nodes.apply_option_node(state)
        message = update['response']['message']
        self.assertIn('[Catalog h-far](product:h-far)', message)
        self.assertIn('bớt 5.000.000 ₫', message)
        final = nodes.finalize_node({**state, **update, 'conversation_history': []})
        self.assertEqual(final['http_status'], 200)
        self.assertEqual([turn['role'] for turn in final['conversation_history']], ['user', 'assistant'])

    def test_a_group_needing_several_rooms_can_swap_and_swap_back(self):
        """Trace 09/10/2026 (`e7fb8709…`, 4 người lớn): lịch đã lưu chỉ giữ `summary` của khách sạn, mất
        `attributes.priceAdults`, nên `finalize` tính lại 1 phòng thay vì 2 và chặn mọi lượt chọn phương án."""
        previous = square_trip()
        previous['intent']['party'] = {'type': 'FRIENDS', 'adults': 4, 'children': 0}
        for hotel_id in ('h-close', 'h-far'):
            previous['candidates'][hotel_id]['attributes']['priceAdults'] = 2
        composed = composition.composed(previous)
        self.assertEqual(composed['response']['itinerary']['stay']['rooms'], 2)
        for _ in range(2):   # đổi sang h-far rồi quay lại h-close
            state = next_turn(previous, composed, pick={'index': 1})
            update = nodes.apply_option_node(state)
            final = nodes.finalize_node({**state, **update, 'conversation_history': []})
            self.assertEqual((final['http_status'], final['validation_issues']), (200, []))
            self.assertEqual(update['response']['itinerary']['stay']['rooms'], 2)
            composed = {'stay_options': update['stay_options'], 'current_plan': update['current_plan']}

    def test_unknown_or_unstored_option_goes_through_the_normal_flow(self):
        previous, composed = first_turn()
        self.assertEqual(routing.route_after_intake(next_turn(previous, composed, pick={'index': 3})), 'precheck')
        self.assertEqual(routing.route_after_intake(next_turn(previous, composed, query='lấy phương án 2')),
                         'precheck')
        # Hội thoại lưu trước khi có lịch từng phương án (không có `previous_plan`).
        old = {**composed, 'current_plan': None}
        self.assertEqual(routing.route_after_intake(next_turn(previous, old, pick={'index': 1})), 'precheck')


class RebasedTests(unittest.TestCase):
    @staticmethod
    def entry(km, money, name):
        return {'distanceKm': km, 'moneyDelta': money, 'stays': [{'name': name}],
                'itinerary': {'estimatedTotal': 10_000_000 + money}}

    def test_previous_plan_is_always_kept_and_close_options_are_dropped(self):
        current = self.entry(30.0, 0, 'current')
        chosen = {**self.entry(40.0, -3_000_000, 'chosen'), 'index': 2}
        others = [{**self.entry(41.0, -3_500_000, 'too-close'), 'index': 1},   # chỉ chênh 1 km với lịch mới
                  {**self.entry(25.0, 2_000_000, 'closer'), 'index': 3}]
        options = option_swap.rebased(current, chosen, others, {'budget': 9_000_000})
        self.assertEqual([o['stays'][0]['name'] for o in options], ['current', 'closer'])
        self.assertEqual([o['index'] for o in options], [1, 2])
        self.assertEqual([(o['kmDelta'], o['moneyDelta']) for o in options], [(-10.0, 3_000_000), (-15.0, 5_000_000)])
        # Vượt ngân sách tính lại theo tổng của từng lịch.
        self.assertEqual([o['overBudget'] for o in options], [1_000_000, 3_000_000])


if __name__ == '__main__':
    unittest.main()


class SilentArchiveTests(unittest.IsolatedAsyncioTestCase):
    async def test_a_tapped_option_updates_the_last_answer_instead_of_adding_messages(self):
        class Store:
            value = None
            async def save(self, conversation_id, value, owner='anonymous'):
                self.value = value

        class Archive:
            recorded, updated = [], []
            async def record_turn(self, *args):
                self.recorded.append(args)
            async def update_last_turn(self, *args):
                self.updated.append(args)

        previous, composed = first_turn()
        state = next_turn(previous, composed, pick={'index': 1})
        state = {**state, **nodes.apply_option_node(state), 'request_id': 'r2'}
        store, archive = Store(), Archive()
        await nodes.finalize_node_async(state, store=store, archive=archive, cdp_user_id='VP1')
        self.assertEqual(archive.recorded, [])
        [(conversation_id, user, payload)] = archive.updated
        self.assertEqual((conversation_id, user), ('c1', 'VP1'))
        self.assertEqual(hotel(payload['response']['itinerary']), 'h-far')
        self.assertEqual(hotel(store.value['previous_plan']['itinerary']), 'h-far')


class ArchivedWorkingStateTests(unittest.TestCase):
    """Archive không lưu lặp lịch: các lịch đã có trong `response` cùng dòng bị bỏ khỏi working state, `restored` dựng
    lại đúng như cũ."""

    plan = {"itinerary": {"days": [1]}, "searchResults": {"tour": [{"productId": "t"}]}, "distanceKm": 33.1,
            "warnings": [], "stays": [{"productId": "h1"}]}
    options = [{"index": 1, "itinerary": {"days": [2]}, "warnings": [], "distanceKm": 42.3, "kmDelta": 9.2}]
    response = {"status": "COMPLETED", "itinerary": {"days": [1]}, "searchResults": {"tour": [{"productId": "t"}]},
                "stayOptions": {"distanceKm": 33.1, "options": [{"index": 1, "itinerary": {"days": [2]}}]}}

    def working_state(self):
        return {"intent": {}, "previous_plan": deepcopy(self.plan), "previous_options": deepcopy(self.options)}

    def test_round_trip_drops_the_copies_and_restores_them(self):
        archived = option_swap.archived(self.working_state(), self.response)
        self.assertNotIn("itinerary", archived["previous_plan"])
        self.assertNotIn("searchResults", archived["previous_plan"])
        self.assertNotIn("itinerary", archived["previous_options"][0])
        self.assertEqual(option_swap.restored({**archived, "lastResponse": self.response}), self.working_state())

    def test_keeps_plans_the_response_does_not_carry(self):
        # Lượt hỏi lại sau một lịch: response không có lịch nên working state giữ nguyên để lượt sau vẫn chọn được.
        clarification = {"status": "NEEDS_CLARIFICATION"}
        self.assertEqual(option_swap.archived(self.working_state(), clarification), self.working_state())
