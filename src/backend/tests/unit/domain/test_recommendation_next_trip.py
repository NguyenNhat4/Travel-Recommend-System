"""FR-REC-04 / FR-REC-02 (chốt 2026-10-09, đề xuất `update-archive/2026-10-08-recsys-chuan-hoa-so-thich-giua-hai-chuyen.md`,
PR-B): không có chuyến mở → cos chuẩn hoá F14c + tối đa 2 món mỗi điểm đến; tag calibrate gắn với model + text builder."""
from datetime import date

import numpy as np

from src.backend.app.core.config import Settings
from src.backend.app.domain.catalog import TEXT_BUILDER_VERSION
from src.backend.app.domain.recommendation.profile import (
    MAX_PER_DESTINATION, SEMANTIC_CALIBRATION_MODEL_VERSION, SEMANTIC_Q_HIGH, SEMANTIC_Q_LOW, W_NEXT_LONG, W_NEXT_POP,
    W_NEXT_SHORT, W_LONG, W_POP, W_SHORT, ResolvedEvent, ScoreContext, build_profile, calibrated_similarity,
    calibration_applies, mmr_select, score_candidates,
)

TODAY = date(2026, 10, 9)
E = np.array([[1.0, 0.0, 0.0], [0.6, 0.8, 0.0], [0.0, 1.0, 0.0], [0.8, 0.6, 0.0]], dtype=np.float32)
TAX = np.array(["hotel", "hotel", "attraction", "flight"])
DEST = np.array(["Nha Trang", "Nha Trang", "Nha Trang", "Đà Nẵng"])


def closed_profile():
    p = build_profile([ResolvedEvent(0, "purchase", 300, "T", "R1", date(2025, 12, 20))], E, TAX, DEST, today=TODAY)
    assert p.active_trip is None
    return p


def test_calibration_tag_matches_the_configured_model_and_text_builder():
    assert SEMANTIC_CALIBRATION_MODEL_VERSION == f"{Settings.model_fields['embed_model'].default}:{TEXT_BUILDER_VERSION}"
    assert calibration_applies(SEMANTIC_CALIBRATION_MODEL_VERSION) and not calibration_applies("fake@123")
    assert (W_NEXT_SHORT, W_NEXT_POP, W_NEXT_LONG, MAX_PER_DESTINATION) == (0.50, 0.35, 0.15, 2)


def test_no_open_trip_uses_calibrated_similarity_only_when_enabled():
    p = closed_profile()
    pop = np.array([0.0, 0.2, 1.0, 0.5], dtype=np.float32)
    s, u = score_candidates(p, E, pop, next_trip_scoring=True)
    cal = np.clip((E @ p.u_long - SEMANTIC_Q_LOW) / (SEMANTIC_Q_HIGH - SEMANTIC_Q_LOW), 0, 1)
    np.testing.assert_allclose(s, W_NEXT_SHORT * cal + W_NEXT_POP * pop + W_NEXT_LONG * cal, rtol=1e-6)
    np.testing.assert_array_equal(calibrated_similarity(E @ p.u_long), cal.astype(np.float32))
    old, _ = score_candidates(p, E, pop)
    np.testing.assert_allclose(old, W_SHORT * (E @ u) + W_POP * pop + W_LONG * (E @ u), rtol=1e-6)


def test_open_trip_ignores_next_trip_scoring():
    p = build_profile([ResolvedEvent(0, "purchase", 3, "T", "R1", date(2026, 10, 20))], E, TAX, DEST, today=TODAY)
    pop = np.zeros(4, dtype=np.float32)
    a, _ = score_candidates(p, E, pop, next_trip_scoring=True)
    b, _ = score_candidates(p, E, pop)
    np.testing.assert_array_equal(a, b)


def test_origin_mask_still_applies_after_f14c():
    p = closed_profile()
    ctx = ScoreContext(taxonomy=TAX, origin_city=np.array(["", "", "", "Huế"], dtype=object), origin="Hà Nội")
    s, _ = score_candidates(p, E, np.zeros(4, dtype=np.float32), ctx, next_trip_scoring=True)
    assert s[3] == -np.inf and np.isfinite(s[:3]).all()


def test_mmr_caps_items_per_destination():
    score = np.array([0.9, 0.8, 0.7, 0.1], dtype=np.float32)
    free = mmr_select(score, E, [0, 1, 2, 3], TAX, 4, max_per_vertical=None)
    capped = mmr_select(score, E, [0, 1, 2, 3], TAX, 4, max_per_vertical=None, destination=DEST, max_per_destination=2)
    assert len(free) == 4
    assert sorted(capped) in ([0, 1, 3], [0, 2, 3])                      # 2 món Nha Trang + món Đà Nẵng
    assert sum(DEST[i] == "Nha Trang" for i in capped) == 2
