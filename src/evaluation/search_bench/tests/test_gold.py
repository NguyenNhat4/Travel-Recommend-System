from __future__ import annotations

import uuid
from pathlib import Path

import pandas as pd
import pytest

from evaluation.search_bench import gold
from evaluation.search_bench.store.weaviate_store import Hit

FIXTURE = Path(__file__).parent / "fixtures" / "drafts_small.txt"
KEYS = {"pool": 16, "spa": 18, "kids_club": 11}


@pytest.fixture()
def slices(cfg):
    return list(cfg.gold.slices)


def test_parse_fixture(slices):
    ds = gold.parse_drafts(FIXTURE, slices, KEYS)
    assert [d.qid for d in ds] == [f"q{i:03d}" for i in range(1, 11)]
    neg = next(d for d in ds if d.slice == "amenity_negation")
    assert neg.filter == {"and": [{"eq": ["destination", "Đà Nẵng"]}, {"not": {"contains_any": ["amenity_ids", [16]]}}]}
    ooc = next(d for d in ds if d.slice == "out_of_catalog")
    assert ooc.expected_no_result and ooc.filter is None
    assert sum(d.expected_no_result for d in ds) == 1


@pytest.mark.parametrize("line, msg", [
    ("q\tkhong_co_slice", "slice lạ"),
    ("q\tmulti_constraint\t{bad", "JSON"),
    ("q\tmulti_constraint\t{\"contains_any\": [\"amenity_ids\", [\"hot_tub\"]]}", "khoá amenity lạ"),
    ("q\tout_of_catalog\t\tmaybe", "true/false"),
    ("chỉ một cột", "2–4 cột"),
])
def test_parse_errors_have_line_numbers(tmp_path, slices, line, msg):
    p = tmp_path / "d.txt"
    p.write_text("# đầu\n\nok\tdest_type\n" + line + "\n", encoding="utf-8")
    with pytest.raises(gold.GoldError, match=rf"d.txt:4: .*{msg}"):
        gold.parse_drafts(p, slices, KEYS)


def test_parse_rejects_duplicates_and_missing(tmp_path, slices):
    p = tmp_path / "d.txt"
    p.write_text("a\tdest_type\nA\tdest_type\n", encoding="utf-8")
    with pytest.raises(gold.GoldError, match="trùng"):
        gold.parse_drafts(p, slices, KEYS)
    with pytest.raises(gold.GoldError, match="Người A"):
        gold.parse_drafts(tmp_path / "none.txt", slices, KEYS)


def _hits(ids):
    return [Hit(rank=i, product_id=p, name=f"n{p}", destination="X", taxonomy="hotel", variant="hotel_property")
            for i, p in enumerate(ids, 1)]


def test_pool_rows_union_ranks_and_stable_shuffle():
    d = gold.Draft("q007", "q", "dest_type", None, "", False, 1)
    rows = gold.pool_rows(d, _hits(["a", "b", "c"]), _hits(["c", "d"]), seed=42)
    by = {r["product_id"]: r for r in rows}
    assert set(by) == {"a", "b", "c", "d"}
    assert (by["c"]["from"], by["c"]["rank_dense"], by["c"]["rank_lex"]) == ("both", 3, 1)
    assert (by["a"]["from"], by["d"]["from"]) == ("dense", "lexical") and by["d"]["rank_dense"] is None
    assert all(r["label"] == "" for r in rows)
    again = gold.pool_rows(d, _hits(["a", "b", "c"]), _hits(["c", "d"]), seed=42)
    assert [r["product_id"] for r in rows] == [r["product_id"] for r in again]


class FakeStore:
    def __init__(self):
        self.calls = []

    def dense(self, physical, qvec, limit, filters=None):
        self.calls.append(("dense", limit, filters is not None))
        return _hits([f"d{i}" for i in range(limit)])

    def bm25(self, physical, query, limit, *, fold_mode, filters=None):
        self.calls.append(("bm25", limit, filters is not None))
        return _hits([f"d{i}" for i in range(0, 2 * limit, 2)])


class FakeEmb:
    def __init__(self):
        self.batches = []

    def embed(self, texts, input_type):
        self.batches.append((len(texts), input_type))
        import numpy as np
        return np.zeros((len(texts), 4), dtype="float32")


def test_build_pool_embeds_once_and_applies_filter(slices, cfg):
    ds = gold.parse_drafts(FIXTURE, slices, KEYS)
    st, emb = FakeStore(), FakeEmb()
    df = gold.build_pool(ds, store=st, embedder=emb, physical="P", fold_mode="analyzer", depth=15,
                         query_input_type="query", seed=cfg.run.seed)
    assert emb.batches == [(10, "query")]                          # một lượt embed cho mọi draft
    assert list(df.columns) == gold.POOL_COLUMNS
    assert df.groupby("qid").size().tolist() == [22] * 10          # 15 dense ∪ 15 bm25 (8 trùng) = 22
    with_filter = [c for c in st.calls if c[2]]
    assert len(with_filter) == 4                                    # 2 draft có filter × (dense + bm25)
    s = gold.pool_summary(ds, df)
    assert s["n_rows"] == 220 and s["empty_queries"] == []


