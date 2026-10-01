import asyncio
import tempfile
import unittest
from pathlib import Path

from collectors.common import Paths, StateDB
from collectors.plan import DESTINATIONS
from collectors.trip import TripFlights, TripOptions

# Trang sân bay của Trip liệt kê tuyến bằng mã THÀNH PHỐ của Trip: Nha Trang là "nha" (sân bay CXR), không phải "cxr".
PAGES = {
    "airport-cxr": "/flights/nha-trang-to-ho-chi-minh-city/airfares-nha-sgn/ /flights/nha-trang-to-hanoi/airfares-nha-han/",
    "airport-sgn": "/flights/ho-chi-minh-city-to-nha-trang/airfares-sgn-nha/ /flights/ho-chi-minh-city-to-hanoi/airfares-sgn-han/",
    "airport-han": "/flights/hanoi-to-nha-trang/airfares-han-nha/ /flights/hanoi-to-ho-chi-minh-city/airfares-han-sgn/",
}


class FakeTrip(TripFlights):
    fetched: list

    async def cached_page(self, key, url):
        self.fetched.append(key)
        return PAGES.get(key)


def discover(routes):
    with tempfile.TemporaryDirectory() as tmp:
        paths = Paths(Path(tmp)).ensure()
        state = StateDB(paths)
        crawler = FakeTrip(paths, TripOptions(routes=routes, destinations=DESTINATIONS), state)
        crawler.fetched = []
        found = asyncio.run(crawler.discover())
        urls = sorted(u.rsplit("/airfares-", 1)[1].strip("/") for u in crawler.discovered_urls)
        asyncio.run(crawler.close())
        state.close()
        return found, urls, crawler.fetched


class TripRouteDiscoveryTests(unittest.TestCase):
    def test_routes_use_iata_pairs_even_when_trip_city_code_differs(self):
        found, urls, fetched = discover((("CXR", "SGN"), ("HAN", "CXR")))
        self.assertEqual(urls, ["han-nha", "nha-sgn"])  # Nha Trang không bị bỏ sót vì "nha" != "CXR"
        self.assertEqual(found, 2)
        self.assertEqual(sorted(fetched), ["airport-cxr", "airport-han", "airport-sgn"])  # chỉ tải sân bay có trong --routes

    def test_only_airports_named_in_routes_are_fetched(self):
        _, urls, fetched = discover((("SGN", "HAN"),))
        self.assertEqual(urls, ["sgn-han"])
        self.assertEqual(sorted(fetched), ["airport-han", "airport-sgn"])

    def test_without_routes_every_route_between_fetched_airports_is_kept(self):
        _, urls, _ = discover(())
        self.assertEqual(urls, ["han-nha", "han-sgn", "nha-han", "nha-sgn", "sgn-han", "sgn-nha"])


if __name__ == "__main__":
    unittest.main()


# Hạng vé khứ hồi: thẻ khứ hồi trên trang tuyến ghi hạng từng chặng; JSON-LD không có. Trang tổng hợp dạng thật (29/09/2026).
ROUTE_URL = "https://vn.trip.com/flights/hanoi-to-ho-chi-minh-city/airfares-han-sgn/"


def _flight(node_id, number, dep, arr, when, until, price=None):
    node = {"@type": "Flight", "@id": f"{ROUTE_URL}#{node_id}", "flightNumber": number,
            "provider": {"name": "VietJet Air", "iataCode": "VJ"},
            "departureAirport": {"iataCode": dep}, "arrivalAirport": {"iataCode": arr},
            "departureTime": when, "arrivalTime": until}
    if price:
        node["offers"] = {"price": price, "priceCurrency": "VND", "priceValidUntil": "2026-09-30"}
    return node


