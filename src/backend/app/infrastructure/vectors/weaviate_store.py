"""Weaviate adapter with self-provided Cohere vectors."""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass

import httpx
import numpy as np

from src.backend.app.application.ports import UnitIndex
from src.backend.app.infrastructure.vectors.postgres_store import CatalogUnits, PostgresCatalogReader


@dataclass(frozen=True)
class VectorMetadata:
    uuid: str
    product_id: str
    model_version: str
    text_hash: str


class WeaviateClient:
    """Small REST client for the subset needed by the index job and runtime loader."""

    def __init__(
        self,
        base_url: str,
        *,
        collection: str = "Product",
        api_key: str = "",
        timeout_seconds: float = 30.0,
        client: httpx.Client | None = None,
    ):
        if not re.fullmatch(r"[A-Z][A-Za-z0-9_]*", collection):
            raise ValueError("WEAVIATE_COLLECTION must be a valid GraphQL collection name")
        self.collection = collection
        self._owns_client = client is None
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._client = client or httpx.Client(
            base_url=base_url.rstrip("/"), timeout=timeout_seconds, headers=headers
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
            return
        if response.status_code != 404:
            response.raise_for_status()
        created = self._client.post(
            "/v1/schema",
            json={
                "class": self.collection,
                "description": "V-OTA search units indexed with Cohere embed-multilingual-v3.0",
                "vectorizer": "none",
                "vectorIndexType": "hnsw",
                "vectorIndexConfig": {"distance": "cosine"},
                "properties": [
                    {"name": "productId", "dataType": ["text"], "indexFilterable": True, "indexSearchable": False},
                    {"name": "modelVersion", "dataType": ["text"], "indexFilterable": True, "indexSearchable": False},
                    {"name": "textHash", "dataType": ["text"], "indexFilterable": True, "indexSearchable": False},
                ],
            },
        )
        created.raise_for_status()

    def _graphql(self, query: str) -> dict:
        response = self._client.post("/v1/graphql", json={"query": query})
        response.raise_for_status()
        payload = response.json()
        if payload.get("errors"):
            raise RuntimeError(f"Weaviate GraphQL error: {payload['errors']}")
        return payload["data"]

    def fetch(self, *, include_vectors: bool) -> tuple[dict[str, VectorMetadata], dict[str, np.ndarray]]:
        additional = "_additional { id vector }" if include_vectors else "_additional { id }"
        data = self._graphql(
            "{ Get { "
            + self.collection
            + f"(limit: 10000) {{ productId modelVersion textHash {additional} }} }} }}"
        )
        rows = data.get("Get", {}).get(self.collection) or []
        metadata: dict[str, VectorMetadata] = {}
        vectors: dict[str, np.ndarray] = {}
        for row in rows:
            product_id = str(row["productId"])
            extra = row.get("_additional") or {}
            metadata[product_id] = VectorMetadata(
                uuid=str(extra["id"]),
                product_id=product_id,
                model_version=str(row.get("modelVersion") or ""),
                text_hash=str(row.get("textHash") or ""),
            )
            if include_vectors:
                vectors[product_id] = np.asarray(extra.get("vector") or [], dtype=np.float32)
        return metadata, vectors

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


class WeaviateVectorStore:
    """Load persisted vectors from Weaviate and grounded display data from PostgreSQL."""

    def __init__(
        self,
        database_url: str,
        client: WeaviateClient,
        *,
        expected_model_version: str,
        dimension: int = 1024,
    ):
        self.reader = PostgresCatalogReader(database_url)
        self.client = client
        self.expected_model_version = expected_model_version
        self.dimension = dimension

    def load(self) -> UnitIndex:
        catalog = self.reader.load()
        self.client.ready()
        self.client.ensure_collection()
        metadata, vectors = self.client.fetch(include_vectors=True)
        missing = [p.product_id for p in catalog.units if p.product_id not in vectors]
        if missing:
            raise RuntimeError(
                f"Weaviate thiếu {len(missing)} search unit; chạy `make index-vectors` trước khi mở RecSys"
            )
        wrong_model = [
            p.product_id
            for p in catalog.units
            if metadata[p.product_id].model_version != self.expected_model_version
        ]
        if wrong_model:
            raise RuntimeError(
                f"Weaviate có {len(wrong_model)} vector sai model/text version; chạy lại `make index-vectors`"
            )
        embeddings = np.vstack([vectors[p.product_id] for p in catalog.units]).astype(np.float32)
        if embeddings.shape != (len(catalog.units), self.dimension):
            raise RuntimeError(
                f"Weaviate vector shape {embeddings.shape}; expected ({len(catalog.units)}, {self.dimension})"
            )
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        if np.any(norms == 0):
            raise RuntimeError("Weaviate contains a zero-length embedding")
        return catalog.to_index(embeddings / norms, self.expected_model_version)
