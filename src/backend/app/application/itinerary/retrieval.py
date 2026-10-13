"""Hydrate, normalize and filter products returned by itinerary tools."""

from __future__ import annotations

import asyncio
from collections import Counter
from copy import deepcopy
from datetime import date

from src.backend.app.application.ports.itinerary_tools import CatalogPort
from src.backend.app.domain.itinerary.types import (
    Candidates, Constraints, DropSummary, Product, Sources, ToolErrorPayload, ToolResult, TripIntent,
)

from src.backend.app.application.itinerary.tool_contracts import SIMILAR_PRODUCTS

DETAIL_FIELDS = ("description", "attributes", "availableFrom", "availableTo")


def _products(results: list[ToolResult]) -> list[Product]:
    values = []
    for result in results:
        data = result.get("data", {})
        values.extend(data.get("results", []))
        values.extend(data.get("recommendations", []))
    return values


async def hydrate(results: list[ToolResult], tools: CatalogPort, existing_details: dict[str, Product],
                  timeout_seconds: float) -> tuple[dict[str, Product], dict[str, ToolErrorPayload]]:
    details, errors = deepcopy(existing_details), {}
    missing = {p["productId"] for p in _products(results) if p.get("productId") and
               any(field not in p for field in DETAIL_FIELDS)} - details.keys()
    semaphore = asyncio.Semaphore(5)

    async def load(product_id: str) -> None:
        async with semaphore:
            try:
                details[product_id] = await asyncio.wait_for(tools.get_product_detail(product_id), timeout_seconds)
            except Exception as exc:
                errors[product_id] = exc.as_dict() if hasattr(exc, "as_dict") else {
                    "code": "PRODUCT_DETAIL_UNAVAILABLE", "retryable": False, "httpStatus": None}
    await asyncio.gather(*(load(product_id) for product_id in sorted(missing)))
    return details, errors


def _normalized(value: str | None) -> str:
    return " ".join((value or "").casefold().split())


def _off_destination(product: Product, intent: TripIntent) -> bool:
    return _normalized(product.get("destination")) != _normalized(intent.get("destination"))


#: Loại sản phẩm được giữ làm lịch tham khảo khi chỉ vướng ngày (chat thử 10/10): điểm tham quan nổi tiếng vẫn ở đó dù vé
#: chưa mở bán cho ngày đi. Khách sạn, vé máy bay, combo vướng ngày vẫn bị loại.
REFERENCE_TAXONOMIES = {"attraction", "golf"}
#: Cờ trên candidate: giữ làm tham khảo, chưa mở bán cho ngày đi; không tính là mục đặt được.
NOT_ON_SALE = "notOnSaleForDate"
#: Số nơi tối đa (và tối thiểu có lượt đánh giá) của lịch tham khảo.
MAX_REFERENCE_PLACES = 8
MIN_REFERENCE_PLACES = 2


def _drop_reason(product: Product, intent: TripIntent, constraints: Constraints) -> str | None:
    if product.get("productId") in constraints.get("exclude_products", []):
        return "PRODUCT_DROPPED_EXCLUDED"
    if _off_destination(product, intent):
        return "PRODUCT_DROPPED_DESTINATION"
    if not product.get("available"):
        return "PRODUCT_DROPPED_UNAVAILABLE"
    taxonomy = product.get("taxonomy")
    if taxonomy in constraints.get("exclude_taxonomies", []):
        return "PRODUCT_DROPPED_TAXONOMY"
    if intent.get("startDate"):
        visit = date.fromisoformat(intent["startDate"])
        if product.get("availableFrom") and visit < date.fromisoformat(product["availableFrom"]):
            return "PRODUCT_DROPPED_DATE"
        if product.get("availableTo") and visit > date.fromisoformat(product["availableTo"]):
            return "PRODUCT_DROPPED_DATE"
    if taxonomy == "hotel":
        price_max, unit = constraints.get("hotel_price_max"), constraints.get("hotel_price_unit")
        if price_max is not None:
            if product.get("unitPrice") is None or (unit and product.get("priceUnit", "UNKNOWN") != unit):
                return "PRODUCT_DROPPED_PRICE_BASIS"
            if product["unitPrice"] > price_max or (constraints.get("price_strict") and product["unitPrice"] >= price_max):
                return "PRODUCT_DROPPED_PRICE"
        attributes = product.get("attributes", {})
        if constraints.get("star_rating_min") is not None and attributes.get("starRating", -1) < constraints["star_rating_min"]:
            return "PRODUCT_DROPPED_ATTRIBUTES"
        if any(attributes.get(key) is not value for key, value in constraints.get("hotel_attributes", {}).items()):
            return "PRODUCT_DROPPED_ATTRIBUTES"
        if constraints.get("specific_hotel") and _normalized(constraints["specific_hotel"]) not in _normalized(product.get("name")):
            return "PRODUCT_DROPPED_NAMED_REQUIREMENT"
    if constraints.get("specific_activity") and taxonomy in {"attraction", "golf"} and \
            _normalized(constraints["specific_activity"]) not in _normalized(product.get("name")):
        return "PRODUCT_DROPPED_NAMED_REQUIREMENT"
    return None


