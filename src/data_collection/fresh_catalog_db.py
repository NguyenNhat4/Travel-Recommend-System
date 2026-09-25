"""Non-destructive daily catalog refresh for V-OTA's cdp.products table.

The source of every price is the current crawl's products.jsonl. Existing catalog
rows are read only to preserve static fields and identify missing Trip room IDs.
No seed history, synthetic availability calendar, or older price is an input.
"""
from __future__ import annotations

import copy
import json
import re
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from collectors.common import read_jsonl
from normalise import PRODUCT_FIELDS as FIELDS, product_id


def validate_catalog(products: list[dict], *, allow_external_parents: bool = False) -> None:
    ids, refs = set(), set()
    for row in products:
        if tuple(row) != FIELDS or row['productId'] != product_id(row['sourceRef']):
            raise ValueError('Catalog thiếu 13 trường đúng thứ tự hoặc productId sai')
        if row['productId'] in ids or row['sourceRef'] in refs:
            raise ValueError('Catalog trùng productId/sourceRef')
        if not row['name'] or not row['destination'] or not row['description'] or row['currency'] != 'VND':
            raise ValueError('Catalog thiếu thông tin hiển thị hoặc currency sai')
        ids.add(row['productId'])
        refs.add(row['sourceRef'])
    if not allow_external_parents:
        for row in products:
            parent = row['attributes'].get('parentProductId')
            if parent and parent not in ids:
                raise ValueError(f"{row['sourceRef']}: thiếu parentProductId")

PRICE_KEYS = ("pricesByDate", "pricesByDateQueried", "availabilityByDate",
              "priceDate", "priceNights", "priceAdults", "otaPrices", "inventoryByDate")
ROOM_REF = re.compile(r"^trip:hotel:(\d+):room:[^:]+$")
PROPERTY_REF = re.compile(r"^trip:hotel:(\d+)$")
COLUMNS = ("product_id", "name", "taxonomy", "destination", "description", "attributes",
           "unit_price", "currency", "available", "available_from", "available_to",
           "image_url", "source_ref")


def checked_trip_hotels(coverage_path: Path) -> set[str]:
    """Return hotels whose every stay-date has a real price or explicit sold-out JSON."""
    coverage = json.loads(coverage_path.read_text(encoding="utf-8"))
    stays = {row["checkin"] for row in coverage["stays"]}
    if not stays or len(stays) != len(coverage["stays"]):
        raise ValueError("Danh sách ngày giá rỗng hoặc trùng")
    grouped: dict[str, dict[str, str]] = {}
    for row in coverage["results"]:
        hotel_id, day = str(row["hotelId"]), row["checkin"]
        if day in grouped.setdefault(hotel_id, {}):
            raise ValueError(f"Trùng hotel-ngày trong báo cáo giá: {hotel_id}@{day}")
        grouped[hotel_id][day] = row["status"]
    if not grouped or len(grouped) != coverage["requestedHotels"]:
        raise ValueError("Báo cáo giá Trip.com thiếu khách sạn")
    if any(set(days) != stays for days in grouped.values()):
        raise ValueError("Báo cáo giá Trip.com thiếu ngày hoặc có ngày lạ")
    checked = {hotel_id for hotel_id, days in grouped.items()
               if all(status in ("priced", "sold_out") for status in days.values())}
    failed = {f"{hotel_id}@{day}" for hotel_id, days in grouped.items()
              for day, status in days.items() if status not in ("priced", "sold_out")}
    if failed != set(coverage.get("unpricedHotelDates") or []):
        raise ValueError("Danh sách hotel-ngày chưa xác nhận không khớp báo cáo")
    if coverage.get("partialAllowed"):
        if not checked or set(coverage.get("completedHotels") or []) != checked:
            raise ValueError("Không có khách sạn hoàn tất hoặc completedHotels không khớp")
    elif failed:
        raise ValueError("Trip.com còn hotel-ngày chưa xác nhận giá/hết phòng; dừng nạp DB")
    return checked


