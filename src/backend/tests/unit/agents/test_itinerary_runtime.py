"""Behavioral regression tests, independent of the user's future LLM evaluation set."""
import asyncio
from copy import deepcopy
import json

import yaml
from types import SimpleNamespace
import unittest

from src.backend.app.agents import nodes, routing
from src.backend.app.agents.graph import build_graph
from src.backend.app.agents.models import ConversationalAnswer, DestinationChoice, Extraction, ItineraryNarration, TurnRoute
from src.backend.app.agents.steps.prompts import SIMILAR_HINT, TOOL_PLAN_PROMPT
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
    return Extraction(start_date_undecided=True, patch=patch)


class ScriptedLlm:
    """Script model decisions rather than matching scenario IDs or query keywords."""
    def __init__(self, extraction=None, plan=None, route='travel',
                 conversational_message='Bạn muốn đi đâu và trong bao nhiêu ngày?',
                 destination_choice=None, fail_destination=False, fail_conversation=False, plan_delay=0,
                 conversational_title=None, narration=None):
        self.fail_conversation = fail_conversation
        self.narration = narration or ItineraryNarration(title='Chuyến đi Nha Trang', message='Lịch trình gợi ý.')
        self.conversational_title = conversational_title
        self.route = route
        self.destination_choice = destination_choice
        self.fail_destination = fail_destination
        self.extraction = extraction or extracted(destination='Nha Trang', days=2, party={'type': 'SOLO', 'adults': 1, 'children': 0})
        self.plan = plan or [{'name': 'search_products', 'args': {'query': 'tham quan'}}]
        self.conversational_message = conversational_message
        self.plan_delay = plan_delay
        self.calls = []
        self.prompts = {}
        self.bound_tools = []  # tên tool đưa cho planner ở mỗi lần bind_tools
        self.tool_choices = []  # tool_choice của mỗi lần bind_tools
        self.planner_messages = []  # (system, human) của mỗi lần lập plan

    def with_structured_output(self, schema):
        async def invoke(prompt):
            self.calls.append(schema.__name__)
            self.prompts[schema.__name__] = str(prompt)
            if schema is TurnRoute:
                return TurnRoute(route=self.route)
            if schema is Extraction:
                return self.extraction
            if schema is DestinationChoice:
                if self.fail_destination:
                    raise RuntimeError('provider error')
                return DestinationChoice(destination=self.destination_choice)
            if schema is ConversationalAnswer:
                if self.fail_conversation:
                    raise RuntimeError('provider error')
                return ConversationalAnswer(title=self.conversational_title, message=self.conversational_message)
            if schema is ItineraryNarration:
                return self.narration
            raise AssertionError(f'the itinerary path must not call the model for {schema.__name__}')
        return SimpleNamespace(ainvoke=invoke)

    def bind_tools(self, definitions, tool_choice=None):
        self.bound_tools.append([d['name'] for d in definitions])
        self.tool_choices.append(tool_choice)

        async def invoke(prompt):
            self.calls.append('planner')
            self.planner_messages.append(prompt)
            if self.plan_delay and self.calls.count('planner') == 1:
                await asyncio.sleep(self.plan_delay)
            return SimpleNamespace(tool_calls=deepcopy(self.plan))
        return SimpleNamespace(ainvoke=invoke)