def route_html(cards, wrapper=False):
    import json as _json
    graph = [{"@type": "Product", "name": "Vé máy bay Hà Nội TP. Hồ Chí Minh",
              "itinerary": [{"name": "Hà Nội"}, {"name": "TP. Hồ Chí Minh"}]},
             _flight("rt-out-vj165-1", "VJ165", "HAN", "SGN", "2026-10-31T14:25:00.000Z", "2026-10-31T16:35:00.000Z", 1539000),
             _flight("rt-in-vj164-1", "VJ164", "SGN", "HAN", "2026-11-05T13:40:00.000Z", "2026-11-05T15:50:00.000Z"),
             _flight("rt-out-vj161-2", "VJ161", "HAN", "SGN", "2026-11-03T11:35:00.000Z", "2026-11-03T13:45:00.000Z", 1600000),
             _flight("rt-in-vj124-2", "VJ124", "SGN", "HAN", "2026-11-10T05:20:00.000Z", "2026-11-10T07:30:00.000Z")]
    html = [f'<script type="application/ld+json">{_json.dumps({"@graph": graph})}</script>']
    body = []
    for out_date, back_date, cabins in cards:
        body.append('<div class="_flightcard-comfort-card"><span test-item="flightcard_depcode_rt_to">HAN</span>'
                    f'<span test-item="flightcard_date_rt_to">{out_date}</span>'
                    f'<span test-item="flightcard_date_rt_return">{back_date}</span>'
                    + "".join(f'<div class="_flightcard-comfort-cabin">{c}</div>' for c in cabins)
                    + '<span test-item="flightcard_saleprice_rt">1.539.000₫</span></div>')
    if wrapper:  # khối gom mọi thẻ (có trên trang thật) không được tính là một thẻ
        body = ['<section><span test-item="flightcard_depcode_rt_to">HAN</span>' + "".join(body)
                + '<span test-item="flightcard_saleprice_rt">x</span></section>']
    return "<html><body>" + "".join(html + body) + "</body></html>"


def cabins_of(html):
    from collectors.trip import TripFlights, parse_route
    payload = TripFlights.extract(None, html)
    legs = parse_route(payload, ROUTE_URL)["roundTripLegs"]
    return [(leg["flightNumber"], leg.get("cabinClass")) for leg in legs]


ECO_CARDS = [("T7, 31 thg 10", "T5, 5 thg 11", ["Economy class", "Economy class"]),
             ("T3, 3 thg 11", "T3, 10 thg 11", ["Economy class", "Economy class"])]


class TripRoundTripCabinTests(unittest.TestCase):
    def test_cards_matching_every_pair_set_each_leg_cabin(self):
        self.assertEqual(cabins_of(route_html(ECO_CARDS)),
                         [("VJ165", "ECONOMY"), ("VJ164", "ECONOMY"), ("VJ161", "ECONOMY"), ("VJ124", "ECONOMY")])
        business = [ECO_CARDS[0], ("T3, 3 thg 11", "T3, 10 thg 11", ["Business class", "Thương gia"])]
        self.assertEqual([c for _, c in cabins_of(route_html(business))], ["ECONOMY", "ECONOMY", "BUSINESS", "BUSINESS"])

    def test_wrapper_block_holding_all_cards_is_ignored(self):
        self.assertEqual({c for _, c in cabins_of(route_html(ECO_CARDS, wrapper=True))}, {"ECONOMY"})

    def test_card_count_or_date_mismatch_leaves_every_cabin_unknown(self):
        for cards in (ECO_CARDS[:1],                                                         # thiếu thẻ
                      [ECO_CARDS[0], ("T3, 3 thg 11", "T4, 11 thg 11", ["Economy class"] * 2)]):  # lệch ngày về
            self.assertEqual({c for _, c in cabins_of(route_html(cards))}, {None}, cards)

    def test_unreadable_or_mixed_cabin_leaves_only_that_pair_unknown(self):
        for cabins in (["", "Economy class"],                     # trang thật: có thẻ trống hạng một chặng
                       ["Economy class"],                         # thiếu một chặng
                       ["Ghế rộng", "Ghế rộng"],                  # không đọc được
                       ["Economy class", "Business class", "Economy class"]):  # nối chặng, lẫn hạng
            cards = [ECO_CARDS[0], ("T3, 3 thg 11", "T3, 10 thg 11", cabins)]
            self.assertEqual([c for _, c in cabins_of(route_html(cards))], ["ECONOMY", "ECONOMY", None, None], cabins)

    def test_connecting_legs_with_one_cabin_throughout_get_that_cabin(self):
        cards = [ECO_CARDS[0], ("T3, 3 thg 11", "T3, 10 thg 11", ["Economy class"] * 3)]
        self.assertEqual({c for _, c in cabins_of(route_html(cards))}, {"ECONOMY"})

    def test_normalised_round_trip_gets_economy_fare(self):
        import normalise as n
        from collectors.trip import TripFlights, parse_route
        record = parse_route(TripFlights.extract(None, route_html(ECO_CARDS)), ROUTE_URL)
        route = {"productId": "R", "destination": "TP. Hồ Chí Minh", "attributes": {"originCity": "Hà Nội"}}
        products = n.trip_roundtrip_products({**record, "crawledAt": "2026-09-30T00:00:00Z"}, route)
        self.assertEqual([p["attributes"]["cabinClass"] for p in products], ["ECONOMY", "ECONOMY"])
        self.assertTrue(products[0]["sourceRef"].endswith(":ECONOMY"))