def price_attributes(fresh: dict, previous: dict | None, seen_at: str) -> dict:
    incoming = fresh["attributes"]
    attrs = copy.deepcopy(previous if previous is not None else incoming)
    for key in PRICE_KEYS:
        attrs.pop(key, None)
    # The seed loader may have supplied a synthetic 30-day availability calendar.
    # Sparse 14/30/60 samples cannot prove the unqueried days are open or closed.
    attrs.pop("availability", None)
    attrs.pop("missingSince", None)
    attrs.pop("priceFreshness", None)
    if incoming.get("sameAs"):
        attrs["sameAs"] = list(dict.fromkeys((attrs.get("sameAs") or []) + incoming["sameAs"]))
    for key in PRICE_KEYS:
        if key in incoming:
            attrs[key] = copy.deepcopy(incoming[key])
    source_fields = copy.deepcopy(attrs.get("fieldSources") or {})
    new_source = (incoming.get("fieldSources") or {}).get("unitPrice")
    if new_source:
        source_fields["unitPrice"] = new_source
    else:
        source_fields.pop("unitPrice", None)
    if source_fields:
        attrs["fieldSources"] = source_fields
    else:
        attrs.pop("fieldSources", None)
    queried = sorted(set(attrs.get("pricesByDateQueried") or []))
    if queried:
        priced = attrs.get("pricesByDate") or {}
        attrs["pricesByDateQueried"] = queried
        attrs["availabilityByDate"] = {day: bool(priced.get(day)) for day in queried}
    attrs["lastSeenAt"] = seen_at
    attrs["priceRefreshedAt"] = datetime.now(timezone.utc).isoformat()
    return attrs


def trip_price_reference(row: dict):
    """Only expire offers whose current price belongs to Trip, including aliases."""
    attrs = row.get("attributes") or {}
    source = (attrs.get("fieldSources") or {}).get("unitPrice")
    if source and source not in {"trip.com", "trip"}:
        return None, None
    refs = [row["source_ref"]]
    if source in {"trip.com", "trip"}:
        refs.extend(attrs.get("sameAs") or [])
    for ref in refs:
        room = ROOM_REF.fullmatch(ref)
        prop = PROPERTY_REF.fullmatch(ref)
        if room or prop:
            return room, prop
    return None, None


def prepare_rows(fresh: list[dict], existing: list[dict], checked_hotels: set[str],
                 seen_at: str, *, trip_max_age_days: int = 7,
                 now: datetime | None = None) -> tuple[list[dict], dict[str, int]]:
    """Preserve DB static columns, update live fields, insert newly seen rooms."""
    if trip_max_age_days < 1:
        raise ValueError("trip_max_age_days phải >= 1")
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=trip_max_age_days)
    validate_catalog(fresh, allow_external_parents=True)
    old = {str(row["product_id"]): row for row in existing}
    by_ref = {}
    for previous in existing:
        for ref in [previous["source_ref"], *((previous["attributes"] or {}).get("sameAs") or [])]:
            if ref in by_ref and by_ref[ref]["product_id"] != previous["product_id"]:
                raise ValueError(f"sourceRef/sameAs conflict: {ref}")
            by_ref[ref] = previous
    # The full catalog may have merged a Trip hotel/room into a Booking row.
    # Resolve by sameAs, then reparent new Trip rooms to the retained DB ID.
    mapped_ids = {item["productId"]: str(by_ref[item["sourceRef"]]["product_id"])
                  for item in fresh if item["sourceRef"] in by_ref}
    canonical_refs = set()
    result = []
    counts = {"new": 0, "newRooms": 0, "refreshed": 0, "missingRooms": 0, "missingProperties": 0, "staleTrip": 0}
    for item in fresh:
        original_ref = item["sourceRef"]
        previous = by_ref.get(original_ref)
        pid = mapped_ids.get(item["productId"], item["productId"])
        if pid in old and not previous:
            raise ValueError(f"ID conflict for {pid}: sourceRef changed")
        attrs = price_attributes(item, previous["attributes"] if previous else None, seen_at)
        # Khoảng ngày của nguồn trong lượt này; apply_window cắt nó vào cửa sổ 30 ngày như seed.
        for key, value in (("sourceAvailableFrom", item["availableFrom"]), ("sourceAvailableTo", item["availableTo"])):
            if value is None:
                attrs.pop(key, None)
            else:
                attrs[key] = value
        parent = attrs.get("parentProductId")
        if parent in mapped_ids:
            attrs["parentProductId"] = mapped_ids[parent]
        row = {snake: item[camel] for snake, camel in zip(COLUMNS, FIELDS)}
        row["product_id"] = pid
        row["source_ref"] = previous["source_ref"] if previous else original_ref
        row["attributes"] = attrs
        if row["source_ref"] in canonical_refs:
            raise ValueError(f"Trùng canonical sourceRef: {row['source_ref']}")
        canonical_refs.add(row["source_ref"])
        if previous:
            counts["refreshed"] += 1
            # SQL UPDATE below only writes attributes, price, available and the booking window.
        else:
            counts["new"] += 1
            counts["newRooms"] += item["taxonomy"] == "hotel" and item["attributes"].get("level") == "room"
        result.append(row)
    represented = {str(row["product_id"]) for row in result}
    for previous in existing:
        room_match, property_match = trip_price_reference(previous)
        match = room_match or property_match
        if not match or match.group(1) not in checked_hotels or previous["source_ref"] in canonical_refs:
            continue
        attrs = copy.deepcopy(previous["attributes"])
        attrs.pop("availability", None)
        for key in PRICE_KEYS:
            attrs.pop(key, None)
        attrs.setdefault("missingSince", seen_at)
        attrs["priceFreshness"] = "missing_from_live_response"
        attrs["priceRefreshedAt"] = datetime.now(timezone.utc).isoformat()
        row = dict(previous, attributes=attrs, unit_price=None, available=False)
        result.append(row)
        counts["missingRooms" if room_match else "missingProperties"] += 1
        represented.add(str(previous["product_id"]))
    # Rotation can take more than one day. Never leave native Trip prices and
    # availability marked live after their last successful capture ages out.
    for previous in existing:
        if (str(previous["product_id"]) in represented
                or (previous.get("attributes") or {}).get("priceFreshness") == "stale"
                or not any(trip_price_reference(previous))):
            continue
        attrs = previous["attributes"] or {}
        refreshed = attrs.get("priceRefreshedAt")
        try:
            refreshed_at = datetime.fromisoformat(refreshed.replace("Z", "+00:00"))
            if refreshed_at.tzinfo is None:
                refreshed_at = refreshed_at.replace(tzinfo=timezone.utc)
        except (AttributeError, ValueError):
            refreshed_at = datetime.min.replace(tzinfo=timezone.utc)
        if refreshed_at >= cutoff:
            continue
        expired = copy.deepcopy(attrs)
        expired.pop("availability", None)
        for key in PRICE_KEYS:
            expired.pop(key, None)
        sources = expired.get("fieldSources") or {}
        if sources:
            sources = copy.deepcopy(sources)
            sources.pop("unitPrice", None)
            expired["fieldSources"] = sources
        expired["priceFreshness"] = "stale"
        result.append(dict(previous, attributes=expired, unit_price=None, available=False))
        counts["staleTrip"] += 1
    return result, counts


