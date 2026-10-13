"""Những gì trợ lý đã cho người dùng xem trong hội thoại: thẻ khám phá, thẻ vé, sản phẩm của lịch (FR-AGT-01,
`architecture.md` §3 "Ngữ cảnh cho LLM", "Hội thoại": working memory giữ sản phẩm vừa hiển thị).

Lỗi gốc (2026-10-12, `docs/plan/2026-10-12-nho-ket-qua-da-xem.md`): "hà nội" → "ngoài ra còn gì nữa" (hay "đi rồi") trả lại
đúng 4 thẻ cũ, vì không lượt nào nhớ đã cho xem gì; ghi chú lượt khám phá chỉ giữ tên 3 thẻ.

`finalize` ghi từ chính response đã qua kiểm tra (`record`), nên chỉ thứ người dùng thật sự thấy mới vào đây. Mỗi sản phẩm
một mã ngắn `#n` giữ suốt hội thoại (hiện lại thì giữ mã cũ, mã không dùng lại), kèm một dòng thông tin (`facts`) đủ để LLM
nhận ra người dùng đang nói tới sản phẩm nào ("cái có hồ bơi", "cái rẻ nhất lúc nãy", "cái thứ hai"). Đây là trí nhớ để
nhớ, loại, so; không phải nguồn của câu trả lời: thẻ, giá, giờ, tiện ích, tình trạng còn chỗ trong response luôn từ tool
của chính lượt đó, kể cả khi dòng ở đây đã có.

Dạng: `{"turn": số lượt đã chốt, "seq": mã lớn nhất đã cấp, "items": [{"ref": "#3", "productId", "taxonomy", "name",
"place", "turn", "where", "facts"}]}`, mục cũ trước. `place` là điểm đến, hoặc tuyến `"<nơi đi>→<nơi đến>"` với vé máy bay.
"""
from __future__ import annotations

import re
from copy import deepcopy

from src.backend.app.domain.catalog.fares import CABIN_CODES, CABIN_NAMES
from src.backend.app.domain.itinerary import flights as flight_rules
from src.backend.app.domain.itinerary.exploration import short_name
from src.backend.app.domain.itinerary.normalization import fold
from src.backend.app.domain.search.amenities import AMENITIES, amenity_keys

from .messages import money

EMPTY = {"turn": 0, "seq": 0, "items": []}
#: Mục tối đa giữ cho mỗi điểm đến (hoặc tuyến bay); quá thì bỏ mục cũ nhất của nơi đó.
MAX_PER_PLACE = 40
#: Số tiện ích (khách sạn) và nhãn (điểm tham quan) tối đa trong một dòng.
MAX_AMENITIES = 5
MAX_TAGS = 3
#: Giờ mở cửa dài hơn chừng này ký tự thì bỏ (catalog có chuỗi giờ của cả tuần).
MAX_HOURS_TEXT = 40
#: Độ dài tối đa của các dòng sản phẩm trong khối ngữ cảnh LLM (`context`), để câu mới nhất không chìm (lost in the middle).
MAX_CONTEXT_CHARS = 2_000
ABOUT = ("Sản phẩm trợ lý đã cho người dùng xem trong hội thoại, cũ trước, mỗi cái một mã #n. Giá là giá lúc gợi ý, "
         "không phải ngân sách hay yêu cầu của người dùng.")
