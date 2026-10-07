"""Nạp catalog, vector và event cho harness qua đúng adapter của backend — không SQL thẳng vào `cdp.*` (AGENTS.md §6.1).

Hai connection như backend: catalog qua `DATABASE_URL` (role `vota_app`, đọc được `catalog.product_meta`), event qua
`EVAL_DATABASE_URL` (role `cdp_eval_login` thuộc `cdp_reader`, chỉ đọc; `.env.example`). Thiếu `EVAL_DATABASE_URL` thì
lùi về `CDP_DATABASE_URL` và cảnh báo. psycopg/weaviate chỉ import trong hàm để test chạy không cần DB.

Chế độ vector:
- `none` — chỉ catalog (arm random không cần vector);
- `weaviate` — y hệt `main.build_recsys`: `WeaviateVectorStore(...).load()`, mỗi request truy vấn top-K (đúng production);
- `numpy` — kéo toàn bộ vector một lần qua REST (`WeaviateClient.fetch`), cache `.npz`, tra bằng `NumpyVectorSearch`
  (kNN chính xác, nhanh cho grid-search; lệch nhẹ so với HNSW).
- `npy:<prefix>` (05/10, plan `docs/plan/2026-10-05-bench-recsys-e5-small.md` 6.5) — vector document đã embed sẵn của search
  bench (`<prefix>.npy` + `.ids.json` + `.meta.json`, vd `bench_out/search/data/vec_T3+R_e5-small`), tra bằng
  `NumpyVectorSearch`. Không cần Weaviate, không bị khoá vào model của settings backend: `modelVersion` =
  `<cache_model>:<text_builder_version>` của file meta.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import datetime, time, timedelta, timezone

import numpy as np

from src.backend.app.application.ports import UnitIndex, VectorSearchPort

from .events import parse_ts
from .paths import cache_dir

logger = logging.getLogger("recsys_bench")

VECTOR_MODES = ("none", "weaviate", "numpy")
NPY_PREFIX = "npy:"
NORM_TOLERANCE = 1e-3


def settings():
    from src.backend.app.core.config import get_settings
    return get_settings()


def model_version(s) -> str:
    from src.backend.app.domain.catalog import TEXT_BUILDER_VERSION
    return f"{s.embed_model}:{TEXT_BUILDER_VERSION}"


def eval_cdp_url() -> str:
    url = os.environ.get("EVAL_DATABASE_URL")
    if url:
        return url
    logger.warning("EVAL_DATABASE_URL trống — dùng CDP_DATABASE_URL (role ghi); nên dùng role chỉ đọc cdp_eval_login")
    return settings().cdp_database_url


def dsn_label(dsn: str) -> str:
    """host:port/db của DSN, không kèm user/mật khẩu — để in và làm khoá cache."""
    from psycopg.conninfo import conninfo_to_dict
    info = conninfo_to_dict(dsn)
    return f"{info.get('host', '?')}:{info.get('port', '5432')}/{info.get('dbname', '?')}"


def load_index(mode: str = "none") -> tuple[UnitIndex, VectorSearchPort | None]:
    if mode.startswith(NPY_PREFIX):
        return _npy_index(mode[len(NPY_PREFIX):])
    if mode not in VECTOR_MODES:
        raise ValueError(f"--vectors phải là một trong {VECTOR_MODES} hoặc {NPY_PREFIX}<prefix>")
    s = settings()
    version = model_version(s)
    if mode == "weaviate":
        from src.backend.app.infrastructure.vectors.weaviate_store import (
            WeaviateVectorSearch, WeaviateVectorStore, connect_weaviate)
        search = WeaviateVectorSearch(
            connect_weaviate(s.weaviate_url, api_key=s.weaviate_api_key, grpc_port=s.weaviate_grpc_port,
                             timeout_seconds=s.weaviate_timeout_seconds),
            collection=s.vector_collection, dimension=s.embed_dimension)
        return WeaviateVectorStore(s.database_url, search, expected_model_version=version).load()
    from src.backend.app.infrastructure.vectors.postgres_store import PostgresCatalogReader
    index = PostgresCatalogReader(s.database_url).load().to_index(version)
    if mode == "none":
        return index, None
    return index, _numpy_vectors(index, s, version)


def _numpy_vectors(index: UnitIndex, s, version: str) -> VectorSearchPort:
    from src.backend.app.infrastructure.vectors.numpy_search import NumpyVectorSearch
    wanted = [p.product_id for p in index.units]
    key = hashlib.sha1((s.weaviate_url + version + "\n".join(wanted)).encode("utf-8")).hexdigest()[:12]
    path = cache_dir() / f"vectors-{key}.npz"
    if path.exists():
        data = np.load(path, allow_pickle=False)
        return NumpyVectorSearch(list(data["ids"]), data["E"])
    from src.backend.app.infrastructure.vectors.weaviate_store import WeaviateClient
    client = WeaviateClient(s.weaviate_url, collection=s.vector_collection, api_key=s.weaviate_api_key,
                            timeout_seconds=s.weaviate_timeout_seconds)
    try:
        metadata, vectors = client.fetch(include_vectors=True)
    finally:
        client.close()
    ids = [pid for pid in wanted if pid in vectors and metadata[pid].model_version == version and vectors[pid].size]
    if 2 * len(ids) < len(wanted):
        raise RuntimeError(f"Weaviate chỉ có {len(ids)}/{len(wanted)} vector model {version}; chạy index trước")
    E = np.stack([vectors[pid] for pid in ids]).astype(np.float32)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez(path, ids=np.array(ids), E=E)
    return NumpyVectorSearch(ids, E)


def read_npy_vectors(prefix: str) -> tuple[list[str], np.ndarray, dict]:
    """(ids, E, meta) của bộ `<prefix>.npy` / `.ids.json` / `.meta.json`; kiểm số dòng, số chiều, chuẩn hoá L2 và
    text builder (vector dựng bằng text khác production thì không đo được engine production)."""
    from src.backend.app.domain.catalog import TEXT_BUILDER_VERSION
    paths = {ext: f"{prefix}{ext}" for ext in (".npy", ".ids.json", ".meta.json")}
    missing = [p for p in paths.values() if not os.path.exists(p)]
    if missing:
        raise FileNotFoundError(f"thiếu file vector: {missing}")
    E = np.load(paths[".npy"], allow_pickle=False).astype(np.float32)
    with open(paths[".ids.json"], encoding="utf-8") as f:
        ids = json.load(f)
    with open(paths[".meta.json"], encoding="utf-8") as f:
        meta = json.load(f)
    if E.ndim != 2 or len(ids) != E.shape[0]:
        raise ValueError(f"{paths['.npy']}: {E.shape} không khớp {len(ids)} id")
    if len(set(ids)) != len(ids):
        raise ValueError(f"{paths['.ids.json']}: id trùng")
    if meta.get("dim") is not None and int(meta["dim"]) != E.shape[1]:
        raise ValueError(f"meta dim {meta['dim']} ≠ {E.shape[1]} chiều của ma trận")
    if meta.get("text_builder_version") != TEXT_BUILDER_VERSION:
        raise ValueError(f"vector dựng bằng text {meta.get('text_builder_version')!r}, backend đang là {TEXT_BUILDER_VERSION!r}")
    if not meta.get("cache_model"):
        raise ValueError(f"{paths['.meta.json']}: thiếu cache_model")
    norms = np.linalg.norm(E, axis=1)
    if not np.allclose(norms, 1.0, atol=NORM_TOLERANCE):
        raise ValueError(f"vector chưa chuẩn hoá L2 (norm {norms.min():.4f}..{norms.max():.4f})")
    return list(ids), E, meta


def _npy_index(prefix: str) -> tuple[UnitIndex, VectorSearchPort]:
    from src.backend.app.infrastructure.vectors.numpy_search import NumpyVectorSearch
    from src.backend.app.infrastructure.vectors.postgres_store import PostgresCatalogReader
    ids, E, meta = read_npy_vectors(prefix)
    version = f"{meta['cache_model']}:{meta['text_builder_version']}"
    index = PostgresCatalogReader(settings().database_url).load().to_index(version)
    pos = {pid: i for i, pid in enumerate(ids)}
    keep = [p.product_id for p in index.units if p.product_id in pos]
    if 2 * len(keep) < len(index.units):
        raise RuntimeError(f"{prefix}: chỉ {len(keep)}/{len(index.units)} search unit có vector — catalog khác bộ vector")
    if len(keep) < len(index.units):
        logger.warning("%s: %d search unit không có vector", prefix, len(index.units) - len(keep))
    search = NumpyVectorSearch(keep, E[[pos[pid] for pid in keep]])
    search.source = {"prefix": os.path.basename(prefix), "cacheModel": meta["cache_model"], "dim": int(E.shape[1]),
                     "itemsSha256": meta.get("items_sha256"), "textSha256": meta.get("text_sha256"),
                     "npySha256": _file_sha256(f"{prefix}.npy"), "nFile": len(ids), "nUsed": len(keep)}
    return index, search


def _file_sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _event_cache_key(url: str) -> str:
    return hashlib.sha1(dsn_label(url).encode("utf-8")).hexdigest()[:8]


def clear_event_cache() -> int:
    """Xoá mọi cache event **và profile** của DB đang trỏ tới (mọi as_of) — gọi sau khi seed lại. Trả số file đã xoá."""
    removed = 0
    key = _event_cache_key(eval_cdp_url())
    for pattern in (f"events-{key}-*.jsonl", f"profiles-{key}.jsonl"):
        for path in cache_dir().glob(pattern):
            path.unlink()
            removed += 1
    return removed


def load_events(as_of: datetime | None = None, *, refresh: bool = False) -> list[dict]:
    """Event qua `PostgresCdpReader.all_events(until=as_of)`, cache JSONL theo DB + as_of."""
    from src.backend.app.infrastructure.cdp.postgres_cdp_reader import PostgresCdpReader
    url = eval_cdp_url()
    stamp = as_of.strftime("%Y%m%dT%H%M%S") if as_of else "all"
    path = cache_dir() / f"events-{_event_cache_key(url)}-{stamp}.jsonl"
    if path.exists() and not refresh:
        with open(path, encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]
    events = PostgresCdpReader(url, timeout_seconds=30).all_events(until=as_of)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for e in events:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    return events


def load_profiles(*, refresh: bool = False) -> list[dict]:
    """`cdp.profiles` qua `PostgresCdpReader.all_profiles()` (01/10, chỉ cho sanity), cache JSONL theo DB."""
    from src.backend.app.infrastructure.cdp.postgres_cdp_reader import PostgresCdpReader
    url = eval_cdp_url()
    path = cache_dir() / f"profiles-{_event_cache_key(url)}.jsonl"
    if path.exists() and not refresh:
        with open(path, encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]
    profiles = PostgresCdpReader(url, timeout_seconds=30).all_profiles()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for p in profiles:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    return profiles


def derive_as_of(events: list[dict]) -> datetime:
    """Mốc snapshot = 00:00 UTC của ngày sau event cuối (seed sinh mọi event trong [as_of − 730, as_of − 1])."""
    if not events:
        raise ValueError("CDP chưa có event — seed trước (`make demo-db`)")
    last = max(parse_ts(e["timestamp"]) for e in events).astimezone(timezone.utc)
    return datetime.combine(last.date() + timedelta(days=1), time(0), tzinfo=timezone.utc)