CALENDAR_VARIANTS = ("hotel_room", "attraction", "golf")


def _seed_rules():
    """Dùng lại đúng hàm cửa sổ và lịch của seed (MOCK_DATA_SPEC §2 bước 1–2) thay vì chép lại quy tắc."""
    source_root = str(Path(__file__).resolve().parent.parent)
    if source_root not in sys.path:
        sys.path.insert(0, source_root)
    from data_collection.seed import catalog_meta, load_products
    return catalog_meta, load_products


def _as_date(value) -> date | None:
    return date.fromisoformat(value) if isinstance(value, str) else value


def _with_observed(calendar: str, attrs: dict, as_of: date) -> str:
    """Ngày đã hỏi giá nằm trong cửa sổ ghi theo kết quả thật: có giá = 1, hết phòng = 0."""
    marks, priced = list(calendar), attrs.get("pricesByDate") or {}
    for day in attrs.get("pricesByDateQueried") or []:
        index = (date.fromisoformat(day) - as_of).days
        if 0 <= index < len(marks):
            value = priced.get(day)
            marks[index] = "1" if value is not None and value > 0 else "0"
    return "".join(marks)


def _calendar(kind: str, row: dict, view: dict, views: dict, as_of: date, meta, loader) -> str:
    """Lịch 30 ký tự như seed; dòng chưa khả dụng (hết bán, giá quá hạn, ngoài cửa sổ) đóng cả 30 ngày."""
    if not row["available"] or row["available_from"] is None:
        return "0" * meta.WINDOW_DAYS
    attrs = row["attributes"]
    if kind == "hotel_room":
        calendar = loader.real_room_calendar(attrs.get("pricesByDate"), attrs.get("pricesByDateQueried"), as_of)
        if calendar is None:  # dữ liệu hỏi thưa: lịch mô phỏng của seed, cộng các ngày mẫu đã biết
            calendar = _with_observed(meta.room_calendar(view, as_of, views), attrs, as_of)
    else:
        calendar = meta.ticket_calendar(view["productId"], as_of)
    return loader.zero_outside(calendar, as_of, row["available_from"].isoformat(), row["available_to"].isoformat())


