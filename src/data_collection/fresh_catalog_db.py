"""Non-destructive daily catalog refresh for V-OTA's cdp.products table.

The source of every price is the current crawl's products.jsonl. Existing catalog
rows are read only to preserve static fields and identify missing Trip room IDs.
No seed history, synthetic availability calendar, or older price is an input.
"""
from __future__ import annotations

import copy
import json
import re
import shutil
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from collectors.common import read_jsonl
from collectors.textutil import fold, trip_combo_dates
from normalise import PRODUCT_FIELDS as FIELDS, product_id
from stage_log import Stages


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
    attrs.pop("windowClosed", None)  # `available` của lượt này do nguồn quyết định; apply_window đánh dấu lại nếu cần
    if incoming.get("sameAs"):
        attrs["sameAs"] = list(dict.fromkeys((attrs.get("sameAs") or []) + incoming["sameAs"]))
    if fresh.get("taxonomy") == "flight":
        # Legacy IDs only gain tripType; fixed-date variants carry a distinct sourceRef.
        keys = ("tripType",) if not incoming.get("fixedDepartureDate") else (
            "tripType", "cabinClass", "fixedDepartureDate", "returnFlight", "returnDate", "stayDays",
            "departureAt", "arrivalAt", "priceBasis", "priceValidUntil", "priceObservedAt", "priceContext")
        for key in keys:
            if key in incoming:
                attrs[key] = copy.deepcopy(incoming[key])
        if incoming.get("fixedDepartureDate") and "priceValidUntil" not in incoming:
            attrs.pop("priceValidUntil", None)  # a newer quote without a validity must not inherit the old expiry
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
                 now: datetime | None = None, quarantine: list[dict] | None = None) -> tuple[list[dict], dict[str, int]]:
    """Preserve DB static columns, update live fields, insert newly seen rooms.

    `trip_max_age_days`: giá Trip gốc chưa làm mới quá số ngày này thì xoá giá và tắt bán; 0 = không tắt (setting
    `tripHotels.priceMaxAgeDays`).
    `quarantine`: có danh sách thì dòng mới không ghép được với DB (ID trùng nhưng ref khác, trùng sourceRef chuẩn) được bỏ
    ra, ghi vào danh sách kèm lý do, các dòng khác vẫn nạp — trước đây một dòng như vậy làm hỏng cả
    lượt nạp (03–05/10/2026). Không có danh sách thì vẫn ném lỗi như cũ."""
    if trip_max_age_days < 0:
        raise ValueError("trip_max_age_days phải >= 0")
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=trip_max_age_days)
    validate_catalog(fresh, allow_external_parents=True)
    old = {str(row["product_id"]): row for row in existing}
    by_ref, merged_away = resolve_ref_conflicts(existing)
    # The full catalog may have merged a Trip hotel/room into a Booking row.
    # Resolve by sameAs, then reparent new Trip rooms to the retained DB ID.
    # Tra bằng MỌI ref của dòng mới (sourceRef rồi sameAs), không chỉ sourceRef: dòng được giữ khi gộp trùng có thể đổi
    # theo thứ tự nguồn về (nạp theo phần, L4 docs/plan/2026-09-28-pipeline-chay-lien-tuc.md). Nhiều dòng cũ cùng khớp thì
    # giữ dòng khớp trước (ưu tiên sourceRef của chính nó), các dòng kia được đánh dấu đã gộp (mergedInto) và ẩn đi.
    matches: dict[str, list[dict]] = {}
    for item in fresh:
        hits: list[dict] = []
        for ref in [item["sourceRef"], *((item.get("attributes") or {}).get("sameAs") or [])]:
            row = by_ref.get(ref)
            if row is not None and all(row["product_id"] != hit["product_id"] for hit in hits):
                hits.append(row)
        matches[item["productId"]] = hits
    mapped_ids = {pid: str(hits[0]["product_id"]) for pid, hits in matches.items() if hits}
    db_matched = match_existing_hotels(fresh, existing, matches)
    skipped = _quarantine_plan(fresh, matches, mapped_ids, old) if quarantine is not None else {}
    for item in fresh:
        if item["productId"] in skipped:
            quarantine.append({"productId": item["productId"], "sourceRef": item["sourceRef"], "name": item["name"],
                               "reason": skipped[item["productId"]]})
    canonical_refs = set()
    result = []
    counts = {"new": 0, "newRooms": 0, "refreshed": 0, "missingRooms": 0, "missingProperties": 0, "staleTrip": 0,
              "mergedAway": 0, "refConflicts": len(merged_away), "quarantined": len(skipped), "dbMatched": 0,
              "keptMerged": 0}
    hidden: dict[str, str] = {}      # product_id ẩn đi → dòng giữ (phòng con của nó chuyển sang dòng giữ)
    stay_merged: dict[str, str] = {}  # dòng đã gộp vẫn được nguồn đăng (tin trùng cùng nguồn) → dòng giữ
    links: list[tuple[str, str]] = []  # (dòng giữ trong DB, ref của khách sạn mới gộp vào nó)
    for item in fresh:
        if item["productId"] in skipped:
            continue
        original_ref = item["sourceRef"]
        hits = matches[item["productId"]]
        previous = hits[0] if hits else None
        merged_away += [(row, mapped_ids[item["productId"]]) for row in hits[1:]]
        pid = mapped_ids.get(item["productId"], item["productId"])
        if pid in old and not previous:
            raise ValueError(f"ID conflict for {pid}: sourceRef changed")
        attrs = price_attributes(item, previous["attributes"] if previous else None, seen_at)
        if attrs.get("mergedInto") and str(attrs["mergedInto"]) not in old:
            attrs.pop("mergedInto")  # gộp vào dòng đã không còn trong DB: nguồn còn bán thì dòng này hiện lại
        # Khoảng ngày của nguồn trong lượt này; apply_window cắt nó vào cửa sổ 30 ngày như seed.
        for key, value in (("sourceAvailableFrom", item["availableFrom"]), ("sourceAvailableTo", item["availableTo"])):
            if value is None:
                attrs.pop(key, None)
            else:
                attrs[key] = value
        parent = attrs.get("parentProductId")
        if parent in mapped_ids:
            attrs["parentProductId"] = mapped_ids[parent]
        if previous and previous["source_ref"] != original_ref:
            # dòng giữ trong DB mang sourceRef cũ (cột tĩnh): ref của nguồn thắng lần này vào sameAs để lần sau vẫn khớp
            same = [ref for ref in attrs.get("sameAs") or [] if ref != previous["source_ref"]]
            attrs["sameAs"] = same + ([original_ref] if original_ref not in same else [])
        row = {snake: item[camel] for snake, camel in zip(COLUMNS, FIELDS)}
        row["product_id"] = pid
        row["source_ref"] = previous["source_ref"] if previous else original_ref
        row["attributes"] = attrs
        keeper = db_matched.get(item["productId"])
        if keeper is not None:
            # Khách sạn mới trùng một khách sạn nguồn khác đã có trong DB (bước gộp trùng không thấy vì nguồn kia không cào
            # được ở lượt này): ghi nhưng ẩn, gộp vào dòng đã có — như dòng "gộp đi" — thay vì thêm một dòng trùng đang bán.
            attrs["mergedInto"] = str(keeper["product_id"])
            attrs.pop("availability", None)
            row["available"] = False
            hidden[pid] = str(keeper["product_id"])
            links.append((str(keeper["product_id"]), original_ref))
            counts["dbMatched"] += 1
        elif previous and attrs.get("mergedInto") and str(attrs["mergedInto"]) in old:
            # Dòng đã gộp vào một dòng còn trong DB nhưng nguồn vẫn đăng nó riêng (vd. hai tin Booking cùng khách sạn): giữ ẩn,
            # không để lượt cào bật lại.
            attrs.pop("availability", None)
            row["available"] = False
            stay_merged[pid] = str(attrs["mergedInto"])
            counts["keptMerged"] += 1
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
    _link_db_matches(result, links, existing)
    for index, row in enumerate(result):  # phòng cùng nguồn của dòng giữ ẩn: ẩn theo (dòng giữ đã có hạng phòng của nó)
        parent = (row["attributes"] or {}).get("parentProductId")
        if parent in stay_merged and row.get("available"):
            attrs = dict(row["attributes"], mergedInto=stay_merged[parent])
            attrs.pop("availability", None)
            result[index] = dict(row, attributes=attrs, available=False)
    represented = {str(row["product_id"]) for row in result}
    for previous, keeper in merged_away:
        pid = str(previous["product_id"])
        if pid in represented:
            continue
        attrs = copy.deepcopy(previous["attributes"] or {})
        attrs["mergedInto"] = keeper
        attrs.pop("availability", None)
        result.append(dict(previous, attributes=attrs, available=False))
        counts["mergedAway"] += 1
        represented.add(pid)
        hidden[pid] = keeper
    for previous in existing:
        room_match, property_match = trip_price_reference(previous)
        match = room_match or property_match
        if (not match or match.group(1) not in checked_hotels or previous["source_ref"] in canonical_refs
                or str(previous["product_id"]) in represented):  # dòng vừa gộp đi đã được ghi ở trên
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
    for previous in existing if trip_max_age_days else ():
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
    # Phòng con của dòng vừa bị gộp chuyển sang dòng giữ, để không treo dưới một property đã ẩn.
    written = {str(row["product_id"]): index for index, row in enumerate(result)}
    for child in existing:
        parent = (child["attributes"] or {}).get("parentProductId")
        if parent in hidden and str(child["product_id"]) not in written:
            written[str(child["product_id"])] = len(result)
            result.append(child)
    for index, row in enumerate(result):
        parent = (row["attributes"] or {}).get("parentProductId")
        if parent in hidden:
            result[index] = dict(row, attributes=dict(row["attributes"], parentProductId=hidden[parent]))
    return result, counts


