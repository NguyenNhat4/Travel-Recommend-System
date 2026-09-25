"""Weaviate adapter with self-provided Cohere vectors.

`WeaviateClient` (REST) phục vụ job `embed_products`; `WeaviateVectorSearch` (client v4, gRPC) phục vụ
truy vấn top-K mỗi request của Search / Similar / Recommendation.
"""
from __future__ import annotations

import hashlib
import logging
import re
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx
import numpy as np

from src.backend.app.application.ports import UnitIndex, VectorHit
from src.backend.app.infrastructure.vectors.postgres_store import PostgresCatalogReader

logger = logging.getLogger("uvicorn.error")


@dataclass(frozen=True)
class VectorMetadata:
    uuid: str
    product_id: str
    model_version: str
    text_hash: str


def normalize_weaviate_url(url: str) -> str:
    value = url.strip().rstrip("/")
    if "://" not in value:
        value = "https://" + value
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("WEAVIATE_URL must be an HTTP(S) endpoint")
    return value


class WeaviateClient:
    """Small REST client for the subset needed by the index job and runtime loader."""

    def __init__(
        self,
        base_url: str,
        *,
        collection: str = "Product",
        vector_index_type: str = "hnsw",
        api_key: str = "",
        timeout_seconds: float = 30.0,
        client: httpx.Client | None = None,
    ):
        if not re.fullmatch(r"[A-Z][A-Za-z0-9_]*", collection):
            raise ValueError("WEAVIATE_COLLECTION must be a valid GraphQL collection name")
        if vector_index_type not in {"hnsw", "hfresh"}:
            raise ValueError("WEAVIATE_VECTOR_INDEX_TYPE must be hnsw or hfresh")
        self.vector_index_type = vector_index_type
        self.collection = collection
        self._owns_client = client is None
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._client = client or httpx.Client(
            base_url=normalize_weaviate_url(base_url), timeout=timeout_seconds, headers=headers
        )

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def ready(self) -> None:
        response = self._client.get("/v1/.well-known/ready")
        response.raise_for_status()

    def ensure_collection(self) -> None:
        response = self._client.get(f"/v1/schema/{self.collection}")
        if response.status_code == 200:
            schema = response.json()
            if schema.get("vectorizer") != "none":
                raise RuntimeError(f"Weaviate collection {self.collection} must use vectorizer=none")
            distance = (schema.get("vectorIndexConfig") or {}).get("distance")
            if distance and distance != "cosine":
                raise RuntimeError(f"Weaviate collection {self.collection} must use cosine distance")
            actual = schema.get("vectorIndexType")
            if actual and actual != self.vector_index_type:
                # Loại index chỉ áp dụng khi tạo collection mới (deployment-plan.md §2); collection đã có giữ nguyên.
                logger.warning(
                    "weaviate.collection.index_type collection=%s actual=%s configured=%s; giữ collection hiện có",
                    self.collection, actual, self.vector_index_type,
                )
            return
        if response.status_code != 404:
            response.raise_for_status()
        created = self._client.post(
            "/v1/schema",
            json={
                "class": self.collection,
                "description": "V-OTA search units indexed with Cohere embed-multilingual-v3.0",
                "vectorizer": "none",
                "vectorIndexType": self.vector_index_type,
                "vectorIndexConfig": {"distance": "cosine"},
                "properties": [
                    {"name": "productId", "dataType": ["text"], "indexFilterable": True, "indexSearchable": False},
                    {"name": "modelVersion", "dataType": ["text"], "indexFilterable": True, "indexSearchable": False},
                    {"name": "textHash", "dataType": ["text"], "indexFilterable": True, "indexSearchable": False},
                ],
            },
        )
        created.raise_for_status()

    def fetch(
        self, *, include_vectors: bool, page_size: int = 500
    ) -> tuple[dict[str, VectorMetadata], dict[str, np.ndarray]]:
        """List objects via REST cursor pagination (Weaviate Cloud may disable GraphQL)."""
        metadata: dict[str, VectorMetadata] = {}
        vectors: dict[str, np.ndarray] = {}
        after = ""
        while True:
            params = {"class": self.collection, "limit": page_size}
            if after:
                params["after"] = after
            if include_vectors:
                params["include"] = "vector"
            response = self._client.get("/v1/objects", params=params)
            response.raise_for_status()
            rows = response.json().get("objects") or []
            for row in rows:
                props = row.get("properties") or {}
                product_id = str(props["productId"])
                metadata[product_id] = VectorMetadata(
                    uuid=str(row["id"]),
                    product_id=product_id,
                    model_version=str(props.get("modelVersion") or ""),
                    text_hash=str(props.get("textHash") or ""),
                )
                if include_vectors:
                    vectors[product_id] = np.asarray(row.get("vector") or [], dtype=np.float32)
            if len(rows) < page_size:
                return metadata, vectors
            after = str(rows[-1]["id"])

    @staticmethod
    def object_uuid(product_id: str) -> str:
        return str(uuid.uuid5(uuid.NAMESPACE_URL, f"vota:product:{product_id}"))

    def delete(self, object_ids: list[str]) -> None:
        for object_id in object_ids:
            response = self._client.delete(f"/v1/objects/{self.collection}/{object_id}")
            if response.status_code not in {200, 204, 404}:
                response.raise_for_status()

    def insert(self, objects: list[dict], *, batch_size: int = 100) -> None:
        for start in range(0, len(objects), batch_size):
            response = self._client.post("/v1/batch/objects", json={"objects": objects[start : start + batch_size]})
            response.raise_for_status()
            failures = [
                item for item in response.json()
                if ((item.get("result") or {}).get("status") or "SUCCESS").upper() != "SUCCESS"
            ]
            if failures:
                raise RuntimeError(f"Weaviate batch failed for {len(failures)} objects: {failures[:1]}")


