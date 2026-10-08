"""Map amenity thô → amenity_ids (spec Part 1). KHÔNG phải taxonomy chính thức.

Dùng lại `vector_bench/dataset/amenities.py` (alias exact → cụm từ dài nhất → `raw:<slug>` ≥ amenity_min_freq, id int16)
và chèn thêm một bước giữa: similarity trigram kiểu pg_trgm (Jaccard trên tập trigram của từng từ đã fold, đệm "  w ")
với alias seed, khớp khi > amenity_fuzzy_min. Không dùng rapidfuzz ratio: trên snapshot 2026-09-21 nó map sai ~141 chuỗi
(`ban cong` → breakfast, `phong tam rieng` → family_room…). Mọi lần khớp trigram được ghi lại để Người A soát.

Chuỗi không phải tiện ích của sản phẩm bị bỏ trước khi khớp (05/10, gold_v4 — D11): chuỗi phủ định "Không có …" / "… : no"
(cơ sở KHÔNG có tiện ích đó; trước đây "Không có Thang máy" thành `elevator`), chuỗi khoảng cách tới địa điểm lân cận
"… 570 m" / "… 1,6 km" (trước đây "Sân Golf Đà Lạt 570 m" thành `golf`, "Story Beach & Pool 190 m" thành `pool`) và tiện
ích "(Tạm thời ngừng hoạt động)".
"""
from __future__ import annotations

import csv
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from evaluation.vector_bench.dataset.amenities import AmenityMatcher, AmenityVocab, SeedAmenity, build_vocab, load_seed
from evaluation.vector_bench.lexical import fold

__all__ = ["AmenityVocab", "TrigramAmenityMatcher", "build_vocab", "is_not_amenity", "load_seed", "similarity", "trigrams"]

_NEGATED = "khong co "                                          # fold("Không có …")
_NO_FLAG = re.compile(r":\s*(?:no|không)\s*$", re.IGNORECASE)       # "Phòng / tầng không hút thuốc : no"
_CLOSED = "tam thoi ngung hoat dong"                             # fold("(Tạm thời ngừng hoạt động)")
_DISTANCE = re.compile(r"\d+(?:[.,]\d+)?\s*(?:m|km)\s*$", re.IGNORECASE)   # "Chợ Đà Lạt 1,6 km", "… : 1km", "… 570 m"


def is_not_amenity(raw: str) -> bool:
    """Chuỗi trong `attributes.amenities` mà không phải tiện ích sản phẩm đang có: phủ định ("Không có …", "… : no"),
    khoảng cách tới nơi khác, hoặc tiện ích tạm ngừng hoạt động."""
    f, s = fold(raw), raw.strip()
    return f.startswith(_NEGATED) or _CLOSED in f or bool(_NO_FLAG.search(s) or _DISTANCE.search(s))


def trigrams(s: str) -> frozenset[str]:
    """Tập trigram như pg_trgm: mỗi từ (đã fold) đệm hai khoảng trắng trước, một sau."""
    out: set[str] = set()
    for w in fold(s).split():
        padded = f"  {w} "
        out.update(padded[i:i + 3] for i in range(len(padded) - 2))
    return frozenset(out)


def similarity(a: str, b: str) -> float:
    ta, tb = trigrams(a), trigrams(b)
    union = ta | tb
    return len(ta & tb) / len(union) if union else 0.0


@dataclass(frozen=True)
class FuzzyHit:
    folded: str
    alias: str
    key: str
    score: float


class TrigramAmenityMatcher:
    """Cùng giao diện `.seed` / `.match(raw)` với AmenityMatcher của vbench để đưa thẳng vào `build_vocab`."""

    def __init__(self, seed: list[SeedAmenity], min_similarity: float):
        self.seed = seed
        self.min_similarity = min_similarity
        self._base = AmenityMatcher(seed)
        self._aliases = [(a, s.key, trigrams(a)) for s in seed for a in s.aliases]
        self._fuzzy: dict[str, FuzzyHit | None] = {}
        self.hit_counts: Counter[str] = Counter()          # folded → số lần gặp (theo chuỗi thô, không theo unit)

    def match(self, raw: str) -> tuple[str, str]:
        if is_not_amenity(raw):
            return "raw", ""                                        # build_vocab bỏ qua giá trị rỗng
        kind, val = self._base.match(raw)
        if kind == "seed" or not val:
            return kind, val
        if val not in self._fuzzy:
            self._fuzzy[val] = self._best(val)
        hit = self._fuzzy[val]
        if hit is None:
            return "raw", val
        self.hit_counts[val] += 1
        return "seed", hit.key

    def _best(self, folded: str) -> FuzzyHit | None:
        t = trigrams(folded)
        best: FuzzyHit | None = None
        for alias, key, ta in self._aliases:
            union = t | ta
            score = len(t & ta) / len(union) if union else 0.0
            if score > self.min_similarity and (best is None or score > best.score):
                best = FuzzyHit(folded, alias, key, round(score, 4))
        return best

    def fuzzy_hits(self) -> list[FuzzyHit]:
        return sorted((h for h in self._fuzzy.values() if h is not None), key=lambda h: (-self.hit_counts[h.folded], h.folded))

    def write_hits(self, path: Path) -> int:
        hits = self.fuzzy_hits()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["raw_folded", "matched_alias", "key", "score", "occurrences"])
            for h in hits:
                w.writerow([h.folded, h.alias, h.key, h.score, self.hit_counts[h.folded]])
        return len(hits)


def id_drift(old: dict[str, dict], new: dict[str, dict]) -> tuple[list[str], list[str]]:
    """So hai amenity_vocab.json ({id: {key, …}}). Trả (khoá đổi id, khoá biến mất)."""
    old_ids = {e["key"]: int(i) for i, e in old.items()}
    new_ids = {e["key"]: int(i) for i, e in new.items()}
    changed = sorted(k for k, i in old_ids.items() if k in new_ids and new_ids[k] != i)
    removed = sorted(k for k in old_ids if k not in new_ids)
    return changed, removed
