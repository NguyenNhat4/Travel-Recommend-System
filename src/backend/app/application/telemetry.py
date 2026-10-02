"""Bọc use case để ghi chi tiết lần gọi (docs/prd/deployment-plan.md §5).

Composition root bọc search / similar / recommend / catalog; route web và công cụ agent gọi cùng một đối tượng nên
cả hai được đo như nhau. Chỉ đọc kết quả trả về (productId, số kết quả, `diagnostics.stageMs`), không đọc tham số
(câu tìm kiếm có thể chứa dữ liệu cá nhân).
"""
from __future__ import annotations

import inspect
import time
from typing import Any

from src.backend.app.core.call_context import note

MAX_IDS = 20
TRACED_METHODS = ("lookup",)


def _items(result: Any) -> list | None:
    if isinstance(result, list):
        return result
    if isinstance(result, dict):
        for key in ("results", "items", "products", "recommendations"):
            if isinstance(result.get(key), list):
                return result[key]
    for attr in ("results", "items"):
        value = getattr(result, attr, None)
        if isinstance(value, (list, tuple)):
            return list(value)
    return None


def summarize(result: Any) -> dict[str, Any]:
    """{resultCount, productIds (tối đa 20), stageMs} lấy từ kết quả; khoá nào không có thì bỏ."""
    out: dict[str, Any] = {}
    items = _items(result)
    if items is not None:
        out["resultCount"] = len(items)
        ids = [i.get("productId") for i in items if isinstance(i, dict) and i.get("productId")]
        if ids:
            out["productIds"] = ids[:MAX_IDS]
    if isinstance(result, dict):
        if isinstance(result.get("productId"), str) and "resultCount" not in out:
            out.update(resultCount=1, productIds=[result["productId"]])
        stages = (result.get("diagnostics") or {}).get("stageMs") if isinstance(result.get("diagnostics"), dict) else None
        if isinstance(stages, dict):
            out["stageMs"] = stages
    return out


class Traced:
    """Proxy trong suốt: gọi y như use case gốc, thêm ghi `useCase`, `useCaseMs` và `summarize(kết quả)`."""

    __slots__ = ("_inner", "_name")

    def __init__(self, inner: Any, name: str):
        self._inner = inner
        self._name = name

    @property
    def traced_inner(self) -> Any:
        return self._inner

    def _note(self, started: float, result: Any) -> None:
        note(useCase=self._name, useCaseMs=round((time.perf_counter() - started) * 1000, 1), **summarize(result))

    def _call(self, fn, *args, **kwargs):
        started = time.perf_counter()
        result = fn(*args, **kwargs)
        if inspect.isawaitable(result):  # use case catalog là async: đo tới khi có kết quả thật
            async def finish():
                value = await result
                self._note(started, value)
                return value
            return finish()
        self._note(started, result)
        return result

    def __call__(self, *args, **kwargs):
        return self._call(self._inner, *args, **kwargs)

    def __getattr__(self, name: str):
        value = getattr(self._inner, name)
        if name in TRACED_METHODS and callable(value):
            return lambda *args, **kwargs: self._call(value, *args, **kwargs)
        return value


def traced(service: Any, name: str) -> Any:
    """Bọc một lần; None và đối tượng đã bọc giữ nguyên."""
    if service is None or isinstance(service, Traced):
        return service
    return Traced(service, name)
