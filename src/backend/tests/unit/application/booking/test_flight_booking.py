"""Dated cabin variants use the existing productId-based cart and checkout contract."""
import asyncio
from datetime import date

import pytest
from src.backend.app.application.booking import Contact
from src.backend.app.application.booking.errors import LineRejected
from src.backend.tests.fakes.booking import HOTEL, TICKET, PRINCIPAL, World, product


def test_roundtrip_cabins_remain_distinct_through_cart_payment_and_purchase():
    async def go():
        day = date(2026, 10, 10)
        common = dict(level='flight', tripType='roundTrip', fixedDepartureDate=True,
                      departureAt='2026-10-10T08:00:00+07:00', returnDate='2026-10-13',
                      returnFlight={'flightNumber': 'VN101', 'departureAt': '2026-10-13T08:00:00+07:00'})
        eco = product(HOTEL, 'flight', price=2400000, available_from=day, available_to=day,
                      attributes={**common, 'cabinClass': 'ECONOMY'})
        biz = product(TICKET, 'flight', price=5200000, available_from=day, available_to=day,
                      attributes={**common, 'cabinClass': 'BUSINESS'})
        w = World(products=[eco, biz])
        with pytest.raises(LineRejected) as exc:
            await w.cart.add(PRINCIPAL, product_id=HOTEL, using_date=date(2026, 10, 13), quantity=1, nights=None)
        assert exc.value.code == 'DATE_OUT_OF_RANGE'
        await w.cart.add(PRINCIPAL, product_id=HOTEL, using_date=day, quantity=2, nights=3)
        cart = await w.cart.add(PRINCIPAL, product_id=TICKET, using_date=day, quantity=1, nights=None)
        assert cart['itemCount'] == 2
        assert cart['total'] == 2400000 * 2 + 5200000  # no multiplication by stayDays/nights
        assert all(line['nights'] is None for line in cart['items'])
        held = await w.create(PRINCIPAL, Contact('Test Guest', 'test@example.vn', '0901234567'), await w.details())
        assert held['payment']['amount'] == cart['total']
        ref = held['referenceCode']
        await w.handler(w.gateway.pay(w.booking(ref).payment.checkout_session_id))
        shown = await w.get(PRINCIPAL, ref)
        assert shown['status'] == 'CONFIRMED'
        items = [item for group in shown['groups'] for item in group['items']]
        assert {item['product']['productId'] for item in items} == {HOTEL, TICKET}
        assert {item['product']['attributes']['cabinClass'] for item in items} == {'ECONOMY', 'BUSINESS'}
        assert all(item['nights'] is None and item['product']['attributes']['returnDate'] == '2026-10-13' for item in items)
        assert len(w.cdp.recorded) == 1
    asyncio.run(go())
