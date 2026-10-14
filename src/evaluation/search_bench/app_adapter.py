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
- Model khác Cohere v3 (05/10, Day 5 Search: model chốt e5-small): mỗi model một collection `ProductBench__<model>` nạp từ
  `vec_T3+R_<model>.npy` của bench, `modelVersion = <cache_model>:<text_builder_version>`, embedder truy vấn đúng model đó.
  `ProductBench` (không hậu tố) giữ nguyên cho Cohere v3.
- 06/10 (ma trận ablation): mọi núm của pipeline đi qua khối `app:` của arm — cờ `tone_normalize` / `taxonomy_strong_only` /
  `party_filter` của `SearchProducts`, kênh fuzzy + trọng số RRF theo nhánh của `HybridConfig`, và `retrieval_mode`
  (hybrid | dense | lexical). `lexical` = BM25-only qua đúng đường hybrid của use case: nhánh dense rỗng (`candidate_k = 0`
  → `near_vector` của adapter Weaviate trả `[]`), BM25 là danh sách xếp hạng duy nhất, cùng mask / filter / cutoff cosine.
  Field backend chưa có: giá trị "tắt" thì bỏ qua, giá trị bật thì lỗi "backend chưa có field …" (không đo nhầm).
  Arm có `rerank:` → cross-encoder offline chấm lại top-N (`rerank.py`, chỉ trong bench).

