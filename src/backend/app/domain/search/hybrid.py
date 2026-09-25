"""Hợp nhất nhánh dense và nhánh lexical của /search (`HYBRID_CANDIDATE_SCORE`, spec §2.2–2.4).

`scores` trả về vẫn là cosine để `hit()` và trường `score` của contract không đổi nghĩa; chỉ THỨ TỰ theo RRF.
Kết quả chỉ có ở nhánh lexical được "vớt" vào R khi đủ ba điều kiện: rank BM25 ≤ `lexical_k`,
cosine ≥ `lexical_cutoff`, và tên phủ đủ token của truy vấn (`admissible`, xem `lexical.coverage`).
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping
from dataclasses import dataclass

import numpy as np

from .scoring import SearchOutcome


@dataclass(frozen=True)
class HybridConfig:
    rrf_k: int = 60
    lexical_k: int = 10
    lexical_cutoff: float = 0.50
    min_coverage: float = 0.6    # tên phải chứa ≥ 60% token của truy vấn mới được vớt (xem lexical.coverage)


@dataclass
class HybridOutcome(SearchOutcome):
    lexical_only: frozenset[int] = frozenset()   # unit vào R chỉ nhờ nhánh lexical (score < cutoff)


def rrf(dense_rank: Mapping[int, int], lexical_rank: Mapping[int, int], k: int = 60) -> dict[int, float]:
    """Reciprocal rank fusion: Σ 1/(k + rank) trên các nhánh có mặt; rank bắt đầu từ 1."""
    out: dict[int, float] = {}
    for ranks in (dense_rank, lexical_rank):
        for u, r in ranks.items():
            out[u] = out.get(u, 0.0) + 1.0 / (k + r)
    return out


def hybrid_filter_score(cosines: Mapping[int, float], dense_rank: Mapping[int, int], lexical_rank: Mapping[int, int],
                        admissible: Callable[[int], bool], cutoff: float, cfg: HybridConfig,
                        filtered_count: int, facet_fields: dict[str, np.ndarray]) -> HybridOutcome:
    """`cosines`: cosine của mọi ứng viên hai nhánh. Giữ dense ≥ cutoff, vớt lexical theo `cfg`, sắp theo RRF.

    `lexical_k = 0` cho đúng tập R của `candidate_filter_score` (chỉ khác thứ tự).
    """
    kept_dense = {u for u, c in cosines.items() if c >= cutoff}
    kept_lex = {u for u, r in lexical_rank.items()
                if u not in kept_dense and r <= cfg.lexical_k and cosines.get(u, -1.0) >= cfg.lexical_cutoff
                and admissible(u)}
    fused = rrf(dense_rank, lexical_rank, cfg.rrf_k)
    kept = kept_dense | kept_lex
    order = sorted(kept, key=lambda u: (-fused.get(u, 0.0), -cosines[u], u))
    facets = {name: dict(Counter(str(arr[u]) for u in order)) for name, arr in facet_fields.items()}
    return HybridOutcome(order=order, scores={u: float(cosines[u]) for u in kept}, filtered_count=filtered_count,
                         facets=facets, lexical_only=frozenset(kept_lex))
