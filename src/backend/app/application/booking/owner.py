"""Chủ của giỏ hàng và đơn nháp: người đã đăng nhập hoặc khách chưa đăng nhập (spec dat-truc-tiep-theo-don-nhap.md §8)."""
from __future__ import annotations

import re
from dataclasses import dataclass

from src.backend.app.application.auth.principal import AuthPrincipal

# guestId do BFF phát: `g_` + 128 bit ngẫu nhiên dạng base64url (R-GST-03).
GUEST_ID_PATTERN = re.compile(r"^g_[A-Za-z0-9_-]{22}$")


@dataclass(frozen=True)
class CartOwner:
    """`key` là `cdp_user_id` (người dùng) hoặc `guestId` (khách). Khách không có danh tính CDP nên không sinh event."""

    key: str
    is_guest: bool = False

    @classmethod
    def user(cls, cdp_user_id: str) -> "CartOwner":
        return cls(cdp_user_id, False)

    @classmethod
    def guest(cls, guest_id: str) -> "CartOwner":
        return cls(guest_id, True)

    @property
    def cdp_user_id(self) -> str | None:
        return None if self.is_guest else self.key


def owner_of(who: "CartOwner | AuthPrincipal") -> CartOwner:
    """Use case nhận cả `AuthPrincipal` (route chỉ dành cho người đã đăng nhập, test cũ) lẫn `CartOwner`."""
    return who if isinstance(who, CartOwner) else CartOwner.user(who.cdp_user_id)
