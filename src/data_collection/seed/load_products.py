"""Loader: products.jsonl (catalog đóng băng) → bản ghi `cdp.products` đã áp cửa sổ đặt chỗ 30 ngày, cộng `catalog.combo_items`.

Theo MOCK_DATA_SPEC §2 và file thiết kế DB của nhóm (20/09/2026). **Không sửa products.jsonl**; đầu ra là file để nạp vào DB.

    python -m data_collection.seed.load_products [--data-dir data] [--out-dir data/loader] [--as-of YYYY-MM-DD]

Quy tắc (--as-of mặc định là hôm nay; chạy lại trước demo để cuộn cửa sổ, nếu không toàn bộ catalog hết hạn). Tham số ở config.py.
  * cửa sổ = [as_of, as_of + 29];  available_from = GREATEST(nguồn_from, as_of),  available_to = LEAST(nguồn_to, as_of + 29);
    nguồn không có thì lấy nguyên cửa sổ. Nếu giao rỗng, đặt available = false và hai ngày DB = NULL để thỏa CHECK
    available_from <= available_to; ngày nguồn vẫn nằm trong attributes.sourceAvailableFrom/To.
  * vé máy bay: from = to = ngày bay. Ngày bay = ngày trip.com đã liệt kê (attributes.datesSeen) sớm nhất trong cửa sổ — trùng
    sourceAvailableFrom khi nó nằm trong cửa sổ; không có thì dời vào cửa sổ: as_of + crc32(productId) % 30.
    attributes.departureAt / arrivalAt đổi sang ngày đó, giữ giờ và thời lượng. Tuyến bay: from / to = ngày nhỏ nhất / lớn nhất của các chuyến con.
    Vé có báo giá ngày cố định (fixedDepartureDate, gồm khứ hồi): giữ ngày đi thật nếu trong cửa sổ, không thì dời như trên; hai chặng
    dời cùng số ngày, returnDate và ngày trong tên/mô tả đổi theo; ngày đã có cùng hành trình thì lùi sang ngày kế tiếp
    (PRD data-model §3, chỉ seed demo — job cào giữ ngày thật).
  * hạng phòng: available_from/to = nguyên cửa sổ, không cắt theo khoảng ngày của nguồn (chốt 02/10/2026).
  * attributes.availability = {"from": as_of, "days": 30, "calendar": <30 ký tự 1/0>} chỉ cho hạng phòng, điểm tham quan, golf:
    hạng phòng Vinpearl dùng lịch thật khi `pricesByDateQueried` phủ ít nhất 85% cửa sổ; dữ liệu thưa thì mở đủ 30 đêm.
    Điểm tham quan / golf toàn trống trừ 15% sản phẩm blackout 2–3 ngày. Ngày ngoài khoảng bán của nguồn luôn đóng (trừ hạng
    phòng, xem trên). Chuyến bay, property, tuyến, combo không có khoá này.
  * khách sạn (property) thiếu giờ thì gán checkInTime / checkOutTime mặc định.
  * combo: gán thêm attributes.priceBasis / nights / minPax từ combo_attributes.json (kết quả parse_combos.py).
Đầu ra: cdp_products.jsonl / .csv (cột snake_case như ERD), catalog_combo_items.jsonl, loader_report.md. Kết quả xác định.
"""
from __future__ import annotations

import argparse
import csv
import json
import shutil
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path

from . import config
from .catalog_meta import WINDOW_DAYS, build_meta, room_calendar, stable_order_key, ticket_calendar, variant, window

COLUMNS = ["product_id", "name", "taxonomy", "destination", "description", "attributes", "unit_price", "currency", "available",
           "available_from", "available_to", "image_url", "source_ref"]


def clip(src_from: str | None, src_to: str | None, lo: date, hi: date) -> tuple[str, str]:
    """available_from = GREATEST(nguồn_from, lo); available_to = LEAST(nguồn_to, hi); nguồn thiếu → lấy cả cửa sổ."""
    f = max(date.fromisoformat(src_from), lo) if src_from else lo
    t = min(date.fromisoformat(src_to), hi) if src_to else hi
    return f.isoformat(), t.isoformat()


