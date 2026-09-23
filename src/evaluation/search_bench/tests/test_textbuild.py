from __future__ import annotations

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
    """Snapshot: T3+R phải trùng khít build_text của backend trên 5 search unit cố định của sample."""
    from backend.app.domain.catalog import Product, build_text
    df, meta = textbuild.build_texts(cfg, "sample", "T3+R")
    assert meta["text_builder"].startswith("app:backend:") and meta["complete"] and len(df) == 26
    by_id = {r["productId"]: r for r in sample_records}
    kids: dict[str, list] = {}
    for r in sample_records:
        p = (r.get("attributes") or {}).get("parentProductId")
        if p:
            kids.setdefault(p, []).append(r)
    for row in df.sort_values("product_id").head(5).itertuples():
        expected = build_text(Product.from_cdp(by_id[row.product_id]),
                              [Product.from_cdp(k) for k in kids.get(row.product_id, [])], max_desc_words=60)
        assert row.text == expected
        assert row.text_hash == textbuild.text_hash(row.text)


def test_missing_backend_builder_is_hard_error(cfg, sample_built, monkeypatch):
    monkeypatch.setattr(textbuild, "backend_text_builder", lambda: (None, "fallback"))
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
    snap = json.loads((Path(__file__).parent / "fixtures" / "text_snapshot_T3+R.json").read_text(encoding="utf-8"))["texts"]
    df, _ = textbuild.build_texts(cfg, "sample", "T3+R")
    got = dict(zip(df["product_id"], df["text"]))
    assert {pid: got[pid] for pid in snap} == snap


def test_fingerprint_change_forces_rebuild(cfg, sample_built, monkeypatch):
    df, meta = textbuild.load_texts(cfg, "sample", "T3+R")
    monkeypatch.setattr(textbuild, "builder_fingerprint", lambda c: "khac")
    calls = []
    real = textbuild.build_texts
    monkeypatch.setattr(textbuild, "build_texts", lambda *a, **k: calls.append(1) or real(*a, **k))
    textbuild.load_texts(cfg, "sample", "T3+R")
    assert calls == [1]
