"""Lời diễn giải lịch trình `COMPLETED` (node `narrate`): LLM viết, backend kiểm và điền dữ liệu thật.

LLM nhắc sản phẩm bằng link `[Tên](product:<productId>)` và ghi giá bằng placeholder `[[price:<id>]]`, `[[total]]`,
`[[budget]]`; nó không viết tên hay con số tiền nào mà backend không kiểm được. `render` thay tên trong link bằng tên
canonical, điền giá từ dữ liệu sản phẩm và từ chối mọi id lạ hoặc số tiền tự viết. Câu ghi nhận thay đổi ("Mình ghi nhận
đổi ngày đi thành 15/10/2026") do backend chèn vì nó phải luôn đúng. Không dùng được câu của LLM thì `fallback_message`
dựng cùng bố cục bằng luật.
"""
from __future__ import annotations

from copy import deepcopy
import re

from src.backend.app.domain.itinerary.planning import free_to_visit, multi_day_span

from ..models import ItineraryNarration
from .classification import TRIP_FIELDS
from .history import llm_context, prompt_yaml
from .messages import MAX_TITLE_CHARS, PRODUCT_LINK, display_date, message, strip_title, titled
from .messages import money as _money, party_text as _party
from .prompts import NARRATE_PROMPT

PLACEHOLDER = re.compile(r"\[\[(?:price:([^\[\]\s]{1,200})|(total)|(budget))\]\]")
#: Số tiền LLM tự viết (giá, tổng, ngân sách) — giá chỉ được đến từ placeholder.
RAW_MONEY = re.compile(r"\d[\d.,]*\s*(?:₫|đ\b|đồng|dong\b|vnd|vnđ|k\b|nghìn|ngàn|triệu|trieu|tr\b|usd|\$)",
                       re.IGNORECASE)
#: Hoạt động dài từ mức này chiếm trọn ngày (cùng ngưỡng với `planning.allowed_times`).
FULL_DAY_MINUTES = 360


def _display(state: dict, field: str, value) -> str:
    if field == "startDate":
        return display_date(value)
    if field == "party":
        return _party(state, value)
    if field == "budget":
        return _money(value, state.get("language", "vi"))
    return str(value)


def trip_changes(state: dict) -> list[dict]:
    """Trường chuyến đi lượt này đổi so với bản đã lưu; trường trước đó còn trống không tính là "đổi"."""
    before, after = state.get("previous_intent") or {}, state.get("intent") or {}
    return [{"field": field, "from": _display(state, field, before[field]), "to": _display(state, field, after[field])}
            for field in TRIP_FIELDS
            if before.get(field) is not None and after.get(field) is not None and before[field] != after[field]]


def changes_sentence(state: dict) -> str | None:
    changes = trip_changes(state)
    if not changes:
        return None
    parts = [message(state, f"change_to_{item['field']}", value=item["to"]) for item in changes]
    return message(state, "narrate_changes", changes=", ".join(parts))


def reference_note(state: dict, response: dict) -> str | None:
    """Câu mở đầu của lịch tham khảo: vé chưa mở bán cho ngày đi (cảnh báo `PRODUCT_NOT_ON_SALE_FOR_DATE` của
    `compose`), kèm ngày gần nhất còn bán. Code viết, không để LLM nói về ngày mở bán (chat thử 10/10: trợ lý chỉ nói
    "chưa có sản phẩm mở bán cho ngày này")."""
    flagged = [warning.get("productId") for warning in response.get("warnings", [])
               if warning.get("code") == "PRODUCT_NOT_ON_SALE_FOR_DATE"]
    intent = state.get("intent") or {}
    if not flagged or not intent.get("startDate"):
        return None
    ends = [state.get("candidates", {}).get(pid, {}).get("availableTo") for pid in flagged]
    ends = [end for end in ends if end]
    end = display_date(max(ends)) if ends else message(state, "sale_window_unknown")
    text = message(state, "reference_note", date=display_date(intent["startDate"]),
                   destination=intent.get("destination") or "", end=end)
    if state.get("nearest_open_date"):
        text += " " + message(state, "reference_nearest", destination=intent.get("destination") or "",
                              days=intent.get("days") or 1, nearest=display_date(state["nearest_open_date"]))
    return text


