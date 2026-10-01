"""`mmr_select`: cap 2 món mỗi taxonomy là mặc định production (spec §4.7); `max_per_vertical=None` chỉ để harness đánh giá
offline lấy đủ k món (quyết định 30/09) — không đổi hành vi mặc định."""
import numpy as np

from src.backend.app.domain.recommendation.profile import MAX_PER_VERTICAL, mmr_select


def _space(n=8):
    rng = np.random.default_rng(0)
    E = rng.standard_normal((n, 4)).astype(np.float32)
    E /= np.linalg.norm(E, axis=1, keepdims=True)
    return E


def test_default_cap_is_two_per_taxonomy_and_none_removes_it():
    E = _space()
    score = np.linspace(1.0, 0.1, 8, dtype=np.float32)
    taxonomy = np.array(["hotel"] * 8)
    assert MAX_PER_VERTICAL == 2
    assert len(mmr_select(score, E, list(range(8)), taxonomy, k=6)) == 2
    assert len(mmr_select(score, E, list(range(8)), taxonomy, k=6, max_per_vertical=None)) == 6
    assert len(mmr_select(score, E, list(range(8)), taxonomy, k=6, max_per_vertical=3)) == 3
    assert mmr_select(score, E, [], taxonomy, k=6, max_per_vertical=None) == []
