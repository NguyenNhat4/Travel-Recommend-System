from __future__ import annotations

import pytest

from evaluation.search_bench import amenities, paths


@pytest.fixture(scope="module")
def matcher(cfg):
    seed = amenities.load_seed(paths.resolve_repo_path(cfg.catalog.amenity_seed_path))
    return amenities.TrigramAmenityMatcher(seed, cfg.catalog.amenity_fuzzy_min)


def test_trigrams_pg_trgm_padding():
    assert amenities.trigrams("Gym") == frozenset({"  g", " gy", "gym", "ym "})
    assert amenities.similarity("hồ bơi", "ho boi") == 1.0          # so sánh sau fold (bỏ dấu, lower)
    assert amenities.similarity("", "") == 0.0


@pytest.mark.parametrize("raw", [
    # rapidfuzz ratio > 0,6 map sai những chuỗi này trên snapshot 2026-09-21 — trigram không được khớp
    "Ban công", "Phòng tắm riêng", "Tủ lạnh", "Điện thoại", "Khu vực hút thuốc", "Đổi ngoại tệ", "Bếp riêng",
    "Thêm", "Phòng",
])
def test_known_false_friends_stay_raw(matcher, raw):
    kind, _ = matcher.match(raw)
    assert kind == "raw", raw


@pytest.mark.parametrize("raw, key", [
    ("Hồ bơi ngoài trời", "pool"),        # alias exact
    ("2 hồ bơi", "pool"),                 # cụm từ trong câu (vbench)
    ("Massages", "spa"),                  # trigram: 7/10
    ("Fitnes", "fitness"),                # trigram: gõ thiếu chữ
])
def test_positive_matches(matcher, raw, key):
    assert matcher.match(raw) == ("seed", key)


def test_fuzzy_hits_are_recorded(cfg, tmp_path):
    seed = amenities.load_seed(paths.resolve_repo_path(cfg.catalog.amenity_seed_path))
    m = amenities.TrigramAmenityMatcher(seed, cfg.catalog.amenity_fuzzy_min)
    m.match("Massages")
    m.match("Massages")
    m.match("Hồ bơi")                     # exact → không phải hit trigram
    hits = m.fuzzy_hits()
    assert [(h.folded, h.key) for h in hits] == [("massages", "spa")]
    n = m.write_hits(tmp_path / "hits.csv")
    assert n == 1
    lines = (tmp_path / "hits.csv").read_text(encoding="utf-8").splitlines()
    assert lines[0].startswith("raw_folded,") and lines[1].endswith(",2")


def test_id_drift():
    old = {"1": {"key": "pool"}, "2": {"key": "spa"}, "3": {"key": "raw:minibar"}}
    new = {"1": {"key": "pool"}, "2": {"key": "raw:minibar"}, "3": {"key": "spa"}}
    changed, removed = amenities.id_drift(old, new)
    assert changed == ["raw:minibar", "spa"] and removed == []
    assert amenities.id_drift(old, {"1": {"key": "pool"}}) == ([], ["raw:minibar", "spa"])
