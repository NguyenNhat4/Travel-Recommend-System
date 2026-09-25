from __future__ import annotations

import json
import uuid
from collections import Counter
from pathlib import Path

import pytest

from evaluation.search_bench import gold
from evaluation.search_bench.gold_schema import Child, PoolRow, file_sha256, read_pool_csv, write_pool_csv
from evaluation.search_bench.store import filters as F
from evaluation.search_bench.store.weaviate_store import Hit

FIXTURE = Path(__file__).parent / "fixtures" / "drafts_small.txt"
GOLD_SMALL = Path(__file__).parent / "fixtures" / "gold_small"
KEYS = {"pool": 16, "spa": 18, "kids_club": 11}


@pytest.fixture()
def slices(cfg):
    return list(cfg.gold.slices)


def test_parse_fixture(slices):
    ds = gold.parse_drafts(FIXTURE, slices, KEYS)
    assert [d.qid for d in ds] == [f"q{i:03d}" for i in range(1, 11)]
    neg = next(d for d in ds if d.slice == "amenity_negation")
    assert neg.filter == {"and": [{"eq": ["destination", "Đà Nẵng"]}, {"not": {"contains_any": ["amenity_ids", [16]]}}]}
    assert neg.filter_keys == {"and": [{"eq": ["destination", "Đà Nẵng"]}, {"not": {"contains_any": ["amenity_ids", ["pool"]]}}]}
    ooc = next(d for d in ds if d.slice == "out_of_catalog")
    assert ooc.expected_no_result and ooc.filter is None
    assert sum(d.expected_no_result for d in ds) == 1


