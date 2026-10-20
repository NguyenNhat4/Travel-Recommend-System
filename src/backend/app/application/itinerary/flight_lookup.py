"""Tool lookup_flights của assistant v2: chuyến bay một chiều của một tuyến trong cả đợt mở bán (AC-AGT-08).

Không soạn câu trả lời và không chọn vé thay orc. Đọc hết các trang chuyến của tuyến (tối đa `MAX_PAGES`, mỗi trang
tốn một suất ngân sách) để thống kê cả đợt là thật: rẻ nhất, đắt nhất, trung vị, ngày có và không có chuyến.
"""
from __future__ import annotations

from datetime import date, timedelta
from statistics import median
from typing import Any

from src.backend.app.application.ports.itinerary_tools import ToolError
from src.backend.app.domain.itinerary.flights import flight_date
from src.backend.app.domain.itinerary.normalization import fold

from .flights import MAX_PAGES, PAGE, canonical_city

#: Khung giờ cất cánh (phút trong ngày), AC-AGT-08.
TIME_OF_DAY = {"early": (0, 540), "morning": (300, 720), "afternoon": (720, 1080), "evening": (1080, 1440)}
MAX_LISTED_DAYS = 8


def _minute(product: dict[str, Any]) -> int | None:
    attributes = product.get("attributes") or {}
    text = attributes.get("departureTimeLocal") or str(attributes.get("departureAt") or "")[11:16]
    try:
        hours, minutes = map(int, str(text).split(":")[:2])
    except ValueError:
        return None
    return hours * 60 + minutes


def _sellable(product: dict[str, Any], now) -> bool:
    """Chuyến một chiều còn bán, có giá, chưa cất cánh."""
    attributes = product.get("attributes") or {}
    day = flight_date(product)
    if not product.get("available") or product.get("unitPrice") is None or attributes.get("tripType") == "roundTrip":
        return False
    if day is None or day < now.date():
        return False
    minute = _minute(product)
    return day > now.date() or (minute is not None and minute > now.hour * 60 + now.minute)


async def lookup_flights(dispatcher, args: dict[str, Any], result: dict[str, Any]) -> None:
    if not args["origin"] or not args["destination"]:
        result["status"] = "needs_input"
        result["data"] = {"missing": [key for key in ("origin", "destination") if not args[key]]}
        return
    origin, destination = canonical_city(args["origin"]), canonical_city(args["destination"])
    routes = await dispatcher.source("list", {"taxonomy": "flight", "destination": destination, "limit": PAGE,
                                              "offset": 0})
    route = next((row for row in routes["results"]
                  if fold((row.get("attributes") or {}).get("originCity")) == fold(origin)), None)
    if route is None:
        result["status"] = "empty"
        result["data"] = {"origin": origin, "destination": destination, "route_found": False}
        return

    flights: list[dict] = []
    total = None
    for page in range(MAX_PAGES):
        try:
            data = await dispatcher.source("list", {"parentProductId": route["productId"], "availableOnly": True,
                                                    "limit": PAGE, "offset": page * PAGE})
        except ToolError:
            if not flights:
                raise
            result["status"] = "partial"  # các trang đã đọc vẫn dùng được; thống kê chỉ trên phần đã đọc
            break
        flights += data["results"]
        total = data["total"]
        if len(flights) >= total or not data["results"]:
            break

    now = dispatcher.now()
    sellable = [p for p in flights if _sellable(p, now)]
    real = [p for p in sellable if not (p.get("attributes") or {}).get("simulated")]
    pool = real or sellable  # giá minh hoạ chỉ dùng khi tuyến không còn chuyến giá thật
    time_matched = None
    if args["time_of_day"]:
        low, high = TIME_OF_DAY[args["time_of_day"]]
        in_window = [p for p in pool if (minute := _minute(p)) is not None and low <= minute < high]
        time_matched = bool(in_window)
        pool = in_window or pool  # không có chuyến trong khung thì tính mọi giờ
    wanted = date.fromisoformat(args["date"]) if args["date"] else None
    chosen = [p for p in pool if wanted is None or flight_date(p) == wanted]
    orders = {"price_asc": lambda p: (p["unitPrice"], flight_date(p), p["productId"]),
              "price_desc": lambda p: (-p["unitPrice"], flight_date(p), p["productId"]),
              "departure_asc": lambda p: (flight_date(p), _minute(p) or 0, p["productId"])}
    chosen.sort(key=orders[args["sort"] or "price_asc"])
    result["refs"] = [dispatcher.registry.add(p) for p in chosen[:args["limit"] or 5]]
    result["coverage"] = {"checked": len(flights), "total": total, "next_cursor": None}

    days = sorted({flight_date(p) for p in pool})
    period = None
    if days:
        prices = [p["unitPrice"] for p in pool]
        cheapest, priciest = (min(pool, key=lambda p: (p["unitPrice"], p["productId"])),
                              max(pool, key=lambda p: (p["unitPrice"], p["productId"])))
        missing = [days[0] + timedelta(days=n) for n in range((days[-1] - days[0]).days + 1)
                   if days[0] + timedelta(days=n) not in days]
        period = {"from": days[0].isoformat(), "to": days[-1].isoformat(), "flights": len(pool),
                  "days_with_flights": len(days), "days_without_flights": [d.isoformat() for d in missing[:MAX_LISTED_DAYS]],
                  "days_without_flights_count": len(missing),
                  "cheapest_ref": dispatcher.registry.add(cheapest), "cheapest_price_vnd": cheapest["unitPrice"],
                  "priciest_ref": dispatcher.registry.add(priciest), "priciest_price_vnd": priciest["unitPrice"],
                  "median_price_vnd": int(median(prices))}
    nearest = []
    if wanted and not chosen:
        nearest = [d.isoformat() for d in sorted(days, key=lambda d: (abs((d - wanted).days), d))[:2]]
    result["data"] = {"origin": route["attributes"]["originCity"], "destination": destination, "route_found": True,
                      "period": period, "date_flights": len(chosen) if wanted else None,
                      "nearest_dates_with_flights": nearest, "time_of_day_matched": time_matched,
                      "simulated_prices": bool(sellable) and not real}
    if not chosen and result["status"] == "ok":
        result["status"] = "empty"
