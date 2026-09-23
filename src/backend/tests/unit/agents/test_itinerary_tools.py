"""Tool boundary checks using transport doubles, without an API mock dataset."""
import asyncio
import copy
import importlib.util
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import httpx

from src.backend.app.agents import nodes, routing
from src.backend.app.agents.tools.itinerary_gateway import ItineraryToolGateway
from src.backend.app.application.itinerary.tool_contracts import definitions, normalize_arguments, validate
from src.backend.app.application.ports.itinerary_tools import ToolError
from src.backend.app.infrastructure.clients.itinerary_http_clients import ItineraryHttpClients
from src.backend.app.core.request_context import _request_id


class ContractTests(unittest.TestCase):
    def test_nonfinite_numbers_are_not_valid_json_contract_values(self):
        for number in (float('nan'), float('inf')):
            with self.subTest(number=number), self.assertRaises(ToolError):
                validate('search_products', {'results': [], 'total': number}, 'response')

    def test_schemas_and_defaults(self):
        self.assertEqual({d['name'] for d in definitions()}, {'search_products', 'get_recommendations'})
        args = normalize_arguments('search_products', {'query': 'hotel', 'availableOnly': False,
                                                     'offset': 0, 'limit': None, 'sort': None})
        # includeVariants mặc định false theo SearchRequest (schemas/search.yaml): chỉ tầng cha,
        # không trả hạng phòng và chuyến bay cụ thể.
        self.assertEqual(args, {'query': 'hotel', 'availableOnly': False, 'offset': 0,
                               'limit': 20, 'sort': 'relevance', 'includeVariants': False})
        self.assertEqual(normalize_arguments('get_recommendations', {}), {'k': 5})

    def test_unsupported_and_invalid_arguments(self):
        cases = [('search_products', {'query': ' '}), ('search_products', {'query': 'hotel', 'startDate': '2026-10-01'}),
                 ('search_products', {'query': 'hotel', 'priceMin': 2, 'priceMax': 1}),
                 ('search_products', {'query': 'hotel', 'authorization': 'secret'}),
                 ('get_recommendations', {'k': 0}), ('get_recommendations', {'k': 21}),
                 ('get_recommendations', {'k': None}), ('booking', {})]
        for name, args in cases:
            with self.subTest(name=name, args=args), self.assertRaises(ToolError):
                normalize_arguments(name, args)


