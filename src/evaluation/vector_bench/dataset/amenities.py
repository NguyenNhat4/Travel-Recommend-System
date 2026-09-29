"""Fallback chuẩn hoá amenity → amenity_ids (spec P1.3). KHÔNG phải taxonomy chính thức.

1. fold chuỗi amenity.
2. Khớp alias trong config/amenity_seed.yaml: exact trước, sau đó theo cụm từ nguyên token (alias dài nhất thắng).
3. Không khớp → chuỗi raw; raw xuất hiện ≥ amenity_min_freq lần trên các search unit → id riêng `raw:<slug>`, ít hơn → bỏ.
4. id int16 từ 1: seed key theo alphabet, rồi raw theo tần suất giảm dần (hoà: theo slug).
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .. import paths
from ..lexical import fold, slug

INT16_MAX = 32767


@dataclass
class SeedAmenity:
    key: str
    label: str
    aliases: list[str]


def load_seed(path: Path | None = None) -> list[SeedAmenity]:
    p = path or (paths.CONFIG_DIR / "amenity_seed.yaml")
    raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    out = []
    for key, v in raw.items():
        out.append(SeedAmenity(key=key, label=v["label"], aliases=[fold(a) for a in v["aliases"]]))
    return out


class AmenityMatcher:
    def __init__(self, seed: list[SeedAmenity]):
        self.seed = seed
        self.exact: dict[str, str] = {}
        self.phrases: list[tuple[int, int, tuple[str, ...], str]] = []   # (−len token, −len chars, tokens, key)
        for s in seed:
            for a in s.aliases:
                self.exact.setdefault(a, s.key)
                toks = tuple(a.split())
                self.phrases.append((-len(toks), -len(a), toks, s.key))
        self.phrases.sort()
        self._cache: dict[str, tuple[str, str]] = {}

    def match(self, raw: str) -> tuple[str, str]:
        """→ ('seed', key) hoặc ('raw', folded)."""
        f = fold(raw)
        hit = self._cache.get(f)
        if hit is None:
            hit = self._match_folded(f)
            self._cache[f] = hit
        return hit

    def _match_folded(self, f: str) -> tuple[str, str]:
        if not f:
            return ("raw", "")
        if f in self.exact:
            return ("seed", self.exact[f])
        toks = f.split()
        for _, _, ph, key in self.phrases:   # dài nhất trước
            n = len(ph)
            for i in range(len(toks) - n + 1):
                if tuple(toks[i:i + n]) == ph:
                    return ("seed", key)
        return ("raw", f)


@dataclass
class AmenityVocab:
    ids: dict[str, int] = field(default_factory=dict)          # key ("pool" | "raw:<slug>") → id
    entries: dict[int, dict] = field(default_factory=dict)      # id → {key, label, source, freq}
    dropped_distinct: int = 0
    dropped_occurrences: int = 0

    def to_json(self) -> dict[str, dict]:
        return {str(i): e for i, e in sorted(self.entries.items())}


def build_vocab(unit_raw_lists: list[list[str]], matcher: AmenityMatcher, min_freq: int) -> tuple[AmenityVocab, list[list[int]]]:
    """unit_raw_lists: mỗi search unit một danh sách chuỗi amenity gốc (đã hợp phòng con nếu scope yêu cầu).

    Trả vocab và amenity_ids (đã sắp, không trùng) cho từng unit.
    """
    unit_keys: list[set[str]] = []
    raw_freq: Counter[str] = Counter()     # folded raw → số unit chứa nó
    raw_label: dict[str, Counter[str]] = {}
    seed_freq: Counter[str] = Counter()
    for raws in unit_raw_lists:
        keys: set[str] = set()
        raws_seen: set[str] = set()
        for r in raws:
            if not isinstance(r, str):
                continue
            kind, val = matcher.match(r)
            if kind == "seed":
                keys.add(val)
            elif val:
                raws_seen.add(val)
                raw_label.setdefault(val, Counter())[r.strip()] += 1
        for k in keys:
            seed_freq[k] += 1
        for v in raws_seen:
            raw_freq[v] += 1
            keys.add("raw:" + v)
        unit_keys.append(keys)

    vocab = AmenityVocab()
    next_id = 1
    for s in sorted(matcher.seed, key=lambda x: x.key):
        vocab.ids[s.key] = next_id
        vocab.entries[next_id] = {"key": s.key, "label": s.label, "source": "seed", "freq": int(seed_freq.get(s.key, 0))}
        next_id += 1
    kept = sorted(((f, v) for v, f in raw_freq.items() if f >= min_freq), key=lambda x: (-x[0], x[1]))
    for f, v in kept:
        if next_id > INT16_MAX:
            raise ValueError("vượt giới hạn int16 cho amenity_ids")
        key = "raw:" + slug(v)
        vocab.ids["raw:" + v] = next_id
        label = raw_label[v].most_common(1)[0][0]
        vocab.entries[next_id] = {"key": key, "label": label, "source": "raw", "freq": int(f)}
        next_id += 1
    dropped = [(v, f) for v, f in raw_freq.items() if f < min_freq]
    vocab.dropped_distinct = len(dropped)
    vocab.dropped_occurrences = int(sum(f for _, f in dropped))

    ids_per_unit = [sorted({vocab.ids[k] for k in keys if k in vocab.ids}) for keys in unit_keys]
    return vocab, ids_per_unit
