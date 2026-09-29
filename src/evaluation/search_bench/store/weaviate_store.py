"""Part 4 — adapter Weaviate: collection theo cặp variant × model, nạp vector tự cung cấp, query dense / bm25.

Tên collection: logic `products__<variant>__<model_slug>` (ghi trong results) ↔ vật lý `Products__<variant "+"→"_">__<model_slug>`
(+ `__<dataset>` khi không phải jsonl) vì Weaviate chỉ nhận `^[A-Z][_0-9A-Za-z]*$`. Mô tả collection là JSON ghi nguồn gốc
(dataset, items_sha256, n, variant, model, ascii_fold_mode, text builder) để lệnh sau kiểm được collection còn khớp dữ liệu.

Fold dấu cho BM25 lấy từ config (`weaviate.ascii_fold`), không tự đoán: `analyzer` = text_analyzer(ascii_fold=True) của
Weaviate ≥ 1.37 trên `name`, `embed_text`; `shadow` = app tạo `name_ascii`, `embed_text_ascii` (fold) và fold cả query.
Property kiểu `field` chỉ để lọc (không searchable); BM25 luôn truyền query_properties tường minh.
"""
from __future__ import annotations

import json
import re
import warnings
from dataclasses import dataclass
from typing import Any, Iterable
from urllib.parse import urlparse

import numpy as np
import pandas as pd
import structlog

from evaluation.vector_bench.lexical import fold

from ..config import WeaviateConfig
from ..textbuild import normalize_variant

log = structlog.get_logger("sbench.weaviate")

PHYSICAL_NAME = re.compile(r"^[A-Z][_0-9A-Za-z]*$")
CONTENT_VECTOR = "content"
KEYWORD_PROPS = ("product_id", "taxonomy", "variant", "destination", "province", "brand", "parent_product_id")
TEXT_PROPS = ("name", "embed_text")
NUMBER_PROPS = ("star_rating", "unit_price_min")
BOOL_PROPS = ("ticketed", "family_friendly", "ocean_view", "available")
RETURN_PROPS = ["product_id", "name", "destination", "taxonomy", "variant", "parent_product_id"]


class StoreError(RuntimeError):
    pass


def model_slug(model: str) -> str:
    return model.replace("-", "_")


def collection_name(variant: str, model: str, dataset: str = "jsonl") -> tuple[str, str]:
    v = normalize_variant(variant)
    logical = f"products__{v}__{model_slug(model)}"
    physical = f"Products__{v.replace('+', '_')}__{model_slug(model)}" + ("" if dataset == "jsonl" else f"__{dataset}")
    if not PHYSICAL_NAME.match(physical):
        raise StoreError(f"tên collection không hợp lệ với Weaviate: {physical}")
    return logical, physical


def bm25_query_properties(fold_mode: str) -> list[str]:
    return ["name_ascii^2", "embed_text_ascii"] if fold_mode == "shadow" else ["name^2", "embed_text"]


def build_properties(fold_mode: str, tokenization: str) -> list:
    from weaviate.classes.config import Configure, DataType, Property, Tokenization
    text_tok = Tokenization(tokenization)
    analyzer = Configure.text_analyzer(ascii_fold=True) if fold_mode == "analyzer" else None
    props = [Property(name=p, data_type=DataType.TEXT, tokenization=Tokenization.FIELD, index_searchable=False,
                      index_filterable=True) for p in KEYWORD_PROPS]
    props += [Property(name=p, data_type=DataType.TEXT, tokenization=text_tok, text_analyzer=analyzer) for p in TEXT_PROPS]
    if fold_mode == "shadow":
        props += [Property(name=f"{p}_ascii", data_type=DataType.TEXT, tokenization=text_tok) for p in TEXT_PROPS]
    props.append(Property(name="amenity_ids", data_type=DataType.INT_ARRAY))
    props += [Property(name=p, data_type=DataType.NUMBER) for p in NUMBER_PROPS]
    props += [Property(name=p, data_type=DataType.BOOL) for p in BOOL_PROPS]
    return props


def _clean(v: Any) -> Any:
    if v is None:
        return None
    if isinstance(v, float) and np.isnan(v):
        return None
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        return None if np.isnan(v) else float(v)
    if isinstance(v, (np.bool_,)):
        return bool(v)
    if isinstance(v, (list, tuple, np.ndarray)):
        return [_clean(x) for x in v]
    return v


def object_properties(item: dict, text: str, fold_mode: str) -> dict:
    props = {k: _clean(item.get(k)) for k in (*KEYWORD_PROPS, *NUMBER_PROPS, *BOOL_PROPS)}
    props["name"] = item["name"]
    props["embed_text"] = text
    props["amenity_ids"] = [int(x) for x in (item.get("amenity_ids") if item.get("amenity_ids") is not None else [])]
    if fold_mode == "shadow":
        props["name_ascii"] = fold(item["name"])
        props["embed_text_ascii"] = fold(text)
    return {k: v for k, v in props.items() if v is not None}


