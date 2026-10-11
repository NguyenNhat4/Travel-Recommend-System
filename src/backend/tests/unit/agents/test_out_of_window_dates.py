"""Ngày đi ngoài cửa sổ mở bán: không bao giờ chỉ nói "không có sản phẩm" (chat thử 10/10, lỗi H).

"khởi hành 12/11, ngân sách 15 triệu, từ Đà Nẵng" từng ra NO_RESULTS "Chưa có sản phẩm mở bán cho ngày này". Nay: lịch
tham khảo từ các điểm tham quan nổi tiếng (điểm có vé gắn cờ chưa mở bán, không tính là đặt được), câu mở đầu do code viết
nêu ngày và ngày gần nhất còn bán. Grounding giữ nguyên: mọi thẻ vẫn là sản phẩm Search.
"""
import unittest

from src.backend.app.application.itinerary.retrieval import NOT_ON_SALE, collect, reference_only

from . import test_itinerary_runtime as runtime
from .test_itinerary_runtime import Clients, ScriptedLlm, extracted, product

WINDOW = {'availableFrom': '2999-10-01', 'availableTo': '2999-10-24'}
INTENT = {'destination': 'Nha Trang', 'startDate': '2999-12-01', 'days': 2}


def _result(*products):
    return [{'name': 'search_products', 'data': {'results': list(products)}}]


class ReferenceRuleTests(unittest.TestCase):
    def test_a_sight_only_out_of_window_is_kept_with_a_flag_and_a_hotel_is_dropped(self):
        candidates, _, dropped = collect(_result(product('sight', **WINDOW), product('hotel', taxonomy='hotel', **WINDOW)),
                                         {}, INTENT, {})
        self.assertTrue(candidates['sight'][NOT_ON_SALE])
        self.assertEqual(dropped, {'hotel': 'PRODUCT_DROPPED_DATE'})

    def test_flagged_sights_are_dropped_again_when_the_date_has_sights_on_sale(self):
        open_sight = product('open', availableFrom='2999-11-25', availableTo='2999-12-20')
        candidates, _, dropped = collect(_result(product('sight', **WINDOW), open_sight), {}, INTENT, {})
        kept = reference_only(candidates, dropped)
        self.assertEqual(set(kept), {'open'})
        self.assertEqual(dropped['sight'], 'PRODUCT_DROPPED_DATE')

    def test_the_reference_plan_keeps_the_most_reviewed_places(self):
        products = [product(f'p{index}', reviewCount=index, **WINDOW) for index in range(12)]
        products.append(product('ticket', **WINDOW))  # vé lẻ không ai đánh giá
        candidates, _, dropped = collect(_result(*products), {}, INTENT, {})
        kept = reference_only(candidates, dropped)
        self.assertEqual(set(kept), {f'p{index}' for index in range(4, 12)})
        self.assertEqual(dropped['ticket'], 'PRODUCT_DROPPED_DATE')

    def test_another_reason_still_drops_the_sight(self):
        candidates, _, dropped = collect(_result(product('far', destination='Huế', **WINDOW)), {}, INTENT, {})
        self.assertEqual(candidates, {})
        self.assertEqual(dropped['far'], 'PRODUCT_DROPPED_DESTINATION')


class ReferencePlanFlowTests(unittest.IsolatedAsyncioTestCase):
    run_graph = runtime.RuntimeTests.run_graph

    async def test_out_of_window_date_gets_a_reference_plan_not_no_results(self):
        free = product('ho', unitPrice=None, attributes={'ticketed': False}, **WINDOW)
        paid = product('show', unitPrice=300_000, **WINDOW)
        hotel = product('ks', taxonomy='hotel', **WINDOW)
        clients = Clients(products=[free, paid, hotel], destinations=['Nha Trang'])
        llm = ScriptedLlm(extraction=extracted(destination='Nha Trang', days=2, startDate='2999-12-01'))
        result = await self.run_graph(llm, clients)
        response = result['response']
        self.assertEqual(response['status'], 'COMPLETED')
        scheduled = {slot['product']['productId'] for day in response['itinerary']['days'] for slot in day['slots']
                     if slot['product']}
        self.assertLessEqual(scheduled, {'ho', 'show'})
        self.assertIn('show', scheduled)
        codes = [(w['code'], w.get('productId')) for w in response['warnings']]
        self.assertIn(('PRODUCT_NOT_ON_SALE_FOR_DATE', 'show'), codes)
        self.assertNotIn(('PRODUCT_NOT_ON_SALE_FOR_DATE', 'ho'), codes)  # tự do: không có vé để mở bán
        # Điểm có vé chưa mở bán không được đếm (`planning` vẫn đếm điểm tự do như trước, ngoài phạm vi thay đổi này).
        self.assertEqual(response['itinerary']['bookableCount'], len(scheduled - {'show'}))
        message = response['message']
        self.assertIn('Mình chưa tìm thấy vé mở bán cho ngày 01/12/2999', message)
        self.assertIn('đang mở bán đến 24/10/2999', message)
        # Ngày đi chung: chuyến 2 ngày phải về trước khi hết cửa sổ bán (24/10), và mục khách sạn nói cùng ngày đó.
        self.assertIn('Đi Nha Trang 2 ngày từ ngày 23/10/2999', message)
        self.assertIn('dời ngày khởi hành sang 23/10/2999', message)
        self.assertNotIn('Chưa có sản phẩm mở bán', message)
        self.assertEqual(result['validation_issues'], [])
        # LLM kể chuyện từng nơi của lịch tham khảo từ mô tả catalog.
        self.assertIn('reference_only: true', llm.prompts['ItineraryNarration'])
        self.assertIn('about:', llm.prompts['ItineraryNarration'])

    async def test_without_any_sight_the_answer_is_still_no_results_with_the_nearest_date(self):
        clients = Clients(products=[product('ks', taxonomy='hotel', **WINDOW)], destinations=['Nha Trang'])
        llm = ScriptedLlm(extraction=extracted(destination='Nha Trang', days=2, startDate='2999-12-01'))
        response = (await self.run_graph(llm, clients))['response']
        self.assertEqual(response['status'], 'NO_RESULTS')
        self.assertIn('Đi Nha Trang 2 ngày từ ngày 24/10/2999', response['suggestions'])


if __name__ == '__main__':
    unittest.main()