class HttpTests(unittest.IsolatedAsyncioTestCase):
    async def test_auth_tracing_defaults_and_empty_responses(self):
        requests = []
        async def handler(request):
            requests.append(request)
            body = {'results': [], 'total': 0} if request.url.path.endswith('/search') else {'strategy': 'popular', 'recommendations': []}
            return httpx.Response(200, json=body)
        token = _request_id.set('tools-test')
        try:
            async with httpx.AsyncClient(base_url='https://service.test/api/v1/',
                    transport=httpx.MockTransport(handler), auth=('inherited', 'secret'),
                    headers={'Authorization': 'inherited-secret'}, cookies={'session': 'secret'}) as http:
                clients = ItineraryHttpClients(http)
                gateway = ItineraryToolGateway(clients, clients, recommendation_authorization='Bearer request-jwt')
                search = await gateway.execute({'id': 'a', 'name': 'search_products', 'args': {'query': 'hotel'}})
                rec = await gateway.execute({'id': 'b', 'name': 'get_recommendations', 'args': {}})
                self.assertNotIn('error', search)
                self.assertNotIn('error', rec)
                self.assertEqual(search['data'], {'results': [], 'total': 0})
                self.assertNotIn('authorization', requests[0].headers)
                self.assertEqual(requests[1].headers['authorization'], 'Bearer request-jwt')
                self.assertEqual(requests[1].url.params['k'], '5')
                self.assertEqual(requests[0].method, 'GET')
                self.assertEqual(requests[0].url.path, '/api/v1/search')
                self.assertEqual(requests[0].url.params['q'], 'hotel')
                for request in requests:
                    self.assertNotIn('cookie', request.headers)
                    self.assertEqual(request.headers['X-Request-ID'], 'tools-test')
                self.assertNotIn('request-jwt', str(rec))
        finally:
            _request_id.reset(token)

    async def test_errors_are_safe_and_classified(self):
        cases = [(401, {'message': 'secret'}, False), (400, {}, False),
                 (503, {}, True), (200, {'results': [], 'total': -1}, False)]
        for status, body, retryable in cases:
            with self.subTest(status=status):
                async with httpx.AsyncClient(base_url='https://service.test/api/v1/',
                        transport=httpx.MockTransport(lambda request: httpx.Response(status, json=body))) as http:
                    clients = ItineraryHttpClients(http)
                    result = await ItineraryToolGateway(clients, clients).execute(
                        {'id': 'a', 'name': 'search_products', 'args': {'query': 'hotel'}})
                    self.assertEqual(result['error']['retryable'], retryable)
                    self.assertNotIn('secret', str(result))
                    self.assertEqual(result['error']['httpStatus'], status if status != 200 else None)

    async def test_minimal_projection_preserves_null_false_and_because(self):
        product = {'productId': 'contract-test', 'name': 'ERROR is product text', 'taxonomy': 'hotel',
                   'destination': 'Nha Trang', 'unitPrice': None, 'currency': 'VND',
                   'priceUnit': 'UNKNOWN', 'available': False, 'because': [],
                   'attributes': {'oceanView': False}}
        body = {'strategy': 'popular', 'recommendations': [product]}
        async with httpx.AsyncClient(base_url='https://service.test/api/v1/',
                transport=httpx.MockTransport(lambda request: httpx.Response(200, json=body))) as http:
            clients = ItineraryHttpClients(http)
            result = await ItineraryToolGateway(clients, clients).execute(
                {'id': 'a', 'name': 'get_recommendations', 'args': {}})
            self.assertEqual(result['data'], body)
            self.assertEqual(nodes.evaluate_node({'tool_results': [result]})['evaluation_result'], 'success')
            product['because'] = [{'productName': 'Hotel', 'event': 'product_view', 'daysAgo': 1}]
            invalid = await ItineraryToolGateway(clients, clients).execute(
                {'id': 'b', 'name': 'get_recommendations', 'args': {}})
            self.assertEqual(invalid['error']['code'], 'INVALID_TOOL_RESPONSE')

    async def test_upstream_contract_code_is_preserved_without_message(self):
        body = {'error': {'code': 'TOKEN_EXPIRED', 'message': 'secret',
                          'retryable': True, 'requestId': 'test'}}
        async with httpx.AsyncClient(base_url='https://service.test/api/v1/',
                transport=httpx.MockTransport(lambda request: httpx.Response(401, json=body))) as http:
            clients = ItineraryHttpClients(http)
            result = await ItineraryToolGateway(clients, clients).execute(
                {'id': 'a', 'name': 'get_recommendations', 'args': {}})
            self.assertEqual(result['error']['code'], 'TOKEN_EXPIRED')
            self.assertFalse(result['error']['retryable'])
            self.assertNotIn('secret', str(result))

    async def test_timeout_and_invalid_json(self):
        async def timeout(request):
            raise httpx.ReadTimeout('secret', request=request)
        for handler, code in [(timeout, 'TOOL_TIMEOUT'),
                              (lambda request: httpx.Response(200, text='not json'), 'INVALID_TOOL_RESPONSE')]:
            async with httpx.AsyncClient(base_url='https://service.test/api/v1/', transport=httpx.MockTransport(handler)) as http:
                clients = ItineraryHttpClients(http)
                result = await ItineraryToolGateway(clients, clients).execute(
                    {'id': 'a', 'name': 'search_products', 'args': {'query': 'hotel'}})
                self.assertEqual(result['error']['code'], code)
                self.assertNotIn('secret', str(result))

    async def test_search_maps_only_supported_legacy_query_parameters(self):
        requests = []

        async def handler(request):
            requests.append(request)
            return httpx.Response(200, json={'results': [], 'total': 0})

        async with httpx.AsyncClient(base_url='https://service.test/api/v1/',
                transport=httpx.MockTransport(handler)) as http:
            clients = ItineraryHttpClients(http)
            result = await ItineraryToolGateway(clients, clients).execute({
                'id': 'a', 'name': 'search_products',
                'args': {'query': 'hotel gia đình', 'destination': 'Nha Trang',
                         'priceMax': 2_000_000, 'starRatingMin': 4},
            })
        self.assertNotIn('error', result)
        self.assertEqual(dict(requests[0].url.params), {
            'q': 'hotel gia đình', 'destination': 'Nha Trang', 'limit': '20', 'offset': '0'
        })
        self.assertNotIn('authorization', requests[0].headers)


