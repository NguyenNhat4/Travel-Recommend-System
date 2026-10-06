"""FR-SRC-03 — lọc cứng điểm đến suy ra từ câu trong `SearchProducts` (cờ `dest_filter`, mặc định tắt).

Fixture catalog (tests/conftest.py ROWS) chỉ có hai điểm đến: Nha Trang (H1, H2, A1, A2, C1, G1, F1 route) và Phú Quốc (H3)."""
import json

from jsonschema import Draft202012Validator

from src.backend.app.application.itinerary.tool_contracts import contracts
from src.backend.app.application.search import SearchProducts
from src.backend.app.application.search.responses import search_tool_payload
from src.backend.app.domain.search import HybridConfig
from src.backend.tests.conftest import FakeEmbedder

DEST_KEYS = {"derivedDestinations", "destinationFilter"}


class SpyEmbedder(FakeEmbedder):
    calls = 0

    def embed_query(self, q):
        self.calls += 1
        return super().embed_query(q)


def _engine(services, **kw):
    kw.setdefault("cutoff", -1.0)
    return SearchProducts(services["index"], services["vectors"], kw.pop("embedder", FakeEmbedder()), **kw)


def _strip(r: dict) -> dict:
    d = {k: v for k, v in r["diagnostics"].items() if k != "stageMs"}
    return {**r, "diagnostics": d}


def test_flag_off_is_todays_behaviour_but_declares_derived_places(services):
    on = _engine(services, dest_filter=True)("resort Phú Quốc", limit=50)
    off = _engine(services)("resort Phú Quốc", limit=50)
    assert off["diagnostics"]["derivedDestinations"] == ["Phú Quốc"]         # phát kể cả khi cờ tắt (đo tần suất)
    assert "destinationFilter" not in off["diagnostics"] and "appliedFilters" not in off
    assert {x["destination"] for x in off["results"]} == {"Nha Trang", "Phú Quốc"}   # không lọc
    assert {x["destination"] for x in on["results"]} == {"Phú Quốc"}
    # cờ tắt phải giống hệt bản trước (chỉ thêm khoá khai báo): so với engine không có tham số mới
    base = SearchProducts(services["index"], services["vectors"], FakeEmbedder(), cutoff=-1.0)("resort Phú Quốc", limit=50)
    assert _strip(base) == _strip(off)


def test_single_place_filters_counts_and_applied_filters(services):
    r = _engine(services, dest_filter=True)("resort Phú Quốc", limit=50)
    assert [x["productId"] for x in r["results"]] == ["H3"]
    assert r["total"] == 1 and r["diagnostics"]["filteredCount"] == 1 and r["facets"]["destination"] == {"Phú Quốc": 1}
    assert r["diagnostics"]["destinationFilter"] == {"source": "query", "value": "Phú Quốc"}
    assert r["appliedFilters"] == {"hard": {"destination": "Phú Quốc", "destinationSource": "query"}, "soft": {}}
    assert "appliedFilters" in search_tool_payload(r)                        # Agent nhận được khối hard filter (§2.5)


def test_param_wins_over_query_place(services):
    r = _engine(services, dest_filter=True)("resort Phú Quốc", destination="Nha Trang", taxonomy="hotel", limit=50)
    assert {x["destination"] for x in r["results"]} == {"Nha Trang"} and {x["taxonomy"] for x in r["results"]} == {"hotel"}
    assert r["diagnostics"]["destinationFilter"] == {"source": "param", "value": "Nha Trang"}
    assert r["appliedFilters"]["hard"] == {"taxonomy": "hotel", "destination": "Nha Trang", "destinationSource": "param"}


def test_two_places_and_flight_queries_skip_filter(services):
    e = _engine(services, dest_filter=True)
    two = e("khách sạn Nha Trang hoặc Phú Quốc", limit=50)
    assert set(two["facets"]["destination"]) == {"Nha Trang", "Phú Quốc"}
    assert two["diagnostics"]["destinationFilter"] == {"source": "none", "value": None, "skipped": "multi"}
    assert two["diagnostics"]["derivedDestinations"] == ["Nha Trang", "Phú Quốc"] and "appliedFilters" not in two
    fl = e("vé máy bay Phú Quốc", limit=50)
    assert fl["diagnostics"]["destinationFilter"]["skipped"] == "flight" and set(fl["facets"]["destination"]) == {"Nha Trang", "Phú Quốc"}
    fl2 = e("Phú Quốc", taxonomy="flight", limit=50)
    assert fl2["diagnostics"]["destinationFilter"]["skipped"] == "flight" and fl2["appliedFilters"]["hard"] == {"taxonomy": "flight"}