def apply_window(rows: list[dict], as_of: date) -> dict[str, dict]:
    """Cửa sổ đặt chỗ và lịch 30 ngày cho toàn catalog, như seed (DATABASE_SCHEMA.md #13, MOCK_DATA_SPEC.md §2).

    available_from/to = khoảng nguồn `attributes.sourceAvailableFrom/To` cắt vào [as_of, as_of + 29]; nguồn không
    có thì lấy cả cửa sổ. Chuyến bay: from = to = ngày bay (ngày đã thấy trong cửa sổ, không có thì dời vào cửa sổ
    theo crc32), giờ bay đổi theo. Tuyến: min/max ngày của các chuyến con. Giao rỗng thì available = false và hai
    ngày = NULL. Không bật lại dòng đang available = false: nguồn còn bán thì lượt cào sau ghi lại.
    Hạng phòng, điểm tham quan, golf có `attributes.availability` phủ đúng cửa sổ (xem `_calendar`).
    Trả về các dòng có thay đổi, theo product_id.
    """
    meta, loader = _seed_rules()
    lo, hi = meta.window(as_of)
    before = {str(row["product_id"]): row for row in rows}
    views = {pid: {"productId": pid, "sourceRef": row["source_ref"], "attributes": row["attributes"] or {}}
             for pid, row in before.items()}
    after: dict[str, dict] = {}
    kinds: dict[str, str] = {}
    flight_days: dict[str, list[date]] = defaultdict(list)
    for pid, row in before.items():
        attrs = row["attributes"] or {}
        kinds[pid] = meta.variant({"taxonomy": row["taxonomy"], "attributes": attrs})
        start, end = (date.fromisoformat(day) for day in
                      loader.clip(attrs.get("sourceAvailableFrom"), attrs.get("sourceAvailableTo"), lo, hi))
        if kinds[pid] == "flight":
            start, _ = loader.pick_flight_date({"productId": pid, "availableFrom": attrs.get("sourceAvailableFrom"),
                                                "attributes": attrs}, lo, hi)
            end = start
            attrs = copy.deepcopy(attrs)
            loader.move_flight(attrs, start)
            flight_days[attrs.get("parentProductId") or ""].append(start)
        after[pid] = dict(row, attributes=attrs, available_from=start, available_to=end)
    changed = {}
    for pid, row in after.items():
        if kinds[pid] == "flight_route" and flight_days.get(pid):
            row["available_from"], row["available_to"] = min(flight_days[pid]), max(flight_days[pid])
        if row["available_from"] > row["available_to"]:
            row.update(available=False, available_from=None, available_to=None)
        if kinds[pid] in CALENDAR_VARIANTS:
            calendar = _calendar(kinds[pid], row, views[pid], views, as_of, meta, loader)
            row["attributes"] = dict(row["attributes"], availability={
                "from": as_of.isoformat(), "days": meta.WINDOW_DAYS, "calendar": calendar})
        old = before[pid]
        if ((row["available"], row["available_from"], row["available_to"], row["attributes"])
                != (old["available"], _as_date(old["available_from"]), _as_date(old["available_to"]),
                    old["attributes"] or {})):
            changed[pid] = row
    return changed


def maintain_catalog(url: str, *, today: date | None = None, now: datetime | None = None) -> dict[str, int]:
    """Transaction riêng ở đầu mỗi lượt, chạy cả khi mọi nguồn lỗi: hết hạn giá Trip quá hạn và cuộn cửa sổ 30 ngày."""
    import psycopg
    from psycopg.types.json import Jsonb
    today = today or date.today()
    with psycopg.connect(url, row_factory=psycopg.rows.dict_row) as conn:
        conn.execute("SELECT pg_advisory_xact_lock(7791024)")
        existing = conn.execute("SELECT * FROM cdp.products").fetchall()
        expired, counts = prepare_rows([], existing, set(), today.isoformat(), now=now)
        state = {str(row["product_id"]): row for row in existing}
        state.update((str(row["product_id"]), row) for row in expired)
        windowed = apply_window(list(state.values()), today)
        writes = {str(row["product_id"]): row for row in expired}
        writes.update(windowed)
        with conn.cursor() as cursor:
            cursor.executemany(
                """UPDATE cdp.products SET attributes = %s, unit_price = %s, available = %s,
                       available_from = %s, available_to = %s
                   WHERE product_id = %s""",
                [(Jsonb(row["attributes"]), row["unit_price"], row["available"], row["available_from"],
                  row["available_to"], row["product_id"]) for row in writes.values()])
    return {"staleTrip": counts["staleTrip"], "windowRows": len(windowed)}


