from __future__ import annotations

import json

import pytest

from evaluation.search_bench import catalog, textbuild


@pytest.mark.parametrize("raw, norm", [
    ("T3+R", "T3+R"),
    ("T3+DF+R", "T3+R+DF"),
    ("T2+w150+R", "T2+R+w150"),
    ("T3+w60", "T3"),                     # w60 là mặc định, không ghi trong tên
    ("T3+R+NUM", "T3+R+NUM"),
    ("T3+NUM+KV+R", "T3+R+KV+NUM"),
])
def test_normalize(raw, norm):
    assert textbuild.normalize_variant(raw) == norm


@pytest.mark.parametrize("bad, msg", [
    ("T1+w150", "T1 không có description"),
    ("T4", "base phải là"),
    ("T3+X", "modifier lạ"),
    ("T3+R+R", "lặp"),
    ("T3+w30+w150", "một modifier độ dài"),
])
def test_normalize_rejects(bad, msg):
    with pytest.raises(textbuild.VariantError, match=msg):
        textbuild.normalize_variant(bad)


@pytest.fixture()
def sample_built(cfg, home):
    catalog.build_catalog(cfg, "sample")


def test_t3r_is_backend_build_text(cfg, sample_built, sample_records):
    """T3+R gọi build_text của backend đúng như PostgresCatalogReader: con + combo_items + thuộc tính combo."""
    from backend.app.domain.catalog import TEXT_BUILDER_VERSION, Product, build_text
    df, meta = textbuild.build_texts(cfg, "sample", "T3+R")
    assert meta["text_builder"].startswith("app:backend:") and meta["complete"] and len(df) == 26
    assert meta["text_builder_version"] == TEXT_BUILDER_VERSION
    by_id = {r["productId"]: r for r in sample_records}
    kids: dict[str, list] = {}
    for r in sample_records:
        p = (r.get("attributes") or {}).get("parentProductId")
        if p:
            kids.setdefault(p, []).append(r)
    got = dict(zip(df["product_id"], df["text"]))
    non_combo = [pid for pid in sorted(got) if by_id[pid]["taxonomy"] != "combo"][:5]
    for pid in non_combo:                                   # không phải combo → không cần combo_items
        expected = build_text(Product.from_cdp(by_id[pid]), [Product.from_cdp(k) for k in kids.get(pid, [])], max_desc_words=60)
        assert got[pid] == expected
    combos = [pid for pid in got if by_id[pid]["taxonomy"] == "combo"]
    assert combos and all("Gồm:" in got[pid] for pid in combos)      # ô ROLLUP từ combo_items
    assert meta["combo_items"]["n_combos"] == len(combos) and meta["combo_items"]["n_items"] >= len(combos)


def test_combo_enrichment_matches_seed_pipeline(sample_records, tmp_path):
    from evaluation.search_bench.catalog import combo_enrichment
    items, attrs, info = combo_enrichment(sample_records, None)
    combos = [r["productId"] for r in sample_records if r["taxonomy"] == "combo"]
    assert set(items) == set(combos) == set(attrs)
    assert all(a.get("priceBasis") in ("per_package", "per_person") for a in attrs.values())
    assert info["manual_file"] is None and info["n_manual_rows"] == 0
    # bản soát tay (như combo_items_manual.jsonl đi kèm snapshot) thay dòng parse cùng (combo, position)
    cid = combos[0]
    manual = tmp_path / "combo_items_manual.jsonl"
    manual.write_text(json.dumps({"combo_product_id": cid, "position": 1, "label": "NHÃN SOÁT TAY", "item_kind": "attraction",
                                  "item_product_id": None, "quantity": 1.0, "unit": "vé", "is_optional": False,
                                  "source": "manual", "confidence": 0.9, "evidence": "test"}, ensure_ascii=False) + chr(10),
                      encoding="utf-8")
    items2, _, info2 = combo_enrichment(sample_records, manual)
    assert items2[cid][0]["label"] == "NHÃN SOÁT TAY" and items2[cid][0]["source"] == "manual"
    assert info2["n_manual_rows"] == 1 and info2["manual_file_rows"] == 1