def test_empty_filtered_set_falls_back_without_second_embed(services):
    # cutoff 2.0 + lexical_cutoff -1: chỉ hit BM25 có tên phủ đủ token mới vào R. "resort Phú Quốc" lọc về Phú Quốc, nhưng
    # sau khi bỏ token địa danh khỏi độ phủ, "Resort Phú Quốc" vẫn phủ "resort" 1/1 → R không rỗng. Dùng câu không khớp tên nào.
    spy = SpyEmbedder()
    e = _engine(services, embedder=spy, cutoff=2.0, lexical=services["vectors"], hybrid=HybridConfig(lexical_cutoff=-1.0),
                dest_filter=True)
    r = e("biệt thự Phú Quốc", limit=50)
    assert spy.calls == 1                                                      # chạy lại không gọi embed lần hai
    assert r["diagnostics"]["destinationFilter"] == {"source": "query", "value": "Phú Quốc", "fallback": "dropped_empty"}
    assert "appliedFilters" not in r                                           # sau fallback không còn hard filter nào
    assert r["diagnostics"]["filteredCount"] == len(services["index"].units)   # F của lượt không lọc
    assert r["total"] == 0                                                      # fixture không có tên nào phủ "biệt thự"
    no_fb = _engine(services, cutoff=2.0, lexical=services["vectors"], hybrid=HybridConfig(lexical_cutoff=-1.0),
                    dest_filter=True, dest_filter_fallback=False)("biệt thự Phú Quốc", limit=50)
    assert no_fb["diagnostics"]["destinationFilter"] == {"source": "query", "value": "Phú Quốc"}
    assert no_fb["diagnostics"]["filteredCount"] == 1


def test_place_tokens_are_removed_from_coverage_when_filtering(services):
    # rescue-only: "sân golf ở Nha Trang" — không lọc: "Vinpearl Resort Nha Trang" phủ 2/3 ("nha", "trang") → bị vớt nhầm;
    # có lọc: bỏ "nha trang" khỏi độ phủ → chỉ tên có "san"/"golf" ("Vinpearl Golf Nha Trang": golf 1/2 < 0.6 → cũng không) …
    kw = dict(cutoff=2.0, lexical=services["vectors"], hybrid=HybridConfig(lexical_cutoff=-1.0, min_coverage=0.5))
    off = _engine(services, **kw)("sân golf ở Nha Trang", limit=50)
    on = _engine(services, dest_filter=True, **kw)("sân golf ở Nha Trang", limit=50)
    assert "H1" in {x["productId"] for x in off["results"]}                    # phủ 2/3 nhờ "Nha Trang"
    assert "H1" not in {x["productId"] for x in on["results"]}                 # địa danh không còn là bằng chứng
    assert "G1" in {x["productId"] for x in on["results"]}                      # "golf" phủ 1/2 ≥ 0.5 → vẫn tới được


def test_agent_can_override_per_call(services):
    e = _engine(services, dest_filter=False)
    r = e("resort Phú Quốc", limit=50, derive_destination=True)
    assert [x["productId"] for x in r["results"]] == ["H3"] and r["diagnostics"]["destinationFilter"]["source"] == "query"
    r2 = _engine(services, dest_filter=True)("resort Phú Quốc", limit=50, derive_destination=False)
    assert "destinationFilter" not in r2["diagnostics"] and len(r2["results"]) > 1


def test_response_with_dest_filter_matches_contract(services):
    e = SearchProducts(services["index"], services["vectors"], FakeEmbedder(), cutoff=0.0, lexical=services["vectors"],
                       hybrid=HybridConfig(lexical_cutoff=0.0), dest_filter=True)
    schema = contracts()["search_products"]["response"]
    for q, kw in (("resort Phú Quốc", {}), ("khách sạn Nha Trang hoặc Phú Quốc", {}), ("vé máy bay Phú Quốc", {}),
                  ("resort", {"destination": "Nha Trang", "taxonomy": "hotel"}), ("zzzz không khớp gì", {})):
        r = e(q, limit=5, **kw)
        r["diagnostics"]["latencyMs"] = 0
        errors = [er.message for er in Draft202012Validator(schema).iter_errors(r)]
        assert errors == [], (q, errors)
        json.dumps(r)