def fixed_flight_window(attrs: dict, lo: date, hi: date) -> tuple[date, date]:
    try:
        departure = date.fromisoformat(str(attrs['departureAt'])[:10])
        expires = date.fromisoformat(attrs['priceValidUntil']) if attrs.get('priceValidUntil') else hi
    except (ValueError, KeyError):
        return lo, lo - timedelta(days=1)
    return max(lo, departure), min(hi, departure, expires if expires < lo else hi)


def pick_flight_date(product: dict, lo: date, hi: date) -> tuple[date, bool]:
    """(ngày bay, là ngày thật?). Ngày thật = ngày trip.com đã liệt kê nằm trong cửa sổ (sớm nhất; trùng sourceAvailableFrom khi nó nằm
    trong cửa sổ); không có thì dời vào cửa sổ: as_of + crc32(productId) % 30 (MOCK_DATA_SPEC §2.1)."""
    seen = sorted(d for d in product["attributes"].get("datesSeen") or [] if lo <= date.fromisoformat(d) <= hi)
    src = product.get("availableFrom")
    if not seen and src and lo <= date.fromisoformat(src) <= hi:
        seen = [src]
    if seen:
        return date.fromisoformat(seen[0]), True
    return lo + timedelta(days=stable_order_key(product["productId"]) % WINDOW_DAYS), False


def move_flight(attrs: dict, day: date) -> None:
    """Đổi ngày của departureAt / arrivalAt, giữ giờ (+07:00) và thời lượng."""
    dep, arr = attrs.get("departureAt"), attrs.get("arrivalAt")
    if not dep:
        return
    d0 = datetime.fromisoformat(dep)
    d1 = d0.replace(year=day.year, month=day.month, day=day.day)
    attrs["departureAt"] = d1.isoformat(timespec="seconds")
    if arr:
        attrs["arrivalAt"] = (d1 + (datetime.fromisoformat(arr) - d0)).isoformat(timespec="seconds")


def _departure_day(attrs: dict) -> date | None:
    try:
        return date.fromisoformat(str(attrs['departureAt'])[:10])
    except (ValueError, KeyError):
        return None


def itinerary(attrs: dict) -> tuple:
    """Hành trình cố định (tuyến, số hiệu và giờ hai chặng, số ngày lưu trú, ngày đi gốc), không gồm hạng vé: các hạng của cùng
    hành trình dời cùng một ngày để fareClasses vẫn gom được."""
    back = attrs.get('returnFlight') if isinstance(attrs.get('returnFlight'), dict) else {}
    return (attrs.get('parentProductId'), attrs.get('tripType'), attrs.get('flightNumber'), back.get('flightNumber'),
            str(attrs.get('departureAt'))[11:16], attrs.get('stayDays'), str(attrs.get('departureAt'))[:10])


def seed_fixed_flight_date(product_id: str, attrs: dict, lo: date, hi: date,
                           taken: dict | None = None) -> tuple[date | None, bool | None]:
    """Seed demo (PRD data-model §3): vé có báo giá ngày cố định giữ ngày đi thật nếu nằm trong cửa sổ, không thì dời vào cửa sổ
    như vé không cố định ngày (as_of + crc32(productId) % 30; `product_id` là ID đại diện của hành trình). Ô (hành trình, ngày)
    đã có hành trình khác cùng chuyến thì lùi sang ngày kế tiếp. Không xét priceValidUntil: vé seed vẫn đặt được, fareClasses báo
    EXPIRED. Job cào (fresh_catalog_db.apply_window) dùng cùng hàm này (PRD data-model §3.1, chốt 06/10)."""
    departure = _departure_day(attrs)
    if departure is None:
        return None, None
    if lo <= departure <= hi:
        return departure, True
    trip = itinerary(attrs)
    taken = taken if taken is not None else {}
    offset = stable_order_key(product_id) % WINDOW_DAYS
    for step in range(WINDOW_DAYS):
        day = lo + timedelta(days=(offset + step) % WINDOW_DAYS)
        if taken.get(trip[:-1] + (day,), trip) == trip:
            break
    taken[trip[:-1] + (day,)] = trip
    return day, False