class Clients:
    def __init__(self, products=None, rec_error=None, rec=None, incomplete=False, destinations=None,
                 search_error=None):
        self.destinations = destinations
        self.products = products if products is not None else [product()]
        self.calls = []
        self.rec_error = rec_error
        self.rec = rec
        self.incomplete = incomplete
        self.search_error = search_error

    async def search_products(self, args):
        self.calls.append('search')
        if self.search_error:
            raise self.search_error
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
        # Như composition root: chỉ nối port Similar khi adapter khai báo supports_similar.
        gateway = ItineraryToolGateway(clients, clients, clients,
                                       similar=clients if getattr(clients, 'supports_similar', False) else None)
        graph = build_graph(tools=gateway, llm=llm, **kwargs)
        # Mặc định coi như đã hỏi ngày đi/số người/ngân sách, để test tập trung vào luồng đang kiểm.
        inputs = {'query': 'a user request', 'request_id': 'test', 'start_date_asked': True, **(state or {})}
        result = await graph.ainvoke(inputs)
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
                         ['intake', 'classify', 'extract', 'tool', 'evaluate', 'compose', 'narrate', 'finalize'])
        # `narrate` adds the chat text; it survives `finalize` and links only scheduled products.
        self.assertTrue(result['response']['message'].startswith('**Chuyến đi Nha Trang**\n'))
        self.assertIn('[Catalog a](product:a)', result['response']['message'])
        self.assertEqual(result['final_answer'], result['response']['message'])

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
        self.assertIn('normalized destination', [e['message'] for e in result['events'] if e['node'] == 'extract'])

    async def test_accent_and_case_variants_match_without_calling_the_llm(self):
        llm = ScriptedLlm(extraction=extracted(destination='NHA  trang', days=2))
        result = await self.run_graph(llm)
        self.assertEqual(result['intent']['destination'], 'Nha Trang')
        self.assertEqual(llm.calls.count('DestinationChoice'), 0)

    async def test_destination_without_catalog_match_is_asked_again_before_search(self):
        for choice in (None, 'Atlantis'):  # model says none, or names something the catalog does not list
            with self.subTest(choice=choice):
                clients = Clients()
                llm = ScriptedLlm(extraction=extracted(destination='Paris', days=2), destination_choice=choice,
                                  conversational_title='Điểm đến chưa được hỗ trợ',
                                  conversational_message='Mình chưa có dịch vụ ở Paris, bạn chọn điểm đến khác nhé.')
                result = await self.run_graph(llm, clients)
                self.assertEqual(result['http_status'], 200)
                response = result['response']
                self.assertEqual(response['status'], 'NEEDS_CLARIFICATION')
                self.assertEqual(response['question'], '**Điểm đến chưa được hỗ trợ**\nMình chưa có dịch vụ ở Paris, bạn chọn điểm đến khác nhé.')
                self.assertEqual(response['missingFields'], ['destination'])
                self.assertEqual(response['suggestedValues']['destination'], ['Nha Trang'])
                self.assertIsNone(response['knownIntent']['destination'])
                self.assertEqual(response['knownIntent']['days'], 2)
                self.assertEqual(clients.calls, [])
                payload = llm.prompts['ConversationalAnswer']
                self.assertIn('unsupported_destination', payload)
                self.assertIn('Paris', payload)

    async def test_destination_outside_the_catalog_is_rejected_even_when_days_are_still_missing(self):
        clients = Clients()
        llm = ScriptedLlm(extraction=extracted(destination='Trung Quốc'), destination_choice=None,
                          conversational_title='Điểm đến chưa được hỗ trợ',
                          conversational_message='Mình chỉ lên kế hoạch trong Việt Nam.')
        result = await self.run_graph(llm, clients)
        response = result['response']
        self.assertEqual(response['status'], 'NEEDS_CLARIFICATION')
        self.assertEqual(response['missingFields'], ['destination', 'days'])
        self.assertIsNone(response['knownIntent'].get('destination'))
        self.assertEqual(response['suggestedValues']['destination'], ['Nha Trang'])
        self.assertIn('unsupported_destination', llm.prompts['ConversationalAnswer'])
        self.assertIn('Trung Quốc', llm.prompts['ConversationalAnswer'])
        self.assertEqual(clients.calls, [])

    async def test_unsupported_destination_keeps_trip_so_a_valid_destination_completes_it(self):
        store = InMemoryConversationStore()
        clients = Clients()
        first = await self.run_graph(
            ScriptedLlm(extraction=extracted(destination='Tokyo', days=4, startDate='2999-09-21'), destination_choice=None),
            clients, store=store)
        self.assertEqual(first['response']['status'], 'NEEDS_CLARIFICATION')
        cid = first['response']['conversationId']
        self.assertEqual(cid, first['conversation_id'])
        self.assertEqual(clients.calls, [])
        second = await self.run_graph(ScriptedLlm(extraction=extracted(destination='Nha Trang')), clients,
                                      state={'conversation_id': cid}, store=store)
        self.assertEqual(second['http_status'], 200)
        self.assertEqual(second['response']['status'], 'COMPLETED')
        self.assertEqual((second['intent']['destination'], second['intent']['days'], second['intent']['startDate']),
                         ('Nha Trang', 4, '2999-09-21'))

    async def test_unsupported_destination_is_not_kept_when_the_user_gives_only_days(self):
        store = InMemoryConversationStore()
        first = await self.run_graph(ScriptedLlm(extraction=extracted(destination='Tokyo', days=4), destination_choice=None),
                                     Clients(), store=store)
        second = await self.run_graph(ScriptedLlm(extraction=extracted(days=5)), Clients(), store=store,
                                      state={'conversation_id': first['conversation_id']})
        self.assertEqual(second['response']['status'], 'NEEDS_CLARIFICATION')
        self.assertEqual(second['response']['missingFields'], ['destination'])

    async def test_unsupported_destination_fixed_question_names_the_request_and_lists_catalog_destinations(self):
        for language, expected in (('vi', 'chưa có dịch vụ tại Paris'), ('en', 'Paris is not among')):
            with self.subTest(language=language):
                llm = ScriptedLlm(extraction=extracted(destination='Paris', days=2), destination_choice=None,
                                  fail_conversation=True)
                result = await self.run_graph(llm, Clients(), state={'language': language})
                question = result['response']['question']
                self.assertTrue(question.startswith('**'))
                self.assertIn(expected, question)
                self.assertIn('Nha Trang', question)

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
        llm = ScriptedLlm(extraction=Extraction(start_date_undecided=True, patch={'destination': 'Nha Trang', 'days': 2},
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

    async def test_missing_trip_details_are_asked_once_in_one_question_then_the_trip_is_planned(self):
        store = InMemoryConversationStore()
        clients = Clients()
        llm = ScriptedLlm(extraction=Extraction(patch={'destination': 'Nha Trang', 'days': 2}), fail_conversation=True)
        first = await self.run_graph(llm, clients, state={'start_date_asked': False}, store=store, owner='one')
        self.assertEqual(first['response']['status'], 'NEEDS_CLARIFICATION')
        self.assertEqual(first['response']['missingFields'], ['startDate', 'party', 'budget'])
        # Câu cố định (LLM lỗi) vẫn hỏi gộp cả ba trong một câu.
        question = first['response']['question']
        for phrase in ('ngày khởi hành', 'số người lớn và trẻ em', 'ngân sách tổng'):
            self.assertIn(phrase, question)
        self.assertEqual(clients.calls, [])
        self.assertEqual([e['node'] for e in first['events']], ['intake', 'classify', 'extract', 'clarify', 'finalize'])

        # Người dùng trả lời không nêu gì: hội thoại nhớ đã hỏi nên không hỏi lại mà lập lịch luôn.
        second = await self.run_graph(ScriptedLlm(extraction=Extraction()), clients,
                                      state={'conversation_id': first['conversation_id']}, store=store, owner='one')
        self.assertEqual(second['response']['status'], 'COMPLETED')
        self.assertIsNone(second['intent']['startDate'])
        self.assertEqual(clients.calls[0], 'search')

    async def test_trip_details_given_in_the_first_message_are_not_asked(self):
        llm = ScriptedLlm(extraction=Extraction(
                          patch={'destination': 'Nha Trang', 'days': 2, 'startDate': '2999-10-10', 'budget': 5_000_000,
                                 'party': {'type': 'COUPLE', 'adults': 2, 'children': 0}}))
        result = await self.run_graph(llm, state={'start_date_asked': False})
        self.assertEqual(result['response']['status'], 'COMPLETED')
        self.assertEqual(result['intent']['startDate'], '2999-10-10')

    async def test_cross_sell_exclusion_is_not_saved_for_the_next_turn(self):
        # excludedVerticals là thứ user đã mua trên CDP, không phải yêu cầu của user. Lưu nó vào
        # constraints thì lượt sau `tool` cấm hẳn vertical đó (lỗi "1 ngày thôi" ra FALLBACK).
        rec = {'strategy': 'cross_vertical', 'nextVertical': 'hotel', 'destination': 'Nha Trang',
               'recommendations': [{**product('h', taxonomy='hotel'), 'because': []}],
               'diagnostics': {'eventsUsed': 3, 'coldStart': False, 'excludedVerticals': ['attraction'], 'latencyMs': 1}}
        store = InMemoryConversationStore()
        clients = Clients(products=[product(), product('h', taxonomy='hotel')], rec=rec)
        plan = [{'name': 'search_products', 'args': {'query': 'tour'}}, {'name': 'get_recommendations', 'args': {}}]
        first = await self.run_graph(ScriptedLlm(plan=plan), clients, store=store, owner='one')
        self.assertNotIn('a', first['candidates'])
        self.assertNotIn('attraction', first['constraints'].get('exclude_taxonomies', []))
        saved = await store.load(first['conversation_id'], 'one')
        self.assertNotIn('attraction', saved['constraints'].get('exclude_taxonomies', []))

        clients.rec = {**rec, 'strategy': 'popular', 'diagnostics': {**rec['diagnostics'], 'excludedVerticals': []}}
        second = await self.run_graph(ScriptedLlm(plan=plan), clients,
                                      state={'conversation_id': first['conversation_id']}, store=store, owner='one')
        self.assertIn('a', second['candidates'])
        self.assertEqual(second['response']['status'], 'COMPLETED')

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
            route='conversation',
            conversational_message='Xin chào! Bạn muốn đi đâu và dự định đi trong bao nhiêu ngày?',
        )
        result = await self.run_graph(llm, clients)
        self.assertEqual(result['http_status'], 200)
        self.assertEqual(result['response']['status'], 'NEEDS_CLARIFICATION')
        self.assertEqual(result['response']['question'], llm.conversational_message)
        self.assertEqual(result['response']['missingFields'], ['destination', 'days'])
        self.assertEqual(llm.calls, ['TurnRoute', 'ConversationalAnswer'])
        self.assertFalse(clients.calls)

    async def test_broad_suggestion_is_asked_by_clarify_without_catalog_claims(self):
        clients = Clients()
        llm = ScriptedLlm(
            extraction=extracted(),
            conversational_message='Mình có thể gợi ý sau khi bạn cho biết điểm đến và số ngày nhé.',
        )
        result = await self.run_graph(llm, clients, state={'query': 'Gợi ý cho tôi một chuyến đi'})
        self.assertEqual([event['node'] for event in result['events']], ['intake', 'classify', 'extract', 'clarify', 'finalize'])
        self.assertEqual(result['response']['status'], 'NEEDS_CLARIFICATION')
        # Không có `title` từ LLM thì dòng đầu in đậm là tiêu đề cố định của trường hợp thiếu cả điểm đến và số ngày.
        self.assertEqual(result['response']['question'], f'**Cần biết điểm đến và số ngày**\n{llm.conversational_message}')
        self.assertEqual(result['response']['missingFields'], ['destination', 'days'])
        self.assertEqual(llm.calls, ['TurnRoute', 'Extraction', 'ConversationalAnswer'])
        self.assertFalse(clients.calls)

    async def test_conversation_label_goes_to_converse_without_extracting(self):
        """`classify` quyết luồng một mình: nhãn conversation không chạy `extract`, không đụng intent."""
        clients = Clients()
        llm = ScriptedLlm(route='conversation', extraction=Extraction(patch={'days': 3}),
                          conversational_message='Chào bạn! Bạn muốn đi đâu?')
        result = await self.run_graph(llm, clients, state={'query': 'chào bạn'})
        self.assertEqual([event['node'] for event in result['events']], ['intake', 'classify', 'converse', 'finalize'])
        self.assertEqual(result['interaction_type'], 'conversation')
        self.assertNotIn('Extraction', llm.calls)
        self.assertIsNone(result['intent']['days'])
        self.assertFalse(clients.calls)

    async def test_intent_override_skips_the_classify_llm(self):
        llm = ScriptedLlm()
        result = await self.run_graph(llm, state={'query': '', 'intent_override': {'days': 2}})
        self.assertNotIn('TurnRoute', llm.calls)
        self.assertEqual([e['node'] for e in result['events']][:3], ['intake', 'classify', 'extract'])

    async def test_missing_trip_details_are_asked_by_clarify_and_chit_chat_is_answered(self):
        llm = ScriptedLlm(extraction=extracted(days=3), conversational_message='Bạn muốn đi thành phố nào?')
        result = await self.run_graph(llm)
        nodes = [event['node'] for event in result['events']]
        self.assertEqual(nodes, ['intake', 'classify', 'extract', 'clarify', 'finalize'])
        self.assertEqual(result['response']['question'], '**Bạn muốn đi đâu?**\nBạn muốn đi thành phố nào?')
        self.assertEqual(result['final_answer'], '**Bạn muốn đi đâu?**\nBạn muốn đi thành phố nào?')
        greeting = await self.run_graph(ScriptedLlm(route='conversation'))
        self.assertFalse(greeting['response']['question'].startswith('**'))  # chào hỏi, cảm ơn: không có tiêu đề
        self.assertEqual([event['node'] for event in greeting['events']], ['intake', 'classify', 'converse', 'finalize'])

    async def test_clarify_falls_back_to_the_reason_specific_fixed_question_when_the_model_fails(self):
        clients = Clients()
        conflict = Extraction(start_date_undecided=True, patch={'destination': 'Nha Trang', 'startDate': '2999-10-10', 'days': 2}, end_date='2999-10-12')
        result = await self.run_graph(ScriptedLlm(extraction=conflict, fail_conversation=True), clients)
        self.assertEqual(result['response']['status'], 'NEEDS_CLARIFICATION')
        self.assertIn('mâu thuẫn', result['response']['question'])
        self.assertTrue(result['response']['question'].startswith('**Thông tin chuyến đi chưa khớp nhau**\n'))
        missing = await self.run_graph(ScriptedLlm(extraction=extracted(days=3), fail_conversation=True), clients)
        self.assertEqual(missing['response']['question'],
                         '**Bạn muốn đi đâu?**\nBạn muốn đi du lịch ở tỉnh hoặc thành phố nào?')
        self.assertFalse(clients.calls)

    async def test_a_past_start_date_is_asked_again_by_the_model_without_searching(self):
        from datetime import timedelta
        from src.backend.app.agents.steps.classification import vietnam_today
        today = vietnam_today()
        yesterday = today - timedelta(days=1)
        clients = Clients()
        llm = ScriptedLlm(extraction=extracted(destination='Nha Trang', days=3, startDate=yesterday.isoformat()),
                          conversational_title='Ngày khởi hành không hợp lệ',
                          conversational_message='Ngày đó đã qua, bạn chọn ngày khác nhé.')
        result = await self.run_graph(llm, clients)
        response = result['response']
        self.assertEqual(response['status'], 'NEEDS_CLARIFICATION')
        self.assertEqual(response['question'], '**Ngày khởi hành không hợp lệ**\nNgày đó đã qua, bạn chọn ngày khác nhé.')
        self.assertIn('startDate', response['missingFields'])
        self.assertIsNone(response['knownIntent']['startDate'])
        self.assertFalse(clients.calls)
        # Câu hỏi do LLM viết; payload đưa sẵn hai ngày dd/mm/yyyy để nó chép lại.
        self.assertIn('ConversationalAnswer', llm.calls)
        prompt = llm.prompts['ConversationalAnswer']
        self.assertIn('past_date', prompt)
        self.assertIn(yesterday.strftime('%d/%m/%Y'), prompt)
        self.assertIn(today.strftime('%d/%m/%Y'), prompt)

    async def test_a_past_date_is_named_on_the_form_round_even_without_destination_and_days(self):
        # "di ngay 28 thang9" khi hôm nay là sau ngày đó: câu phải nêu ngày đã qua, form vẫn hiện và điền hôm nay.
        from datetime import timedelta
        from src.backend.app.agents.steps.classification import vietnam_today
        today = vietnam_today()
        past = today - timedelta(days=2)
        llm = ScriptedLlm(extraction=extracted(startDate=past.isoformat()), conversational_title='Ngày khởi hành không hợp lệ')
        clients = Clients()
        response = (await self.run_graph(llm, clients, state={'clarification_rounds': 1}))['response']
        self.assertEqual(response['status'], 'NEEDS_CLARIFICATION')
        self.assertTrue(response['question'].startswith('**Ngày khởi hành không hợp lệ**\n'))
        self.assertEqual(response['missingFields'][:2], ['destination', 'days'])
        self.assertIn('startDate', response['missingFields'])
        self.assertEqual(response['clarificationForm']['defaults']['startDate'], today.isoformat())
        self.assertIn('form_shown: true', llm.prompts['ConversationalAnswer'])
        self.assertFalse(clients.calls)

    async def test_change_without_a_value_asks_again_instead_of_planning_the_same_trip(self):
        # "đổi ngày" sau khi đã có lịch: LLM trích change_without_value, không patch gì → hỏi ngày mới, không gọi tool.
        extraction = Extraction(change_without_value=['startDate'])
        llm = ScriptedLlm(extraction=extraction, conversational_title='Đổi ngày khởi hành',
                          conversational_message='Bạn muốn đổi ngày khởi hành từ 10/10/2999 sang ngày nào?')
        clients = Clients()
        intent = {**empty_intent(), 'destination': 'Nha Trang', 'days': 2, 'startDate': '2999-10-10',
                  'party': {'type': 'SOLO', 'adults': 1, 'children': 0}}
        result = await self.run_graph(llm, clients, state={
            'query': 'đổi ngày', 'intent': intent,
            'previous_selection': [{'productId': 'a', 'name': 'Catalog a', 'taxonomy': 'hotel'}]})
        response = result['response']
        self.assertEqual(response['status'], 'NEEDS_CLARIFICATION')
        self.assertEqual(response['missingFields'], ['startDate'])
        self.assertEqual(response['knownIntent']['startDate'], '2999-10-10')
        self.assertTrue(response['question'].startswith('**Đổi ngày khởi hành**\n'))
        self.assertIn('clarification_reason: change_without_value', llm.prompts['ConversationalAnswer'])
        self.assertNotIn('tool', [event['node'] for event in result['events']])
        self.assertFalse(clients.calls)

    async def test_the_bold_title_falls_back_to_a_fixed_one_when_the_model_gives_none(self):
        from datetime import timedelta
        from src.backend.app.agents.steps.classification import vietnam_today
        yesterday = vietnam_today() - timedelta(days=1)
        llm = ScriptedLlm(extraction=extracted(destination='Nha Trang', days=3, startDate=yesterday.isoformat()))
        question = (await self.run_graph(llm))['response']['question']
        self.assertTrue(question.startswith('**Ngày khởi hành không hợp lệ**\n'))

    async def test_a_past_start_date_falls_back_to_a_fixed_question_naming_both_dates(self):
        from datetime import timedelta
        from src.backend.app.agents.steps.classification import vietnam_today
        today = vietnam_today()
        yesterday = today - timedelta(days=1)
        llm = ScriptedLlm(extraction=extracted(destination='Nha Trang', days=3, startDate=yesterday.isoformat()),
                          fail_conversation=True)
        response = (await self.run_graph(llm, state={'start_date_asked': True}))['response']
        self.assertEqual(response['status'], 'NEEDS_CLARIFICATION')
        self.assertTrue(response['question'].startswith('**Ngày khởi hành không hợp lệ**\n'))
        self.assertIn(yesterday.strftime('%d/%m/%Y'), response['question'])
        self.assertIn(today.strftime('%d/%m/%Y'), response['question'])
        self.assertEqual(response['missingFields'], ['startDate'])

    async def test_unmet_required_condition_is_asked_by_clarify_without_calling_the_model(self):
        clients = Clients(products=[product(taxonomy='hotel', unitPrice=1100000, priceUnit='UNKNOWN')])
        llm = ScriptedLlm(extraction=Extraction(start_date_undecided=True, patch={'destination': 'Nha Trang', 'days': 2},
                constraints={'require_hotel': True, 'hotel_price_max': 1200000, 'price_strict': True, 'hotel_price_unit': 'PER_NIGHT'}))
        result = await self.run_graph(llm, clients)
        self.assertEqual([event['node'] for event in result['events']][-3:], ['evaluate', 'clarify', 'finalize'])
        self.assertEqual(result['response']['status'], 'NEEDS_CLARIFICATION')
        self.assertNotIn('ConversationalAnswer', llm.calls)

    async def test_dates_derive_duration_and_conflicts_do_not_search(self):
        llm = ScriptedLlm(extraction=Extraction(start_date_undecided=True, patch={'destination': 'Nha Trang', 'startDate': '2999-10-10'}, end_date='2999-10-12'))
        result = await self.run_graph(llm)
        self.assertEqual(result['intent']['days'], 3)
        self.assertEqual(result['response']['itinerary']['days'][-1]['date'], '2999-10-12')
        clients = Clients()
        llm.extraction = Extraction(start_date_undecided=True, patch={'destination': 'Nha Trang', 'startDate': '2999-10-10', 'days': 2}, end_date='2999-10-12')
        result = await self.run_graph(llm, clients)
        self.assertEqual(result['response']['status'], 'NEEDS_CLARIFICATION')
        self.assertFalse(clients.calls)

    async def test_duration_outside_contract_is_asked_again_without_searching(self):
        clients = Clients()
        llm = ScriptedLlm(extraction=extracted(destination='Nha Trang', days=8), conversational_title='Số ngày không hợp lệ',
                          conversational_message='Mình lên lịch được từ 1 đến 7 ngày, bạn chọn lại giúp mình nhé.')
        result = await self.run_graph(llm, clients)
        self.assertEqual(result['http_status'], 200)
        response = result['response']
        self.assertEqual(response['status'], 'NEEDS_CLARIFICATION')
        self.assertTrue(response['question'].startswith('**Số ngày không hợp lệ**\n'))
        self.assertEqual(response['missingFields'], ['days'])
        self.assertEqual(response['suggestedValues']['days'], list(range(1, 8)))
        self.assertFalse(clients.calls)

    async def test_out_of_range_party_is_asked_again_instead_of_failing_as_llm_unavailable(self):
        party = {'type': 'SOLO', 'adults': 0, 'children': 0}
        result = await self.run_graph(ScriptedLlm(extraction=extracted(destination='Nha Trang', days=2, party=party)))
        self.assertEqual(result['http_status'], 200)
        self.assertEqual(result['response']['status'], 'NEEDS_CLARIFICATION')
        self.assertIn('party', result['response']['missingFields'])

    async def test_unsupported_destination_requires_catalog_evidence(self):
        clients = Clients(products=[])
        result = await self.run_graph(ScriptedLlm(extraction=extracted(destination='Tokyo', days=3)), clients)
        self.assertEqual(result['http_status'], 200)
        self.assertEqual(result['response']['status'], 'NEEDS_CLARIFICATION')
        self.assertEqual(result['response']['suggestedValues']['destination'], ['Nha Trang'])
        self.assertFalse(clients.calls)

    async def test_empty_search_is_not_a_provider_failure_or_an_unsupported_country_claim(self):
        result = await self.run_graph(clients=Clients(products=[]))
        self.assertEqual(result['response']['status'], 'NO_RESULTS')
        self.assertNotIn('trong nước', result['response']['message'])

    async def test_start_date_outside_the_sale_window_offers_the_nearest_open_date_and_other_destinations(self):
        window = {'availableFrom': '2999-10-01', 'availableTo': '2999-10-24'}
        clients = Clients(products=[product('a', **window), product('b', taxonomy='hotel', **window)],
                          destinations=['Nha Trang', 'Huế', 'Đà Nẵng'])
        llm = ScriptedLlm(extraction=extracted(destination='Nha Trang', days=3, startDate='2999-12-01'))
        result = await self.run_graph(llm, clients)
        response = result['response']
        self.assertEqual(response['status'], 'NO_RESULTS')
        self.assertIn('01/12/2999', response['message'])
        self.assertEqual(response['suggestions'],
                         ['Đi Nha Trang 3 ngày từ ngày 24/10/2999', 'Đi Huế 3 ngày', 'Đi Đà Nẵng 3 ngày'])

    async def test_catalog_destinations_are_listed_by_product_count_then_name(self):
        from src.backend.app.agents.steps.tool_planning import catalog_destinations

        class Listing:
            async def list_destinations(self):
                return {'destinations': [{'destination': 'An Giang', 'productCount': 3},
                                         {'destination': 'Nha Trang', 'productCount': 90},
                                         {'destination': 'Huế', 'productCount': 90}]}

        self.assertEqual(await catalog_destinations(Listing(), 1), ['Huế', 'Nha Trang', 'An Giang'])

    async def test_start_date_before_the_sale_window_suggests_the_first_open_day(self):
        window = {'availableFrom': '2999-10-01', 'availableTo': '2999-10-24'}
        clients = Clients(products=[product('a', **window)], destinations=['Nha Trang'])
        llm = ScriptedLlm(extraction=extracted(destination='Nha Trang', days=2, startDate='2999-09-01'))
        response = (await self.run_graph(llm, clients))['response']
        self.assertEqual(response['status'], 'NO_RESULTS')
        self.assertEqual(response['suggestions'], ['Đi Nha Trang 2 ngày từ ngày 01/10/2999'])

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
        # Intent extraction, the tool planner and the narration remain; nothing else may consult the model,
        # and the narration only words an itinerary that `compose` already built.
        self.assertEqual(llm.calls, ['TurnRoute', 'Extraction', 'planner', 'ItineraryNarration'])

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
            llm = ScriptedLlm(extraction=Extraction(start_date_undecided=True, patch={'destination': 'Nha Trang', 'days': 2},
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
        # `details` bị `evaluate` xoá sau khi dùng (docs/spec/agent/field-review.md §3.2); đếm qua
        # số lời gọi get_product_detail thay vì đọc lại state.
        self.assertEqual(len([call for call in clients.calls if call.startswith('detail:')]), 10)

    async def test_all_transient_failures_terminate_without_fake_results(self):
        # Kể cả get_recommendations là lời gọi duy nhất của planner, lưới an toàn category mặc định (§2.6) vẫn
        # thêm search hotel/attraction/golf; search cũng phải lỗi tạm thời để lượt này thực sự không còn ứng
        # viên nào, nếu không kết quả search thật sẽ hợp lệ thành FALLBACK thay vì lỗi.
        error = ToolError('TOOL_TIMEOUT', retryable=True)
        clients = Clients(rec_error=error, search_error=error)
        llm = ScriptedLlm(plan=[{'name': 'get_recommendations', 'args': {}}])
        result = await self.run_graph(llm, clients)
        self.assertEqual(clients.calls, ['rec', 'search', 'search', 'search'] * 2)
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
        result = await self.run_graph(ScriptedLlm(route='out_of_scope'), clients)
        self.assertEqual(result['http_status'], 400)
        self.assertFalse(clients.calls)

    async def test_a_travel_request_mixed_with_injection_is_refused_by_converse_without_planning(self):
        # Câu có lệnh chèn bị từ chối cả câu: dù patch có điểm đến và số ngày, không được đi tiếp tới tool/clarify.
        clients = Clients()
        llm = ScriptedLlm(route='out_of_scope', extraction=Extraction(patch={'destination': 'Nha Trang', 'days': 2}))
        result = await self.run_graph(llm, clients)
        self.assertEqual(result['http_status'], 400)
        self.assertEqual(result['response']['error']['code'], 'VALIDATION_ERROR')
        self.assertEqual([e['node'] for e in result['events']], ['intake', 'classify', 'converse', 'finalize'])
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
        second = await self.run_graph(ScriptedLlm(extraction=Extraction(
                    constraints={'exclude_products': ['vinpearl']})),
                    clients, state={'conversation_id': cid}, store=store, owner='one')
        chosen = [slot['product']['productId'] for day in second['response']['itinerary']['days']
                 for slot in day['slots'] if slot['product']]
        self.assertNotIn('vinpearl', chosen)
        self.assertIn('other', chosen)

    async def swap_turns(self, clients=None):
        """Hai lượt trên fixture catalog: lịch trình có chỗ ở, rồi "đổi khách sạn khác giống cái này"."""
        from src.backend.app.infrastructure.clients.itinerary_fixture_clients import FixtureItineraryClients
        store, clients = InMemoryConversationStore(), clients or FixtureItineraryClients()
        first_llm = ScriptedLlm()
        first = await self.run_graph(first_llm, clients, store=store)
        stay = first['response']['itinerary']['stay']['product']['productId']
        # Như LLM ở lượt đổi món: loại chỗ ở cũ, tìm chỗ ở tương tự nó và vẫn search loại còn lại.
        second_llm = ScriptedLlm(
            extraction=Extraction(start_date_undecided=True, constraints={'exclude_products': [stay]}),
            plan=[{'name': 'get_similar_products', 'args': {'productId': stay}},
                  {'name': 'search_products', 'args': {'query': 'tham quan', 'taxonomy': 'attraction'}}])
        second = await self.run_graph(second_llm, clients, state={'conversation_id': first['conversation_id']},
                                      store=store)
        return clients, first_llm, first, second_llm, second

    async def test_similar_is_offered_only_on_a_swap_turn(self):
        from src.backend.app.agents.steps.validation import selection_snapshot
        _, first_llm, first, second_llm, _ = await self.swap_turns()
        # Lượt đầu chưa có sản phẩm đã hiển thị: đúng bộ tool và prompt như trước khi có Similar.
        self.assertEqual(first_llm.bound_tools, [['search_products', 'get_recommendations']])
        # Planner luôn bị ép gọi tool: trả lời bằng câu chat thì plan rỗng và lượt rơi vào dead_letter.
        self.assertEqual(first_llm.tool_choices, ['any'])
        (_, system), (_, human) = first_llm.planner_messages[0]
        self.assertEqual(system, TOOL_PLAN_PROMPT)
        self.assertEqual(yaml.safe_load(human)['previous_selection'], [])    # ngữ cảnh chung: chưa hiển thị gì
        # Lượt đổi món: tool, gợi ý prompt và danh sách anchor lưu phía server cùng xuất hiện.
        self.assertIn('get_similar_products', second_llm.bound_tools[0])
        (_, system), (_, human) = second_llm.planner_messages[0]
        self.assertEqual(system, f'{TOOL_PLAN_PROMPT} {SIMILAR_HINT}')
        self.assertEqual(yaml.safe_load(human)['previous_selection'], selection_snapshot(first['response']))

    async def test_swap_turn_gets_a_grounded_similar_stay_labelled_search(self):
        clients, _, first, _, second = await self.swap_turns()
        catalog = {p['productId']: p for p in clients._products}
        old = first['response']['itinerary']['stay']['product']['productId']
        self.assertEqual(second['response']['status'], 'COMPLETED')
        self.assertEqual(second['validation_issues'], [])
        self.assertEqual(second['attempt'], 0)
        stay = second['response']['itinerary']['stay']
        new = stay['product']['productId']
        self.assertNotEqual(new, old)
        self.assertEqual(stay['source'], 'SEARCH')
        # Tên, giá lấy nguyên từ catalog; cùng taxonomy và cùng điểm đến với chỗ ở cũ.
        source = catalog[new]
        self.assertEqual((stay['product']['name'], stay['product']['unitPrice']), (source['name'], source['unitPrice']))
        self.assertEqual((source['taxonomy'], source['destination']), ('hotel', 'Nha Trang'))
        similar = next(r for r in second['tool_results'] if r['name'] == 'get_similar_products')
        self.assertEqual(similar['arguments']['productId'], old)
        # Kết quả Similar cùng điểm đến thành ứng viên nguồn search. Compose vẫn chọn chỗ ở theo luật cố định
        # (rẻ nhất trước) trên cả kết quả search khách sạn mà lưới an toàn thêm vào, nên stay có thể đến từ search.
        alternatives = [p['productId'] for p in similar['data']['results'] if p['destination'] == 'Nha Trang']
        self.assertTrue(alternatives)
        self.assertTrue(all(pid in second['candidates'] and second['sources'][pid] == 'search' for pid in alternatives))
        self.assertIn({'name': 'search_products', 'taxonomy': 'hotel'},
                      [{'name': call['name'], 'taxonomy': call['args'].get('taxonomy')} for call in second['tool_plan']])
        # Similar trả cả khách sạn nơi khác: bị bỏ lặng lẽ, không thành ứng viên hay cảnh báo.
        self.assertTrue(any(p['destination'] != 'Nha Trang' for p in similar['data']['results']))
        self.assertTrue(all(p['destination'] == 'Nha Trang' for p in second['candidates'].values()))
        self.assertNotIn('PRODUCT_DROPPED_DESTINATION', [w['code'] for w in second['warnings']])

    async def test_swap_turn_keeps_a_stay_when_similar_has_no_alternative(self):
        from src.backend.app.infrastructure.clients.itinerary_fixture_clients import FixtureItineraryClients

        class NotIndexed(FixtureItineraryClients):
            async def get_similar_products(self, product_id, limit):
                raise ToolError('PRODUCT_NOT_INDEXED', http_status=409)

        # Plan chỉ search loại khác (attraction): lưới an toàn phải thêm search chỗ ở cho loại đang đổi.
        _, _, first, _, second = await self.swap_turns(NotIndexed())
        old = first['response']['itinerary']['stay']['product']['productId']
        self.assertEqual(second['response']['status'], 'COMPLETED')
        self.assertEqual(second['attempt'], 0)
        self.assertIn({'name': 'search_products', 'taxonomy': 'hotel'},
                      [{'name': call['name'], 'taxonomy': call['args'].get('taxonomy')} for call in second['tool_plan']])
        stay = second['response']['itinerary']['stay']
        self.assertIsNotNone(stay)
        self.assertNotEqual(stay['product']['productId'], old)
        self.assertEqual(stay['source'], 'SEARCH')

    async def test_unavailable_similar_is_not_retried_when_search_returned_data(self):
        class SimilarClients(Clients):
            supports_similar = True
            failure = None

            async def get_similar_products(self, product_id, limit):
                self.calls.append('similar')
                if self.failure == 'timeout':
                    await asyncio.sleep(1)
                raise ToolError('SEARCH_UNAVAILABLE', retryable=True, http_status=503)

        shown = [{'productId': 'a', 'name': 'Catalog a', 'taxonomy': 'attraction'}]
        plan = [{'name': 'get_similar_products', 'args': {'productId': 'a'}},
                {'name': 'search_products', 'args': {'query': 'tham quan'}}]
        for failure in ('unavailable', 'timeout'):
            with self.subTest(failure=failure):
                clients = SimilarClients(products=[product('a'), product('b')])
                clients.failure = failure
                result = await self.run_graph(ScriptedLlm(plan=plan), clients, state={'previous_selection': shown},
                                              tool_timeout_seconds=0.1)
                self.assertEqual(result['response']['status'], 'COMPLETED')
                self.assertEqual(result['attempt'], 0)
                self.assertEqual(clients.calls.count('similar'), 1)
                self.assertNotIn('retry', [event['node'] for event in result['events']])

    async def test_memory_checkpoint_resumes_after_classification(self):
        clients, llm = Clients(), ScriptedLlm()
        gateway = ItineraryToolGateway(clients, clients, clients)
        checkpointer = build_checkpointer()
        interrupted = build_graph(tools=gateway, llm=llm, checkpointer=checkpointer)
        # A fresh compiled graph can resume a saved thread without redoing classification.
        config = {'configurable': {'thread_id': 'resume-test'}}
        await interrupted.ainvoke({'query': 'travel', 'request_id': 'resume', 'start_date_asked': True}, config,
                                  interrupt_after=['extract'])
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

    async def test_a_stated_budget_keeps_the_total_and_says_what_it_covers(self):
        # A budget is the reason to show the number, not to hide it; the warning carries the caveat.
        result = await self.run_graph(ScriptedLlm(extraction=extracted(destination='Nha Trang', days=2,
                        budget=1000000, party={'type': 'SOLO', 'adults': 1, 'children': 0})))
        itinerary = result['response']['itinerary']
        self.assertIsNotNone(itinerary['estimatedTotal'])
        self.assertIn(itinerary['budgetStatus'], ('WITHIN_BUDGET', 'OVER_BUDGET'))
        codes = [w['code'] for w in result['response']['warnings']]
        self.assertIn('PRODUCT_COST_ONLY', codes)
        self.assertIn('BUDGET_ON_PRODUCT_COST', codes)
        self.assertNotIn('UNKNOWN_TOTAL', codes)

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
