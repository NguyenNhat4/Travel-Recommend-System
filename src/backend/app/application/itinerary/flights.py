"""Tra chuyến bay cho chặng bay của lịch trình (AC-AGT-02) qua `CatalogPort.list_products`; chọn vé ở `domain/itinerary/flights.py`.

Không qua LLM planner: nơi đi, điểm đến và ngày đã đủ để tra tất định. Bốn lời gọi GET /products:
1. tuyến về điểm đến (`taxonomy=flight, destination=<điểm đến>`), lấy tuyến có `originCity` là nơi đi;
2. tuyến về nơi đi, lấy tuyến có `originCity` là điểm đến (chặng về);
3–4. chuyến của từng tuyến (`parentProductId`), gồm cả vé khứ hồi nằm dưới tuyến chiều đi.
Bộ lọc `destination` của GET /products so khớp chính xác, nên nơi đi được đưa về đúng tên catalog trước (alias như
"Sài Gòn" → "TP. Hồ Chí Minh", rồi `originCity` của tuyến khớp). Lỗi tra cứu không làm hỏng lượt: lịch trình vẫn dựng,
chỉ không có chặng bay và có cảnh báo.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from src.backend.app.application.ports.itinerary_tools import CatalogPort
from src.backend.app.domain.itinerary.flights import NO_ROUTE, UNAVAILABLE, skip_reason
from src.backend.app.domain.itinerary.normalization import fold
from src.backend.app.domain.search.lexical import fold as search_fold
from src.backend.app.domain.search.normalize import DESTINATION_ALIASES

logger = logging.getLogger("uvicorn.error")

PAGE = 50  # `Limit.maximum` của GET /products
MAX_PAGES = 4


def canonical_city(value: str) -> str:
    """Tên thành phố theo catalog khi là cách viết khác đã biết ("sg", "Sài Gòn"); không thì giữ nguyên."""
    return DESTINATION_ALIASES.get(search_fold(value), value)


async def _all(tools: CatalogPort, params: dict[str, Any], timeout_seconds: float) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for page in range(MAX_PAGES):
        data = await asyncio.wait_for(tools.list_products({**params, "limit": PAGE, "offset": page * PAGE}),
                                      timeout_seconds)
        results.extend(data["results"])
        if len(results) >= data["total"] or not data["results"]:
            break
    return results


def _route_from(routes: list[dict[str, Any]], city: str) -> dict[str, Any] | None:
    key = fold(city)
    return next((route for route in routes if fold((route.get("attributes") or {}).get("originCity")) == key), None)


async def flight_options(tools: CatalogPort | None, intent: dict[str, Any], constraints: dict[str, Any],
                         timeout_seconds: float, request_id: str = "unknown", *, notify=None, counts=None) -> dict[str, Any]:
    """`{"status": lý do | None, "origin": tên catalog, "outbound": [...], "return": [...]}` cho `choose_flights`."""
    reason = skip_reason(intent, constraints)
    if reason is not None:
        return {"status": reason}
    if tools is None or not hasattr(tools, "list_products") or not getattr(tools, "supports_catalog", False):
        return {"status": UNAVAILABLE}
    origin, destination = canonical_city(intent["origin"]), intent["destination"]
    if notify:
        notify("SEARCHING_FLIGHTS", origin=origin, destination=destination, date=intent.get("startDate"))
    try:
        to_destination = await _all(tools, {"taxonomy": "flight", "destination": destination}, timeout_seconds)
        going = _route_from(to_destination, origin)
        if going is not None:
            origin = going["attributes"]["originCity"]
        to_origin = await _all(tools, {"taxonomy": "flight", "destination": origin}, timeout_seconds)
        coming = _route_from(to_origin, destination)
        if going is None and coming is None:
            return {"status": NO_ROUTE, "origin": origin}
        outbound, inbound = await asyncio.gather(*(
            _all(tools, {"parentProductId": route["productId"], "availableOnly": True}, timeout_seconds)
            if route is not None else asyncio.sleep(0, result=[]) for route in (going, coming)))
    except Exception as exc:  # ToolError, timeout, schema: chỉ mất chặng bay, không mất lượt
        logger.warning("itinerary.flights.unavailable requestId=%s reason=%s", request_id,
                       getattr(exc, "code", type(exc).__name__))
        return {"status": UNAVAILABLE}
    if counts is not None:
        from src.backend.app.domain.itinerary import flights as rules
        dates = rules.trip_dates(intent)
        for pool, day in ((outbound, dates[0] if dates else None), (inbound, dates[1] if dates else None)):
            for p in pool:
                reason = ('PRODUCT_DROPPED_UNAVAILABLE' if not rules._bookable(p) else
                          'PRODUCT_DROPPED_DATE' if rules.flight_date(p)!=day or (rules._is_round_trip(p) and dates and rules._return_date(p)!=dates[1]) else None)
                counts.record(p['productId'], reason)
    return {"status": None, "origin": origin, "outbound": outbound, "return": inbound}
