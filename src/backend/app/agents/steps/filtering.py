"""Bước của node `filter`: bỏ điểm tham quan trùng trước `compose` (AC-AGT-04, chốt 2026-10-08).

Luật chạy trước (cùng tên, `dedupe.same_name_pairs`); LLM chỉ nhận mã và tên các điểm còn lại, trả cặp mã trùng
(`DuplicatePairs`). Giữ mã nào do `dedupe.apply_pairs` quyết định, nên LLM không thêm, đổi hay xếp sản phẩm nào.
"""

from __future__ import annotations

from typing import Any

from src.backend.app.domain.itinerary import dedupe

from ..models import DuplicatePairs
from .history import prompt_yaml
from .messages import message
from .prompts import FILTER_PROMPT


def ruled(state: dict) -> dict | None:
    """Kết quả bước luật: `candidates`, `dropped_duplicates`. None khi lượt không đi tới lịch (không có gì để lọc).

    Điểm tham quan: cùng tên. Gói nhiều ngày: cùng các từ, không kể thứ tự, chỉ so giữa các gói với nhau.
    """
    if state.get("decision") != "compose" or not state.get("candidates"):
        return None
    sources = state.get("sources", {})
    candidates, dropped = dedupe.apply_pairs(state["candidates"], sources,
                                             dedupe.same_name_pairs(dedupe.filterable(state["candidates"])),
                                             dedupe.RULE)
    candidates, passes = dedupe.apply_pairs(candidates, sources,
                                            dedupe.same_name_pairs(dedupe.multi_day(candidates), any_order=True),
                                            dedupe.RULE, pool=dedupe.multi_day)
    return {"candidates": candidates, "dropped_duplicates": [*dropped, *passes]}


def needs_llm(update: dict | None) -> bool:
    """Còn từ hai điểm tham quan thì mới có cặp để hỏi LLM."""
    return update is not None and len(dedupe.filterable(update["candidates"])) >= 2


def filter_input(state: dict, update: dict) -> list:
    """Chỉ mã và tên các điểm tham quan sau bước luật, theo mã; không giá, không ngữ cảnh hội thoại."""
    products = [{"id": product["productId"], "name": product.get("name")}
                for product in sorted(dedupe.filterable(update["candidates"]), key=lambda item: item["productId"])]
    payload = {"destination": (state.get("intent") or {}).get("destination"), "products": products}
    return [("system", FILTER_PROMPT), ("human", prompt_yaml(payload))]


def filtered(state: dict, update: dict, result: DuplicatePairs | None) -> dict:
    """Áp cặp của LLM lên kết quả bước luật rồi nối cảnh báo `PRODUCT_DROPPED_DUPLICATE` cho mọi mã bị bỏ."""
    candidates, dropped = update["candidates"], list(update["dropped_duplicates"])
    if result is not None:
        candidates, by_llm = dedupe.apply_pairs(candidates, state.get("sources", {}),
                                                [tuple(pair.ids) for pair in result.pairs if pair.duplicate],
                                                dedupe.LLM)
        dropped += by_llm
    warnings: list[dict[str, Any]] = [
        {"code": "PRODUCT_DROPPED_DUPLICATE", "productId": item["productId"],
         "message": message(state, "dropped_duplicate", name=item["name"], kept=item["duplicateOfName"])}
        for item in dropped]
    return {"candidates": candidates, "dropped_duplicates": dropped,
            "warnings": [*state.get("warnings", []), *warnings]}
