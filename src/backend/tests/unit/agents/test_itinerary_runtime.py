"""Behavioral regression tests, independent of the user's future LLM evaluation set."""
import asyncio
from copy import deepcopy
import json
from types import SimpleNamespace
import unittest

from src.backend.app.agents import nodes, routing
from src.backend.app.agents.graph import build_graph
from src.backend.app.agents.models import Composition, ConversationalAnswer, Extraction
from src.backend.app.agents.persistence import build_checkpointer
from src.backend.app.agents.tools.itinerary_gateway import ItineraryToolGateway
from src.backend.app.application.itinerary.contracts import valid
from src.backend.app.application.ports.itinerary_tools import ToolError
from src.backend.app.domain.itinerary.planning import empty_intent, render_proposal, totals, validate_plan
from src.backend.app.infrastructure.clients.itinerary_conversation_store import InMemoryConversationStore


def product(pid='a', **updates):
    return {'productId': pid, 'name': f'Catalog {pid}', 'taxonomy': 'attraction',
            'destination': 'Nha Trang', 'unitPrice': 100000, 'currency': 'VND', 'available': True,
            'description': 'Source text', 'attributes': {}, 'availableFrom': None, 'availableTo': None,
            'priceUnit': 'PER_PERSON', **updates}


def extracted(**patch):
    return Extraction(domain='travel', patch=patch)


class ScriptedLlm:
    """Script model decisions rather than matching scenario IDs or query keywords."""
    def __init__(self, extraction=None, composition=None, plan=None, fail_composition=False,
                 conversational_message='Bạn muốn đi đâu và trong bao nhiêu ngày?'):
        self.extraction = extraction or extracted(destination='Nha Trang', days=2, party={'type': 'SOLO', 'adults': 1, 'children': 0})
        self.composition = composition or Composition(slots=[{'day': 1, 'time': 'MORNING', 'product_id': 'a'}])
        self.plan = plan or [{'name': 'search_products', 'args': {'query': 'tham quan'}}]
        self.fail_composition = fail_composition
        self.conversational_message = conversational_message
        self.calls = []

    def with_structured_output(self, schema):
        async def invoke(prompt):
            self.calls.append(schema.__name__)
            if schema is Extraction:
                return self.extraction
            if schema is ConversationalAnswer:
                return ConversationalAnswer(message=self.conversational_message)
            if self.fail_composition:
                raise RuntimeError('provider error containing a secret')
            return self.composition
        return SimpleNamespace(ainvoke=invoke)

    def bind_tools(self, definitions):
        async def invoke(prompt):
            self.calls.append('planner')
            return SimpleNamespace(tool_calls=deepcopy(self.plan))
        return SimpleNamespace(ainvoke=invoke)


class Clients:
    def __init__(self, products=None, rec_error=None, rec=None, incomplete=False):
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
        return {'destinations': [{'destination': 'Nha Trang', 'productCount': len(self.products)}]}


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

    async def test_checked_in_catalog_fixture_runs_through_the_graph(self):
        from src.backend.app.infrastructure.clients.itinerary_fixture_clients import FixtureItineraryClients
        clients = FixtureItineraryClients()
        source = next(p for p in clients._products if p['destination'] == 'Nha Trang' and p['taxonomy'] == 'attraction' and p['available'])
        llm = ScriptedLlm(composition=Composition(slots=[{'day': 1, 'time': 'MORNING', 'product_id': source['productId']}]))
        result = await self.run_graph(llm, clients)
        self.assertEqual(result['response']['status'], 'COMPLETED')
        returned = result['response']['itinerary']['days'][0]['slots'][0]['product']
        self.assertEqual(returned['name'], source['name'])
        self.assertEqual(returned['unitPrice'], source['unitPrice'])

    async def test_required_hotel_features_and_unknown_occupancy_total(self):
        clients = Clients(products=[product('h', taxonomy='hotel', priceUnit='PER_NIGHT',
                           attributes={'starRating': 5, 'oceanView': True})])
        llm = ScriptedLlm(extraction=Extraction(domain='travel', patch={'destination': 'Nha Trang', 'days': 2},
                         constraints={'require_hotel': True, 'star_rating_min': 5, 'hotel_attributes': {'oceanView': True}}),
                         composition=Composition(stay_id='h'))
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

    async def test_broad_suggestion_uses_llm_answer_without_catalog_claims(self):
        clients = Clients()
        llm = ScriptedLlm(
            extraction=Extraction(domain='conversation'),
            conversational_message='Mình có thể gợi ý sau khi bạn cho biết điểm đến và số ngày nhé.',
        )
        result = await self.run_graph(llm, clients, state={'query': 'Gợi ý cho tôi một chuyến đi'})
        self.assertEqual(result['response']['status'], 'NEEDS_CLARIFICATION')
        self.assertEqual(result['response']['question'], llm.conversational_message)
        self.assertEqual(result['interaction_type'], 'conversation')
        self.assertEqual(llm.calls, ['Extraction', 'ConversationalAnswer'])
        self.assertFalse(clients.calls)

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

    async def test_unknown_or_duplicate_ids_never_complete(self):
        for slots in ([{'day': 1, 'time': 'MORNING', 'product_id': 'fake'}],
                      [{'day': 1, 'time': 'MORNING', 'product_id': 'a'}, {'day': 2, 'time': 'AFTERNOON', 'product_id': 'a'}]):
            with self.subTest(slots=slots):
                result = await self.run_graph(ScriptedLlm(composition=Composition(slots=slots)))
                self.assertEqual(result['response']['status'], 'FALLBACK')

    async def test_model_failure_falls_back_only_to_actual_candidates(self):
        result = await self.run_graph(ScriptedLlm(fail_composition=True))
        self.assertEqual(result['response']['status'], 'FALLBACK')
        self.assertEqual(result['response']['searchResults']['attraction'][0]['productId'], 'a')
        self.assertNotIn('secret', json.dumps(result))

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
        llm = ScriptedLlm(composition=Composition(slots=[{'day': 1, 'time': 'MORNING', 'product_id': 'p0'}]))
        result = await self.run_graph(llm, clients)
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

    async def test_full_day_activity_cannot_overlap_another_visit(self):
        clients = Clients(products=[product('a', attributes={'openingHours': '09:00–18:00', 'durationMinutes': 480}), product('b')])
        llm = ScriptedLlm(composition=Composition(slots=[{'day': 1, 'time': 'MORNING', 'product_id': 'a'},
                                                      {'day': 1, 'time': 'AFTERNOON', 'product_id': 'b'}]))
        result = await self.run_graph(llm, clients)
        self.assertEqual(result['response']['status'], 'FALLBACK')


if __name__ == '__main__':
    unittest.main()
