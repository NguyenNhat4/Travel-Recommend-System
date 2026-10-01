"""Nạp catalog, vector và event cho harness qua đúng adapter của backend — không SQL thẳng vào `cdp.*` (AGENTS.md §6.1).

Hai connection như backend: catalog qua `DATABASE_URL` (role `vota_app`, đọc được `catalog.product_meta`), event qua
`EVAL_DATABASE_URL` (role `cdp_eval_login` thuộc `cdp_reader`, chỉ đọc; `.env.example`). Thiếu `EVAL_DATABASE_URL` thì
lùi về `CDP_DATABASE_URL` và cảnh báo. psycopg/weaviate chỉ import trong hàm để test chạy không cần DB.

Chế độ vector:
- `none` — chỉ catalog (arm random không cần vector);
- `weaviate` — y hệt `main.build_recsys`: `WeaviateVectorStore(...).load()`, mỗi request truy vấn top-K (đúng production);
- `numpy` — kéo toàn bộ vector một lần qua REST (`WeaviateClient.fetch`), cache `.npz`, tra bằng `NumpyVectorSearch`
  (kNN chính xác, nhanh cho grid-search; lệch nhẹ so với HNSW).
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
    if mode not in VECTOR_MODES:
        raise ValueError(f"--vectors phải là một trong {VECTOR_MODES}")
    s = settings()
    version = model_version(s)
    if mode == "weaviate":
        from src.backend.app.infrastructure.vectors.weaviate_store import (
            WeaviateVectorSearch, WeaviateVectorStore, connect_weaviate)
        search = WeaviateVectorSearch(
            connect_weaviate(s.weaviate_url, api_key=s.weaviate_api_key, grpc_port=s.weaviate_grpc_port,
                             timeout_seconds=s.weaviate_timeout_seconds),
            collection=s.weaviate_collection, dimension=s.embed_dimension)
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
    client = WeaviateClient(s.weaviate_url, collection=s.weaviate_collection, api_key=s.weaviate_api_key,
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
