"""Tool boundary checks using transport doubles, without an API mock dataset."""
import asyncio
import copy
import importlib.util
import json
import unittest
from types import SimpleNamespace

import httpx

from src.backend.app.agents import nodes, routing
from src.backend.app.agents.steps import tool_planning
from src.backend.app.agents.steps.history import llm_context
from src.backend.app.agents.steps.prompts import SIMILAR_HINT, TOOL_PLAN_PROMPT
from src.backend.app.agents.tools.itinerary_gateway import ItineraryToolGateway
from src.backend.app.application.itinerary.tool_contracts import contracts, definitions, normalize_arguments, validate
from src.backend.app.application.ports.itinerary_tools import ToolError
from src.backend.app.infrastructure.clients.itinerary_http_clients import ItineraryHttpClients
from src.backend.app.core.request_context import _request_id


class ContractTests(unittest.TestCase):
    def test_nonfinite_numbers_are_not_valid_json_contract_values(self):
        for number in (float('nan'), float('inf')):
            with self.subTest(number=number), self.assertRaises(ToolError):
                validate('search_products', {'results': [], 'total': number}, 'response')

    def test_schemas_and_defaults(self):
        self.assertEqual({d['name'] for d in definitions()},
                         {'search_products', 'get_recommendations', 'get_similar_products'})
        args = normalize_arguments('search_products', {'query': 'hotel', 'availableOnly': False,
                                                     'offset': 0, 'limit': None, 'sort': None})
        # includeVariants mặc định false theo SearchRequest (schemas/search.yaml): chỉ tầng cha,
        # không trả hạng phòng và chuyến bay cụ thể.
        self.assertEqual(args, {'query': 'hotel', 'availableOnly': False, 'offset': 0,
                               'limit': 20, 'sort': 'relevance', 'includeVariants': False})
        self.assertEqual(normalize_arguments('get_recommendations', {}), {'k': 5})
        # Tham số path productId là đối số bắt buộc; limit mặc định 8 theo getSimilarProducts.
        self.assertEqual(normalize_arguments('get_similar_products', {'productId': 'x'}),
                         {'productId': 'x', 'limit': 8})

    def test_unsupported_and_invalid_arguments(self):
        cases = [('search_products', {'query': ' '}), ('search_products', {'query': 'hotel', 'startDate': '2026-10-01'}),
                 ('search_products', {'query': 'hotel', 'priceMin': 2, 'priceMax': 1}),
                 ('search_products', {'query': 'hotel', 'authorization': 'secret'}),
                 ('get_recommendations', {'k': 0}), ('get_recommendations', {'k': 21}),
                 ('get_recommendations', {'k': None}), ('booking', {}),
                 ('get_similar_products', {}), ('get_similar_products', {'limit': 5}),
                 ('get_similar_products', {'productId': 'x', 'destination': 'Nha Trang'}),
                 ('get_similar_products', {'productId': 'x', 'limit': 0}),
                 ('get_similar_products', {'productId': 'x', 'limit': 21})]
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

    async def test_each_call_logs_one_line_without_arguments_or_token(self):
        """Log `itinerary.tool` thay access log khi tool chạy trong tiến trình; không bao giờ mang args/token."""
        body = {'results': [], 'total': 0}
        async with httpx.AsyncClient(base_url='https://service.test/api/v1/',
                transport=httpx.MockTransport(lambda request: httpx.Response(200, json=body))) as http:
            clients = ItineraryHttpClients(http)
            gateway = ItineraryToolGateway(clients, clients, recommendation_authorization='Bearer request-jwt')
            token = _request_id.set('log-test')
            try:
                with self.assertLogs('uvicorn.error', level='INFO') as logs:
                    await gateway.execute({'id': 'a', 'name': 'search_products',
                                           'args': {'query': 'secret-query-text', 'destination': 'Nha Trang'}})
                    await gateway.execute({'id': 'b', 'name': 'get_recommendations', 'args': {'k': 0}})
                    await gateway.execute({'id': 'c', 'name': 'checkout\nforged=1', 'args': {}})
            finally:
                _request_id.reset(token)
        lines = [line for line in logs.output if 'itinerary.tool ' in line]
        self.assertEqual(len(lines), 3)
        self.assertIn('requestId=log-test name=search_products outcome=ok code=- retryable=-', lines[0])
        self.assertIn('name=get_recommendations outcome=error code=INVALID_ARGUMENTS retryable=False', lines[1])
        self.assertIn('name=unknown outcome=error code=TOOL_NOT_ALLOWED', lines[2])
        for leaked in ('secret-query-text', 'Nha Trang', 'request-jwt', 'forged'):
            self.assertNotIn(leaked, '\n'.join(logs.output))

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

    async def test_similar_encodes_the_id_and_never_sends_authorization(self):
        requests = []

        async def handler(request):
            requests.append(request)
            return httpx.Response(200, json={'productId': 'H 1/x', 'strategy': 'same_taxonomy',
                                             'results': [], 'requestId': 'similar-test'})

        async with httpx.AsyncClient(base_url='https://service.test/api/v1/',
                transport=httpx.MockTransport(handler), headers={'Authorization': 'inherited-secret'}) as http:
            clients = ItineraryHttpClients(http)
            gateway = ItineraryToolGateway(clients, clients, recommendation_authorization='Bearer request-jwt',
                                           similar=clients)
            result = await gateway.execute({'id': 'a', 'name': 'get_similar_products',
                                            'args': {'productId': 'H 1/x', 'limit': 20}})
        self.assertNotIn('error', result)
        self.assertEqual(requests[0].method, 'GET')
        self.assertEqual(requests[0].url.raw_path, b'/api/v1/products/H%201%2Fx/similar?limit=20')
        self.assertNotIn('authorization', requests[0].headers)

    async def test_similar_not_indexed_is_final_and_unavailable_is_retryable(self):
        for status, code, retryable in ((409, 'PRODUCT_NOT_INDEXED', False), (404, 'PRODUCT_NOT_FOUND', False),
                                         (503, 'SEARCH_UNAVAILABLE', True)):
            body = {'error': {'code': code, 'message': 'secret', 'retryable': retryable, 'requestId': 'test'}}
            with self.subTest(status=status):
                async with httpx.AsyncClient(base_url='https://service.test/api/v1/',
                        transport=httpx.MockTransport(lambda request: httpx.Response(status, json=body))) as http:
                    clients = ItineraryHttpClients(http)
                    result = await ItineraryToolGateway(clients, clients, similar=clients).execute(
                        {'id': 'a', 'name': 'get_similar_products', 'args': {'productId': 'H1'}})
                self.assertEqual(result['error'], {'code': code, 'retryable': retryable, 'httpStatus': status})
                self.assertNotIn('secret', str(result))


