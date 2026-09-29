"""Part 7 — adapter Qdrant (ứng viên đầu tiên).

VERIFY đã tra trên qdrant/qdrant:v1.19.1 + qdrant-client 1.19.1 (workflow vbench-verify-research, thử thật):
- VectorParams(size, Distance.COSINE, datatype=Datatype.FLOAT16, hnsw_config=HnswConfigDiff(m, ef_construct)); mặc định server
  m=16, ef_construct=100, full_scan_threshold=10000 KB, indexing_threshold=10000 KB (theo từng segment).
- indexing_threshold = 0 nghĩa là TẮT index (không phải "index ngay"). Nạp lô: tắt index khi upload rồi trả về giá trị mặc định
  của server (đọc từ collection vừa tạo) — HNSW build sau khi nạp xong, cấu hình cuối cùng vẫn là mặc định.
- MatchValue trên mảng = "chứa"; ALL-of = một MatchValue mỗi id trong must; must_not(MatchAny) cho mảng rỗng → thoả (đúng AST).
- Range loại null/missing; GeoRadius: haversine R = 6.371.008,8 m, so sánh CHẶT d < r (khác ≤ ở evaluator → vùng biên xử lý).
- query_points(…, using="dense"); ACORN: SearchParams(acorn=AcornSearchParams(enable=True)) có từ 1.16.
- Client HTTP mặc định TẮT keep-alive với localhost (13–16 ms/query) → dùng gRPC (prefer_grpc=True, ~6 ms).
Lexical (sparse bm25), facet, snapshot: bỏ ở fast-track (spec-fasttrack §4 Part 7).
"""
from __future__ import annotations

import importlib.metadata as md
import math
import time
from typing import Any

import numpy as np

from ..filters import validate
from .base import ALL_FILTER_OPS, BaseStore, Capabilities, Hit, QueryTimeout, StoreOptions, UnsupportedFilter

COLLECTION = "items"
KEYWORD = ("taxonomy", "destination", "variant")
LOAD_TIMEOUT_S = 300