def _synthetic_pool(n_per_slice: dict[str, int]) -> pd.DataFrame:
    rows, q = [], 0
    for s, n in n_per_slice.items():
        for _ in range(n):
            q += 1
            rows += [{"qid": f"q{q:03d}", "slice": s, "product_id": f"p{q}_{k}"} for k in range(3)]
    return pd.DataFrame(rows)


def test_split_invariants():
    df = _synthetic_pool({"dest_type": 12, "named_entity": 8, "no_diacritics": 8, "out_of_catalog": 4})
    a, b, shared = gold.split_pool(df, overlap=8, seed=42)
    qa, qb, qall = set(a["qid"]), set(b["qid"]), set(df["qid"])
    assert qa & qb == set(shared) and qa | qb == qall and len(shared) == 8
    slices_of = df.drop_duplicates("qid").set_index("qid")["slice"]
    assert sorted(slices_of[shared].value_counts().to_dict().items()) == \
        [("dest_type", 3), ("named_entity", 2), ("no_diacritics", 2), ("out_of_catalog", 1)]
    only_a, only_b = qa - set(shared), qb - set(shared)
    assert all(int(x[1:]) % 2 == 1 for x in only_a) and all(int(x[1:]) % 2 == 0 for x in only_b)
    a2, b2, shared2 = gold.split_pool(df, overlap=8, seed=42)
    assert shared2 == shared and a2.equals(a) and b2.equals(b)
    with pytest.raises(gold.GoldError, match="overlap"):
        gold.split_pool(df, overlap=32, seed=42)


def test_overlap_quota_small_slices():
    assert gold.overlap_quota({"a": 1, "b": 1, "c": 10}, 5) == {"a": 1, "b": 0, "c": 4}   # dư 1 → phần lẻ lớn nhất, hoà theo tên
    q = gold.overlap_quota({"a": 1, "b": 20}, 3)
    assert sum(q.values()) == 3 and q["a"] <= 1


def test_csv_roundtrip(tmp_path):
    df = pd.DataFrame([{c: "" for c in gold.POOL_COLUMNS} | {"qid": "q001", "name": "Đà Nẵng", "rank_dense": 1}])
    gold.write_csv(df, tmp_path / "p.csv")
    assert (tmp_path / "p.csv").read_bytes().startswith(b"\xef\xbb\xbf")          # BOM cho Excel
    back = gold.read_pool(tmp_path / "p.csv")
    assert back.loc[0, "name"] == "Đà Nẵng" and back.loc[0, "qid"] == "q001"


# ------------------------------------------------------------------ integration: pool thật trên collection tạm
@pytest.mark.integration
def test_pool_on_weaviate_respects_filter(cfg, home):
    from evaluation.search_bench import catalog, textbuild
    from evaluation.search_bench.embed.cache import CachedEmbedder, EmbeddingCache
    from evaluation.search_bench.embed.fake import FakeEmbedder
    from evaluation.search_bench.store.weaviate_store import WeaviateStore
    catalog.build_catalog(cfg, "sample")
    texts, _ = textbuild.build_texts(cfg, "sample", "T3+R")
    items = catalog.read_items("sample")
    ids = texts["product_id"].tolist()
    fake = FakeEmbedder(cfg.model_cfg("fake").dim)
    vecs = fake.embed(texts["text"].tolist(), "document")
    key_idx = gold.load_key_index(catalog.paths.data_dir("sample") / "amenity_vocab.json")
    p = home / "d.txt"
    p.write_text("resort Đà Nẵng\tdest_type\t{\"eq\": [\"destination\", \"Đà Nẵng\"]}\nVinWonders\tnamed_entity\n", encoding="utf-8")
    ds = gold.parse_drafts(p, list(cfg.gold.slices), key_idx)
    name = f"Products__itg_{uuid.uuid4().hex[:10]}"
    st = WeaviateStore(cfg.weaviate)
    try:
        mode = st.create_collection(name, description={})
        st.load(name, items, dict(zip(ids, texts["text"])), ids, vecs, fold_mode=mode)
        emb = CachedEmbedder(fake, EmbeddingCache(home / "c.sqlite"))
        df = gold.build_pool(ds, store=st, embedder=emb, physical=name, fold_mode=mode, depth=5,
                             query_input_type="query", seed=cfg.run.seed)
    finally:
        if st.exists(name):
            st.drop(name)
        st.close()
    q1 = df[df["qid"] == "q001"]
    assert len(q1) and set(q1["destination"]) == {"Đà Nẵng"}          # filter áp cho cả dense lẫn BM25
    q2 = df[df["qid"] == "q002"]
    assert 5 <= len(q2) <= 10 and set(q2["from"]) <= {"dense", "lexical", "both"}
    assert any(q2["name"].str.contains("VinWonders"))                 # BM25 bắt tên riêng
