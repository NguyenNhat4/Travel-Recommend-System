"""Mọi núm 1.16.0 (và ba cờ 1.18.0: duration / poi / entity) ở mặc định ≡ response 1.15.0 (trừ `queryPlan.confidence` /
`fallbackReasons`): chạy toàn bộ câu prewarm (gold active) + câu của fixture trên catalog tests/conftest.py, ở chế độ ANN và
hybrid, với mọi cờ query plan cũ tắt và bật."""
from pathlib import Path

import pytest

from src.backend.app.application.search import SearchProducts
from src.backend.app.application.search.prewarm import read_query_file
from src.backend.app.domain.search import HybridConfig
from src.backend.tests.conftest import FakeEmbedder

PREWARM = Path(__file__).resolve().parents[3] / "data" / "search_prewarm_queries.txt"
EXTRA = ("khách sạn Nha Trang không có hồ bơi", "resort 5 sao Phú Quốc dưới 2 triệu", "vé máy bay từ Hà Nội đến Nha Trang",
         "khách sạn, vé máy bay và vé tham quan ở Nha Trang", "khách sạn cho 3 người ở Nha Trang", "Vinwondrs Nha Trang",
         "combo không gồm vé máy bay", "nghỉ dưỡng Nha Trang", "thuỷ cung hoà bình",
         # ba câu gốc của lỗi production 07/10 (spec tong-hop-chinh-sua-luong-search-ota.md §1): cờ 1.18.0 tắt → không parse
         "vinwonder 3 ngay 2 dem", "khách sạn gần Hồ Hoàn Kiếm", "khách sạn Nha Trang 2 đêm")
#: Khoá của khối queryPlan ở contract 1.15.0 + hai khoá 1.16.0 luôn khai.
QP_115 = {"taxonomy", "route", "mustNot", "softDropped", "unresolved", "price", "star", "lexicalText", "applied",
          "revalidatedDrops", "emptyReason", "ignored"}
QP_ALWAYS = {"confidence", "fallbackReasons"}
#: Khối 1.18.0 — chỉ khai khi cờ của họ bật (mặc định tắt → không bao giờ có).
QP_118 = {"duration", "location", "entity"}
OLD_FLAGS = dict(negation_filter=True, taxonomy_filter=True, route_filter=True, numeric_filter=True, dest_filter=True)


def _queries():
    return [*read_query_file(PREWARM), *EXTRA]


def _strip(r):
    return {**r, "diagnostics": {k: v for k, v in r["diagnostics"].items() if k != "stageMs"}}


@pytest.mark.parametrize("old_flags", [False, True], ids=["plan_flags_off", "plan_flags_on"])
@pytest.mark.parametrize("hybrid", [False, True], ids=["ann", "hybrid"])
def test_new_knobs_at_default_add_only_confidence_keys(services, hybrid, old_flags):
    kw = dict(cutoff=0.0, **(OLD_FLAGS if old_flags else {}))
    if hybrid:
        kw.update(lexical=services["vectors"], hybrid=HybridConfig(lexical_cutoff=0.0))
    default = SearchProducts(services["index"], services["vectors"], FakeEmbedder(), **kw)
    if hybrid:   # đúng giá trị main.py dựng khi mọi biến SEARCH_* mới ở mặc định (fuzzy_min_sim 0.75 ≠ mặc định HybridConfig)
        kw["hybrid"] = HybridConfig(lexical_cutoff=0.0, fuzzy_k=0, fuzzy_candidate_k=50, fuzzy_min_sim=0.75,
                                    dense_weight=1.0, lexical_weight=1.0, fuzzy_weight=1.0)
    explicit = SearchProducts(services["index"], services["vectors"], FakeEmbedder(), tone_normalize=False,
                              taxonomy_strong_only=False, party_filter=False,
                              duration_filter=False, poi_resolve=False, entity_filter=False, **kw)
    queries = _queries()
    assert len(queries) >= 150
    for q in queries:
        a, b = default(q, limit=50), explicit(q, limit=50)
        assert _strip(a) == _strip(b), q
        d = a["diagnostics"]
        assert "fuzzyCount" not in d and "fuzzy" not in d["stageMs"], q
        qp = d.get("queryPlan", {})
        assert set(qp) <= QP_115 | QP_ALWAYS, (q, set(qp) - QP_115)
        assert not (QP_118 & set(qp)), (q, QP_118 & set(qp))
        assert "party" not in qp and "strength" not in qp.get("taxonomy", {}), q
        assert "duration" not in qp.get("applied", []) and "entity" not in qp.get("applied", []), q
        assert (a.get("appliedFilters") or {}).get("hard", {}).get("destinationSource") != "poi", q
        if not old_flags:   # cờ numeric bật thì giá suy từ câu được áp → matchedChildren là đúng hành vi 1.16.0
            assert all("matchedChildren" not in x for x in a["results"]), q
            assert set(qp.get("mustNot", {})) <= {"amenities", "brands"}, q
            assert "appliedFilters" not in a, q
        if qp:
            assert 0.0 <= qp["confidence"] <= 1.0 and isinstance(qp.get("fallbackReasons", []), list), q
