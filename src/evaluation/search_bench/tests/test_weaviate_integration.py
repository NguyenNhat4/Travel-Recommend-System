"""Integration: cần Weaviate của sbench (`docker compose -f evaluation/search_bench/docker/compose.yml up -d --wait`).
Chạy: `pytest -m integration evaluation/search_bench/tests`. Dùng collection tên riêng, xoá sau khi xong."""
from __future__ import annotations

import uuid

import numpy as np
import pytest

from evaluation.search_bench import catalog, textbuild
from evaluation.search_bench.embed.fake import FakeEmbedder
from evaluation.search_bench.store.weaviate_store import WeaviateStore

pytestmark = pytest.mark.integration


@pytest.fixture()
def loaded(cfg, home):
    catalog.build_catalog(cfg, "sample")
    texts, _ = textbuild.build_texts(cfg, "sample", "T3+R")
    items = catalog.read_items("sample")
    ids = texts["product_id"].tolist()
    vecs = FakeEmbedder(cfg.model_cfg("fake").dim).embed(texts["text"].tolist(), "document")
    name = f"Products__it_{uuid.uuid4().hex[:10]}"
    st = WeaviateStore(cfg.weaviate)
    try:
        mode = st.create_collection(name, description={"logical_name": "it", "n": len(ids)})
        n = st.load(name, items, dict(zip(ids, texts["text"])), ids, vecs, fold_mode=mode)
        yield st, name, ids, vecs, n, mode
    finally:
        if st.exists(name):
            st.drop(name)
        st.close()


def test_load_count_and_description(loaded):
    st, name, ids, _, n, mode = loaded
    assert n == len(ids) == 26 == st.count(name)
    d = st.description(name)
    assert d["logical_name"] == "it" and d["ascii_fold_mode"] == mode and d["vector_index"] == "flat"


def test_dense_returns_self_first(loaded):
    st, name, ids, vecs, _, _ = loaded
    for i in (0, 7, 25):
        hits = st.dense(name, vecs[i], 3)
        assert hits[0].product_id == ids[i] and hits[0].distance == pytest.approx(0.0, abs=1e-4)


def test_bm25_folds_diacritics(loaded):
    st, name, _, _, _, mode = loaded
    hits = st.bm25(name, "da nang", 5, fold_mode=mode)          # không dấu → phải ra sản phẩm Đà Nẵng
    assert hits and hits[0].destination == "Đà Nẵng"
    assert {h.destination for h in hits[:2]} == {"Đà Nẵng"}


def test_recreate_guard(loaded):
    st, name, *_ = loaded
    from evaluation.search_bench.store.weaviate_store import StoreError
    with pytest.raises(StoreError, match="--recreate"):
        st.create_collection(name, description={})
    assert np.isfinite(st.count(name))


def test_stopwords_none_keeps_vietnamese_syllables(loaded):
    """Preset 'en' mặc định của Weaviate bỏ 'an' → query 'an' không ra gì; config đặt none nên phải ra sản phẩm Hội An."""
    st, name, _, _, _, mode = loaded
    assert st.description(name)["bm25"]["stopwords_preset"] == "none"
    hits = st.bm25(name, "an", 5, fold_mode=mode)
    assert hits and any(h.destination == "Hội An" for h in hits)


def test_check_ready_requires_complete(loaded):
    st, name, ids, *_ = loaded
    from evaluation.search_bench.store.weaviate_store import StoreError
    with pytest.raises(StoreError, match="chưa nạp xong"):
        st.check_ready(name)
    st.mark_complete(name)
    d = st.check_ready(name)
    assert d["complete"] is True and d["n"] == len(ids)
    with pytest.raises(StoreError, match="items cũ"):
        st.check_ready(name, items_sha256="khac")


def test_check_ready_rejects_stale_text(loaded):
    st, name, *_ = loaded
    from evaluation.search_bench.store.weaviate_store import StoreError
    st.mark_complete(name, builder_fingerprint="old", combo_manual_sha256=None)
    assert st.check_ready(name, expected={"builder_fingerprint": "old"})
    with pytest.raises(StoreError, match="text cũ"):
        st.check_ready(name, expected={"builder_fingerprint": "new"})
