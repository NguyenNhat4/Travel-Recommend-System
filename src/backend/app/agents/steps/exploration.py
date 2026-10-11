"""Lượt khám phá trước khi lập lịch và nút gợi ý (FR-AGT-06, chốt 2026-10-10).

Người dùng hỏi "Hà Nội có gì?", "khách sạn nào có hồ bơi?" khi chưa đồng ý lập lịch: trợ lý trả lời bằng thẻ sản phẩm
thật thay vì hỏi số ngày hay hiện form. Việc chia như mọi node khác: code tìm (Search), chọn thẻ và lý do
(`domain/itinerary/exploration.py`), điền mọi con số; LLM chỉ viết câu dẫn và đề xuất nút. LLM lỗi thì câu dẫn do
code dựng từ lý do, lượt vẫn trả lời được.
"""
from __future__ import annotations

import asyncio
import re
import unicodedata

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
#: "phố cổ" không kèm thành phố: catalog có hai nơi gọi như vậy, phải hỏi lại (chat thử 10/10).
#: Hỏi lại khi tên nơi khớp nhiều thành phố: tối đa chừng này lựa chọn (mỗi lựa chọn một nút).
MAX_PLACE_CHOICES = 3
#: "gần <nơi>" trong câu gốc (giữ dấu, để câu tìm khách sạn đúng nghĩa): "gần phố cổ không?" → "phố cổ".
_NEAR_PHRASE = re.compile(r"\bgần\s+(.{2,40}?)(?=\s+(?:không|ko|hông|nhé|nha|vậy|ạ|ha)\b|[?.!,]|$)", re.IGNORECASE)
#: Câu trả lời ngắn nêu điểm đến cho câu hỏi còn dở ("hà nội cha ơi", "Phố cổ Hà Nội").
MAX_ANSWER_WORDS = 6
#: Hỏi quanh một nơi ("gần Văn Miếu có gì?"): khác với hỏi về chính nơi đó.
_AROUND = re.compile(r"\b(?:gan|quanh|canh|xung quanh|lan can|near|around)\b")
_PLACEHOLDER = re.compile(r"\[\[(price|rating|reviews):([^\]\s]{1,200})\]\]")
MAX_SUGGESTION_CHARS = 60
MAX_SUGGESTIONS = 3
#: Số điểm đến của catalog đưa cho LLM để gợi ý nút (nhiều sản phẩm nhất trước).
CATALOG_HINT = 12
NAMED_CALL_ID = "explore-named"
NEAR_CALL_ID = "explore-near"
#: Khách sạn "gần <nơi>": trong bán kính này (đường chim bay) quanh nơi đó; kịch bản cảnh 5 dùng 1 km quanh phố cổ.
NEAR_HOTEL_KM = 1.5
PLACE_CALL_ID = "explore-place"
#: Mô tả catalog đưa cho LLM, đủ để kể nơi đó có gì hay trong 2–3 câu (chat thử 10/10: 360 ký tự cho câu quá cụt).
ABOUT_CHARS = 700
#: Số tiện ích, nhãn đưa cho LLM mỗi thẻ.
HIGHLIGHTS = 8
#: Cụm khen dễ bị lặp ở mọi dòng ("nhiều người ghé", "được khen nhiều"): mỗi câu trả lời giữ lần đầu, bỏ các lần sau
#: (so trên chuỗi đã `fold`, kèm dấu nối đứng trước).
_PRAISE = re.compile(r"(?:\s*[,;–-]\s*|\s+)(?:va |lai |cung )?(?:duoc (?:du khach |nhieu nguoi )?khen nhieu|"
                     r"(?:cung )?(?:duoc )?nhieu nguoi ghe(?: nhat(?: o day)?)?|ngay gan do|gia mem)")
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
    """Điểm đến cần khám phá, bỏ qua nơi người dùng đã chê: nơi câu này nhắc tới (tên thành phố, hoặc thành phố LLM hiểu
    từ câu, `explore_city`), nơi trợ lý tự chọn (bậc 2 của "không
    biết", hoặc vừa bị chê) theo thứ tự nhiều sản phẩm nhất, rồi điểm đến của chuyến."""
    rejected = {fold(name) for name in state.get("rejected_destinations") or []}
    allowed = [name for name in supported or [] if fold(name) not in rejected]
    named = _named_destination(state.get("query", ""), allowed)
    if named:
        return named
    # Thành phố LLM hiểu từ câu (kể cả "ở đó", "chỗ đó", hay thành phố của nơi được hỏi: "chợ bến thành mở tới mấy giờ"
    # giữa cuộc chat về Hà Nội), chỉ dùng khi đúng là điểm đến của catalog.
    understood = _named_destination(state.get("explore_city") or "", allowed)
    if understood:
        return understood
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
    """Câu hỏi riêng về chỗ ở ("khách sạn nào…", "ở đâu", "có hồ bơi không"), hoặc LLM hiểu là chỉ hỏi chỗ ở qua ngữ
    cảnh ("khách sạn" trả lời câu hỏi loại vé, "rẻ nhất là chỗ nào" ngay sau danh sách khách sạn)."""
    focus = state.get("explore_focus")
    if focus == "sights":
        return False
    query = fold(state.get("query", ""))
    return focus == "hotels" or bool(_HOTEL_FOCUS.search(query) or _POOL.search(query))