def shift_fixed_flight(attrs: dict, day: date, name: str, description: str) -> tuple[str, str]:
    """Dời hai chặng cùng số ngày (giữ giờ bay và stayDays); returnDate và ngày ghi trong tên/mô tả đổi theo."""
    old_out = str(attrs['departureAt'])[:10]
    delta = day - date.fromisoformat(old_out)
    move_flight(attrs, day)
    renamed = {old_out: day.isoformat()}
    back = attrs.get('returnFlight')
    if isinstance(back, dict) and back.get('departureAt'):
        move_flight(back, date.fromisoformat(str(back['departureAt'])[:10]) + delta)
    if attrs.get('returnDate'):
        new_return = (date.fromisoformat(attrs['returnDate']) + delta).isoformat()
        renamed[attrs['returnDate']] = new_return
        attrs['returnDate'] = new_return
    for i, old in enumerate(renamed):  # hai bước qua chuỗi tạm: ngày mới của chặng này có thể trùng ngày cũ của chặng kia
        name, description = name.replace(old, f"\0{i}\0"), description.replace(old, f"\0{i}\0")
    for i, new in enumerate(renamed.values()):
        name, description = name.replace(f"\0{i}\0", new), description.replace(f"\0{i}\0", new)
    return name, description


def zero_outside(calendar: str, as_of: date, f: str, t: str) -> str:
    """Các ngày ngoài [available_from, available_to] không đặt được."""
    lo, hi = date.fromisoformat(f), date.fromisoformat(t)
    return "".join(c if lo <= as_of + timedelta(days=i) <= hi else "0" for i, c in enumerate(calendar))


def real_room_calendar(prices_by_date: dict | None, dates_queried: list | None, as_of: date,
                       min_coverage: float = 0.85) -> str | None:
    """Build a real 30-day room calendar only from a sufficiently dense Vinpearl sweep.

    A queried day with a positive price is open; a queried day without one is closed. Unqueried
    days must never be interpreted as sold out, so sparse samples fall back to the deterministic
    demo calendar. At 85%, a 30-day window needs at least 26 queried dates.
    """
    if not dates_queried:
        return None
    queried = {d for d in dates_queried if 0 <= (date.fromisoformat(d) - as_of).days < WINDOW_DAYS}
    if len(queried) < min_coverage * WINDOW_DAYS:
        return None
    priced = {d for d, value in (prices_by_date or {}).items() if value is not None and value > 0}
    return "".join("1" if (as_of + timedelta(days=i)).isoformat() in priced else "0" for i in range(WINDOW_DAYS))


