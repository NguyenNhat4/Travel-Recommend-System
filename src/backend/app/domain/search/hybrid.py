"""Hợp nhất nhánh dense, nhánh lexical (và nhánh fuzzy tuỳ chọn) của /search (`HYBRID_CANDIDATE_SCORE`, spec §2.2–2.4;
kiến trúc Phase A/B §7–§8).

`scores` trả về vẫn là cosine để `hit()` và trường `score` của contract không đổi nghĩa; chỉ THỨ TỰ theo RRF.
Kết quả chỉ có ở nhánh lexical được "vớt" vào R khi đủ ba điều kiện: rank BM25 ≤ `lexical_k`,
cosine ≥ `lexical_cutoff`, và tên phủ đủ token của truy vấn (`admissible`, xem `lexical.coverage`).

Nhánh fuzzy (`fuzzy.FuzzyIndex`, tên gần đúng với một đoạn câu) mặc định TẮT (`fuzzy_k = 0`): khi tắt, kết quả y hệt bản hai
nhánh. Bật thì unit không được dense/lexical giữ được vớt khi rank fuzzy ≤ `fuzzy_k`, cosine ≥ `lexical_cutoff` và
`fuzzy_admissible` (use case truyền độ giống ≥ `fuzzy_min_sim`); thứ tự = RRF có trọng số trên mọi nhánh unit có mặt.
Trọng số nhánh mặc định 1.0 → đúng RRF thường, số y hệt trước (kiến trúc §8: chỉ tune trọng số trên split dev).
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
    # Kênh fuzzy/alias (kiến trúc §7 5C). `fuzzy_k = 0` = TẮT kênh: không vớt, không góp RRF dù có truyền rank fuzzy.
    fuzzy_k: int = 0                 # unit chỉ nhờ nhánh fuzzy được vớt khi rank fuzzy ≤ fuzzy_k
    fuzzy_candidate_k: int = 50      # độ dài danh sách fuzzy đem fuse (use case truyền vào `FuzzyIndex.search`)
    fuzzy_min_sim: float = 0.6       # độ giống trigram cửa sổ tối thiểu để vớt (use case kiểm qua `fuzzy_admissible`)
    # Trọng số RRF theo nhánh (kiến trúc §8 weighted fusion); 1.0 = RRF thường.
    dense_weight: float = 1.0
    lexical_weight: float = 1.0
    fuzzy_weight: float = 1.0
    # Cổng bằng chứng (plan 2026-10-13 §2.2): BM25 chỉ được cộng điểm RRF cho unit có bằng chứng cụm (`rrf_admissible`);
    # `admissible` (vớt) do use case truyền bằng chứng TÊN theo cụm thay cho độ phủ túi chữ. False = như trước.
    evidence_gate: bool = False


@dataclass
class HybridOutcome(SearchOutcome):
    lexical_only: frozenset[int] = frozenset()   # unit vào R chỉ nhờ nhánh lexical (score < cutoff)
    fuzzy_only: frozenset[int] = frozenset()     # unit vào R chỉ nhờ nhánh fuzzy (không được dense lẫn lexical giữ)


def rrf(dense_rank: Mapping[int, int], lexical_rank: Mapping[int, int], k: int = 60, *,
        fuzzy_rank: Mapping[int, int] | None = None, dense_weight: float = 1.0, lexical_weight: float = 1.0,
        fuzzy_weight: float = 1.0) -> dict[int, float]:
    """Reciprocal rank fusion: Σ w_nhánh / (k + rank) trên các nhánh có mặt; rank bắt đầu từ 1.

    Trọng số 1.0 cho đúng số của RRF thường (1.0 / x == 1 / x); nhánh trọng số 0 bị bỏ hẳn (không thêm khoá điểm 0)."""
    out: dict[int, float] = {}
    legs = [(dense_rank, dense_weight), (lexical_rank, lexical_weight)]
    if fuzzy_rank:
        legs.append((fuzzy_rank, fuzzy_weight))
    for ranks, w in legs:
        if w == 0:
            continue
        for u, r in ranks.items():
            out[u] = out.get(u, 0.0) + w / (k + r)
    return out


def hybrid_filter_score(cosines: Mapping[int, float], dense_rank: Mapping[int, int], lexical_rank: Mapping[int, int],
                        admissible: Callable[[int], bool], cutoff: float, cfg: HybridConfig,
                        filtered_count: int, facet_fields: dict[str, np.ndarray], *,
                        fuzzy_rank: Mapping[int, int] | None = None,
                        fuzzy_admissible: Callable[[int], bool] | None = None,
                        rrf_admissible: Callable[[int], bool] | None = None) -> HybridOutcome:
    """`cosines`: cosine của mọi ứng viên các nhánh. Giữ dense ≥ cutoff, vớt lexical (và fuzzy) theo `cfg`, sắp theo RRF.

    `lexical_k = 0` cho đúng tập R của `candidate_filter_score` (chỉ khác thứ tự). `fuzzy_rank` None hoặc `cfg.fuzzy_k = 0`
    → bỏ qua nhánh fuzzy. Unit vớt nhờ fuzzy phải có cosine trong `cosines` (use case lấy vector cho unit chỉ có ở fuzzy);
    `fuzzy_admissible` None = mọi unit đạt.
    """
    kept_dense = {u for u, c in cosines.items() if c >= cutoff}
    kept_lex = {u for u, r in lexical_rank.items()
                if u not in kept_dense and r <= cfg.lexical_k and cosines.get(u, -1.0) >= cfg.lexical_cutoff
                and admissible(u)}
    fuzzy = fuzzy_rank if fuzzy_rank and cfg.fuzzy_k > 0 else None
    kept_fuzzy: set[int] = set()
    if fuzzy:
        kept_fuzzy = {u for u, r in fuzzy.items()
                      if u not in kept_dense and u not in kept_lex and r <= cfg.fuzzy_k and u in cosines
                      and cosines[u] >= cfg.lexical_cutoff and (fuzzy_admissible is None or fuzzy_admissible(u))}
    if cfg.evidence_gate and rrf_admissible is not None:   # khớp rời rạc / sai dấu không được đẩy thứ hạng
        lexical_rank = {u: r for u, r in lexical_rank.items() if u in kept_lex or rrf_admissible(u)}
    fused = rrf(dense_rank, lexical_rank, cfg.rrf_k, fuzzy_rank=fuzzy, dense_weight=cfg.dense_weight,
                lexical_weight=cfg.lexical_weight, fuzzy_weight=cfg.fuzzy_weight)
    kept = kept_dense | kept_lex | kept_fuzzy
    order = sorted(kept, key=lambda u: (-fused.get(u, 0.0), -cosines[u], u))
    facets = {name: dict(Counter(str(arr[u]) for u in order)) for name, arr in facet_fields.items()}
    return HybridOutcome(order=order, scores={u: float(cosines[u]) for u in kept}, filtered_count=filtered_count,
                         facets=facets, lexical_only=frozenset(kept_lex), fuzzy_only=frozenset(kept_fuzzy))