def _without_cities(text: str, names: list[str]) -> str:
    """Bỏ tên thành phố của catalog (kể cả cách gọi khác) khỏi tên một nơi, cho lượt tìm trên cả catalog: không lọc thành
    phố thì Search hiểu "Hồ Chí Minh" trong "Lăng Chủ tịch Hồ Chí Minh" là điểm đến TP. Hồ Chí Minh và trả toàn kết quả ở
    đó (đo 2026-10-11). Lượt tìm đã lọc thành phố thì giữ nguyên tên: bỏ đi lại làm Search trả 0 kết quả ("khách sạn
    được đánh giá tốt gần Phố cổ" ở Hội An: 0; "… gần Phố cổ Hội An": 20)."""
    words = text.split()
    folded = [fold(word) for word in words]
    keys = set()
    for name in [*names, *DESTINATION_ALIASES, *DESTINATION_ALIASES.values()]:
        key = fold(name).split()
        keys.add(tuple(key))
        if len(key) > 1 and key[0] in ("tp", "thanh"):
            keys.add(tuple(key[2:] if key[:2] == ["thanh", "pho"] else key[1:]))
    keep = [True] * len(words)
    index = 0
    while index < len(words):
        length = next((len(key) for key in sorted(keys, key=len, reverse=True)
                       if key and tuple(folded[index:index + len(key)]) == key), 0)
        for offset in range(length):
            keep[index + offset] = False
        index += length or 1
    stripped = " ".join(word for word, kept in zip(words, keep) if kept).strip(" -–,")
    return stripped or text


def place_query(state: dict, names: list[str] | None = None) -> str:
    """Câu tìm nơi người dùng hỏi: tên nơi LLM đọc ra từ câu (đã đưa về tên thường dùng: "lăng bác" → "Lăng Chủ tịch Hồ Chí
    Minh"); LLM không đọc ra nơi nào thì dùng nguyên câu. Không tìm bằng nguyên câu khi đã có tên nơi: Search hiểu "ko" là
    phủ định và trả 0 kết quả cho "văn miếu tối mở ko b" (chat thử M03). `names`: tìm trên cả catalog, bỏ tên các thành
    phố này khỏi tên nơi (`_without_cities`)."""
    place = state.get("explore_place")
    if not place:
        return state.get("query", "")
    return _without_cities(place, names) if names else place


def _place_candidates(state: dict, products: list[dict], exclude: list[str]) -> tuple[dict | None, list[dict]]:
    """(sản phẩm là nơi người dùng hỏi, các nơi cùng tên ở những thành phố khác nhau). Nơi đó: tên nằm trọn trong câu
    hoặc trong tên LLM đọc ra; không có thì nơi có tên gần nhất với tên LLM đọc ra. Các nơi gần nhất ở nhiều thành phố
    ("phố cổ": Khu Phố Cổ Hà Nội, Phố cổ Hội An) thì không chọn, trả các nơi đó để hỏi lại."""
    place = state.get("explore_place") or ""
    named = rules.named_in(products, f"{state.get('query', '')} {place}", exclude=exclude)
    if named or not place:
        return named, []
    by_city: dict[str, dict] = {}
    for product in rules.closest_matches(products, place, exclude=exclude):
        by_city.setdefault(fold(product.get("destination")), product)
    choices = list(by_city.values())
    return (choices[0], []) if len(choices) == 1 else (None, choices)


def _named_place(state: dict, products: list[dict], exclude: list[str]) -> dict | None:
    return _place_candidates(state, products, exclude)[0]


def _asked(state: dict, destination: str, results: list[dict]) -> dict | None:
    """Nơi người dùng hỏi tới ("Văn Miếu buổi tối có mở không?", "lăng bác mấy giờ mở cửa"), trong lượt Search tìm chính
    nơi đó (`place_query`)."""
    named = [result for result in results if result.get("tool_call_id") == NAMED_CALL_ID]
    products = [product for taxonomy in ("attraction", "hotel") for product in _products(named, destination, taxonomy)]
    return _named_place(state, products, [destination])


def near_place_name(state: dict) -> str | None:
    """Nơi người dùng muốn ở gần khi hỏi chỗ ở: nơi LLM đọc ra từ câu (`explore_place`: "khách sạn gần hồ gươm" → "Hồ
    Hoàn Kiếm"); LLM không đọc ra thì cụm "gần <nơi>" của câu."""
    if not hotel_focus(state):
        return None
    return state.get("explore_place") or near_phrase(state.get("query", ""))


