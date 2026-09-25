"""Chính sách giữ chỗ (FR-BKG-05)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

# Stripe chỉ cho phiên Checkout hết hạn sau ít nhất 30 phút kể từ lúc tạo.
MIN_HOLD_MINUTES = 30
# Phiên Stripe được tạo sau khi tính hạn, nên cộng đệm để expires_at gửi sang Stripe không rơi xuống dưới 30 phút.
STRIPE_BUFFER_SECONDS = 60


@dataclass(frozen=True)
class HoldPolicy:
    minutes: int = MIN_HOLD_MINUTES

    def __post_init__(self) -> None:
        if self.minutes < MIN_HOLD_MINUTES:
            raise ValueError(f"thời gian giữ chỗ tối thiểu {MIN_HOLD_MINUTES} phút (giới hạn của Stripe Checkout)")

    def expires_at(self, now: datetime) -> datetime:
        return now + timedelta(minutes=self.minutes, seconds=STRIPE_BUFFER_SECONDS)

    @staticmethod
    def is_active(hold_expires_at: datetime | None, now: datetime) -> bool:
        return hold_expires_at is not None and now < hold_expires_at
