"""Port nạp chỉ mục vector của các search unit."""
from __future__ import annotations

from typing import Protocol

from .unit_index import UnitIndex


class VectorStorePort(Protocol):
    def load(self) -> UnitIndex: ...
