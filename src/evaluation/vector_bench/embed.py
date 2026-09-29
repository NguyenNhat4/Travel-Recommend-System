"""Part 2 — embedding + cache. Ma trận vector chuẩn dùng chung cho mọi engine.

--target items   : passage_prefix + embed_text theo thứ tự row → L2-normalize fp32 → float16 → vectors.npy (N × D).
                   Chạy lại chỉ embed dòng có text_hash mới (cùng model/backend/dim/prefix/normalize/max_seq_length).
--target queries : query_prefix + text của queries.jsonl → query_vectors.npy (chỉ scale catalog; scale lớn lấy từ Part 10).
--backend fake   : không cần model — tâm cụm theo destination và variant; KHÔNG dùng recall từ vector fake để kết luận.
"""
from __future__ import annotations

import hashlib
import importlib.metadata as md
import json
import logging
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from . import paths
from .config import VBenchConfig
from .results import dump_json, sha256_file

log = logging.getLogger("vbench.embed")

FAKE_W_VARIANT = 0.7   # spec Part 2: v = normalize(c_dest + 0.7·c_variant + 0.6·ε)
FAKE_W_NOISE = 0.6
FAKE_Q_NOISE = 0.8     # query fake: normalize(v_item + 0.8·ε)


def l2_normalize(x: np.ndarray) -> np.ndarray:
    x = x.astype(np.float32, copy=False)
    n = np.linalg.norm(x, axis=1, keepdims=True)
    n[n == 0] = 1.0
    return x / n


def to_fp16_normalized(x: np.ndarray) -> np.ndarray:
    return l2_normalize(x).astype(np.float16)


def _seed_of(s: str, base: int) -> int:
    return (int.from_bytes(hashlib.sha256(s.encode("utf-8")).digest()[:8], "little") ^ base) & (2**63 - 1)


def _centers(keys: list[str], dim: int, seed: int, salt: str) -> dict[str, np.ndarray]:
    out = {}
    for k in sorted(set(keys)):
        rng = np.random.default_rng(_seed_of(f"{salt}:{k}", seed))
        out[k] = l2_normalize(rng.normal(size=(1, dim)))[0]
    return out


def fake_item_vectors(ids: list[str], dests: list[str], variants: list[str], dim: int, seed: int) -> np.ndarray:
    cd, cv = _centers(dests, dim, seed, "dest"), _centers(variants, dim, seed, "variant")
    out = np.empty((len(ids), dim), dtype=np.float32)
    for i, (pid, d, v) in enumerate(zip(ids, dests, variants)):
        eps = np.random.default_rng(_seed_of(pid, seed)).normal(size=dim) / np.sqrt(dim)   # ‖ε‖ ≈ 1, như tâm cụm
        out[i] = cd[d] + FAKE_W_VARIANT * cv[v] + FAKE_W_NOISE * eps
    return to_fp16_normalized(out)


def fake_query_vectors(qids: list[str], item_vectors: np.ndarray, seed: int) -> np.ndarray:
    dim = item_vectors.shape[1]
    out = np.empty((len(qids), dim), dtype=np.float32)
    for i, q in enumerate(qids):
        rng = np.random.default_rng(_seed_of("q:" + q, seed))
        j = int(rng.integers(item_vectors.shape[0]))
        eps = rng.normal(size=dim) / np.sqrt(dim)
        out[i] = item_vectors[j].astype(np.float32) + FAKE_Q_NOISE * eps
    return to_fp16_normalized(out)


class _STEncoder:
    def __init__(self, cfg: VBenchConfig):
        from sentence_transformers import SentenceTransformer
        ec = cfg.embedding
        self.model = SentenceTransformer(ec.model, device=ec.device)
        self.model.max_seq_length = ec.max_seq_length
        self.batch = ec.batch_size
        self.revision = None
        try:
            cfgd = getattr(self.model[0].auto_model, "config", None)
            self.revision = getattr(cfgd, "_commit_hash", None)
        except Exception:  # noqa: BLE001
            pass

    def encode(self, texts: list[str]) -> np.ndarray:
        v = self.model.encode(texts, batch_size=self.batch, normalize_embeddings=False, convert_to_numpy=True,
                              show_progress_bar=len(texts) > 200)
        return np.asarray(v, dtype=np.float32)


def _meta_key(cfg: VBenchConfig, backend: str, prefix: str) -> dict[str, Any]:
    ec = cfg.embedding
    return {"model": ec.model if backend == "st" else "fake", "backend": backend, "dim": ec.dim, "normalize": ec.normalize,
            "max_seq_length": ec.max_seq_length, "prefix": prefix}


def _versions() -> dict[str, str | None]:
    out = {}
    for d in ("sentence-transformers", "torch"):
        try:
            out[d] = md.version(d)
        except md.PackageNotFoundError:
            out[d] = None
    return out