class GatewayTests(unittest.IsolatedAsyncioTestCase):
    """Bảng handler: planner chỉ thấy và gọi được tool có port; similar đi đúng port của nó."""

    class Ports:
        def __init__(self):
            self.calls = []

        async def search_products(self, request):
            self.calls.append(('search', request))
            return {'results': [], 'total': 0}

        async def get_recommendations(self, request, authorization=None):
            self.calls.append(('rec', request))
            return {'strategy': 'popular', 'recommendations': []}

    class Similar:
        def __init__(self, body=None):
            self.calls = []
            self.body = body if body is not None else {'productId': 'H1', 'strategy': 'same_taxonomy',
                                                       'results': [], 'requestId': 'similar-test'}

        async def get_similar_products(self, product_id, limit):
            self.calls.append((product_id, limit))
            return copy.deepcopy(self.body)

    async def test_similar_is_routed_to_the_similar_port(self):
        ports, similar = self.Ports(), self.Similar()
        gateway = ItineraryToolGateway(ports, ports, similar=similar)
        self.assertEqual({d['name'] for d in gateway.definitions()},
                         {'search_products', 'get_recommendations', 'get_similar_products'})
        result = await gateway.execute({'id': 'a', 'name': 'get_similar_products', 'args': {'productId': 'H1'}})
        self.assertEqual(result['data'], similar.body)
        self.assertEqual(result['arguments'], {'productId': 'H1', 'limit': 8})
        self.assertEqual(similar.calls, [('H1', 8)])
        self.assertEqual(ports.calls, [])
        self.assertEqual(await gateway.call_tool('get_similar_products', {'productId': 'H2', 'limit': 3}),
                         similar.body)
        self.assertEqual(similar.calls[-1], ('H2', 3))

    async def test_without_a_similar_port_the_tool_is_hidden_and_not_allowed(self):
        ports = self.Ports()
        gateway = ItineraryToolGateway(ports, ports, ports)
        self.assertEqual([d['name'] for d in gateway.definitions()], ['search_products', 'get_recommendations'])
        for args in ({'productId': 'H1'}, {'productId': 'H1', 'limit': 0}):
            with self.subTest(args=args):
                result = await gateway.execute({'id': 'a', 'name': 'get_similar_products', 'args': args})
                self.assertEqual(result['error']['code'], 'TOOL_NOT_ALLOWED')
                self.assertEqual(result['arguments'], {})
        with self.assertRaises(ToolError) as caught:
            await gateway.call_tool('get_similar_products', {'productId': 'H1'})
        self.assertEqual(caught.exception.code, 'TOOL_NOT_ALLOWED')
        self.assertEqual(ports.calls, [])

    async def test_similar_response_is_validated_against_the_contract(self):
        ports = self.Ports()
        body = {'productId': 'H1', 'strategy': 'same_taxonomy', 'results': []}  # thiếu requestId
        gateway = ItineraryToolGateway(ports, ports, similar=self.Similar(body))
        result = await gateway.execute({'id': 'a', 'name': 'get_similar_products', 'args': {'productId': 'H1'}})
        self.assertEqual(result['error']['code'], 'INVALID_TOOL_RESPONSE')
        self.assertNotIn('data', result)


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
        result = await nodes.tool_node({'query': 'recommend Da Nang'}, tools=Executor(), llm=llm)
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
        result = await nodes.tool_node(state, tools=Executor(), llm=llm)
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
        result = await nodes.tool_node(state, tools=tools, llm=llm)
        self.assertEqual(result['tool_plan'][0]['args']['query'], 'Hạ Long')
        self.assertEqual(tools.seen[0]['query'], 'Hạ Long')

    async def test_unknown_argument_from_planner_is_dropped_not_fatal(self):
        """Planner tự thêm `excludeProducts` (không có trong SearchRequest) khi constraints có
        exclude_products; trước đây cả plan bị huỷ → 503 LLM_UNAVAILABLE ở lượt đổi số ngày."""
        class Executor:
            definitions = staticmethod(definitions)
            def __init__(self):
                self.seen = []
            async def execute(self, call):
                self.seen.append(call['args'])
                return {'tool_call_id': call['id'], 'data': {'results': []}}
        async def plan(prompt):
            return SimpleNamespace(tool_calls=[{'name': 'search_products', 'args': {
                'query': 'Đà Lạt', 'taxonomy': 'attraction', 'limit': 5, 'excludeProducts': ['p-1']}}])
        llm = SimpleNamespace(bind_tools=lambda schemas: SimpleNamespace(ainvoke=plan))
        tools = Executor()
        state = {'query': 'rút ngắn còn 2 ngày', 'intent': {'destination': 'Đà Lạt', 'days': 2},
                 'constraints': {'exclude_products': ['p-1']}}
        result = await nodes.tool_node(state, tools=tools, llm=llm)
        self.assertEqual(len(result['tool_plan']), 1)
        self.assertNotIn('excludeProducts', result['tool_plan'][0]['args'])
        self.assertNotIn('excludeProducts', tools.seen[0])
        self.assertNotIn('error', result.get('response', {}))

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

    async def test_timeout_is_logged_without_arguments(self):
        class Slow:
            async def execute(self, call):
                await asyncio.sleep(10)
        state = {'request_id': 'timeout-test',
                 'tool_plan': [{'name': 'get_recommendations', 'args': {'destination': 'Secret Bay'}}]}
        with self.assertLogs('uvicorn.error', level='WARNING') as logs:
            await nodes.tool_node(state, tools=Slow(), timeout_seconds=0.01)
        self.assertIn('itinerary.tool.timeout requestId=timeout-test name=get_recommendations', logs.output[0])
        self.assertNotIn('Secret Bay', '\n'.join(logs.output))


