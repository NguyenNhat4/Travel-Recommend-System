"""Luật chọn lọc cứng điểm đến từ câu (FR-SRC-03; `domain/search/destination.py`) — bảng quyết định, thuần, không catalog."""
import pytest

from src.backend.app.domain.search import DestinationDecision, NormalizedQuery, decide_destination, is_flight_query


def nq(*dests: str, text: str = "x") -> NormalizedQuery:
    return NormalizedQuery(text, destinations=tuple(dests))


def test_explicit_param_always_wins_even_over_query_place():
    d = decide_destination(nq("Phú Quốc"), "Nha Trang", None, True, query="resort Phú Quốc")
    assert d == DestinationDecision("Nha Trang", "param", None, ("Phú Quốc",))
    # cờ tắt vẫn ghi nhận tham số (hành vi hôm nay)
    assert decide_destination(nq("Phú Quốc"), "Nha Trang", None, False).value == "Nha Trang"


def test_single_place_in_query_is_used_only_when_enabled():
    on = decide_destination(nq("Phú Quốc"), None, None, True, query="resort Phú Quốc")
    assert (on.value, on.source, on.skipped) == ("Phú Quốc", "query", None)
    off = decide_destination(nq("Phú Quốc"), None, None, False, query="resort Phú Quốc")
    assert (off.value, off.source, off.skipped, off.candidates) == (None, None, None, ("Phú Quốc",))


def test_two_places_skip_filter():
    d = decide_destination(nq("Hà Nội", "Hạ Long"), None, None, True, query="khách sạn Hà Nội hoặc Hạ Long")
    assert (d.value, d.source, d.skipped) == (None, None, "multi") and d.candidates == ("Hà Nội", "Hạ Long")


@pytest.mark.parametrize("query, taxonomy", [
    ("vé máy bay Hà Nội", None), ("ve may bay di ha noi", None), ("chuyến bay đến Đà Nẵng", None),
    ("đường bay Hà Nội", None), ("chặng bay Hà Nội", None), ("khách sạn Hà Nội", "flight"),
])
def test_flight_queries_skip_filter(query, taxonomy):
    d = decide_destination(nq("Hà Nội"), None, taxonomy, True, query=query)
    assert (d.value, d.source, d.skipped) == (None, None, "flight")
    assert is_flight_query(query, taxonomy)


def test_flight_cue_matches_whole_words_only():
    assert not is_flight_query("khách sạn Hà Nội", None)
    assert not is_flight_query("maybay", None)
    assert is_flight_query("Vé máy bay Hà Nội - Cam Ranh", None)


def test_no_normalizer_or_no_place_means_no_filter():
    assert decide_destination(None, None, None, True, query="resort Phú Quốc") == DestinationDecision(None, None, None, ())
    assert decide_destination(nq(), None, None, True, query="resort").candidates == ()


def test_as_dict_matches_contract_shape():
    assert decide_destination(nq("Phú Quốc"), None, None, True, query="resort Phú Quốc").as_dict() == \
        {"source": "query", "value": "Phú Quốc"}
    assert decide_destination(nq("Phú Quốc"), None, None, True, query="resort Phú Quốc").as_dict("dropped_empty") == \
        {"source": "query", "value": "Phú Quốc", "fallback": "dropped_empty"}
    assert decide_destination(nq("A", "B"), None, None, True, query="A hoặc B").as_dict() == \
        {"source": "none", "value": None, "skipped": "multi"}
    assert decide_destination(nq(), None, None, True).as_dict() == {"source": "none", "value": None}
