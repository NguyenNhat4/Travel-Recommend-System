"""Part 12.2 — kiểm tra cứng của pipeline, chạy rời bằng `sb sanity` (máy trạng thái cổng đầy đủ làm sau).

Hỏng một kiểm tra cứng → mọi số sau đó vô nghĩa (spec 12.2):
- `input_type_vectors_differ`: embed câu gold hai lần (`query` và `document`) bằng model của arm; trung bình `1 − cos`
  phải > `stages.pipeline_checks.input_type_min_cos_gap` — không thì `input_type` không tới API / prefix không được ghép.
- `cache_recheck`: embed lại `cache_recheck_n` text ngẫu nhiên **không qua cache**; cos với vector trong cache ≥ 0,999 —
  không thì cache trả vector cũ / sai model.
- `collection_counts`: mọi collection dùng có `count == n_items`.
- `gold_append_ok`: `verify-append` từ `gold_v1` tới gold hiện tại (chưa có tag thì bỏ qua, báo).
Số câu cho `input_type_vectors_differ` = min(`n_queries`, số câu active) — gold hiện có 131 câu, spec ghi 200.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

COS_MIN_RECHECK = 0.999


@dataclass
class Check:
    name: str
    ok: bool | None            # None = bỏ qua (không có dữ liệu để kiểm)
    detail: str
    model: str | None = None


def input_type_vectors_differ(embedder: Any, texts: list[str], *, min_gap: float, model: str) -> Check:
    if not texts:
        return Check("input_type_vectors_differ", None, "không có câu", model)
    q = np.asarray(embedder.embed(list(texts), "query"), dtype=np.float32)
    d = np.asarray(embedder.embed(list(texts), "document"), dtype=np.float32)
    gap = float(np.mean(1.0 - np.sum(q * d, axis=1)))
    return Check("input_type_vectors_differ", gap > min_gap,
                 f"mean(1 − cos(query, document)) = {gap:.4f} trên {len(texts)} câu (cần > {min_gap})", model)


def cache_recheck(cached: Any, fresh: Any, texts: list[str], *, n: int, seed: int, model: str,
                  input_type: str = "query") -> Check:
    """`cached` = embedder qua cache, `fresh` = cùng model nhưng `no_cache=True`."""
    if not texts:
        return Check("cache_recheck", None, "không có text", model)
    sample = random.Random(seed).sample(list(texts), min(n, len(texts)))
    a = np.asarray(cached.embed(sample, input_type), dtype=np.float32)
    b = np.asarray(fresh.embed(sample, input_type), dtype=np.float32)
    cos = np.sum(a * b, axis=1) / (np.linalg.norm(a, axis=1) * np.linalg.norm(b, axis=1) + 1e-12)
    worst = float(cos.min())
    return Check("cache_recheck", worst >= COS_MIN_RECHECK,
                 f"cos(cache, embed lại) min = {worst:.6f} trên {len(sample)} text (cần ≥ {COS_MIN_RECHECK})", model)


def collection_counts(counts: dict[str, int], n_items: int) -> Check:
    bad = {c: n for c, n in counts.items() if n != n_items}
    detail = ", ".join(f"{c}={n}" for c, n in counts.items()) + f" (cần {n_items})"
    return Check("collection_counts", not bad, detail)


def gold_append_ok(gold_path: Path) -> Check:
    from .gold_schema import read_gold_jsonl
    from .holes import gold_at, list_gold_tags, verify_append
    tags = list_gold_tags()
    if not tags:
        return Check("gold_append_ok", None, "chưa có tag gold_v* — bỏ qua")
    problems = verify_append(gold_at(tags[0]), read_gold_jsonl(gold_path))
    return Check("gold_append_ok", not problems,
                 f"{tags[0]} → {gold_path.name}: " + ("chỉ thêm" if not problems else f"{len(problems)} vi phạm, vd {problems[0]}"))


def summary(checks: list[Check]) -> tuple[str, list[Check]]:
    """`SANITY_FAIL` nếu có kiểm tra cứng hỏng, không thì `PASS`; kèm danh sách hỏng."""
    failed = [c for c in checks if c.ok is False]
    return ("SANITY_FAIL" if failed else "PASS"), failed
