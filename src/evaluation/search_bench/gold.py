"""Part 5 (phần Người B chạy ngày 2) — `sb gold pool` và `sb gold split`.

- `drafts.txt`: mỗi dòng `query \\t slice [\\t filter_json] [\\t expected_no_result]`; dòng trống / bắt đầu `#` bỏ qua;
  qid `q001…` theo thứ tự dòng. Slice phải thuộc `gold.slices`; filter kiểm và đổi khoá amenity → id (`store/filters.py`).
- `pool`: với mỗi draft, dense top-`depth` (collection của B0, embed query theo arm) ∪ BM25 top-`depth`, cùng filter →
  `pool.csv` đúng cột spec, **xáo thứ tự trong mỗi qid** (seed cố định) để người gán không thấy rank.
- `split`: 25 qid chung chọn stratified theo slice; phần còn lại qid lẻ → `pool_A.csv`, chẵn → `pool_B.csv`.
`kappa`, `merge`, `import`, `check` thuộc ngày 3–4 (Người A) — chưa cài ở đây.
"""
from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .store import filters as F

POOL_COLUMNS = ["qid", "query", "slice", "product_id", "name", "variant", "destination", "from", "rank_dense", "rank_lex", "label"]
CSV_ENCODING = "utf-8-sig"      # Excel mở đúng tiếng Việt


class GoldError(ValueError):
    pass


@dataclass
class Draft:
    qid: str
    query: str
    slice: str
    filter: dict | None           # AST đã resolve (id amenity)
    filter_raw: str
    expected_no_result: bool
    line: int


def parse_drafts(path: Path, slices: list[str], key_to_id: dict[str, int]) -> list[Draft]:
    if not path.exists():
        raise GoldError(f"không thấy {path} — drafts.txt do Người A soạn (checklist ngày 1)")
    out: list[Draft] = []
    for lineno, raw in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        parts = raw.split("\t")
        if not 2 <= len(parts) <= 4:
            raise GoldError(f"{path.name}:{lineno}: cần 2–4 cột phân cách bằng TAB, gặp {len(parts)}")
        query, sl = parts[0].strip(), parts[1].strip()
        if not query:
            raise GoldError(f"{path.name}:{lineno}: query rỗng")
        if sl not in slices:
            raise GoldError(f"{path.name}:{lineno}: slice lạ {sl!r} (có: {', '.join(slices)})")
        fraw = parts[2].strip() if len(parts) > 2 else ""
        try:
            flt = F.parse(fraw)
            flt = F.resolve(flt, key_to_id) if flt else None
        except F.FilterError as e:
            raise GoldError(f"{path.name}:{lineno}: {e}") from None
        eno_raw = parts[3].strip().lower() if len(parts) > 3 else ""
        if eno_raw not in ("", "true", "false"):
            raise GoldError(f"{path.name}:{lineno}: expected_no_result phải là true/false, gặp {parts[3]!r}")
        out.append(Draft(qid=f"q{len(out) + 1:03d}", query=query, slice=sl, filter=flt, filter_raw=fraw,
                         expected_no_result=eno_raw == "true", line=lineno))
    if not out:
        raise GoldError(f"{path.name}: không có draft nào")
    dup = [q for q, n in Counter((d.query.lower(), d.slice) for d in out).items() if n > 1]
    if dup:
        raise GoldError(f"{path.name}: draft trùng (query, slice): {dup[:3]}")
    return out


def _qnum(qid: str) -> int:
    return int(qid.lstrip("q"))


def pool_rows(draft: Draft, dense: list, lexical: list, seed: int) -> list[dict]:
    """Hợp dense ∪ BM25 cho một draft, ghi rank ở từng kênh, xáo thứ tự dòng (seed cố định theo qid)."""
    rows: dict[str, dict] = {}
    for kind, hits in (("dense", dense), ("lexical", lexical)):
        for h in hits:
            r = rows.setdefault(h.product_id, {"qid": draft.qid, "query": draft.query, "slice": draft.slice,
                                               "product_id": h.product_id, "name": h.name, "variant": h.variant,
                                               "destination": h.destination, "rank_dense": None, "rank_lex": None, "label": ""})
            r["rank_dense" if kind == "dense" else "rank_lex"] = h.rank
    for r in rows.values():
        r["from"] = "both" if r["rank_dense"] and r["rank_lex"] else ("dense" if r["rank_dense"] else "lexical")
    ordered = sorted(rows.values(), key=lambda r: r["product_id"])
    perm = np.random.default_rng([seed, _qnum(draft.qid)]).permutation(len(ordered))
    return [ordered[i] for i in perm]