_PERIODS = {"MORNING": "sáng", "NOON": "trưa", "AFTERNOON": "chiều", "EVENING": "tối"}
#: Đơn vị giá theo `priceUnit` của catalog, để LLM không so giá theo đêm với giá theo gói khi nhận ra "cái rẻ hơn"; câu
#: trả lời về giá vẫn tra lại. Thiếu `priceUnit` thì khách sạn tính theo đêm, vé máy bay theo khách; `UNKNOWN` thì không
#: ghi đơn vị.
_UNITS = {"PER_NIGHT": "/đêm", "PER_PERSON": "/khách", "PER_PACKAGE": "/gói"}
_DEFAULT_UNITS = {"hotel": "/đêm", "flight": "/khách"}
_DIRECTIONS = {"OUTBOUND": "chặng đi", "RETURN": "chặng về", "ROUND_TRIP": "vé khứ hồi"}
_AMENITY_ORDER = {item.key: index for index, item in enumerate(AMENITIES)}
#: Khu vực trong địa chỉ catalog ("…, Phường Hồng Hà, …"): quận/huyện trước, không có thì phường/xã.
_DISTRICT = re.compile(r"\b(?:Quận|Huyện|Thị xã)\s+[^,]+", re.IGNORECASE)
_WARD = re.compile(r"\b(?:Phường|Xã|Thị trấn)\s+[^,]+", re.IGNORECASE)


def current(state: dict) -> dict:
    """`shown` của state; hội thoại lưu trước khi có trường này thì rỗng."""
    value = state.get("shown")
    return deepcopy(value) if isinstance(value, dict) and isinstance(value.get("items"), list) else deepcopy(EMPTY)


def by_ref(shown: dict) -> dict[str, dict]:
    """Mã `#n` → mục, để code map mã LLM nhắc về `productId`."""
    archived = {item["ref"]: {"productId": product_id, **item}
                for product_id, item in (shown.get("seen") or {}).items()}
    return {**archived, **{item["ref"]: item for item in shown.get("items") or []}}


def ref_of(shown: dict, product_id: str) -> str | None:
    return next((item["ref"] for item in shown.get("items") or [] if item.get("productId") == product_id), None) \
        or (shown.get("seen") or {}).get(product_id, {}).get("ref")


def record(state: dict, response: dict) -> dict:
    """`shown` sau lượt này: thêm sản phẩm `response` vừa hiện (thẻ khám phá, thẻ vé, khách sạn, vé, hoạt động của lịch).

    Thông tin chi tiết lấy từ bản đầy đủ của tool lượt này (`candidates`, `details`); không có thì từ bản rút gọn trong
    response. Lượt không hiện sản phẩm nào vẫn tăng số lượt.
    """
    shown = current(state)
    shown["turn"] = int(shown.get("turn") or 0) + 1
    full = {**(state.get("details") or {}), **(state.get("candidates") or {})}
    turn_refs = {product_id: ref for ref, product_id in (state.get("turn_codes") or {}).items()}
    shown["seq"] = max(shown.get("seq", 0), state.get("turn_seq", 0))
    via = {}
    for row in state.get("turn_jobs") or []:
        if row.get("status") in ("failed", "superseded") or row.get("intent") == "about_shown" or row.get("kind") != "explore":
            continue
        for product in row.get("products") or []:
            if turn_refs.get(product["productId"]) in (row.get("listed") or []):
                via[product["productId"]] = {key: row["spec"].get(key) for key in ("destination", "taxonomy", "query", "near", "sort")}
                if row["spec"].get("excluded_destinations"):
                    via[product["productId"]]["excluded_destinations"] = deepcopy(row["spec"]["excluded_destinations"])
    remember_all = state.get("orchestrator_active") or "seen" in shown
    if remember_all:
        shown.setdefault("seen", {})
        for old_item in shown["items"]:
            shown["seen"][old_item["productId"]] = {key: old_item.get(key) for key in ("ref", "place", "taxonomy", "via")}
    for product, where in _displayed(response):
        product_id = product.get("productId")
        if not product_id:
            continue
        product = full.get(product_id) or product
        item = {"productId": product_id, "taxonomy": product.get("taxonomy"), "name": _label(product),
                "place": _place(product), "turn": shown["turn"], "where": where, "facts": facts(product)}
        old = next((entry for entry in shown["items"] if entry.get("productId") == product_id), None)
        if old is not None:
            # Hiện lại: giữ mã cũ để các lượt trước và lượt sau nói cùng một mã; mục chuyển xuống cuối (mới nhất).
            shown["items"].remove(old)
            item["ref"] = old["ref"]
        elif product_id in turn_refs or remember_all and product_id in shown["seen"]:
            item["ref"] = turn_refs.get(product_id) or shown["seen"][product_id]["ref"]
        else:
            shown["seq"] = int(shown.get("seq") or 0) + 1
            item["ref"] = f"#{shown['seq']}"
        if product_id in via:
            item["via"] = via[product_id]
        elif old and old.get("via"):
            item["via"] = old["via"]
        shown["items"].append(item)
        if remember_all:
            shown["seen"][product_id] = {key: item.get(key) for key in ("ref", "place", "taxonomy", "via")}
    shown["items"] = _capped(shown["items"])
    return shown