class QdrantStore(BaseStore):
    name = "qdrant"

    def __init__(self, cfg, dim: int, opts: StoreOptions | None = None):
        self.cfg = cfg
        self.url = cfg.get("url")
        self.grpc_port = int(cfg.get("grpc_port"))
        self.dim = dim
        self.opts = opts or StoreOptions()
        self.client = None
        self._index = None
        self._default_indexing_threshold: int | None = None
        self.query_timeout_s = max(1, math.ceil((self.opts.timeout_ms or 0) / 1000)) if self.opts.timeout_ms else None

    def connect(self) -> None:
        from qdrant_client import QdrantClient
        self.client = QdrantClient(url=self.url, grpc_port=self.grpc_port, prefer_grpc=True, timeout=LOAD_TIMEOUT_S)

    def close(self) -> None:
        if self.client is not None:
            self.client.close()
            self.client = None

    def server_version(self) -> str:
        return f"qdrant {self.client.info().version}"

    def client_version(self) -> str:
        return f"qdrant-client {md.version('qdrant-client')} (gRPC)"

    def capabilities(self) -> Capabilities:
        return Capabilities(exact_search=True, filter_ops=ALL_FILTER_OPS, geo="native", count_exact=True, facet="exact",
                            lexical="sparse_bm25", vector_dtypes=frozenset({"f32", "f16", "int8", "binary"}), async_client=True,
                            backup="native", acorn=True,
                            notes=("lexical/facet/snapshot chưa cài ở fast-track",
                                   "geo so sánh chặt d < r (evaluator: d ≤ r) — chênh nằm trong vùng biên geo_boundary_tol",
                                   "client gRPC (HTTP mặc định tắt keep-alive với localhost)",
                                   "nạp lô: indexing_threshold=0 khi upload rồi trả về mặc định server; HNSW build sau khi nạp"))

    # ------------------------------------------------------------ dịch filter (thuần)
    def translate(self, filt: dict | None):
        from qdrant_client import models as m
        if filt is None:
            return None
        validate(filt)
        c = self._cond(filt, m)
        return c if isinstance(c, m.Filter) else m.Filter(must=[c])

    def _cond(self, node: dict, m):
        (op, arg), = node.items()
        if op == "and":
            return m.Filter(must=[self._cond(c, m) for c in arg])
        if op == "or":
            return m.Filter(should=[self._cond(c, m) for c in arg])
        if op == "not":
            return m.Filter(must_not=[self._cond(arg, m)])
        if op == "eq":
            fld, v = arg
            if fld not in KEYWORD + ("available",):
                raise UnsupportedFilter("eq", fld)
            return m.FieldCondition(key=fld, match=m.MatchValue(value=v))
        if op == "in":
            fld, vals = arg
            if fld not in KEYWORD:
                raise UnsupportedFilter("in", fld)
            return m.FieldCondition(key=fld, match=m.MatchAny(any=list(vals)))
        if op == "range":
            fld, cond = arg
            return m.FieldCondition(key=fld, range=m.Range(**{k: float(v) for k, v in cond.items()}))
        if op == "all":
            return m.Filter(must=[m.FieldCondition(key="amenity_ids", match=m.MatchValue(value=int(a))) for a in arg[1]])
        if op == "any":
            return m.FieldCondition(key="amenity_ids", match=m.MatchAny(any=[int(a) for a in arg[1]]))
        if op == "geo":
            return m.FieldCondition(key="location", geo_radius=m.GeoRadius(
                center=m.GeoPoint(lat=float(arg["lat"]), lon=float(arg["lon"])), radius=float(arg["radius_m"])))
        if op == "id_in":
            return m.HasIdCondition(has_id=[str(x) for x in arg])
        raise UnsupportedFilter(op)

    # ------------------------------------------------------------ tạo + nạp
    def create(self, index) -> None:
        from qdrant_client import models as m
        self._index = index
        p = dict(index.params)
        c = self.client
        if c.collection_exists(COLLECTION):
            c.delete_collection(COLLECTION)
        hnsw = {k: p[k] for k in ("m", "ef_construct") if k in p}
        if "full_scan_threshold_kb" in p:
            hnsw["full_scan_threshold"] = int(p["full_scan_threshold_kb"])
        c.create_collection(COLLECTION, vectors_config={"dense": m.VectorParams(
            size=self.dim, distance=m.Distance.COSINE, datatype=m.Datatype.FLOAT16, hnsw_config=m.HnswConfigDiff(**hnsw))})
        info = c.get_collection(COLLECTION)
        self._default_indexing_threshold = int(p.get("indexing_threshold_kb", info.config.optimizer_config.indexing_threshold))
        # payload index TRƯỚC khi nạp (filterable HNSW thêm cạnh theo giá trị lúc build)
        for f in KEYWORD:
            c.create_payload_index(COLLECTION, field_name=f, field_schema=m.PayloadSchemaType.KEYWORD, wait=True)
        c.create_payload_index(COLLECTION, field_name="available", field_schema=m.PayloadSchemaType.BOOL, wait=True)
        c.create_payload_index(COLLECTION, field_name="amenity_ids", field_schema=m.PayloadSchemaType.INTEGER, wait=True)
        for f in ("unit_price", "star_rating"):
            c.create_payload_index(COLLECTION, field_name=f, field_schema=m.PayloadSchemaType.FLOAT, wait=True)
        c.create_payload_index(COLLECTION, field_name="location", field_schema=m.PayloadSchemaType.GEO, wait=True)
        c.update_collection(COLLECTION, optimizers_config=m.OptimizersConfigDiff(indexing_threshold=0))   # tắt index khi nạp lô

    @staticmethod
    def _payload(pl: dict) -> dict:
        return {"variant": pl["variant"], "taxonomy": pl["taxonomy"], "destination": pl["destination"],
                "available": bool(pl["available"]), "amenity_ids": [int(a) for a in pl["amenity_ids"]],
                "unit_price": pl["unit_price"], "star_rating": pl["star_rating"],
                "location": {"lat": float(pl["lat"]), "lon": float(pl["lon"])}}

    def upsert(self, ids: list[str], vecs: np.ndarray, payloads: list[dict]) -> None:
        from qdrant_client import models as m
        self.client.upsert(COLLECTION, points=m.Batch(ids=list(ids), vectors={"dense": np.asarray(vecs, dtype=np.float32).tolist()},
                                                      payloads=[self._payload(p) for p in payloads]), wait=True)

    def finalize(self) -> float:
        from qdrant_client import models as m
        t0 = time.perf_counter()
        self.client.update_collection(COLLECTION, optimizers_config=m.OptimizersConfigDiff(
            indexing_threshold=self._default_indexing_threshold))
        time.sleep(1.0)                     # optimizer có thể chưa kịp chuyển YELLOW ngay sau update
        stable = 0
        dl = self.opts.extra.get("deadline")            # chặn thời gian của `vb fast`
        while stable < 3:
            if dl is not None and time.perf_counter() > dl:
                raise TimeoutError("vượt chặn thời gian khi chờ Qdrant build index")
            info = self.client.get_collection(COLLECTION)
            qlen = info.update_queue.length if getattr(info, "update_queue", None) else 0
            ok = info.status == m.CollectionStatus.GREEN and not qlen
            stable = stable + 1 if ok else 0
            if info.status == m.CollectionStatus.RED:
                raise RuntimeError(f"collection RED: {info.optimizer_status}")
            time.sleep(1.0)
        return time.perf_counter() - t0 - 3.0     # trừ 3 lần poll xác nhận ổn định

    def index_meta(self) -> dict:
        i = self.client.get_collection(COLLECTION)
        return {"points_count": i.points_count, "indexed_vectors_count": i.indexed_vectors_count,
                "segments_count": i.segments_count, "status": str(i.status),
                "indexing_threshold_kb": self._default_indexing_threshold}

    # ------------------------------------------------------------ truy vấn
    def supports_query_config(self, qp: dict) -> tuple[bool, str]:
        mode = qp.get("mode", "ann")
        if mode in ("exact", "ann", "ann_acorn"):
            return True, ""
        return False, f"mode {mode} không có ở qdrant"

    def search_params(self, qp: dict):
        from qdrant_client import models as m
        mode = qp.get("mode", "ann")
        if mode == "exact":
            return m.SearchParams(exact=True)
        kw: dict[str, Any] = {}
        if "hnsw_ef" in qp:
            kw["hnsw_ef"] = int(qp["hnsw_ef"])
        if mode == "ann_acorn":
            kw["acorn"] = m.AcornSearchParams(enable=True)
        return m.SearchParams(**kw) if kw else None

    def search(self, q: np.ndarray, filt: dict | None, k: int, qp: dict) -> list[Hit]:
        flt = self.translate(filt)
        try:
            res = self.client.query_points(COLLECTION, query=np.asarray(q, dtype=np.float32).tolist(), using="dense",
                                           query_filter=flt, limit=k, search_params=self.search_params(qp),
                                           with_payload=False, timeout=self.query_timeout_s)
        except Exception as e:  # noqa: BLE001
            s = repr(e)
            if "DEADLINE_EXCEEDED" in s or "Timeout" in s or "timed out" in s:
                raise QueryTimeout(s) from e
            raise
        return [(str(p.id), float(p.score)) for p in res.points]

    def ping(self) -> None:
        self.client.collection_exists(COLLECTION)

    def count(self, filt: dict | None) -> tuple[int, bool]:
        return int(self.client.count(COLLECTION, count_filter=self.translate(filt), exact=True).count), True

    def set_available(self, id: str, value: bool) -> None:
        self.client.set_payload(COLLECTION, payload={"available": bool(value)}, points=[id], wait=True)

    def delete_ids(self, ids: list[str]) -> None:
        from qdrant_client import models as m
        self.client.delete(COLLECTION, points_selector=m.PointIdsList(points=list(ids)), wait=True)

    def delete_all(self) -> None:
        self.create(self._index)
