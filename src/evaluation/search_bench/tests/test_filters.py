from __future__ import annotations

import json
import uuid

import numpy as np
import pandas as pd
import pytest

from evaluation.search_bench.store import filters as F


@pytest.mark.parametrize("bad, msg", [
    ({"xor": []}, "toán tử lạ"),
    ({"and": []}, "khác rỗng"),
    ({"eq": ["star_rating", 5]}, "eq star_rating"),
    ({"eq": ["family_friendly", "yes"]}, "eq family_friendly"),
    ({"in": ["destination", []]}, "in cần"),
    ({"contains_all": ["destination", ["x"]]}, "contains_all cần"),
    ({"lte": ["destination", 3]}, "lte cần"),
    ({"not": {"eq": ["brand", "Vinpearl"]}}, "not chỉ bọc"),          # brand có thể null
    ({"not": {"contains_all": ["amenity_ids", ["pool"]]}}, "not chỉ bọc"),
    ({"eq": "destination"}, "cần \\[trường"),
])
def test_validate_rejects(bad, msg):
    with pytest.raises(F.FilterError, match=msg):
        F.validate(bad)


def test_parse_accepts_spec_example():
    raw = json.dumps({"and": [{"eq": ["destination", "Nha Trang"]}, {"in": ["taxonomy", ["hotel", "combo"]]},
                              {"contains_all": ["amenity_ids", ["pool", 17]]}, {"not": {"contains_any": ["amenity_ids", [5]]}},
                              {"lte": ["unit_price_min", 3000000]}, {"gte": ["star_rating", 4]}]})
    assert F.parse(raw)["and"][0] == {"eq": ["destination", "Nha Trang"]}
    assert F.parse("") is None and F.parse(None) is None
    with pytest.raises(F.FilterError, match="JSON"):
        F.parse("{bad")


def test_resolve_amenity_keys():
    idx = F.amenity_key_index({"1": {"key": "pool"}, "2": {"key": "raw:ban-cong"}})
    node = {"and": [{"contains_all": ["amenity_ids", ["pool", "raw:ban-cong", 1]]}, {"eq": ["destination", "Đà Nẵng"]}]}
    assert F.resolve(node, idx) == {"and": [{"contains_all": ["amenity_ids", [1, 2]]}, {"eq": ["destination", "Đà Nẵng"]}]}
    with pytest.raises(F.FilterError, match="khoá amenity lạ"):
        F.resolve({"contains_any": ["amenity_ids", ["kids_club"]]}, idx)


def test_mask_null_semantics():
    df = pd.DataFrame({
        "destination": ["A", "B", "A"], "brand": ["V", None, None], "star_rating": [5.0, np.nan, 3.0],
        "family_friendly": [True, None, False], "amenity_ids": [[1, 2], [], None],
    })
    assert F.mask({"eq": ["brand", "V"]}, df).tolist() == [True, False, False]
    assert F.mask({"gte": ["star_rating", 3]}, df).tolist() == [True, False, True]       # NaN không khớp
    assert F.mask({"eq": ["family_friendly", False]}, df).tolist() == [False, False, True]
    assert F.mask({"contains_all": ["amenity_ids", [1, 2]]}, df).tolist() == [True, False, False]
    assert F.mask({"not": {"contains_any": ["amenity_ids", [1]]}}, df).tolist() == [False, True, True]
    assert F.mask({"or": [{"eq": ["destination", "B"]}, {"lt": ["star_rating", 4]}]}, df).tolist() == [False, True, True]
    assert F.mask(None, df).all()


def test_to_weaviate_builds():
    node = {"and": [{"not": {"eq": ["taxonomy", "hotel"]}}, {"not": {"contains_any": ["amenity_ids", [3]]}},
                    {"or": [{"gt": ["unit_price_min", 1.5]}, {"eq": ["ocean_view", True]}]}]}
    assert F.to_weaviate(node) is not None and F.to_weaviate(None) is None