def _products(itinerary: dict) -> dict[str, dict]:
    """productId → sản phẩm đã xếp, theo thứ tự xuất hiện (stay trước, rồi từng slot)."""
    found = {}
    for stay in _stays(itinerary):
        found[stay["product"]["productId"]] = stay["product"]
    for day in itinerary.get("days", []):
        for slot in day.get("slots", []):
            if slot.get("product"):
                found.setdefault(slot["product"]["productId"], slot["product"])
    return found


def _stays(itinerary: dict) -> list[dict]:
    """Khách sạn theo đêm (AC-AGT-04); response cũ chỉ có `stay`."""
    stays = itinerary.get("stays") or ([itinerary["stay"]] if itinerary.get("stay") else [])
    return [stay for stay in stays if stay.get("product")]


def _nights_label(state: dict, stay: dict) -> str:
    first = stay.get("fromNight") or 1
    last = first + stay.get("nights", 1) - 1
    return message(state, "stay_night_single", first=first) if first == last else \
        message(state, "stay_nights_range", first=first, last=last)


def _flight_products(itinerary: dict) -> dict[str, dict]:
    """productId → vé máy bay của lịch trình; hệ thống tự viết mục riêng cho chúng, không qua câu LLM."""
    return {leg["product"]["productId"]: leg["product"] for leg in itinerary.get("flights", []) if leg.get("product")}


def _offers(response: dict) -> dict[str, dict]:
    """productId → gói/tour nhiều ngày trả kèm (`searchResults` của `COMPLETED`), không nằm trong lịch."""
    if response.get("status") not in (None, "COMPLETED"):
        return {}
    return {product["productId"]: product for products in (response.get("searchResults") or {}).values()
            for product in products}


def _price(state: dict, product: dict) -> str:
    if free_to_visit(product):
        return message(state, "free_entry")
    if product.get("unitPrice") is None:
        return message(state, "no_price")
    unit = product.get("priceUnit", "UNKNOWN")
    suffix = message(state, f"unit_{unit}") if unit in ("PER_NIGHT", "PER_PERSON", "PER_PACKAGE") else ""
    return _money(product["unitPrice"], state.get("language", "vi")) + suffix


def _stay_price(state: dict, stay: dict) -> str:
    """Giá một đêm của khách sạn, kèm số phòng khi đoàn ở từ 2 phòng (AC-AGT-04, chốt 2026-10-09)."""
    price = _price(state, stay["product"])
    rooms = stay.get("rooms") or 1
    if rooms > 1 and stay["product"].get("unitPrice") is not None:
        price += message(state, "stay_rooms", rooms=rooms)
    return price


def _time_label(state: dict, slot: dict) -> str:
    duration = (slot.get("product") or {}).get("attributes", {}).get("durationMinutes")
    if isinstance(duration, (int, float)) and duration >= FULL_DAY_MINUTES:
        return message(state, "time_FULL_DAY")
    return message(state, f"time_{slot['time']}")


def _day_heading(state: dict, day: dict) -> str:
    heading = message(state, "section_day", day=day["day"])
    return f"{heading} · {display_date(day['date'])}" if day.get("date") else heading


def _label(product: dict) -> str:
    """Tên hiển thị trong link: bỏ `[` `]` vì catalog có tên dạng "[Grand World Phú Quốc] - Vé…" và dấu ngoặc vuông lồng
    trong nhãn làm hỏng cú pháp `[Tên](product:id)` (frontend không nhận ra link, id hiện thô trong chat)."""
    return " ".join(re.sub(r"[\[\]]", " ", product["name"]).split()) or product["productId"]


def product_link(product: dict) -> str:
    """`[Tên](product:id)` của một sản phẩm, tên đã qua `_label`; dùng chung cho mọi câu do code dựng."""
    return f"[{_label(product)}](product:{product['productId']})"


