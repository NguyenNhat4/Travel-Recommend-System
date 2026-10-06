"""Câu gõ không dấu (slice `no_diacritics`): bộ ngưỡng vớt BM25 / cutoff riêng chỉ áp cho câu `is_unaccented`
(`SEARCH_NO_DIACRITICS_MODE=relax`); câu có dấu và chế độ `off` giữ nguyên hành vi hôm nay."""
import json

from jsonschema import Draft202012Validator

from src.backend.app.application.itinerary.tool_contracts import contracts
from src.backend.app.application.search import SearchProducts
from src.backend.app.domain.search import HybridConfig
from src.backend.tests.conftest import FakeEmbedder

RELAX = HybridConfig(lexical_k=20, lexical_cutoff=-1.0, min_coverage=0.4)
STRICT = HybridConfig(lexical_cutoff=-1.0)          # cosine giả không chặn phần vớt; chỉ độ phủ 0.6 quyết định


def _rescue_only(services, **kw):
    return SearchProducts(services["index"], services["vectors"], FakeEmbedder(), cutoff=2.0, lexical=services["vectors"],
                          hybrid=STRICT, **kw)


def test_relaxed_thresholds_apply_only_to_unaccented_queries(services):
    e = _rescue_only(services, no_diacritics=RELAX)
    # "Khách sạn B Nha Trang" phủ 4/9 token ("khach", "san", "nha", "trang") của câu — qua 0.4, không qua 0.6
    q_ascii, q_accent = "tim khach san o nha trang co ho boi gia tot", "tìm khách sạn ở Nha Trang có hồ bơi giá tốt"
    on = e(q_ascii, limit=10)
    assert on["diagnostics"]["queryProfile"] == "no_diacritics"
    assert on["diagnostics"]["lexicalMinCoverage"] == 0.4 and on["diagnostics"]["lexicalK"] == 20
    assert "H2" in {x["productId"] for x in on["results"]}
    accented = e(q_accent, limit=10)
    assert "queryProfile" not in accented["diagnostics"] and accented["diagnostics"]["lexicalMinCoverage"] == 0.6
    assert "H2" not in {x["productId"] for x in accented["results"]}


def test_mode_off_matches_today(services):
    q = "tim khach san o nha trang co ho boi gia tot"
    off = _rescue_only(services)(q, limit=10)
    today = SearchProducts(services["index"], services["vectors"], FakeEmbedder(), cutoff=2.0, lexical=services["vectors"],
                           hybrid=STRICT)(q, limit=10)
    strip = lambda r: {**r, "diagnostics": {k: v for k, v in r["diagnostics"].items() if k != "stageMs"}}  # noqa: E731
    assert strip(off) == strip(today) and "queryProfile" not in off["diagnostics"] and off["cutoff"] == 2.0


def test_effective_cutoff_is_reported_and_short_queries_keep_defaults(services):
    e = SearchProducts(services["index"], services["vectors"], FakeEmbedder(), cutoff=0.9, lexical=services["vectors"],
                       hybrid=HybridConfig(lexical_cutoff=0.5), no_diacritics=RELAX, no_diacritics_cutoff=-1.0)
    r = e("khach san nha trang gia tot", limit=50)
    assert r["cutoff"] == -1.0 and r["diagnostics"]["queryProfile"] == "no_diacritics" and r["total"] > 0
    short = e("VinWonders", limit=50)                       # < 3 token → ngưỡng chung, không có profile
    assert short["cutoff"] == 0.9 and "queryProfile" not in short["diagnostics"]
    digits = e("2024 2025 2026", limit=50)
    assert "queryProfile" not in digits["diagnostics"]
    strict_tokens = SearchProducts(services["index"], services["vectors"], FakeEmbedder(), cutoff=0.9, lexical=services["vectors"],
                                   hybrid=HybridConfig(lexical_cutoff=0.5), no_diacritics=RELAX, no_diacritics_min_tokens=7)
    assert "queryProfile" not in strict_tokens("khach san nha trang gia tot", limit=50)["diagnostics"]


def test_dense_only_engine_applies_cutoff_override_only(services):
    e = SearchProducts(services["index"], services["vectors"], FakeEmbedder(), cutoff=2.0, no_diacritics_cutoff=-1.0)
    r = e("khach san nha trang gia tot", limit=50)
    assert r["diagnostics"]["searchMode"] == "ANN_CANDIDATE_SCORE" and r["cutoff"] == -1.0 and r["total"] > 0
    assert r["diagnostics"]["queryProfile"] == "no_diacritics"
    assert e("khách sạn Nha Trang giá tốt", limit=50)["total"] == 0


def test_response_with_profile_matches_contract(services):
    e = SearchProducts(services["index"], services["vectors"], FakeEmbedder(), cutoff=0.0, lexical=services["vectors"],
                       hybrid=HybridConfig(lexical_cutoff=0.0), no_diacritics=HybridConfig(lexical_k=20, lexical_cutoff=0.0, min_coverage=0.4),
                       no_diacritics_cutoff=0.0, dest_filter=True)
    schema = contracts()["search_products"]["response"]
    for q in ("khach san o nha trang co ho boi", "resort Phu Quoc gia tot", "VinWonders Nha Trang"):
        r = e(q, limit=5)
        r["diagnostics"]["latencyMs"] = 0
        errors = [er.message for er in Draft202012Validator(schema).iter_errors(r)]
        assert errors == [], (q, errors)
        json.dumps(r)