def context(state: dict, max_chars: int = MAX_CONTEXT_CHARS) -> dict | None:
    """Khối "đã gợi ý" cho mọi lời gọi LLM (`history.llm_context`): mỗi sản phẩm một dòng, cũ trước, và lịch gần nhất tóm
    theo mã. Dài quá `max_chars` thì bỏ lượt cũ nhất trước; giữ trọn lượt gần nhất và sản phẩm của lịch gần nhất khi còn
    chỗ. Không có tổng tiền lịch; giá là giá lúc gợi ý (prompt dặn không dùng làm ngân sách)."""
    seen = current(state)
    items = seen["items"]
    if not items:
        return None
    plan_ids = _plan_ids(state)
    latest = max(int(item.get("turn") or 0) for item in items)
    order = {id(item): index for index, item in enumerate(items)}
    # Ưu tiên: lượt gần nhất, sản phẩm của lịch gần nhất, rồi các lượt khác từ mới tới cũ.
    ranked = sorted(items, key=lambda item: (item.get("turn") != latest, item.get("productId") not in plan_ids,
                                             -int(item.get("turn") or 0), order[id(item)]))
    kept, used = [], 0
    for item in ranked:
        line = _line(item)
        if used + len(line) > max_chars:
            continue
        kept.append(item)
        used += len(line)
    block: dict = {"about": ABOUT,
                   "items": [_line(item) for item in sorted(kept, key=lambda item: order[id(item)])]}
    plan = plan_line(state, seen)
    if plan:
        block["current_plan"] = plan
    return block


def _line(item: dict) -> str:
    return f"{item['ref']} {item.get('name') or ''} — {item.get('facts') or ''} [lượt {item.get('turn')}, " \
           f"{item.get('where') or ''}]"


def _plan_ids(state: dict) -> set[str]:
    itinerary = (state.get("previous_plan") or {}).get("itinerary") or {}
    return {product["productId"] for product, _ in _displayed({"status": "COMPLETED", "itinerary": itinerary})
            if product.get("productId")}


def plan_line(state: dict, seen: dict | None = None) -> str | None:
    """Lịch gần nhất tóm theo mã: "chặng đi #5; khách sạn #3 (đêm 1–2); ngày 1: sáng #1, chiều #2; …"; sản phẩm chưa có
    mã (hội thoại lưu trước khi có `shown`) thì dùng tên ngắn."""
    itinerary = (state.get("previous_plan") or {}).get("itinerary") or {}
    if not itinerary.get("days"):
        return None
    seen = seen if seen is not None else current(state)

    def name(product: dict) -> str:
        return ref_of(seen, product.get("productId")) or _label(product)

    parts = [f"{_DIRECTIONS.get(flight.get('direction'), 'vé')} {name(flight.get('product') or {})}"
             for flight in itinerary.get("flights") or [] if flight.get("direction") != "RETURN"]
    for stay in itinerary.get("stays") or ([itinerary["stay"]] if itinerary.get("stay") else []):
        first, nights = stay.get("fromNight"), stay.get("nights")
        nights_text = f" (đêm {first}–{first + nights - 1})" if isinstance(first, int) and isinstance(nights, int) \
            and nights > 1 else f" (đêm {first})" if isinstance(first, int) else ""
        parts.append(f"khách sạn {name(stay.get('product') or {})}{nights_text}")
    for day in itinerary.get("days") or []:
        slots = [f"{_PERIODS.get(slot.get('time'), '')} {name(slot['product'])}".strip()
                 for slot in day.get("slots") or [] if slot.get("product")]
        parts.append(f"ngày {day.get('day')}: {', '.join(slots) if slots else 'tự do'}")
    parts += [f"{_DIRECTIONS['RETURN']} {name(flight.get('product') or {})}"
              for flight in itinerary.get("flights") or [] if flight.get("direction") == "RETURN"]
    return "; ".join(parts)


