"""Vé phủ ngày cho demo (docs/prd/data-model.md §3.1 "Vé phủ ngày", FR-CAT-03 ngoại lệ 2, chốt 09/10/2026).

Mỗi tuyến, mỗi ngày trong cửa sổ đặt chỗ [as_of, as_of + 29] chưa có vé một chiều đặt được (hạng không phải Thương gia) thì sinh
một vé một chiều; chưa có vé khứ hồi đặt được thì sinh một vé khứ hồi. Chặng đi chép từ một vé thật của tuyến (chọn cố định theo
ngày bằng crc32); chặng về chép từ vé thật của tuyến ngược chiều, ngày về = ngày đi + 2–5 ngày (crc32); tuyến không có chiều ngược
thì đảo sân bay của chặng đi, giữ hãng, không có số hiệu. Giá = giá vé thật đã chép (khứ hồi: giá một vé khứ hồi thật của tuyến,
không có thì `roundTripFrom` của tuyến, không có nữa thì cộng hai chặng). Luôn `simulated: true` + "(giá minh hoạ)". Vé thật luôn
thắng: ngày đã có vé thật, ngày đã qua, hoặc tắt cấu hình → vé phủ ngày `available = false`, không xoá dòng (đơn cũ có thể trỏ tới).

Trước bước vé, sinh tuyến chiều ngược mô phỏng (`demo:reverse:*`) cho tuyến thật A → B có vé thật mà chưa có tuyến B → A: chặng mẫu
`templateFlights` = vé thật A → B đảo sân bay (giữ hãng, giờ cất cánh, không số hiệu), giá chép từ vé thật đó. Tuyến mô phỏng không có
vé thật (tuyến chiều ngược, tuyến của thành phần combo `comboOnly`) lấy chặng mẫu từ `templateFlights` / `templateFlight` /
`templateReturnFlight`, giá từ chặng mẫu hoặc `unit_price` / `roundTripFrom` của tuyến.

Chạy sau simulated_business (và sau combo_components để tuyến mô phỏng có vé). Một lần qua tunnel DB:
    python -m data_collection.seed.simulated_fill --database-url-env CLOUD_SEED_DATABASE_URL [--as-of YYYY-MM-DD] [--dry-run]
"""
from __future__ import annotations

import argparse
import os
import sys
import uuid
from collections import defaultdict
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from .catalog_meta import WINDOW_DAYS, stable_order_key, window
from .simulated_business import COLUMNS, MUTABLE, NAMESPACE

ENV = "SIMULATED_FILL_FLIGHTS"
PREFIX = "demo:fill:"
REVERSE = "demo:reverse:"
DEMO = "demo:"
SKIP_PREFIXES = ("demo:",)   # dòng mô phỏng (vé phủ ngày, Thương gia, tuyến chiều ngược, combo) không làm mẫu, không tính là thật
STAY_DAYS = (2, 3, 4, 5)
LEG_KEYS = ("airline", "airlineCode", "flightNumber", "originAirport", "destinationAirport", "departureAt", "arrivalAt",
            "departureTimeLocal", "arrivalTimeLocal", "durationMinutes", "nonstop")
ROUTE_KEYS = ("originCity", "originDestination", "originLatitude", "originLongitude", "latitude", "longitude",
              "destinationAirportName", "locationSource", "locationPrecision", "url")
TZ = ZoneInfo("Asia/Ho_Chi_Minh")


def enabled(env: dict | None = None) -> bool:
    """Mặc định bật (docs/prd/data-model.md §3.1); chỉ 0/false/no/off là tắt."""
    return str((os.environ if env is None else env).get(ENV, "")).strip().lower() not in ("0", "false", "no", "off")


def today_vn() -> date:
    return datetime.now(TZ).date()


def _is_real(row: dict) -> bool:
    a = row["attributes"] or {}
    return not a.get("simulated") and not str(row["source_ref"]).startswith(SKIP_PREFIXES)


def _trip(a: dict) -> str:
    return "roundTrip" if a.get("tripType") == "roundTrip" else "oneWay"


def _day(row: dict) -> date | None:
    """Ngày đi theo giờ Việt Nam (departureAt mang +07:00); không có thì available_from."""
    dep = (row["attributes"] or {}).get("departureAt")
    if dep:
        try:
            return datetime.fromisoformat(str(dep)).astimezone(TZ).date()
        except ValueError:
            pass
    value = row.get("available_from")
    return date.fromisoformat(str(value)[:10]) if value else None


