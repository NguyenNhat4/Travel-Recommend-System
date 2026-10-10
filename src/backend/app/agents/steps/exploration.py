"""Lượt khám phá trước khi lập lịch và nút gợi ý (FR-AGT-06, chốt 2026-10-10).

Người dùng hỏi "Hà Nội có gì?", "khách sạn nào có hồ bơi?" khi chưa đồng ý lập lịch: trợ lý trả lời bằng thẻ sản phẩm
thật thay vì hỏi số ngày hay hiện form. Việc chia như mọi node khác: code tìm (Search), chọn thẻ và lý do
(`domain/itinerary/exploration.py`), điền mọi con số; LLM chỉ viết câu dẫn và đề xuất nút. LLM lỗi thì câu dẫn do
code dựng từ lý do, lượt vẫn trả lời được.
"""
from __future__ import annotations

import asyncio
import re

from src.backend.app.application.ports.itinerary_tools import ToolError, ToolExecutorPort
from src.backend.app.domain.itinerary import exploration as rules
from src.backend.app.domain.itinerary import preferences
from src.backend.app.domain.itinerary.normalization import fold
from src.backend.app.domain.itinerary.planning import summary
from src.backend.app.domain.search.normalize import DESTINATION_ALIASES

from ..models import ExploreNarration
from . import tool_planning
from .classification import REQUIRED_FIELDS, asks_for_plan
from .history import llm_context, prompt_yaml
from .messages import PRODUCT_LINK, event, message, money, titled
from .narration import product_link
from .prompts import EXPLORE_PROMPT

#: Tối đa 4 thẻ mỗi lượt (khung chat hẹp): hỏi chung thì 2 điểm tham quan + 2 khách sạn, hỏi riêng một loại thì 4.
MAX_CARDS = 4
#: Hỏi về chỗ ở (so trên chuỗi đã `fold`).
_HOTEL_FOCUS = re.compile(r"\b(?:khach san|ks|resort|homestay|hostel|cho o|cho nghi|noi o|o dau|villa|nha nghi|hotel)\b")
_POOL = re.compile(r"\b(?:ho boi|be boi|pool)\b")
#: Hỏi quanh một nơi ("gần Văn Miếu có gì?"): khác với hỏi về chính nơi đó.
_AROUND = re.compile(r"\b(?:gan|quanh|canh|xung quanh|lan can|near|around)\b")
_PLACEHOLDER = re.compile(r"\[\[(price|rating|reviews):([^\]\s]{1,200})\]\]")
MAX_SUGGESTION_CHARS = 60
MAX_SUGGESTIONS = 3
#: Số điểm đến của catalog đưa cho LLM để gợi ý nút (nhiều sản phẩm nhất trước).
CATALOG_HINT = 12
NAMED_CALL_ID = "explore-named"
PLACE_CALL_ID = "explore-place"
#: Mô tả catalog đưa cho LLM, đủ để nói điểm đó có gì hay mà không làm prompt dài.
ABOUT_CHARS = 360
#: Câu trong mô tả catalog chỉ chứa số liệu (giờ, địa chỉ, thời lượng): thẻ bên phải đã hiện, câu chat không nhắc lại.
_DATA_SENTENCE = re.compile(r"^\s*(?:gio mo cua|dia chi|thoi gian tham quan|loai hinh|dia diem|toi da|\d)")
#: Người dùng hỏi về giá: chỉ khi đó câu chat mới nêu giá; còn lại giá chỉ nằm trên thẻ.
_PRICE_ASKED = re.compile(r"\b(?:gia(?! dinh)|bao nhieu|re|mem|tiet kiem|binh dan|dat do|dat qua|chi phi|het bao)\b")


def _named_destination(query: str, supported: list[str]) -> str | None:
    """Điểm đến của catalog được nhắc trong câu, kể cả cách gọi khác đã biết ("hn", "Sài Gòn", "pq",
    `domain/search/normalize.DESTINATION_ALIASES`); nhiều tên thì lấy tên dài nhất."""
    text = f" {fold(query)} "
    named = [name for name in supported if fold(name) and f" {fold(name)} " in text]
    allowed = set(supported)
    named += [name for alias, name in DESTINATION_ALIASES.items() if name in allowed and f" {fold(alias)} " in text]
    return max(named, key=len) if named else None