def embed_items(cfg: VBenchConfig, scale: str, backend: str) -> dict:
    d = paths.data_dir(scale)
    items = pd.read_parquet(d / paths.ITEMS, columns=["row", "id", "variant", "destination", "embed_text", "text_hash"])
    items = items.sort_values("row")
    ec = cfg.embedding
    prefix = ec.passage_prefix
    key = _meta_key(cfg, backend, prefix)
    hashes = items["text_hash"].tolist()
    n, dim = len(items), ec.dim

    # cache tăng dần: cùng model/backend/dim/prefix… và cùng hash → dùng lại vector cũ
    old: dict[str, np.ndarray] = {}
    meta_p, vec_p, hash_p = d / paths.EMBED_META, d / paths.VECTORS, d / paths.EMBED_HASHES
    if meta_p.exists() and vec_p.exists() and hash_p.exists():
        m = json.loads(meta_p.read_text(encoding="utf-8"))
        if all(m.get(k) == v for k, v in key.items()):
            ov = np.load(vec_p)
            oh = json.loads(hash_p.read_text(encoding="utf-8"))
            if len(oh) == ov.shape[0]:
                old = {h: ov[i] for i, h in enumerate(oh)}
    todo = [i for i, h in enumerate(hashes) if h not in old]
    t0 = time.perf_counter()
    out = np.empty((n, dim), dtype=np.float16)
    for i, h in enumerate(hashes):
        if h in old:
            out[i] = old[h]
    revision = None
    if todo:
        if backend == "fake":
            sub = items.iloc[todo]
            out[todo] = fake_item_vectors(sub["id"].tolist(), sub["destination"].tolist(), sub["variant"].tolist(), dim, cfg.run.seed)
        else:
            enc = _STEncoder(cfg)
            revision = enc.revision
            texts = [prefix + t for t in items["embed_text"].iloc[todo].tolist()]
            v = enc.encode(texts)
            if v.shape[1] != dim:
                raise ValueError(f"model trả {v.shape[1]} chiều, config embedding.dim = {dim}")
            out[todo] = to_fp16_normalized(v) if ec.normalize else v.astype(np.float16)
    secs = time.perf_counter() - t0
    np.save(vec_p, out)
    hash_p.write_text(json.dumps(hashes), encoding="utf-8")
    norms = np.linalg.norm(out.astype(np.float32), axis=1)
    meta = {**key, "revision": revision, "device": ec.device, "n": n, "seconds": round(secs, 2),
            "items_per_s": round(len(todo) / secs, 1) if todo and secs > 0 else None, "re_embedded": len(todo),
            "reused": n - len(todo), **_versions(), "vectors_sha256": sha256_file(vec_p),
            "norm_min": float(norms.min()), "norm_max": float(norms.max())}
    dump_json(meta_p, meta)
    log.info("embed items %s: shape=%s re-embedded: %d, reused: %d, %.1fs, norm ∈ [%.4f, %.4f]",
             scale, out.shape, len(todo), n - len(todo), secs, norms.min(), norms.max())
    print(f"vectors.npy shape={out.shape} · re-embedded: {len(todo)} · reused: {n - len(todo)} · {secs:.1f}s · "
          f"norm ∈ [{norms.min():.4f}, {norms.max():.4f}]")
    return meta


def embed_queries(cfg: VBenchConfig, scale: str, backend: str) -> dict:
    if scale != "catalog":
        raise ValueError("--target queries chỉ dùng cho scale catalog; scale lớn lấy query vector từ Part 10")
    d = paths.data_dir(scale)
    qs = [json.loads(line) for line in open(d / paths.QUERIES, encoding="utf-8")]
    ec = cfg.embedding
    t0 = time.perf_counter()
    if backend == "fake":
        items_v = np.load(d / paths.VECTORS, mmap_mode="r")
        out = fake_query_vectors([q["qid"] for q in qs], np.asarray(items_v), cfg.run.seed)
    else:
        enc = _STEncoder(cfg)
        v = enc.encode([ec.query_prefix + q["text"] for q in qs])
        out = to_fp16_normalized(v) if ec.normalize else v.astype(np.float16)
    secs = time.perf_counter() - t0
    p = d / paths.QUERY_VECTORS
    np.save(p, out)
    norms = np.linalg.norm(out.astype(np.float32), axis=1)
    meta = {**_meta_key(cfg, backend, ec.query_prefix), "n": len(qs), "seconds": round(secs, 2),
            "query_vectors_sha256": sha256_file(p), "queries_sha256": sha256_file(d / paths.QUERIES), **_versions(),
            "norm_min": float(norms.min()), "norm_max": float(norms.max())}
    dump_json(d / paths.QUERY_EMBED_META, meta)
    print(f"query_vectors.npy shape={out.shape} · {secs:.1f}s · norm ∈ [{norms.min():.4f}, {norms.max():.4f}]")
    return meta


def run_embed(cfg: VBenchConfig, *, scale: str, target: str, backend: str | None) -> int:
    backend = backend or cfg.embedding.backend
    if target == "items":
        meta = embed_items(cfg, scale, backend)
        bad = not (abs(meta["norm_min"] - 1) <= 0.01 and abs(meta["norm_max"] - 1) <= 0.01)
    elif target == "queries":
        meta = embed_queries(cfg, scale, backend)
        bad = not (abs(meta["norm_min"] - 1) <= 0.01 and abs(meta["norm_max"] - 1) <= 0.01)
    else:
        raise ValueError(f"target không hợp lệ: {target}")
    if bad:
        log.error("norm sau fp16 lệch quá 1 ± 0,01")
        return 1
    return 0
