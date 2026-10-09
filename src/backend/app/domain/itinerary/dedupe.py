"""Bỏ điểm tham quan trùng nhau trước khi xếp lịch (AC-AGT-04, node `filter`). Hàm thuần, không gọi model.

Hai nguồn cặp trùng: luật (`same_name_pairs`, cùng tên đã `fold`) và LLM (cặp mã do node `filter` nhận). Cả hai đi qua
`apply_pairs`: chỉ cặp gồm hai điểm tham quan có trong ứng viên được nhận; mỗi cặp giữ một mã theo `planning.keep_rank`.

Không bắc cầu (trace 08/10/2026): combo "Water Taxi + Bảo Tàng Gấu" trùng với cả vé Water Taxi lẫn vé Bảo tàng Gấu, nhưng
hai vé đó là hai việc khác nhau. Duyệt mã theo `keep_rank`; một mã chỉ bị bỏ khi nó cặp với một mã đang được giữ.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from .normalization import fold
from .planning import SLOT_TAXONOMIES, keep_rank, multi_day_span
from .types import Candidates, Product, Sources

RULE = "rule"
LLM = "llm"


def filterable(candidates: Candidates) -> list[Product]:
    """Điểm tham quan có thể vào một buổi của lịch; khách sạn, vé bay, combo và gói nhiều ngày không qua bước lọc."""
    return [product for product in candidates.values()
            if product.get("taxonomy") in SLOT_TAXONOMIES and not multi_day_span(product)]


def same_name_pairs(products: Iterable[Product]) -> list[tuple[str, str]]:
    """Mọi cặp sản phẩm cùng tên, không phân biệt dấu, chữ hoa và dấu câu."""
    by_name: dict[str, list[str]] = {}
    for product in sorted(products, key=lambda item: item["productId"]):
        if key := fold(product.get("name")):
            by_name.setdefault(key, []).append(product["productId"])
    return [(a, b) for ids in by_name.values() for index, a in enumerate(ids) for b in ids[index + 1:]]


def apply_pairs(candidates: Candidates, sources: Sources, pairs: Iterable[tuple[str, str]],
                by: str) -> tuple[Candidates, list[dict[str, Any]]]:
    """`(ứng viên còn lại, mã bị bỏ)`. Cặp có mã lạ, mã không phải điểm tham quan, hay hai mã giống nhau bị bỏ qua.

    Mỗi mục bị bỏ: `productId`, `name`, `duplicateOf` (mã được giữ mà nó trùng, thứ hạng tốt nhất), `duplicateOfName`, `by`
    (`rule`/`llm`). Kết quả không phụ thuộc thứ tự các cặp.
    """
    allowed = {product["productId"] for product in filterable(candidates)}
    rank = {product_id: keep_rank(sources, candidates[product_id]) for product_id in allowed}
    partners: dict[str, set[str]] = {product_id: set() for product_id in allowed}
    for a, b in pairs:
        if a in allowed and b in allowed and a != b:
            partners[a].add(b)
            partners[b].add(a)
    kept = dict(candidates)
    keeping: set[str] = set()
    dropped = []
    for product_id in sorted(allowed, key=rank.__getitem__):
        better = partners[product_id] & keeping
        if not better:
            keeping.add(product_id)
            continue
        keep = min(better, key=rank.__getitem__)
        del kept[product_id]
        dropped.append({"productId": product_id, "name": candidates[product_id].get("name"),
                        "duplicateOf": keep, "duplicateOfName": candidates[keep].get("name"), "by": by})
    return kept, dropped
