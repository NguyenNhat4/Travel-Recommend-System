"""Port nạp metadata của các search unit kèm kho vector để truy vấn theo request."""
from __future__ import annotations

from typing import Protocol

from .unit_index import UnitIndex
from .vector_search import VectorSearchPort


class VectorStorePort(Protocol):
    def load(self) -> tuple[UnitIndex, VectorSearchPort]: ...
