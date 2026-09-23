"""Port (interface) mà infrastructure và agents phải hiện thực. Application chỉ phụ thuộc vào package này.

Mỗi port một file (docs/prd/architecture.md §2). Re-export các port RecSys để
`from ...application.ports import UnitIndex` vẫn viết được.
"""

from .cdp_client import CdpHistoryReader
from .embedder import EmbedderPort
from .unit_index import UnitIndex
from .vector_store import VectorStorePort

__all__ = ["CdpHistoryReader", "EmbedderPort", "UnitIndex", "VectorStorePort"]
