"""Sản phẩm cho mọi thành phần combo + phần giá (docs/prd/data-model.md §3.1 "Thành phần combo mô phỏng", FR-CAT-04, FR-CAT-03
ngoại lệ 3, chốt 09/10/2026).

Bước thanh toán tách combo thành từng dịch vụ, nên mỗi dòng `catalog.combo_items` phải trỏ tới một sản phẩm đặt được:
  * khách sạn → hạng phòng thật khi tên khách sạn và tên hạng phòng khớp catalog (sau chuẩn hoá, độ giống ≥ 0,9); không thì một
    khách sạn tổng + một hạng phòng mô phỏng riêng của combo (chép thông tin khách sạn thật đã khớp, ghi `comboBaseProductId`);
  * vé máy bay → tuyến theo sân bay đi/đến của combo; chưa có tuyến thì tuyến mô phỏng (chặng mẫu = giờ bay ghi trong combo, để
    seed/simulated_fill.py phủ vé mọi ngày);
  * vé tham quan / golf → giữ vé đặt được; chưa nối hoặc trỏ tới điểm không bán vé thì vé mô phỏng;
  * ăn uống, xe đưa đón, voucher, khác (`meal` / `transfer` / `other`) không thuộc loại catalog nào → đi kèm combo: không sinh sản phẩm,
    `item_product_id` NULL, `price_share` NULL (chốt 09/10/2026).
Sản phẩm mô phỏng mang `comboOnly: true` (view catalog.product_meta: không là search unit, không gợi ý), `simulated: true`, tên có
"(giá minh hoạ)", `sourceRef = demo:combo:<sourceRef combo>:<position>` (khách sạn tổng thêm `:property`).

`price_share` (chỉ thành phần có sản phẩm) = giá combo × giá tham khảo / tổng giá tham khảo, làm tròn nghìn đồng, phần lẻ dồn vào thành
phần lớn nhất (tổng đúng bằng giá combo). Giá tham khảo × số lượng: phòng = giá hạng phòng thật (hoặc giá khách sạn đã khớp), vé máy bay =
giá khứ hồi rẻ nhất của tuyến, vé = giá vé (vé mô phỏng: số tiền trong nhãn nếu có); thiếu thì bằng thành phần rẻ nhất của combo, không
thành phần nào có giá thì chia đều. Giá lẻ của sản phẩm mô phỏng = giá thật nếu có (giá khách sạn đã khớp, số tiền trong nhãn), không thì
`price_share / số lượng`; giá trong combo luôn là `price_share`. Combo hết bán / đổi thành phần / tắt cấu hình
→ sản phẩm mô phỏng `available = false`, không xoá dòng.

Chạy sau parse combo, trước simulated_fill. Một lần qua tunnel DB:
    python -m data_collection.seed.combo_components --database-url-env CLOUD_SEED_DATABASE_URL [--dry-run] [--report out.json]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import uuid
from collections import defaultdict
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from difflib import SequenceMatcher
from pathlib import Path

from data_collection.collectors.textutil import fold

from .catalog_meta import WINDOW_DAYS, variant, window
from .simulated_business import COLUMNS, MUTABLE, NAMESPACE
from .simulated_fill import today_vn

ENV = "SIMULATED_COMBO_ITEMS"
PREFIX = "demo:combo:"
REVERSE = "demo:reverse:"
DEMO = "demo:"
MATCH = 0.9  # độ giống tối thiểu của tên khách sạn và tên hạng phòng (PRD data-model §3.1)
SERVICE_KINDS = ("meal", "transfer", "other")
NOTE = "Thành phần combo mô phỏng (giá minh hoạ = phần giá trong combo, không phải giá nguồn báo); chỉ đặt qua combo, chỉ dùng cho demo."
HOTEL_WORDS = re.compile(r"\b(?:khach san|hotel|resort)\b")
AMOUNT_RE = re.compile(r"(\d{1,3}(?:[.,]\d{3})+|\d+)\s*(k|nghìn|ngàn|vnđ|vnd|đ)(?![a-zà-ỹ])", re.I)
DURATION_RE = re.compile(r"(?:(\d+)\s*g)?\s*(?:(\d+)\s*p)?")
COPY_HOTEL = ("address", "province", "city", "starRating", "starRatingType", "latitude", "longitude", "locationPrecision",
              "locationSource", "amenities", "images", "checkInTime", "checkOutTime", "propertyType", "brand")
COPY_PLACE = ("latitude", "longitude", "locationPrecision", "locationSource", "address", "province", "city", "venue")


def enabled(env: dict | None = None) -> bool:
    """Mặc định bật (docs/prd/data-model.md §3.1); chỉ 0/false/no/off là tắt."""
    return str((os.environ if env is None else env).get(ENV, "")).strip().lower() not in ("0", "false", "no", "off")


def norm_hotel(name: str | None) -> str:
    return re.sub(r"\s+", " ", HOTEL_WORDS.sub(" ", fold(name))).strip()


def sim(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio() if a and b else 0.0


def label_amount(label: str | None) -> Decimal | None:
    """Số tiền ghi trong nhãn: "300k" → 300.000; "150.000 VNĐ" → 150.000; không có thì None."""
    m = AMOUNT_RE.search(label or "")
    if not m:
        return None
    value = Decimal(re.sub(r"[.,]", "", m.group(1)))
    return value * 1000 if m.group(2).lower() == "k" or m.group(2).lower() in ("nghìn", "ngàn") else value


def minutes(text: str | None) -> int | None:
    """"1g 20p" → 80."""
    m = DURATION_RE.fullmatch((text or "").strip())
    if not m or not any(m.groups()):
        return None
    return int(m.group(1) or 0) * 60 + int(m.group(2) or 0)


def _real(row: dict | None) -> bool:
    return bool(row) and not str(row["source_ref"]).startswith(DEMO) and not (row["attributes"] or {}).get("mergedInto")


def _bookable(row: dict | None) -> bool:
    return (_real(row) and row["available"] and row.get("unit_price") is not None
            and (row["attributes"] or {}).get("ticketed") is not False)


def _price(row: dict | None) -> Decimal | None:
    return Decimal(str(row["unit_price"])) if row and row.get("unit_price") is not None else None


class Catalog:
    def __init__(self, rows: list[dict]):
        self.by_id = {r["product_id"]: r for r in rows}
        self.hotels: dict[str, list[dict]] = defaultdict(list)
        self.rooms: dict[str, list[dict]] = defaultdict(list)
        self.routes: dict[tuple[str, str], dict] = {}
        self.airline: dict[str, str] = {}
        self.airport: dict[str, dict] = {}
        self.reverse_routes: dict[tuple[str, str], dict] = {}
        for r in sorted(rows, key=lambda r: r["product_id"]):
            a = r["attributes"] or {}
            kind = variant({"taxonomy": r["taxonomy"], "attributes": a})
            if kind == "flight_route" and str(r["source_ref"]).startswith(REVERSE) and r["available"]:
                for o in a.get("originAirports") or []:  # tuyến chiều ngược mô phỏng (seed/simulated_fill.py): hiện như tuyến thật
                    for t in a.get("destinationAirports") or []:
                        self.reverse_routes.setdefault((o, t), r)
            if not _real(r):
                continue
            if kind == "hotel_property":
                self.hotels[r["destination"]].append(r)
            elif kind == "hotel_room":
                self.rooms[a.get("parentProductId")].append(r)
            elif kind == "flight_route":
                for o in a.get("originAirports") or []:
                    self.airport.setdefault(o, {"city": a.get("originCity"), "latitude": a.get("originLatitude"),
                                                "longitude": a.get("originLongitude")})
                    for t in a.get("destinationAirports") or []:
                        self.routes.setdefault((o, t), r)
            elif kind == "flight" and a.get("airlineCode") and a.get("airline"):
                self.airline.setdefault(a["airlineCode"], a["airline"])

    def property_for(self, name: str, destination: str) -> tuple[dict | None, float]:
        want = norm_hotel(name)
        scored = [(sim(want, norm_hotel(h["name"])), h["product_id"], h) for h in self.hotels.get(destination, [])]
        if not scored:
            return None, 0.0
        score, _, best = max(scored, key=lambda t: (t[0], t[1]))
        return (best, score) if score >= MATCH else (None, score)

    def room_for(self, prop: dict, room_type: str | None) -> tuple[dict | None, float]:
        if not room_type:
            return None, 0.0
        want = fold(room_type)
        scored = [(sim(want, fold((r["attributes"] or {}).get("roomName") or r["name"].split(" - ")[-1])), r["product_id"], r)
                  for r in self.rooms.get(prop["product_id"], []) if _bookable(r)]
        if not scored:
            return None, 0.0
        score, _, best = max(scored, key=lambda t: (t[0], t[1]))
        return (best, score) if score >= MATCH else (None, score)


def shares(price: Decimal | None, refs: list[Decimal | None]) -> list[Decimal | None]:
    """Chia giá combo theo giá tham khảo; tổng đúng bằng `price` (PRD data-model §3.1)."""
    if price is None or not refs:
        return [None] * len(refs)
    known = [r for r in refs if r is not None and r > 0]
    fallback = min(known) if known else Decimal(1)
    weights = [r if r is not None and r > 0 else fallback for r in refs]
    total = sum(weights)
    raw = [price * w / total for w in weights]
    out = [(r / 1000).quantize(Decimal(1), rounding=ROUND_HALF_UP) * 1000 for r in raw]
    biggest = max(range(len(raw)), key=lambda i: (raw[i], -i))
    out[biggest] += price - sum(out)
    return [o.quantize(Decimal("0.01")) for o in out]


def _place_from(base: dict | None, combo: dict) -> dict:
    src = (base or {}).get("attributes") or {}
    ca = combo["attributes"] or {}
    return {k: src.get(k, ca.get(k)) for k in COPY_PLACE if src.get(k, ca.get(k)) is not None}


def _leg(flight: dict | None, catalog: Catalog) -> dict | None:
    """Chặng mẫu từ `outboundFlight` / `inboundFlight` của combo Trip (giờ bay, hãng, sân bay; không có số hiệu)."""
    if not isinstance(flight, dict) or not flight.get("departTime"):
        return None
    code = flight.get("airlineCode")
    airport = lambda v: (v or "").split()[0] or None  # "HAN T1" → "HAN"
    leg = {"airline": catalog.airline.get(code, code), "airlineCode": code, "originAirport": airport(flight.get("departAirport")),
           "destinationAirport": airport(flight.get("arriveAirport")), "departureTimeLocal": flight.get("departTime"),
           "arrivalTimeLocal": flight.get("arriveTime"), "durationMinutes": minutes(flight.get("durationText"))}
    return {k: v for k, v in leg.items() if v is not None}


class Plan:
    """Kết quả cho một lượt: sản phẩm mô phỏng mong muốn, cập nhật combo_items, và báo cáo từng thành phần."""

    def __init__(self):
        self.products: dict[str, dict] = {}
        self.items: list[dict] = []
        self.report: list[dict] = []


def _mock(ref: str, name: str, taxonomy: str, combo: dict, attrs: dict, available_from, available_to, image_url) -> dict:
    a = dict(attrs)
    a.update(comboOnly=True, simulated=True, comboProductId=combo["product_id"], descriptionLang="vi",
             descriptionSource="mô phỏng: thành phần combo", fieldSources={"unitPrice": "mô phỏng"})
    return {"product_id": str(uuid.uuid5(NAMESPACE, ref)), "name": f"{name} (giá minh hoạ)", "taxonomy": taxonomy,
            "destination": combo["destination"], "description": f"{NOTE} Thuộc combo: {combo['name']}.", "attributes": a,
            "unit_price": None, "currency": combo.get("currency") or "VND", "available": False,
            "available_from": available_from, "available_to": available_to, "image_url": image_url, "source_ref": ref}


def _unwrap(item: dict, catalog: Catalog) -> tuple[str, dict | None]:
    """(loại gốc, sản phẩm gốc) của dòng: lần chạy sau dòng đã trỏ vào sản phẩm mô phỏng của lần trước, nên lấy lại liên kết gốc
    (`comboBaseProductId`, khách sạn tổng của phòng mô phỏng) và loại gốc (`serviceKind`) để kết quả không đổi giữa các lần chạy."""
    linked = catalog.by_id.get(item["item_product_id"]) if item["item_product_id"] else None
    for _ in range(3):  # dòng đã gộp → dòng giữ (như fresh_catalog_db._canonical_ids)
        target = ((linked or {}).get("attributes") or {}).get("mergedInto")
        if not target or target not in catalog.by_id:
            break
        linked = catalog.by_id[target]
    if not linked or not str(linked["source_ref"]).startswith(PREFIX):
        return item["item_kind"], linked
    a = linked["attributes"] or {}
    holder = catalog.by_id.get(a.get("parentProductId")) if a.get("level") == "room" else linked
    base = ((holder or {}).get("attributes") or {}).get("comboBaseProductId")
    return a.get("serviceKind") or item["item_kind"], catalog.by_id.get(base) if base else None


def resolve(combo: dict, item: dict, catalog: Catalog, lo: date, hi: date) -> dict:
    """Một thành phần → {target (productId sẽ trỏ tới), kind, ref (giá tham khảo × số lượng), mocks, note}."""
    a = combo["attributes"] or {}
    q = Decimal(str(item["quantity"] or 1))
    kind, linked = _unwrap(item, catalog)
    ref_base = f"{PREFIX}{combo['source_ref']}:{item['position']}"
    window_dates = (combo.get("available_from"), combo.get("available_to"))

    if kind == "hotel":
        if linked and _real(linked) and variant({"taxonomy": "hotel", "attributes": linked["attributes"]}) == "hotel_room" \
                and _bookable(linked):
            return {"target": linked["product_id"], "kind": kind, "ref": _price(linked) * q, "mocks": [],
                    "note": f"giữ hạng phòng thật: {linked['name'][:70]}"}
        hotel_name = a.get("hotelName") or item["label"]
        room_type = a.get("roomType")
        prop, prop_score = (linked, 1.0) if linked and _real(linked) and (linked["attributes"] or {}).get("level") == "property" \
            else catalog.property_for(hotel_name, combo["destination"])
        if prop is not None:
            room, room_score = catalog.room_for(prop, room_type)
            if room is not None:
                return {"target": room["product_id"], "kind": kind, "ref": _price(room) * q, "mocks": [],
                        "note": f"khớp hạng phòng thật ({prop_score:.2f}/{room_score:.2f}): {room['name'][:70]}"}
        base = (prop or {}).get("attributes") or {}
        prop_attrs = {k: base[k] for k in COPY_HOTEL if base.get(k) is not None} if prop else {
            "address": a.get("address"), "starRating": a.get("hotelStarRating") or a.get("starRating"),
            **{k: a[k] for k in ("latitude", "longitude", "locationPrecision", "locationSource", "images") if a.get(k) is not None}}
        prop_attrs = {k: v for k, v in prop_attrs.items() if v is not None}
        prop_attrs.update(level="property", hotelName=hotel_name)
        if prop:
            prop_attrs["comboBaseProductId"] = prop["product_id"]
        lo_s, hi_s = lo, hi
        mock_prop = _mock(f"{ref_base}:property", prop["name"] if prop else hotel_name, "hotel", combo, prop_attrs, lo_s, hi_s,
                          (prop or {}).get("image_url") or combo.get("image_url"))
        room_name = room_type or "Phòng theo combo"
        room_attrs = {"level": "room", "parentProductId": mock_prop["product_id"], "roomName": room_name,
                      "hotelName": prop["name"] if prop else hotel_name, "priceNights": 1,
                      "maxOccupancy": int(a.get("priceAdults") or a.get("minPax") or 2),
                      "availability": {"from": lo.isoformat(), "days": WINDOW_DAYS, "calendar": "1" * WINDOW_DAYS},
                      **{k: prop_attrs[k] for k in ("latitude", "longitude", "locationPrecision", "locationSource") if k in prop_attrs}}
        mock_room = _mock(ref_base, f"{mock_prop['name'][:-len(' (giá minh hoạ)')]} - {room_name}", "hotel", combo, room_attrs,
                          lo_s, hi_s, mock_prop["image_url"])
        real = _price(prop) if prop and prop.get("unit_price") is not None else None  # giá khách sạn thật (giá thấp nhất nguồn báo)
        why = (f"khách sạn thật {prop['name'][:50]} ({prop_score:.2f}), hạng phòng \"{room_type}\" không khớp" if prop
               else f"khách sạn \"{hotel_name}\" không có trong catalog (giống nhất {prop_score:.2f})")
        return {"target": mock_room["product_id"], "kind": kind, "ref": real * q if real is not None else None, "real": real,
                "mocks": [mock_room, mock_prop], "room": mock_room, "property": mock_prop, "note": f"phòng mô phỏng: {why}"}

    if kind == "flight":
        route = None
        if linked and (_real(linked) or str(linked["source_ref"]).startswith(REVERSE)):
            la = linked["attributes"] or {}
            route = linked if la.get("level") == "route" else catalog.by_id.get(la.get("parentProductId"))
        origin = a.get("fromCode") or a.get("originAirport")
        dest = a.get("toCode") or a.get("destinationAirport")
        route = route or catalog.routes.get((origin, dest)) or catalog.reverse_routes.get((origin, dest))
        if route is not None:
            ra = route["attributes"] or {}
            rt = Decimal(str(ra["roundTripFrom"])) if ra.get("roundTripFrom") else (_price(route) * 2 if _price(route) else None)
            return {"target": route["product_id"], "kind": kind, "ref": rt * q if rt is not None else None, "mocks": [],
                    "note": f"tuyến {'chiều ngược mô phỏng' if str(route['source_ref']).startswith(REVERSE) else 'thật'}: "
                            f"{route['name'][:60]}"}
        here = catalog.airport.get(origin) or {}
        attrs = {"level": "route", "originAirports": [origin], "destinationAirports": [dest], "originCity": here.get("city") or origin,
                 "destinationCity": combo["destination"], "originLatitude": here.get("latitude"),
                 "originLongitude": here.get("longitude"), "templateFlight": _leg(a.get("outboundFlight"), catalog),
                 "templateReturnFlight": _leg(a.get("inboundFlight"), catalog),
                 **{k: a[k] for k in ("latitude", "longitude") if a.get(k) is not None}, "locationPrecision": "destination"}
        attrs = {k: v for k, v in attrs.items() if v is not None}
        if attrs.get("templateFlight", {}).get("airline"):
            attrs["airlines"] = [attrs["templateFlight"]["airline"]]
        mock_route = _mock(ref_base, f"Vé máy bay {attrs['originCity']} - {combo['destination']}", "flight", combo, attrs,
                           lo, hi, combo.get("image_url"))
        return {"target": mock_route["product_id"], "kind": kind, "ref": None, "mocks": [mock_route], "route": mock_route,
                "note": f"tuyến mô phỏng {origin}-{dest} (chưa có trong catalog)"}

    if kind in ("attraction", "golf") and _bookable(linked):
        return {"target": linked["product_id"], "kind": kind, "ref": _price(linked) * q, "mocks": [],
                "note": f"giữ vé thật: {linked['name'][:70]}"}

    if kind in SERVICE_KINDS:  # ăn uống, xe đưa đón, voucher, khác: không thuộc loại catalog nào → đi kèm combo, không sản phẩm, không phần giá
        return {"target": None, "kind": kind, "ref": None, "mocks": [], "included": True,
                "note": "dịch vụ đi kèm (không thuộc loại catalog), không sinh sản phẩm"}
    taxonomy = kind
    venue = a.get("venue") or a.get("poiName") or a.get("hotelName") or combo["destination"]
    attrs = {**_place_from(linked if _real(linked) else None, combo), "venue": venue,
             "availability": {"from": lo.isoformat(), "days": WINDOW_DAYS, "calendar": "1" * WINDOW_DAYS}}
    if linked and _real(linked):
        attrs["comboBaseProductId"] = linked["product_id"]
    label = re.sub(r"^\s*(?:tặng|TẶNG|Tặng)\s+", "", item["label"]).strip() or item["label"]
    name = label if fold(venue) in fold(label) else f"{label} — {venue}"
    image = (linked if _real(linked) else {}).get("image_url") or combo.get("image_url")
    mock = _mock(ref_base, name, taxonomy, combo, attrs, *window_dates, image)
    amount = label_amount(item["label"])
    why = "điểm không bán vé" if linked else "vé chưa nối"
    return {"target": mock["product_id"], "kind": taxonomy, "ref": amount * q if amount is not None else None, "real": amount,
            "mocks": [mock], "note": f"{why} mô phỏng" + (f", giá trong nhãn {amount:,.0f}" if amount is not None else "")}


def plan(rows: list[dict], items: list[dict], as_of: date, on: bool) -> Plan:
    lo, hi = window(as_of)
    catalog = Catalog(rows)
    out = Plan()
    by_combo: dict[str, list[dict]] = defaultdict(list)
    for item in items:
        by_combo[str(item["combo_product_id"])].append(item)
    if on:
        for cid in sorted(by_combo):
            combo = catalog.by_id.get(cid)
            if combo is None:
                continue
            lines = sorted(by_combo[cid], key=lambda i: i["position"])
            resolved = [resolve(combo, item, catalog, lo, hi) for item in lines]
            # giá combo chỉ chia cho thành phần có sản phẩm; dịch vụ đi kèm có price_share = NULL
            priced = [i for i, r in enumerate(resolved) if not r.get("included")]
            split = dict(zip(priced, shares(_price(combo), [resolved[i]["ref"] for i in priced])))
            parts = [split.get(i) for i in range(len(resolved))]
            for item, res, share in zip(lines, resolved, parts):
                q = Decimal(str(item["quantity"] or 1))
                # giá lẻ của sản phẩm mô phỏng: giá thật nếu có, không thì phần giá combo / số lượng (giá trong combo luôn là price_share)
                real = res.get("real")
                unit = (real if real is not None else share / q if share is not None else None)
                unit = unit.quantize(Decimal("0.01")) if unit is not None else None
                live = bool(combo["available"]) and unit is not None
                for mock in res["mocks"]:
                    mock.update(available=live)
                if "room" in res:
                    res["room"]["unit_price"] = unit
                    res["property"]["unit_price"] = unit
                elif "route" in res:
                    unit = (share / q).quantize(Decimal("0.01")) if share is not None else None  # tuyến: không có giá thật
                    if unit is not None:
                        res["route"]["unit_price"] = (unit / 2 / 1000).quantize(Decimal(1), rounding=ROUND_HALF_UP) * 1000
                        res["route"]["attributes"]["roundTripFrom"] = float(unit)
                    res["route"]["available"] = live and bool(res["route"]["attributes"].get("templateFlight"))
                elif res["mocks"]:
                    res["mocks"][0]["unit_price"] = unit
                for mock in res["mocks"]:
                    out.products[mock["source_ref"]] = mock
                out.items.append({"combo_product_id": cid, "position": item["position"], "item_product_id": res["target"],
                                  "item_kind": res["kind"], "price_share": share})
                out.report.append({"combo": combo["name"], "comboAvailable": bool(combo["available"]),
                                   "comboPrice": str(_price(combo)), "position": item["position"], "label": item["label"],
                                   "kindBefore": item["item_kind"], "kindAfter": res["kind"],
                                   "linkedBefore": item["item_product_id"] and str(item["item_product_id"]),
                                   "target": res["target"], "mock": bool(res["mocks"]), "included": bool(res.get("included")),
                                   "reference": None if res["ref"] is None else str(res["ref"]),
                                   "priceShare": None if share is None else str(share), "note": res["note"]})
    for row in rows:
        ref = str(row["source_ref"])
        if ref.startswith(PREFIX) and ref not in out.products and row["available"]:
            out.products[ref] = {**row, "available": False}  # combo đổi thành phần / tắt cấu hình → khoá, giữ dòng
    return out


def sync(conn, on: bool | None = None, as_of: date | None = None, dry_run: bool = False,
         report_path: Path | None = None) -> dict[str, int]:
    """Upsert demo:combo:* trong transaction của `conn`, rồi cập nhật item_product_id / item_kind / price_share của combo_items."""
    from psycopg.rows import dict_row
    from psycopg.types.json import Jsonb
    on = enabled() if on is None else on
    as_of = as_of or today_vn()
    with conn.cursor(row_factory=dict_row) as cursor:
        cursor.execute(f"SELECT {', '.join(COLUMNS)} FROM cdp.products")
        rows = [{**r, "product_id": str(r["product_id"])} for r in cursor.fetchall()]
        cursor.execute("SELECT combo_product_id, position, label, item_kind, item_product_id, quantity, price_share "
                       "FROM catalog.combo_items")
        items = [{**i, "combo_product_id": str(i["combo_product_id"]),
                  "item_product_id": i["item_product_id"] and str(i["item_product_id"])} for i in cursor.fetchall()]
    result = plan(rows, items, as_of, on)
    before = {r["product_id"]: r for r in rows}
    for product in result.products.values():
        # Tuyến bay mô phỏng: ảnh đã có trên DB (ảnh thành phố đến, đặt 12/10/2026) thắng ảnh combo (thường trống).
        old = before.get(product["product_id"])
        if product["taxonomy"] == "flight" and old and old.get("image_url"):
            product["image_url"] = old["image_url"]
    changes = [r for r in result.products.values() if r["product_id"] not in before
               or any(before[r["product_id"]][c] != r[c] for c in MUTABLE)]
    stored = {(i["combo_product_id"], i["position"]): i for i in items}
    relinks = [i for i in result.items if (stored[(i["combo_product_id"], i["position"])]["item_product_id"],
                                           stored[(i["combo_product_id"], i["position"])]["item_kind"],
                                           stored[(i["combo_product_id"], i["position"])]["price_share"])
               != (i["item_product_id"], i["item_kind"], i["price_share"])]
    if not dry_run:
        with conn.cursor() as cursor:
            if changes:
                cursor.executemany(
                    f"""INSERT INTO cdp.products AS p ({', '.join(COLUMNS)}) VALUES ({', '.join(['%s'] * len(COLUMNS))})
                        ON CONFLICT (product_id) DO UPDATE SET {', '.join(f'{c} = EXCLUDED.{c}' for c in MUTABLE)}""",
                    [[Jsonb(row[c]) if c == "attributes" else row[c] for c in COLUMNS] for row in changes])
            if relinks:
                cursor.executemany(
                    """UPDATE catalog.combo_items SET item_product_id = %s::uuid, item_kind = %s, price_share = %s
                       WHERE combo_product_id = %s::uuid AND position = %s""",
                    [(i["item_product_id"], i["item_kind"], i["price_share"], i["combo_product_id"], i["position"])
                     for i in relinks])
    if report_path is not None:
        report_path.write_text(json.dumps(result.report, ensure_ascii=False, indent=1), encoding="utf-8")
    mocks = list(result.products.values())
    return {"comboItems": len(result.items), "itemsMock": sum(1 for r in result.report if r["mock"]),
            "itemsReal": sum(1 for r in result.report if not r["mock"] and not r["included"]),
            "itemsIncluded": sum(1 for r in result.report if r["included"]),
            "mockProducts": sum(1 for r in mocks if r["available"]),
            "mockProductsClosed": sum(1 for r in mocks if not r["available"]),
            "productsChanged": len(changes), "comboItemsChanged": len(relinks),
            "written": 0 if dry_run else len(changes) + len(relinks)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sản phẩm cho mọi thành phần combo (demo:combo:*) + price_share.")
    parser.add_argument("--database-url-env", default="SEED_DATABASE_URL", help="tên biến môi trường chứa DSN")
    parser.add_argument("--as-of", type=date.fromisoformat, default=None, help="ngày đầu cửa sổ (mặc định: hôm nay giờ VN)")
    parser.add_argument("--dry-run", action="store_true", help="chỉ tính, không ghi")
    parser.add_argument("--report", type=Path, default=None, help="ghi quyết định từng thành phần ra file JSON")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--enable", action="store_true", help=f"bật kể cả khi {ENV}=0")
    group.add_argument("--disable", action="store_true", help="khoá mọi sản phẩm thành phần mô phỏng")
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
        counts = sync(conn, on, args.as_of, dry_run=args.dry_run, report_path=args.report)
    print(" · ".join(f"{k}={v}" for k, v in counts.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