class NodeTests(unittest.IsolatedAsyncioTestCase):
    async def test_retry_only_failed_call_without_replanning_or_mutation(self):
        class Executor:
            def __init__(self):
                self.calls = []
            async def execute(self, call):
                self.calls.append(call['name'])
                if call['name'] == 'get_recommendations' and self.calls.count(call['name']) == 1:
                    return {'tool_call_id': call['id'], 'error': ToolError('TOOL_TIMEOUT', retryable=True).as_dict()}
                data = {'results': [], 'total': 0} if call['name'] == 'search_products' else {'strategy': 'popular', 'recommendations': []}
                return {'tool_call_id': call['id'], 'data': data}
        tools = Executor()
        state = {'tool_plan': [{'name': 'search_products', 'args': {'query': 'hotel'}},
                               {'name': 'get_recommendations', 'args': {}}], 'attempt': 0, 'max_attempts': 3}
        before = copy.deepcopy(state)
        first = await nodes.tool_node(state, tools=tools)
        self.assertEqual(state, before)
        self.assertEqual(nodes.evaluate_node(first)['evaluation_result'], 'needs_retry')
        second = await nodes.tool_node({**state, **first, 'attempt': 1}, tools=tools)
        self.assertEqual(tools.calls, ['search_products', 'get_recommendations', 'get_recommendations'])
        self.assertEqual(nodes.evaluate_node(second)['evaluation_result'], 'success')
        self.assertEqual(routing.route_after_retry({'attempt': 2, 'max_attempts': 100}), 'dead_letter')

    async def test_planner_uses_tool_definitions(self):
        class Executor:
            definitions = staticmethod(definitions)
            async def execute(self, call):
                return {'tool_call_id': call['id'], 'data': {'strategy': 'popular', 'recommendations': []}}
        async def plan(prompt):
            return SimpleNamespace(tool_calls=[{'name': 'get_recommendations', 'args': {'destination': 'Da Nang'}}])
        llm = SimpleNamespace(bind_tools=lambda schemas: SimpleNamespace(ainvoke=plan))
        with patch.object(nodes, 'get_llm', return_value=llm):
            result = await nodes.tool_node({'query': 'recommend Da Nang'}, tools=Executor())
        self.assertEqual(result['tool_plan'][0]['args'], {'destination': 'Da Nang', 'k': 5})

    async def test_planner_wording_of_the_destination_does_not_fail_the_plan(self):
        """Planner viết "Hồ Chí Minh", intent giữ tên catalog "TP. Hồ Chí Minh" — cùng một chuyến đi."""
        class Executor:
            definitions = staticmethod(definitions)
            async def execute(self, call):
                return {'tool_call_id': call['id'], 'data': {'strategy': 'popular', 'recommendations': []}}
        async def plan(prompt):
            return SimpleNamespace(tool_calls=[{'name': 'get_recommendations', 'args': {'destination': 'Hồ Chí Minh'}}])
        llm = SimpleNamespace(bind_tools=lambda schemas: SimpleNamespace(ainvoke=plan))
        state = {'query': '2 ngày', 'intent': {'destination': 'TP. Hồ Chí Minh', 'days': 2}}
        with patch.object(nodes, 'get_llm', return_value=llm):
            result = await nodes.tool_node(state, tools=Executor())
        self.assertEqual(result['tool_plan'][0]['args']['destination'], 'TP. Hồ Chí Minh')
        self.assertNotIn('error', result.get('response', {}))

    async def test_search_call_without_query_falls_back_to_the_destination(self):
        """SearchRequest bắt buộc `query`; planner bỏ quên thì không được làm hỏng cả request."""
        class Executor:
            definitions = staticmethod(definitions)
            def __init__(self):
                self.seen = []
            async def execute(self, call):
                self.seen.append(call['args'])
                return {'tool_call_id': call['id'], 'data': {'results': []}}
        async def plan(prompt):
            return SimpleNamespace(tool_calls=[
                {'name': 'search_products', 'args': {'destination': 'Hạ Long', 'taxonomy': 'attraction', 'limit': 5}}])
        llm = SimpleNamespace(bind_tools=lambda schemas: SimpleNamespace(ainvoke=plan))
        tools = Executor()
        state = {'query': '2 ngày', 'intent': {'destination': 'Hạ Long', 'days': 2}}
        with patch.object(nodes, 'get_llm', return_value=llm):
            result = await nodes.tool_node(state, tools=tools)
        self.assertEqual(result['tool_plan'][0]['args']['query'], 'Hạ Long')
        self.assertEqual(tools.seen[0]['query'], 'Hạ Long')

    async def test_permanent_error_and_missing_configuration_do_not_retry(self):
        result = await nodes.tool_node({'query': 'hotel'})
        evaluated = nodes.evaluate_node(result)
        self.assertEqual(routing.route_after_evaluate(evaluated), 'dead_letter')
        self.assertEqual(nodes.evaluate_node({'tool_results': [{'error': ToolError('TOOL_HTTP_ERROR', http_status=401).as_dict()}]})['evaluation_result'], 'failed')

    async def test_deadline_is_bounded(self):
        class Slow:
            async def execute(self, call):
                await asyncio.sleep(10)
        result = await nodes.tool_node({'tool_plan': [{'name': 'get_recommendations', 'args': {}}]},
                                       tools=Slow(), timeout_seconds=0.01)
        self.assertEqual(result['tool_results'][0]['error']['code'], 'TOOL_TIMEOUT')