def destination_for(state: dict, supported: list[str] | None) -> str | None:
    """Điểm đến cần khám phá, bỏ qua nơi người dùng đã chê: nơi câu này nhắc tới, nơi trợ lý tự chọn (bậc 2 của "không
    biết", hoặc vừa bị chê) theo thứ tự nhiều sản phẩm nhất, rồi điểm đến của chuyến."""
    rejected = {fold(name) for name in state.get("rejected_destinations") or []}
    allowed = [name for name in supported or [] if fold(name) not in rejected]
    named = _named_destination(state.get("query", ""), allowed)
    if named:
        return named
    current = (state.get("intent") or {}).get("destination")
    if state.get("explore_pick") or (current and fold(current) in rejected):
        return allowed[0] if allowed else None
    return current


def _pattern(text: str, destinations: list[str]) -> str:
    """Mẫu câu của một nút: bỏ tên điểm đến và chữ số, để "Hà Nội có gì?" và "Đà Nẵng có gì?" là cùng một mẫu."""
    key = f" {fold(text)} "
    for name in sorted(destinations, key=len, reverse=True):
        if fold(name):
            key = key.replace(f" {fold(name)} ", " _ ")
    return " ".join(re.sub(r"\d+", "#", key).split())


def checked_suggestions(proposed: list[str], previous: list[str], templates: list[str], *,
                        destinations: list[str], plan_chip: str | None = None,
                        avoid: list[str] | None = None) -> list[str]:
    """Tối đa 3 nút: bỏ nút rỗng, quá dài, lặp nút lượt trước, nhắc nơi bị chê (`avoid`) hoặc trùng mẫu câu với nút đã
    giữ (AC-AGT-07).

    `plan_chip` (nút đi tiếp: lập lịch, tiếp tục lập lịch) luôn có một chỗ khi chưa nút nào xin lập lịch. Thiếu nút thì
    bù bằng `templates` theo cùng luật.
    """
    seen_text = {fold(item) for item in previous}
    avoided = [fold(name) for name in avoid or [] if fold(name)]
    kept: list[str] = []
    patterns: set[str] = set()

    def add(text: str) -> None:
        clean = " ".join(str(text or "").split())
        if not clean or len(clean) > MAX_SUGGESTION_CHARS or fold(clean) in seen_text or len(kept) >= MAX_SUGGESTIONS:
            return
        if any(f" {name} " in f" {fold(clean)} " for name in avoided):
            return
        pattern = _pattern(clean, destinations)
        if pattern in patterns:
            return
        patterns.add(pattern)
        kept.append(clean)

    for item in proposed:
        add(item)
    if plan_chip and not any(asks_for_plan(item) for item in kept):
        if len(kept) >= MAX_SUGGESTIONS:
            dropped = kept.pop()
            patterns.discard(_pattern(dropped, destinations))
        seen_text.discard(fold(plan_chip))
        add(plan_chip)
        kept.sort(key=lambda item: not asks_for_plan(item))  # nút đi tiếp đứng đầu
    for item in templates:
        if len(kept) >= 2:
            break
        add(item)
    return kept


def conversation_templates(state: dict, supported: list[str] | None) -> list[str]:
    """Nút dự phòng của lượt trò chuyện, mỗi nút một hướng (xem một nơi, kiểu chuyến, để trợ lý chọn); nút lặp lượt trước
    bị `checked_suggestions` bỏ nên có dư để bù."""
    rejected = {fold(name) for name in state.get("rejected_destinations") or []}
    places = [name for name in (supported or []) if name and fold(name) not in rejected][:1]
    chips = [message(state, "chip_sights", destination=place) for place in places]
    return [*chips, message(state, "chip_beach"), message(state, "chip_pick"), message(state, "chip_cool")]