def collect(tool_results: list[ToolResult], details: dict[str, Product], intent: TripIntent,
            constraints: Constraints, *, counts=None) -> tuple[Candidates, Sources, dict[str, str]]:
    candidates, sources, dropped = {}, {}, {}
    for result in tool_results:
        data = result.get("data", {})
        # Similar tìm cùng taxonomy trên cả catalog, không theo điểm đến: sản phẩm ở nơi khác không phải
        # sản phẩm "bị loại" của chuyến này, nên bỏ qua lặng lẽ thay vì thành cảnh báo. Kết quả nằm ở
        # `results` nên mang nguồn "search" (ItemSource.SEARCH), như Search.
        similar = result.get("name") == SIMILAR_PRODUCTS
        for source, products in (("search", data.get("results", [])),
                                 ("recommendation", data.get("recommendations", []))):
            for projection in products:
                product_id = projection.get("productId")
                if not product_id:
                    continue
                product = {**deepcopy(details.get(product_id, {})), **deepcopy(projection)}
                counter = counts(product.get('taxonomy')) if counts else None
                if counter:
                    counter.source_total = data.get('total')
                if similar and _off_destination(product, intent):
                    if counter:
                        counter.record(product_id, 'PRODUCT_DROPPED_DESTINATION', outside=True)
                    continue
                reason = _drop_reason(product, intent, constraints)
                if (reason == "PRODUCT_DROPPED_DATE" and product.get("taxonomy") in REFERENCE_TAXONOMIES
                        and _drop_reason(product, {**intent, "startDate": None}, constraints) is None):
                    # Điểm tham quan chỉ vướng ngày: giữ tạm, gắn cờ; `reference_only` quyết định có dùng làm lịch tham
                    # khảo hay không (chỉ khi ngày đi không còn điểm tham quan nào mở bán).
                    product[NOT_ON_SALE] = True
                    reason = None
                if counter:
                    counter.record(product_id, reason, outside=reason in NOT_SUPPLY_REASONS)
                if reason:
                    dropped[product_id] = reason
                    candidates.pop(product_id, None)
                    sources.pop(product_id, None)
                else:
                    candidates[product_id], sources[product_id] = product, source
    return candidates, sources, dropped


def reference_only(candidates: Candidates, dropped: dict[str, str]) -> Candidates:
    """Lịch tham khảo khi vé chưa mở bán cho ngày đi (chat thử 10/10: không bao giờ chỉ nói "không có sản phẩm").

    Còn điểm tham quan mở bán cho ngày đi thì bỏ các điểm gắn cờ `NOT_ON_SALE` (trả lại thành loại vì ngày trong
    `dropped`), lịch giữ như cũ. Không còn điểm nào thì giữ chúng: lịch dựng từ các điểm nổi tiếng của nơi đó, điểm có vé
    không tính là đặt được.
    """
    on_sale = any(product.get("taxonomy") in REFERENCE_TAXONOMIES and not product.get(NOT_ON_SALE)
                  for product in candidates.values())
    flagged = [product for product in candidates.values() if product.get(NOT_ON_SALE)]
    if on_sale:
        keep: set[str] = set()
    else:
        # Lịch tham khảo dựng từ những nơi nổi tiếng nhất (nhiều lượt đánh giá: Hồ Hoàn Kiếm, Văn Miếu), không từ vé lẻ
        # không ai đánh giá (vé hạng Vinpalace, chat thử 10/10). Ít nơi có đánh giá quá thì giữ cả.
        reviewed = sorted((product for product in flagged if _reviews(product) > 0), key=_reviews, reverse=True)
        keep = {product["productId"] for product in (reviewed if len(reviewed) >= MIN_REFERENCE_PLACES else flagged)
                [:MAX_REFERENCE_PLACES]}
    for product in flagged:
        if product["productId"] not in keep:
            dropped[product["productId"]] = "PRODUCT_DROPPED_DATE"
            del candidates[product["productId"]]
    return candidates