def _displayed(response: dict) -> list[tuple[dict, str]]:
    """(sản phẩm, đã hiện ở đâu) theo thứ tự người dùng thấy."""
    found: list[tuple[dict, str]] = []
    for taxonomy, products in (response.get("searchResults") or {}).items():
        where = "vé máy bay" if taxonomy == "flight" else "khám phá"
        found += [(product, where) for product in products or [] if isinstance(product, dict)]
    itinerary = response.get("itinerary") if response.get("status") == "COMPLETED" else None
    if not isinstance(itinerary, dict):
        return found
    for flight in itinerary.get("flights") or []:
        found.append((flight.get("product") or {}, f"lịch, {_DIRECTIONS.get(flight.get('direction'), 'vé')}"))
    for stay in itinerary.get("stays") or ([itinerary["stay"]] if itinerary.get("stay") else []):
        found.append((stay.get("product") or {}, "lịch, khách sạn"))
    for day in itinerary.get("days") or []:
        for slot in day.get("slots") or []:
            if slot.get("product"):
                period = _PERIODS.get(slot.get("time"), "")
                found.append((slot["product"], f"lịch, ngày {day.get('day')} {period}".rstrip()))
    return found


def _label(product: dict) -> str:
    """Tên ngắn như người dùng gọi; tên mở bằng nhãn trong ngoặc ("[03 ngày] - VinWonders + Safari") bỏ dấu nối đầu. Vé
    máy bay là hãng và số hiệu ("VietJet Air VJ124"); tuyến, ngày, giờ nằm ở `facts`."""
    if product.get("taxonomy") == "flight":
        item = flight_rules.brief(product)
        label = " ".join(part for part in (item.get("airline"), item.get("flightNumber")) if part)
        if label:
            return label
    return short_name(product).lstrip("-–| ").strip() or " ".join(str(product.get("name") or "").split())


def _place(product: dict) -> str:
    attributes = product.get("attributes") or {}
    if product.get("taxonomy") == "flight" and attributes.get("originCity"):
        return f"{attributes['originCity']}→{attributes.get('destinationCity') or product.get('destination') or ''}"
    return product.get("destination") or ""


def _capped(items: list[dict]) -> list[dict]:
    """Giữ tối đa `MAX_PER_PLACE` mục mới nhất của mỗi nơi."""
    kept: list[dict] = []
    counts: dict[str, int] = {}
    for item in reversed(items):
        counts[item["place"]] = counts.get(item["place"], 0) + 1
        if counts[item["place"]] <= MAX_PER_PLACE:
            kept.append(item)
    return kept[::-1]