def narration_input(state: dict) -> list:
    """Lịch đã dựng (không kèm con số giá) cộng ngữ cảnh hội thoại chung; LLM chỉ viết câu chữ."""
    response = state["response"]
    itinerary = response["itinerary"]
    view = {"stays": [], "days": []}
    for stay in _stays(itinerary):
        view["stays"].append({"productId": stay["product"]["productId"], "name": _label(stay["product"]),
                              "price_known": stay["product"].get("unitPrice") is not None,
                              "nights": stay.get("nights"), "from_night": stay.get("fromNight") or 1,
                              "note": stay.get("note"), "because": stay.get("because") or []})
    for day in itinerary.get("days", []):
        view["days"].append({
            "day": day["day"], "date": display_date(day["date"]) if day.get("date") else None,
            "items": [{"time": _time_label(state, slot), "productId": slot["product"]["productId"],
                       "name": _label(slot["product"]), "taxonomy": slot["product"].get("taxonomy"),
                       "durationMinutes": slot["product"].get("attributes", {}).get("durationMinutes"),
                       "free_to_visit": free_to_visit(slot["product"]),
                       "note": slot.get("note"), "because": slot.get("because") or []}
                      if slot.get("product") else
                      {"time": _time_label(state, slot), "activityType": slot.get("activityType"), "note": slot.get("note")}
                      for slot in day.get("slots", [])]})
    if reference_note(state, response) is not None:
        # Lịch tham khảo (vé chưa mở bán cho ngày đi): LLM kể chuyện từng nơi nên cần mô tả catalog của nó.
        from .exploration import about  # import muộn: exploration dùng product_link của module này
        candidates = state.get("candidates") or {}
        for day in view["days"]:
            for item in day["items"]:
                if item.get("productId") in candidates:
                    item["about"] = about(candidates[item["productId"]])
    offers = [{"productId": product["productId"], "name": _label(product), "days_covered": multi_day_span(product),
               "price_known": product.get("unitPrice") is not None} for product in _offers(response).values()]
    language = "Vietnamese" if state.get("language", "vi") == "vi" else "English"
    payload = {"message": state.get("query", ""), **llm_context(state),
               "itinerary": view, "consider_separately": offers, "changes": trip_changes(state),
               "budgetStatus": itinerary.get("budgetStatus"), "total_known": itinerary.get("estimatedTotal") is not None,
               "no_stay_explained": _no_stay_block(state, response) is not None,
               "reference_only": reference_note(state, response) is not None,
               "flights_shown_separately": _flights_block(state, response) is not None,
               "criteria_shown_separately": _criteria_block(state, response) is not None,
               "has_budget": state["intent"].get("budget") is not None}
    return [("system", NARRATE_PROMPT + f"\nReply in {language}."), ("human", prompt_yaml(payload))]


def _default_title(state: dict) -> str:
    intent = state["intent"]
    return message(state, "narrate_title", days=intent.get("days"), destination=intent.get("destination"))


def _cost_line(state: dict, itinerary: dict) -> str:
    status = itinerary.get("budgetStatus", "UNKNOWN")
    if itinerary.get("estimatedTotal") is None:
        return message(state, "cost_UNKNOWN")
    language = state.get("language", "vi")
    budget = state["intent"].get("budget")
    return message(state, f"cost_{status}", total=_money(itinerary["estimatedTotal"], language),
                   budget=_money(budget, language) if budget is not None else message(state, "no_budget"))


def _offers_block(state: dict, offers) -> str:
    lines = [f"• {product_link(product)} — {message(state, 'offer_days', days=multi_day_span(product) or 2)}" for product in offers]
    return f"**{message(state, 'section_offers')}**\n" + "\n".join(lines) + f"\n{message(state, 'offers_question')}"


def _before_cost(state: dict, body: str, block: str) -> str:
    """Chèn một mục do hệ thống viết ngay trước mục chi phí; không có mục chi phí thì nối vào cuối."""
    heading = f"**{message(state, 'section_cost')}"
    position = body.find(heading)
    if position < 0:
        return f"{body}\n\n{block}"
    return f"{body[:position]}{block}\n\n{body[position:]}"


def _with_offers(state: dict, body: str, offers) -> str:
    return _before_cost(state, body, _offers_block(state, offers))


