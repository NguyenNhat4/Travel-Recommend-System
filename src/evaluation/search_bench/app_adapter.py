"""Cổng APP (arms.md §1, 30/09) — chạy đúng use case `/search` của backend (`SearchProducts`) trên gold.

Mục đích: đo dense-only / hybrid / hybrid + normalize **như production** (M2), không dựng lại RRF hay luật vớt trong
bench. Mọi thứ đi qua chính lớp `application/search/use_cases.py`; chỉ ba adapter được thay:

- `UnitIndex` dựng từ catalog snapshot của bench (`Product.from_cdp` với attributes combo như `load_products`), thay cho
  Postgres (`PostgresCatalogReader`). Text = text T3+R của bench (`textbuild.load_texts`, đã kiểm trùng production).
- Kho vector: collection `ProductBench` trên Weaviate của bench (`:58080`), hình dạng y hệt collection `Product` của
  production (`WeaviateClient.ensure_collection` + `insert` của backend: `productId`, `modelVersion`, `textHash`,
  `nameAscii` / `searchTextAscii` fold ở app, uuid5 `vota:product:<id>`), vector lấy từ file `.npy` đã embed cho B0 →
  0 lượt gọi Cohere. Backend chỉ nhận `hnsw` / `hfresh` (không `flat`), nên kết quả có nhiễu ANN nhỏ — ghi caveat.
- Embedder truy vấn: `CachedEmbedder` của bench (Cohere v3, `input_type=query`, cache sqlite) bọc thành `EmbedderPort`.

Mọi import backend đi qua tiền tố `src.backend.*` (use case tự import như vậy); không trộn với tiền tố `backend.` của
`textbuild._import_backend`.
"""
from __future__ import annotations

import hashlib
import sys
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any

import numpy as np

from . import catalog, paths, vectors
from .config import SBenchConfig
from .textbuild import load_texts

PRODUCT_BENCH = "ProductBench"
MODEL_VERSION = "embed-multilingual-v3.0:catalog-text-v2"      # như production (main.build_recsys)


class AppAdapterError(RuntimeError):
    pass


def _backend():
    root = str(paths.repo_root())
    if root not in sys.path:
        sys.path.insert(0, root)
    try:
        from src.backend.app.application.ports import UnitIndex
        from src.backend.app.application.search.use_cases import SearchProducts
        from src.backend.app.domain.catalog import Product
        from src.backend.app.domain.search import HybridConfig
        from src.backend.app.infrastructure.vectors import weaviate_store as W
    except Exception as e:  # noqa: BLE001
        raise AppAdapterError(f"không import được backend (src.backend.app…): {type(e).__name__}: {e}") from None
    return UnitIndex, SearchProducts, Product, HybridConfig, W


# ------------------------------------------------------------------ UnitIndex từ snapshot
@dataclass
class AppCatalog:
    index: Any                        # UnitIndex của backend
    texts: dict[str, str]             # product_id → text T3+R (= production)
    text_hash: dict[str, str]         # sha256(text) như WeaviateVectorStore / job embed_products


def build_app_catalog(cfg: SBenchConfig, dataset: str) -> AppCatalog:
    """`Product` cho mọi search unit của dataset (attributes combo gắn thêm như `load_products`), `parent_of` con → cha,
    `available` / `taxonomy` / `destination` như `CatalogUnits.to_index`. Text lấy từ `load_texts` (T3+R)."""
    UnitIndex, _, Product, _, _ = _backend()
    records = catalog.reload_records(cfg, dataset)
    units, children, _, _ = catalog.group_children(records, cfg.catalog.search_unit_variants)
    manual = catalog.source_manual_path(dataset)
    _, combo_attrs, _ = catalog.combo_enrichment(records, manual)
    items = catalog.read_items(dataset)
    ids = items["product_id"].tolist()
    by_id = {r["productId"]: r for r in units}
    missing = [pid for pid in ids if pid not in by_id]
    if missing:
        raise AppAdapterError(f"{len(missing)} search unit của items không có trong nguồn, ví dụ {missing[:3]} — `sb catalog build`")

    def product(rec: dict):
        extra = combo_attrs.get(rec["productId"])
        return Product.from_cdp({**rec, "attributes": {**(rec.get("attributes") or {}), **extra}} if extra else rec)

    products = [product(by_id[pid]) for pid in ids]
    parent_of = {k["productId"]: pid for pid, kids in children.items() for k in kids}
    tdf, _ = load_texts(cfg, dataset, "T3+R", need=len(ids))
    texts = dict(zip(tdf["product_id"], tdf["text"]))
    lost = [pid for pid in ids if pid not in texts]
    if lost:
        raise AppAdapterError(f"{len(lost)} unit không có text T3+R, ví dụ {lost[:3]} — `sb text --variant T3+R`")
    index = UnitIndex(units=products, taxonomy=np.array([p.taxonomy for p in products], dtype=object),
                      destination=np.array([p.destination for p in products], dtype=object),
                      available=np.array([bool(p.available) for p in products], dtype=bool),
                      recommendable=np.array([bool(p.available) for p in products], dtype=bool),
                      parent_of=parent_of, model_version=MODEL_VERSION)
    return AppCatalog(index=index, texts={pid: texts[pid] for pid in ids},
                      text_hash={pid: hashlib.sha256(texts[pid].encode("utf-8")).hexdigest() for pid in ids})