@unittest.skipUnless(importlib.util.find_spec("langgraph"), "LangGraph is not installed")
class GraphToolTests(unittest.TestCase):
    def test_graph_uses_http_gateway_and_retries_only_recommendations(self):
        from src.backend.app.agents.graph import build_graph
        calls = []
        def handler(request):
            calls.append(request.url.path)
            if request.url.path.endswith('/search'):
                return httpx.Response(200, json={'results': [], 'total': 0})
            if calls.count('/api/v1/recommendations') == 1:
                return httpx.Response(503, json={})
            return httpx.Response(200, json={'strategy': 'popular', 'recommendations': []})
        http = httpx.AsyncClient(base_url='https://service.test/api/v1/', transport=httpx.MockTransport(handler))
        clients = ItineraryHttpClients(http)
        gateway = ItineraryToolGateway(clients, clients)
        state = {'query': 'search hotel', 'attempt': 0, 'max_attempts': 3,
                 'tool_plan': [{'name': 'search_products', 'args': {'query': 'hotel'}},
                               {'name': 'get_recommendations', 'args': {}}]}
        try:
            from src.backend.tests.unit.agents.test_itinerary_runtime import ScriptedLlm
            llm = ScriptedLlm(plan=state['tool_plan'])
            result = asyncio.run(build_graph(tools=gateway, llm=llm).ainvoke(state))
            self.assertEqual(calls, ['/api/v1/search', '/api/v1/recommendations', '/api/v1/recommendations'])
            self.assertEqual(result['attempt'], 1)
            self.assertEqual(result['evaluation_result'], 'success')
            self.assertEqual(len(result['tool_results']), 2)
            self.assertEqual(result['events'][-1]['node'], 'finalize')
        finally:
            asyncio.run(http.aclose())


if __name__ == '__main__':
    unittest.main()