def _flights_block(state: dict, response: dict) -> str | None:
    """Mục "Vé máy bay" dựng bằng luật (AC-AGT-02): từng vé kèm ngày, giờ, giá × số khách; hoặc lý do chưa có vé."""
    language = state.get("language", "vi")
    lines = []
    for leg in response["itinerary"].get("flights", []):
        product, attributes = leg["product"], leg["product"].get("attributes", {})
        when = display_date(leg["date"]) + (f" – {display_date(leg['returnDate'])}" if leg.get("returnDate") else "")
        bits = [when]
        clock = attributes.get("departureTimeLocal") or str(attributes.get("departureAt") or "")[11:16]
        if clock:
            bits.append(clock)
        if attributes.get("nonstop") is True:
            bits.append(message(state, "flight_nonstop"))

        lines.append(f"• {message(state, 'flight_' + leg['direction'])} — {product_link(product)} · {' · '.join(bits)}")
    lines += [warning["message"] for warning in response.get("warnings", [])
              if str(warning.get("code", "")).startswith("FLIGHT_")]
    return f"**{message(state, 'section_flights')}**\n" + "\n".join(lines) if lines else None


def _before_sections(body: str, block: str) -> str:
    """Chèn mục do hệ thống viết ngay sau câu mở đầu, trước mục in đậm đầu tiên."""
    position = body.find("\n\n**")
    return f"{body}\n\n{block}" if position < 0 else f"{body[:position]}\n\n{block}{body[position:]}"


def _no_stay_block(state: dict, response: dict) -> str | None:
    """Mục "Chưa có khách sạn" nêu lý do thật (cảnh báo `NO_STAY_AVAILABLE` của `compose`); None khi đã có chỗ ở."""
    note = next((warning["message"] for warning in response.get("warnings", [])
                 if warning.get("code") == "NO_STAY_AVAILABLE"), None)
    return f"**{message(state, 'section_no_stay')}**\n{note}" if note else None


def _criteria_block(state: dict, response: dict) -> str | None:
    """Mục "Cách mình xếp lịch" (cảnh báo `PLAN_CRITERIA` của `compose`, AC-AGT-04); None khi lịch không xếp theo vị trí."""
    note = next((warning["message"] for warning in response.get("warnings", [])
                 if warning.get("code") == "PLAN_CRITERIA"), None)
    return f"**{message(state, 'section_criteria')}**\n{note}" if note else None


def fallback_message(state: dict, response: dict) -> str:
    """Bản dựng bằng luật, cùng bố cục với câu LLM: tiêu đề, ghi nhận thay đổi, nơi nghỉ, từng ngày, chi phí, lưu ý."""
    itinerary = response["itinerary"]
    blocks = [changes_sentence(state) or message(state, "narrate_intro")]
    if (note := reference_note(state, response)):
        blocks.insert(0, note)
    flights = _flights_block(state, response)
    if flights:
        blocks.append(flights)
    stays = _stays(itinerary)
    if len(stays) == 1:
        stay = stays[0]
        blocks.append(f"**{message(state, 'section_stay')}**\n• {product_link(stay['product'])} — "
                      f"{message(state, 'stay_nights', nights=stay.get('nights', 1))}")
    elif stays:
        # Đổi khách sạn giữa chuyến (AC-AGT-04): mỗi khách sạn một dòng, kèm các đêm ở đó.
        blocks.append(f"**{message(state, 'section_stay')}**\n" + "\n".join(
            f"• {_nights_label(state, stay)} — {product_link(stay['product'])}"
            for stay in stays))
    for day in itinerary.get("days", []):
        # Slot đã theo thứ tự buổi; dòng di chuyển ngày đến/ngày về (AC-AGT-02) in bằng ghi chú của nó.
        lines = [f"• {_time_label(state, slot)} — " + (f"{product_link(slot['product'])}"
                                                       if slot.get("product") else slot["note"])
                 for slot in day.get("slots", []) if slot.get("product") or slot.get("activityType") == "TRANSFER"]
        blocks.append(f"**{_day_heading(state, day)}**\n" + ("\n".join(lines) or message(state, "free_day")))
    offers = _offers(response)
    if offers:
        blocks.append(_offers_block(state, offers.values()))
    no_stay = _no_stay_block(state, response)
    if no_stay:
        blocks.append(no_stay)
    criteria = _criteria_block(state, response)
    if criteria:
        blocks.append(criteria)
    if itinerary.get("estimatedTotal") is None:
        blocks.append(_cost_line(state, itinerary))
    blocks.append(f"**{message(state, 'section_notes')}**\n{message(state, 'narrate_notes')}\n"
                  f"{message(state, 'narrate_outro')}")
    return titled(itinerary.get("title") or _default_title(state), "\n\n".join(blocks))