# ------------------------------------------------------------------ integration: 50 filter ngẫu nhiên vs pandas
def random_filter(rng: np.random.Generator, df: pd.DataFrame) -> dict:
    ids = sorted({int(i) for xs in df["amenity_ids"] for i in xs})

    def vals(col):
        return [v for v in df[col].dropna().unique().tolist()]

    def leaf():
        kind = rng.integers(8)
        if kind == 0:
            col = str(rng.choice(["taxonomy", "variant", "destination", "province", "brand"]))
            pool = vals(col) or ["_"]
            return {"eq": [col, str(rng.choice(pool + ["không-có"]))]}
        if kind == 1:
            return {"eq": [str(rng.choice(F.BOOL_FIELDS)), bool(rng.integers(2))]}
        if kind == 2:
            col = str(rng.choice(["destination", "variant"]))
            return {"in": [col, [str(x) for x in rng.choice(vals(col), size=min(3, len(vals(col))), replace=False)]]}
        if kind in (3, 4):
            op = "contains_all" if kind == 3 else "contains_any"
            return {op: ["amenity_ids", [int(x) for x in rng.choice(ids, size=int(rng.integers(1, 3)), replace=False)]]}
        if kind == 5:
            col = str(rng.choice(F.NUMBER_FIELDS))
            q = float(np.nanquantile(pd.to_numeric(df[col], errors="coerce"), rng.uniform(0.1, 0.9)))
            return {str(rng.choice(F.RANGE_OPS)): [col, q]}
        if kind == 6:
            return {"not": {"contains_any": ["amenity_ids", [int(rng.choice(ids))]]}}
        return {"not": {"eq": ["destination", str(rng.choice(vals("destination")))]}}

    n = int(rng.integers(1, 4))
    if n == 1:
        return leaf()
    return {str(rng.choice(["and", "or"])): [leaf() for _ in range(n)]}


@pytest.fixture()
def fake_collection(cfg, home):
    from evaluation.search_bench import catalog
    from evaluation.search_bench.embed.fake import FakeEmbedder
    from evaluation.search_bench.store.weaviate_store import WeaviateStore
    catalog.build_catalog(cfg, "fake")
    items = catalog.read_items("fake")
    ids = items["product_id"].tolist()
    vecs = FakeEmbedder(cfg.model_cfg("fake").dim).embed(items["name"].tolist(), "document")
    name = f"Products__itf_{uuid.uuid4().hex[:10]}"
    st = WeaviateStore(cfg.weaviate)
    try:
        mode = st.create_collection(name, description={})
        st.load(name, items, dict(zip(ids, items["name"])), ids, vecs, fold_mode=mode)
        yield st, name, items
    finally:
        if st.exists(name):
            st.drop(name)
        st.close()


@pytest.mark.integration
def test_50_random_filters_match_pandas(fake_collection):
    """Spec Part 4 Done: filter trả đúng so với evaluator tham chiếu trên pandas (50 filter ngẫu nhiên)."""
    st, name, items = fake_collection
    rng = np.random.default_rng(42)
    empty_amen = int((items["amenity_ids"].str.len() == 0).sum())
    assert empty_amen > 0          # catalog fake có property không amenity → kiểm được ngữ nghĩa mảng rỗng
    checked = 0
    for i in range(50):
        node = random_filter(rng, items)
        F.validate(node)
        want = set(items.loc[F.mask(node, items), "product_id"])
        got = set(st.fetch_ids(name, F.to_weaviate(node), limit=len(items) + 10))
        assert got == want, f"filter #{i} {json.dumps(node, ensure_ascii=False)}: Weaviate {len(got)} ≠ pandas {len(want)}"
        assert st.count(name, F.to_weaviate(node)) == len(want)
        checked += 1
    assert checked == 50


@pytest.mark.integration
def test_negation_keeps_items_without_amenities(fake_collection):
    """"Khách sạn không có hồ bơi" = không ghi nhận amenity đó — sản phẩm mảng amenity rỗng phải có trong kết quả."""
    st, name, items = fake_collection
    aid = int(items["amenity_ids"].explode().dropna().astype(int).value_counts().index[0])
    node = {"not": {"contains_any": ["amenity_ids", [aid]]}}
    got = set(st.fetch_ids(name, F.to_weaviate(node), limit=len(items) + 10))
    empty = set(items.loc[items["amenity_ids"].str.len() == 0, "product_id"])
    assert empty and empty <= got
    assert got == set(items.loc[F.mask(node, items), "product_id"])
