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