# ------------------------------------------------------------------ ProductBench: collection hình dạng production
def product_bench_status(cfg: SBenchConfig, cat: AppCatalog, *, collection: str = PRODUCT_BENCH) -> dict:
    """{n, matching, missing, stale}: object có đúng textHash / còn thiếu / text cũ so với catalog hiện tại."""
    _, _, _, _, W = _backend()
    client = W.WeaviateClient(cfg.weaviate.url, collection=collection, vector_index_type="hnsw")
    try:
        try:
            meta, _ = client.fetch(include_vectors=False)
        except Exception:  # noqa: BLE001 — collection chưa có
            return {"n": 0, "matching": 0, "missing": len(cat.texts), "stale": 0, "exists": False}
    finally:
        client.close()
    matching = sum(1 for pid, m in meta.items() if cat.text_hash.get(pid) == m.text_hash and m.model_version == MODEL_VERSION)
    return {"n": len(meta), "matching": matching, "missing": len(cat.texts) - matching,
            "stale": sum(1 for pid, m in meta.items() if pid in cat.text_hash and cat.text_hash[pid] != m.text_hash), "exists": True}


def load_product_bench(cfg: SBenchConfig, dataset: str, cat: AppCatalog, *, collection: str = PRODUCT_BENCH,
                       recreate: bool = False) -> dict:
    """Dựng `collection` bằng chính `WeaviateClient` của backend và nạp vector đã embed cho B0 (`vec_T3+R_cohere-v3.npy`).
    Đã đủ và đúng textHash thì không làm gì (trừ `recreate`). 0 lượt gọi Cohere."""
    _, _, _, _, W = _backend()
    status = product_bench_status(cfg, cat, collection=collection)
    if status["exists"] and not recreate and status["missing"] == 0 and status["stale"] == 0 and status["n"] == len(cat.texts):
        return {**status, "loaded": 0}
    ids, vecs, vmeta = vectors.read(dataset, "T3+R", "cohere-v3", "document")
    if vmeta.get("cache_model") != "embed-multilingual-v3.0":
        raise AppAdapterError(f"vector B0 do {vmeta.get('cache_model')} sinh — cần embed-multilingual-v3.0 (production)")
    if set(ids) != set(cat.texts):
        raise AppAdapterError(f"vector B0 có {len(ids)} id, catalog có {len(cat.texts)} — chạy lại `sb embed --variant T3+R --model cohere-v3`")
    if vmeta.get("text_sha256") and vmeta.get("text_sha256") != vectors.texts_digest([
            hashlib.sha1(cat.texts[p].encode("utf-8")).hexdigest() for p in ids]):
        pass   # digest của bench dùng text_hash riêng (textbuild.text_hash) — kiểm theo textHash từng object bên dưới
    client = W.WeaviateClient(cfg.weaviate.url, collection=collection, vector_index_type="hnsw")
    try:
        if status["exists"] and (recreate or status["stale"] or status["n"] != status["matching"]):
            r = client._client.delete(f"/v1/schema/{collection}")           # dựng lại từ đầu, không nạp dở
            if r.status_code not in (200, 204, 404):
                r.raise_for_status()
        client.ensure_collection()
        objects = []
        for pid, vec in zip(ids, vecs):
            p = cat.index.units[cat.index.idx[pid]]
            objects.append({"class": collection, "id": client.object_uuid(pid),
                            "properties": {"productId": pid, "modelVersion": MODEL_VERSION, "textHash": cat.text_hash[pid],
                                           **W.lexical_properties(p.name, cat.texts[pid])},
                            "vector": np.asarray(vec, dtype=np.float32).tolist()})
        client.insert(objects)
        meta, _ = client.fetch(include_vectors=False)
    finally:
        client.close()
    if len(meta) != len(ids):
        raise AppAdapterError(f"{collection}: {len(meta)} object sau khi nạp, cần {len(ids)}")
    return {**product_bench_status(cfg, cat, collection=collection), "loaded": len(objects)}


# ------------------------------------------------------------------ SearchProducts như production
class BenchQueryEmbedder:
    """`EmbedderPort` bọc CachedEmbedder của bench: embed_query = Cohere v3 `input_type=query` (cache sqlite)."""

    def __init__(self, emb: Any):
        self.emb = emb

    def embed_query(self, q: str) -> np.ndarray:
        return np.asarray(self.emb.embed([q], "query")[0], dtype=np.float32)

    def embed_docs(self, texts: list[str]) -> np.ndarray:
        raise AppAdapterError("adapter chỉ embed truy vấn; vector document lấy từ file .npy của B0")