SELECTION = [{'productId': 'H1', 'name': 'Khách sạn đã xem', 'taxonomy': 'hotel'},
             {'productId': 'A1', 'name': 'Điểm tham quan đã xem', 'taxonomy': 'attraction'}]
REC = {'name': 'get_recommendations', 'args': {}}


def swap_state(**updates):
    """State của lượt đổi món: previous_selection do server lưu từ lịch trình lượt trước."""
    return {'request_id': 'swap-test', 'query': 'đổi khách sạn khác giống cái này',
            'previous_selection': copy.deepcopy(SELECTION), 'intent': {'destination': 'Nha Trang', 'days': 2},
            'constraints': {}, **updates}


def similar(product_id, **args):
    return {'name': 'get_similar_products', 'args': {'productId': product_id, **args}}


def search(**args):
    return {'name': 'search_products', 'args': {'query': 'khách sạn', **args}}


def names(plan):
    return [call['name'] for call in plan]


class SimilarPlanTests(unittest.IsolatedAsyncioTestCase):
    """validated_plan/build_plan với Similar: anchor chỉ từ previous_selection, tối đa 2 lời gọi, lưới an toàn
    search, id liên tục (docs/spec/hop-dong-tich-hop-itinerary-assistant.md §2.5)."""

    def test_invented_anchor_is_dropped_and_the_log_never_carries_it(self):
        with self.assertLogs('uvicorn.error', level='WARNING') as logs:
            plan = tool_planning.validated_plan(swap_state(), [similar('H1'), similar('INVENTED-9'),
                                                               similar(['H1']), search()])
        self.assertEqual(names(plan), ['get_similar_products', 'search_products'])
        self.assertEqual(plan[0]['args']['productId'], 'H1')
        self.assertEqual(len(logs.output), 2)
        for line in logs.output:
            self.assertIn('itinerary.tool_plan.similar_dropped requestId=swap-test reason=unknown_anchor', line)
        self.assertNotIn('INVENTED-9', '\n'.join(logs.output))

    def test_plan_with_only_invented_anchors_becomes_a_deterministic_destination_search(self):
        expected = normalize_arguments('search_products', {'query': 'Nha Trang', 'destination': 'Nha Trang'})
        plan = tool_planning.validated_plan(swap_state(), [similar('X1'), similar('X2')])
        self.assertEqual(plan, [{'id': 'call-0', 'name': 'search_products', 'args': expected}])
        with_rec = tool_planning.validated_plan(swap_state(), [similar('X1')], require_recommendations=True)
        self.assertEqual(names(with_rec), ['search_products', 'get_recommendations'])
        self.assertEqual([call['id'] for call in with_rec], ['call-0', 'call-1'])
        # Không có điểm đến chuẩn hóa thì không có search tất định để thay; plan rỗng vẫn sai như trước.
        for state, plan in ((swap_state(intent={}), [similar('X1')]), (swap_state(), [])):
            with self.subTest(plan=plan), self.assertRaises(ToolError) as caught:
                tool_planning.validated_plan(state, plan)
            self.assertEqual(caught.exception.code, 'INVALID_TOOL_PLAN')

    def test_six_raw_calls_with_a_duplicate_similar_fit_the_call_budget(self):
        raw = [similar('H1'), similar('H1'), search(), search(taxonomy='attraction'), search(taxonomy='golf'), REC]
        plan = tool_planning.validated_plan(swap_state(), raw)
        self.assertEqual(len(plan), tool_planning.MAX_CALLS)
        self.assertEqual(names(plan), ['get_similar_products', 'search_products', 'search_products',
                                       'search_products', 'get_recommendations'])

    def test_valid_anchor_gets_the_contract_maximum_limit_and_no_destination(self):
        maximum = contracts()['get_similar_products']['arguments']['properties']['limit']['maximum']
        # limit do planner chọn (kể cả ngoài hợp đồng) bị thay; destination không phải tham số của Similar.
        plan = tool_planning.validated_plan(swap_state(), [similar('H1', limit=99, destination='Đà Nẵng'), search()])
        self.assertEqual(plan[0]['args'], {'productId': 'H1', 'limit': maximum})
        self.assertEqual(plan[1]['args']['destination'], 'Nha Trang')

    def test_at_most_two_similar_calls_and_one_per_anchor(self):
        selection = SELECTION + [{'productId': 'G1', 'name': 'Sân golf đã xem', 'taxonomy': 'golf'}]
        raw = [similar('H1'), similar('H1'), similar('A1'), similar('G1'), search()]
        with self.assertLogs('uvicorn.error', level='WARNING') as logs:
            plan = tool_planning.validated_plan(swap_state(previous_selection=selection), raw)
        self.assertEqual([call['args'].get('productId') for call in plan], ['H1', 'A1', None])
        self.assertIn('reason=duplicate_anchor', logs.output[0])
        self.assertIn('reason=similar_limit', logs.output[1])

    def test_full_budget_with_required_recommendations_drops_the_last_similar_call(self):
        raw = [similar('H1'), search(), search(taxonomy='attraction'), search(taxonomy='golf'), similar('A1')]
        plan = tool_planning.validated_plan(swap_state(), raw, require_recommendations=True)
        self.assertEqual(names(plan), ['get_similar_products', 'search_products', 'search_products',
                                       'search_products', 'get_recommendations'])
        self.assertEqual(plan[0]['args']['productId'], 'H1')
        # Không còn Similar để nhường chỗ thì vẫn là plan sai như trước khi có Similar.
        with self.assertRaises(ToolError) as caught:
            tool_planning.validated_plan(swap_state(), [search()] * 5, require_recommendations=True)
        self.assertEqual(caught.exception.code, 'INVALID_TOOL_PLAN')

    def test_similar_without_search_gets_a_safety_net_search(self):
        plan = tool_planning.validated_plan(swap_state(), [similar('H1')])
        self.assertEqual(names(plan), ['get_similar_products', 'search_products'])
        # Search tất định cho đúng loại đang đổi (loại của anchor trong previous_selection).
        self.assertEqual((plan[1]['args']['query'], plan[1]['args']['destination'], plan[1]['args']['taxonomy']),
                         ('Nha Trang', 'Nha Trang', 'hotel'))
        # Đã đủ 5 lời gọi: bỏ Similar cuối để chèn search, không vượt trần.
        full = tool_planning.validated_plan(swap_state(), [similar('H1'), REC, REC, REC, REC])
        self.assertEqual(names(full), ['get_recommendations', 'get_recommendations', 'get_recommendations',
                                       'get_recommendations', 'search_products'])
        self.assertEqual(full[4]['args']['taxonomy'], 'hotel')
        # Hai loại đang đổi, trần đầy: mỗi loại một search, nhường chỗ bằng cả hai lời gọi Similar.
        both = tool_planning.validated_plan(swap_state(), [similar('H1'), similar('A1'), REC, REC, REC])
        self.assertEqual(names(both), ['get_recommendations'] * 3 + ['search_products'] * 2)
        self.assertEqual([call['args']['taxonomy'] for call in both[3:]], ['hotel', 'attraction'])

    def test_safety_net_searches_the_category_being_swapped(self):
        # Search của loại khác không che được loại đang đổi: Similar lỗi mềm hay chỉ ra kết quả nơi khác thì
        # lượt đổi khách sạn sẽ không còn ứng viên chỗ ở.
        state = swap_state(constraints={'hotel_price_max': 900000})
        plan = tool_planning.validated_plan(state, [similar('H1'), search(taxonomy='attraction')])
        self.assertEqual(names(plan), ['get_similar_products', 'search_products', 'search_products'])
        self.assertEqual(plan[2]['args']['taxonomy'], 'hotel')
        self.assertEqual((plan[2]['args']['query'], plan[2]['args']['priceMax']), ('Nha Trang', 900000))
        self.assertEqual(tool_planning.validated_plan(state, copy.deepcopy(plan)), plan)
        # Search đúng loại, hoặc search không lọc loại, đã đủ: không thêm gì.
        for covering in (search(taxonomy='hotel'), search()):
            with self.subTest(covering=covering['args']):
                self.assertEqual(len(tool_planning.validated_plan(swap_state(), [similar('H1'), covering])), 2)
        # Mỗi loại đang đổi một search; loại người dùng đã loại trừ thì không search.
        two = tool_planning.validated_plan(swap_state(), [similar('H1'), similar('A1'), search(taxonomy='golf')])
        self.assertEqual([call['args'].get('taxonomy') for call in two[2:]], ['golf', 'hotel', 'attraction'])
        excluded = tool_planning.validated_plan(swap_state(constraints={'exclude_taxonomies': ['attraction']}),
                                                [similar('A1'), search(taxonomy='hotel')])
        self.assertEqual(names(excluded), ['get_similar_products', 'search_products'])
        # Similar nhường chỗ cho search của loại đang đổi; get_recommendations bắt buộc được xếp chỗ trước. Hết
        # chỗ mà không còn Similar để bỏ thì giữ plan như plan không có Similar, không huỷ lượt.
        others = [search(taxonomy='golf'), search(taxonomy='combo'), search(taxonomy='golf'), search(taxonomy='combo')]
        swapped = tool_planning.validated_plan(swap_state(), [similar('H1'), REC] + others[:3])
        self.assertEqual([call['args'].get('taxonomy') for call in swapped[1:]], ['golf', 'combo', 'golf', 'hotel'])
        full = tool_planning.validated_plan(swap_state(), [similar('H1')] + others, require_recommendations=True)
        self.assertEqual(names(full), ['search_products'] * 4 + ['get_recommendations'])
        self.assertEqual(tool_planning.validated_plan(swap_state(), copy.deepcopy(full), require_recommendations=True),
                         full)

    def test_similar_calls_over_the_call_budget_are_dropped_not_the_plan(self):
        raw = [similar('H1'), similar('A1'), search(taxonomy='hotel'), search(taxonomy='attraction'),
               search(taxonomy='golf'), REC]
        with self.assertLogs('uvicorn.error', level='WARNING') as logs:
            plan = tool_planning.validated_plan(swap_state(), raw)
        self.assertEqual(names(plan), ['get_similar_products'] + ['search_products'] * 3 + ['get_recommendations'])
        self.assertEqual(plan[0]['args']['productId'], 'H1')
        self.assertIn('reason=call_budget', logs.output[0])
        self.assertEqual(tool_planning.validated_plan(swap_state(), copy.deepcopy(plan)), plan)
        only = tool_planning.validated_plan(swap_state(), [similar('H1'), search(), search(taxonomy='attraction'),
                                                           search(taxonomy='golf'), search(taxonomy='combo'), REC])
        self.assertEqual(names(only), ['search_products'] * 4 + ['get_recommendations'])
        # Plan quá trần không vì Similar vẫn sai như trước khi có Similar.
        with self.assertRaises(ToolError) as caught:
            tool_planning.validated_plan(swap_state(), [search()] * 5 + [REC])
        self.assertEqual(caught.exception.code, 'INVALID_TOOL_PLAN')

    def test_dropped_similar_still_gets_the_safety_net_search(self):
        # Similar bị bỏ (anchor bịa, hoặc không được mời) không được làm lượt đổi món mất search mà Similar hợp lệ có.
        # Anchor bịa không cho biết loại nên search theo điểm đến; anchor thật (dù Similar không được mời) thì theo loại.
        for plan, offered, taxonomy in (([similar('X1'), REC], None, None),
                                        ([similar('H1'), REC], frozenset({'search_products', 'get_recommendations'}),
                                         'hotel')):
            with self.subTest(offered=offered):
                validated = tool_planning.validated_plan(swap_state(), plan, offered=offered)
                self.assertEqual(names(validated), ['get_recommendations', 'search_products'])
                self.assertEqual([call['id'] for call in validated], ['call-0', 'call-1'])
                self.assertEqual(validated[1]['args']['query'], 'Nha Trang')
                self.assertEqual(validated[1]['args'].get('taxonomy'), taxonomy)
        # Plan không có Similar giữ nguyên như trước; đã đủ 5 lời gọi mà không còn Similar để nhường chỗ thì sai.
        self.assertEqual(names(tool_planning.validated_plan(swap_state(), [REC])), ['get_recommendations'])
        with self.assertRaises(ToolError) as caught:
            tool_planning.validated_plan(swap_state(), [similar('X1')] + [REC] * 5)
        self.assertEqual(caught.exception.code, 'INVALID_TOOL_PLAN')

    def test_ids_are_contiguous_and_stable_when_a_stored_plan_is_revalidated(self):
        raw = [similar('X1'), similar('H1'), search(), similar('H1')]
        plan = tool_planning.validated_plan(swap_state(), raw, require_recommendations=True)
        self.assertEqual([call['id'] for call in plan], ['call-0', 'call-1', 'call-2'])
        self.assertEqual(names(plan), ['get_similar_products', 'search_products', 'get_recommendations'])
        self.assertEqual(tool_planning.validated_plan(swap_state(), copy.deepcopy(plan), require_recommendations=True),
                         plan)

    def test_offered_none_skips_only_the_not_offered_check(self):
        raw = [similar('H1'), search()]
        self.assertEqual(names(tool_planning.validated_plan(swap_state(), raw, offered=None)),
                         ['get_similar_products', 'search_products'])
        with self.assertLogs('uvicorn.error', level='WARNING') as logs:
            plan = tool_planning.validated_plan(swap_state(), raw,
                                                offered=frozenset({'search_products', 'get_recommendations'}))
        self.assertEqual(names(plan), ['search_products'])
        self.assertIn('reason=not_offered', logs.output[0])
        # "Không được mời" chỉ áp cho Similar: tool khác vẫn qua dù danh sách mời rỗng.
        self.assertEqual(names(tool_planning.validated_plan(swap_state(), [search()], offered=frozenset())),
                         ['search_products'])

    async def test_stored_plan_with_similar_reruns_without_definitions_or_the_llm(self):
        class Executor:  # không có definitions(): lần chạy lại plan đã lưu không được đọc danh sách tool
            def __init__(self):
                self.calls = []

            async def execute(self, call):
                self.calls.append((call['id'], call['name']))
                if call['name'] == 'get_similar_products':
                    data = {'productId': 'H1', 'strategy': 'same_taxonomy', 'results': [], 'requestId': 'r'}
                else:
                    data = {'results': [], 'total': 0}
                return {'tool_call_id': call['id'], 'data': data}

        def never(_definitions):
            raise AssertionError('plan đã lưu không được lập lại bằng LLM')

        stored = tool_planning.validated_plan(swap_state(), [similar('X1'), similar('H1'), search()])
        tools = Executor()
        result = await nodes.tool_node(swap_state(tool_plan=copy.deepcopy(stored)), tools=tools,
                                       llm=SimpleNamespace(bind_tools=never))
        self.assertEqual(result['tool_plan'], stored)
        self.assertEqual(tools.calls, [('call-0', 'get_similar_products'), ('call-1', 'search_products')])

    async def test_similar_is_offered_only_with_a_selection_and_a_similar_port(self):
        every = ('search_products', 'get_recommendations', 'get_similar_products')

        class Tools:
            def __init__(self, allowed):
                self.allowed = allowed

            def definitions(self):
                return [d for d in definitions() if d['name'] in self.allowed]

        for state, allowed, offered in ((swap_state(previous_selection=[]), every, False),
                                        (swap_state(), every[:2], False),
                                        (swap_state(), every, True)):
            bound, prompts = [], []

            def bind_tools(schemas):
                bound.append([d['name'] for d in schemas])

                async def invoke(messages):
                    prompts.append(messages)
                    return SimpleNamespace(tool_calls=[similar('H1'), search()])
                return SimpleNamespace(ainvoke=invoke)

            with self.subTest(selection=bool(state['previous_selection']), allowed=allowed):
                plan, error = await tool_planning.build_plan(
                    state, state['intent'], {}, tools=Tools(allowed), llm=SimpleNamespace(bind_tools=bind_tools),
                    llm_timeout_seconds=1, require_recommendations=False)
                self.assertIsNone(error)
                (system_role, system), (_, human) = prompts[0]
                payload = json.loads(human)
                if offered:
                    self.assertEqual(bound, [list(every)])
                    self.assertEqual(system, f'{TOOL_PLAN_PROMPT} {SIMILAR_HINT}')
                    self.assertEqual(payload['previous_selection'], SELECTION)
                    self.assertEqual(names(plan), ['get_similar_products', 'search_products'])
                else:
                    # Đúng bộ tool và prompt như trước khi có Similar; lời gọi Similar LLM tự bịa bị bỏ.
                    self.assertEqual(bound, [list(every[:2])])
                    self.assertEqual((system_role, system), ('system', TOOL_PLAN_PROMPT))
                    # Payload vẫn mang ngữ cảnh chung của mọi lượt gọi LLM (architecture §3), không thêm khoá nào.
                    self.assertEqual(set(payload), {'message', 'intent', 'constraints', *llm_context(state)})
                    self.assertEqual(payload['previous_selection'], state['previous_selection'])
                    self.assertEqual(names(plan), ['search_products'])


