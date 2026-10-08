"""Quy tắc /search: FILTER → SCORE → CUTOFF → TOTAL/FACETS → SORT → PAGE (không SQL, không HTTP).

`candidate_filter_score` là bản ANN: SCORE do kho vector trả cho top-K ứng viên đã lọc id; total/facets
chỉ đếm trên tập ứng viên đó (spec §2.2, `ANN_CANDIDATE_SCORE`). `exact_filter_score` quét toàn bộ ma trận.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

import numpy as np


@dataclass
class SearchOutcome:
    order: list[int]                 # index đã sort, chỉ phần tử đạt cutoff
    scores: np.ndarray | Mapping[int, float]   # tra theo index unit: scores[i]
    filtered_count: int
    facets: dict[str, dict[str, int]] = field(default_factory=dict)

    @property
    def total(self) -> int:
        return len(self.order)


def exact_filter_score(E: np.ndarray, qvec: np.ndarray, mask: np.ndarray, cutoff: float,
                       facet_fields: dict[str, np.ndarray]) -> SearchOutcome:
    scores = E @ qvec
    relevant = mask & (scores >= cutoff)
    idx = np.flatnonzero(relevant)
    order = idx[np.argsort(-scores[idx])].tolist()
    facets = {name: dict(Counter(map(str, arr[relevant]))) for name, arr in facet_fields.items()}
    return SearchOutcome(order=order, scores=scores, filtered_count=int(mask.sum()), facets=facets)


def candidate_filter_score(units: Sequence[int], scores: Sequence[float], cutoff: float, filtered_count: int,
                           facet_fields: dict[str, np.ndarray]) -> SearchOutcome:
    """`units`/`scores`: ứng viên top-K (đã qua structured filter) và cosine tương ứng."""
    kept = {int(u): float(sc) for u, sc in zip(units, scores) if sc >= cutoff}
    order = sorted(kept, key=lambda u: -kept[u])
    facets = {name: dict(Counter(str(arr[u]) for u in order)) for name, arr in facet_fields.items()}
    return SearchOutcome(order=order, scores=kept, filtered_count=filtered_count, facets=facets)


def soft_star_order(order: Sequence[int], known_ok: np.ndarray) -> list[int]:
    """Hạng sao mềm (Phase A, F6): unit có sao ĐÃ BIẾT và đạt ngưỡng lên trước, unit chưa biết sao xuống sau.

    Phân hoạch ổn định — thứ tự tương đối trong từng nhóm giữ nguyên, nên điểm RRF vẫn quyết định bên trong nhóm.
    `known_ok` = `UnitIndex.star_known_ok(star_min)` (bool theo index unit)."""
    head = [i for i in order if known_ok[i]]
    tail = [i for i in order if not known_ok[i]]
    return head + tail


def revalidate(order: Sequence[int], mask: np.ndarray) -> tuple[list[int], int]:
    """Soát lại thứ tự sau khi kho vector trả về: bỏ index không còn trong `mask` (filter cứng áp sau ANN).

    Trả (thứ tự còn lại, số phần tử bị bỏ) để use case ghi vào diagnostics."""
    kept = [i for i in order if mask[i]]
    return kept, len(order) - len(kept)
