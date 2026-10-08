"""Use case gợi ý tức thì (`GET /search/suggestions`, FR-SRC-05).

Chỉ đọc `UnitIndex` đã nằm trong bộ nhớ: không gọi embed, kho vector hay database, và không ghi event/search log —
Web gọi theo từng lần gõ. Được dựng lại mỗi lần catalog nạp lại nên bộ đệm ở đây tự hết hạn theo catalog.
"""
from __future__ import annotations

from collections import OrderedDict
from collections.abc import Mapping
from threading import Lock

from src.backend.app.application.catalog.views import destination_list
from src.backend.app.application.ports import UnitIndex
from src.backend.app.domain.search import SUGGEST_GROUPS, SuggestEntry, fold, is_suggestable, suggest

from .use_cases import canonical_query


def _payload(entry: SuggestEntry) -> dict:
    if entry.group == "destination":
        return {"type": "destination", "label": entry.label, "productCount": int(entry.weight)}
    return {"type": "product", "label": entry.label, "productId": entry.product_id, "taxonomy": entry.group,
            "destination": entry.destination or None}


class SuggestProducts:
    def __init__(self, index: UnitIndex, popularity: Mapping[str, float] | None = None, *,
                 max_limit: int = 10, cache_size: int = 512) -> None:
        popularity = popularity or {}
        # Điểm đến: cùng tên và số đếm với /destinations. Sản phẩm: search unit còn bán, trừ vé máy bay.
        self._entries: list[SuggestEntry] = [
            SuggestEntry("destination", item["destination"], weight=float(item["productCount"]))
            for item in destination_list(index.destination)["destinations"] if item["destination"].strip()
        ]
        for i, product in enumerate(index.units):
            if product.taxonomy in SUGGEST_GROUPS and bool(index.available[i]) and product.name.strip():
                self._entries.append(SuggestEntry(
                    product.taxonomy, product.name, weight=float(popularity.get(product.product_id, 0.0)),
                    product_id=product.product_id, destination=product.destination))
        self.max_limit = max_limit
        self._cache: OrderedDict[tuple[str, int], list[dict]] = OrderedDict()
        self._cache_size = cache_size
        self._lock = Lock()   # route đồng bộ chạy trong threadpool

    def __call__(self, q: str, *, limit: int = 8) -> dict:
        query = canonical_query(q)
        limit = max(1, min(limit, self.max_limit))
        if not is_suggestable(query):
            return {"query": query, "suggestions": []}
        key = (fold(query), limit)
        with self._lock:
            cached = self._cache.get(key)
            if cached is not None:
                self._cache.move_to_end(key)
        if cached is None:
            cached = [_payload(entry) for entry in suggest(self._entries, query, limit)]
            with self._lock:
                self._cache[key] = cached
                while len(self._cache) > self._cache_size:
                    self._cache.popitem(last=False)
        return {"query": query, "suggestions": [dict(item) for item in cached]}
