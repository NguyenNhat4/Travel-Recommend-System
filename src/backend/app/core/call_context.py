"""Nguồn và chi tiết của lần gọi đang xử lý (web qua HTTP hoặc agent gọi công cụ trong tiến trình).

Chỉ giữ `ContextVar`, không import FastAPI (docs/prd/architecture.md §2, quy tắc 9). Chi tiết là một dict dùng chung:
use case chạy trong thread (`asyncio.to_thread`, `copy_context().run`) ghi vào cùng dict nên nơi mở lần gọi đọc lại
được (docs/prd/deployment-plan.md §5, đo lần gọi web / agent).
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar

_source: ContextVar[str | None] = ContextVar("call_source", default=None)
_detail: ContextVar[dict | None] = ContextVar("call_detail", default=None)


def current_source() -> str | None:
    return _source.get()


@contextmanager
def call_scope(source: str):
    """Mở một lần gọi: `source` là `web` hoặc `agent`; trả dict chi tiết mà use case ghi vào."""
    detail: dict = {}
    s_token, d_token = _source.set(source), _detail.set(detail)
    try:
        yield detail
    finally:
        _source.reset(s_token)
        _detail.reset(d_token)


def note(**values) -> None:
    """Use case / wrapper ghi chi tiết (stageMs, số kết quả…). Ngoài lần gọi nào thì bỏ qua."""
    detail = _detail.get()
    if detail is not None:
        detail.update(values)