def _search_call(state: dict, destination: str, taxonomy: str, query: str, index: int) -> dict | None:
    """Một lời gọi Search đã ép đúng hợp đồng tool, như các lời gọi của tool plan (`tool_planning._validated_args`)."""
    scoped = {**state, "intent": {**(state.get("intent") or {}), "destination": destination}}
    try:
        args = tool_planning._validated_args(scoped, {"name": "search_products",
                                                      "args": {"query": query, "taxonomy": taxonomy,
                                                               "destination": destination}})
    except ToolError:
        return None
    return {"id": f"explore-{index}-{taxonomy}", "name": "search_products", "args": args}


def _products(results: list[dict], destination: str, taxonomy: str) -> list[dict]:
    """Sản phẩm đúng loại, đúng điểm đến và còn bán, theo thứ tự Search trả về."""
    items = []
    for result in results:
        for product in (result.get("data") or {}).get("results", []):
            if (product.get("taxonomy") == taxonomy and product.get("available") is not False
                    and fold(product.get("destination")) == fold(destination) and product.get("productId")):
                items.append(product)
    return items


def hotel_focus(state: dict) -> bool:
    """Câu hỏi riêng về chỗ ở ("khách sạn nào…", "ở đâu", "có hồ bơi không")."""
    query = fold(state.get("query", ""))
    return bool(_HOTEL_FOCUS.search(query) or _POOL.search(query))


def _asked(state: dict, destination: str, results: list[dict]) -> dict | None:
    """Nơi người dùng nêu tên ("Văn Miếu buổi tối có mở không?"), tìm trong lượt Search bằng nguyên câu hỏi."""
    named = [result for result in results if result.get("tool_call_id") == NAMED_CALL_ID]
    products = [product for taxonomy in ("attraction", "hotel") for product in _products(named, destination, taxonomy)]
    return rules.named_in(products, state.get("query", ""), exclude=[destination])


def asked_only(state: dict, cards: list[dict]) -> bool:
    """Lượt chỉ trả lời về một nơi người dùng nêu tên ("Văn Miếu buổi tối có mở không?"): một thẻ, lý do `asked`."""
    return len(cards) == 1 and rules.ASKED in cards[0]["reasons"]