def build_pool(drafts: list[Draft], *, store: Any, embedder: Any, physical: str, fold_mode: str, depth: int,
               query_input_type: str, seed: int) -> pd.DataFrame:
    qvecs = embedder.embed([d.query for d in drafts], query_input_type)       # một lượt gom, qua cache
    rows: list[dict] = []
    for d, qv in zip(drafts, qvecs):
        flt = F.to_weaviate(d.filter)
        dense = store.dense(physical, qv, depth, filters=flt)
        lexical = store.bm25(physical, d.query, depth, fold_mode=fold_mode, filters=flt)
        rows += pool_rows(d, dense, lexical, seed)
    df = pd.DataFrame(rows, columns=POOL_COLUMNS)
    for c in ("rank_dense", "rank_lex"):
        df[c] = df[c].astype("Int64")
    return df


def pool_summary(drafts: list[Draft], df: pd.DataFrame) -> dict:
    per_q = df.groupby("qid").size() if len(df) else pd.Series(dtype=int)
    empty = [d.qid for d in drafts if d.qid not in per_q.index]
    return {"n_queries": len(drafts), "n_rows": int(len(df)),
            "docs_per_query": {"p50": float(per_q.median()) if len(per_q) else 0.0, "max": int(per_q.max()) if len(per_q) else 0},
            "from": dict(Counter(df["from"])), "empty_queries": empty,
            "by_slice": dict(Counter(d.slice for d in drafts))}


def write_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding=CSV_ENCODING)


def read_pool(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise GoldError(f"không thấy {path} — chạy `sb gold pool` trước")
    df = pd.read_csv(path, encoding=CSV_ENCODING, dtype={"qid": str, "product_id": str, "label": str}, keep_default_na=False)
    missing = [c for c in POOL_COLUMNS if c not in df.columns]
    if missing:
        raise GoldError(f"{path.name} thiếu cột {missing}")
    return df


def overlap_quota(slice_counts: dict[str, int], overlap: int) -> dict[str, int]:
    """Chia `overlap` theo tỷ lệ slice (largest remainder; hoà → tên slice), không vượt số query của slice."""
    total = sum(slice_counts.values())
    raw = {s: overlap * n / total for s, n in slice_counts.items()}
    quota = {s: min(int(np.floor(v)), slice_counts[s]) for s, v in raw.items()}
    rest = overlap - sum(quota.values())
    for s in sorted(raw, key=lambda s: (-(raw[s] - np.floor(raw[s])), s)):
        if rest <= 0:
            break
        if quota[s] < slice_counts[s]:
            quota[s] += 1
            rest -= 1
    for s in sorted(slice_counts):              # còn dư (slice nhỏ đã đầy) → dồn sang slice còn chỗ
        while rest > 0 and quota[s] < slice_counts[s]:
            quota[s] += 1
            rest -= 1
    return quota


def split_pool(df: pd.DataFrame, overlap: int, seed: int) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    q = df.drop_duplicates("qid")[["qid", "slice"]]
    n = len(q)
    if not 0 <= overlap < n:
        raise GoldError(f"overlap {overlap} phải trong [0, {n}) (số query của pool)")
    by_slice = {s: sorted(g["qid"], key=_qnum) for s, g in q.groupby("slice")}
    quota = overlap_quota({s: len(v) for s, v in by_slice.items()}, overlap)
    rng = np.random.default_rng(seed)
    shared: list[str] = []
    for s in sorted(by_slice):
        if quota[s]:
            shared += [str(x) for x in rng.choice(by_slice[s], size=quota[s], replace=False)]
    shared_set = set(shared)
    rest = [x for x in q["qid"] if x not in shared_set]
    a = shared_set | {x for x in rest if _qnum(x) % 2 == 1}
    b = shared_set | {x for x in rest if _qnum(x) % 2 == 0}
    return df[df["qid"].isin(a)].copy(), df[df["qid"].isin(b)].copy(), sorted(shared, key=_qnum)


def load_key_index(amenity_vocab_path: Path) -> dict[str, int]:
    if not amenity_vocab_path.exists():
        raise GoldError(f"chưa có {amenity_vocab_path} — chạy `sb catalog build` trước")
    return F.amenity_key_index(json.loads(amenity_vocab_path.read_text(encoding="utf-8")))
