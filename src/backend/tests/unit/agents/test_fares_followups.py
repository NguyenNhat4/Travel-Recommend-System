"""Câu hỏi vé: hỏi lại khi mơ hồ, nhớ ngữ cảnh giá vé, đắt nhất/rẻ nhất, đã có lịch (chat thử 10/10, lỗi C–F).

- "giờ tao đi hà nội thì vé nào rẻ" từng lập lịch luôn thay vì hỏi vé gì.
- "tao hỏi vé máy bay mà" từng đi LLM và lại lập lịch.
- "giá máy bay đó rẻ nhất chưa" chỉ báo ngày đã chọn; "đắt nhất thì soa" lập lại cả lịch.
- Đang hỏi vé, "đi đâu cũng được, miễn đắt nhất" từng chuyển sang khám phá Nha Trang.

`classify` (LLM) hiểu câu và đọc ra các trường của `FareQuestion`; test giả lập phần đó (`fare_llm`).
"""
import unittest
from datetime import date

from src.backend.app.agents.steps import fares
from src.backend.app.infrastructure.persistence.conversation_store import InMemoryConversationStore

from . import test_itinerary_runtime as runtime
from .test_fares import fare_llm
from .test_itinerary_runtime import START, FlightClients, flight_product, product

NEXT_DAY = START[:8] + f'{int(START[8:10]) + 1:02d}'
TODAY = date(2999, 10, 1)


class MoreFlights(FlightClients):
    """Thêm chuyến Hà Nội → Nha Trang ngày sau, và tuyến Hà Nội → Phú Quốc, để so rẻ/đắt."""

    def __init__(self, **kwargs):
        super().__init__(destinations=['Nha Trang', 'Hà Nội', 'Phú Quốc'], **kwargs)
        self.routes.append(product('r-pq', taxonomy='flight', destination='Phú Quốc', unitPrice=None,
                                   attributes={'level': 'route', 'originCity': 'Hà Nội'}))
        self.flights += [flight_product('VJ3', 'Nha Trang', NEXT_DAY, 700_000, parent='r-out', clock='06:00'),
                         flight_product('VN9', 'Nha Trang', START, 2_500_000, parent='r-out', clock='12:00'),
                         flight_product('QH5', 'Phú Quốc', START, 3_200_000, parent='r-pq', clock='09:00')]