def pick(state: dict, destination: str, results: list[dict]) -> tuple[list[dict], str | None]:
    """Thẻ của lượt này và tiện ích đã dùng để lọc (`pool`) nếu có. Nơi câu hỏi nêu tên đứng đầu (lý do `asked`).

    Câu hỏi về chính một nơi (giờ mở cửa, giá vé, có gì) chỉ trả thẻ nơi đó: kịch bản cảnh 9 và chat thử 10/10, nơi
    thẻ chung (điểm khác, khách sạn) làm lệch câu trả lời. Hỏi quanh nơi đó ("gần Văn Miếu có gì?") thì vẫn gợi ý thêm.
    """
    query = fold(state.get("query", ""))
    asked = _asked(state, destination, results)
    if asked and not hotel_focus(state):
        if not _AROUND.search(query):
            return [{"product": asked, "reasons": [rules.ASKED]}], None
        # Hỏi quanh một nơi: các điểm tham quan gần nó nhất, không lặp lại chính nó, không chen khách sạn.
        general = [result for result in results if result.get("tool_call_id") != NAMED_CALL_ID]
        others = _products(general, destination, "attraction") + _products(results, destination, "attraction")
        near = rules.near_cards(others, asked, MAX_CARDS - 1)
        if near:
            return near, None
    general = [result for result in results if result.get("tool_call_id") != NAMED_CALL_ID]
    hotels = _products(general, destination, "hotel")
    filtered_by = None
    if _POOL.search(query):
        hotels, filtered_by = rules.with_amenity(hotels, "pool"), "pool"
    first = [{"product": asked, "reasons": [rules.ASKED]}] if asked else []
    skip = {asked["productId"]} if asked else set()
    if hotel_focus(state):
        hotels = [item for item in hotels if item["productId"] not in skip]
        return first + rules.pick_cards(hotels, MAX_CARDS - len(first), "hotel"), filtered_by
    attractions = [item for item in _products(general, destination, "attraction") if item["productId"] not in skip]
    hotels = [item for item in hotels if item["productId"] not in skip]
    hotel_cards = rules.pick_cards(hotels, MAX_CARDS // 2, "hotel")
    attraction_cards = rules.pick_cards(attractions, MAX_CARDS - len(hotel_cards) - len(first), "attraction")
    return first + attraction_cards + hotel_cards, filtered_by


async def place_destination(state: dict, supported: list[str] | None, tools: ToolExecutorPort,
                            timeout_seconds: float) -> str | None:
    """Câu nêu tên một nơi mà không nêu thành phố ("Văn Miếu buổi tối có mở không?"): tìm nguyên câu trên cả catalog,
    nơi khớp tên thì lấy điểm đến của chính sản phẩm đó. Điểm đến đến từ catalog, không để LLM đoán (LLM thật đoán ra
    Hà Nội lúc có lúc không, 2026-10-10)."""
    rejected = {fold(name) for name in state.get("rejected_destinations") or []}
    allowed = [name for name in supported or [] if fold(name) not in rejected]
    if not allowed:
        return None
    unscoped = {**state, "intent": {**(state.get("intent") or {}), "destination": None}, "tool_results": []}
    try:
        args = tool_planning._validated_args(unscoped, {"name": "search_products",
                                                        "args": {"query": state.get("query", ""),
                                                                 "taxonomy": "attraction"}})
    except ToolError:
        return None
    results = await tool_planning.run_calls(unscoped, [{"id": PLACE_CALL_ID, "name": "search_products", "args": args}],
                                            tools, timeout_seconds)
    products = [product for result in results for product in (result.get("data") or {}).get("results", [])
                if product.get("productId") and product.get("available") is not False]
    named = rules.named_in(products, state.get("query", ""), exclude=allowed)
    destination = (named or {}).get("destination")
    return next((name for name in allowed if fold(name) == fold(destination)), None) if destination else None


async def search(state: dict, destination: str, tools: ToolExecutorPort, timeout_seconds: float) -> list[dict]:
    """Search điểm tham quan và khách sạn của điểm đến song song; hỏi riêng chỗ ở thì chỉ khách sạn."""
    query = fold(state.get("query", ""))
    hotel_query = "khách sạn có hồ bơi" if _POOL.search(query) else "khách sạn được đánh giá tốt"
    calls = [_search_call(state, destination, "hotel", hotel_query, 0)]
    if not hotel_focus(state):
        calls.append(_search_call(state, destination, "attraction", "điểm tham quan nổi tiếng", 1))
    # Thêm một lượt bằng nguyên câu hỏi, để câu nêu tên một nơi ("Văn Miếu buổi tối có mở không?") ra đúng nơi đó.
    named = _search_call(state, destination, "attraction", state.get("query", ""), 2)
    if named is not None:
        calls.append({**named, "id": NAMED_CALL_ID})
    plan = [call for call in calls if call is not None]
    return await tool_planning.run_calls({**state, "tool_results": []}, plan, tools, timeout_seconds)


def _price_text(state: dict, product: dict) -> str:
    if rules.free_entry(product):
        return message(state, "explore_price_free")
    value = rules.price(product)
    if value is None:
        return message(state, "explore_price_unknown")
    return message(state, "explore_price_from", money=money(value, state.get("language", "vi")))


def price_asked(state: dict) -> bool:
    return bool(_PRICE_ASKED.search(fold(state.get("query", ""))))


def _fill(state: dict, text: str, products: dict[str, dict]) -> str:
    """Thay placeholder số bằng dữ liệu sản phẩm; placeholder của id lạ hoặc số thiếu thì bỏ đi.

    Điểm và lượt đánh giá không vào câu chat (thẻ bên phải đã hiện, góp ý người dùng 2026-10-10); giá chỉ vào khi
    người dùng hỏi giá. LLM có lỡ viết placeholder đó thì cũng bị bỏ ở đây.
    """
    with_price = price_asked(state)

    def value(match: re.Match) -> str:
        kind, product_id = match.group(1), match.group(2)
        product = products.get(product_id)
        if product is None or kind != "price" or not with_price:
            return ""
        return _price_text(state, product)

    filled = _PLACEHOLDER.sub(value, text)
    # Chỗ placeholder bị bỏ để lại ngoặc rỗng hoặc dấu cách đôi.
    filled = re.sub(r"\(\s*[,;]?\s*\)", "", filled)
    filled = re.sub(r"[ \t]+([.,;:!?])", r"\1", filled)
    return "\n".join(" ".join(line.split()) for line in filled.split("\n"))


def _unlink_unknown(text: str, products: dict[str, dict]) -> str:
    """Link tới sản phẩm không có trong thẻ thì chỉ giữ chữ: lời dẫn không được nhắc sản phẩm ngoài kết quả."""
    return PRODUCT_LINK.sub(lambda match: match.group(0) if match.group(2) in products else match.group(1), text)


#: Câu mô tả trong dòng dự phòng: một câu, cắt ở dấu phẩy nếu dài.
SHORT_ABOUT_CHARS = 160


def _short_about(product: dict) -> str:
    """Câu đầu mô tả của một điểm tham quan. Khách sạn không dùng: mô tả của chúng là văn quảng cáo ("Chỗ Nghỉ Thanh
    Lịch: …"), cắt ra thành câu cụt."""
    if product.get("taxonomy") == "hotel":
        return ""
    first = re.split(r"(?<=[.!?])\s+", about(product), maxsplit=1)[0].rstrip(".!? ")
    if len(first) > SHORT_ABOUT_CHARS:
        cut = first[:SHORT_ABOUT_CHARS]
        first = cut.rsplit(",", 1)[0] if "," in cut else cut.rsplit(" ", 1)[0]
    return first


#: Cụm tiện ích trong dòng dự phòng của khách sạn ("khách sạn có hồ bơi, spa"); trẻ nhỏ nói riêng ("hợp gia đình có trẻ
#: nhỏ") vì không đọc được sau chữ "có".
_FEATURE_WORDS = {"pool": "hồ bơi", "seaView": "view biển", "breakfast": "bữa sáng", "spa": "spa"}


def _hotel_features(product: dict, reason: str) -> str:
    found = {item.key for item in preferences.PREFERENCES if preferences.satisfies(product, item)}
    parts = []
    words = [word for key, word in _FEATURE_WORDS.items() if key in found]
    if words:
        parts.append("khách sạn có " + ", ".join(words))
    if "familyFriendly" in found:
        parts.append("hợp gia đình có trẻ nhỏ")
    return ", ".join([*parts, reason])


def card_line(state: dict, card: dict) -> str:
    """Dòng dẫn do code dựng cho một thẻ: câu mô tả của catalog (nơi đó là gì), không có thì lý do đầu tiên; giá chỉ khi
    người dùng hỏi giá. Điểm, lượt đánh giá, giờ mở cửa nằm trên thẻ."""
    product = card["product"]
    reason = (_short_about(product) if state.get("language", "vi") == "vi" else "") \
        or message(state, f"reason_{card['reasons'][0]}")
    if product.get("taxonomy") == "hotel" and state.get("language", "vi") == "vi":
        reason = _hotel_features(product, reason)
    if price_asked(state):
        reason = f"{reason}, {_price_text(state, product)}"
    return message(state, "explore_card_line", link=product_link(product), reason=reason)


def _relinked(text: str, products: dict[str, dict]) -> str:
    """LLM đôi khi chép tên một thẻ với id của thẻ khác (LLM thật 2026-10-10: tên khách sạn, id Hồ Hoàn Kiếm). Chữ link
    trùng đúng tên một thẻ thì id theo tên đó, để câu không dẫn sai thẻ và thẻ thật không bị coi là chưa nhắc."""
    by_name: dict[str, str] = {}
    for product_id, product in products.items():
        by_name.setdefault(fold(product.get("name") or ""), product_id)

    def fix(match: re.Match) -> str:
        product_id = by_name.get(fold(match.group(1)))
        if product_id is None or product_id == match.group(2):
            return match.group(0)
        return f"[{match.group(1)}](product:{product_id})"

    # LLM có lúc viết "(product: <id>)" có dấu cách: không gỡ thì link không nhận ra và thẻ bị coi là chưa nhắc.
    return PRODUCT_LINK.sub(fix, re.sub(r"\(product:\s+", "(product:", text))


def about(product: dict) -> str:
    """Phần mô tả catalog nói nơi đó là gì: bỏ câu lặp tên và câu chỉ có số liệu, cắt ở ranh giới câu."""
    name = fold(product.get("name") or "")
    sentences = re.split(r"(?<=[.!?])\s+|\n+", product.get("description") or "")
    kept = [text.strip() for text in sentences
            if text.strip() and fold(text).rstrip(". ") != name and not _DATA_SENTENCE.match(fold(text))]
    result = ""
    for text in kept:
        if len(result) + len(text) > ABOUT_CHARS:
            break
        result = f"{result} {text}".strip()
    return result or (kept[0][:ABOUT_CHARS] if kept else "")


def _card_input(card: dict) -> dict:
    product = card["product"]
    attributes = product.get("attributes") or {}
    tags = attributes.get("tags")
    item = {"productId": product["productId"], "name": product.get("name"), "taxonomy": product.get("taxonomy"),
            "reasons": card["reasons"], "free_to_visit": rules.free_entry(product), "about": about(product),
            "tags": [tag for tag in tags if isinstance(tag, str)][:6] if isinstance(tags, list) else []}
    # Giờ mở cửa chỉ đưa cho nơi người dùng hỏi tới, để trả lời đúng câu hỏi; nơi khác giờ nằm trên thẻ.
    if rules.ASKED in card["reasons"] and attributes.get("openingHours"):
        item["facts"] = {"openingHours": attributes["openingHours"]}
    return item


def _ensure_cards(state: dict, body: str, cards: list[dict]) -> str:
    """Mỗi thẻ phải có một dòng nhắc nó (thẻ hiện ngay sau dòng đó); LLM bỏ sót thẻ nào thì chèn dòng của code vào đúng
    thứ tự thẻ: trước dòng của thẻ kế tiếp đã được nhắc, không có thì ở cuối."""
    lines = body.rstrip().split("\n")

    def line_of(product_id: str) -> int | None:
        return next((index for index, line in enumerate(lines)
                     if any(match.group(2) == product_id for match in PRODUCT_LINK.finditer(line))), None)

    for position, card in enumerate(cards):
        found = line_of(card["product"]["productId"])
        if found is not None and PRODUCT_LINK.sub("", lines[found]).strip(" .,:;-–") == "":
            # LLM chỉ viết link trơn, không nói gì về nơi đó: thay bằng dòng của code.
            lines[found] = card_line(state, card)
        if found is not None:
            continue
        later = [line_of(other["product"]["productId"]) for other in cards[position + 1:]]
        index = min((item for item in later if item is not None), default=len(lines))
        lines.insert(index, card_line(state, card))
    return "\n".join(lines)


def fallback_body(state: dict, destination: str, cards: list[dict], filtered_by: str | None) -> str:
    lines = [message(state, "explore_intro", destination=destination)]
    if filtered_by == "pool":
        lines.append(message(state, "explore_filtered_pool"))
    lines += [card_line(state, card) for card in cards]
    return "\n".join(lines)


def explore_input(state: dict, destination: str, cards: list[dict], filtered_by: str | None,
                  supported: list[str] | None) -> list:
    language = "Vietnamese" if state.get("language", "vi") == "vi" else "English"
    payload = {"message": state.get("query", ""), **llm_context(state), "destination": destination,
               "filtered_by": filtered_by,
               "price_asked": price_asked(state),
               "asked_only": asked_only(state, cards),
               "cards": [_card_input(card) for card in cards],
               "catalog_destinations": (supported or [])[:CATALOG_HINT],
               "previous_suggestions": state.get("last_suggestions", []),
               "rejected_destinations": state.get("rejected_destinations", []),
               "just_rejected": bool(state.get("explore_pick")) and bool(state.get("rejected_destinations"))}
    return [("system", EXPLORE_PROMPT + f"\nReply in {language}."), ("human", prompt_yaml(payload))]


def _closing(state: dict, destination: str) -> tuple[str | None, dict]:
    """Câu cuối do code thêm: mời lập lịch (lần đầu với điểm đến này, chưa đồng ý) hoặc nhắc tiếp tục lập lịch."""
    if state.get("plan_consent"):
        intent = state.get("intent") or {}
        if any(intent.get(key) is None for key in REQUIRED_FIELDS):
            return message(state, "explore_continue"), {}
        return None, {}
    offered = list(state.get("offered_destinations") or [])
    update = {"pending_offer": {"destination": destination}}
    if destination in offered:
        return None, update
    return message(state, "explore_offer", destination=destination), \
        {**update, "offered_destinations": [*offered, destination]}


def _plan_chip(state: dict, destination: str) -> str | None:
    """Nút đi tiếp: mời lập lịch khi chưa đồng ý; "Tiếp tục lập lịch" khi đang lập lịch mà chuyến còn thiếu thông tin;
    không có khi chuyến đã đủ (bấm vào chỉ lập lại đúng lịch cũ)."""
    if not state.get("plan_consent"):
        return message(state, "chip_plan", destination=destination)
    intent = state.get("intent") or {}
    if any(intent.get(key) is None for key in REQUIRED_FIELDS):
        return message(state, "chip_continue")
    return None


def explored(state: dict, destination: str, cards: list[dict], filtered_by: str | None,
             narration: ExploreNarration | None, supported: list[str] | None, *, search_failed: bool = False) -> dict:
    """Update của `explore`: response `NEEDS_CLARIFICATION` có `searchResults`, nút gợi ý, lời mời lập lịch.

    `search_failed`: mọi lời gọi Search đều lỗi hoặc quá giờ; khi đó nói chưa tải được, không nói "không có chỗ nào".
    """
    products = {card["product"]["productId"]: card["product"] for card in cards}
    hotel_only = bool(cards) and all(card["product"].get("taxonomy") == "hotel" for card in cards)
    if not cards and search_failed:
        body = message(state, "explore_unavailable", destination=destination)
        title = message(state, "explore_title", destination=destination)
    elif not cards:
        body = message(state, "explore_none_pool" if filtered_by == "pool" else "explore_none", destination=destination)
        title = message(state, "explore_hotel_title" if hotel_focus(state) else "explore_title", destination=destination)
    elif narration is not None:
        body = _ensure_cards(state, _fill(state, _unlink_unknown(_relinked(narration.message.strip(), products),
                                                                  products), products), cards)
        title = narration.title or message(state, "explore_title", destination=destination)
    else:
        body = fallback_body(state, destination, cards, filtered_by)
        title = message(state, "explore_hotel_title" if hotel_only else "explore_title", destination=destination)
    closing, offer_update = _closing(state, destination)
    if closing:
        body = f"{body.rstrip()}\n{closing}"
    templates = [message(state, "chip_sights" if hotel_only else "chip_hotels", destination=destination),
                 message(state, "chip_elsewhere")]
    if asked_only(state, cards):
        # Hỏi về một nơi: nút dẫn tiếp quanh nơi đó và cả điểm đến, không nhảy sang khách sạn.
        templates = [message(state, "chip_near", place=rules.short_name(cards[0]["product"])),
                     message(state, "chip_more_sights", destination=destination)]
    proposed = list(narration.suggestions) if narration else []
    if state.get("plan_consent"):
        # Đã đồng ý: nút đi tiếp phải đúng tên câu dẫn nhắc ("Tiếp tục lập lịch"), không để nút lập lịch của LLM thay.
        proposed = [item for item in proposed if not asks_for_plan(item)]
    suggestions = checked_suggestions(proposed, state.get("last_suggestions", []), templates,
                                      destinations=supported or [destination], plan_chip=_plan_chip(state, destination),
                                      avoid=state.get("rejected_destinations"))
    by_taxonomy: dict[str, list[dict]] = {}
    for card in cards:
        by_taxonomy.setdefault(card["product"]["taxonomy"], []).append(summary(card["product"]))
    response = {"status": "NEEDS_CLARIFICATION", "conversationId": state["conversation_id"],
                "question": titled(title, body), "knownIntent": state["intent"]}
    if by_taxonomy:
        response["searchResults"] = by_taxonomy
    if suggestions:
        response["suggestions"] = suggestions
    return {"response": response, "candidates": products, "sources": {}, "final_answer": response["question"],
            "supported_destinations": supported, "intent": state["intent"], **offer_update,
            "events": [event("explore", "explored", destination=destination, cards=len(cards),
                             narrated=narration is not None, filtered_by=filtered_by)]}


def _recorded(state: dict, destination: str) -> dict:
    """Chưa đồng ý lập lịch mà người dùng hỏi về một nơi: ghi nơi đó làm điểm đến của chuyến (như `extract` vẫn ghi), để
    "ok" sau lời mời lập lịch đúng nơi. Trợ lý tự chọn (`explore_pick`) hoặc đang lập lịch thì giữ nguyên chuyến."""
    intent = state.get("intent") or {}
    if state.get("plan_consent") or state.get("explore_pick") or intent.get("destination") == destination:
        return state
    return {**state, "intent": {**intent, "destination": destination}}


def no_destination(state: dict, supported: list[str] | None) -> dict:
    """Không biết khám phá nơi nào (catalog không tải được, chưa có điểm đến): hỏi điểm đến bằng câu cố định, kèm nút."""
    suggestions = checked_suggestions([], state.get("last_suggestions", []), conversation_templates(state, supported),
                                      destinations=supported or [], avoid=state.get("rejected_destinations"))
    response = {"status": "NEEDS_CLARIFICATION", "conversationId": state["conversation_id"],
                "question": titled(message(state, "title_missing_destination"), message(state, "missing_destination")),
                "knownIntent": state["intent"], "missingFields": ["destination"]}
    if suggestions:
        response["suggestions"] = suggestions
    return {"response": response, "final_answer": response["question"], "supported_destinations": supported,
            "events": [event("explore", "no destination to explore")]}


async def explore(state: dict, *, tools: ToolExecutorPort | None, llm_call, tool_timeout_seconds: float,
                  llm_timeout_seconds: float) -> dict:
    """Cả lượt khám phá. `llm_call(prompt)` trả `ExploreNarration`; lỗi hoặc quá giờ thì câu dẫn do code dựng."""
    supported = state.get("supported_destinations")
    if supported is None and tools is not None and getattr(tools, "supports_catalog", False):
        supported = await tool_planning.catalog_destinations(tools, tool_timeout_seconds)
    destination = destination_for(state, supported)
    if destination is None and state.get("explore_direct") and tools is not None:
        destination = await place_destination(state, supported, tools, tool_timeout_seconds)
    if destination is None and state.get("explore_direct"):
        # Đi thẳng từ `classify` mà không tra được tên nơi: để `extract` đọc câu (tên lạ, nơi ngoài catalog) rồi quay lại.
        return {"decision": "needs_extract", "explore_direct": False, "supported_destinations": supported,
                "events": [event("explore", "destination not found, extracting")]}
    if destination is None or tools is None:
        return no_destination(state, supported)
    state = _recorded(state, destination)
    results = await search(state, destination, tools, tool_timeout_seconds)
    search_failed = bool(results) and all("error" in result for result in results)
    cards, filtered_by = pick(state, destination, results)
    narration = None
    if cards:
        try:
            narration = ExploreNarration.model_validate(await asyncio.wait_for(
                llm_call(explore_input(state, destination, cards, filtered_by, supported)), llm_timeout_seconds))
        except Exception:
            narration = None
    return explored(state, destination, cards, filtered_by, narration, supported, search_failed=search_failed)