APP_DEFAULTS = {"cutoff": 0.62, "candidate_k": 200, "hybrid": True, "normalize": True, "rrf_k": 60, "lexical_k": 10,
                "lexical_cutoff": 0.50, "min_coverage": 0.6, "lexical_candidate_k": 50}


def app_params(arm_app: dict | None) -> dict:
    """Tham số của arm APP: thiếu khoá nào thì lỗi (spec §1.5: mọi con số vào config, không có mặc định ngầm trong code)."""
    p = dict(arm_app or {})
    missing = [k for k in APP_DEFAULTS if k not in p]
    if missing:
        raise AppAdapterError(f"arm APP thiếu app.{', app.'.join(missing)} (xem arms/APP.*.yaml)")
    return p


@dataclass
class AppSearch:
    """Một `SearchProducts` dựng từ tham số arm; `search` trả (top_ids, top_scores, diagnostics)."""
    engine: Any
    params: dict
    calls: int = 0
    lexical_count: int = 0
    extra: dict[str, Any] = field(default_factory=dict)

    def search(self, q: str, *, limit: int) -> tuple[list[str], list[float], dict]:
        out = self.engine(q, limit=limit)
        self.calls += 1
        ids = [r["productId"] for r in out["results"]]
        scores = [float(r["score"]) for r in out["results"]]
        d = out.get("diagnostics") or {}
        return ids, scores, {"total": out.get("total"), "topScore": out.get("topScore"), "normalizedQuery": d.get("normalizedQuery"),
                             "lexicalCount": d.get("lexicalCount"), "lexicalCandidates": d.get("lexicalCandidates"),
                             "corrections": d.get("corrections"), "appliedAliases": d.get("appliedAliases"), "party": d.get("party")}


@dataclass
class AppContext:
    """Index + kho vector production-shape dùng chung cho mọi arm APP trong một lượt `sb run`."""
    cfg: SBenchConfig
    dataset: str
    cat: AppCatalog
    collection: str = PRODUCT_BENCH
    _client: Any = None
    _vs: Any = None

    @classmethod
    def open(cls, cfg: SBenchConfig, dataset: str, *, collection: str = PRODUCT_BENCH, ensure_loaded: bool = True) -> "AppContext":
        cat = build_app_catalog(cfg, dataset)
        if ensure_loaded:
            load_product_bench(cfg, dataset, cat, collection=collection)
        return cls(cfg=cfg, dataset=dataset, cat=cat, collection=collection)

    def vector_search(self):
        if self._vs is None:
            _, _, _, _, W = _backend()
            self._client = W.connect_weaviate(self.cfg.weaviate.url, grpc_port=self.cfg.weaviate.grpc_port,
                                              timeout_seconds=self.cfg.weaviate.query_timeout_s)
            self._vs = W.WeaviateVectorSearch(self._client, collection=self.collection, dimension=1024)
        return self._vs

    def close(self) -> None:
        if self._vs is not None:
            self._vs.close()
            self._vs = None
            self._client = None

    def make_search(self, arm_app: dict | None, embedder: Any) -> AppSearch:
        _, SearchProducts, _, HybridConfig, _ = _backend()
        p = app_params(arm_app)
        vs = self.vector_search()
        hybrid = HybridConfig(rrf_k=int(p["rrf_k"]), lexical_k=int(p["lexical_k"]),
                              lexical_cutoff=min(float(p["lexical_cutoff"]), float(p["cutoff"])),   # như build_recsys
                              min_coverage=float(p["min_coverage"])) if p["hybrid"] else None
        engine = SearchProducts(self.cat.index, vs, BenchQueryEmbedder(embedder), cutoff=float(p["cutoff"]),
                                candidate_k=int(p["candidate_k"]), lexical=vs if hybrid else None, hybrid=hybrid,
                                lexical_candidate_k=int(p["lexical_candidate_k"]), normalize=bool(p["normalize"]))
        return AppSearch(engine=engine, params=p)


def retrieve_app(arm, env, ctx: AppContext, embedder: Any, *, limit: int | None = None) -> list:
    """Top-k của mỗi câu gold qua `SearchProducts` thật; `top_scores` = cosine (trường `score` của contract)."""
    from .runner import Retrieved
    k = limit or env.k
    s = ctx.make_search(arm.app, embedder)
    out = []
    for g in env.gold:
        t0 = perf_counter()
        ids, scores, diag = s.search(g.text, limit=k)
        out.append(Retrieved(qid=g.qid, top_ids=ids, top_scores=scores, applied_filter=None,
                             latency_ms=(perf_counter() - t0) * 1000.0, extra=diag))
    return out
