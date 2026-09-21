"""Quy tắc /search: FILTER → SCORE → CUTOFF → TOTAL/FACETS → SORT → PAGE (không SQL, không HTTP)."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

import numpy as np


@dataclass
class SearchOutcome:
    order: list[int]                 # index đã sort, chỉ phần tử đạt cutoff
    scores: np.ndarray
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