def convert(rows: list[dict], combo_attrs: dict[str, dict], as_of: date,
            real_flight_dates: bool = False) -> tuple[list[dict], dict]:
    """`real_flight_dates`: job cào nạp dữ liệu thật (daily.py) — vé báo giá ngày cố định giữ ngày thật, ngoài cửa sổ hoặc hết hạn
    báo giá thì không đặt được, như fresh_catalog_db.apply_window. Mặc định (seed demo): dời vào cửa sổ (PRD data-model §3)."""
    lo, hi = window(as_of)
    stats: Counter = Counter()
    out: dict[str, dict] = {}
    flight_dates: dict[str, list[str]] = {}
    closed_frac: list[float] = []
    meta = build_meta(rows)
    by_id = {r["productId"]: r for r in rows}
    fixed = [r for r in rows if variant(r) == "flight" and r["attributes"].get("fixedDepartureDate")]
    # Vé ngày cố định giữ ngày thật được giữ chỗ trước; các hạng của cùng hành trình dời theo ID nhỏ nhất của nhóm.
    taken = {itinerary(r["attributes"])[:-1] + (d,): itinerary(r["attributes"]) for r in fixed
             for d in [_departure_day(r["attributes"])] if d is not None and lo <= d <= hi}
    trip_ids: dict[tuple, str] = {}
    for r in fixed:
        trip = itinerary(r["attributes"])
        trip_ids[trip] = min(trip_ids.get(trip, r["productId"]), r["productId"])
    for r in rows:
        v = variant(r)
        attrs = json.loads(json.dumps(r["attributes"], ensure_ascii=False))
        if r["availableFrom"] is not None:
            attrs["sourceAvailableFrom"] = r["availableFrom"]
        if r["availableTo"] is not None:
            attrs["sourceAvailableTo"] = r["availableTo"]
        # Hạng phòng: nguyên cửa sổ, không cắt theo ngày nguồn (ngày nguồn chỉ là ngày đã hỏi giá; giá dùng làm giá tham khảo).
        f, t = (lo.isoformat(), hi.isoformat()) if v == "hotel_room" else clip(r["availableFrom"], r["availableTo"], lo, hi)
        available = bool(r["available"])
        name, description = r["name"], r["description"]
        if v == "flight" and attrs.get('fixedDepartureDate') and real_flight_dates:
            start, end = fixed_flight_window(attrs, lo, hi)
            f, t = start.isoformat(), end.isoformat()
            if start <= end:
                flight_dates.setdefault(attrs.get('parentProductId') or '', []).append(f)
            stats['chuyến bay: báo giá ngày cố định (ngày thật, job cào)'] += 1
        elif v == "flight" and attrs.get('fixedDepartureDate'):
            day, real = seed_fixed_flight_date(trip_ids.get(itinerary(attrs), r["productId"]), attrs, lo, hi, taken)
            if day is None:  # thiếu/sai departureAt: không đặt được như trước
                f, t = lo.isoformat(), (lo - timedelta(days=1)).isoformat()
            else:
                if not real:
                    name, description = shift_fixed_flight(attrs, day, name, description)
                f = t = day.isoformat()
                flight_dates.setdefault(attrs.get('parentProductId') or '', []).append(f)
            stats['chuyến bay: báo giá ngày cố định (ngày thật)'] += bool(real)
            stats['chuyến bay: báo giá ngày cố định (dời vào cửa sổ)'] += real is False
        elif v == "flight":
            day, real = pick_flight_date(r, lo, hi)
            f = t = day.isoformat()
            move_flight(attrs, day)
            flight_dates.setdefault(attrs.get("parentProductId") or "", []).append(f)
            stats["chuyến bay: ngày thật"] += real
            stats["chuyến bay: ngày mock (không có ngày thật trong cửa sổ)"] += not real
        elif v in ("hotel_room", "attraction", "golf"):
            real_cal = real_room_calendar(attrs.get("pricesByDate"), attrs.get("pricesByDateQueried"), as_of) if v == "hotel_room" else None
            cal = real_cal if real_cal is not None else (room_calendar(r, as_of, by_id) if v == "hotel_room" else ticket_calendar(r["productId"], as_of))
            cal = zero_outside(cal, as_of, f, t) if f <= t else "0" * WINDOW_DAYS
            attrs["availability"] = {"from": as_of.isoformat(), "days": WINDOW_DAYS, "calendar": cal}
            if v == "hotel_room":
                closed_frac.append(cal.count("0") / WINDOW_DAYS)
            stats[f"lịch khả dụng: {v}" + (" (dữ liệu thật)" if real_cal is not None else "")] += 1
        elif v == "hotel_property":
            for key, default in (("checkInTime", config.HOTEL_CHECK_IN), ("checkOutTime", config.HOTEL_CHECK_OUT)):
                if not attrs.get(key):
                    attrs[key] = default
                    stats[f"khách sạn: gán {key} mặc định"] += 1
        if v == "combo" and r["productId"] in combo_attrs:
            attrs.update(combo_attrs[r["productId"]]["attributes"])
            stats["combo gán priceBasis/nights/minPax"] += 1
        out[r["productId"]] = {"product_id": r["productId"], "name": name, "taxonomy": r["taxonomy"], "destination": r["destination"],
                               "description": description, "attributes": attrs, "unit_price": r["unitPrice"], "currency": r["currency"],
                               "available": available, "available_from": f, "available_to": t, "image_url": r["imageUrl"],
                               "source_ref": r["sourceRef"], "_variant": v}
    for pid, p in out.items():  # tuyến bay: khoảng của các chuyến con
        if p["_variant"] == "flight_route" and flight_dates.get(pid):
            p["available_from"], p["available_to"] = min(flight_dates[pid]), max(flight_dates[pid])
            stats["tuyến bay: khoảng lấy từ các chuyến con"] += 1
    for p in out.values():
        if p["available_from"] > p["available_to"]:
            source_to = p["available_to"]
            if p["available"]:
                stats["đổi available=false vì from > to sau khi cắt"] += 1
                if len(stats_examples) < 5:
                    stats_examples.append(f"{p['name'][:60]} (không giao cửa sổ; mốc cắt {source_to})")
            p["available"] = False
            p["available_from"] = p["available_to"] = None
        elif p["_variant"] not in ("flight", "flight_route") and (p["available_from"] > lo.isoformat() or p["available_to"] < hi.isoformat()):
            stats["khoảng bị cắt hẹp hơn cửa sổ (theo khoảng bán của nguồn)"] += 1
    # PRD FR-CAT-02 (chốt 06/10): khách sạn tổng quan không có hạng phòng con đặt được → available = false (như job cào).
    bookable = {p["attributes"].get("parentProductId") for p in out.values()
                if p["_variant"] == "hotel_room" and p["available"] and p["unit_price"] is not None
                and p["attributes"].get("ticketed") is not False}
    for pid, p in out.items():
        if p["_variant"] == "hotel_property" and p["available"] and pid not in bookable:
            p["available"] = False
            p["attributes"]["noBookableRoom"] = True
            stats["khách sạn không có phòng đặt được → available=false"] += 1
    stats["hạng phòng: tỷ lệ đêm kín trung bình (%)"] = round(100 * sum(closed_frac) / max(1, len(closed_frac)))
    stats["available=true"] = sum(1 for p in out.values() if p["available"])
    stats["is_bookable"] = sum(1 for m in meta.values() if m["is_bookable"])
    stats["is_search_unit"] = sum(1 for m in meta.values() if m["is_search_unit"])
    stats["is_recommendable"] = sum(1 for m in meta.values() if m["is_recommendable"])
    return [{k: v for k, v in p.items() if k != "_variant"} for p in out.values()], dict(stats)