@pytest.mark.parametrize("line, msg", [
    ("q\tkhong_co_slice", "slice lạ"),
    ("q\tmulti_constraint\t{bad", "JSON"),
    ("q\tmulti_constraint\t{\"contains_any\": [\"amenity_ids\", [\"hot_tub\"]]}", "khoá amenity lạ"),
    ("q\tout_of_catalog\t\tmaybe", "true/false"),
    ("chỉ một cột", "2–4 cột"),
    ("q\tmulti_constraint\t{\"or\": [{\"lte\": [\"unit_price_min\", 1]}, {\"gte\": [\"star_rating\", 4]}]}", "AND ở mức ngoài"),
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


def test_qid_num():
    assert gold.qid_num("q007") == 7 and gold.qid_num("c0202") == 202 and gold.qid_num("c9001") == 9001
    with pytest.raises(gold.GoldError):
        gold.qid_num("abc")


# ------------------------------------------------------------------ qid = case_id
def test_case_ids_for_maps_raw_and_override(tmp_path, slices):
    p = tmp_path / "d.txt"
    p.write_text("resort ở Nha Trang\tdest_type\nkhách sạn gần biển Mỹ Khê\tdest_type\n", encoding="utf-8")
    ds = gold.parse_drafts(p, slices, KEYS)
    raw = [{"case_id": "c0001", "query": "Resort ở Nha Trang", "slice": "dest_type"},
           {"case_id": "c0002", "query": "ks gần biển mỹ khê", "slice": "dest_type"}]
    over = {"c0002": {"verdict": "NEEDS_EDIT", "edited_query": "khách sạn gần biển Mỹ Khê"}}
    assert gold.case_ids_for(ds, raw, over) == ["c0001", "c0002"]
    with pytest.raises(gold.GoldError, match="không khớp case nào"):
        gold.case_ids_for(ds, raw, {})
    with pytest.raises(gold.GoldError, match="khớp"):
        gold.case_ids_for(ds, raw + [{"case_id": "c0009", "query": "resort ở nha trang", "slice": "dest_type"}], over)


def test_case_ids_on_committed_drafts(cfg):
    """drafts.txt đang commit map đủ, không trùng sang case_id (drafts_raw.tsv + overrides.tsv)."""
    ds = gold.parse_drafts(gold_dir() / "drafts.txt", list(cfg.gold.slices), {})
    cases = gold.read_draft_cases(gold_dir() / "drafts_raw.tsv")
    over = gold.read_overrides(gold_dir() / "overrides.tsv", {r["case_id"] for r in cases})
    ids = gold.case_ids_for(ds, cases, over)
    assert len(ids) == len(set(ids)) == len(ds)
    assert ids == sorted(ids, key=gold.qid_num)                         # drafts.txt ghi theo thứ tự case_id


def gold_dir() -> Path:
    from evaluation.search_bench import paths
    return paths.GOLD_DIR


# ------------------------------------------------------------------ filter: tách parent / child, viết thành chữ
def test_split_filter_moves_price_to_child(slices):
    ds = {d.slice: d for d in gold.parse_drafts(FIXTURE, slices, KEYS)}
    parent, child = gold.split_filter(ds["multi_constraint"].filter_keys)
    assert "unit_price" not in json.dumps(parent) and "unit_price_min" not in json.dumps(parent)
    assert child == {"lte": ["unit_price", 3000000]}
    F.validate(parent)
    gold.validate_child_filter(child)
    assert gold.split_filter(ds["amenity_negation"].filter_keys) == (ds["amenity_negation"].filter_keys, None)
    assert gold.split_filter(None) == (None, None)
    with pytest.raises(gold.GoldError):
        gold.validate_child_filter({"lte": ["star_rating", 3]})


def test_render_filter_text_matches_fixture_c9003():
    row = next(r for r in read_pool_csv(GOLD_SMALL / "pool_B.csv") if r.qid == "c9003")
    assert gold.render_filter_text(row.filter_json, row.child_filter_json) == row.filter_text


def test_render_filter_text_other_nodes():
    parent = {"and": [{"eq": ["variant", "hotel_property"]}, {"gte": ["star_rating", 4.5]},
                      {"contains_all": ["amenity_ids", ["pool"]]}, {"not": {"contains_any": ["amenity_ids", ["spa", 7]]}}]}
    txt = gold.render_filter_text(parent, {"lte": ["unit_price", 500000]}, {"pool": "hồ bơi", "spa": "spa", 7: "sauna"})
    assert txt == ("loại = hotel_property · hạng sao ≥ 4,5 · có tiện ích: hồ bơi · không có: spa, sauna · "
                   "giá ≤ 500.000 (kiểm ở cấp room)")
    assert gold.render_filter_text(None, None) == ""


# ------------------------------------------------------------------ pool rows
VIEW = gold.PoolView(
    items={"a": dict(product_id="a", name="Resort A", variant="hotel_property", destination="Đà Nẵng", star_rating=4.5,
                     amenity_ids=[1, 2, 3]),
           "b": dict(product_id="b", name="Vé B", variant="attraction", destination="Đà Nẵng", star_rating=None,
                     amenity_ids=[]),
           "c": dict(product_id="c", name="KS C", variant="hotel_property", destination="Huế", star_rating=3.0,
                     amenity_ids=[1]),
           "d": dict(product_id="d", name="Combo D", variant="combo", destination="Huế", star_rating=None,
                     amenity_ids=[])},
    snippets={"a": "Resort A ở Đà Nẵng", "b": "Vé B"},
    children={"a": [Child(id="r1", name="Deluxe"), Child(id="r2", name="Villa")], "c": []},
    amenity_label={1: "hồ bơi", 2: "spa", 3: "bàn làm việc"},
    amenity_order={1: (0, -10, 1), 2: (0, -5, 2), 3: (1, -1, 3)},
    key_to_id={"pool": 1, "spa": 2, "raw:ban-lam-viec": 3})


def test_pick_amenities_order_and_cap():
    assert gold.pick_amenities([1, 2, 3], VIEW, must={2}, query="khach san co ban lam viec") == ["spa", "bàn làm việc", "hồ bơi"]
    assert gold.pick_amenities([1, 2, 3], VIEW, must=set(), query="resort", k=2) == ["hồ bơi", "spa"]


def _hits(ids):
    return [Hit(rank=i, product_id=p, name=f"n{p}", destination="X", taxonomy="hotel", variant="hotel_property")
            for i, p in enumerate(ids, 1)]


def test_pool_rows_contract_roundtrip(tmp_path):
    d = gold.Draft("c0007", "resort Đà Nẵng dưới 1 triệu", "multi_constraint", {"lte": ["unit_price_min", 1000000]},
                   "", False, 1, filter_keys={"and": [{"eq": ["destination", "Đà Nẵng"]}, {"lte": ["unit_price_min", 1000000]}]})
    rows = gold.pool_rows(d, _hits(["a", "b", "c"]), _hits(["c", "d"]), VIEW)
    by = {r.product_id: r for r in rows}
    assert [r.product_id for r in rows] == ["a", "b", "c", "d"]
    assert (by["c"].source, by["c"].rank_dense, by["c"].rank_lex) == ("both", 3, 1)
    assert (by["a"].source, by["d"].source, by["d"].rank_dense) == ("dense", "lexical", None)
    assert by["a"].taxonomy == "hotel_property" and by["a"].star_rating == 4.5 and by["b"].star_rating is None
    assert [c.id for c in by["a"].children] == ["r1", "r2"] and by["b"].children == [] and by["d"].children == []
    assert by["a"].filter_json == {"eq": ["destination", "Đà Nẵng"]}
    assert by["a"].child_filter_json == {"lte": ["unit_price", 1000000]}
    assert by["a"].filter_text == "destination = Đà Nẵng · giá ≤ 1.000.000 (kiểm ở cấp room)"
    write_pool_csv(rows, tmp_path / "p.csv")
    assert (tmp_path / "p.csv").read_bytes().startswith(b"\xef\xbb\xbf")
    assert read_pool_csv(tmp_path / "p.csv") == rows
    with pytest.raises(gold.GoldError, match="items.parquet"):
        gold.pool_rows(d, _hits(["zz"]), [], VIEW)


class FakeStore:
    def __init__(self):
        self.calls = []

    def dense(self, physical, qvec, limit, filters=None):
        self.calls.append(("dense", limit, filters))
        return _hits(["a", "b", "c"][:limit])

    def bm25(self, physical, query, limit, *, fold_mode, filters=None):
        self.calls.append(("bm25", limit, filters))
        return _hits(["c", "d"][:limit])


class FakeEmb:
    def __init__(self):
        self.batches = []

    def embed(self, texts, input_type):
        self.batches.append((len(texts), input_type))
        import numpy as np
        return np.zeros((len(texts), 4), dtype="float32")


def test_build_pool_embeds_once_and_retrieves_with_full_filter(slices, monkeypatch):
    monkeypatch.setattr(gold.F, "to_weaviate", lambda node: node)            # nhìn thấy filter gửi xuống store
    ds = gold.parse_drafts(FIXTURE, slices, KEYS)
    st, emb = FakeStore(), FakeEmb()
    rows = gold.build_pool(ds, store=st, embedder=emb, physical="P", fold_mode="analyzer", depth=15,
                           query_input_type="query", view=VIEW)
    assert emb.batches == [(10, "query")]                                   # một lượt embed cho mọi draft
    assert len(rows) == 40 and {r.qid for r in rows} == {d.qid for d in ds}
    sent = [json.dumps(c[2]) for c in st.calls if c[2] is not None]
    assert len(sent) == 4 and any("unit_price_min" in s for s in sent)      # truy xuất dùng cả điều kiện giá
    s = gold.pool_summary(ds, rows)
    assert s["n_rows"] == 40 and s["empty_queries"] == [] and s["docs_per_query"] == {"p50": 4.0, "max": 4}


# ------------------------------------------------------------------ split
def _synthetic_rows(n_per_slice: dict[str, int], per_q: int = 5) -> list[PoolRow]:
    rows, q = [], 0
    for s, n in n_per_slice.items():
        for _ in range(n):
            q += 1
            rows += [PoolRow(qid=f"c{q:04d}", query=f"câu {q}", slice=s, product_id=f"p{q}_{k}", name=f"SP {k}",
                             taxonomy="hotel_property", source="dense", rank_dense=k + 1) for k in range(per_q)]
    return rows


def _build(rows_path: Path, **kw) -> gold.PoolBuild:
    from datetime import datetime
    return gold.PoolBuild(snapshot="2026-09-23", collection="products__T3+R__cohere_v3", depth=15, seed=42,
                          qid_mode="case", drafts_sha256=None, pool_sha256=file_sha256(rows_path), qids=[], empty_qids=[],
                          created_at=datetime(2026, 9, 25, 12, 0).astimezone(), **kw)


def test_split_invariants_and_balance():
    rows = _synthetic_rows({"dest_type": 12, "named_entity": 8, "no_diacritics": 8, "out_of_catalog": 4})
    a, b, shared = gold.split_pool(rows, overlap=8, seed=42)
    qa, qb = {r.qid for r in a}, {r.qid for r in b}
    assert qa & qb == set(shared) and qa | qb == {r.qid for r in rows} and len(shared) == 8
    slice_of = {r.qid: r.slice for r in rows}
    assert sorted(Counter(slice_of[q] for q in shared).items()) == \
        [("dest_type", 3), ("named_entity", 2), ("no_diacritics", 2), ("out_of_catalog", 1)]
    only_a, only_b = qa - set(shared), qb - set(shared)
    assert abs(len(only_a) - len(only_b)) <= 1
    for s in ("dest_type", "named_entity", "no_diacritics", "out_of_catalog"):
        assert abs(sum(slice_of[q] == s for q in only_a) - sum(slice_of[q] == s for q in only_b)) <= 1
    assert all(r.is_overlap == (r.qid in shared) for r in a + b)
    order_a = {q: [r.product_id for r in a if r.qid == q] for q in shared}
    order_b = {q: [r.product_id for r in b if r.qid == q] for q in shared}
    assert all(sorted(order_a[q]) == sorted(order_b[q]) for q in shared)
    assert any(order_a[q] != order_b[q] for q in shared)                   # mỗi người một thứ tự xáo
    a2, b2, shared2 = gold.split_pool(rows, overlap=8, seed=42)
    assert (a2, b2, shared2) == (a, b, shared)
    with pytest.raises(gold.GoldError, match="overlap"):
        gold.split_pool(rows, overlap=32, seed=42)


def test_write_split_meta_matches_files_and_is_deterministic(tmp_path):
    rows = _synthetic_rows({"dest_type": 6, "parent_child": 4})
    write_pool_csv(rows, tmp_path / "pool.csv")
    build = _build(tmp_path / "pool.csv")
    a, b, shared = gold.split_pool(rows, overlap=3, seed=42)
    out1, out2 = tmp_path / "o1", tmp_path / "o2"
    out1.mkdir()
    out2.mkdir()
    meta = gold.write_split(a, b, shared, build, out1)
    gold.write_split(a, b, shared, build, out2)
    for x in ("A", "B"):
        p = out1 / f"pool_{x}.csv"
        assert meta.files[x].sha256 == file_sha256(p) and meta.files[x].path == p.name
        assert p.read_bytes() == (out2 / p.name).read_bytes()
    ps = gold.load_pool_set(out1 / "pool_meta.json")
    assert ps.meta.overlap_qids == shared and len(ps.overlap_keys()) == 3 * 5
    (out1 / "labels").mkdir()
    (out1 / "labels" / "labels_A.csv").write_bytes(b"x")
    with pytest.raises(gold.GoldError, match="--force"):
        gold.write_split(a, b, shared, build, out1)
    gold.write_split(a, b, shared, build, out1, force=True)


def test_overlap_quota_small_slices():
    assert gold.overlap_quota({"a": 1, "b": 1, "c": 10}, 5) == {"a": 1, "b": 0, "c": 4}   # dư 1 → phần lẻ lớn nhất, hoà theo tên
    q = gold.overlap_quota({"a": 1, "b": 20}, 3)
    assert sum(q.values()) == 3 and q["a"] <= 1


def test_pool_build_roundtrip(tmp_path):
    (tmp_path / "pool.csv").write_bytes(b"x")
    b = _build(tmp_path / "pool.csv", slice_filter="dest_type")
    gold.write_pool_build(b, gold.pool_build_path(tmp_path / "pool.csv"))
    assert gold.pool_build_path(tmp_path / "pool.csv").name == "pool.build.json"
    assert gold.read_pool_build(tmp_path / "pool.build.json") == b
    with pytest.raises(gold.GoldError, match="sb gold pool"):
        gold.read_pool_build(tmp_path / "none.build.json")
    assert gold.snapshot_of({"path": "src/data_collection/data/snapshots/2026-09-23/products.jsonl"}, "jsonl") == "2026-09-23"
    assert gold.snapshot_of({"path": "sample/products-sample.jsonl"}, "sample") == "sample"



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
    view = gold.load_pool_view(cfg, "sample", "T3+R")
    p = home / "d.txt"
    p.write_text("resort Đà Nẵng\tdest_type\t{\"eq\": [\"destination\", \"Đà Nẵng\"]}\nVinWonders\tnamed_entity\n", encoding="utf-8")
    ds = gold.parse_drafts(p, list(cfg.gold.slices), key_idx)
    name = f"Products__itg_{uuid.uuid4().hex[:10]}"
    st = WeaviateStore(cfg.weaviate)
    try:
        mode = st.create_collection(name, description={})
        st.load(name, items, dict(zip(ids, texts["text"])), ids, vecs, fold_mode=mode)
        emb = CachedEmbedder(fake, EmbeddingCache(home / "c.sqlite"))
        rows = gold.build_pool(ds, store=st, embedder=emb, physical=name, fold_mode=mode, depth=5,
                               query_input_type="query", view=view)
    finally:
        if st.exists(name):
            st.drop(name)
        st.close()
    q1 = [r for r in rows if r.qid == "q001"]
    assert q1 and {r.destination for r in q1} == {"Đà Nẵng"}              # filter áp cho cả dense lẫn BM25
    q2 = [r for r in rows if r.qid == "q002"]
    assert 5 <= len(q2) <= 10 and any("VinWonders" in r.name for r in q2)  # BM25 bắt tên riêng
    assert all(r.snippet for r in rows) and all(len(r.amenities) <= gold.AMENITIES_SHOWN for r in rows)
    hotels = [r for r in rows if r.taxonomy == "hotel_property"]
    assert all(r.children == view.children.get(r.product_id, []) for r in hotels)
    assert all(not r.children for r in rows if r.taxonomy != "hotel_property")
    write_pool_csv(rows, home / "pool.csv")
    assert read_pool_csv(home / "pool.csv") == rows