Mọi import backend đi qua tiền tố `src.backend.*` (use case tự import như vậy); không trộn với tiền tố `backend.` của
`textbuild._import_backend`.
"""
from __future__ import annotations

import dataclasses
import hashlib
import inspect
import json
import sys
from pathlib import Path
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any

import numpy as np

from . import catalog, paths, vectors
from .config import SBenchConfig
from .textbuild import load_texts

PRODUCT_BENCH = "ProductBench"
MODEL_VERSION = "embed-multilingual-v3.0:catalog-text-v2"      # như production (main.build_recsys)
PRODUCTION_MODEL = "cohere-v3"                                  # model bench tương ứng MODEL_VERSION


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


def app_collection(model: str) -> str:
    """Collection APP của một model bench: `ProductBench` cho Cohere v3 (như trước), `ProductBench__<model>` cho model khác."""
    return PRODUCT_BENCH if model == PRODUCTION_MODEL else f"{PRODUCT_BENCH}__{model.replace('-', '_')}"


def build_app_catalog(cfg: SBenchConfig, dataset: str, *, model_version: str = MODEL_VERSION) -> AppCatalog:
    """`Product` cho mọi search unit của dataset (attributes combo gắn thêm như `load_products`), `parent_of` con → cha,
    `available` / `taxonomy` / `destination` như `CatalogUnits.to_index`. Text lấy từ `load_texts` (T3+R).
    `model_version`: của model đang đo (`model_vectors(...)[3]`) — vào `UnitIndex.model_version` và `diagnostics`."""
    UnitIndex, _, Product, _, _ = _backend()
    records = catalog.reload_records(cfg, dataset)
    units, children, _, _ = catalog.group_children(records, cfg.catalog.search_unit_variants)
    manual = catalog.source_manual_path(dataset)
    combo_items, combo_attrs, _ = catalog.combo_enrichment(records, manual)
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
    # Thuộc tính lọc Phase A dựng KÈM phòng/chuyến con như `PostgresCatalogReader.load` (giá thấp nhất của con, tiện ích con,
    # sức chứa, danh sách con theo giá). Cờ combo includesFlight / includesHotel lấy từ `item_kind` của chính các thành phần
    # `combo_enrichment` vừa dựng (= `catalog.combo_items` mà production đọc: parse_combos + bản soát tay), không suy từ text.
    from src.backend.app.domain.catalog import UnitAttributes  # sys.path đã có repo root sau `_backend()`
    children_products = {pid: [Product.from_cdp(k) for k in kids] for pid, kids in children.items()}
    combo_kinds = {pid: [str(it["item_kind"]) for it in its if it.get("item_kind")] for pid, its in combo_items.items()}
    attrs = UnitAttributes.build(products, children_products, combo_kinds)
    tdf, _ = load_texts(cfg, dataset, "T3+R", need=len(ids))
    texts = dict(zip(tdf["product_id"], tdf["text"]))
    lost = [pid for pid in ids if pid not in texts]
    if lost:
        raise AppAdapterError(f"{len(lost)} unit không có text T3+R, ví dụ {lost[:3]} — `sb text --variant T3+R`")
    index = UnitIndex(units=products, taxonomy=np.array([p.taxonomy for p in products], dtype=object),
                      destination=np.array([p.destination for p in products], dtype=object),
                      available=np.array([bool(p.available) for p in products], dtype=bool),
                      recommendable=np.array([bool(p.available) for p in products], dtype=bool),
                      parent_of=parent_of, model_version=model_version, attrs=attrs)
    return AppCatalog(index=index, texts={pid: texts[pid] for pid in ids},
                      text_hash={pid: hashlib.sha256(texts[pid].encode("utf-8")).hexdigest() for pid in ids})


# ------------------------------------------------------------------ ProductBench: collection hình dạng production
def product_bench_status(cfg: SBenchConfig, cat: AppCatalog, *, collection: str = PRODUCT_BENCH,
                         model_version: str = MODEL_VERSION) -> dict:
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
    matching = sum(1 for pid, m in meta.items() if cat.text_hash.get(pid) == m.text_hash and m.model_version == model_version)
    return {"n": len(meta), "matching": matching, "missing": len(cat.texts) - matching,
            "stale": sum(1 for pid, m in meta.items() if pid in cat.text_hash and cat.text_hash[pid] != m.text_hash), "exists": True}


def model_vectors(dataset: str, model: str) -> tuple[list[str], Any, dict, str]:
    """(ids, vectors, meta, modelVersion) của vector document T3+R của `model`; Cohere v3 phải đúng model production."""
    ids, vecs, vmeta = vectors.read(dataset, "T3+R", model, "document")
    if model == PRODUCTION_MODEL:
        if vmeta.get("cache_model") != MODEL_VERSION.split(":")[0]:
            raise AppAdapterError(f"vector B0 do {vmeta.get('cache_model')} sinh — cần {MODEL_VERSION.split(':')[0]} (production)")
        return ids, vecs, vmeta, MODEL_VERSION
    if not vmeta.get("cache_model") or vmeta.get("text_builder_version") != MODEL_VERSION.split(":")[1]:
        raise AppAdapterError(f"vector {model}: cache_model {vmeta.get('cache_model')!r}, text {vmeta.get('text_builder_version')!r} — "
                              f"cần text {MODEL_VERSION.split(':')[1]} như production")
    return ids, vecs, vmeta, f"{vmeta['cache_model']}:{vmeta['text_builder_version']}"


def load_product_bench(cfg: SBenchConfig, dataset: str, cat: AppCatalog, *, collection: str = PRODUCT_BENCH,
                       recreate: bool = False, model: str = PRODUCTION_MODEL) -> dict:
    """Dựng `collection` bằng chính `WeaviateClient` của backend và nạp vector document đã embed của `model`
    (`vec_T3+R_<model>.npy`; mặc định B0 Cohere v3). Đã đủ và đúng textHash thì không làm gì (trừ `recreate`). 0 lượt gọi API."""
    _, _, _, _, W = _backend()
    ids, vecs, vmeta, model_version = model_vectors(dataset, model)
    status = product_bench_status(cfg, cat, collection=collection, model_version=model_version)
    if status["exists"] and not recreate and status["missing"] == 0 and status["stale"] == 0 and status["n"] == len(cat.texts):
        return {**status, "loaded": 0}
    if set(ids) != set(cat.texts):
        raise AppAdapterError(f"vector {model} có {len(ids)} id, catalog có {len(cat.texts)} — chạy lại `sb embed --variant T3+R --model {model}`")
    if vmeta.get("text_sha256") and vmeta.get("text_sha256") != vectors.texts_digest([
            hashlib.sha1(cat.texts[p].encode("utf-8")).hexdigest() for p in ids]):
        pass   # digest của bench dùng text_hash riêng (textbuild.text_hash) — kiểm theo textHash từng object bên dưới
    n = load_collection(cfg, cat, ids, vecs, collection=collection, model_version=model_version,
                        drop_first=status["exists"] and (recreate or status["stale"] or status["n"] != status["matching"]))
    return {**product_bench_status(cfg, cat, collection=collection, model_version=model_version), "loaded": n}


def load_collection(cfg: SBenchConfig, cat: AppCatalog, ids: list[str], vecs: Any, *, collection: str,
                    drop_first: bool, model_version: str = MODEL_VERSION) -> int:
    """Nạp `collection` trên Weaviate bench bằng `WeaviateClient` của backend từ (ids, vectors) cho trước — hình dạng như
    `Product` production (property BM25 fold ở app, uuid5). Trả số object đã nạp; sai số lượng sau nạp → lỗi."""
    _, _, _, _, W = _backend()
    unknown = [pid for pid in ids if pid not in cat.index.idx]
    if unknown:
        raise AppAdapterError(f"{len(unknown)} vector không có unit trong catalog, ví dụ {unknown[:3]}")
    client = W.WeaviateClient(cfg.weaviate.url, collection=collection, vector_index_type="hnsw")
    try:
        if drop_first:
            r = client._client.delete(f"/v1/schema/{collection}")           # dựng lại từ đầu, không nạp dở
            if r.status_code not in (200, 204, 404):
                r.raise_for_status()
        client.ensure_collection()
        objects = []
        for pid, vec in zip(ids, vecs):
            p = cat.index.units[cat.index.idx[pid]]
            objects.append({"class": collection, "id": client.object_uuid(pid),
                            "properties": {"productId": pid, "modelVersion": model_version, "textHash": cat.text_hash[pid],
                                           **W.lexical_properties(p.name, cat.texts[pid])},
                            "vector": np.asarray(vec, dtype=np.float32).tolist()})
        client.insert(objects)
        meta, _ = client.fetch(include_vectors=False)
        # Truy vấn ngay sau khi nạp lô lớn (3k object) từng cho thứ tự sai (01/10: dense có filter trả đúng tập nhưng theo
        # uuid trong lúc HNSW còn đang dựng) → chờ shard báo READY và hàng đợi index rỗng rồi mới trả về.
        wait_index_ready(client._client, collection)
        # 05/10: ~60 s đầu sau khi nạp, BM25 của Weaviate chấm điểm theo thống kê độ dài chưa cập nhật → thứ tự sai ở mọi câu
        # (lượt hybrid đo ngay sau nạp lệch 79–93/131 câu). Chờ kết quả BM25 của câu thăm dò đổi rồi đứng yên.
        wait_bm25_settled(client._client, collection)
    finally:
        client.close()
    if len(meta) != len(ids):
        raise AppAdapterError(f"{collection}: {len(meta)} object sau khi nạp, cần {len(ids)}")
    # 05/10: ba arm hybrid chạy trong ~25 s đầu sau khi nạp ProductBench_e5_small cho top-10 khác hẳn các arm cùng cấu hình chạy sau
    # (BM25 còn đang cập nhật inverted index dù vector index đã READY) → chờ thêm cho BM25 ổn định trước khi trả về.
    return len(objects)


def index_status(http: Any, collection: str) -> tuple[str | None, int | None]:
    """(vectorIndexingStatus, vectorQueueLength) của shard `collection` theo `GET /v1/nodes?output=verbose`; None khi không thấy."""
    r = http.get("/v1/nodes", params={"output": "verbose"})
    r.raise_for_status()
    for node in r.json().get("nodes") or []:
        for shard in node.get("shards") or []:
            if shard.get("class") == collection:
                return shard.get("vectorIndexingStatus"), shard.get("vectorQueueLength")
    return None, None


def wait_index_ready(http: Any, collection: str, *, timeout_s: float = 300.0, poll_s: float = 1.0,
                     sleep: Any = None) -> tuple[str | None, int | None]:
    """Chờ tới khi shard READY và `vectorQueueLength == 0`; quá `timeout_s` thì AppAdapterError (không đo trên index dở)."""
    import time
    sleep = sleep or time.sleep
    deadline = time.monotonic() + timeout_s
    while True:
        status, queue = index_status(http, collection)
        if status is None or (status == "READY" and not queue):
            return status, queue
        if time.monotonic() >= deadline:
            raise AppAdapterError(f"{collection}: index chưa sẵn sàng sau {timeout_s:.0f} s (status {status}, queue {queue})")
        sleep(poll_s)


BM25_PROBES = ("khach san nha trang", "ve may bay ha noi", "combo phu quoc", "vinwonders", "resort bai bien")


def bm25_snapshot(http: Any, collection: str, probes: tuple[str, ...] = BM25_PROBES) -> tuple:
    """(productId, score) top-10 BM25 (`nameAscii^2`, `searchTextAscii` — như backend) của từng câu thăm dò, qua GraphQL."""
    out = []
    for q in probes:
        gql = ('{ Get { %s(bm25: {query: %s, properties: ["nameAscii^2", "searchTextAscii"]}, limit: 10) '
               '{ productId _additional { score } } } }') % (collection, json.dumps(q))
        r = http.post("/v1/graphql", json={"query": gql})
        r.raise_for_status()
        body = r.json()
        if body.get("errors"):
            raise AppAdapterError(f"{collection}: BM25 thăm dò lỗi {body['errors'][:1]}")
        hits = (body.get("data") or {}).get("Get", {}).get(collection) or []
        out.append(tuple((h["productId"], round(float(h["_additional"]["score"]), 4)) for h in hits))
    return tuple(out)


def wait_bm25_settled(http: Any, collection: str, *, max_wait_s: float = 90.0, poll_s: float = 3.0, stable_polls: int = 2,
                      sleep: Any = None, clock: Any = None) -> dict:
    """Chờ BM25 của `collection` ổn định sau khi nạp: kết quả câu thăm dò **đổi** so với lần chụp đầu rồi giữ nguyên `stable_polls`
    lần liền. Không đổi trong `max_wait_s` → coi là đã ổn định từ đầu (collection nạp trước đó, thống kê đã có). Trả {changed, waited_s}."""
    import time
    sleep = sleep or time.sleep
    clock = clock or time.monotonic
    start = clock()
    first = last = bm25_snapshot(http, collection)
    changed, same = False, 0
    while clock() - start < max_wait_s:
        sleep(poll_s)
        cur = bm25_snapshot(http, collection)
        if cur != first:
            changed = True
        same = same + 1 if cur == last else 0
        last = cur
        if changed and same >= stable_polls:
            break
    return {"changed": changed, "waited_s": round(clock() - start, 1)}


# ------------------------------------------------------------------ catalog VM + vector Cloud (sb parity --mode weaviate)
def build_vm_catalog(database_url: str) -> AppCatalog:
    """`UnitIndex` + text từ Postgres qua chính `PostgresCatalogReader` của backend (catalog VM qua tunnel SSH) — đúng
    như `main.build_recsys`; text = `catalog-text-v2`, textHash như job `embed_products`."""
    _backend()
    try:
        from src.backend.app.infrastructure.vectors.postgres_store import PostgresCatalogReader
    except Exception as e:  # noqa: BLE001
        raise AppAdapterError(f"không import được PostgresCatalogReader: {type(e).__name__}: {e}") from None
    cu = PostgresCatalogReader(database_url).load()
    ids = [u.product_id for u in cu.units]
    texts = dict(zip(ids, cu.texts, strict=True))
    return AppCatalog(index=cu.to_index(MODEL_VERSION), texts=texts,
                      text_hash={pid: hashlib.sha256(texts[pid].encode("utf-8")).hexdigest() for pid in ids})


def fetch_cloud_vectors(url: str, api_key: str, *, collection: str, timeout_s: float = 60.0) -> tuple[dict, dict]:
    """(metadata, vectors) của mọi object trong `collection` — REST cursor của `WeaviateClient.fetch`, 0 Cohere."""
    _, _, _, _, W = _backend()
    client = W.WeaviateClient(url, collection=collection, api_key=api_key, timeout_seconds=timeout_s)
    try:
        return client.fetch(include_vectors=True)
    finally:
        client.close()


def parity_contexts(cfg: SBenchConfig, cat: AppCatalog, *, cloud_url: str, cloud_api_key: str, cloud_collection: str,
                    vm_collection: str, recreate: bool = False) -> tuple["AppContext", "AppContext", dict]:
    """Hai `AppContext` trên cùng catalog VM: A = `cloud_collection` trên Weaviate Cloud (đọc trực tiếp), B = `vm_collection`
    trên Weaviate bench nạp từ vector kéo về từ A. Trả thêm thống kê: object Cloud, unit VM có / không có vector Cloud,
    object Cloud không còn trong catalog VM (mồ côi), object thiếu property BM25."""
    meta, vecs = fetch_cloud_vectors(cloud_url, cloud_api_key, collection=cloud_collection)
    ids = [pid for pid in cat.index.idx if pid in vecs and vecs[pid].size]
    stats = {"cloud_objects": len(meta), "vm_units": len(cat.index.idx), "with_vector": len(ids),
             "without_vector": len(cat.index.idx) - len(ids), "orphans": len(set(meta) - set(cat.index.idx)),
             "missing_lexical": sum(1 for m in meta.values() if not m.lexical),
             "stale_text": sum(1 for pid in ids if meta[pid].text_hash != cat.text_hash[pid]),
             "model_versions": sorted({m.model_version for m in meta.values()})}
    if not ids:
        raise AppAdapterError(f"{cloud_collection}@Cloud không có vector nào cho catalog VM ({len(meta)} object)")
    status = product_bench_status(cfg, cat, collection=vm_collection)
    need = recreate or not status["exists"] or status["n"] != len(ids) or status["stale"] or status["n"] != status["matching"]
    stats["vm_loaded"] = load_collection(cfg, cat, ids, [vecs[p] for p in ids], collection=vm_collection,
                                         drop_first=status["exists"]) if need else 0
    a = AppContext(cfg=cfg, dataset="vm", cat=cat, collection=cloud_collection, weaviate_url=cloud_url, api_key=cloud_api_key,
                   grpc_port=443)
    b = AppContext(cfg=cfg, dataset="vm", cat=cat, collection=vm_collection)
    return a, b, stats


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
                "lexical_cutoff": 0.50, "min_coverage": 0.6, "lexical_candidate_k": 50,
                # 05/10 (fix/search): F1 lọc điểm đến suy từ câu, F2 bộ ngưỡng câu không dấu — giá trị = production hôm nay (tắt)
                "dest_filter": False, "dest_filter_fallback": True, "no_diacritics_mode": "off",
                # 05/10: query plan F3 phủ định tiện ích / F4 loại sản phẩm / F5 chiều bay / F6 giá-sao — mặc định tắt = production
                "negation_filter": False, "taxonomy_filter": False, "route_filter": False, "numeric_filter": False,
                "no_diacritics": {"lexical_k": 20, "lexical_cutoff": 0.0, "min_coverage": 0.4, "cutoff": None, "min_tokens": 3},
                # 06/10 (ma trận ablation): chuẩn hoá dấu thanh, F4 chỉ cue mạnh, số khách suy từ câu — mặc định tắt = production
                "tone_normalize": False, "taxonomy_strong_only": False, "party_filter": False,
                # kênh fuzzy (fuzzy_k 0 = tắt) + trọng số RRF theo nhánh (1.0 = RRF thường) — field của HybridConfig
                "fuzzy_k": 0, "fuzzy_candidate_k": 50, "fuzzy_min_sim": 0.75,
                "dense_weight": 1.0, "lexical_weight": 1.0, "fuzzy_weight": 1.0,
                # hybrid (dense + BM25) | dense (= hybrid: false) | lexical (BM25-only qua đường hybrid, nhánh dense rỗng)
                "retrieval_mode": "hybrid"}
#: khoá bắt buộc trong `app.no_diacritics` của arm yaml
NO_DIACRITICS_KEYS = ("lexical_k", "lexical_cutoff", "min_coverage", "cutoff", "min_tokens")
#: bốn cờ query plan (05/10) → kwargs cùng tên của `SearchProducts`
QUERY_PLAN_KEYS = ("negation_filter", "taxonomy_filter", "route_filter", "numeric_filter")
#: 06/10: ba cờ mới của `SearchProducts` → kwargs cùng tên (giá trị tắt = False)
ENGINE_FLAG_KEYS = ("tone_normalize", "taxonomy_strong_only", "party_filter")
#: 06/10: kênh fuzzy + trọng số RRF theo nhánh → field cùng tên của `HybridConfig` (domain/search/hybrid.py)
HYBRID_CHANNEL_KEYS = ("fuzzy_k", "fuzzy_candidate_k", "fuzzy_min_sim", "dense_weight", "lexical_weight", "fuzzy_weight")
RETRIEVAL_MODES = ("hybrid", "dense", "lexical")
#: 07/10 (contract 1.18.0): ba cờ TUỲ CHỌN của `SearchProducts` — F7 thời lượng, địa danh gazetteer → F1, entity gate cứng.
#: Vắng trong YAML ≡ False (tiền lệ khối `app.llm`): KHÔNG vào `APP_DEFAULTS` để 55 arm cũ, `config_hash` của chúng và
#: `regression/baseline_v1.json` giữ nguyên; vẫn đi qua `supported_kwargs` nên bật trên backend thiếu field thì lỗi.
V118_FLAG_KEYS = ("duration_filter", "poi_resolve", "entity_filter")
#: 13/10 (contract 1.30.0, plan docs/plan/2026-10-13-search-evidence-gate-no-answer.md): bốn cờ TUỲ CHỌN của `SearchProducts` +
#: `evidence_gate` (field HybridConfig). Vắng ≡ False như V118 → arm cũ giữ nguyên hash. `no_diacritics_mode` nhận thêm `restore`.
V128_FLAG_KEYS = ("duration_mask", "embed_residual", "unexplained_empty", "emit_background")
#: giá trị "không đổi hành vi" của từng núm mới — backend chưa có field mà arm để giá trị này thì bỏ qua, khác thì lỗi
NEUTRAL = {"tone_normalize": False, "taxonomy_strong_only": False, "party_filter": False,
           "fuzzy_k": 0, "dense_weight": 1.0, "lexical_weight": 1.0, "fuzzy_weight": 1.0,
           "duration_filter": False, "poi_resolve": False, "entity_filter": False,
           "duration_mask": False, "embed_residual": False, "unexplained_empty": False, "emit_background": False,
           "evidence_gate": False}


def app_params(arm_app: dict | None) -> dict:
    """Tham số của arm APP: thiếu khoá nào thì lỗi (spec §1.5: mọi con số vào config, không có mặc định ngầm trong code)."""
    p = dict(arm_app or {})
    missing = [k for k in APP_DEFAULTS if k not in p]
    if missing:
        raise AppAdapterError(f"arm APP thiếu app.{', app.'.join(missing)} (xem arms/APP.*.yaml)")
    nd = p.get("no_diacritics")
    if not isinstance(nd, dict) or any(k not in nd for k in NO_DIACRITICS_KEYS):
        raise AppAdapterError(f"arm APP: app.no_diacritics phải có đủ {NO_DIACRITICS_KEYS}")
    if p["no_diacritics_mode"] not in ("off", "relax", "restore"):
        raise AppAdapterError(f"arm APP: app.no_diacritics_mode = {p['no_diacritics_mode']!r} (off | relax | restore)")
    mode = p["retrieval_mode"]
    if mode not in RETRIEVAL_MODES:
        raise AppAdapterError(f"arm APP: app.retrieval_mode = {mode!r} ({' | '.join(RETRIEVAL_MODES)})")
    if bool(p["hybrid"]) != (mode != "dense"):
        raise AppAdapterError(f"arm APP: app.hybrid = {p['hybrid']} mâu thuẫn app.retrieval_mode = {mode!r} "
                              "(dense ⇔ hybrid: false; hybrid / lexical cần hybrid: true)")
    if int(p["fuzzy_k"]) < 0 or int(p["fuzzy_candidate_k"]) < 1 or not 0.0 <= float(p["fuzzy_min_sim"]) <= 1.0:
        raise AppAdapterError(f"arm APP: fuzzy_k ≥ 0, fuzzy_candidate_k ≥ 1, 0 ≤ fuzzy_min_sim ≤ 1 (đang {p['fuzzy_k']}, "
                              f"{p['fuzzy_candidate_k']}, {p['fuzzy_min_sim']})")
    if any(float(p[k]) < 0 for k in ("dense_weight", "lexical_weight", "fuzzy_weight")):
        raise AppAdapterError("arm APP: dense_weight / lexical_weight / fuzzy_weight phải ≥ 0")
    if mode == "dense" and any(p[k] != NEUTRAL[k] for k in ("fuzzy_k", "dense_weight", "lexical_weight", "fuzzy_weight")):
        raise AppAdapterError("arm APP: retrieval_mode dense không có nhánh fuzzy / RRF — fuzzy_k phải 0, trọng số phải 1.0")
    if mode == "lexical" and float(p["lexical_weight"]) <= 0:
        raise AppAdapterError("arm APP: retrieval_mode lexical cần lexical_weight > 0 (BM25 là danh sách xếp hạng duy nhất)")
    # 07/10 (contract 1.18.0): cờ tuỳ chọn — vắng = False; có thì phải là bool thật (YAML `true`/`false`, không phải 1/"on")
    for k in (*V118_FLAG_KEYS, *V128_FLAG_KEYS, "evidence_gate"):
        p.setdefault(k, False)
        if not isinstance(p[k], bool):
            raise AppAdapterError(f"arm APP: app.{k} phải là true/false (đang {p[k]!r})")
    return p


def _init_names(cls: Any) -> set[str] | None:
    """Tên tham số khởi tạo của `cls` (dataclass: field init); None = nhận mọi kwargs (lớp giả trong test)."""
    if dataclasses.is_dataclass(cls):
        return {f.name for f in dataclasses.fields(cls) if f.init}
    params = inspect.signature(cls).parameters.values()
    if any(x.kind is inspect.Parameter.VAR_KEYWORD for x in params):
        return None
    return {x.name for x in params}


def _is_neutral(p: dict, key: str) -> bool:
    if key in ("fuzzy_candidate_k", "fuzzy_min_sim"):      # chỉ có tác dụng khi kênh fuzzy bật
        return int(p["fuzzy_k"]) == 0
    return p[key] == NEUTRAL[key]


def supported_kwargs(cls: Any, what: str, p: dict, keys: tuple[str, ...], cast: Any) -> dict:
    """kwargs `keys` (giá trị `cast(p[k])`) mà `cls` nhận. Backend chưa có field: giá trị tắt → bỏ qua (arm cũ chạy được trên
    backend cũ), giá trị bật → AppAdapterError nêu đúng field (không đo nhầm một arm "bật" mà thật ra không có tác dụng)."""
    names = _init_names(cls)
    out: dict = {}
    for k in keys:
        if names is None or k in names:
            out[k] = cast(k, p[k])
        elif not _is_neutral(p, k):
            raise AppAdapterError(f"backend chưa có field {what}.{k} (arm đặt app.{k} = {p[k]!r}) — chờ backend cài "
                                  f"(src/backend/app/…) rồi chạy lại arm này")
    return out


def _cast_channel(k: str, v: Any) -> Any:
    return int(v) if k in ("fuzzy_k", "fuzzy_candidate_k") else float(v)


#: khoá diagnostics chỉ nhắc lại cấu hình arm (giống nhau mọi câu) — không chép vào extra
DIAG_STATIC = frozenset({"searchMode", "approximate", "totalExact", "facetsExact", "fusion", "rrfK", "lexicalK", "lexicalCutoff",
                         "lexicalMinCoverage", "modelVersion", "fuzzyK", "fuzzyMinSim", "fuzzyCandidateK"})


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
        extra = {"total": out.get("total"), "topScore": out.get("topScore"), "normalizedQuery": d.get("normalizedQuery"),
                 "lexicalCount": d.get("lexicalCount"), "lexicalCandidates": d.get("lexicalCandidates"),
                 "corrections": d.get("corrections"), "appliedAliases": d.get("appliedAliases"), "party": d.get("party"),
                 # 05/10: F1 / F2 (contract 1.14.0)
                 "derivedDestinations": d.get("derivedDestinations"), "destinationFilter": d.get("destinationFilter"),
                 "queryProfile": d.get("queryProfile"), "appliedFilters": out.get("appliedFilters"),
                 # 05/10: query plan F3–F6 (diagnostics.queryPlan nguyên khối — khoá mở rộng 06/10 đi theo)
                 "queryPlan": d.get("queryPlan"),
                 # 06/10: kênh fuzzy (None khi backend / cấu hình không có)
                 "fuzzyCount": d.get("fuzzyCount"),
                 "cutoff": out.get("cutoff")}
        # 06/10: khoá diagnostics khác của từng câu (fuzzyCandidates, stageMs, filteredCount… và khoá backend thêm sau) đi
        # thẳng vào extra; khoá chỉ nhắc lại cấu hình arm thì bỏ.
        extra.update({k: v for k, v in d.items() if k not in extra and k not in DIAG_STATIC})
        if self.params.get("retrieval_mode") not in (None, "hybrid"):
            extra["retrievalMode"] = self.params["retrieval_mode"]
        return ids, scores, extra


@dataclass
class AppContext:
    """Index + kho vector production-shape dùng chung cho mọi arm APP trong một lượt `sb run`."""
    cfg: SBenchConfig
    dataset: str
    cat: AppCatalog
    collection: str = PRODUCT_BENCH
    model: str = PRODUCTION_MODEL       # model bench của vector trong collection (embedder truy vấn phải cùng model)
    cache_model: str = MODEL_VERSION.split(":")[0]
    dimension: int = 1024
    weaviate_url: str | None = None      # None → Weaviate của bench (cfg.weaviate); Cloud → URL + api_key (sb parity)
    api_key: str = ""
    grpc_port: int | None = None
    _client: Any = None
    _vs: Any = None

    @classmethod
    def open(cls, cfg: SBenchConfig, dataset: str, *, model: str = PRODUCTION_MODEL, collection: str | None = None,
             ensure_loaded: bool = True) -> "AppContext":
        _, vecs, vmeta, model_version = model_vectors(dataset, model)
        collection = collection or app_collection(model)
        cat = build_app_catalog(cfg, dataset, model_version=model_version)
        if ensure_loaded:
            load_product_bench(cfg, dataset, cat, collection=collection, model=model)
        return cls(cfg=cfg, dataset=dataset, cat=cat, collection=collection, model=model,
                   cache_model=vmeta["cache_model"], dimension=int(vecs.shape[1]))

    def vector_search(self):
        if self._vs is None:
            _, _, _, _, W = _backend()
            self._client = W.connect_weaviate(self.weaviate_url or self.cfg.weaviate.url, api_key=self.api_key,
                                              grpc_port=self.grpc_port or self.cfg.weaviate.grpc_port,
                                              timeout_seconds=self.cfg.weaviate.query_timeout_s)
            self._vs = W.WeaviateVectorSearch(self._client, collection=self.collection, dimension=self.dimension)
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
        # 06/10: kênh fuzzy + trọng số RRF theo nhánh → field HybridConfig; dùng cho CẢ bộ ngưỡng chung lẫn bộ câu không dấu
        # (đây là núm của kênh, không phải ngưỡng vớt: câu không dấu / gõ sai là nơi fuzzy có ích nhất).
        channel = supported_kwargs(HybridConfig, "HybridConfig", p, HYBRID_CHANNEL_KEYS, _cast_channel) if p["hybrid"] else {}
        if p["hybrid"]:   # 13/10: cổng bằng chứng theo cụm (vắng ≡ False)
            channel.update(supported_kwargs(HybridConfig, "HybridConfig", p, ("evidence_gate",), lambda _k, v: bool(v)))
        hybrid = HybridConfig(rrf_k=int(p["rrf_k"]), lexical_k=int(p["lexical_k"]),
                              lexical_cutoff=min(float(p["lexical_cutoff"]), float(p["cutoff"])),   # như build_recsys
                              min_coverage=float(p["min_coverage"]), **channel) if p["hybrid"] else None
        # F2 (05/10): bộ ngưỡng riêng cho câu không dấu — dựng như main.build_recsys (chỉ khi hybrid và mode relax)
        nd = p["no_diacritics"]
        relax = p["no_diacritics_mode"] == "relax"
        nd_cutoff = float(nd["cutoff"]) if (relax and nd.get("cutoff") is not None) else None
        no_diacritics = HybridConfig(
            rrf_k=int(p["rrf_k"]), lexical_k=int(nd["lexical_k"]),
            lexical_cutoff=min(float(nd["lexical_cutoff"]), nd_cutoff if nd_cutoff is not None else float(p["cutoff"])),
            min_coverage=float(nd["min_coverage"]), **channel) if hybrid and relax else None
        # 06/10: ba cờ mới của SearchProducts (tone / F4 cue mạnh / số khách) — backend chưa có field thì chỉ chạy được khi tắt
        flags = supported_kwargs(SearchProducts, "SearchProducts", p, ENGINE_FLAG_KEYS, lambda _k, v: bool(v))
        # 07/10 (contract 1.18.0): F7 duration / POI → F1 / entity gate — tuỳ chọn, vắng = False (app_params đã setdefault)
        flags.update(supported_kwargs(SearchProducts, "SearchProducts", p, V118_FLAG_KEYS, lambda _k, v: bool(v)))
        # 13/10 (contract 1.30.0): bốn cờ mới + phục hồi dấu (`no_diacritics_mode: restore`) — vắng = False
        flags.update(supported_kwargs(SearchProducts, "SearchProducts", p, V128_FLAG_KEYS, lambda _k, v: bool(v)))
        if p["no_diacritics_mode"] == "restore":
            flags["no_diacritics_restore"] = True
        # lexical: nhánh dense rỗng (near_vector limit 0 → []), BM25 là danh sách xếp hạng duy nhất; cosine của hit BM25 vẫn
        # tính từ vector kho → cutoff / vớt / mask / kiểm lại filter y như hybrid (use_cases._hybrid).
        candidate_k = 0 if p["retrieval_mode"] == "lexical" else int(p["candidate_k"])
        engine = SearchProducts(self.cat.index, vs, BenchQueryEmbedder(embedder), cutoff=float(p["cutoff"]),
                                candidate_k=candidate_k, lexical=vs if hybrid else None, hybrid=hybrid,
                                lexical_candidate_k=int(p["lexical_candidate_k"]), normalize=bool(p["normalize"]),
                                dest_filter=bool(p["dest_filter"]), dest_filter_fallback=bool(p["dest_filter_fallback"]),
                                no_diacritics=no_diacritics, no_diacritics_cutoff=nd_cutoff,
                                no_diacritics_min_tokens=int(nd["min_tokens"]),
                                # 05/10: query plan F3–F6, mỗi cờ một kwarg cùng tên
                                **{k: bool(p[k]) for k in QUERY_PLAN_KEYS}, **flags, **self.llm_kwargs(p))
        return AppSearch(engine=engine, params=p)

    def llm_kwargs(self, p: dict) -> dict:
        """06/10 (contract 1.17.0): khối TUỲ CHỌN `app.llm: {mode: on|shadow, min_confidence, cache_path}` — LLM fallback của
        query plan, PHÁT LẠI từ cache JSONL (`cache_only`, không gọi API; nạp cache bằng `src/backend/jobs/prewarm_llm_hypotheses.py`).
        Vắng khối → không truyền gì (≡ off). Câu không có trong cache → `queryPlan.llm.status = cache_miss`, giữ plan luật."""
        cfg = p.get("llm")
        if not cfg:
            return {}
        mode = cfg.get("mode")
        if mode not in ("on", "shadow") or not cfg.get("cache_path"):
            raise AppAdapterError("arm APP: app.llm cần mode (on | shadow) và cache_path")
        from src.backend.app.application.search.query_plan_llm import CachedQueryHypothesizer, HypothesisCache
        path = Path(cfg["cache_path"])
        path = path if path.is_absolute() else paths.repo_root() / path
        if not path.exists():
            raise AppAdapterError(f"arm APP: chưa có cache giả thuyết LLM {path} — chạy prewarm_llm_hypotheses trước")
        hyp = getattr(self, "_llm_hyp", {}).get(str(path))
        if hyp is None:
            hyp = CachedQueryHypothesizer(None, cache=HypothesisCache(100_000, path=path), cache_only=True)
            self._llm_hyp = {**getattr(self, "_llm_hyp", {}), str(path): hyp}
        return {"llm_fallback": mode, "llm_min_confidence": float(cfg.get("min_confidence", 0.75)),
                "llm_timeout_ms": int(cfg.get("timeout_ms", 60_000)), "hypothesizer": hyp}


def retrieve_app(arm, env, ctx: AppContext, embedder: Any, *, limit: int | None = None, reranker: Any = None) -> list:
    """Top-k của mỗi câu gold qua `SearchProducts` thật; `top_scores` = cosine (trường `score` của contract).

    Arm có `rerank:` (06/10, Phase D offline): engine trả top-`rerank.top_n`, cross-encoder chấm lại (`rerank.py`), cắt top-k;
    cosine đi theo unit. `latency_ms` = chỉ thời gian `SearchProducts` (so được với arm cha); thời gian rerank ở
    `extra.rerank` (`ms` tường của lượt này, `modelMs` ước lượng CPU lạnh từ cache). `reranker` tiêm được cho test."""
    from .runner import Retrieved
    k = limit or env.k
    rr = None
    if arm.rerank:
        from .rerank import RerankError, open_reranker, rerank_params
        try:
            rr = rerank_params(arm.rerank, k=k)
        except RerankError as e:
            raise AppAdapterError(f"arm {arm.id}: {e}") from None
        if arm.engine != "app":
            raise AppAdapterError(f"arm {arm.id}: rerank.parent_engine app cần engine: app")
    own = rr is not None and reranker is None
    if own:
        reranker = open_reranker(rr)
    s = ctx.make_search(arm.app, embedder)
    out = []
    try:
        for g in env.gold:
            t0 = perf_counter()
            ids, scores, diag = s.search(g.text, limit=rr["top_n"] if rr else k)
            latency = (perf_counter() - t0) * 1000.0
            if rr:
                ids, scores, diag = rerank_hits(reranker, rr, g.text, ids, scores, diag, ctx.cat.texts, k=k)
            out.append(Retrieved(qid=g.qid, top_ids=ids, top_scores=scores, applied_filter=applied_filter_of(diag),
                                 latency_ms=latency, extra=diag))
    finally:
        if own:
            reranker.close()
    return out


def rerank_hits(reranker: Any, rr: dict, query: str, ids: list[str], scores: list[float], diag: dict,
                texts: dict[str, str], *, k: int) -> tuple[list[str], list[float], dict]:
    """Sắp lại top-N của engine theo cross-encoder rồi cắt top-k; `extra.rerank` ghi model, số cặp chấm mới / từ cache,
    thời gian, điểm top-k và số unit mới vào top-k so với thứ tự engine."""
    text_q = query if rr["query"] == "raw" else (diag.get("normalizedQuery") or query)
    missing = [pid for pid in ids if pid not in texts]
    if missing:
        raise AppAdapterError(f"rerank: {len(missing)} unit không có text T3+R, ví dụ {missing[:3]}")
    res = reranker.rerank(text_q, ids, [texts[pid] for pid in ids])
    new_ids = [ids[i] for i in res.order][:k]
    new_scores = [scores[i] for i in res.order][:k]
    info = {"model": rr["model"], "topN": rr["top_n"], "inputN": len(ids), "query": rr["query"],
            "ms": round(res.ms, 2), "modelMs": round(res.model_ms, 2), "scored": res.n_scored, "cached": res.n_cached,
            "truncated": res.n_truncated, "scores": [round(x, 4) for x in res.scores[:k]],
            "movedIn": len(set(new_ids) - set(ids[:k]))}
    return new_ids, new_scores, {**diag, "rerank": info}


def applied_filter_of(diag: dict) -> dict | None:
    """Hard filter engine đã áp (`appliedFilters.hard`, 05–05/10) → node filter của bench (`store/filters.py`) để
    `filter_recall_loss` đếm nhãn liên quan bị filter suy ra loại. Mỗi khoá một node, nhiều khoá → `and`; None khi không lọc.

    - `destination` → `eq destination` (F1) · `taxonomy` → `eq taxonomy` (F4) · `origin` → `eq origin_city` (F5)
    - `mustNotAmenities` → `not contains_any features` (F3) · `mustNotBrands` → mỗi thương hiệu một `not eq brand` (F3)
    - `priceMin` / `priceMax` → `gte` / `lte unit_price_min` (F6)
    - bỏ qua `*Source`, `destinationCity`, `availableOnly` (không phải điều kiện trên items của bench).
    Tên trường `origin_city` / `features` theo items + `store/filters.py` (block B, 05/10)."""
    hard = ((diag.get("appliedFilters") or {}).get("hard") or {})
    nodes: list[dict] = []
    for key, fld in (("destination", "destination"), ("taxonomy", "taxonomy"), ("origin", "origin_city")):
        if hard.get(key):
            nodes.append({"eq": [fld, hard[key]]})
    must_not = [str(a) for a in (hard.get("mustNotAmenities") or []) if a]
    if must_not:
        nodes.append({"not": {"contains_any": ["features", must_not]}})
    for brand in (hard.get("mustNotBrands") or []):     # brand có thể null → not(eq) giữ cả unit không ghi thương hiệu
        if brand:
            nodes.append({"not": {"eq": ["brand", str(brand)]}})
    if hard.get("priceMin") is not None:
        nodes.append({"gte": ["unit_price_min", hard["priceMin"]]})
    if hard.get("priceMax") is not None:
        nodes.append({"lte": ["unit_price_min", hard["priceMax"]]})
    if not nodes:
        return None
    return nodes[0] if len(nodes) == 1 else {"and": nodes}
