"""Part 4 — ground truth brute-force: top-K cosine fp32 trên đúng TẬP CHẶT của filter (mask & ~vùng biên).

Chạy theo khối `chunk_rows` dòng: ma trận điểm Q × chunk bằng một phép matmul → áp mask của khối → gộp top-K bằng argpartition.
vectors.npy mở mmap. Cosine luôn chia norm (vector fp16 có norm lệch 1 một chút — Phụ lục B 11).
gt.npz: rows (Q×K int32, −1 = trống) · scores (Q×K float32, NaN = trống) · n_match (tập chặt) · n_boundary · k.
Facet GT: bỏ ở fast-track (spec-fasttrack §4 Part 4).
"""
from __future__ import annotations

import json
import logging
import time

import numpy as np

from . import paths
from .config import VBenchConfig
from .filters import Table, strict_mask
from .results import dump_json, sha256_file

log = logging.getLogger("vbench.gt")

Q_BLOCK = 256   # số query mỗi lần matmul — giữ ma trận điểm ≤ ~100 MB ở chunk 100k


def normalize_rows(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=np.float32)
    n = np.linalg.norm(x, axis=1, keepdims=True)
    n[n == 0] = 1.0
    return x / n


class PackedMasks:
    """Mask bool N của từng query lưu dạng packbits (ở 1M: 125 KB/query thay vì 1 MB). None = không lọc."""

    def __init__(self, masks: list[np.ndarray | None]):
        self.packed = [None if m is None else np.packbits(m) for m in masks]

    def __len__(self) -> int:
        return len(self.packed)

    def __getitem__(self, j: int):
        return self.packed[j]

    def slice(self, j: int, a: int, b: int) -> np.ndarray | None:
        p = self.packed[j]
        if p is None:
            return None
        assert a % 8 == 0, "chunk_rows phải chia hết cho 8"
        return np.unpackbits(p[a // 8:(b + 7) // 8], count=b - a).astype(bool)

    def full(self, j: int, n: int) -> np.ndarray | None:
        return self.slice(j, 0, n)


def topk_exact(vectors: np.ndarray, queries: np.ndarray, k: int, chunk_rows: int,
               masks: "list[np.ndarray | None] | PackedMasks | None" = None) -> tuple[np.ndarray, np.ndarray]:
    """Top-k cosine chính xác. masks[i] = mảng bool N hoặc PackedMasks (None = không lọc). Trả (rows int32 −1, scores float32 NaN)."""
    n = vectors.shape[0]
    packed = isinstance(masks, PackedMasks)
    qn = normalize_rows(queries)
    Q = qn.shape[0]
    best_s = np.full((Q, k), -np.inf, dtype=np.float32)
    best_r = np.full((Q, k), -1, dtype=np.int64)
    for a in range(0, n, chunk_rows):
        b = min(a + chunk_rows, n)
        v = normalize_rows(vectors[a:b])
        for qa in range(0, Q, Q_BLOCK):
            qb = min(qa + Q_BLOCK, Q)
            s = qn[qa:qb] @ v.T                                    # (block × chunk)
            if masks is not None:
                for j in range(qa, qb):
                    m = masks.slice(j, a, b) if packed else (None if masks[j] is None else masks[j][a:b])
                    if m is not None:
                        s[j - qa, ~m] = -np.inf
            kk = min(k, b - a)
            idx = np.argpartition(-s, kk - 1, axis=1)[:, :kk]
            cs = np.take_along_axis(s, idx, axis=1)
            cr = idx.astype(np.int64) + a
            all_s = np.concatenate([best_s[qa:qb], cs], axis=1)
            all_r = np.concatenate([best_r[qa:qb], cr], axis=1)
            # sắp: điểm giảm dần, hoà thì row tăng dần (tất định)
            order = np.lexsort((np.where(all_r < 0, np.iinfo(np.int64).max, all_r), -all_s), axis=1)[:, :k]
            best_s[qa:qb] = np.take_along_axis(all_s, order, axis=1)
            best_r[qa:qb] = np.take_along_axis(all_r, order, axis=1)
    empty = ~np.isfinite(best_s)
    rows = np.where(empty, -1, best_r).astype(np.int32)
    scores = np.where(empty, np.nan, best_s).astype(np.float32)
    return rows, scores


def naive_topk(vectors: np.ndarray, q: np.ndarray, k: int, m: np.ndarray | None) -> tuple[np.ndarray, np.ndarray]:
    """Cách ngây thơ để tự kiểm tra: điểm của MỌI dòng thoả mask rồi sắp xếp đầy đủ (không argpartition, không gộp theo khối).

    Tính theo lát 50k dòng chỉ để giới hạn bộ nhớ ở 1M; không có bước gộp top-k nào.
    """
    qn = normalize_rows(q[None, :])[0]
    cand = np.flatnonzero(m) if m is not None else np.arange(vectors.shape[0])
    parts = []
    for a in range(0, len(cand), 50_000):
        rows = cand[a:a + 50_000]
        v = np.asarray(vectors[rows], dtype=np.float32)
        parts.append((v @ qn) / np.linalg.norm(v, axis=1))
    sc = np.concatenate(parts).astype(np.float32) if parts else np.empty(0, np.float32)
    order = np.lexsort((cand, -sc))[:k]
    rows = np.full(k, -1, dtype=np.int32)
    scores = np.full(k, np.nan, dtype=np.float32)
    rows[:len(order)] = cand[order]
    scores[:len(order)] = sc[order]
    return rows, scores


def _same_topk(r1, s1, r2, s2, eps: float = 1e-5) -> bool:
    """So hai top-k cho phép hoán vị trong nhóm điểm hoà."""
    ok1, ok2 = r1 >= 0, r2 >= 0
    if ok1.sum() != ok2.sum():
        return False
    if not np.allclose(s1[ok1], s2[ok2], atol=eps):
        return False
    if len(s1[ok1]) == 0:
        return True
    last = s1[ok1][-1]
    strict = s1[ok1] > last + eps                     # phần chắc chắn (trên nhóm hoà cuối cùng)
    return set(r1[ok1][strict].tolist()) == set(r2[ok2][s2[ok2] > last + eps].tolist())


def compute_gt(cfg: VBenchConfig, scale: str) -> dict:
    g = cfg.groundtruth
    d = paths.data_dir(scale, create=False)
    t0 = time.perf_counter()
    table = Table.from_parquet(d / paths.ITEMS, with_ids=False)
    vectors = np.load(d / paths.VECTORS, mmap_mode="r")
    qv = np.load(d / paths.QUERY_VECTORS)
    queries = [json.loads(line) for line in open(d / paths.QUERIES, encoding="utf-8") if line.strip()]
    if len(queries) != qv.shape[0]:
        raise ValueError(f"queries.jsonl ({len(queries)}) ≠ query_vectors.npy ({qv.shape[0]})")
    if vectors.shape[0] != table.n:
        raise ValueError(f"vectors.npy ({vectors.shape[0]}) ≠ items.parquet ({table.n})")

    raw_masks: list[np.ndarray | None] = []
    n_match = np.zeros(len(queries), dtype=np.int64)
    n_boundary = np.zeros(len(queries), dtype=np.int64)
    for i, q in enumerate(queries):
        f = q["filter"]
        if f is None:
            raw_masks.append(None)
            n_match[i] = table.n
            continue
        m, bnd = strict_mask(f, table, g.geo_boundary_tol)
        strict = m & ~bnd
        raw_masks.append(strict)
        n_match[i] = int(strict.sum())
        n_boundary[i] = int(bnd.sum())
        if len(raw_masks) % 64 == 0:        # nén dần để bộ nhớ không phình ở 1M
            raw_masks[-64:] = [None if x is None else np.packbits(x) for x in raw_masks[-64:]]
    masks = PackedMasks([None] * len(raw_masks))
    masks.packed = [None if x is None else (x if x.dtype == np.uint8 else np.packbits(x)) for x in raw_masks]
    del raw_masks
    t_mask = time.perf_counter() - t0

    rows, scores = topk_exact(vectors, qv, g.k, g.chunk_rows, masks)
    t_topk = time.perf_counter() - t0 - t_mask
    out = d / paths.GT
    np.savez(out, rows=rows, scores=scores, n_match=n_match, n_boundary=n_boundary, k=np.int32(g.k))

    # -- tự kiểm tra 1: 50 item làm query, không filter → top-1 là chính nó, điểm ≥ ngưỡng (cho phép hoà với bản trùng)
    rng = np.random.default_rng(cfg.run.seed + 4000)
    pick = rng.choice(table.n, size=min(g.self_check_items, table.n), replace=False)
    r1, s1 = topk_exact(vectors, np.asarray(vectors[np.sort(pick)]), 2, g.chunk_rows, None)
    self_ok = 0
    for j, item in enumerate(np.sort(pick)):
        own = r1[j, 0] == item or (s1[j, 0] - s1[j, 1] < 1e-6 and r1[j, 1] == item)
        if own and s1[j, 0] >= g.self_check_min_score:
            self_ok += 1
    check1 = self_ok == len(pick)

    # -- tự kiểm tra 2: 20 query ngẫu nhiên tính lại bằng vòng lặp ngây thơ → trùng kết quả chạy theo khối
    naive_pick = rng.choice(len(queries), size=min(g.self_check_naive, len(queries)), replace=False)
    naive_ok = 0
    for i in naive_pick:
        nr, ns = naive_topk(vectors, qv[i], g.k, masks.full(int(i), table.n))
        if _same_topk(rows[i], scores[i], nr, ns):
            naive_ok += 1
    check2 = naive_ok == len(naive_pick)
    secs = time.perf_counter() - t0
    meta = {"scale": scale, "n": table.n, "q": len(queries), "k": g.k, "chunk_rows": g.chunk_rows,
            "seconds": round(secs, 2), "seconds_masks": round(t_mask, 2), "seconds_topk": round(t_topk, 2),
            "self_check_top1_self": {"pass": check1, "ok": self_ok, "n": len(pick)},
            "self_check_naive": {"pass": check2, "ok": naive_ok, "n": len(naive_pick)},
            "empty_queries": int((n_match == 0).sum()), "gt_sha256": sha256_file(out)}
    dump_json(d / "gt_meta.json", meta)
    log.info("GT %s: %d query × %d dòng, %.1fs (mask %.1fs, top-k %.1fs)", scale, len(queries), table.n, secs, t_mask, t_topk)
    print(f"gt.npz: Q={len(queries)} K={g.k} N={table.n} · {secs:.1f}s · top-1 là chính nó {self_ok}/{len(pick)} · "
          f"ngây thơ trùng {naive_ok}/{len(naive_pick)}")
    return meta


def load_gt(scale: str) -> dict[str, np.ndarray]:
    z = np.load(paths.data_dir(scale, create=False) / paths.GT)
    return {k: z[k] for k in z.files}


def run_gt(cfg: VBenchConfig, *, scale: str) -> int:
    meta = compute_gt(cfg, scale)
    ok = meta["self_check_top1_self"]["pass"] and meta["self_check_naive"]["pass"]
    return 0 if ok else 2