def _reviews(product: Product) -> int:
    value = product.get("reviewCount")
    if not isinstance(value, int):
        value = (product.get("attributes") or {}).get("reviewCount")
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def nearest_open_date(tool_results: list[ToolResult], details: dict[str, Product], intent: TripIntent,
                      constraints: Constraints, today: date, taxonomy: str | None = None) -> str | None:
    """Ngày khởi hành gần `startDate` nhất mà có sản phẩm bị loại vì `DATE` đang mở bán; None khi không có.

    Chỉ xét sản phẩm mà `_drop_reason` xếp là DATE (đã đúng điểm đến, còn bán, không bị loại loại/giá), nên
    ngày trả về đặt lại chuyến là có sản phẩm thật. Không bao giờ sớm hơn `today` hay muộn hơn `availableTo`.
    `taxonomy` giới hạn ở một loại sản phẩm (ví dụ ngày gần nhất có khách sạn).
    """
    if not intent.get("startDate"):
        return None
    visit = date.fromisoformat(intent["startDate"])
    best: date | None = None
    for result in tool_results:
        data = result.get("data", {})
        for projection in (*data.get("results", []), *data.get("recommendations", [])):
            product_id = projection.get("productId")
            if not product_id:
                continue
            product = {**details.get(product_id, {}), **projection}
            if taxonomy is not None and product.get("taxonomy") != taxonomy:
                continue
            if _drop_reason(product, intent, constraints) != "PRODUCT_DROPPED_DATE":
                continue
            opens = date.fromisoformat(product["availableFrom"]) if product.get("availableFrom") else visit
            closes = date.fromisoformat(product["availableTo"]) if product.get("availableTo") else None
            nearest = max(min(max(visit, opens), closes) if closes else max(visit, opens), today)
            if closes and nearest > closes:
                continue
            if best is None or abs(nearest - visit) < abs(best - visit):
                best = nearest
    return best.isoformat() if best else None


#: Lý do loại không nói gì về nguồn cung ở điểm đến này: sản phẩm nơi khác, hoặc do chính người dùng loại ra.
NOT_SUPPLY_REASONS = {"PRODUCT_DROPPED_DESTINATION", "PRODUCT_DROPPED_EXCLUDED", "PRODUCT_DROPPED_TAXONOMY"}


def drop_summary(tool_results: list[ToolResult], details: dict[str, Product], intent: TripIntent,
                 constraints: Constraints, today: date) -> dict[str, DropSummary]:
    """Vì sao từng taxonomy không còn candidate nào, để câu trả lời nêu được lý do thật thay vì câu chung.

    Một taxonomy có mục khi nó không còn candidate và: hoặc có sản phẩm đúng điểm đến bị loại (lý do phổ biến
    nhất, cửa sổ mở bán, ngày gần nhất), hoặc đã được tìm riêng (`search_products` có `taxonomy`) mà không ra gì
    (`count = 0`). Mọi giá trị lấy từ kết quả tool của lượt này, cùng luật `_drop_reason` với `collect()`.
    """
    kept: set[str] = set()
    dropped: dict[str, dict[str, str]] = {}  # taxonomy → productId → reason (một sản phẩm đếm một lần)
    windows: dict[str, list[tuple[str | None, str | None]]] = {}
    searched: set[str] = set()
    for result in tool_results:
        if result.get("name") == "search_products" and (result.get("arguments") or {}).get("taxonomy"):
            searched.add(result["arguments"]["taxonomy"])
        data = result.get("data", {})
        similar = result.get("name") == SIMILAR_PRODUCTS
        for projection in (*data.get("results", []), *data.get("recommendations", [])):
            product_id = projection.get("productId")
            if not product_id:
                continue
            product = {**details.get(product_id, {}), **projection}
            taxonomy = product.get("taxonomy")
            if not taxonomy or (similar and _off_destination(product, intent)):
                continue
            reason = _drop_reason(product, intent, constraints)
            if reason is None:
                kept.add(taxonomy)
            elif reason not in NOT_SUPPLY_REASONS:
                dropped.setdefault(taxonomy, {})[product_id] = reason
                if reason == "PRODUCT_DROPPED_DATE":
                    windows.setdefault(taxonomy, []).append((product.get("availableFrom"), product.get("availableTo")))
    summary: dict[str, DropSummary] = {}
    for taxonomy in sorted((set(dropped) | searched) - kept):
        reasons = Counter(dropped.get(taxonomy, {}).values())
        opens = [start for start, _ in windows.get(taxonomy, []) if start]
        closes = [end for _, end in windows.get(taxonomy, []) if end]
        summary[taxonomy] = {
            "count": sum(reasons.values()),
            "reason": reasons.most_common(1)[0][0] if reasons else None,
            "openFrom": min(opens) if opens else None,
            "openTo": max(closes) if closes else None,
            "nearestOpenDate": nearest_open_date(tool_results, details, intent, constraints, today, taxonomy=taxonomy),
        }
    return summary