def _landmark(state: dict, destination: str, results: list[dict]) -> dict | None:
    """Nơi người dùng muốn ở gần ("phố cổ" → "Khu Phố Cổ Hà Nội"): trong lượt tìm mốc, sản phẩm có tên chứa cụm đó (nhiều
    lượt đánh giá nhất), không có thì sản phẩm có tên gần nhất."""
    near = near_place_name(state)
    if not near:
        return None
    found = _products([result for result in results if result.get("tool_call_id") == NEAR_CALL_ID], destination,
                      "attraction")
    key = f" {fold(near)} "
    matches = [product for product in found if key in f" {fold(product.get('name'))} "]
    if matches:
        return max(matches, key=lambda product: product.get("reviewCount") or 0)
    return rules.named_in(found, f"{state.get('query', '')} {near}") or rules.closest_named(found, near)


def asked_only(state: dict, cards: list[dict]) -> bool:
    """Lượt chỉ trả lời về một nơi người dùng nêu tên ("Văn Miếu buổi tối có mở không?"): một thẻ, lý do `asked`."""
    return len(cards) == 1 and rules.ASKED in cards[0]["reasons"]


def _hotel_cards(state: dict, hotels: list[dict], limit: int) -> list[dict]:
    """Thẻ khách sạn: người dùng muốn chỗ rẻ (`explore_price` = `cheap`, LLM hiểu từ câu: "giá rẻ", "rẻ nhất là chỗ
    nào") thì rẻ nhất trước (chat thử M08 từng có khách sạn 3 triệu/đêm khi hỏi "giá rẻ"); không thì mỗi thẻ một lý do."""
    if state.get("explore_price") == "cheap":
        # Không khách sạn nào có giá thì không nói được nơi nào rẻ: chọn như thường thay vì trả rỗng.
        return rules.cheapest_cards(hotels, limit) or rules.pick_cards(hotels, limit, "hotel")
    return rules.pick_cards(hotels, limit, "hotel")


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
        # Hỏi chỗ ở: chỉ thẻ khách sạn; nơi được nêu tên ("gần phố cổ", "gần Văn Miếu") là mốc đo khoảng cách, không thành
        # thẻ riêng.
        landmark = _landmark(state, destination, results) or asked
        if landmark is not None:
            close = rules.within_km(hotels, landmark, NEAR_HOTEL_KM)
            if close:
                # "Gần phố cổ": chỉ tính khách sạn trong bán kính quanh mốc; lý do rẻ nhất, điểm cao nhất tính trên nhóm này.
                cards = _hotel_cards(state, close, MAX_CARDS)
                for card in cards:
                    card["reasons"].append(rules.NEAR)
                return cards, filtered_by
        return _hotel_cards(state, hotels, MAX_CARDS), filtered_by
    attractions = [item for item in _products(general, destination, "attraction") if item["productId"] not in skip]
    hotels = [item for item in hotels if item["productId"] not in skip]
    hotel_cards = _hotel_cards(state, hotels, MAX_CARDS // 2)
    attraction_cards = rules.pick_cards(attractions, MAX_CARDS - len(hotel_cards) - len(first), "attraction")
    return first + attraction_cards + hotel_cards, filtered_by


async def place_destination(state: dict, supported: list[str] | None, tools: ToolExecutorPort,
                            timeout_seconds: float) -> tuple[str | None, list[dict]]:
    """(điểm đến, các nơi cùng tên ở nhiều thành phố) của nơi câu hỏi nêu tên: tìm nơi đó trên cả catalog (`place_query`),
    nơi khớp tên thì điểm đến là điểm đến của chính sản phẩm đó. Điểm đến đến từ catalog: LLM thật đoán thành phố lúc có
    lúc không ("Văn Miếu" 2026-10-10; "văn miếu vé vào cửa nhiu" thành Đà Nẵng 2026-10-11). Tên khớp nơi ở nhiều thành
    phố thì không có điểm đến, trả các nơi đó để hỏi lại."""
    rejected = {fold(name) for name in state.get("rejected_destinations") or []}
    allowed = [name for name in supported or [] if fold(name) not in rejected]
    if not allowed:
        return None, []
    unscoped = {**state, "intent": {**(state.get("intent") or {}), "destination": None}, "tool_results": []}
    try:
        args = tool_planning._validated_args(unscoped, {"name": "search_products",
                                                        "args": {"query": place_query(state, allowed),
                                                                 "taxonomy": "attraction"}})
    except ToolError:
        return None, []
    results = await tool_planning.run_calls(unscoped, [{"id": PLACE_CALL_ID, "name": "search_products", "args": args}],
                                            tools, timeout_seconds)
    products = [product for result in results for product in (result.get("data") or {}).get("results", [])
                if product.get("productId") and product.get("available") is not False]
    in_catalog = {fold(name): name for name in allowed}
    named, choices = _place_candidates(state, products, allowed)
    choices = [product for product in choices if fold(product.get("destination")) in in_catalog]
    destination = in_catalog.get(fold((named or {}).get("destination")))
    return destination, ([] if destination else choices)


def near_phrase(text: str) -> str | None:
    """Nơi người dùng muốn ở gần ("có khách sạn nào gần phố cổ không?" → "phố cổ")."""
    match = _NEAR_PHRASE.search(text or "")
    return " ".join(match.group(1).split()) if match else None


def _in_city(name: str, destination: str) -> str:
    """Tên nơi kèm tên điểm đến khi tên chưa có ("Phố cổ" ở Hội An → "Phố cổ Hội An"): lượt tìm đã lọc Hội An vẫn trả 0
    kết quả cho "khách sạn được đánh giá tốt gần Phố cổ", ra 20 khi có tên thành phố (đo 2026-10-11)."""
    return name if fold(destination) in fold(name) else f"{name} {destination}"


async def search(state: dict, destination: str, tools: ToolExecutorPort, timeout_seconds: float) -> list[dict]:
    """Search điểm tham quan và khách sạn của điểm đến song song; hỏi riêng chỗ ở thì chỉ khách sạn.

    Hỏi chỗ ở gần một nơi mà câu tìm có "gần <nơi>" không ra khách sạn nào ở điểm đến: tìm lại bằng câu chung, rồi
    `pick` vẫn lọc theo khoảng cách tới nơi đó.
    """
    query = fold(state.get("query", ""))
    base_hotel_query = "khách sạn có hồ bơi" if _POOL.search(query) else "khách sạn được đánh giá tốt"
    near = near_place_name(state)
    near = _in_city(near, destination) if near else None
    hotel_query = f"{base_hotel_query} gần {near}" if near else base_hotel_query
    calls = [_search_call(state, destination, "hotel", hotel_query, 0)]
    if near:
        # Tìm chính nơi đó để làm mốc đo khoảng cách ("Khu Phố Cổ Hà Nội").
        landmark = _search_call(state, destination, "attraction", near, 3)
        if landmark is not None:
            calls.append({**landmark, "id": NEAR_CALL_ID})
    if not hotel_focus(state):
        calls.append(_search_call(state, destination, "attraction", "điểm tham quan nổi tiếng", 1))
    # Thêm một lượt tìm chính nơi câu hỏi nêu tên ("Văn Miếu buổi tối có mở không?", "lăng bác mấy giờ mở cửa").
    named_query = _in_city(state["explore_place"], destination) if state.get("explore_place") else place_query(state)
    named = _search_call(state, destination, "attraction", named_query, 2)
    if named is not None:
        calls.append({**named, "id": NAMED_CALL_ID})
    plan = [call for call in calls if call is not None]
    results = await tool_planning.run_calls({**state, "tool_results": []}, plan, tools, timeout_seconds)
    if near and not _products(results, destination, "hotel"):
        broad = _search_call(state, destination, "hotel", base_hotel_query, 4)
        if broad is not None:
            results += await tool_planning.run_calls({**state, "tool_results": []}, [broad], tools, timeout_seconds)
    return results


def _price_text(state: dict, product: dict) -> str:
    value = rules.price(product)
    if rules.free_entry(product) or (value is None and product.get("taxonomy") == "attraction"):
        # Điểm tham quan không có giá là nơi đến chơi, như câu dẫn lịch (`narration._price`, người dùng chốt 01/10).
        return message(state, "explore_price_free")
    if value is None:
        return message(state, "explore_price_unknown")
    return message(state, "explore_price_from", money=money(value, state.get("language", "vi")))


def price_asked(state: dict) -> bool:
    """Người dùng hỏi giá hoặc muốn chỗ rẻ: LLM hiểu từ câu (`explore_price`: "có mất vé ko", "vào cửa bao nhiu"), hoặc
    câu có từ hỏi giá."""
    return bool(state.get("explore_price")) or bool(_PRICE_ASKED.search(fold(state.get("query", ""))))


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
    # LLM có lúc đặt placeholder giá sau dấu chấm ("… bằng xe. [[price:id]]"): nối giá vào câu trước.
    filled = re.sub(r"(?<=\w)[.!?][ \t]+((?:từ|from) [\d.,]+ ₫)[ \t]*\.?[ \t]*(?=\n|$)", r", \1.", filled)
    # Chỗ placeholder bị bỏ để lại ngoặc rỗng hoặc dấu cách đôi.
    filled = re.sub(r"\(\s*[,;]?\s*\)", "", filled)
    filled = re.sub(r"[ \t]+([.,;:!?])", r"\1", filled)
    return "\n".join(" ".join(line.split()) for line in filled.split("\n"))


def _unlink_unknown(text: str, products: dict[str, dict]) -> str:
    """Link tới sản phẩm không có trong thẻ thì chỉ giữ chữ: lời dẫn không được nhắc sản phẩm ngoài kết quả."""
    return PRODUCT_LINK.sub(lambda match: match.group(0) if match.group(2) in products else match.group(1), text)


#: Câu mô tả trong dòng dự phòng: một câu, cắt ở dấu phẩy nếu dài.
SHORT_ABOUT_CHARS = 160
#: Câu mô tả bắt đầu bằng tên mà phần còn lại ngắn hơn chừng này ký tự thì không dùng làm dòng dẫn.
MIN_ABOUT_EXTRA = 30


def _short_about(product: dict) -> str:
    """Câu đầu mô tả của một điểm tham quan. Khách sạn không dùng: mô tả của chúng là văn quảng cáo ("Chỗ Nghỉ Thanh
    Lịch: …"), cắt ra thành câu cụt."""
    if product.get("taxonomy") == "hotel":
        return ""
    first = re.split(r"(?<=[.!?])\s+", about(product), maxsplit=1)[0].rstrip(".!? ")
    name = fold(product.get("name") or "")
    if name and fold(first).startswith(name) and len(fold(first)) - len(name) < MIN_ABOUT_EXTRA:
        # "Bảo tàng Gấu Teddy tại An Giang": chỉ nhắc lại tên và nơi, không nói được nơi đó có gì (chat thử 10/10).
        return ""
    if len(first) > SHORT_ABOUT_CHARS:
        cut = first[:SHORT_ABOUT_CHARS]
        first = cut.rsplit(",", 1)[0] if "," in cut else cut.rsplit(" ", 1)[0]
    return first


#: Cụm tiện ích trong dòng dự phòng của khách sạn ("khách sạn có hồ bơi, spa"); trẻ nhỏ nói riêng ("hợp gia đình có trẻ
#: nhỏ") vì không đọc được sau chữ "có".
_FEATURE_WORDS = {"pool": "hồ bơi", "seaView": "view biển", "breakfast": "bữa sáng", "spa": "spa"}


#: Số nhãn/tiện ích của catalog kể trong dòng dự phòng khi không có câu mô tả; số phần đầu của địa chỉ khi không có cả nhãn.
FALLBACK_DETAILS = 3
ADDRESS_PARTS = 2


def _catalog_details(product: dict) -> list[str]:
    """Nhãn (điểm tham quan) hoặc tiện ích (khách sạn) của catalog, viết thường, để dòng dự phòng nói được nơi đó là gì
    thay vì chỉ "cũng được nhiều người ghé" (chat thử M02)."""
    attributes = product.get("attributes") or {}
    values = attributes.get("amenities") if product.get("taxonomy") == "hotel" else attributes.get("tags")
    details = [value.strip() for value in values if isinstance(value, str) and value.strip()] \
        if isinstance(values, list) else []
    details = [value[:1].lower() + value[1:] for value in details[:FALLBACK_DETAILS]]
    address = attributes.get("address")
    if not details and product.get("taxonomy") != "hotel" and isinstance(address, str) and address.strip():
        # Không nhãn, không mô tả (Bảo tàng Gấu Teddy): ít ra nói nơi đó nằm ở đâu, lấy từ địa chỉ catalog.
        details = ["ở " + ", ".join(part.strip() for part in address.split(",")[:ADDRESS_PARTS] if part.strip())]
    return details


def _hotel_features(product: dict, reason: str) -> str:
    found = {item.key for item in preferences.PREFERENCES if preferences.satisfies(product, item)}
    parts = []
    words = [word for key, word in _FEATURE_WORDS.items() if key in found] or _catalog_details(product)
    if words:
        parts.append("khách sạn có " + ", ".join(words))
    if "familyFriendly" in found:
        parts.append("hợp gia đình có trẻ nhỏ")
    return ", ".join([*parts, reason])


def card_line(state: dict, card: dict) -> str:
    """Dòng dẫn do code dựng cho một thẻ: câu mô tả của catalog (nơi đó là gì); không có thì nhãn/tiện ích của catalog
    kèm lý do đầu tiên; giá chỉ khi người dùng hỏi giá. Điểm, lượt đánh giá, giờ mở cửa nằm trên thẻ."""
    product = card["product"]
    reason = message(state, f"reason_{card['reasons'][0]}")
    if state.get("language", "vi") == "vi" and product.get("taxonomy") != "hotel":
        details = _catalog_details(product)
        reason = _short_about(product) or (", ".join([*details, reason]) if details else reason)
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
    # Tên trong link có lúc bị in đậm ("[**Tên**](product:…)"): bỏ dấu in đậm để chữ link đúng tên thẻ.
    text = re.sub(r"\[(?:\*\*)?\s*([^\]]+?)\s*(?:\*\*)?\]\(product:", r"[\1](product:", text)
    # LLM có lúc bỏ dấu "[" mở link ("Lăng Chủ tịch Hồ Chí Minh](product:…)", trace 2026-10-11): tên thẻ đứng ngay trước
    # "](product:" mà không có "[" thì chèn lại. Chạy sau bước gỡ in đậm, để không chèn thừa vào "[**Tên**](…)".
    for product in products.values():
        name = (product.get("name") or "").strip()
        if name:
            text = re.sub(rf"(?<!\[){re.escape(name)}\]\(product:", f"[{name}](product:", text)
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


def _card_input(card: dict, language: str = "vi") -> dict:
    product = card["product"]
    attributes = product.get("attributes") or {}
    tags = attributes.get("tags")
    amenities = attributes.get("amenities")
    item = {"productId": product["productId"], "name": (product.get("name") or "").strip(),
            "taxonomy": product.get("taxonomy"),
            "reasons": card["reasons"], "free_to_visit": rules.free_entry(product), "about": about(product),
            "tags": [tag for tag in tags if isinstance(tag, str)][:HIGHLIGHTS] if isinstance(tags, list) else []}
    if isinstance(amenities, list):
        # Khách sạn: tiện ích có thật để kể về kỳ nghỉ (hồ bơi, spa, bữa sáng), không chỉ "giá mềm".
        item["highlights"] = [text for text in amenities if isinstance(text, str)][:HIGHLIGHTS]
    # Giờ mở cửa, vé vào chỉ đưa cho nơi người dùng hỏi tới, để trả lời đúng câu hỏi; nơi khác nằm trên thẻ.
    if rules.ASKED in card["reasons"]:
        facts = {"openingHours": attributes["openingHours"]} if attributes.get("openingHours") else {}
        if product.get("taxonomy") == "attraction" and (rules.free_entry(product) or product.get("unitPrice") is None):
            # Nơi công cộng không bán vé (Hồ Hoàn Kiếm): lịch cũng coi là tham quan tự do (`FREE_ENTRY_ASSUMED`).
            facts["entry"] = "free_no_ticket_sold"
        elif rules.price(product) is not None:
            # Giá vé do code dựng từ catalog, LLM chép nguyên văn: đưa placeholder thì LLM thật có lúc nói "chưa kiểm tra
            # được giá vé" dù có giá (2026-10-11).
            facts["ticketPrice"] = message({"language": language}, "explore_price_from",
                                           money=money(rules.price(product), language))
        item["facts"] = facts
    return item


def _plain(text: str) -> str:
    """Chữ thường, bỏ dấu từng ký tự, đ → d; giữ nguyên độ dài (khác `fold`, vốn gộp dấu cách và ký hiệu)."""
    return "".join((unicodedata.normalize("NFD", char)[0] if char not in "đĐ" else "d").lower() for char in text)


def once_praise(text: str) -> str:
    """Mỗi cụm khen chung chỉ giữ lần xuất hiện đầu tiên trong câu trả lời (chat thử 10/10: "nhiều người ghé" ở mọi
    dòng). So trên chuỗi bỏ dấu từng ký tự (giữ độ dài, nên vị trí khớp chuỗi gốc)."""
    folded = _plain(text)
    seen: set[str] = set()
    cuts = []
    for match in _PRAISE.finditer(folded):
        phrase = match.group(0)
        key = "khen" if "khen" in phrase else "ghe" if "ghe" in phrase else "gan" if "gan do" in phrase else "gia"
        if key in seen:
            cuts.append(match.span())
        seen.add(key)
    for start, end in reversed(cuts):
        text = text[:start] + text[end:]
    # Bỏ cụm ở cuối câu có thể để lại "…:." hoặc ", ."
    text = re.sub(r"\s*[,;:–-]\s*([.!?])", r"\1", text)
    return "\n".join(line.rstrip() for line in text.split("\n"))


def _link_plain_name(lines: list[str], product: dict) -> int | None:
    """LLM nêu tên thẻ mà không gắn link ("Có, Văn Miếu – Quốc Tử Giám mở buổi tối…"): gắn link vào lần nêu đầu tiên và
    trả số dòng, thay vì chèn thêm một dòng nhắc lại nơi đó (chat thử M03 từng ra hai dòng Văn Miếu)."""
    product_id = product["productId"]
    for name in dict.fromkeys(((product.get("name") or "").strip(), rules.short_name(product))):
        if len(name.split()) < 2:
            continue
        pattern = re.compile(rf"(?<!\[){re.escape(name)}(?!\]\(product:)")
        for index, line in enumerate(lines):
            masked = PRODUCT_LINK.sub(lambda match: " " * len(match.group(0)), line)
            match = pattern.search(masked)
            if match:
                lines[index] = f"{line[:match.start()]}[{name}](product:{product_id}){line[match.end():]}"
                return index
    return None


def _with_asked_price(state: dict, text: str, cards: list[dict]) -> str:
    """Hỏi giá vé một nơi có giá ("văn miếu vé vào cửa bao nhiêu") mà câu LLM không nêu giá (LLM thật 2026-10-11): thêm
    câu giá vào cuối đoạn của nơi đó, số do `_fill` điền."""
    asked = next((card["product"] for card in cards if rules.ASKED in card["reasons"]), None)
    if asked is None or not price_asked(state) or rules.price(asked) is None:
        return text
    product_id = asked["productId"]
    if f"[[price:{product_id}]]" in text or money(rules.price(asked), state.get("language", "vi")) in text:
        return text
    lines = text.split("\n")
    index = next((number for number, line in enumerate(lines)
                  if any(match.group(2) == product_id for match in PRODUCT_LINK.finditer(line))), None)
    if index is None:
        return text
    lines[index] = f"{lines[index].rstrip().rstrip('.')}. {message(state, 'explore_asked_price', price=f'[[price:{product_id}]]')}"
    return "\n".join(lines)


def _ensure_cards(state: dict, body: str, cards: list[dict]) -> str:
    """Mỗi thẻ phải có một dòng nhắc nó (thẻ hiện ngay sau dòng đó); LLM bỏ sót thẻ nào thì chèn dòng của code vào đúng
    thứ tự thẻ: trước dòng của thẻ kế tiếp đã được nhắc, không có thì ở cuối."""
    lines = body.rstrip().split("\n")

    def line_of(product_id: str) -> int | None:
        return next((index for index, line in enumerate(lines)
                     if any(match.group(2) == product_id for match in PRODUCT_LINK.finditer(line))), None)

    for position, card in enumerate(cards):
        found = line_of(card["product"]["productId"])
        if found is None:
            found = _link_plain_name(lines, card["product"])
        if found is not None and PRODUCT_LINK.sub("", lines[found]).strip(" .,:;-–") == "":
            # LLM chỉ viết link trơn, không nói gì về nơi đó: thay bằng dòng của code.
            lines[found] = card_line(state, card)
        if found is not None:
            continue
        later = [line_of(other["product"]["productId"]) for other in cards[position + 1:]]
        index = min((item for item in later if item is not None), default=len(lines))
        lines.insert(index, card_line(state, card))
    return "\n".join(lines)


def _near_place(state: dict, cards: list[dict]) -> str | None:
    """Cụm "gần <nơi>" của câu hỏi khi thẻ đã được lọc theo khoảng cách tới nơi đó (lý do `near`)."""
    if cards and all(rules.NEAR in card["reasons"] for card in cards):
        return near_place_name(state)
    return None


def fallback_body(state: dict, destination: str, cards: list[dict], filtered_by: str | None) -> str:
    lines = [message(state, "explore_intro", destination=destination)]
    if filtered_by == "pool":
        lines.append(message(state, "explore_filtered_pool"))
    if (place := _near_place(state, cards)):
        lines.append(message(state, "explore_filtered_near", place=place))
    lines += [card_line(state, card) for card in cards]
    return "\n".join(lines)


def explore_input(state: dict, destination: str, cards: list[dict], filtered_by: str | None,
                  supported: list[str] | None) -> list:
    language = "Vietnamese" if state.get("language", "vi") == "vi" else "English"
    payload = {"message": state.get("query", ""), **llm_context(state), "destination": destination,
               "filtered_by": filtered_by,
               "price_asked": price_asked(state),
               "asked_only": asked_only(state, cards),
               "near_place": _near_place(state, cards),
               "cards": [_card_input(card, state.get("language", "vi")) for card in cards],
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
        # Dòng trống giữa các đoạn (LLM thật 10/10) làm thẻ tách khỏi câu dẫn: gộp về một dòng mỗi đoạn.
        narration = narration.model_copy(update={"message": re.sub(r"\n\s*\n+", "\n", narration.message)})
        linked = _unlink_unknown(_relinked(narration.message.strip(), products), products)
        body = once_praise(_ensure_cards(state, _fill(state, _with_asked_price(state, linked, cards), products), cards))
        title = narration.title or message(state, "explore_title", destination=destination)
    else:
        body = once_praise(fallback_body(state, destination, cards, filtered_by))
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
            "supported_destinations": supported, "intent": state["intent"], **offer_update, "open_question": None,
            "open_understood": None,
            "events": [event("explore", "explored", destination=destination, cards=len(cards),
                             narrated=narration is not None, filtered_by=filtered_by)]}


def _recorded(state: dict, destination: str) -> dict:
    """Chưa đồng ý lập lịch mà người dùng hỏi về một nơi: ghi nơi đó làm điểm đến của chuyến (như `extract` vẫn ghi), để
    "ok" sau lời mời lập lịch đúng nơi. Trợ lý tự chọn (`explore_pick`) hoặc đang lập lịch thì giữ nguyên chuyến."""
    intent = state.get("intent") or {}
    if state.get("plan_consent") or state.get("explore_pick") or intent.get("destination") == destination:
        return state
    return {**state, "intent": {**intent, "destination": destination}}


def resumed(state: dict, supported: list[str] | None) -> tuple[dict, str | None]:
    """Lượt trả lời điểm đến cho câu hỏi còn dở: (state với câu hỏi gốc làm `query`, điểm đến) hoặc (state, None).

    "có khách sạn nào có hồ bơi gần phố cổ không?" → trợ lý hỏi lại nơi → "hà nội cha ơi": khám phá khách sạn có hồ bơi
    gần phố cổ ở Hà Nội, không phải "Hà Nội có gì" chung chung (chat thử 10/10).
    """
    pending = state.get("open_question")
    reply = state.get("query", "")
    if not pending or not 0 < len(reply.split()) <= MAX_ANSWER_WORDS:
        return state, None
    rejected = {fold(name) for name in state.get("rejected_destinations") or []}
    named = _named_destination(reply, [name for name in supported or [] if fold(name) not in rejected])
    if named is None:
        return state, None
    intent = state.get("intent") or {}
    # Những gì LLM đã hiểu ở câu hỏi gốc (chỗ ở, giá rẻ, nơi muốn ở gần) đi theo câu hỏi; lượt này đọc ra gì thì thắng.
    kept = {key: value for key, value in (state.get("open_understood") or {}).items() if not state.get(key)}
    return {**state, **kept, "query": pending, "intent": {**intent, "destination": named}}, named


def _open(state: dict) -> dict:
    """Câu hỏi còn dở khi trợ lý phải hỏi lại nơi: câu gốc và những gì LLM đã hiểu ở câu đó, để lượt trả lời dùng lại."""
    return {"open_question": state.get("query"),
            "open_understood": {key: state.get(key) for key in ("explore_place", "explore_focus", "explore_price")
                                if state.get(key)}}


def ask_which_place(state: dict, supported: list[str] | None, choices: list[dict]) -> dict:
    """Tên nơi khớp nơi ở nhiều thành phố ("khách sạn gần phố cổ": Khu Phố Cổ Hà Nội, Phố cổ Hội An): hỏi lại kèm một
    nút cho mỗi nơi (tên catalog), giữ câu hỏi để lượt sau trả lời tiếp."""
    names = [(product.get("name") or "").strip() for product in choices[:MAX_PLACE_CHOICES]]
    response = {"status": "NEEDS_CLARIFICATION", "conversationId": state["conversation_id"],
                "question": message(state, "explore_ask_which_place",
                                    places=message(state, "explore_place_joiner").join(names)),
                "knownIntent": state["intent"], "missingFields": ["destination"], "suggestions": names}
    return {"response": response, "final_answer": response["question"], "supported_destinations": supported,
            **_open(state), "events": [event("explore", "place in several cities, asked which", choices=len(names))]}


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
    state, answered = resumed(state, supported)
    destination = answered
    if destination is None and state.get("explore_place") and tools is not None:
        # Câu nêu tên một nơi: thành phố của nơi đó lấy từ catalog, không theo thành phố LLM đoán (LLM thật gán "văn miếu
        # vé vào cửa nhiu" cho Đà Nẵng vì lượt trước nói về Bà Nà, 2026-10-11).
        destination, choices = await place_destination(state, supported, tools, tool_timeout_seconds)
        said = destination_for(state, supported) if choices else None
        chosen = next((product for product in choices if fold(product.get("destination")) == fold(said)), None)
        if chosen is not None:
            destination = said  # câu đã nêu thành phố ("phố cổ ở Hội An"): không hỏi lại
        elif len(choices) > 1:
            return ask_which_place(state, supported, choices)
    destination = destination or destination_for(state, supported)
    if destination is None and state.get("explore_direct") and tools is not None and not state.get("explore_place"):
        destination, _ = await place_destination(state, supported, tools, tool_timeout_seconds)
    if destination is None and state.get("explore_direct"):
        # Đi thẳng từ `classify` mà không tra được tên nơi: để `extract` đọc câu (tên lạ, nơi ngoài catalog) rồi quay lại.
        # Câu hỏi được giữ (`open_question`): trợ lý hỏi lại nơi thì lượt sau trả lời tiếp câu này.
        return {"decision": "needs_extract", "explore_direct": False, "supported_destinations": supported,
                **_open(state), "events": [event("explore", "destination not found, extracting")]}
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