def test_missing_backend_builder_is_hard_error(cfg, sample_built, monkeypatch):
    def boom():
        raise ImportError("không có backend")
    monkeypatch.setattr(textbuild, "_import_backend", boom)
    with pytest.raises(textbuild.TextBuildError, match="bắt buộc dùng bản production"):
        textbuild.build_texts(cfg, "sample", "T3+R")


def test_other_variants_not_yet(cfg, sample_built):
    with pytest.raises(textbuild.VariantNotImplemented, match="ngày 4"):
        textbuild.build_texts(cfg, "sample", "T1")


def test_load_texts_rebuilds_when_stale(cfg, sample_built, home):
    df, meta = textbuild.build_texts(cfg, "sample", "T3+R", limit=3)
    textbuild.write_texts("sample", df, meta)
    again, meta2 = textbuild.load_texts(cfg, "sample", "T3+R", need=10)     # file chỉ có 3 dòng → dựng lại đủ
    assert len(again) == 26 and meta2["complete"]
    same, _ = textbuild.load_texts(cfg, "sample", "T3+R", need=10)
    assert same["text_hash"].tolist() == again["text_hash"].tolist()
    stats = catalog.read_stats("sample")
    assert stats["text_builders"]["T3+R"].startswith("app:")


def test_t3r_snapshot(cfg, sample_built):
    """Snapshot cố định (tests/fixtures/text_snapshot_T3+R.json): đổi text builder backend hoặc config text → test đỏ,
    phải cập nhật snapshot có chủ đích (và chạy lại embed/regression)."""
    import json
    from pathlib import Path
    from backend.app.domain.catalog import TEXT_BUILDER_VERSION
    fx = json.loads((Path(__file__).parent / "fixtures" / "text_snapshot_T3+R.json").read_text(encoding="utf-8"))
    assert fx["text_builder_version"] == TEXT_BUILDER_VERSION          # builder backend đổi phiên bản → cập nhật có chủ đích
    snap = fx["texts"]
    df, _ = textbuild.build_texts(cfg, "sample", "T3+R")
    got = dict(zip(df["product_id"], df["text"]))
    assert {pid: got[pid] for pid in snap} == snap
    assert all(h == textbuild.text_hash(t) for t, h in zip(df["text"], df["text_hash"]))


def test_fingerprint_change_forces_rebuild(cfg, sample_built, monkeypatch):
    df, meta = textbuild.load_texts(cfg, "sample", "T3+R")
    monkeypatch.setattr(textbuild, "builder_fingerprint", lambda c: "khac")
    calls = []
    real = textbuild.build_texts
    monkeypatch.setattr(textbuild, "build_texts", lambda *a, **k: calls.append(1) or real(*a, **k))
    textbuild.load_texts(cfg, "sample", "T3+R")
    assert calls == [1]


