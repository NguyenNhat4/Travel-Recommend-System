"""Port (interface) mà infrastructure và agents phải hiện thực. Application chỉ phụ thuộc vào package này.

Mỗi port một file (docs/prd/architecture.md §2). Re-export các port RecSys để
`from ...application.ports import UnitIndex` vẫn viết được.
"""

from .cdp_client import CdpHistoryReader
from .embedder import EmbedderPort
from .recommendation_cache import RecommendationCacheStore, RecommendationCacheUnavailable
from .search_logs import SearchLogReader
from .unit_index import UnitIndex
from .vector_search import LexicalHit, LexicalSearchPort, VectorHit, VectorSearchPort
from .vector_store import VectorStorePort

__all__ = ["CdpHistoryReader", "EmbedderPort", "LexicalHit", "LexicalSearchPort", "RecommendationCacheStore",
           "RecommendationCacheUnavailable", "SearchLogReader", "UnitIndex", "VectorHit", "VectorSearchPort",
           "VectorStorePort"]
