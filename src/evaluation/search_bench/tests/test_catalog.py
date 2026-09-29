from __future__ import annotations

import json

import pyarrow.parquet as pq
import pytest

from evaluation.search_bench import catalog, paths


@pytest.fixture()
def built(cfg, home):
    stats = catalog.build_catalog(cfg, "sample")
    return stats, catalog.read_items("sample")


def test_sample_has_26_search_units(built):
    stats, df = built
    assert stats["n_search_units"] == 26 == len(df)
    assert stats["search_units_by_variant"] == {"hotel_property": 8, "attraction": 5, "combo": 5, "flight_route": 4, "golf": 4}
    assert not df["variant"].isin(["hotel_room", "flight"]).any()
    assert df["parent_product_id"].isna().all()
    assert stats["orphan_children"] == 0


def test_children_folded_into_parents(built, sample_records):
    _, df = built
    kids = {}
    for r in sample_records:
        p = (r.get("attributes") or {}).get("parentProductId")
        if p:
            kids.setdefault(p, []).append(r)
    for row in df.itertuples():
        own = next(r for r in sample_records if r["productId"] == row.product_id)
        assert row.n_children == len(kids.get(row.product_id, []))
        if row.variant == "hotel_property" and row.n_children:
            assert len(row.room_vocab) > 0
        if row.variant == "flight_route" and row.n_children:
            assert len(row.airlines) > 0
        if own.get("unitPrice") is not None:
            assert row.unit_price_min <= own["unitPrice"]


def test_items_schema_and_types(built, home):
    _, df = built
    schema = pq.read_schema(paths.data_dir("sample") / paths.ITEMS)
    assert schema == catalog.ITEM_SCHEMA
    ids = [i for xs in df["amenity_ids"] for i in xs]
    assert ids and all(1 <= i <= 32767 for i in ids)
    assert df["description_is_derived"].dtype == bool


def test_stats_written(built, home):
    stats, _ = built
    on_disk = json.loads((paths.data_dir("sample") / paths.STATS).read_text(encoding="utf-8"))
    assert on_disk["items_sha256"] == stats["items_sha256"]
    for k in ("search_units_by_taxonomy", "amenity", "description_derived_rate", "n_children", "records_sha256"):
        assert k in on_disk
    assert (paths.data_dir("sample") / paths.AMENITY_FUZZY_HITS).exists()


def test_rebuild_is_deterministic(cfg, built):
    stats, _ = built
    again = catalog.build_catalog(cfg, "sample")
    assert again["items_sha256"] == stats["items_sha256"]


def test_amenity_id_drift_guard(cfg, built, home):
    p = paths.data_dir("sample") / paths.AMENITY_VOCAB
    vocab = json.loads(p.read_text(encoding="utf-8"))
    a, b = list(vocab)[:2]
    vocab[a], vocab[b] = vocab[b], vocab[a]           # giả lập id của hai khoá bị đổi chỗ so với lần trước
    p.write_text(json.dumps(vocab, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(catalog.CatalogError, match="amenity id đổi"):
        catalog.build_catalog(cfg, "sample")
    stats = catalog.build_catalog(cfg, "sample", allow_id_drift=True)
    assert len(stats["amenity"]["id_drift"]["changed"]) == 2


def test_vocab(cfg, built):
    v = catalog.build_vocab_file(cfg, "sample")
    dests = {d["value"]: d["folded"] for d in v["destinations"]}
    assert dests.get("Đà Nẵng") == "da nang"
    assert v["filter_fields"]["taxonomy"] and v["filter_fields"]["amenity_keys"]
    assert all(set(a) >= {"id", "key", "label", "folded"} for a in v["amenities"])
    assert v["iata"] and all(len(x["code"]) == 3 for x in v["iata"])
    assert len(v["products"]) == 26


def test_vocab_refuses_changed_source(cfg, built, home):
    stats_p = paths.data_dir("sample") / paths.STATS
    stats = json.loads(stats_p.read_text(encoding="utf-8"))
    stats["records_sha256"] = "0" * 64
    stats_p.write_text(json.dumps(stats), encoding="utf-8")
    with pytest.raises(catalog.CatalogError, match="đã đổi"):
        catalog.build_vocab_file(cfg, "sample")


def test_fake_source_builds(cfg, home):
    stats = catalog.build_catalog(cfg, "fake")
    assert stats["source"] == "fake" and stats["n_search_units"] > 0
    assert paths.data_dir("fake").name == "_fake"