def _seed_emulated_texts(cfg, seed_dir):
    """Đường production không cần DB: parse_combos.main + load_products.convert (như job seed ghi cdp.products /
    catalog.combo_items), rồi dựng text như PostgresCatalogReader.load() — JSONB round-trip, search unit theo view
    (level ∉ room/flight), con theo parentProductId, combo_items theo position, build_text với mặc định."""
    from datetime import date
    from backend.app.domain.catalog import Product, build_text
    from data_collection.seed import load_products, parse_combos
    parse_combos.main(["--data-dir", str(seed_dir)])
    rows = [json.loads(x) for x in (seed_dir / "products.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    combo_attrs = json.loads((seed_dir / "combo_attributes.json").read_text(encoding="utf-8"))
    loaded, _ = load_products.convert(rows, combo_attrs, date(2026, 9, 24))
    prods = {}
    for r in loaded:
        prods[r["product_id"]] = Product.from_cdp({
            "productId": r["product_id"], "name": r["name"], "taxonomy": r["taxonomy"], "destination": r["destination"],
            "description": r["description"], "attributes": json.loads(json.dumps(r["attributes"], sort_keys=True)),
            "unitPrice": r["unit_price"], "currency": r["currency"], "available": r["available"],
            "availableFrom": r["available_from"], "availableTo": r["available_to"], "imageUrl": r["image_url"]})
    children: dict[str, list] = {}
    for p in prods.values():
        if p.attributes.get("parentProductId"):
            children.setdefault(p.attributes["parentProductId"], []).append(p)
    items: dict[str, list] = {}
    for x in (seed_dir / "combo_items.jsonl").read_text(encoding="utf-8").splitlines():
        if x.strip():
            it = json.loads(x)
            items.setdefault(it["combo_product_id"], []).append(it)
    return {pid: build_text(p, children.get(pid, []), combo_items=sorted(items.get(pid, []), key=lambda i: i["position"]))
            for pid, p in prods.items() if (p.attributes.get("level") or "") not in ("room", "flight")}


def test_t3r_equals_production_path(cfg, home, tmp_path, monkeypatch, sample_records):
    """B0 = production (chốt 24/09): text của bench trùng khít text mà job seed + PostgresCatalogReader tạo, kể cả combo có
    dòng soát tay."""
    import shutil
    seed_dir = tmp_path / "seed"
    seed_dir.mkdir()
    shutil.copyfile(catalog.paths.resolve_repo_path(cfg.catalog.sample_path), seed_dir / "products.jsonl")
    combo = next(r["productId"] for r in sample_records if r["taxonomy"] == "combo")
    manual = seed_dir / catalog.COMBO_MANUAL
    manual.write_text(json.dumps({"combo_product_id": combo, "position": 1, "label": "NHÃN SOÁT TAY", "item_kind": "attraction",
                                  "item_product_id": None, "quantity": 1.0, "unit": "vé", "is_optional": False, "source": "manual",
                                  "confidence": 0.9, "evidence": "test"}, ensure_ascii=False) + chr(10), encoding="utf-8")
    want = _seed_emulated_texts(cfg, seed_dir)
    catalog.build_catalog(cfg, "sample")
    monkeypatch.setattr(catalog, "source_manual_path", lambda dataset: manual)
    df, meta = textbuild.build_texts(cfg, "sample", "T3+R")
    got = dict(zip(df["product_id"], df["text"]))
    assert got == want
    assert "NHÃN SOÁT TAY" in got[combo] and meta["combo_items"]["n_manual_rows"] == 1


def test_manual_change_forces_rebuild(cfg, sample_built, monkeypatch, tmp_path):
    textbuild.load_texts(cfg, "sample", "T3+R")
    manual = tmp_path / "combo_items_manual.jsonl"
    manual.write_text("", encoding="utf-8")
    monkeypatch.setattr(catalog, "source_manual_path", lambda dataset: manual)
    calls = []
    real = textbuild.build_texts
    monkeypatch.setattr(textbuild, "build_texts", lambda *a, **k: calls.append(1) or real(*a, **k))
    _, meta = textbuild.load_texts(cfg, "sample", "T3+R")
    assert calls == [1] and meta["combo_manual_sha256"] is not None


def test_jsonl_without_manual_is_an_error(cfg, home):
    jcfg = cfg.model_copy(update={"catalog": cfg.catalog.model_copy(update={"products_path": cfg.catalog.sample_path})})
    catalog.build_catalog(jcfg, "jsonl")                       # nguồn "jsonl" không có combo_items_manual.jsonl bên cạnh
    with pytest.raises(textbuild.TextBuildError, match="combo_items_manual"):
        textbuild.build_texts(jcfg, "jsonl", "T3+R")
