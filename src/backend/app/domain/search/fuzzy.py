"""Kênh fuzzy / alias của /search (kiến trúc Phase A/B §7 — 5C): tên unit gần đúng với một đoạn của câu hỏi.

Độ giống = Jaccard trên TẬP trigram kiểu pg_trgm (`similarity()` của Postgres, cùng cách với `parse_combos.trigrams`): fold
(`lexical.fold`), mỗi token đệm "  w " rồi cắt trigram. Khác pg_trgm ở một điểm: tên được so với từng CỬA SỔ token liên tiếp
của câu hỏi có độ dài trong khoảng (số token của tên ± 1), lấy max — câu dài chứa tên gõ sai ("Vinpeal Resort Nha Trnag gia
tot") vẫn khớp "Vinpearl Resort Nha Trang", điều mà similarity() trên cả câu không làm được (phần thừa "gia tot" kéo Jaccard
xuống). Câu ngắn hơn (số token của tên − 1) → cửa sổ duy nhất là cả câu.

Nhanh nhờ chỉ mục ngược trigram → unit. Mỗi câu đếm số trigram chung giữa tên và CẢ câu (|N∩Q|); vì cửa sổ ⊆ câu nên
|N∩W| ≤ |N∩Q| và |N∪W| ≥ |N|, tức |N∩Q| / |N| là CẬN TRÊN của độ giống cửa sổ. Duyệt unit theo cận giảm dần (tối đa
`shortlist` unit), dừng sớm khi cận < điểm thứ k: trong giới hạn `shortlist`, kết quả đúng như quét toàn catalog.

Kênh này chỉ sinh ứng viên + rank (`hybrid.hybrid_filter_score` fuse và quyết định vớt); không đổi điểm `score` của contract.
Thuần stdlib + numpy.
"""
from __future__ import annotations

import heapq
from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache

import numpy as np

from .lexical import fold

#: Số unit tối đa được tính độ giống cửa sổ cho một câu (theo cận trên giảm dần).
SHORTLIST = 200


@lru_cache(maxsize=65536)
def word_trigrams(word: str) -> frozenset[str]:
    """Trigram của MỘT token đã fold, đệm như pg_trgm: hai khoảng trắng đầu, một khoảng trắng cuối."""
    padded = f"  {word} "
    return frozenset(padded[i:i + 3] for i in range(len(padded) - 2))


def trigrams(text: str) -> frozenset[str]:
    """Tập trigram của cả chuỗi (fold rồi hợp trigram từng token) — như `show_trgm` của pg_trgm."""
    out: set[str] = set()
    for w in fold(text).split():
        out |= word_trigrams(w)
    return frozenset(out)


def _jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    inter = len(a & b)
    union = len(a) + len(b) - inter
    return inter / union if union else 0.0


def similarity(a: str, b: str) -> float:
    """pg_trgm `similarity(a, b)`: |A∩B| / |A∪B| trên tập trigram; chuỗi rỗng → 0."""
    return _jaccard(trigrams(a), trigrams(b))


def _window_lengths(n_name: int, n_query: int) -> range | None:
    """Độ dài cửa sổ được xét cho tên `n_name` token trên câu `n_query` token; None = dùng cả câu làm cửa sổ duy nhất."""
    lo, hi = max(1, n_name - 1), min(n_name + 1, n_query)
    return range(lo, hi + 1) if lo <= hi else None


class _Windows:
    """Trigram của cửa sổ token liên tiếp của một câu, tính lười và nhớ lại (dùng chung cho mọi unit của lượt tìm)."""

    __slots__ = ("tok", "whole", "_memo")

    def __init__(self, query_tokens: Sequence[str]):
        self.tok = [word_trigrams(t) for t in query_tokens]
        self.whole: frozenset[str] = frozenset().union(*self.tok) if self.tok else frozenset()
        self._memo: dict[tuple[int, int], frozenset[str]] = {}

    def get(self, start: int, length: int) -> frozenset[str]:
        key = (start, length)
        got = self._memo.get(key)
        if got is None:
            got = self.tok[start] if length == 1 else self.get(start, length - 1) | self.tok[start + length - 1]
            self._memo[key] = got
        return got

    def best(self, name_grams: frozenset[str], n_name: int) -> float:
        """max Jaccard(tên, cửa sổ) trên mọi cửa sổ có độ dài trong (n_name ± 1); câu quá ngắn → so với cả câu."""
        m = len(self.tok)
        lengths = _window_lengths(n_name, m)
        if lengths is None:
            return _jaccard(name_grams, self.whole)
        best = 0.0
        for length in lengths:
            for start in range(m - length + 1):
                s = _jaccard(name_grams, self.get(start, length))
                if s > best:
                    best = s
                    if best >= 1.0:
                        return best
        return best