#: `(product:<id>)` đứng lẻ, không ngay sau `]` của một link đúng cú pháp.
STRAY_PRODUCT = re.compile(r"(?<!\])\s*\(product:([^()\s]{1,200})\)")


def _repair_links(body: str, products: dict[str, dict]) -> str:
    """Sửa link LLM viết lệch cú pháp nhưng trỏ đúng sản phẩm trong lịch, thay vì bỏ cả bài viết.

    Trace thật (gpt-4o-mini, tên catalog "[Grand World Phú Quốc] - Vé…"): LLM viết
    `[Grand World Phú Quốc] - Vé… (product:id)` hoặc `[[Grand World…] - Vé…](product:id)`. Tên (gốc hoặc đã bỏ ngoặc)
    đứng ngay trước `(product:id)` thì gộp thành link chuẩn; `(product:id)` lẻ còn lại của id đã biết thì bỏ đi, sản
    phẩm đó vẫn được thêm vào mục "Ngoài ra" để bấm được. Id lạ giữ nguyên để kiểm grounding phía sau bác bỏ.
    """
    for product_id, product in products.items():
        for name in sorted({product["name"], _label(product)}, key=len, reverse=True):
            pattern = re.compile(r"\[?" + re.escape(name) + r"\]?\s*\(product:" + re.escape(product_id) + r"\)")
            body = pattern.sub(lambda _match, product=product: product_link(product), body)
    return STRAY_PRODUCT.sub(lambda match: "" if match.group(1) in products else match.group(0), body)


def _link_plain_mention(body: str, product: dict) -> str | None:
    """Gắn link vào lần đầu tên sản phẩm được nhắc bằng chữ thường (ngoài mọi link có sẵn); không thấy thì `None`.

    Trace thật: LLM viết "ghé thăm Cầu Hôn Phú Quốc" không kèm link; trước đây sản phẩm bị dồn xuống mục "Ngoài ra"
    ở cuối, trông như câu trả lời bị cắt dở.
    """
    for name in sorted({product["name"], _label(product)}, key=len, reverse=True):
        start = 0
        for match in [*PRODUCT_LINK.finditer(body), None]:
            end = match.start() if match else len(body)
            position = body.find(name, start, end)
            if position >= 0:
                return body[:position] + product_link(product) + body[position + len(name):]
            if match:
                start = match.end()
    return None


