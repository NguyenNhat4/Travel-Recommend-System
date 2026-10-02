from __future__ import annotations

import numpy as np
import pytest

from evaluation.search_bench import arms, vectors
from evaluation.search_bench.store import weaviate_store as ws


def test_collection_names():
    assert ws.collection_name("T3+R", "cohere-v3") == ("products__T3+R__cohere_v3", "Products__T3_R__cohere_v3")
    assert ws.collection_name("T3+DF+R", "fake", "sample")[1] == "Products__T3_R_DF__fake__sample"
    names = {ws.collection_name(v, m, d)[1] for v in ("T0", "T3+R", "T3+R+DF", "T2+R+w150") for m in ("cohere-v3", "cohere-v4", "bge-m3")
             for d in ("jsonl", "sample")}
    assert len(names) == 24 and all(ws.PHYSICAL_NAME.match(n) for n in names)


def test_properties_analyzer_vs_shadow():
    ana = {p.name: p for p in ws.build_properties("analyzer", "word")}
    assert set(ws.KEYWORD_PROPS) <= set(ana) and "name_ascii" not in ana
    assert all(ana[k].indexSearchable is False and ana[k].tokenization.value == "field" for k in ws.KEYWORD_PROPS)
    assert ana["name"].textAnalyzer is not None and ana["embed_text"].tokenization.value == "word"
    sh = {p.name: p for p in ws.build_properties("shadow", "word")}
    assert {"name_ascii", "embed_text_ascii"} <= set(sh) and sh["name"].textAnalyzer is None
    assert ws.bm25_query_properties("shadow") == ["name_ascii^2", "embed_text_ascii"]
    assert ws.bm25_query_properties("analyzer") == ["name^2", "embed_text"]


def test_object_properties():
    item = {"product_id": "p1", "taxonomy": "hotel", "variant": "hotel_property", "destination": "Đà Nẵng", "province": None,
            "brand": None, "parent_product_id": None, "name": "Khách sạn Đà Nẵng", "star_rating": np.float32(4.5),
            "unit_price_min": float("nan"), "ticketed": None, "family_friendly": True, "ocean_view": None, "available": True,
            "amenity_ids": np.array([3, 17], dtype=np.int16)}
    p = ws.object_properties(item, "Khách sạn Đà Nẵng — 4,5 sao", "analyzer")
    assert p["amenity_ids"] == [3, 17] and p["star_rating"] == pytest.approx(4.5)
    assert "province" not in p and "unit_price_min" not in p and "name_ascii" not in p
    s = ws.object_properties(item, "Khách sạn Đà Nẵng", "shadow")
    assert s["name_ascii"] == "khach san da nang"


def test_b0_arm_loads():
    a = arms.load_arm("B0")
    assert (a.text_variant, a.model, a.retrieval, a.query_input_type, a.embedding_types) == ("T3+R", "cohere-v3", "dense", "query", "float")


def test_arm_refs_rejected(tmp_path):
    base = (arms.paths.ARMS_DIR / "B0.yaml").read_text(encoding="utf-8")
    (tmp_path / "X.yaml").write_text(base.replace("id: B0", "id: X").replace("text_variant: T3+R", 'text_variant: "@E1a+R"'),
                                     encoding="utf-8")
    with pytest.raises(arms.ArmError, match="ngày 4"):
        arms.load_arm("X", tmp_path)
    (tmp_path / "Y.yaml").write_text(base.replace("id: B0", "id: Z"), encoding="utf-8")
    with pytest.raises(arms.ArmError, match="tên file"):
        arms.load_arm("Y", tmp_path)
    with pytest.raises(arms.ArmError, match="không có arm"):
        arms.load_arm("NOPE", tmp_path)


def test_vectors_roundtrip(home):
    v = np.eye(3, dtype=np.float32)
    meta = vectors.write("sample", "T3+R", "fake", "document", ["a", "b", "c"], v, extra={"x": 1})
    assert meta["file"] == "vec_T3+R_fake.npy" and meta["dim"] == 3
    ids, vv, m = vectors.read("sample", "T3+R", "fake", "document")
    assert ids == ["a", "b", "c"] and np.array_equal(vv, v) and m["x"] == 1
    with pytest.raises(vectors.VectorsMissing):
        vectors.read("sample", "T3+R", "fake", "query")
    assert vectors.stem("sample", "T3+R", "fake", "query").name == "vec_T3+R_fake__query"


def test_arm_yaml_errors_are_arm_errors(tmp_path):
    (tmp_path / "Bad.yaml").write_text("id: [unclosed" + chr(10), encoding="utf-8")
    with pytest.raises(arms.ArmError, match="YAML"):
        arms.load_arm("Bad", tmp_path)
    (tmp_path / "L.yaml").write_text("- a" + chr(10) + "- b" + chr(10), encoding="utf-8")
    with pytest.raises(arms.ArmError, match="mapping"):
        arms.load_arm("L", tmp_path)
    base = (arms.paths.ARMS_DIR / "B0.yaml").read_text(encoding="utf-8")
    (tmp_path / "V.yaml").write_text(base.replace("id: B0", "id: V").replace("text_variant: T3+R", "text_variant: T1+w150"),
                                     encoding="utf-8")
    with pytest.raises(arms.ArmError, match="T1"):
        arms.load_arm("V", tmp_path)
    (tmp_path / "N.yaml").write_text(base.replace("id: B0", "id: N").replace("text_variant: T3+R", "text_variant: T3+DF+R"),
                                     encoding="utf-8")
    assert arms.load_arm("N", tmp_path).text_variant == "T3+R+DF"


def test_tier1_embedding_arms_share_dense_retrieval_and_distinct_vector_identity():
    from evaluation.search_bench.config import load_config
    from evaluation.search_bench.embed import embedder_name
    cfg = load_config(None)
    names = {}
    for arm_id, dim in {"E2.e5s": 384, "E2.e5L": 1024, "E2.gte": 768, "E2.bge": 1024,
                        "E2.v4-1536": 1536, "E2.v4-1024": 1024,
                        "E2.v4-512": 512, "E2.v4-256": 256}.items():
        arm = arms.load_arm(arm_id)
        baseline = arms.load_arm("E2.e5")
        assert arm.text_variant == baseline.text_variant == "T3+R"
        assert arm.retrieval == baseline.retrieval == "dense"
        assert arm.filters == baseline.filters and arm.cutoff == baseline.cutoff
        assert arm.query_input_type == "query" and cfg.model_cfg(arm.model).dim == dim
        names[arm_id] = (embedder_name(cfg, arm.model), ws.collection_name(arm.text_variant, arm.model)[1])
    assert len({name for name, _ in names.values()}) == len(names)
    assert len({collection for _, collection in names.values()}) == len(names)
    assert cfg.model_cfg("e5-small").query_prefix == "query: "
    assert cfg.model_cfg("e5-small").passage_prefix == "passage: "
    e5_large = cfg.model_cfg("e5-large-instruct")
    assert e5_large.dim == 1024
    assert e5_large.query_prefix == (
        "Instruct: Given a web search query, retrieve relevant passages that answer the query\nQuery: "
    )
    assert e5_large.passage_prefix == ""