def load_into_db(products_path: Path, coverage_path: Path, url: str,
                 collection_root: Path) -> dict[str, int]:
    """COPY into a temporary table then upsert in one transaction, as V-OTA does."""
    import psycopg
    source_root = collection_root.parent
    if str(source_root) not in sys.path:
        sys.path.insert(0, str(source_root))
    from data_collection.seed.database import COMBO, copy_rows
    from data_collection.seed import parse_combos

    fresh = list(read_jsonl(products_path))
    checked = checked_trip_hotels(coverage_path)
    for item in fresh:
        match = re.match(r"^trip:hotel:(\d+)(?::room:.*)?$", item["sourceRef"])
        if match and match.group(1) not in checked:
            raise ValueError(f"Trip hotel chưa đủ coverage: {item['sourceRef']}")
    # Parse combo relationships with the same implementation as the source repo.
    parse_combos.main(["--data-dir", str(products_path.parent)])
    combo_attrs = json.loads((products_path.parent / "combo_attributes.json").read_text(encoding="utf-8"))
    for item in fresh:
        if item["taxonomy"] == "combo" and item["productId"] in combo_attrs:
            item["attributes"].update(combo_attrs[item["productId"]]["attributes"])
    combos = list(read_jsonl(products_path.parent / "combo_items.jsonl"))
    seen_at = date.today().isoformat()
    with psycopg.connect(url) as conn:
        conn.execute("SELECT pg_advisory_xact_lock(7791024)")
        with conn.cursor(row_factory=psycopg.rows.dict_row) as cursor:
            cursor.execute("SELECT * FROM cdp.products")
            existing = cursor.fetchall()
        prepared, counts = prepare_rows(fresh, existing, checked, seen_at)
        # Cửa sổ 30 ngày tính trên trạng thái sau lượt này: dòng mới/làm mới, và tuyến có chuyến con đổi ngày.
        state = {str(row["product_id"]): row for row in existing}
        state.update((str(row["product_id"]), row) for row in prepared)
        windowed = apply_window(list(state.values()), date.fromisoformat(seen_at))
        # Giữ thứ tự: canonical_ids bên dưới ánh xạ fresh[i] với prepared[i].
        prepared = [windowed.pop(str(row["product_id"]), row) for row in prepared]
        prepared.extend(windowed.values())
        # Combo parser sees IDs from this run. Existing DB aliases can retain an
        # older canonical productId, so map both ends before FK validation.
        canonical_ids = {item["productId"]: prepared[index]["product_id"]
                         for index, item in enumerate(fresh)}
        for combo in combos:
            combo["combo_product_id"] = canonical_ids.get(
                combo["combo_product_id"], combo["combo_product_id"])
            if combo.get("item_product_id"):
                combo["item_product_id"] = canonical_ids.get(
                    combo["item_product_id"], combo["item_product_id"])
        conn.execute("CREATE TEMP TABLE incoming_products (LIKE cdp.products INCLUDING DEFAULTS) ON COMMIT DROP")
        copy_rows(conn, "incoming_products", list(COLUMNS), prepared)
        cols = ", ".join(COLUMNS)
        changed = " OR ".join(f"p.{c} IS DISTINCT FROM EXCLUDED.{c}" for c in
                              ("attributes", "unit_price", "available", "available_from", "available_to"))
        written = conn.execute(f"""
            INSERT INTO cdp.products AS p ({cols}) SELECT {cols} FROM incoming_products WHERE true
            ON CONFLICT (product_id) DO UPDATE SET
                attributes = EXCLUDED.attributes,
                unit_price = EXCLUDED.unit_price,
                available = EXCLUDED.available,
                available_from = EXCLUDED.available_from,
                available_to = EXCLUDED.available_to
            WHERE {changed}
            RETURNING product_id
        """).fetchall()
        combo_ids = [canonical_ids[row["productId"]] for row in fresh if row["taxonomy"] == "combo"]
        if combo_ids:
            conn.execute("DELETE FROM catalog.combo_items WHERE combo_product_id = ANY(%s::uuid[])", (combo_ids,))
            copy_rows(conn, "catalog.combo_items", COMBO, combos)
        counts["dbRowsWritten"] = len(written)
        counts["comboItemsWritten"] = len(combos)
    return counts