def connect_weaviate(url: str, *, api_key: str = "", grpc_port: int = 50051, timeout_seconds: float = 30.0):
    """Client v4 (REST + gRPC). Truy vấn `nearVector` phải đi gRPC vì Weaviate Cloud của nhóm tắt GraphQL."""
    import weaviate
    from weaviate.classes.init import AdditionalConfig, Auth, Timeout

    parsed = urlparse(normalize_weaviate_url(url))
    host = parsed.hostname or "localhost"
    auth = Auth.api_key(api_key) if api_key else None
    config = AdditionalConfig(timeout=Timeout(init=timeout_seconds, query=timeout_seconds, insert=timeout_seconds))
    if host.endswith((".weaviate.cloud", ".weaviate.network")):
        # Cloud tự suy ra host gRPC `grpc-<cluster>` ở cổng 443.
        return weaviate.connect_to_weaviate_cloud(parsed.geturl(), auth_credentials=auth, additional_config=config)
    secure = parsed.scheme == "https"
    return weaviate.connect_to_custom(
        http_host=host,
        http_port=parsed.port or (443 if secure else 80),
        http_secure=secure,
        grpc_host=host,
        grpc_port=grpc_port,
        grpc_secure=secure,
        auth_credentials=auth,
        additional_config=config,
    )


def _object_vector(obj) -> np.ndarray:
    vector = obj.vector
    if isinstance(vector, dict):  # collection tạo bằng REST không đặt tên vector → key "default"
        vector = vector.get("default")
    return np.asarray(vector or [], dtype=np.float32)