class AnswerTextTests(unittest.TestCase):
    def setUp(self):
        self.flights = [item for item in MoreFlights().flights if item['attributes']['parentProductId'] == 'r-out']

    def test_cheapest_on_the_chosen_day_is_compared_with_the_whole_window(self):
        state = {'intent': {'startDate': START}}
        _, body, shown = fares.answer_text(state, 'Hà Nội', 'Nha Trang', self.flights, TODAY)
        self.assertIn(f'Ngày {START[8:10]}/{START[5:7]} có 2 chuyến Hà Nội → Nha Trang còn vé; rẻ nhất 1.000.000 ₫', body)
        self.assertIn(f'rẻ nhất là 700.000 ₫/khách, bay ngày {NEXT_DAY[8:10]}/{NEXT_DAY[5:7]}', body)
        # Thẻ: các chuyến của ngày hỏi (rẻ trước) rồi chuyến rẻ nhất cả đợt.
        self.assertEqual([item['productId'] for item in shown], ['VJ1', 'VN9', 'VJ3'])

    def test_dearest(self):
        _, body, shown = fares.answer_text({'intent': {}}, 'Hà Nội', 'Nha Trang', self.flights, TODAY, fares.DEAREST)
        self.assertIn('đắt nhất mình thấy là 2.500.000 ₫/khách', body)
        self.assertIn('[VietJet Air VN9](product:VN9)', body)
        self.assertEqual(shown[0]['productId'], 'VN9')

    def test_a_chosen_day_without_flights_names_the_nearest_days_and_the_best_day(self):
        state = {'intent': {'startDate': '2999-10-20'}}
        _, body, shown = fares.answer_text(state, 'Hà Nội', 'Nha Trang', self.flights, TODAY)
        self.assertIn('Ngày 20/10 chưa có chuyến còn vé', body)
        self.assertIn('Ngày gần nhất có chuyến: 10/10 từ 1.000.000 ₫, 11/10 từ 700.000 ₫', body)
        self.assertIn('rẻ nhất là 700.000 ₫', body)
        self.assertEqual({item['productId'] for item in shown}, {'VJ1', 'VJ3'})

    def test_the_other_days_are_cards_not_a_line_of_prices(self):
        _, body, shown = fares.answer_text({'intent': {}}, 'Hà Nội', 'Nha Trang', self.flights, TODAY)
        self.assertNotIn('Ngày khác:', body)
        self.assertEqual([item['productId'] for item in shown], ['VJ3', 'VJ1'])

    def test_a_time_of_day_keeps_only_flights_in_that_window(self):
        _, body, shown = fares.answer_text({'intent': {}}, 'Hà Nội', 'Nha Trang', self.flights, TODAY,
                                           period='afternoon')
        self.assertIn('Hà Nội → Nha Trang buổi chiều (12:00–18:00) rẻ nhất mình thấy là 2.500.000 ₫', body)
        self.assertEqual([item['productId'] for item in shown], ['VN9'])

    def test_no_flight_in_the_window_says_so_and_uses_every_time(self):
        _, body, _ = fares.answer_text({'intent': {}}, 'Hà Nội', 'Nha Trang', self.flights, TODAY, period='evening')
        self.assertIn('chưa có chuyến buổi tối (sau 18:00) nào còn vé', body)
        self.assertIn('rẻ nhất mình thấy là 700.000 ₫', body)

    def test_availability_lists_the_sale_window_and_the_days_without_flights(self):
        flights = self.flights + [flight_product('VJ7', 'Nha Trang', '2999-10-14', 800_000, parent='r-out')]
        _, body, _ = fares.answer_text({'intent': {}}, 'Hà Nội', 'Nha Trang', flights, TODAY, availability=True)
        self.assertIn('đang mở bán từ 10/10 đến 14/10; có chuyến 3/5 ngày', body)
        self.assertIn('Các ngày chưa có chuyến: 12/10, 13/10.', body)

    def test_why_explains_from_the_data_only_and_shows_the_flight(self):
        pending = {'shown': ['VN9'], 'kind': fares.DEAREST}
        title, body, shown = fares.why_text({}, 'Hà Nội', 'Nha Trang', self.flights, TODAY, pending)
        self.assertIn('không khẳng định được hãng định giá vì sao', body)
        self.assertIn('2.500.000 ₫/khách, gấp 4 lần vé rẻ nhất của tuyến (700.000 ₫)', body)
        self.assertIn('Bạn bấm vào vé bên dưới', body)
        self.assertEqual([item['productId'] for item in shown], ['VN9'])

    def test_illustrative_business_fares_are_left_out_while_real_fares_exist(self):
        business = flight_product('BIZ', 'Nha Trang', START, 9_000_000, parent='r-out')
        business['attributes'].update(cabinClass='BUSINESS', simulated=True)
        _, body, shown = fares.answer_text({'intent': {}}, 'Hà Nội', 'Nha Trang', self.flights + [business], TODAY,
                                           fares.DEAREST)
        self.assertIn('đắt nhất mình thấy là 2.500.000 ₫', body)
        self.assertNotIn('BIZ', [item['productId'] for item in shown])

    def test_why_names_the_cabin_and_the_illustrative_price(self):
        business = flight_product('BIZ', 'Nha Trang', START, 9_000_000, parent='r-out')
        business['attributes'].update(cabinClass='BUSINESS', simulated=True)
        cheap = [dict(item, attributes={**item['attributes'], 'cabinClass': 'ECONOMY', 'simulated': True})
                 for item in self.flights]
        _, body, _ = fares.why_text({}, 'Hà Nội', 'Nha Trang', cheap + [business], TODAY, {'shown': ['BIZ']})
        self.assertIn('Vé này là hạng Thương gia, còn vé rẻ nhất tuyến là hạng Phổ thông.', body)
        self.assertIn('giá minh hoạ trong dữ liệu', body)
        self.assertIn('[VietJet Air BIZ](product:BIZ) hạng Thương gia', body)


