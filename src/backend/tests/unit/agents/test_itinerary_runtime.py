"""Behavioral regression tests, independent of the user's future LLM evaluation set."""
import asyncio
from copy import deepcopy
import json
from types import SimpleNamespace
import unittest

from src.backend.app.agents import nodes, routing
from src.backend.app.agents.graph import build_graph
from src.backend.app.agents.models import ConversationalAnswer, DestinationChoice, Extraction
from src.backend.app.infrastructure.persistence.langgraph_checkpointer import build_checkpointer
from src.backend.app.agents.tools.itinerary_gateway import ItineraryToolGateway
from src.backend.app.application.itinerary.contracts import valid
from src.backend.app.application.ports.itinerary_tools import ToolError
from src.backend.app.domain.itinerary.planning import empty_intent, render_proposal, totals, validate_plan
from src.backend.app.infrastructure.persistence.conversation_store import InMemoryConversationStore


def product(pid='a', **updates):
    return {'productId': pid, 'name': f'Catalog {pid}', 'taxonomy': 'attraction',
            'destination': 'Nha Trang', 'unitPrice': 100000, 'currency': 'VND', 'available': True,
            'description': 'Source text', 'attributes': {}, 'availableFrom': None, 'availableTo': None,
            'priceUnit': 'PER_PERSON', **updates}


def extracted(**patch):
    return Extraction(domain='travel', patch=patch)


class ScriptedLlm:
    """Script model decisions rather than matching scenario IDs or query keywords."""
    def __init__(self, extraction=None, plan=None,
                 conversational_message='Bạn muốn đi đâu và trong bao nhiêu ngày?',
                 destination_choice=None, fail_destination=False, fail_conversation=False, plan_delay=0):
        self.fail_conversation = fail_conversation
        self.destination_choice = destination_choice
        self.fail_destination = fail_destination
        self.extraction = extraction or extracted(destination='Nha Trang', days=2, party={'type': 'SOLO', 'adults': 1, 'children': 0})
        self.plan = plan or [{'name': 'search_products', 'args': {'query': 'tham quan'}}]
        self.conversational_message = conversational_message
        self.plan_delay = plan_delay
        self.calls = []
        self.prompts = {}

    def with_structured_output(self, schema):
        async def invoke(prompt):
            self.calls.append(schema.__name__)
            self.prompts[schema.__name__] = str(prompt)
            if schema is Extraction:
                return self.extraction
            if schema is DestinationChoice:
                if self.fail_destination:
                    raise RuntimeError('provider error')
                return DestinationChoice(destination=self.destination_choice)
            if schema is ConversationalAnswer:
                if self.fail_conversation:
                    raise RuntimeError('provider error')
                return ConversationalAnswer(message=self.conversational_message)
            raise AssertionError(f'the itinerary path must not call the model for {schema.__name__}')
        return SimpleNamespace(ainvoke=invoke)

    def bind_tools(self, definitions):
        async def invoke(prompt):
            self.calls.append('planner')
            if self.plan_delay and self.calls.count('planner') == 1:
                await asyncio.sleep(self.plan_delay)
            return SimpleNamespace(tool_calls=deepcopy(self.plan))
        return SimpleNamespace(ainvoke=invoke)


class Clients:
    def __init__(self, products=None, rec_error=None, rec=None, incomplete=False, destinations=None):
        self.destinations = destinations
        self.products = products if products is not None else [product()]
        self.calls = []
        self.rec_error = rec_error
        self.rec = rec
        self.incomplete = incomplete

    async def search_products(self, args):
        self.calls.append('search')
        values = deepcopy(self.products)
        if self.incomplete:
            for p in values:
                for field in ('description', 'attributes', 'availableFrom', 'availableTo'):
                    p.pop(field, None)
        return {'results': [{**p, 'score': 0.9} for p in values], 'total': len(values)}

    async def get_recommendations(self, args, authorization=None):
        self.calls.append('rec')
        if self.rec_error:
            raise self.rec_error
        return self.rec or {'strategy': 'popular', 'recommendations': []}

    async def get_product_detail(self, pid):
        self.calls.append(f'detail:{pid}')
        return deepcopy(next(p for p in self.products if p['productId'] == pid))

    async def list_destinations(self):
        names = self.destinations or ['Nha Trang']
        return {'destinations': [{'destination': name, 'productCount': len(self.products)} for name in names]}


class RuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def run_graph(self, llm=None, clients=None, state=None, **kwargs):
        llm = llm or ScriptedLlm()
        clients = clients or Clients()
        gateway = ItineraryToolGateway(clients, clients, clients)
        graph = build_graph(tools=gateway, llm=llm, **kwargs)
        result = await graph.ainvoke({'query': 'a user request', 'request_id': 'test', **(state or {})})
        self.assertEqual(result['events'][-1]['node'], 'finalize')
        self.assertTrue(valid('ItineraryResponse' if result['http_status'] == 200 else 'ErrorResponse', result['response']))
        return result

    async def test_completed_is_grounded_and_has_exact_days_and_computed_total(self):
        clients = Clients(incomplete=True)
        result = await self.run_graph(clients=clients)
        plan = result['response']['itinerary']
        self.assertEqual([d['day'] for d in plan['days']], [1, 2])
        self.assertEqual(plan['days'][0]['slots'][0]['product']['name'], 'Catalog a')
        self.assertEqual(plan['estimatedTotal'], 100000)
        self.assertEqual(plan['budgetStatus'], 'NO_BUDGET')
        self.assertEqual(clients.calls, ['search', 'detail:a'])
        self.assertEqual(result['validation_issues'], [])
        # The itinerary is built by `compose`; `converse` only handles chit-chat and never sees products.
        self.assertEqual([event['node'] for event in result['events']],
                         ['intake', 'classify', 'tool', 'evaluate', 'compose', 'finalize'])

    async def test_checked_in_catalog_fixture_runs_through_the_graph(self):
        from src.backend.app.infrastructure.clients.itinerary_fixture_clients import FixtureItineraryClients
        clients = FixtureItineraryClients()
        catalog = {p['productId']: p for p in clients._products}
        result = await self.run_graph(clients=clients)
        plan = result['response']['itinerary']
        self.assertEqual(result['response']['status'], 'COMPLETED')
        returned = ([plan['stay']['product']] if plan.get('stay') else []) + [
            slot['product'] for day in plan['days'] for slot in day['slots'] if slot['product']]
        self.assertTrue(returned)
        for item in returned:
            source = catalog[item['productId']]
            self.assertEqual((item['name'], item['unitPrice'], item['destination']),
                             (source['name'], source['unitPrice'], source['destination']))
        # Cheapest first is the documented rule, so the stay is verifiable against the catalog.
        hotels = [p for p in clients._products
                  if p['destination'] == 'Nha Trang' and p['taxonomy'] == 'hotel' and p['available']]
        self.assertEqual(plan['stay']['product']['productId'],
                         min(hotels, key=lambda p: (p['unitPrice'] is None, p['unitPrice'] or 0))['productId'])

    async def test_abbreviation_is_resolved_by_llm_from_catalog_names_only(self):
        clients = Clients(products=[product('a', destination='TP. Hồ Chí Minh')], destinations=['Nha Trang', 'TP. Hồ Chí Minh'])
        llm = ScriptedLlm(extraction=extracted(destination='tphcm', days=2), destination_choice='TP. Hồ Chí Minh')
        result = await self.run_graph(llm, clients)
        self.assertEqual(result['intent']['destination'], 'TP. Hồ Chí Minh')
        self.assertEqual(result['response']['status'], 'COMPLETED')
        self.assertEqual(llm.calls.count('DestinationChoice'), 1)
        self.assertIn('normalized destination', [e['message'] for e in result['events'] if e['node'] == 'tool'][0])

    async def test_accent_and_case_variants_match_without_calling_the_llm(self):
        llm = ScriptedLlm(extraction=extracted(destination='NHA  trang', days=2))
        result = await self.run_graph(llm)
        self.assertEqual(result['intent']['destination'], 'Nha Trang')
        self.assertEqual(llm.calls.count('DestinationChoice'), 0)

    async def test_destination_without_catalog_match_is_rejected_before_search(self):
        for choice in (None, 'Atlantis'):  # model says none, or names something the catalog does not list
            with self.subTest(choice=choice):
                clients = Clients()
                llm = ScriptedLlm(extraction=extracted(destination='Paris', days=2), destination_choice=choice)
                result = await self.run_graph(llm, clients)
                self.assertEqual(result['http_status'], 422)
                self.assertEqual(result['response']['error']['code'], 'UNSUPPORTED_DESTINATION')
                self.assertEqual(result['response']['error']['details']['supportedDestinations'], ['Nha Trang'])
                self.assertEqual(clients.calls, [])

    async def test_unsupported_destination_keeps_trip_so_a_valid_destination_completes_it(self):
        store = InMemoryConversationStore()
        clients = Clients()
        first = await self.run_graph(
            ScriptedLlm(extraction=extracted(destination='Tokyo', days=4, startDate='2026-09-21'), destination_choice=None),
            clients, store=store)
        self.assertEqual(first['response']['error']['code'], 'UNSUPPORTED_DESTINATION')
        cid = first['response']['error']['details']['conversationId']
        self.assertEqual(cid, first['conversation_id'])
        self.assertEqual(clients.calls, [])
        second = await self.run_graph(ScriptedLlm(extraction=extracted(destination='Nha Trang')), clients,
                                      state={'conversation_id': cid}, store=store)
        self.assertEqual(second['http_status'], 200)
        self.assertEqual(second['response']['status'], 'COMPLETED')
        self.assertEqual((second['intent']['destination'], second['intent']['days'], second['intent']['startDate']),
                         ('Nha Trang', 4, '2026-09-21'))

    async def test_unsupported_destination_is_not_kept_when_the_user_gives_only_days(self):
        store = InMemoryConversationStore()
        first = await self.run_graph(ScriptedLlm(extraction=extracted(destination='Tokyo', days=4), destination_choice=None),
                                     Clients(), store=store)
        second = await self.run_graph(ScriptedLlm(extraction=extracted(days=5)), Clients(), store=store,
                                      state={'conversation_id': first['conversation_id']})
        self.assertEqual(second['response']['status'], 'NEEDS_CLARIFICATION')
        self.assertEqual(second['response']['missingFields'], ['destination'])

    async def test_unsupported_destination_message_names_the_request_and_lists_catalog_destinations(self):
        for language, expected in (('vi', 'chưa có dịch vụ tại Paris'), ('en', 'services in Paris')):
            with self.subTest(language=language):
                llm = ScriptedLlm(extraction=extracted(destination='Paris', days=2), destination_choice=None)
                result = await self.run_graph(llm, Clients(), state={'language': language})
                message = result['response']['error']['message']
                self.assertIn(expected, message)
                self.assertIn('Nha Trang', message)

    async def test_destination_resolution_failure_is_a_controlled_llm_error(self):
        clients = Clients()
        llm = ScriptedLlm(extraction=extracted(destination='tphcm', days=2), fail_destination=True)
        result = await self.run_graph(llm, clients)
        self.assertEqual(result['http_status'], 503)
        self.assertEqual(result['response']['error']['code'], 'LLM_UNAVAILABLE')
        self.assertEqual(clients.calls, [])

    async def test_normalize_drops_guessed_child_count_of_family_party(self):
        party = {'type': 'FAMILY_WITH_KIDS', 'adults': 1, 'children': 0}
        llm = ScriptedLlm(extraction=extracted(destination='Nha Trang', days=2, party=party, interests=[' Biển ', 'biển', '']))
        result = await self.run_graph(llm)
        self.assertIsNone(result['intent']['party'])
        self.assertEqual(result['constraints']['party_type_hint'], 'FAMILY_WITH_KIDS')
        self.assertEqual(result['intent']['interests'], ['Biển'])

    async def test_required_hotel_features_and_unknown_occupancy_total(self):
        clients = Clients(products=[product('h', taxonomy='hotel', priceUnit='PER_NIGHT',
                           attributes={'starRating': 5, 'oceanView': True})])
        llm = ScriptedLlm(extraction=Extraction(domain='travel', patch={'destination': 'Nha Trang', 'days': 2},
                         constraints={'require_hotel': True, 'star_rating_min': 5, 'hotel_attributes': {'oceanView': True}}))
        result = await self.run_graph(llm, clients)
        self.assertEqual(result['response']['status'], 'COMPLETED')
        self.assertEqual(result['response']['itinerary']['stay']['nights'], 1)
        self.assertIsNone(result['response']['itinerary']['estimatedTotal'])

    async def test_cross_sell_excludes_hotel_and_preserves_real_because(self):
        reason = [{'productName': 'Previously viewed product', 'event': 'product_view', 'daysAgo': 2}]
        rec = {'strategy': 'cross_vertical', 'nextVertical': 'attraction', 'destination': 'Nha Trang',
               'recommendations': [{**product(), 'because': reason}],
               'diagnostics': {'eventsUsed': 3, 'coldStart': False, 'excludedVerticals': ['hotel'], 'latencyMs': 1}}
        clients = Clients(products=[product(), product('h', taxonomy='hotel')], rec=rec)
        llm = ScriptedLlm(plan=[{'name': 'search_products', 'args': {'query': 'tour'}}, {'name': 'get_recommendations', 'args': {}}])
        result = await self.run_graph(llm, clients)
        self.assertNotIn('h', result['candidates'])
        slot = result['response']['itinerary']['days'][0]['slots'][0]
        self.assertEqual(slot['source'], 'RECOMMENDATION')
        self.assertEqual(slot['because'], reason)

    async def test_invalid_model_schema_and_tool_allowlist_fail_safely(self):
        llm = ScriptedLlm(plan=[{'name': 'checkout', 'args': {'authorization': 'runtime-secret'}}])
        result = await self.run_graph(llm)
        self.assertEqual(result['http_status'], 503)
        self.assertNotIn('runtime-secret', json.dumps(result))

    async def test_llm_plan_timeout_is_retried_instead_of_treated_as_a_permanent_invalid_plan(self):
        # A slow planner call is a transient provider hiccup, not a structurally invalid plan;
        # it must go through `retry` (a fresh planning attempt) rather than straight to `dead_letter`.
        llm = ScriptedLlm(plan_delay=0.3)
        result = await self.run_graph(llm, llm_timeout_seconds=0.05)
        self.assertEqual(result['response']['status'], 'COMPLETED')
        self.assertEqual(result['attempt'], 1)
        self.assertEqual(llm.calls.count('planner'), 2)

    async def test_missing_destination_prevents_tools_and_preserves_known_fields(self):
        clients = Clients()
        llm = ScriptedLlm(extraction=extracted(days=3, pace='RELAXED'))
        result = await self.run_graph(llm, clients)
        self.assertEqual(result['response']['status'], 'NEEDS_CLARIFICATION')
        self.assertEqual(result['response']['missingFields'], ['destination'])
        self.assertEqual(result['intent']['days'], 3)
        self.assertEqual(clients.calls, [])
        self.assertIn('ConversationalAnswer', llm.calls)

    async def test_greeting_uses_llm_answer_without_calling_product_tools(self):
        clients = Clients()
        llm = ScriptedLlm(
            extraction=Extraction(domain='conversation'),
            conversational_message='Xin chào! Bạn muốn đi đâu và dự định đi trong bao nhiêu ngày?',
        )
        result = await self.run_graph(llm, clients)
        self.assertEqual(result['http_status'], 200)
        self.assertEqual(result['response']['status'], 'NEEDS_CLARIFICATION')
        self.assertEqual(result['response']['question'], llm.conversational_message)
        self.assertEqual(result['response']['missingFields'], ['destination', 'days'])
        self.assertEqual(llm.calls, ['Extraction', 'ConversationalAnswer'])
        self.assertFalse(clients.calls)

    async def test_broad_suggestion_is_asked_by_clarify_without_catalog_claims(self):
        clients = Clients()
        llm = ScriptedLlm(
            extraction=extracted(),
            conversational_message='Mình có thể gợi ý sau khi bạn cho biết điểm đến và số ngày nhé.',
        )
        result = await self.run_graph(llm, clients, state={'query': 'Gợi ý cho tôi một chuyến đi'})
        self.assertEqual([event['node'] for event in result['events']], ['intake', 'classify', 'clarify', 'finalize'])
        self.assertEqual(result['response']['status'], 'NEEDS_CLARIFICATION')
        self.assertEqual(result['response']['question'], llm.conversational_message)
        self.assertEqual(result['response']['missingFields'], ['destination', 'days'])
        self.assertEqual(llm.calls, ['Extraction', 'ConversationalAnswer'])
        self.assertFalse(clients.calls)

    async def test_trip_details_labelled_conversation_still_reach_clarify(self):
        """The model sometimes calls a detail-bearing message chit-chat; routing must not follow it there."""
        clients = Clients()
        llm = ScriptedLlm(
            extraction=Extraction(domain='conversation', patch={'days': 3}),
            conversational_message='Bạn muốn đi thành phố nào?',
        )
        result = await self.run_graph(llm, clients, state={'query': 'đi 3 ngày'})
        self.assertEqual([event['node'] for event in result['events']], ['intake', 'classify', 'clarify', 'finalize'])
        self.assertEqual(result['interaction_type'], 'travel')
        self.assertEqual(result['response']['missingFields'], ['destination'])
        self.assertFalse(clients.calls)

    async def test_missing_trip_details_are_asked_by_clarify_and_chit_chat_is_answered(self):
        llm = ScriptedLlm(extraction=extracted(days=3), conversational_message='Bạn muốn đi thành phố nào?')
        result = await self.run_graph(llm)
        nodes = [event['node'] for event in result['events']]
        self.assertEqual(nodes, ['intake', 'classify', 'clarify', 'finalize'])
        self.assertEqual(result['response']['question'], 'Bạn muốn đi thành phố nào?')
        self.assertEqual(result['final_answer'], 'Bạn muốn đi thành phố nào?')
        greeting = await self.run_graph(ScriptedLlm(extraction=Extraction(domain='conversation')))
        self.assertEqual([event['node'] for event in greeting['events']], ['intake', 'classify', 'converse', 'finalize'])

    async def test_clarify_falls_back_to_the_reason_specific_fixed_question_when_the_model_fails(self):
        clients = Clients()
        conflict = Extraction(domain='travel', patch={'destination': 'Nha Trang', 'startDate': '2026-10-10', 'days': 2}, end_date='2026-10-12')
        result = await self.run_graph(ScriptedLlm(extraction=conflict, fail_conversation=True), clients)
        self.assertEqual(result['response']['status'], 'NEEDS_CLARIFICATION')
        self.assertIn('mâu thuẫn', result['response']['question'])
        missing = await self.run_graph(ScriptedLlm(extraction=extracted(days=3), fail_conversation=True), clients)
        self.assertEqual(missing['response']['question'], 'Bạn muốn đi du lịch ở tỉnh hoặc thành phố nào?')
        self.assertFalse(clients.calls)

    async def test_unmet_required_condition_is_asked_by_clarify_without_calling_the_model(self):
        clients = Clients(products=[product(taxonomy='hotel', unitPrice=1100000, priceUnit='UNKNOWN')])
        llm = ScriptedLlm(extraction=Extraction(domain='travel', patch={'destination': 'Nha Trang', 'days': 2},
                constraints={'require_hotel': True, 'hotel_price_max': 1200000, 'price_strict': True, 'hotel_price_unit': 'PER_NIGHT'}))
        result = await self.run_graph(llm, clients)
        self.assertEqual([event['node'] for event in result['events']][-3:], ['evaluate', 'clarify', 'finalize'])
        self.assertEqual(result['response']['status'], 'NEEDS_CLARIFICATION')
        self.assertNotIn('ConversationalAnswer', llm.calls)

    async def test_dates_derive_duration_and_conflicts_do_not_search(self):
        llm = ScriptedLlm(extraction=Extraction(domain='travel', patch={'destination': 'Nha Trang', 'startDate': '2026-10-10'}, end_date='2026-10-12'))
        result = await self.run_graph(llm)
        self.assertEqual(result['intent']['days'], 3)
        self.assertEqual(result['response']['itinerary']['days'][-1]['date'], '2026-10-12')
        clients = Clients()
        llm.extraction = Extraction(domain='travel', patch={'destination': 'Nha Trang', 'startDate': '2026-10-10', 'days': 2}, end_date='2026-10-12')
        result = await self.run_graph(llm, clients)
        self.assertEqual(result['response']['status'], 'NEEDS_CLARIFICATION')
        self.assertFalse(clients.calls)

    async def test_duration_outside_contract_is_error(self):
        result = await self.run_graph(ScriptedLlm(extraction=extracted(destination='Nha Trang', days=8)))
        self.assertEqual(result['http_status'], 400)
        self.assertEqual(result['response']['error']['code'], 'INVALID_TRIP_DURATION')

    async def test_unsupported_destination_requires_catalog_evidence(self):
        clients = Clients(products=[])
        result = await self.run_graph(ScriptedLlm(extraction=extracted(destination='Tokyo', days=3)), clients)
        self.assertEqual(result['http_status'], 422)
        self.assertEqual(result['response']['error']['code'], 'UNSUPPORTED_DESTINATION')
        self.assertEqual(result['response']['error']['details']['supportedDestinations'], ['Nha Trang'])
        self.assertFalse(clients.calls)

    async def test_empty_search_is_not_a_provider_failure_or_an_unsupported_country_claim(self):
        result = await self.run_graph(clients=Clients(products=[]))
        self.assertEqual(result['response']['status'], 'NO_RESULTS')
        self.assertNotIn('trong nước', result['response']['message'])

    async def test_an_unschedulable_taxonomy_is_retrieved_but_never_scheduled(self):
        # Regression: "đi Nha Trang 2 ngày từ ngày mai" returned FALLBACK because the model put the
        # one combo of the catalog into a slot, and that single slot discarded the whole itinerary.
        clients = Clients(products=[product('a'), product('c', taxonomy='combo')])
        result = await self.run_graph(clients=clients)
        response = result['response']
        self.assertEqual(response['status'], 'COMPLETED')
        scheduled = [slot['product']['productId'] for day in response['itinerary']['days']
                     for slot in day['slots'] if slot['product']]
        self.assertEqual(scheduled, ['a'])
        # The combo is still retrieved and may be shown; it simply never reaches a slot.
        self.assertIn('c', result['candidates'])

    async def test_the_itinerary_path_never_asks_the_model_to_pick_products(self):
        llm = ScriptedLlm()
        result = await self.run_graph(llm)
        self.assertEqual(result['response']['status'], 'COMPLETED')
        # Intent extraction and the tool planner remain; nothing else may consult the model.
        self.assertEqual(llm.calls, ['Extraction', 'planner'])

    async def test_only_retrieved_products_can_reach_a_slot(self):
        clients = Clients(products=[product('a'), product('b'), product('c')])
        result = await self.run_graph(clients=clients)
        plan = result['response']['itinerary']
        scheduled = [slot['product']['productId'] for day in plan['days']
                     for slot in day['slots'] if slot['product']]
        self.assertTrue(set(scheduled) <= set(result['candidates']))
        self.assertEqual(len(scheduled), len(set(scheduled)))

    async def test_nothing_schedulable_falls_back_to_the_real_products(self):
        clients = Clients(products=[product('c', taxonomy='combo')])
        result = await self.run_graph(clients=clients)
        self.assertEqual(result['response']['status'], 'FALLBACK')
        self.assertEqual(result['response']['searchResults']['combo'][0]['productId'], 'c')

    async def test_hotel_price_boundary_unit_and_required_stay_are_enforced(self):
        for price, unit in ((1200000, 'PER_NIGHT'), (1100000, 'UNKNOWN')):
            clients = Clients(products=[product(taxonomy='hotel', unitPrice=price, priceUnit=unit)])
            llm = ScriptedLlm(extraction=Extraction(domain='travel', patch={'destination': 'Nha Trang', 'days': 2},
                    constraints={'require_hotel': True, 'hotel_price_max': 1200000, 'price_strict': True, 'hotel_price_unit': 'PER_NIGHT'}))
            result = await self.run_graph(llm, clients)
            self.assertEqual(result['response']['status'], 'NEEDS_CLARIFICATION')

    async def test_partial_success_retries_failed_rec_once_then_falls_back(self):
        clients = Clients(rec_error=ToolError('TOOL_TIMEOUT', retryable=True))
        llm = ScriptedLlm(plan=[{'name': 'search_products', 'args': {'query': 'tour'}}, {'name': 'get_recommendations', 'args': {}}])
        result = await self.run_graph(llm, clients)
        self.assertEqual(clients.calls, ['search', 'rec', 'rec'])
        self.assertEqual(result['response']['status'], 'FALLBACK')
        self.assertEqual(result['attempt'], 1)
        self.assertEqual(llm.calls.count('planner'), 1)

    async def test_independent_tool_calls_do_not_wait_for_each_other(self):
        ready = asyncio.Event()
        started = set()
        class CoordinatedClients(Clients):
            async def coordinate(self, name):
                started.add(name)
                if len(started) == 2:
                    ready.set()
                await asyncio.wait_for(ready.wait(), 0.2)
            async def search_products(self, args):
                await self.coordinate('search')
                return await super().search_products(args)
            async def get_recommendations(self, args, authorization=None):
                await self.coordinate('rec')
                return await super().get_recommendations(args, authorization)
        llm = ScriptedLlm(plan=[{'name': 'search_products', 'args': {'query': 'tour'}}, {'name': 'get_recommendations', 'args': {}}])
        result = await self.run_graph(llm, CoordinatedClients())
        self.assertEqual(result['attempt'], 0)
        self.assertEqual(result['response']['status'], 'COMPLETED')

    async def test_catalog_hydration_is_concurrent_and_bounded(self):
        class CountingClients(Clients):
            active = 0
            maximum = 0
            async def get_product_detail(self, pid):
                self.active += 1
                self.maximum = max(self.maximum, self.active)
                await asyncio.sleep(0.01)
                try:
                    return await super().get_product_detail(pid)
                finally:
                    self.active -= 1
        clients = CountingClients(products=[product(f'p{i}') for i in range(10)], incomplete=True)
        result = await self.run_graph(clients=clients)
        self.assertEqual(result['response']['status'], 'COMPLETED')
        self.assertEqual(clients.maximum, 5)
        self.assertEqual(len(result['details']), 10)

    async def test_all_transient_failures_terminate_without_fake_results(self):
        clients = Clients(rec_error=ToolError('TOOL_TIMEOUT', retryable=True))
        llm = ScriptedLlm(plan=[{'name': 'get_recommendations', 'args': {}}])
        result = await self.run_graph(llm, clients)
        self.assertEqual(clients.calls, ['rec', 'rec'])
        self.assertEqual(result['http_status'], 503)
        self.assertEqual(result['response']['error']['code'], 'SEARCH_UNAVAILABLE')

    async def test_auth_error_never_becomes_anonymous_fallback(self):
        clients = Clients(rec_error=ToolError('TOKEN_EXPIRED', http_status=401))
        result = await self.run_graph(clients=clients, require_recommendations=True)
        self.assertEqual(result['http_status'], 401)
        self.assertEqual(result['response']['error']['code'], 'TOKEN_EXPIRED')
        self.assertEqual(clients.calls.count('rec'), 1)

    async def test_refusal_never_calls_product_tools(self):
        clients = Clients()
        result = await self.run_graph(ScriptedLlm(extraction=Extraction(domain='out_of_domain')), clients)
        self.assertEqual(result['http_status'], 400)
        self.assertFalse(clients.calls)

    async def test_conversation_merges_override_reloads_prices_and_enforces_owner_and_ttl(self):
        clock = [0]
        store = InMemoryConversationStore(ttl_seconds=10, clock=lambda: clock[0])
        clients = Clients()
        first = await self.run_graph(ScriptedLlm(extraction=extracted(days=3, pace='RELAXED')), clients, store=store, owner='one')
        cid = first['conversation_id']
        second = await self.run_graph(ScriptedLlm(extraction=extracted(destination='Nha Trang')), clients,
                                      state={'conversation_id': cid}, store=store, owner='one')
        self.assertEqual(second['intent']['days'], 3)
        self.assertEqual(second['intent']['pace'], 'RELAXED')
        self.assertEqual(second['response']['status'], 'COMPLETED')
        clients.products[0]['unitPrice'] = 200000
        third = await self.run_graph(ScriptedLlm(extraction=extracted()), clients,
                    state={'conversation_id': cid, 'intent_override': {'days': 2, 'budget': None}}, store=store, owner='one')
        self.assertEqual(third['response']['itinerary']['days'][0]['slots'][0]['product']['unitPrice'], 200000)
        self.assertEqual(third['intent']['days'], 2)
        denied = await self.run_graph(state={'conversation_id': cid}, store=store, owner='two')
        self.assertEqual(denied['http_status'], 404)
        clock[0] = 11
        expired = await self.run_graph(state={'conversation_id': cid}, store=store, owner='one')
        self.assertEqual(expired['http_status'], 404)
        self.assertNotIn('unitPrice', json.dumps(store._items))

    async def test_swap_without_naming_excludes_previously_shown_product(self):
        store = InMemoryConversationStore()
        clients = Clients(products=[product('vinpearl', name='Vinpearl', unitPrice=100000),
                                     product('other', name='Doi Che', unitPrice=200000)])
        first = await self.run_graph(ScriptedLlm(extraction=extracted(destination='Nha Trang', days=1)),
                                     clients, store=store, owner='one')
        self.assertEqual(first['response']['itinerary']['days'][0]['slots'][0]['product']['productId'], 'vinpearl')
        cid = first['conversation_id']
        # User asks to swap out the shown activity without naming a replacement.
        second = await self.run_graph(ScriptedLlm(extraction=Extraction(domain='travel',
                    constraints={'exclude_products': ['vinpearl']})),
                    clients, state={'conversation_id': cid}, store=store, owner='one')
        chosen = [slot['product']['productId'] for day in second['response']['itinerary']['days']
                 for slot in day['slots'] if slot['product']]
        self.assertNotIn('vinpearl', chosen)
        self.assertIn('other', chosen)

    async def test_memory_checkpoint_resumes_after_classification(self):
        clients, llm = Clients(), ScriptedLlm()
        gateway = ItineraryToolGateway(clients, clients, clients)
        checkpointer = build_checkpointer()
        interrupted = build_graph(tools=gateway, llm=llm, checkpointer=checkpointer)
        # A fresh compiled graph can resume a saved thread without redoing classification.
        config = {'configurable': {'thread_id': 'resume-test'}}
        await interrupted.ainvoke({'query': 'travel', 'request_id': 'resume'}, config, interrupt_after=['classify'])
        self.assertFalse(clients.calls)
        self.assertEqual((await interrupted.aget_state(config)).next, ('tool',))
        resumed = build_graph(tools=gateway, llm=llm, checkpointer=checkpointer)
        result = await resumed.ainvoke(None, config)
        self.assertEqual(result['response']['status'], 'COMPLETED')
        self.assertEqual(llm.calls.count('Extraction'), 1)

    async def test_direct_finalize_catches_tampered_price_and_note(self):
        result = await self.run_graph()
        for field, value in (('unitPrice', 1), ('name', 'Invented hotel')):
            bad = deepcopy(result)
            bad['response']['itinerary']['days'][0]['slots'][0]['product'][field] = value
            checked = nodes.finalize_node(bad)
            self.assertEqual(checked['http_status'], 500)
            self.assertIn('grounding', checked['validation_issues'])
        bad = deepcopy(result)
        bad['response']['itinerary']['days'][0]['slots'][0]['note'] = 'Book imaginary VIP room now'
        self.assertEqual(nodes.finalize_node(bad)['http_status'], 500)
        bad['response'] = {'status': 'COMPLETED'}
        self.assertEqual(nodes.finalize_node(bad)['http_status'], 500)

    async def test_total_budget_is_not_certified_from_a_product_subtotal(self):
        result = await self.run_graph(ScriptedLlm(extraction=extracted(destination='Nha Trang', days=2,
                        budget=1000000, party={'type': 'SOLO', 'adults': 1, 'children': 0})))
        self.assertIsNone(result['response']['itinerary']['estimatedTotal'])
        self.assertEqual(result['response']['itinerary']['budgetStatus'], 'UNKNOWN')

    async def test_a_full_day_visit_gets_a_day_to_itself(self):
        clients = Clients(products=[product('a', attributes={'openingHours': '09:00–18:00', 'durationMinutes': 480}), product('b')])
        result = await self.run_graph(clients=clients)
        response = result['response']
        # The full-day visit takes day one alone and the other visit moves to day two.
        self.assertEqual(response['status'], 'COMPLETED')
        scheduled = [(day['day'], slot['time'], slot['product']['productId'])
                     for day in response['itinerary']['days'] for slot in day['slots'] if slot['product']]
        self.assertEqual(scheduled, [(1, 'MORNING', 'a'), (2, 'MORNING', 'b')])


if __name__ == '__main__':
    unittest.main()