def window_similarity(name: str, query: str) -> float:
    """Độ giống của tên `name` với đoạn khớp nhất của câu `query` (cùng công thức `FuzzyIndex.search` dùng)."""
    grams = trigrams(name)
    q_tokens = fold(query).split()
    if not grams or not q_tokens:
        return 0.0
    return _Windows(q_tokens).best(grams, len(fold(name).split()))


@dataclass(frozen=True, eq=False)
class FuzzyIndex:
    """Chỉ mục trigram trên TÊN của search unit; phần tử thứ i ứng với `UnitIndex.units[i]`."""

    name_grams: tuple[frozenset[str], ...]   # tập trigram của tên (rỗng khi tên fold ra rỗng → không bao giờ khớp)
    name_tokens: np.ndarray                  # (n,) int32 — số token của tên sau fold
    sizes: np.ndarray                        # (n,) float64 — |tập trigram| (0 → 1 để chia an toàn; số đếm khi đó luôn 0)
    postings: dict[str, np.ndarray]          # trigram → index unit (int32, tăng dần, không lặp)

    def __len__(self) -> int:
        return len(self.name_grams)

    @staticmethod
    def build(names: Sequence[str]) -> "FuzzyIndex":
        """Một phần tử mỗi tên, đúng thứ tự `names` (= thứ tự `UnitIndex.units`)."""
        grams: list[frozenset[str]] = []
        n_tok: list[int] = []
        post: dict[str, list[int]] = {}
        for i, name in enumerate(names):
            toks = fold(name or "").split()
            g = frozenset().union(*(word_trigrams(t) for t in toks)) if toks else frozenset()
            grams.append(g)
            n_tok.append(len(toks))
            for t in g:
                post.setdefault(t, []).append(i)
        return FuzzyIndex(name_grams=tuple(grams), name_tokens=np.array(n_tok, dtype=np.int32),
                          sizes=np.array([len(g) or 1 for g in grams], dtype=np.float64),
                          postings={t: np.array(ix, dtype=np.int32) for t, ix in post.items()})

    def search(self, query: str, allowed: np.ndarray | None = None, k: int = 50, *, min_sim: float = 0.0,
               shortlist: int = SHORTLIST) -> list[tuple[int, float]]:
        """Top-`k` (index unit, độ giống) theo độ giống cửa sổ giảm dần, hoà → index nhỏ trước; độ giống ∈ (0, 1].

        `allowed`: mask bool theo index unit (tập F sau filter) — unit ngoài mask không bao giờ được trả; None = mọi unit.
        `min_sim`: bỏ unit có độ giống < ngưỡng (cũng dùng để cắt sớm theo cận trên). `shortlist`: số unit tối đa được tính
        độ giống cửa sổ, chọn theo cận trên |N∩Q| / |N| giảm dần."""
        n = len(self.name_grams)
        q_tokens = fold(query or "").split()
        if k <= 0 or n == 0 or not q_tokens or shortlist <= 0:
            return []
        win = _Windows(q_tokens)
        counts = np.zeros(n, dtype=np.int32)
        for t in win.whole:
            ix = self.postings.get(t)
            if ix is not None:
                counts[ix] += 1   # mỗi posting không lặp index nên cộng theo fancy index là đúng
        bound = counts / self.sizes
        if allowed is not None:
            bound = np.where(np.asarray(allowed, dtype=bool), bound, 0.0)
        floor = max(float(min_sim), 0.0)
        cand = np.flatnonzero((bound > 0.0) & (bound >= floor))
        if cand.size == 0:
            return []
        cand = cand[np.lexsort((cand, -bound[cand]))][:shortlist]   # cận giảm dần, hoà → index nhỏ trước
        heap: list[tuple[float, int]] = []   # min-heap (sim, -index): phần tử đầu là kết quả "tệ nhất" đang giữ
        for u in cand.tolist():
            if len(heap) >= k and bound[u] < heap[0][0]:
                break   # mọi unit còn lại có cận ≤ cận này < điểm thứ k
            s = win.best(self.name_grams[u], int(self.name_tokens[u]))
            if s <= 0.0 or s < floor:
                continue
            item = (s, -u)
            if len(heap) < k:
                heapq.heappush(heap, item)
            elif item > heap[0]:
                heapq.heapreplace(heap, item)
        return [(-neg, s) for s, neg in sorted(heap, key=lambda x: (-x[0], -x[1]))]
