"""Mã đặt chỗ hiển thị: VOTA-YYYYMMDD-XXXX (contract ReferenceCode)."""
from __future__ import annotations

import secrets
import string
from datetime import date

_ALPHABET = string.ascii_uppercase + string.digits


def new_reference_code(today: date) -> str:
    return f"VOTA-{today:%Y%m%d}-" + "".join(secrets.choice(_ALPHABET) for _ in range(4))