def render(state: dict, response: dict, narration: ItineraryNarration) -> tuple[str | None, str | None, str]:
    """(title, message, lý do) từ câu LLM; `message` là `None` khi câu không dùng được (lý do nói vì sao)."""
    narration = ItineraryNarration.model_validate(narration)
    scheduled, offers = _products(response["itinerary"]), _offers(response)
    products = {**scheduled, **offers, **_flight_products(response["itinerary"])}
    body = _repair_links(strip_title(narration.message.strip()), products)
    if "[[" in PLACEHOLDER.sub("", body) or "]]" in PLACEHOLDER.sub("", body):
        return None, None, "unknown_placeholder"
    without_tokens = PRODUCT_LINK.sub(" ", PLACEHOLDER.sub(" ", body))
    if RAW_MONEY.search(without_tokens):
        return None, None, "raw_money"
    if "product:" in without_tokens:
        return None, None, "malformed_link"
    linked = [match.group(2) for match in PRODUCT_LINK.finditer(body)]
    priced = [match.group(1) for match in PLACEHOLDER.finditer(body) if match.group(1)]
    if any(product_id not in products for product_id in linked + priced):
        return None, None, "unknown_product"

    stays = {stay["product"]["productId"]: stay for stay in _stays(response["itinerary"])}

    def fill(match: re.Match) -> str:
        if match.group(1):
            stay = stays.get(match.group(1))
            return _stay_price(state, stay) if stay else _price(state, products[match.group(1)])
        itinerary, language = response["itinerary"], state.get("language", "vi")
        if match.group(2):
            total = itinerary.get("estimatedTotal")
            return _money(total, language) if total is not None else message(state, "no_total")
        budget = state["intent"].get("budget")
        return _money(budget, language) if budget is not None else message(state, "no_budget")

    body = "\n".join(line.rstrip() for line in body.splitlines())
    body = PRODUCT_LINK.sub(lambda match: product_link(products[match.group(2)]), body)
    # Legacy models may still emit old placeholders; validate IDs above, then remove duplicated prices.
    body = re.sub(r"\s*[·—,:]?\s*\(?" + PLACEHOLDER.pattern + r"\)?", "", body)
    body = re.sub(r"(?m)^\*\*" + re.escape(message(state, "section_cost")) + r"[^\n]*\n(?:(?!^\*\*)[^\n]*(?:\n|$))*", "", body)
    body = re.sub(r"vé tham quan tự do", "địa điểm tham quan", body, flags=re.I)
    missing = []
    for product_id, product in scheduled.items():
        if product_id in linked:
            continue
        linked_inline = _link_plain_mention(body, product)
        if linked_inline is None:
            missing.append(product)
        else:
            body = linked_inline
    if missing:
        # Mọi sản phẩm đã xếp đều phải bấm được từ khung chat, kể cả khi LLM quên nhắc.
        body += f"\n\n**{message(state, 'section_more')}**\n" + "\n".join(f"• {product_link(product)}" for product in missing)
    if offers:
        # Gói nhiều ngày luôn được hỏi riêng bằng câu cố định (LLM hay quên câu hỏi): chèn trước mục chi phí.
        body = _with_offers(state, body, offers.values())
    no_stay = _no_stay_block(state, response)
    if no_stay:
        # Lý do không có chỗ ở lấy từ dữ liệu tool, không để LLM tự diễn đạt: chèn trước mục chi phí.
        body = _before_cost(state, body, no_stay)
    criteria = _criteria_block(state, response)
    if criteria:
        # Tiêu chí xếp lịch là luật của hệ thống, không để LLM tự diễn đạt (AC-AGT-04): chèn trước mục chi phí.
        body = _before_cost(state, body, criteria)
    flights = _flights_block(state, response)
    if flights:
        # Vé và lý do thiếu vé lấy từ dữ liệu catalog, không để LLM diễn đạt: chèn trước mục đầu tiên.
        body = _before_sections(body, flights)
    changes = changes_sentence(state)
    if changes:
        body = f"{changes}\n\n{body}"
    note = reference_note(state, response)
    if note:
        # Vé chưa mở bán cho ngày đi: câu mở đầu do code viết, đứng trước mọi phần khác.
        body = f"{note}\n\n{body}"
    # Cùng cách làm sạch với `titled`, để `itinerary.title` (header khung bên phải) khớp dòng tiêu đề trong chat.
    title = " ".join((narration.title or "").replace("*", " ").split())[:MAX_TITLE_CHARS].strip() or _default_title(state)
    return title, titled(title, body), "llm"


def narrated(state: dict, narration: ItineraryNarration | None) -> tuple[dict, str]:
    """Response `COMPLETED` kèm `message` và `itinerary.title`; câu LLM không dùng được thì dùng bản dựng bằng luật."""
    response = deepcopy(state["response"])
    title, text, reason = render(state, response, narration) if narration is not None else (None, None, "llm_failed")
    if text is None:
        response["itinerary"]["title"] = response["itinerary"].get("title") or _default_title(state)
        response["message"] = fallback_message(state, response)
    else:
        response["itinerary"]["title"] = title
        response["message"] = text
    chip = reference_chip(state, response)
    if chip:
        response["suggestions"] = [chip]
    return {"response": response}, reason


def reference_chip(state: dict, response: dict) -> str | None:
    """Nút lập lại lịch từ ngày gần nhất còn bán, dưới lịch tham khảo (contract 1.25.0; chat thử M09: chỉ có câu "bạn
    nhắn …", không bấm được). Cùng chữ với câu `reference_nearest`, `extract` đọc được như mọi câu chat."""
    intent = state.get("intent") or {}
    if not state.get("nearest_open_date") or reference_note(state, response) is None:
        return None
    return message(state, "chip_reference_nearest", destination=intent.get("destination") or "",
                   days=intent.get("days") or 1, nearest=display_date(state["nearest_open_date"]))


def unknown_links(response: dict) -> list[str]:
    """productId được link trong `message` mà không có trong `itinerary` — vi phạm grounding."""
    known = {**_products(response.get("itinerary", {})), **_offers(response),
             **_flight_products(response.get("itinerary", {}))}
    return [match.group(2) for match in PRODUCT_LINK.finditer(response.get("message") or "")
            if match.group(2) not in known]