def facts(product: dict) -> str:
    """Một dòng thông tin của sản phẩm theo loại, chỉ trường cần để nhận ra sản phẩm ở câu hỏi tiếp; không mô tả, ảnh,
    địa chỉ đủ."""
    taxonomy = product.get("taxonomy")
    if taxonomy == "flight":
        return _flight_facts(product)
    parts = [taxonomy or "sản phẩm"]
    area = _area(product)
    if area:
        parts.append(area)
    attributes = product.get("attributes") or {}
    if taxonomy == "hotel":
        parts.append(_price(product))
        if isinstance(attributes.get("starRating"), (int, float)):
            parts.append(f"{attributes['starRating']:g} sao")
    elif attributes.get("ticketed") is False or not _positive(product.get("unitPrice")):
        parts.append("tham quan tự do, không mất vé")
    else:
        parts.append(_price(product))
    parts.append(_rating(product))
    if taxonomy == "hotel":
        parts.append(", ".join(_amenities(attributes)))
    else:
        hours = str(attributes.get("openingHours") or "").strip()
        if hours and len(hours) <= MAX_HOURS_TEXT:
            # Catalog có khi đã ghi "Mở cửa cả ngày": không thêm chữ "mở" lần nữa.
            parts.append(hours if fold(hours).startswith("mo ") else f"mở {hours}")
        duration = attributes.get("durationMinutes")
        if isinstance(duration, (int, float)) and 0 < duration < 24 * 60:
            parts.append(f"khoảng {_duration(duration)}")
        tags = [str(tag) for tag in (attributes.get("tags") or []) if isinstance(tag, str)][:MAX_TAGS]
        parts.append(", ".join(tags))
    return "; ".join(part for part in parts if part)


def _flight_facts(product: dict) -> str:
    attributes = product.get("attributes") or {}
    item = flight_rules.brief(product)
    parts = ["flight"]  # hãng và số hiệu nằm ở tên (`_label`)
    if attributes.get("originCity"):
        parts.append(_place(product))
    day = flight_rules.flight_date(product)
    if day:
        parts.append(day.strftime("%d/%m"))
    if item.get("departure"):
        parts.append(f"cất cánh {item['departure']}")
    cabin = CABIN_NAMES.get(CABIN_CODES.get(str(attributes.get("cabinClass") or "").upper(), ""))
    if cabin and cabin != CABIN_NAMES["ECO"]:
        parts.append(f"hạng {cabin}")
    parts.append(_price(product))
    if attributes.get("simulated"):
        parts.append("giá minh hoạ")
    return "; ".join(part for part in parts if part)


def _positive(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0


def _price(product: dict) -> str:
    """Giá niêm yết lúc gợi ý kèm đơn vị theo `priceUnit` ("1.200.000 ₫/đêm", "/khách", "/gói"); không có giá thì bỏ."""
    value = product.get("unitPrice")
    if not _positive(value):
        return ""
    unit = product.get("priceUnit")
    suffix = _UNITS.get(unit, "") if unit else _DEFAULT_UNITS.get(product.get("taxonomy"), "")
    return f"{money(value, 'vi')}{suffix}"


def _rating(product: dict) -> str:
    rating, reviews = product.get("rating"), product.get("reviewCount")
    if not _positive(rating):
        return ""
    text = f"{rating:g} điểm"
    if isinstance(reviews, int) and reviews > 0:
        text += f" ({_count(reviews)} đánh giá)"
    return text


def _count(value: int) -> str:
    """Số đánh giá làm tròn cho gọn: 4.712 → "4,7k"."""
    return f"{value / 1000:.1f}k".replace(".", ",").replace(",0k", "k") if value >= 1000 else str(value)


def _amenities(attributes: dict) -> list[str]:
    strings = [value for value in attributes.get("amenities") or [] if isinstance(value, str)]
    keys = set(amenity_keys(strings)) | {key for key in _AMENITY_ORDER if attributes.get(key) is True}
    return sorted(keys, key=lambda key: _AMENITY_ORDER.get(key, len(_AMENITY_ORDER)))[:MAX_AMENITIES]


def _duration(minutes: float) -> str:
    hours, rest = divmod(int(minutes), 60)
    if not hours:
        return f"{rest} phút"
    return f"{hours} giờ" + (f" {rest} phút" if rest else "")


def _area(product: dict) -> str:
    address = str((product.get("attributes") or {}).get("address") or "")
    found = _DISTRICT.search(address) or _WARD.search(address)
    return " ".join(found.group(0).split()) if found else ""
