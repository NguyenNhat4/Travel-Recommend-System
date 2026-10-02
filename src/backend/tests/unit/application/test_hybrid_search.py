"""Hybrid /search trên fake offline: nhánh BM25 của NumpyVectorSearch + RRF ở app, khai HYBRID_CANDIDATE_SCORE."""
import json
from types import SimpleNamespace

import pytest
from jsonschema import Draft202012Validator

from src.backend.app.application.itinerary.tool_contracts import contracts
from src.backend.app.application.search import SearchProducts
from src.backend.app.application.search.use_cases import scored
from src.backend.app.domain.catalog import Product
from src.backend.app.domain.search import HybridConfig
from src.backend.tests.conftest import FakeEmbedder


@pytest.fixture(scope="module")
def rescue_only(services):
    # cutoff 2.0: không hit dense nào qua; lexical_cutoff -1: cosine giả (ngẫu nhiên) không chặn phần vớt.
    return SearchProducts(services["index"], services["vectors"], FakeEmbedder(), cutoff=2.0,
                          lexical=services["vectors"], hybrid=HybridConfig(lexical_cutoff=-1.0))


@pytest.fixture(scope="module")
def pass_all(services):
    return SearchProducts(services["index"], services["vectors"], FakeEmbedder(), cutoff=-1.0,
                          lexical=services["vectors"], hybrid=HybridConfig())


def test_search_results_carry_the_catalog_rating_for_itinerary_cards(rescue_only):
    # Thẻ sản phẩm trong lời diễn giải của trợ lý hiện điểm đánh giá: Search phải trả `rating`/`reviewCount` (tùy chọn
    # trong ProductSummary), không có điểm thì null. Recommendation giữ payload rút gọn (hop-dong-tich-hop-backend.md).
    result = rescue_only("VinWonders", limit=5)["results"][0]
    assert (result["rating"], result["reviewCount"]) == (None, None)
    rated = Product(product_id="A9", name="Tháp Bà", taxonomy="attraction", destination="Nha Trang", description="",
                    attributes={"rating": 4.6, "ratingScale": 5, "reviewCount": 44})
    rated_result = scored(SimpleNamespace(units=[rated]), 0, 0.7)
    assert (rated_result["rating"], rated_result["reviewCount"], rated_result["score"]) == (4.6, 44, 0.7)


def test_brand_query_is_rescued_from_bm25_and_declared_in_diagnostics(rescue_only):
    r = rescue_only("VinWonders", limit=5)
    assert [x["productId"] for x in r["results"]] == ["A1"]
    d = r["diagnostics"]
    assert d["searchMode"] == "HYBRID_CANDIDATE_SCORE" and d["fusion"] == "rrf" and d["rrfK"] == 60
    assert d["lexicalCount"] == r["total"] == d["relevantCount"] == 1 and d["lexicalCandidates"] >= 1
    assert 0.0 <= r["results"][0]["score"] <= 1.0 and 0.0 <= r["topScore"] <= 1.0
    assert sum(r["facets"]["taxonomy"].values()) == r["total"]
    json.dumps(r)


def test_hybrid_response_matches_contract(services):
    # Giá trị trong miền của contract (cutoff, lexicalCutoff ∈ [0, 1]) — fixture ở trên cố ý vượt miền để ép nhánh vớt.
    s = SearchProducts(services["index"], services["vectors"], FakeEmbedder(), cutoff=0.0,
                       lexical=services["vectors"], hybrid=HybridConfig(lexical_cutoff=0.0))
    for q in ("VinWonders Nha Trang", "resort", "zzzz không khớp gì", "KS ở PQ Vinpeal cho gd"):
        r = s(q, limit=5)
        r["diagnostics"]["latencyMs"] = 0  # route `_safe_search` gắn trường này, use case thì không
        errors = [e.message for e in Draft202012Validator(contracts()["search_products"]["response"]).iter_errors(r)]
        assert errors == [], (q, errors)


def test_partial_name_overlap_is_not_rescued(rescue_only):
    # "Khách sạn B Nha Trang" chỉ phủ 2/4 token của truy vấn (< 0.6): BM25 khớp nhưng không được vớt.
    r = rescue_only("khách sạn ở Cà Mau", limit=5)
    assert r["results"] == [] and r["total"] == 0 and r["topScore"] is None
    assert r["diagnostics"]["lexicalCandidates"] >= 1 and r["diagnostics"]["lexicalCount"] == 0
    assert r["diagnostics"]["lexicalMinCoverage"] == 0.6


def test_hybrid_keeps_dense_set_and_counts_when_everything_passes_cutoff(pass_all, services):
    q = "nghỉ dưỡng biển cho gia đình"
    a, b = pass_all(q, limit=50), services["search"](q, limit=50)
    assert {x["productId"] for x in a["results"]} == {x["productId"] for x in b["results"]}
    assert a["total"] == b["total"] and a["facets"] == b["facets"] and a["topScore"] == b["topScore"]
    assert a["diagnostics"]["lexicalCount"] == 0 and b["diagnostics"]["searchMode"] == "ANN_CANDIDATE_SCORE"


def test_total_and_facets_stable_across_pages(pass_all):
    p1, p2 = pass_all("Nha Trang", limit=2, offset=0), pass_all("Nha Trang", limit=2, offset=2)
    assert p1["total"] == p2["total"] and p1["facets"] == p2["facets"]
    assert [x["productId"] for x in p1["results"]] != [x["productId"] for x in p2["results"]]


class _BrokenLexical:
    def bm25(self, *args, **kwargs):
        raise RuntimeError("collection has no searchable property")


def test_lexical_failure_degrades_to_dense_only_without_error(services):
    s = SearchProducts(services["index"], services["vectors"], FakeEmbedder(), cutoff=-1.0,
                       lexical=_BrokenLexical(), hybrid=HybridConfig())
    r = s("resort", limit=3)
    assert r["diagnostics"]["searchMode"] == "HYBRID_CANDIDATE_SCORE"
    assert r["diagnostics"]["lexicalCandidates"] == 0 and r["diagnostics"]["lexicalCount"] == 0
    assert r["total"] > 0


def test_hybrid_off_when_no_lexical_port(services):
    s = SearchProducts(services["index"], services["vectors"], FakeEmbedder(), cutoff=-1.0, hybrid=HybridConfig())
    assert s.hybrid_on is False and s("resort")["diagnostics"]["searchMode"] == "ANN_CANDIDATE_SCORE"