def _clock(value: str | None) -> str | None:
    return str(value)[11:16] if value and len(str(value)) >= 16 else None


def _at(day: date, hhmm: str | None, plus_minutes: int = 0) -> str | None:
    if not hhmm:
        return None
    hour, minute = (int(x) for x in hhmm.split(":")[:2])
    moment = datetime(day.year, day.month, day.day, hour, minute, tzinfo=TZ) + timedelta(minutes=plus_minutes)
    return moment.isoformat(timespec="seconds")


def _leg_from_flight(row: dict) -> dict:
    """Chặng đi của một vé thật: các khoá LEG_KEYS (giờ giữ nguyên, ngày đổi sau)."""
    a = row["attributes"] or {}
    leg = {k: a.get(k) for k in LEG_KEYS if a.get(k) is not None}
    leg.setdefault("departureTimeLocal", _clock(a.get("departureAt")))
    leg.setdefault("arrivalTimeLocal", _clock(a.get("arrivalAt")))
    return leg


def _minutes(leg: dict) -> int | None:
    if leg.get("durationMinutes"):
        return int(leg["durationMinutes"])
    dep, arr = leg.get("departureAt"), leg.get("arrivalAt")
    if dep and arr:
        try:
            return int((datetime.fromisoformat(arr) - datetime.fromisoformat(dep)).total_seconds() // 60)
        except ValueError:
            return None
    return None


def _place(leg: dict, day: date) -> dict:
    """Chặng `leg` bay ngày `day`: departureAt / arrivalAt dựng lại từ giờ địa phương + thời lượng."""
    out = {k: v for k, v in leg.items() if k not in ("departureAt", "arrivalAt")}
    dep = _at(day, leg.get("departureTimeLocal") or _clock(leg.get("departureAt")))
    minutes = _minutes(leg)
    if dep:
        out["departureAt"] = dep
        if minutes is not None and minutes > 0:
            out["durationMinutes"] = minutes
            out["arrivalAt"] = (datetime.fromisoformat(dep) + timedelta(minutes=minutes)).isoformat(timespec="seconds")
            out["arrivalTimeLocal"] = _clock(out["arrivalAt"])
    return out


def _pick(items: list, key: str):
    return items[stable_order_key(key) % len(items)] if items else None


class Templates:
    """Vé thật làm mẫu theo tuyến: một chiều (tripType khác roundTrip; thiếu thì chặng đi của vé khứ hồi) và khứ hồi."""

    def __init__(self, flights: list[dict], routes: dict[str, dict]):
        self.one_way: dict[str, list[dict]] = defaultdict(list)
        self.round_trip: dict[str, list[dict]] = defaultdict(list)
        for row in sorted(flights, key=lambda r: r["product_id"]):
            a = row["attributes"] or {}
            if (not _is_real(row) or a.get("level") != "flight" or a.get("mergedInto") or row.get("unit_price") is None
                    or a.get("cabinClass") in ("BUSINESS", "FIRST") or not a.get("departureAt")):
                continue
            route = a.get("parentProductId")
            (self.round_trip if _trip(a) == "roundTrip" else self.one_way)[route].append(row)
        self.routes = routes
        self.reverse: dict[str, str] = {}
        by_cities = {}
        for pid, r in sorted(routes.items(), key=lambda kv: (_is_real(kv[1]), kv[0])):  # tuyến thật đè tuyến mô phỏng
            if r["available"] or (r["attributes"] or {}).get("comboOnly"):
                by_cities[(self._origin(r), self._destination(r))] = pid
        for pid, r in routes.items():
            back = by_cities.get((self._destination(r), self._origin(r)))
            if back and back != pid:
                self.reverse[pid] = back

    @staticmethod
    def _origin(route: dict) -> str | None:
        return (route["attributes"] or {}).get("originCity")

    @staticmethod
    def _destination(route: dict) -> str | None:
        return (route["attributes"] or {}).get("destinationCity") or route.get("destination")

    def _mock_templates(self, route_id: str) -> list[dict]:
        """Chặng mẫu ghi trên tuyến mô phỏng: `templateFlights` (tuyến chiều ngược) hoặc `templateFlight` (tuyến của combo)."""
        a = (self.routes.get(route_id) or {}).get("attributes") or {}
        found = a.get("templateFlights") or ([a["templateFlight"]] if isinstance(a.get("templateFlight"), dict) else [])
        return [t for t in found if isinstance(t, dict) and t.get("departureTimeLocal")]

    def _mock_price(self, route_id: str, tpl: dict) -> float | None:
        route = self.routes[route_id]
        if tpl.get("price") is not None:
            return float(tpl["price"])
        return float(route["unit_price"]) if route.get("unit_price") is not None else None

    def outbound(self, route_id: str, key: str) -> tuple[dict, float | None, str | None] | None:
        """(chặng mẫu, giá một chiều, productId vé mẫu) cho tuyến; None khi tuyến không có mẫu."""
        rows = self.one_way.get(route_id) or self.round_trip.get(route_id)
        if rows:
            row = _pick(rows, key)
            price = float(row["unit_price"]) if self.one_way.get(route_id) else None
            return _leg_from_flight(row), price, row["product_id"]
        tpls = self._mock_templates(route_id)
        if tpls:
            tpl = _pick(tpls, key)
            return {k: v for k, v in tpl.items() if k != "price"}, self._mock_price(route_id, tpl), None
        return None

    def inbound(self, route_id: str, key: str) -> tuple[dict, float | None, str | None]:
        """Chặng về: vé thật của tuyến ngược chiều; tuyến mô phỏng dùng `templateReturnFlight`; không có thì đảo sân bay."""
        back = self.reverse.get(route_id)
        if back and self.one_way.get(back):
            row = _pick(self.one_way[back], key)
            return _leg_from_flight(row), float(row["unit_price"]), row["product_id"]
        if back and self._mock_templates(back):  # chiều về là tuyến chiều ngược mô phỏng
            tpl = _pick(self._mock_templates(back), key + ":back")
            return {k: v for k, v in tpl.items() if k != "price"}, self._mock_price(back, tpl), None
        route = self.routes[route_id]
        tpl = (route["attributes"] or {}).get("templateReturnFlight")
        if isinstance(tpl, dict) and tpl.get("departureTimeLocal"):
            return dict(tpl), None, None
        out = self.outbound(route_id, key)
        leg = dict(out[0]) if out else {}
        leg["originAirport"], leg["destinationAirport"] = leg.get("destinationAirport"), leg.get("originAirport")
        leg.pop("flightNumber", None)
        return leg, None, None

    def round_trip_price(self, route_id: str, key: str) -> float | None:
        rows = self.round_trip.get(route_id)
        if rows:
            return float(_pick(rows, key)["unit_price"])
        value = (self.routes[route_id]["attributes"] or {}).get("roundTripFrom")
        return float(value) if value else None


def reverse_routes(rows: list[dict], as_of: date, on: bool) -> list[dict]:
    """Tuyến chiều ngược mô phỏng (`demo:reverse:*`) cho tuyến thật A → B có vé thật mà chưa có tuyến thật B → A, cùng các dòng cũ
    cần khoá (đã có tuyến thật B → A, tuyến gốc hết vé, hoặc tắt cấu hình). PRD data-model §3.1 (chốt 09/10/2026)."""
    from data_collection.collectors.geo import AIRPORTS
    lo, hi = window(as_of)
    routes = {r["product_id"]: r for r in rows if (r["attributes"] or {}).get("level") == "route"
              and not (r["attributes"] or {}).get("mergedInto")}
    templates = Templates([r for r in rows if (r["attributes"] or {}).get("level") != "route"], routes)
    real = {pid: r for pid, r in routes.items() if _is_real(r) and not str(r["source_ref"]).startswith(DEMO)
            and not (r["attributes"] or {}).get("comboOnly")}
    pairs = {(Templates._origin(r), Templates._destination(r)) for r in real.values()}
    existing = {r["source_ref"]: r for r in routes.values() if str(r["source_ref"]).startswith(REVERSE)}
    out: dict[str, dict] = {}
    for pid, route in sorted(real.items()) if on else ():
        a = route["attributes"] or {}
        origin, dest = Templates._origin(route), Templates._destination(route)
        legs = templates.one_way.get(pid) or templates.round_trip.get(pid)
        if not origin or not dest or (dest, origin) in pairs or not legs:
            continue
        flights, seen = [], set()
        for row in legs:
            leg = _leg_from_flight(row)
            key = (leg.get("airlineCode") or leg.get("airline"), leg.get("departureTimeLocal"))
            if key in seen:
                continue
            seen.add(key)
            tpl = {"airline": leg.get("airline"), "airlineCode": leg.get("airlineCode"),
                   "originAirport": leg.get("destinationAirport"), "destinationAirport": leg.get("originAirport"),
                   "departureTimeLocal": leg.get("departureTimeLocal"), "durationMinutes": _minutes(leg),
                   "nonstop": leg.get("nonstop"),
                   "price": float(row["unit_price"]) if templates.one_way.get(pid) else None}
            flights.append({k: v for k, v in tpl.items() if v is not None})
        prices = [t["price"] for t in flights if t.get("price") is not None]
        here = (a.get("originAirports") or [None])[0]
        attrs = {"level": "route", "originCity": dest, "destinationCity": origin, "originDestination": dest,
                 "originAirports": a.get("destinationAirports"), "destinationAirports": a.get("originAirports"),
                 "latitude": a.get("originLatitude"), "longitude": a.get("originLongitude"),
                 "originLatitude": a.get("latitude"), "originLongitude": a.get("longitude"),
                 "destinationAirportName": (AIRPORTS.get(here) or (None,))[0], "locationSource": a.get("locationSource"),
                 "locationPrecision": "airport", "airlines": a.get("airlines"), "roundTripFrom": a.get("roundTripFrom"),
                 "durationMinutes": a.get("durationMinutes"), "templateFlights": flights, "reverseOf": pid, "simulated": True,
                 "fieldSources": {"unitPrice": "mô phỏng", "schedule": "đảo chiều từ vé thật"}, "descriptionLang": "vi",
                 "descriptionSource": "mô phỏng: tuyến chiều ngược"}
        ref = f"{REVERSE}{route['source_ref']}"
        price = _price(min(prices)) if prices else (float(route["unit_price"]) if route.get("unit_price") is not None else None)
        out[ref] = {"product_id": str(uuid.uuid5(NAMESPACE, ref)), "name": f"Vé máy bay {dest} - {origin} (giá minh hoạ)",
                    "taxonomy": "flight", "destination": origin,
                    "description": (f"Tuyến mô phỏng chiều ngược của {route['name']} (giá minh hoạ): lịch bay đảo chiều từ chuyến thật, "
                                    f"giá chép từ vé thật chiều đi. Chỉ dùng cho demo."),
                    "attributes": {k: v for k, v in attrs.items() if v is not None}, "unit_price": price,
                    "currency": route.get("currency") or "VND", "available": price is not None, "available_from": lo,
                    "available_to": hi, "image_url": route.get("image_url"), "source_ref": ref}
    for ref, row in existing.items():
        if ref not in out and row["available"]:
            out[ref] = {**row, "available": False}
    return list(out.values())


def _name_one_way(leg: dict, route: dict) -> str:
    a = route["attributes"] or {}
    who = " ".join(x for x in (leg.get("airline"), leg.get("flightNumber")) if x) or "Chuyến bay"
    when = f" ({leg['departureTimeLocal']})" if leg.get("departureTimeLocal") else ""
    return f"{who}: {a.get('originCity')} - {Templates._destination(route)}{when} (giá minh hoạ)"


def _name_round_trip(out: dict, back: dict, day: date, back_day: date) -> str:
    numbers = " / ".join(x for x in (out.get("flightNumber"), back.get("flightNumber")) if x)  # chặng về đảo chiều: không số hiệu
    return (f"Khứ hồi {numbers + ': ' if numbers else ''}{out.get('originAirport')} - {out.get('destinationAirport')} "
            f"({day.isoformat()} – {back_day.isoformat()}) (giá minh hoạ)")


def _price(value: float | None) -> float | None:
    return None if value is None else float(round(value / 1000.0) * 1000)


def build(route: dict, kind: str, day: date, templates: Templates) -> dict | None:
    """Một vé phủ ngày (`kind` = oneWay | roundTrip) của tuyến `route` bay ngày `day`; None khi tuyến không có mẫu."""
    rid = route["product_id"]
    key = f"{rid}:{kind}:{day.isoformat()}"
    out = templates.outbound(rid, key)
    if out is None:
        return None
    leg, price, source = out
    ra = route["attributes"] or {}
    attrs = {k: ra[k] for k in ROUTE_KEYS if ra.get(k) is not None}
    attrs.update(_place(leg, day))
    attrs.update(level="flight", parentProductId=rid, tripType=kind, cabinClass="ECONOMY", fixedDepartureDate=True,
                 destinationCity=Templates._destination(route), priceBasis="per_person", simulated=True,
                 sourceAvailableFrom=day.isoformat(), sourceAvailableTo=day.isoformat(), descriptionLang="vi",
                 descriptionSource="mô phỏng: vé phủ ngày",
                 fieldSources={"unitPrice": "mô phỏng", "departureAt": "mô phỏng", "schedule": "chép từ vé thật"})
    sources = [source] if source else []
    if kind == "roundTrip":
        stay = STAY_DAYS[stable_order_key(key + ":stay") % len(STAY_DAYS)]
        back_day = day + timedelta(days=stay)
        back, back_price, back_source = templates.inbound(rid, key)
        back = _place(back, back_day)
        attrs["returnFlight"] = {k: back.get(k) for k in ("airline", "flightNumber", "originAirport", "destinationAirport",
                                                          "departureAt", "arrivalAt") if back.get(k) is not None}
        attrs.update(returnDate=back_day.isoformat(), stayDays=stay)
        sources += [back_source] if back_source else []
        total = templates.round_trip_price(rid, key)
        if total is None and price is not None:
            total = price + (back_price if back_price is not None else price)
        price = total
        name = _name_round_trip(attrs, back, day, back_day)
        what = "khứ hồi"
    else:
        name = _name_one_way(attrs, route)
        what = "một chiều"
    if sources:
        attrs["simulatedFrom"] = sources
    price = _price(price)
    ref = f"{PREFIX}{route['source_ref']}:{kind}:{day.isoformat()}"
    description = (f"Vé {what} mô phỏng phủ ngày (giá minh hoạ): lịch bay chép từ chuyến thật của tuyến {route['name']}; giá chép "
                   f"từ vé thật, không phải giá nguồn báo cho ngày này. Chỉ dùng cho demo.")
    return {"product_id": str(uuid.uuid5(NAMESPACE, ref)), "name": name, "taxonomy": "flight",
            "destination": route["destination"], "description": description, "attributes": attrs, "unit_price": price,
            "currency": route.get("currency") or "VND", "available": price is not None, "available_from": day,
            "available_to": day, "image_url": route.get("image_url"), "source_ref": ref}


def plan(rows: list[dict], as_of: date, on: bool) -> tuple[list[dict], list[dict]]:
    """(dòng vé phủ ngày mong muốn, tuyến cần nới available_from/to) từ các dòng taxonomy flight hiện có."""
    lo, hi = window(as_of)
    routes = {r["product_id"]: r for r in rows if (r["attributes"] or {}).get("level") == "route"
              and not (r["attributes"] or {}).get("mergedInto")}
    flights = [r for r in rows if (r["attributes"] or {}).get("level") != "route"]
    templates = Templates(flights, routes)
    covered = set()
    for r in flights:
        a = r["attributes"] or {}
        if (_is_real(r) and r["available"] and r.get("unit_price") is not None and not a.get("mergedInto")
                and a.get("cabinClass") not in ("BUSINESS", "FIRST")):
            covered.add((a.get("parentProductId"), _trip(a), _day(r)))
    existing = {r["source_ref"]: r for r in flights if str(r["source_ref"]).startswith(PREFIX)}
    out: dict[str, dict] = {}
    if on:
        for rid, route in sorted(routes.items()):
            for offset in range(WINDOW_DAYS):
                day = lo + timedelta(days=offset)
                for kind in ("oneWay", "roundTrip"):
                    if (rid, kind, day) in covered:
                        continue
                    row = build(route, kind, day, templates)
                    if row is not None:
                        out[row["source_ref"]] = row
    for ref, row in existing.items():
        if ref not in out and row["available"]:  # ngày đã qua, đã có vé thật, hoặc tắt cấu hình → khoá, giữ dòng
            out[ref] = {**row, "available": False}
    days: dict[str, list[date]] = defaultdict(list)
    for r in [*flights, *out.values()]:
        a = r["attributes"] or {}
        day = date.fromisoformat(str(r["available_from"])[:10]) if r.get("available_from") is not None else None
        if r["available"] and day is not None and lo <= day <= hi and not a.get("mergedInto"):  # cửa sổ tuyến ≤ 30 ngày
            days[a.get("parentProductId")].append(day)
    widened = []
    for rid, route in routes.items():
        if days.get(rid) and (route["available"] or (route["attributes"] or {}).get("comboOnly")):
            first, last = min(days[rid]), max(days[rid])
            if (route.get("available_from"), route.get("available_to")) != (first, last):
                widened.append({**route, "available_from": first, "available_to": last})
    return list(out.values()), widened


def sync(conn, on: bool | None = None, as_of: date | None = None, dry_run: bool = False) -> dict[str, int]:
    """Upsert demo:fill:* trong transaction của `conn`; nới available_from/to của tuyến theo vé con. Chỉ ghi các dòng đó."""
    from psycopg.rows import dict_row
    from psycopg.types.json import Jsonb
    on = enabled() if on is None else on
    as_of = as_of or today_vn()
    with conn.cursor(row_factory=dict_row) as cursor:
        cursor.execute(f"SELECT {', '.join(COLUMNS)} FROM cdp.products WHERE taxonomy = 'flight'")
        rows = [{**r, "product_id": str(r["product_id"])} for r in cursor.fetchall()]
    reverse = reverse_routes(rows, as_of, on)
    merged = {r["product_id"]: r for r in rows}
    merged.update({r["product_id"]: r for r in reverse})
    desired, widened = plan(list(merged.values()), as_of, on)
    before = {r["product_id"]: r for r in rows}
    changes = [r for r in [*reverse, *desired] if r["product_id"] not in before
               or any(before[r["product_id"]][c] != r[c] for c in MUTABLE)]
    if changes and not dry_run:
        with conn.cursor() as cursor:
            cursor.executemany(
                f"""INSERT INTO cdp.products AS p ({', '.join(COLUMNS)}) VALUES ({', '.join(['%s'] * len(COLUMNS))})
                    ON CONFLICT (product_id) DO UPDATE SET {', '.join(f'{c} = EXCLUDED.{c}' for c in MUTABLE)}""",
                [[Jsonb(row[c]) if c == "attributes" else row[c] for c in COLUMNS] for row in changes])
    if widened and not dry_run:
        with conn.cursor() as cursor:
            cursor.executemany("UPDATE cdp.products SET available_from = %s, available_to = %s WHERE product_id = %s::uuid",
                               [(r["available_from"], r["available_to"], r["product_id"]) for r in widened])
    live = [r for r in desired if r["available"]]
    return {"reverseRoutes": sum(1 for r in reverse if r["available"]),
            "reverseRoutesClosed": sum(1 for r in reverse if not r["available"]),"fillOneWay": sum(1 for r in live if r["attributes"]["tripType"] == "oneWay"),
            "fillRoundTrip": sum(1 for r in live if r["attributes"]["tripType"] == "roundTrip"),
            "fillClosed": sum(1 for r in desired if not r["available"]),
            "fillWritten": 0 if dry_run else len(changes), "fillChanged": len(changes),
            "routesWidened": len(widened), "routes": len({r["attributes"]["parentProductId"] for r in live})}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sinh/khoá vé phủ ngày (demo:fill:*) trong cdp.products.")
    parser.add_argument("--database-url-env", default="SEED_DATABASE_URL", help="tên biến môi trường chứa DSN")
    parser.add_argument("--as-of", type=date.fromisoformat, default=None, help="ngày đầu cửa sổ (mặc định: hôm nay giờ VN)")
    parser.add_argument("--dry-run", action="store_true", help="chỉ tính, không ghi")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--enable", action="store_true", help=f"bật kể cả khi {ENV}=0")
    group.add_argument("--disable", action="store_true", help="khoá mọi vé phủ ngày")
    args = parser.parse_args(argv)
    url = os.environ.get(args.database_url_env)
    if not url:
        parser.error(f"{args.database_url_env} chưa đặt")
    import psycopg
    on = True if args.enable else False if args.disable else enabled()
    with psycopg.connect(url) as conn:
        if args.dry_run:
            conn.execute("SET TRANSACTION READ ONLY")
        else:
            conn.execute("SELECT pg_advisory_xact_lock(7791024)")  # cùng khoá ghi catalog với job fresh
        counts = sync(conn, on, args.as_of, dry_run=args.dry_run)
    print(" · ".join(f"{k}={v}" for k, v in counts.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
