"""Đồng hồ của agent: mọi chỗ đo ngân sách thời gian của lượt đọc giờ qua đây.

Snapshot hành vi thay `now` bằng đồng hồ ảo không trôi, để nhánh "hết giờ" không phụ thuộc tốc độ mạng hay model khi ghi
và khi phát lại (`docs/plan/2026-10-12-go-luong-cu-orchestrator-chinh.md`, D2). Gọi qua module (`clock.now()`), không
`from .clock import now`, thì bản thay mới có hiệu lực.
"""
from time import time as _time


def now() -> float:
    """Giây kể từ epoch, như `time.time()`."""
    return _time()
