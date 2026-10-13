"""Danh sách điểm đến cho system prompt orc v2: lấy từ catalog, cache theo TTL, lỗi thì dùng bản cũ hoặc None."""
import asyncio

from src.backend.app.application.itinerary.destination_names import DestinationNames


class Catalog:
    def __init__(self, *responses):
        self.responses, self.calls = list(responses), 0

    async def list_destinations(self):
        self.calls += 1
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return {"destinations": [{"destination": name, "productCount": 1} for name in response]}


def test_names_are_cached_until_ttl_then_refreshed():
    now = [0.0]
    names = DestinationNames(ttl_seconds=600, clock=lambda: now[0])
    catalog = Catalog(["Phú Quốc", "TP. Hồ Chí Minh"], ["Đà Lạt"])
    assert asyncio.run(names.get(catalog)) == ["Phú Quốc", "TP. Hồ Chí Minh"]
    now[0] = 599
    assert asyncio.run(names.get(catalog)) == ["Phú Quốc", "TP. Hồ Chí Minh"] and catalog.calls == 1
    now[0] = 601
    assert asyncio.run(names.get(catalog)) == ["Đà Lạt"] and catalog.calls == 2


def test_failure_keeps_stale_names_and_backs_off_or_returns_none():
    assert asyncio.run(DestinationNames().get(Catalog(ConnectionError()))) is None
    now = [0.0]
    names = DestinationNames(ttl_seconds=10, clock=lambda: now[0])
    catalog = Catalog(["Huế"], ConnectionError(), ["Hội An"])
    asyncio.run(names.get(catalog))
    now[0] = 11
    assert asyncio.run(names.get(catalog)) == ["Huế"]
    now[0] = 15
    assert asyncio.run(names.get(catalog)) == ["Huế"] and catalog.calls == 2
