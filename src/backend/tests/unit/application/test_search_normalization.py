"""Bước chuẩn hoá nằm trong SearchProducts: câu đã chuẩn hoá mới là thứ đi vào embed/BM25, khai ở diagnostics."""
from src.backend.app.application.search import SearchProducts
from src.backend.app.domain.search import HybridConfig
from src.backend.tests.conftest import FakeEmbedder

NORMALIZATION_KEYS = {"normalizedQuery", "appliedAliases", "corrections", "party"}


class SpyEmbedder(FakeEmbedder):
    last_query = None

    def embed_query(self, q):
        self.last_query = q
        return super().embed_query(q)


def test_normalized_text_reaches_embedder_and_diagnostics(services):
    spy = SpyEmbedder()
    s = SearchProducts(services["index"], services["vectors"], spy, cutoff=-1.0)
    r = s("KS ở NT")
    assert spy.last_query == "khách sạn ở Nha Trang"
    d = r["diagnostics"]
    assert d["normalizedQuery"] == "khách sạn ở Nha Trang"
    assert d["appliedAliases"] == [{"from": "KS", "to": "khách sạn"}, {"from": "NT", "to": "Nha Trang"}]
    assert "corrections" not in d and "party" not in d


def test_party_is_declared(services):
    spy = SpyEmbedder()
    r = SearchProducts(services["index"], services["vectors"], spy, cutoff=-1.0)("resort Nha Trang đi cùng bạn trai")
    assert "cặp đôi" in spy.last_query and r["diagnostics"]["party"] == "COUPLE"


def test_unchanged_query_adds_no_keys(services):
    r = SearchProducts(services["index"], services["vectors"], FakeEmbedder(), cutoff=-1.0)("resort")
    assert not NORMALIZATION_KEYS & r["diagnostics"].keys()


def test_normalize_off_passes_raw_text(services):
    spy = SpyEmbedder()
    r = SearchProducts(services["index"], services["vectors"], spy, cutoff=-1.0, normalize=False)("KS ở NT")
    assert spy.last_query == "KS ở NT" and not NORMALIZATION_KEYS & r["diagnostics"].keys()


def test_corrected_brand_is_rescued_by_bm25(services):
    s = SearchProducts(services["index"], services["vectors"], FakeEmbedder(), cutoff=2.0,
                       lexical=services["vectors"], hybrid=HybridConfig(lexical_cutoff=-1.0))
    r = s("Vinpeal Golf Nha Trang", limit=5)
    assert r["diagnostics"]["corrections"] == [{"from": "Vinpeal", "to": "Vinpearl"}]
    ids = [x["productId"] for x in r["results"]]
    # Không hit dense nào qua cutoff 2.0: mọi kết quả đều được vớt từ BM25 nhờ tên đã sửa ("Vinpearl … Nha Trang")
    assert "G1" in ids and r["diagnostics"]["lexicalCount"] == r["total"] == len(ids) >= 1
    assert all("Vinpearl" in x["name"] for x in r["results"])