class SimilarEvaluationTests(unittest.TestCase):
    """Lỗi Similar là best-effort: 404/409 luôn mềm; 503/timeout mềm khi đã có search trả dữ liệu."""

    PRODUCT = {'productId': 'A2', 'name': 'Catalog A2', 'taxonomy': 'attraction', 'destination': 'Nha Trang',
               'unitPrice': 100000, 'currency': 'VND', 'priceUnit': 'PER_PERSON', 'available': True, 'score': 0.9,
               'description': 'Source text', 'attributes': {}, 'availableFrom': None, 'availableTo': None}

    def evaluate(self, error, *, search_result='data', tool='get_similar_products'):
        results = [{'tool_call_id': 'call-0', 'name': tool, 'error': error.as_dict()}]
        if search_result == 'data':
            results.append({'tool_call_id': 'call-1', 'name': 'search_products',
                            'data': {'results': [copy.deepcopy(self.PRODUCT)], 'total': 1}})
        elif search_result == 'error':
            results.append({'tool_call_id': 'call-1', 'name': 'search_products',
                            'error': ToolError('TOOL_HTTP_ERROR', retryable=True).as_dict()})
        return nodes.evaluate_node({'intent': {'destination': 'Nha Trang', 'days': 1}, 'constraints': {},
                                    'tool_results': results})

    def test_unavailable_similar_is_soft_when_search_returned_data(self):
        for error in (ToolError('TOOL_TIMEOUT', retryable=True),
                      ToolError('SEARCH_UNAVAILABLE', retryable=True, http_status=503),
                      # Mode http: engine lỗi bất ngờ thành 500 dạng text, hoặc không kết nối được route.
                      ToolError('INVALID_TOOL_RESPONSE', http_status=500),
                      ToolError('INTERNAL_ERROR', retryable=True, http_status=500),
                      ToolError('TOOL_HTTP_ERROR', retryable=True)):
            with self.subTest(code=error.code):
                evaluated = self.evaluate(error)
                self.assertEqual((evaluated['evaluation_result'], evaluated['decision']), ('success', 'compose'))
                self.assertEqual(routing.route_after_evaluate(evaluated), 'compose')
                self.assertEqual(evaluated['warnings'], [])

    def test_http_mode_similar_server_failure_is_soft_like_inprocess(self):
        # Route Similar ném lỗi bất ngờ ở mode http: Starlette trả 500 dạng text, không phải envelope 503.
        async def similar_error(response):
            async with httpx.AsyncClient(base_url='http://backend/api/v1/',
                                         transport=httpx.MockTransport(lambda request: response)) as http:
                with self.assertRaises(ToolError) as caught:
                    await ItineraryHttpClients(http).get_similar_products('H1', 20)
            return caught.exception

        for response in (httpx.Response(500, text='Internal Server Error'), httpx.Response(502, text='Bad Gateway')):
            with self.subTest(status=response.status_code):
                error = asyncio.run(similar_error(response))
                evaluated = self.evaluate(error)
                self.assertEqual((evaluated['evaluation_result'], evaluated['decision']), ('success', 'compose'))

    def test_unavailable_similar_without_search_data_still_retries(self):
        error = ToolError('SEARCH_UNAVAILABLE', retryable=True, http_status=503)
        for search_result in (None, 'error'):  # không gọi search, hoặc search cũng lỗi: chưa có lưới an toàn
            with self.subTest(search=search_result):
                evaluated = self.evaluate(error, search_result=search_result)
                self.assertEqual(evaluated['evaluation_result'], 'needs_retry')
                self.assertEqual(routing.route_after_evaluate(evaluated), 'retry')

    def test_no_alternative_from_similar_is_always_soft(self):
        for error in (ToolError('PRODUCT_NOT_INDEXED', http_status=409), ToolError('PRODUCT_NOT_FOUND', http_status=404)):
            with self.subTest(code=error.code):
                evaluated = self.evaluate(error)
                self.assertEqual((evaluated['evaluation_result'], evaluated['decision']), ('success', 'compose'))
                alone = self.evaluate(error, search_result=None)
                self.assertEqual((alone['evaluation_result'], alone['decision']), ('success', 'no_results'))

    def test_other_errors_keep_their_meaning(self):
        # Similar trả sai hợp đồng không phải "không có phương án": vẫn là lỗi vĩnh viễn → FALLBACK như trước.
        for error in (ToolError('INVALID_TOOL_RESPONSE'), ToolError('INVALID_TOOL_RESPONSE', http_status=200),
                      ToolError('TOOL_HTTP_ERROR', http_status=418)):
            with self.subTest(error=error.as_dict()):
                broken = self.evaluate(error)
                self.assertEqual((broken['evaluation_result'], broken['decision']), ('success', 'fallback'))
        # 5xx của Similar mà chưa có search trả dữ liệu thì chưa có lưới an toàn: giữ nghĩa cũ.
        alone = self.evaluate(ToolError('INVALID_TOOL_RESPONSE', http_status=500), search_result=None)
        self.assertEqual((alone['evaluation_result'], alone['decision']), ('failed', 'error'))
        # Quy tắc mềm chỉ dành cho Similar: search/recommendation timeout vẫn thử lại.
        rec = self.evaluate(ToolError('TOOL_TIMEOUT', retryable=True), tool='get_recommendations')
        self.assertEqual(rec['evaluation_result'], 'needs_retry')


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
        state = {'query': 'search hotel', 'attempt': 0, 'max_attempts': 3, 'start_date_asked': True,
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