@dataclass
class Hit:
    rank: int
    product_id: str
    name: str
    destination: str
    taxonomy: str
    variant: str
    distance: float | None = None
    score: float | None = None


class WeaviateStore:
    def __init__(self, cfg: WeaviateConfig):
        warnings.filterwarnings("ignore", message="The httpx module is deprecated")
        import weaviate
        from weaviate.classes.init import AdditionalConfig, Timeout
        u = urlparse(cfg.url)
        self.cfg = cfg
        self.client = weaviate.connect_to_local(
            host=u.hostname or "127.0.0.1", port=u.port or 8080, grpc_port=cfg.grpc_port,
            additional_config=AdditionalConfig(timeout=Timeout(query=cfg.query_timeout_s, insert=120, init=10)))

    def __enter__(self) -> "WeaviateStore":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def close(self) -> None:
        self.client.close()

    # ------------------------------------------------------------------ schema
    def server_version(self) -> str:
        return str(self.client.get_meta().get("version"))

    def fold_mode(self) -> str:
        """Chế độ fold theo config; `analyzer` mà server/client không làm được thì lỗi (không tự lùi về shadow)."""
        mode = self.cfg.ascii_fold
        if mode == "analyzer":
            from weaviate.classes.config import Configure
            from ..doctor import version_at_least
            ver = self.server_version()
            if not hasattr(Configure, "text_analyzer") or not version_at_least(ver, "1.37"):
                raise StoreError(f"ascii_fold: analyzer cần Weaviate ≥ 1.37 và client có text_analyzer (server {ver}) — "
                                 "sửa môi trường hoặc đặt weaviate.ascii_fold: shadow")
        return mode

    def exists(self, physical: str) -> bool:
        return self.client.collections.exists(physical)

    def create_collection(self, physical: str, *, description: dict, recreate: bool = False) -> str:
        """Tạo collection; mô tả ghi `complete: false` cho tới khi `mark_complete` sau bước kiểm count.

        Mọi thứ (chế độ fold, property, index) được dựng và kiểm TRƯỚC khi xoá collection cũ — cấu hình sai thì collection
        cũ vẫn còn nguyên.
        """
        from weaviate.classes.config import Configure, StopwordsPreset, VectorDistances
        mode = self.fold_mode()
        bm = self.cfg.bm25
        props = build_properties(mode, bm.tokenization)
        index = (Configure.VectorIndex.flat(distance_metric=VectorDistances.COSINE) if self.cfg.vector_index == "flat"
                 else Configure.VectorIndex.hnsw(distance_metric=VectorDistances.COSINE))
        inverted = Configure.inverted_index(bm25_k1=bm.k1, bm25_b=bm.b, stopwords_preset=StopwordsPreset(bm.stopwords_preset),
                                            index_null_state=True)      # lọc được "thiếu giá trị" (is_none) cho filter AST
        desc = {**description, "complete": False, "ascii_fold_mode": mode, "vector_index": self.cfg.vector_index,
                "bm25": {"k1": bm.k1, "b": bm.b, "tokenization": bm.tokenization, "stopwords_preset": bm.stopwords_preset}}
        if self.exists(physical):
            if not recreate:
                raise StoreError(f"collection {physical} đã có — dùng --recreate để dựng lại")
            self.client.collections.delete(physical)
            log.info("đã xoá collection cũ", collection=physical)
        self.client.collections.create(
            name=physical, description=json.dumps(desc, ensure_ascii=False), properties=props,
            vector_config=Configure.Vectors.self_provided(name=CONTENT_VECTOR, vector_index_config=index),
            inverted_index_config=inverted)
        return mode

    def mark_complete(self, physical: str, **extra: Any) -> dict:
        desc = {**self.description(physical), **extra, "complete": True}
        self.client.collections.get(physical).config.update(description=json.dumps(desc, ensure_ascii=False))
        return desc

    def check_ready(self, physical: str, items_sha256: str | None = None, expected: dict | None = None) -> dict:
        """Collection phải nạp xong (complete, count == n) và — nếu truyền — khớp items hiện tại và mọi khoá trong `expected`
        (vd builder_fingerprint, combo_manual_sha256 của text hiện tại); không thì StoreError."""
        desc = self.description(physical)
        if not desc.get("complete"):
            raise StoreError(f"collection {physical} chưa nạp xong (load lỗi giữa chừng?) — chạy lại `sb load`")
        n = self.count(physical)
        if n != desc.get("n"):
            raise StoreError(f"collection {physical} có {n} object nhưng mô tả ghi {desc.get('n')} — chạy lại `sb load`")
        if items_sha256 is not None and desc.get("items_sha256") != items_sha256:
            raise StoreError(f"collection {physical} dựng từ items cũ (catalog đã build lại) — chạy lại `sb embed` + `sb load`")
        stale = [k for k, v in (expected or {}).items() if desc.get(k) != v]
        if stale:
            raise StoreError(f"collection {physical} dựng từ text cũ ({', '.join(stale)} khác hiện tại — text builder / soát tay "
                             "combo đã đổi) — chạy lại `sb embed` + `sb load`")
        return desc

    def description(self, physical: str) -> dict:
        if not self.exists(physical):
            raise StoreError(f"chưa có collection {physical} — chạy `sb load` trước")
        raw = self.client.collections.get(physical).config.get().description or "{}"
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}

    def list_collections(self, prefix: str = "Products__") -> list[tuple[str, int, dict]]:
        out = []
        for name in sorted(self.client.collections.list_all(simple=True)):
            if name.startswith(prefix):
                out.append((name, self.count(name), self.description(name)))
        return out

    def drop(self, physical: str) -> None:
        if not self.exists(physical):
            raise StoreError(f"không có collection {physical}")
        self.client.collections.delete(physical)

    def count(self, physical: str, filters: Any = None) -> int:
        agg = self.client.collections.get(physical).aggregate.over_all(filters=filters, total_count=True)
        return int(agg.total_count)

    def fetch_ids(self, physical: str, filters: Any = None, limit: int = 10_000) -> list[str]:
        """product_id của mọi object thoả filter (không dùng vector) — để đối chiếu với evaluator pandas."""
        r = self.client.collections.get(physical).query.fetch_objects(filters=filters, limit=limit,
                                                                      return_properties=["product_id"])
        return [o.properties["product_id"] for o in r.objects]

    # ------------------------------------------------------------------ nạp
    def load(self, physical: str, items: pd.DataFrame, texts: dict[str, str], ids: list[str], vectors: np.ndarray,
             *, fold_mode: str) -> int:
        from weaviate.util import generate_uuid5
        if len(ids) != len(vectors):
            raise StoreError(f"{len(ids)} id nhưng {len(vectors)} vector")
        by_id = {r["product_id"]: r for r in items.to_dict(orient="records")}
        missing = [pid for pid in ids if pid not in by_id or pid not in texts]
        if missing:
            raise StoreError(f"{len(missing)} id không có trong items/text hiện tại, ví dụ {missing[:3]} — chạy lại sb embed")
        col = self.client.collections.get(physical)
        with col.batch.fixed_size(batch_size=self.cfg.load_batch_size) as batch:
            for pid, vec in zip(ids, vectors):
                batch.add_object(properties=object_properties(by_id[pid], texts[pid], fold_mode), uuid=generate_uuid5(pid),
                                 vector={CONTENT_VECTOR: np.asarray(vec, dtype=np.float32).tolist()})
        failed = col.batch.failed_objects
        if failed:
            raise StoreError(f"{len(failed)} object nạp lỗi, ví dụ: {failed[0].message}")
        n = self.count(physical)
        if n != len(ids):
            raise StoreError(f"count {n} ≠ {len(ids)} id đã embed")
        return n

    # ------------------------------------------------------------------ truy vấn
    @staticmethod
    def _hits(objs: Iterable[Any], metric: str) -> list[Hit]:
        out = []
        for i, o in enumerate(objs, 1):
            p = o.properties
            md = o.metadata
            out.append(Hit(rank=i, product_id=p.get("product_id"), name=p.get("name"), destination=p.get("destination"),
                           taxonomy=p.get("taxonomy"), variant=p.get("variant"),
                           distance=getattr(md, "distance", None) if metric == "distance" else None,
                           score=getattr(md, "score", None) if metric == "score" else None))
        return out

    def dense(self, physical: str, qvec: np.ndarray, limit: int, filters: Any = None) -> list[Hit]:
        from weaviate.classes.query import MetadataQuery
        r = self.client.collections.get(physical).query.near_vector(
            near_vector=np.asarray(qvec, dtype=np.float32).tolist(), target_vector=CONTENT_VECTOR, limit=limit,
            filters=filters, return_metadata=MetadataQuery(distance=True), return_properties=RETURN_PROPS)
        return self._hits(r.objects, "distance")

    def bm25(self, physical: str, query: str, limit: int, *, fold_mode: str, filters: Any = None) -> list[Hit]:
        from weaviate.classes.query import MetadataQuery
        q = fold(query) if fold_mode == "shadow" else query
        r = self.client.collections.get(physical).query.bm25(
            query=q, query_properties=bm25_query_properties(fold_mode), limit=limit, filters=filters,
            return_metadata=MetadataQuery(score=True), return_properties=RETURN_PROPS)
        return self._hits(r.objects, "score")