SHARED_BUILDING = re.compile(r"\b(apartment|apartments|can ho|condotel|homestay|vinhomes|flc sea tower|apec|studio)\b")


def _float(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def match_existing_hotels(fresh: list[dict], existing: list[dict], matches: dict[str, list[dict]]) -> dict[str, dict]:
    """productId của khách sạn mới (không khớp ref nào trong DB) → dòng khách sạn NGUỒN KHÁC đã có trong DB là cùng một nơi.

    Bước gộp trùng của normalise chỉ ghép các nguồn có mặt trong cùng lượt; dòng Booking của snapshot 23/09 không được cào lại
    nên 20 khách sạn có thêm dòng Agoda/Trip trùng (production 08/10). Điều kiện chặt hơn normalise.cluster_hotels: cùng điểm
    đến, tên gần như trùng (≥ 97), cách ≤ 1 km (hoặc một bên thiếu toạ độ), dòng kia chưa có bản của nguồn này, không phải
    căn hộ/homestay (cùng toà nhà nhưng khác chủ); mỗi dòng DB chỉ nhận một khách sạn mới mỗi lượt và phải là ứng viên duy nhất."""
    from normalise import haversine_m, name_keys, name_score

    def is_property(taxonomy, attrs) -> bool:
        return taxonomy == "hotel" and (attrs or {}).get("level") == "property"

    def coords(attrs) -> dict:
        return {"latitude": _float((attrs or {}).get("latitude")), "longitude": _float((attrs or {}).get("longitude"))}

    by_dest: dict[str, list[dict]] = defaultdict(list)
    for row in existing:
        attrs = row["attributes"] or {}
        if is_property(row.get("taxonomy"), attrs) and not attrs.get("mergedInto"):
            by_dest[row.get("destination")].append(row)
    taken = {str(hits[0]["product_id"]) for hits in matches.values() if hits}
    out: dict[str, dict] = {}
    for item in fresh:
        attrs = item.get("attributes") or {}
        if matches.get(item["productId"]) or not is_property(item.get("taxonomy"), attrs):
            continue
        if SHARED_BUILDING.search(fold(item["name"])):
            continue
        source = item["sourceRef"].split(":", 1)[0]
        keys = name_keys(item["name"], attrs.get("nameEn"))
        found = []
        for row in by_dest.get(item["destination"], ()):
            row_attrs = row["attributes"] or {}
            refs = [row["source_ref"], *(row_attrs.get("sameAs") or [])]
            if str(row["product_id"]) in taken or any(ref.split(":", 1)[0] == source for ref in refs):
                continue
            if name_score(keys, name_keys(row.get("name"), row_attrs.get("nameEn"))) < 97:
                continue
            dist = haversine_m(coords(attrs), coords(row_attrs)) if None not in (*coords(attrs).values(),
                                                                                  *coords(row_attrs).values()) else None
            if dist is None or dist <= 1000:
                found.append(row)
        if len(found) == 1:
            out[item["productId"]] = found[0]
            taken.add(str(found[0]["product_id"]))
    return out


def _link_db_matches(result: list[dict], links: list[tuple[str, str]], existing: list[dict]) -> None:
    """Ref của khách sạn mới vừa gộp vào dòng DB (match_existing_hotels) vào sameAs của dòng giữ, để lượt sau khớp thẳng theo
    ref. Dòng giữ không được làm mới ở lượt này thì thêm vào lô ghi chỉ với sameAs mới."""
    written = {str(row["product_id"]): index for index, row in enumerate(result)}
    by_pid = {str(row["product_id"]): row for row in existing}
    for keeper, ref in links:
        index = written.get(keeper)
        base = result[index] if index is not None else by_pid[keeper]
        attrs = copy.deepcopy(base["attributes"] or {})
        same = list(attrs.get("sameAs") or [])
        if ref in same:
            continue
        attrs["sameAs"] = same + [ref]
        if index is None:
            written[keeper] = len(result)
            result.append(dict(base, attributes=attrs))
        else:
            result[index] = dict(base, attributes=attrs)


def _quarantine_plan(fresh: list[dict], matches: dict[str, list[dict]], mapped_ids: dict[str, str],
                     old: dict[str, dict]) -> dict[str, str]:
    """productId của dòng mới phải bỏ ra → lý do, theo đúng hai điều kiện prepare_rows sẽ ném lỗi. Cả hai trường hợp đều ghép
    vào một dòng đã có trong DB, nên hạng phòng của dòng bị bỏ vẫn có cha trong DB và được nạp."""
    skipped: dict[str, str] = {}
    refs: set[str] = set()
    for item in fresh:
        previous = (matches.get(item["productId"]) or [None])[0]
        pid = mapped_ids.get(item["productId"], item["productId"])
        if pid in old and not previous:
            skipped[item["productId"]] = f"ID {pid} đã có trong DB với sourceRef khác ({old[pid]['source_ref']})"
            continue
        ref = previous["source_ref"] if previous else item["sourceRef"]
        if ref in refs:
            skipped[item["productId"]] = f"trùng sourceRef chuẩn {ref} với một dòng khác của lượt"
            continue
        refs.add(ref)
    return skipped


def resolve_ref_conflicts(existing: list[dict]) -> tuple[dict[str, dict], list[tuple[dict, str]]]:
    """Tra cứu ref → dòng DB. Hai dòng chưa gộp cùng nhận một ref (vd. dòng agoda nạp riêng trong khi dòng booking đã
    ghi ref đó vào sameAs) thì giữ dòng ghi ref trong sameAs — kết quả gộp trùng — và trả dòng kia để đánh dấu mergedInto,
    thay vì dừng cả lượt nạp. Hai bên cùng ghi trong sameAs thì giữ product_id nhỏ hơn cho ổn định."""
    rows = {str(row["product_id"]): row for row in existing}
    owner: dict[str, str] = {}
    losers: dict[str, str] = {}

    def canon(pid: str) -> str:
        while pid in losers:
            pid = losers[pid]
        return pid

    def claims(pid: str, ref: str) -> bool:
        row = rows.get(pid)
        return row is not None and (row["source_ref"] == ref or ref in ((row["attributes"] or {}).get("sameAs") or []))

    for previous in existing:
        refs = [previous["source_ref"], *((previous["attributes"] or {}).get("sameAs") or [])]
        keeper = (previous["attributes"] or {}).get("mergedInto")
        if keeper:
            # Đã gộp vào dòng khác: ref thuộc dòng kia. Dòng kia không còn hoặc không nhận ref (gộp "treo") thì dòng này
            # vẫn giữ ref của chính nó, để lượt cào lại khớp đúng dòng thay vì báo trùng ID và hỏng cả lô nạp.
            refs = [ref for ref in refs if not claims(str(keeper), ref)]
        for ref in refs:
            mine = canon(str(previous["product_id"]))
            theirs = canon(owner[ref]) if ref in owner else mine
            if theirs == mine:
                owner[ref] = mine
                continue
            alias_mine, alias_theirs = rows[mine]["source_ref"] != ref, rows[theirs]["source_ref"] != ref
            hidden_mine, hidden_theirs = (bool((rows[pid]["attributes"] or {}).get("mergedInto")) for pid in (mine, theirs))
            if hidden_mine != hidden_theirs:  # dòng đang hiện thắng dòng đã gộp
                keep = theirs if hidden_mine else mine
            else:
                keep = mine if (alias_mine, theirs) > (alias_theirs, mine) else theirs
            losers[theirs if keep == mine else mine] = keep
            owner[ref] = keep
    by_ref = {ref: rows[canon(pid)] for ref, pid in owner.items()}
    return by_ref, [(rows[pid], canon(pid)) for pid in losers]


CALENDAR_VARIANTS = ("hotel_room", "attraction", "golf")
SIMULATED_PREFIX = "demo:business:"


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
        if calendar is None:  # dữ liệu hỏi thưa: mở đủ 30 đêm, cộng các ngày đã hỏi (hết phòng thật = 0)
            calendar = _with_observed(meta.room_calendar(view, as_of, views), attrs, as_of)
    else:
        calendar = meta.ticket_calendar(view["productId"], as_of)
    return loader.zero_outside(calendar, as_of, row["available_from"].isoformat(), row["available_to"].isoformat())


def apply_window(rows: list[dict], as_of: date) -> dict[str, dict]:
    """Cửa sổ đặt chỗ và lịch 30 ngày cho toàn catalog, như seed (DATABASE_SCHEMA.md #13, MOCK_DATA_SPEC.md §2).

    available_from/to = khoảng nguồn `attributes.sourceAvailableFrom/To` cắt vào [as_of, as_of + 29]; nguồn không
    có thì lấy cả cửa sổ. Hạng phòng luôn lấy cả cửa sổ. Chuyến bay: from = to = ngày bay (ngày đã thấy trong cửa sổ, không có thì dời vào cửa sổ
    theo crc32), giờ bay đổi theo. Vé ngày cố định dùng đúng quy tắc của seed (PRD data-model §3.1, chốt 06/10): ngày đi
    ngoài cửa sổ (đã bay, sau cửa sổ, hết hạn báo giá) thì dời cả hai chặng vào cửa sổ, ngày trong tên/mô tả đổi theo;
    vé đã dời giữ ngày mới tới khi ngày đó qua. Vé máy bay có giá, chưa gộp luôn available. Vé Thương gia mô phỏng
    (`demo:business:*`) không xử lý ở đây: simulated_business.sync chép lại từ vé gốc.
    Tuyến: min/max ngày của các chuyến con. Giao rỗng thì available = false và hai
    ngày = NULL; dòng đang bán bị tắt theo cách này mang `windowClosed` và được bật lại khi cửa sổ cuộn tới khoảng của
    nó (còn giá, chưa gộp, không có priceFreshness). Dòng tắt vì lý do khác (hết bán, giá quá hạn…) không bị bật lại:
    nguồn còn bán thì lượt cào sau ghi lại.
    Hạng phòng, điểm tham quan, golf có `attributes.availability` phủ đúng cửa sổ (xem `_calendar`). Khách sạn tổng quan không
    có phòng con đặt được thì tắt (`_hide_hotels_without_rooms`).
    Trả về các dòng có thay đổi (kể cả name/description của vé được dời), theo product_id.
    """
    meta, loader = _seed_rules()
    lo, hi = meta.window(as_of)
    before = {str(row["product_id"]): row for row in rows}
    views = {pid: {"productId": pid, "sourceRef": row["source_ref"], "attributes": row["attributes"] or {}}
             for pid, row in before.items()}
    after: dict[str, dict] = {}
    kinds: dict[str, str] = {}
    flight_days: dict[str, list[date]] = defaultdict(list)
    simulated = {pid for pid, row in before.items() if str(row["source_ref"]).startswith(SIMULATED_PREFIX)}
    fixed = [row["attributes"] for pid, row in before.items() if pid not in simulated
             and meta.variant({"taxonomy": row["taxonomy"], "attributes": row["attributes"] or {}}) == "flight"
             and (row["attributes"] or {}).get("fixedDepartureDate")]
    # Như load_products.convert: vé giữ ngày thật giữ chỗ trước; các hạng của cùng hành trình dời theo ID nhỏ nhất.
    taken = {loader.itinerary(attrs)[:-1] + (day,): loader.itinerary(attrs) for attrs in fixed
             for day in [loader._departure_day(attrs)] if day is not None and lo <= day <= hi}
    trip_ids: dict[tuple, str] = {}
    for pid, row in before.items():
        if (row["attributes"] or {}).get("fixedDepartureDate") and pid not in simulated:
            trip = loader.itinerary(row["attributes"])
            trip_ids[trip] = min(trip_ids.get(trip, pid), pid)
    for pid, row in before.items():
        if pid in simulated:
            continue
        attrs = row["attributes"] or {}
        name, description = row.get("name"), row.get("description")
        kinds[pid] = meta.variant({"taxonomy": row["taxonomy"], "attributes": attrs})
        start, end = (date.fromisoformat(day) for day in
                      loader.clip(attrs.get("sourceAvailableFrom"), attrs.get("sourceAvailableTo"), lo, hi))
        if kinds[pid] == "combo":  # như load_products.convert: dòng combo trip.com cũ trong DB còn ngày "14/10"
            attrs = trip_combo_dates(attrs)
        if kinds[pid] == "hotel_room":  # nguyên cửa sổ, không cắt theo ngày nguồn (như load_products.convert)
            start, end = lo, hi
        elif kinds[pid] == "flight" and attrs.get("fixedDepartureDate"):
            day, real = loader.seed_fixed_flight_date(trip_ids.get(loader.itinerary(attrs), pid), attrs, lo, hi, taken)
            if day is None:  # thiếu/sai departureAt: không đặt được
                start, end = lo, lo - timedelta(days=1)
            else:
                if not real:
                    attrs = copy.deepcopy(attrs)
                    name, description = loader.shift_fixed_flight(attrs, day, name or "", description or "")
                start = end = day
                flight_days[attrs.get("parentProductId") or ""].append(start)
        elif kinds[pid] == "flight":
            start, _ = loader.pick_flight_date({"productId": pid, "availableFrom": attrs.get("sourceAvailableFrom"),
                                                "attributes": attrs}, lo, hi)
            end = start
            attrs = copy.deepcopy(attrs)
            loader.move_flight(attrs, start)
            flight_days[attrs.get("parentProductId") or ""].append(start)
        after[pid] = dict(row, attributes=attrs, available_from=start, available_to=end, name=name, description=description)
        if kinds[pid] == "flight" and start <= end:  # vé luôn đặt được khi có giá (PRD data-model §3.1, chốt 06/10)
            after[pid]["available"] = row.get("unit_price") is not None and not attrs.get("mergedInto")
    changed = {}
    for pid, row in after.items():
        if kinds[pid] == "flight_route" and flight_days.get(pid):
            row["available_from"], row["available_to"] = min(flight_days[pid]), max(flight_days[pid])
        if row["available_from"] > row["available_to"]:
            if row["available"]:  # chính cửa sổ tắt dòng này: đánh dấu để bật lại khi cửa sổ cuộn tới
                row["attributes"] = dict(row["attributes"], windowClosed=True)
            row.update(available=False, available_from=None, available_to=None)
        elif row["attributes"].get("windowClosed"):
            attrs = {key: value for key, value in row["attributes"].items() if key != "windowClosed"}
            reopen = (not row["available"] and row.get("unit_price") is not None
                      and not attrs.get("mergedInto") and not attrs.get("priceFreshness"))
            row.update(attributes=attrs, available=row["available"] or reopen)
        if kinds[pid] in CALENDAR_VARIANTS:
            calendar = _calendar(kinds[pid], row, views[pid], views, as_of, meta, loader)
            row["attributes"] = dict(row["attributes"], availability={
                "from": as_of.isoformat(), "days": meta.WINDOW_DAYS, "calendar": calendar})
    _hide_hotels_without_rooms(after, kinds)
    for pid, row in after.items():
        old = before[pid]
        if ((row["available"], row["available_from"], row["available_to"], row["attributes"], row.get("name"),
             row.get("description"))
                != (old["available"], _as_date(old["available_from"]), _as_date(old["available_to"]),
                    old["attributes"] or {}, old.get("name"), old.get("description"))):
            changed[pid] = row
    return changed


def _hide_hotels_without_rooms(rows: dict[str, dict], kinds: dict[str, str]) -> None:
    """PRD FR-CAT-02 (chốt 06/10): khách sạn tổng quan không có hạng phòng con nào đặt được (đang bán, có giá, không
    `ticketed: false`) thì `available = false` kèm `noBookableRoom`; có phòng đặt được trở lại thì bỏ dấu và bật lại (trừ
    dòng đã gộp, giá quá hạn hoặc ngoài cửa sổ). Dòng tắt vì lý do khác không có dấu nên không bị bật."""
    bookable = {(row["attributes"] or {}).get("parentProductId") for pid, row in rows.items()
                if kinds[pid] == "hotel_room" and row["available"] and row.get("unit_price") is not None
                and (row["attributes"] or {}).get("ticketed") is not False}
    for pid, row in rows.items():
        if kinds[pid] != "hotel_property":
            continue
        attrs = row["attributes"] or {}
        if pid not in bookable:
            if row["available"]:
                row.update(available=False, attributes=dict(attrs, noBookableRoom=True))
        elif attrs.get("noBookableRoom"):
            attrs = {key: value for key, value in attrs.items() if key != "noBookableRoom"}
            reopen = (row["available_from"] is not None and not attrs.get("mergedInto")
                      and not attrs.get("priceFreshness") and not attrs.get("windowClosed"))
            row.update(attributes=attrs, available=row["available"] or reopen)


def pipeline_connection(url: str, **kwargs):
    """Finite connection, statement and lock waits, confined to this loader connection."""
    import psycopg
    return psycopg.connect(url, connect_timeout=10,
                           options='-c lock_timeout=5000 -c statement_timeout=300000 '
                                   '-c idle_in_transaction_session_timeout=60000', **kwargs)


def maintain_catalog(url: str, *, today: date | None = None, now: datetime | None = None,
                     trip_max_age_days: int = 7, refresh_out: dict | None = None,
                     stages: Stages | None = None) -> dict[str, int]:
    """Transaction riêng ở đầu mỗi lượt, chạy cả khi mọi nguồn lỗi: hết hạn giá Trip quá hạn, cuộn cửa sổ 30 ngày và
    parse lại thành phần combo (sync_combo_items). `refresh_out`: nhận danh sách khách sạn đang có để lượt cào lớn làm mới
    (refresh_targets_from_rows), lấy từ chính lần đọc catalog này thay vì đọc DB thêm một lần. `stages`: bước con cho monitor."""
    import psycopg
    from psycopg.types.json import Jsonb
    stages = stages or Stages()
    today = today or date.today()
    with pipeline_connection(url, row_factory=psycopg.rows.dict_row) as conn:
        conn.execute("SELECT pg_advisory_xact_lock(7791024)")
        with stages.stage("đọc catalog") as stage:
            existing = conn.execute("SELECT * FROM cdp.products").fetchall()
            stage["out"] = len(existing)
        if refresh_out is not None:
            with stages.stage("danh sách làm mới") as stage:  # chọn khách sạn từ catalog, không phải lọc bớt dòng
                refresh_out.update(refresh_targets_from_rows(existing))
                stage["out"] = sum(len(items) for items in refresh_out.values())
                stage["note"] = ", ".join(f"{key} {len(items)}" for key, items in refresh_out.items())
        with stages.stage("hết hạn giá Trip", inp=len(existing)) as stage:
            expired, counts = prepare_rows([], existing, set(), today.isoformat(), now=now,
                                           trip_max_age_days=trip_max_age_days)
            stage["changed"] = counts["staleTrip"]
            stage["note"] = "dòng giá Trip quá hạn bị tắt" if trip_max_age_days else "tắt (tripHotels.priceMaxAgeDays = 0)"
        state = {str(row["product_id"]): row for row in existing}
        state.update((str(row["product_id"]), row) for row in expired)
        with stages.stage("cuộn cửa sổ 30 ngày", inp=len(state)) as stage:
            windowed = apply_window(list(state.values()), today)
            stage["changed"] = len(windowed)
            stage["note"] = "dòng đổi cửa sổ / lịch trống"
        writes = {str(row["product_id"]): row for row in expired}
        writes.update(windowed)
        with stages.stage("ghi DB", inp=len(writes)) as stage, conn.cursor() as cursor:
            cursor.executemany(
                """UPDATE cdp.products SET attributes = %s, unit_price = %s, available = %s,
                       available_from = %s, available_to = %s, name = COALESCE(%s, name), description = COALESCE(%s, description)
                   WHERE product_id = %s""",
                [(Jsonb(row["attributes"]), row["unit_price"], row["available"], row["available_from"],
                  row["available_to"], row.get("name"), row.get("description"), row["product_id"])
                 for row in writes.values()])
            stage["out"] = len(writes)
        from data_collection.seed import simulated_business  # _seed_rules() đã đưa src/ vào sys.path
        # Vé thương gia mô phỏng là dữ liệu demo, không phải bước xử lý: không ghi bước con / dòng log cho monitor (số đếm vẫn
        # vào kết quả của bước).
        simulated = simulated_business.sync(conn)
        # Thành phần combo theo code parse hiện hành cho mọi combo, kể cả combo lượt này không cào được.
        state.update(writes)
        with stages.stage("parse thành phần combo") as stage:
            combos = sync_combo_items(conn, rows=list(state.values()))
            stage.update({"in": combos.get("combos"), "changed": combos.get("combosChanged")})
    return {"staleTrip": counts["staleTrip"], "windowRows": len(windowed), **simulated, **combos}


def row_action(row: dict, previous: dict | None, fresh_ids: set[str]) -> str:
    """Vì sao một dòng được ghi ở lượt này (cho báo cáo nạp DB của monitor)."""
    if previous is None:
        return "new"
    freshness = (row.get("attributes") or {}).get("priceFreshness")
    if freshness == "missing_from_live_response":
        return "missing"
    if freshness == "stale":
        return "stale"
    return "refresh" if str(row["product_id"]) in fresh_ids else "window"


def _brief(row: dict | None) -> dict | None:
    if row is None:
        return None
    return {"unitPrice": None if row.get("unit_price") is None else float(row["unit_price"]),
            "available": row.get("available"),
            "availableFrom": str(row["available_from"]) if row.get("available_from") else None,
            "availableTo": str(row["available_to"]) if row.get("available_to") else None}


def write_load_report(path: Path, prepared: list[dict], existing: list[dict], fresh_ids: set[str],
                      written: set[str]) -> None:
    old = {str(row["product_id"]): row for row in existing}
    with open(path, "w", encoding="utf-8") as out:
        for row in prepared:
            pid = str(row["product_id"])
            previous = old.get(pid)
            attrs = row.get("attributes") or {}
            out.write(json.dumps({
                "productId": pid, "sourceRef": row.get("source_ref"), "name": row.get("name"),
                "taxonomy": row.get("taxonomy"), "level": attrs.get("level"), "destination": row.get("destination"),
                "action": row_action(row, previous, fresh_ids), "written": pid in written,
                "before": _brief(previous), "after": _brief(row),
                "priceSource": (attrs.get("fieldSources") or {}).get("unitPrice"),
            }, ensure_ascii=False, default=str) + "\n")


def bring_manual_combo_mapping(run_dir: Path, source: Path | None = None) -> bool:
    """Thư mục lượt cào không có mapping combo duyệt tay: chép `combo_items_manual.jsonl` của snapshot mặc định vào để
    parse_combos ghép vào (dòng `source = manual`). Thiếu bước này thì mỗi lần nạp DB xoá mất các dòng đã duyệt tay."""
    if source is None:
        from data_collection.seed.config import DEFAULT_SNAPSHOT_DIR
        source = DEFAULT_SNAPSHOT_DIR / "combo_items_manual.jsonl"
    target = run_dir / "combo_items_manual.jsonl"
    if not source.is_file() or target.exists():
        return False
    shutil.copyfile(source, target)
    return True


def _catalog_view(row: dict) -> dict:
    """Dòng `cdp.products` (snake_case) → dạng 13 trường camelCase mà parse_combos đọc."""
    view = {camel: row[snake] for snake, camel in zip(COLUMNS, FIELDS)}
    view.update(productId=str(row["product_id"]), attributes=row["attributes"] or {}, description=row["description"] or "",
                unitPrice=None if row["unit_price"] is None else float(row["unit_price"]))
    return view


def _canonical_ids(rows: list[dict]) -> dict[str, str]:
    """productId / productId của mọi ref (sourceRef, sameAs) → product_id của dòng đang hiện (theo `mergedInto` nếu đã gộp).
    Mapping duyệt tay ghi productId theo snapshot; dòng giữ trong DB có thể mang ID cũ của một nguồn khác."""
    keeper = {str(row["product_id"]): str((row["attributes"] or {}).get("mergedInto") or row["product_id"]) for row in rows}
    out = {}
    for pid in keeper:
        seen = pid
        for _ in range(len(keeper)):  # chuỗi gộp A → B → C
            if keeper.get(seen, seen) == seen:
                break
            seen = keeper[seen]
        out[pid] = seen
    for row in rows:
        target = out[str(row["product_id"])]
        for ref in [row["source_ref"], *((row["attributes"] or {}).get("sameAs") or [])]:
            out.setdefault(product_id(ref), target)
    return out


def combo_items_from_db(rows: list[dict], manual: dict[tuple[str, int], dict]) -> tuple[dict[str, list[dict]], int]:
    """Thành phần của mọi combo đang có trong DB, parse lại từ tên + mô tả đang lưu trong DB và ghép mapping duyệt tay.

    Không phụ thuộc lượt cào: combo không cào được (nguồn chặn, lượt lỗi) vẫn nhận bản parse hiện hành, và thành phần map
    sang sản phẩm của toàn catalog chứ không chỉ sản phẩm của lô đang nạp. Bỏ qua dòng đã gộp (`mergedInto`) và vé Thương
    gia mô phỏng. Trả (combo_product_id → dòng, số dòng duyệt tay bị bỏ vì trỏ tới sản phẩm không có / sai loại)."""
    from data_collection.seed import parse_combos
    live = [row for row in rows if not (row["attributes"] or {}).get("mergedInto")
            and not str(row["source_ref"]).startswith(SIMULATED_PREFIX)]
    views = [_catalog_view(row) for row in live]
    taxonomy = {view["productId"]: view["taxonomy"] for view in views}
    canonical = _canonical_ids(rows)
    reviewed: dict[tuple[str, int], dict] = {}
    skipped = 0
    for (cid, pos), item in manual.items():
        combo = canonical.get(cid, cid)
        target = item.get("item_product_id")
        target = canonical.get(target, target) if target else None
        if taxonomy.get(combo) != "combo":
            continue  # combo không còn trong DB: không có gì để ghép
        if target is not None and (taxonomy.get(target) != item["item_kind"] or target == combo):
            skipped += 1  # FK (item_product_id, item_kind) sẽ hỏng: để dòng parse thay chỗ
            continue
        reviewed[(combo, int(pos))] = {**item, "combo_product_id": combo, "position": int(pos), "item_product_id": target}
    cat = parse_combos.Catalog(views)
    wanted = {view["productId"]: parse_combos.merge_manual(view["productId"], parse_combos.parse_combo(view, cat), reviewed)
              for view in views if view["taxonomy"] == "combo"}
    return wanted, skipped


def _comparable(item: dict) -> tuple:
    """So dòng DB (uuid, Decimal) với dòng parse (str, float) theo đúng kiểu cột (numeric(6,2), numeric(3,2))."""
    def num(value, digits):
        return None if value is None else round(float(value), digits)
    return (int(item["position"]), item["label"], item["item_kind"],
            None if item.get("item_product_id") is None else str(item["item_product_id"]), num(item["quantity"], 2),
            item["unit"], bool(item["is_optional"]), item["source"], num(item.get("confidence"), 2), item.get("evidence"))


def sync_combo_items(conn, *, manual_path: Path | None = None, rows: list[dict] | None = None,
                     dry_run: bool = False) -> dict:
    """Parse lại `catalog.combo_items` của mọi combo từ `cdp.products` trong transaction của `conn`; chỉ xoá + ghi lại combo
    có thành phần đổi (không đổi thì không ghi, nên job index không embed lại). `rows`: trạng thái `cdp.products` đã có trong
    transaction (None = đọc lại). `dry_run`: chỉ tính, không ghi; kết quả kèm `changedCombos` (tên, số dòng trước/sau)."""
    import psycopg
    from data_collection.seed import parse_combos
    from data_collection.seed.database import COMBO, copy_rows
    if manual_path is None:
        from data_collection.seed.config import DEFAULT_SNAPSHOT_DIR
        manual_path = DEFAULT_SNAPSHOT_DIR / "combo_items_manual.jsonl"
    with conn.cursor(row_factory=psycopg.rows.dict_row) as cursor:
        if rows is None:
            rows = cursor.execute("SELECT * FROM cdp.products").fetchall()
        stored: dict[str, list[dict]] = defaultdict(list)
        for item in cursor.execute("SELECT * FROM catalog.combo_items").fetchall():
            stored[str(item["combo_product_id"])].append(item)
    wanted, skipped = combo_items_from_db(rows, parse_combos.load_manual(manual_path))
    changed = [cid for cid, items in wanted.items()
               if sorted(map(_comparable, items)) != sorted(map(_comparable, stored.get(cid, [])))]
    fresh = [{**item, "combo_product_id": cid} for cid in changed for item in wanted[cid]]
    if changed and not dry_run:
        conn.execute("DELETE FROM catalog.combo_items WHERE combo_product_id = ANY(%s::uuid[])", (changed,))
        copy_rows(conn, "catalog.combo_items", COMBO, fresh)
    counts = {"combos": len(wanted), "combosChanged": len(changed), "comboItemsWritten": 0 if dry_run else len(fresh),
              "manualSkipped": skipped}
    if dry_run:
        # Nhãn đổi = text index của combo đổi (text_builder ghép nhãn) → job index embed lại; chỉ đổi map/evidence thì không.
        def labels(items):
            return [item["label"] for item in sorted(items, key=lambda item: int(item["position"]))]
        names = {str(row["product_id"]): row["name"] for row in rows}
        report = []
        for cid in changed:
            before, after = labels(stored.get(cid, [])), labels(wanted[cid])
            entry = {"productId": cid, "name": names.get(cid), "before": len(before), "after": len(after),
                     "labelsChanged": before != after}
            if before != after:
                entry.update(labelsBefore=before, labelsAfter=after)
            report.append(entry)
        counts["combosLabelsChanged"] = sum(entry["labelsChanged"] for entry in report)
        counts["changedCombos"] = report
    return counts


def load_into_db(products_path: Path, coverage_path: Path | None, url: str,
                 collection_root: Path, report_path: Path | None = None, *,
                 trip_max_age_days: int = 7, stages: Stages | None = None) -> dict[str, int]:
    """COPY into a temporary table then upsert in one transaction, as V-OTA does.

    `coverage_path` None = lượt không cào khách sạn Trip (không dòng Trip nào được nạp).
    `report_path`: ghi mỗi dòng được nạp kèm hành động (new/refresh/missing/stale/window) và giá trước/sau."""
    import psycopg
    source_root = collection_root.parent
    if str(source_root) not in sys.path:
        sys.path.insert(0, str(source_root))
    from data_collection.seed.database import copy_rows
    from data_collection.seed import parse_combos

    stages = stages or Stages()
    fresh = list(read_jsonl(products_path))
    checked = checked_trip_hotels(coverage_path) if coverage_path is not None else set()
    quarantine: list[dict] = []  # dòng không nạp được, ghi ra db_quarantine.jsonl; các dòng khác vẫn nạp
    kept = []
    with stages.stage("đọc catalog lượt này") as stage:
        for item in fresh:
            match = re.match(r"^trip:hotel:(\d+)(?::room:.*)?$", item["sourceRef"])
            if match and match.group(1) not in checked:
                quarantine.append({"productId": item["productId"], "sourceRef": item["sourceRef"], "name": item["name"],
                                   "reason": "khách sạn Trip chưa đủ mọi mốc ngày giá"})
            else:
                kept.append(item)
        stage.update({"in": len(fresh), "out": len(kept), "ok": len(kept), "total": len(fresh)})
        if quarantine:
            stage["note"] = f"{len(quarantine)} dòng khách sạn Trip chưa đủ ngày giá bị tách ra"
    fresh = kept
    # priceBasis / nights / minPax của combo mới, cùng file soát tay của lượt. `catalog.combo_items` không lấy từ đây mà
    # parse lại trên toàn catalog trong DB sau upsert (sync_combo_items).
    with stages.stage("thuộc tính combo", inp=sum(item["taxonomy"] == "combo" for item in fresh)) as stage:
        bring_manual_combo_mapping(products_path.parent)
        parse_combos.main(["--data-dir", str(products_path.parent)])
        combo_attrs = json.loads((products_path.parent / "combo_attributes.json").read_text(encoding="utf-8"))
        applied = 0
        for item in fresh:
            if item["taxonomy"] == "combo" and item["productId"] in combo_attrs:
                item["attributes"].update(combo_attrs[item["productId"]]["attributes"])
                applied += 1
        stage["out"] = applied
    seen_at = date.today().isoformat()
    with pipeline_connection(url) as conn:
        conn.execute("SELECT pg_advisory_xact_lock(7791024)")
        with stages.stage("đọc DB") as stage, conn.cursor(row_factory=psycopg.rows.dict_row) as cursor:
            cursor.execute("SELECT * FROM cdp.products")
            existing = cursor.fetchall()
            stage["out"] = len(existing)
        with stages.stage("ghép với DB", inp=len(fresh)) as stage:
            before = len(quarantine)
            prepared, counts = prepare_rows(fresh, existing, checked, seen_at, trip_max_age_days=trip_max_age_days,
                                            quarantine=quarantine)
            dropped = {entry["productId"] for entry in quarantine}
            fresh = [item for item in fresh if item["productId"] not in dropped]  # prepared[i] ứng với fresh[i]
            counts["quarantined"] = len(quarantine)
            merged = stage["in"] - (len(quarantine) - before)
            stage.update({"out": len(prepared), "ok": merged, "total": stage["in"],
                          "note": f"mới {counts['new']} · làm mới {counts['refreshed']} · tách riêng "
                                  f"{len(quarantine) - before} · gộp đi {counts['mergedAway']}"})
        # Cửa sổ 30 ngày tính trên trạng thái sau lượt này: dòng mới/làm mới, và tuyến có chuyến con đổi ngày.
        with stages.stage("cửa sổ 30 ngày") as stage:
            state = {str(row["product_id"]): row for row in existing}
            state.update((str(row["product_id"]), row) for row in prepared)
            stage["in"] = len(state)
            windowed = apply_window(list(state.values()), date.fromisoformat(seen_at))
            stage["changed"] = len(windowed)
            stage["note"] = "dòng đổi cửa sổ / lịch trống"
        # Giữ thứ tự: canonical_ids bên dưới ánh xạ fresh[i] với prepared[i].
        prepared = [windowed.pop(str(row["product_id"]), row) for row in prepared]
        prepared.extend(windowed.values())
        canonical_ids = {item["productId"]: prepared[index]["product_id"]
                         for index, item in enumerate(fresh)}
        with stages.stage("ghi cdp.products", inp=len(prepared)) as entry:
            conn.execute("CREATE TEMP TABLE incoming_products (LIKE cdp.products INCLUDING DEFAULTS) ON COMMIT DROP")
            copy_rows(conn, "incoming_products", list(COLUMNS), prepared)
            cols = ", ".join(COLUMNS)
            changed = " OR ".join(f"p.{c} IS DISTINCT FROM EXCLUDED.{c}" for c in
                                  ("attributes", "unit_price", "available", "available_from", "available_to"))
            changed += " OR (p.taxonomy = 'flight' AND (p.name, p.description) IS DISTINCT FROM (EXCLUDED.name, EXCLUDED.description))"
            written = conn.execute(f"""
                INSERT INTO cdp.products AS p ({cols}) SELECT {cols} FROM incoming_products WHERE true
                ON CONFLICT (product_id) DO UPDATE SET
                    attributes = EXCLUDED.attributes,
                    unit_price = EXCLUDED.unit_price,
                    available = EXCLUDED.available,
                    available_from = EXCLUDED.available_from,
                    available_to = EXCLUDED.available_to,
                    -- Chỉ vé máy bay: ngày trong tên/mô tả đổi khi dời ngày (data-model §3.1). Loại khác giữ text đã có trong DB.
                    name = CASE WHEN p.taxonomy = 'flight' THEN EXCLUDED.name ELSE p.name END,
                    description = CASE WHEN p.taxonomy = 'flight' THEN EXCLUDED.description ELSE p.description END
                WHERE {changed}
                RETURNING product_id
            """).fetchall()
            counts["dbRowsWritten"] = len(written)
            entry.update(changed=len(written), note="dòng giống hệt DB không ghi lại")
        # Đọc lại cdp.products sau upsert (tên/mô tả không phải vé máy bay giữ bản trong DB) rồi parse mọi combo trên toàn
        # catalog: lô nạp theo phần chỉ chứa một phần sản phẩm, parse riêng lô thì thành phần không map được.
        with stages.stage("parse thành phần combo") as stage:
            combos = sync_combo_items(conn)
            counts.update(combos)
            stage.update({"in": combos.get("combos"), "changed": combos.get("combosChanged")})
        from data_collection.seed import simulated_business
        # sau upsert + cửa sổ, cùng transaction (data-model.md §3); dữ liệu demo nên không hiện thành bước con trên monitor
        counts.update(simulated_business.sync(conn))
    # Publish the report only after the connection context has committed successfully.
    if report_path is not None and quarantine:
        (report_path.parent / "db_quarantine.jsonl").write_text(
            "".join(json.dumps(entry, ensure_ascii=False) + "\n" for entry in quarantine), encoding="utf-8")
    if report_path is not None:
        temporary = report_path.with_suffix(".jsonl.tmp")
        write_load_report(temporary, prepared, existing, {str(pid) for pid in canonical_ids.values()},
                          {str(row[0]) for row in written})
        temporary.replace(report_path)
    return counts


# Slug có thể chứa '_' (Agoda đánh số bản trùng: `the-anam_4`, `somerset-west-point-hanoi_3`; ~43 khách sạn ở production 08/10)
BOOKING_HOTEL_URL = re.compile(r"^(https://www\.booking\.com/hotel/vn/[a-z0-9_-]+)(?:\.[a-z-]+)?\.html")
AGODA_HOTEL_URL = re.compile(r"^https://www\.agoda\.com/vi-vn/([a-z0-9_-]+)/hotel/([a-z0-9_-]+)-vn\.html")


def refresh_targets_from_rows(rows: list[dict]) -> dict[str, list[dict]]:
    """Khách sạn Booking/Agoda đang có trong DB để lượt cào lớn mở lại (setting `refresh.existing`).

    Lấy từ dòng `hotel_property` chưa gộp: dòng của chính nguồn (`url`) và dòng nguồn khác đã gộp ref của nguồn đó vào
    `sameAs` (`bookingUrl`/`agodaUrl`). Không xét `available`: khách sạn đang tắt cũng được hỏi lại để bật khi còn bán.
    Dòng lâu chưa thấy (`lastSeenAt` nhỏ, thiếu = snapshot cũ) đứng trước, để lượt hết giờ giữa chừng thì lượt sau tiếp
    phần còn lại thay vì làm lại cùng một đầu danh sách."""
    out: dict[str, dict[str, dict]] = {"booking": {}, "agoda": {}}
    for row in rows:
        attrs = row.get("attributes") or {}
        if attrs.get("level") != "property" or row.get("taxonomy") != "hotel" or attrs.get("mergedInto"):
            continue
        refs = [row["source_ref"], *(attrs.get("sameAs") or [])]
        own = row["source_ref"].split(":", 1)[0]
        seen = attrs.get("lastSeenAt") or ""
        if any(ref.startswith("booking:hotel:") for ref in refs):
            match = BOOKING_HOTEL_URL.match((attrs.get("url") if own == "booking" else attrs.get("bookingUrl")) or "")
            if match:
                url = match.group(1) + ".vi.html"
                out["booking"].setdefault(url, {"url": url, "destination": row["destination"], "lastSeenAt": seen})
        if any(ref.startswith("agoda:hotel:") for ref in refs):
            match = AGODA_HOTEL_URL.match((attrs.get("url") if own == "agoda" else attrs.get("agodaUrl")) or "")
            if match:
                url = match.group(0)
                hotel_id = attrs.get("agodaHotelId") if own == "agoda" else None
                out["agoda"].setdefault(url, {"url": url, "slug": match.group(1), "city": match.group(2),
                                              "hotelId": int(hotel_id) if str(hotel_id or "").isdigit() else None,
                                              "destination": row["destination"], "lastSeenAt": seen})
    return {source: sorted(items.values(), key=lambda item: (item["lastSeenAt"], item["url"]))
            for source, items in out.items()}


def main(argv: list[str] | None = None) -> int:
    """Xem trước, chỉ đọc: combo nào sẽ được parse lại thành phần ở lượt chạy kế tiếp (không ghi gì).

        python src/data_collection/fresh_catalog_db.py combo-items --database-url <dsn>
    """
    import argparse
    import psycopg
    ap = argparse.ArgumentParser(description=main.__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=("combo-items",))
    ap.add_argument("--database-url", required=True)
    args = ap.parse_args(argv)
    _seed_rules()  # đưa src/ vào sys.path cho data_collection.seed
    with pipeline_connection(args.database_url) as conn:
        conn.read_only = True
        report = sync_combo_items(conn, dry_run=True)
    print(json.dumps(report, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
