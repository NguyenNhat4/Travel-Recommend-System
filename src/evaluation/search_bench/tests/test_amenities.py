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


@pytest.mark.parametrize("raw", [
    # 05/10 (D11): chuỗi phủ định và chuỗi khoảng cách không phải tiện ích của sản phẩm
    "Không có Thang máy Thang máy", "Không có Wi-Fi miễn phí trong tất cả các phòng!", "Không có Khu vực hút thuốc",
    "Sân Golf Đà Lạt 570 m", "Story Beach & Pool 190 m", "Chợ Đà Lạt 1,6 km", "Khoảng cách từ trung tâm thành phố : 1km",
    "Phòng / tầng không hút thuốc : no", "Hồ bơi ngoài trời\n\n(Tạm thời ngừng hoạt động)",
])
def test_negated_and_distance_strings_are_dropped(matcher, raw):
    assert amenities.is_not_amenity(raw)
    assert matcher.match(raw) == ("raw", "")


@pytest.mark.parametrize("raw", ["Thang máy", "Phòng không hút thuốc", "Hồ bơi 2 tầng", "Spa 24 giờ", "Wi-Fi miễn phí",
                                 "Phòng / tầng không hút thuốc : yes"])
def test_positive_strings_are_kept(raw):
    assert not amenities.is_not_amenity(raw)


def test_build_vocab_skips_dropped_strings(matcher):
    vocab, ids = amenities.build_vocab([["Không có Thang máy Thang máy", "Sân Golf Đà Lạt 570 m"], ["Thang máy"]],
                                       matcher, 1)
    assert ids[0] == []
    assert ids[1] == [vocab.ids["elevator"]]


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