class FollowUpFlowTests(unittest.IsolatedAsyncioTestCase):
    run_graph = runtime.RuntimeTests.run_graph

    async def turn(self, clients, store, query, conversation=None, llm=None):
        return await self.run_graph(llm or fare_llm(), clients, store=store, owner='u',
                                    state={'query': query, **({'conversation_id': conversation} if conversation else {})})

    async def test_a_vague_ticket_question_asks_which_ticket_then_flights_ask_the_origin(self):
        clients, store = MoreFlights(), InMemoryConversationStore()
        first = await self.turn(clients, store, 'giờ tao đi Nha Trang thì vé nào rẻ', llm=fare_llm(destination='Nha Trang', kind_unclear=True))
        response = first['response']
        self.assertIn('vé máy bay ra Nha Trang, phòng khách sạn hay vé tham quan', response['question'])
        self.assertEqual(response['suggestions'], ['Vé máy bay ra Nha Trang rẻ nhất', 'Khách sạn giá rẻ ở Nha Trang',
                                                   'Giá vé tham quan ở Nha Trang'])
        self.assertNotIn('itinerary', response)
        second = await self.turn(clients, store, 'tao hỏi vé máy bay mà', first['conversation_id'])
        self.assertIn('Bạn bay từ đâu ra Nha Trang?', second['response']['question'])
        third = await self.turn(clients, store, 'Hà Nội', first['conversation_id'], fare_llm(origin='Hà Nội'))
        self.assertIn('rẻ nhất mình thấy là 700.000 ₫', third['response']['question'])

    async def test_dearest_after_a_fare_answer_is_answered_without_planning(self):
        clients, store = MoreFlights(), InMemoryConversationStore()
        first = await self.turn(clients, store, 'vé từ Hà Nội ra Nha Trang giá bao nhiêu',
                                llm=fare_llm(origin='Hà Nội', destination='Nha Trang'))
        self.assertIn('Đắt nhất thì sao?', first['response']['suggestions'])
        second = await self.turn(clients, store, 'đắt nhất thì soa', first['conversation_id'], fare_llm(dearest=True))
        self.assertIn('đắt nhất mình thấy là 2.500.000 ₫', second['response']['question'])
        nodes = [item['node'] for item in second['events']]
        self.assertNotIn('compose', nodes)
        self.assertNotIn('tool', nodes)

    async def test_anywhere_while_asking_fares_compares_routes_from_the_origin(self):
        clients, store = MoreFlights(), InMemoryConversationStore()
        first = await self.turn(clients, store, 'vé từ Hà Nội ra Nha Trang giá bao nhiêu',
                                llm=fare_llm(origin='Hà Nội', destination='Nha Trang'))
        second = await self.turn(clients, store, 'đi đâu cũng được, miễn đắt nhất', first['conversation_id'],
                                 fare_llm(anywhere=True, dearest=True))
        question = second['response']['question']
        self.assertIn('Từ Hà Nội, vé một chiều đắt nhất mình thấy là đi Phú Quốc: 3.200.000 ₫', question)
        self.assertIn('Nha Trang 2.500.000 ₫', question)
        self.assertIn('Phú Quốc có gì chơi?', second['response']['suggestions'])

    async def test_anywhere_without_an_origin_asks_where_from(self):
        clients, store = MoreFlights(), InMemoryConversationStore()
        first = await self.turn(clients, store, 'vé máy bay bao nhiêu vậy?')
        second = await self.turn(clients, store, 'đi đâu cũng được miễn rẻ nhất', first['conversation_id'],
                                 fare_llm(anywhere=True))
        self.assertIn('Bạn bay từ đâu?', second['response']['question'])
        third = await self.turn(clients, store, 'Hà Nội', first['conversation_id'], fare_llm(origin='Hà Nội'))
        self.assertIn('Từ Hà Nội, vé một chiều rẻ nhất mình thấy là đi Nha Trang: 700.000 ₫', third['response']['question'])

    async def test_a_fare_question_after_an_itinerary_keeps_the_itinerary_and_its_intent(self):
        clients, store = MoreFlights(), InMemoryConversationStore()
        plan = {'itinerary': {'days': []}, 'searchResults': {}}
        intent = {'destination': 'Nha Trang', 'origin': 'Hà Nội', 'startDate': START, 'days': 3,
                  'party': {'type': 'COUPLE', 'adults': 2, 'children': 0}, 'budget': None, 'interests': [],
                  'pace': None}
        await store.save('c-plan', {'intent': intent, 'previous_plan': plan, 'plan_consent': True}, 'u')
        result = await self.turn(clients, store, 'giá máy báy đó rẻ nhất chưa', 'c-plan')  # LLM: hỏi vé, không nêu nơi
        question = result['response']['question']
        self.assertIn('rẻ nhất 1.000.000 ₫', question)
        self.assertIn('rẻ nhất là 700.000 ₫/khách', question)
        self.assertNotIn('compose', [item['node'] for item in result['events']])
        saved = await store.load('c-plan', 'u')
        self.assertEqual(saved['previous_plan'], plan)


if __name__ == '__main__':
    unittest.main()