stats_examples: list[str] = []


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir", type=Path, default=Path("data"))
    ap.add_argument("--out-dir", type=Path, default=None)
    ap.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    ap.add_argument("--real-flight-dates", action="store_true",
                    help="job cào (dữ liệu thật): không dời vé báo giá ngày cố định, khoá vé hết hạn báo giá")
    a = ap.parse_args(argv)
    d, out_dir = a.data_dir, a.out_dir or a.data_dir / "loader"
    stats_examples.clear()
    with open(d / "products.jsonl", encoding="utf-8") as f:
        rows = [json.loads(l) for l in f if l.strip()]
    combo_attrs = {}
    if (d / "combo_attributes.json").exists():
        combo_attrs = json.loads((d / "combo_attributes.json").read_text(encoding="utf-8"))
    products, stats = convert(rows, combo_attrs, a.as_of, real_flight_dates=a.real_flight_dates)
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "cdp_products.jsonl", "w", encoding="utf-8") as f:
        for p in products:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    with open(out_dir / "cdp_products.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(COLUMNS)
        for p in products:
            w.writerow([json.dumps(p[c], ensure_ascii=False) if c == "attributes"
                        else (str(p[c]).lower() if isinstance(p[c], bool) else ("" if p[c] is None else p[c])) for c in COLUMNS])
    if (d / "combo_items.jsonl").exists():
        shutil.copyfile(d / "combo_items.jsonl", out_dir / "catalog_combo_items.jsonl")
    lo, hi = window(a.as_of)
    kinds = Counter(variant(r) for r in rows)
    report = [f"# Kết quả loader — cửa sổ {lo.isoformat()} … {hi.isoformat()} (as_of {a.as_of.isoformat()})", "",
              f"- Dòng nạp vào `cdp.products`: **{len(products)}** ({', '.join(f'{k} {v}' for k, v in kinds.most_common())})",
              *[f"- {k}: {v}" for k, v in sorted(stats.items())]]
    if stats_examples:
        report += ["", "Ví dụ dòng bị đổi `available=false`: " + "; ".join(stats_examples)]
    report += ["", "Chạy lại với `--as-of` mới trước demo để cuộn cửa sổ. `products.jsonl` không bị sửa; đầu ra tuân theo DDL chính thức ở `db/vota_schema.sql`."]
    (out_dir / "loader_report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print("\n".join(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