class WeaviateVectorSearch:
    """`VectorSearchPort` trên collection `Product`: mỗi request một truy vấn top-K, lọc theo id object."""

    _ID_CHUNK = 1000

    def __init__(self, client, *, collection: str = "Product", dimension: int = 1024):
        self.client = client
        self.collection = client.collections.get(collection)
        self.dimension = dimension

    def close(self) -> None:
        self.client.close()

    @staticmethod
    def _id_filter(product_ids: Sequence[str]):
        from weaviate.classes.query import Filter

        return Filter.by_id().contains_any([WeaviateClient.object_uuid(p) for p in product_ids])

    def near_vector(self, vector: np.ndarray, allowed: Sequence[str] | None, limit: int,
                    *, with_vectors: bool = False) -> list[VectorHit]:
        from weaviate.classes.query import MetadataQuery

        if limit <= 0 or (allowed is not None and not allowed):
            return []
        result = self.collection.query.near_vector(
            near_vector=np.asarray(vector, dtype=np.float32).tolist(),
            limit=limit,
            filters=self._id_filter(allowed) if allowed is not None else None,
            return_properties=["productId"],
            return_metadata=MetadataQuery(distance=True),
            include_vector=with_vectors,
        )
        return [
            VectorHit(
                product_id=str(obj.properties["productId"]),
                score=1.0 - float(obj.metadata.distance),
                vector=_object_vector(obj) if with_vectors else None,
            )
            for obj in result.objects
        ]

    def vectors(self, product_ids: Sequence[str]) -> dict[str, np.ndarray]:
        ids = list(dict.fromkeys(product_ids))
        out: dict[str, np.ndarray] = {}
        for start in range(0, len(ids), self._ID_CHUNK):
            chunk = ids[start : start + self._ID_CHUNK]
            result = self.collection.query.fetch_objects(
                filters=self._id_filter(chunk), limit=len(chunk), include_vector=True, return_properties=["productId"]
            )
            for obj in result.objects:
                out[str(obj.properties["productId"])] = _object_vector(obj)
        return out

    def metadata(self, product_ids: Sequence[str]) -> dict[str, VectorMetadata]:
        """`modelVersion`/`textHash` của object theo id tất định, không tải vector."""
        out = {}
        ids = list(dict.fromkeys(product_ids))
        for start in range(0, len(ids), self._ID_CHUNK):
            chunk = ids[start:start + self._ID_CHUNK]
            result = self.collection.query.fetch_objects(
                filters=self._id_filter(chunk), limit=len(chunk), include_vector=False,
                return_properties=["productId", "modelVersion", "textHash"],
            )
            for obj in result.objects:
                props = obj.properties
                pid = str(props["productId"])
                out[pid] = VectorMetadata(str(obj.uuid), pid,
                    str(props.get("modelVersion") or ""), str(props.get("textHash") or ""))
        return out


class WeaviateVectorStore:
    """Metadata search unit từ PostgreSQL + kho vector Weaviate để truy vấn theo request.

    Không tải vector lúc khởi động. Mỗi lần nạp kiểm từng unit theo object id, `modelVersion` và `textHash`:
    unit chưa có vector vẫn nằm trong metadata (Weaviate chưa trả nó cho tới khi job index xong), unit có vector
    của text cũ dùng tạm vector đó. Chỉ từ chối khi dưới một nửa unit có vector đúng model — collection rỗng,
    chưa index, hoặc vừa đổi text builder mà chưa index lại.
    """

    def __init__(self, database_url: str, search: WeaviateVectorSearch, *, expected_model_version: str):
        self.reader = PostgresCatalogReader(database_url)
        self.search = search
        self.expected_model_version = expected_model_version
        self.sync: dict[str, int] = {}

    def load(self) -> tuple[UnitIndex, WeaviateVectorSearch]:
        catalog = self.reader.load()
        desired = {p.product_id: hashlib.sha256(text.encode("utf-8")).hexdigest()
                   for p, text in zip(catalog.units, catalog.texts, strict=True)}
        stored = self.search.metadata(list(desired))
        current = {pid for pid, meta in stored.items()
                   if pid in desired and meta.model_version == self.expected_model_version}
        stale = sum(stored[pid].text_hash != desired[pid] for pid in current)
        self.sync = {"searchUnits": len(desired), "missing": len(desired) - len(current), "staleText": stale}
        if 2 * len(current) < len(desired):
            raise RuntimeError(
                f"Weaviate chỉ có {len(current)}/{len(desired)} search unit có vector model "
                f"{self.expected_model_version}; chạy index trước khi mở RecSys"
            )
        if len(current) < len(desired) or stale:
            logger.warning("recsys.vectors.out_of_sync search_units=%d missing=%d stale_text=%d",
                           len(desired), len(desired) - len(current), stale)
        return catalog.to_index(self.expected_model_version), self.search
