"""SearchProducts — bộ lọc ngày (contract 1.19.0, `travelContext.checkIn/checkOut`; FR-SRC-03, FR-CAT-03).

Catalog dựng ở đây (hôm nay giả định 2026-10-07, lịch bắt đầu 2026-10-01, 30 ngày, đêm 2026-10-11 là chỉ số 10):
  HA  hai hạng phòng, lịch mở hết                       HB  một hạng phòng, kín đêm 10-11
  HC  hai hạng phòng: một kín đêm 10-11, một mở         HD  không có hạng phòng nào      HE  hạng phòng chưa có lịch
  HF  hai hạng phòng đều kín đêm 10-11 (nhưng đêm 10-10 thì mở)
  HG  hai hạng phòng: 4 người nhưng kín đêm 10-11, và 2 người còn mở        HH  hạng phòng duy nhất đã ngừng bán
  AT1 vé, cửa sổ 10-01..10-31, không lịch    AT2 vé, lịch kín ngày 10-10    AT3 vé, cửa sổ 11-01..11-30
  C1 combo cửa sổ 10-01..10-31              C2 combo cửa sổ 11-01..11-30     F1 route bay."""
import json
from datetime import date

import pytest

from src.backend.app.application.search import SearchProducts
from src.backend.tests.conftest import P, FakeEmbedder
from src.backend.tests.fakes.in_memory_vector_store import InMemoryVectorStore

TODAY = date(2026, 10, 7)


def _cal(*closed_days: int) -> dict:
    bits = ["1"] * 30
    for k in closed_days:
        bits[k] = "0"
    return {"availability": {"from": "2026-10-01", "days": 30, "calendar": "".join(bits)}}


def _room(pid: str, parent: str, **attrs) -> dict:
    return P(pid, f"{parent} - {pid}", "hotel", "Nha Trang", {"level": "room", "parentProductId": parent, **attrs}, price=2000000)


def _dated(row: dict, start: str, end: str) -> dict:
    return {**row, "availableFrom": start, "availableTo": end}


ROWS = [
    P("HA", "Resort Alpha Nha Trang", "hotel", "Nha Trang", {"level": "property"}, price=None),
    _room("RA1", "HA", **_cal()), _room("RA2", "HA", **_cal()),
    P("HB", "Resort Bravo Nha Trang", "hotel", "Nha Trang", {"level": "property"}, price=None),
    _room("RB1", "HB", **_cal(10)),
    P("HC", "Resort Charlie Nha Trang", "hotel", "Nha Trang", {"level": "property"}, price=None),
    _room("RC1", "HC", **_cal(10)), _room("RC2", "HC", **_cal()),
    P("HD", "Resort Delta Nha Trang", "hotel", "Nha Trang", {"level": "property"}, price=None),
    P("HE", "Resort Echo Nha Trang", "hotel", "Nha Trang", {"level": "property"}, price=None),
    _room("RE1", "HE"),
    P("HF", "Resort Foxtrot Nha Trang", "hotel", "Nha Trang", {"level": "property"}, price=None),
    _room("RF1", "HF", **_cal(10)), _room("RF2", "HF", **_cal(10, 11)),
    P("HG", "Resort Golf Nha Trang", "hotel", "Nha Trang", {"level": "property"}, price=None),
    _room("RG1", "HG", maxOccupancy=4, **_cal(10)), _room("RG2", "HG", maxOccupancy=2, **_cal()),
    P("HH", "Resort Hotel Nha Trang", "hotel", "Nha Trang", {"level": "property"}, price=None),
    P("RH1", "Resort Hotel Nha Trang - RH1", "hotel", "Nha Trang", {"level": "room", "parentProductId": "HH"}, price=2000000,
      avail=False),
    _dated(P("AT1", "Vé Alpha Nha Trang", "attraction", "Nha Trang", {}, price=500000), "2026-10-01", "2026-10-31"),
    _dated(P("AT2", "Vé Bravo Nha Trang", "attraction", "Nha Trang", _cal(9), price=500000), "2026-10-01", "2026-10-31"),
    _dated(P("AT3", "Vé Charlie Nha Trang", "attraction", "Nha Trang", {}, price=500000), "2026-11-01", "2026-11-30"),
    _dated(P("C1", "Combo Alpha Nha Trang", "combo", "Nha Trang", {"nights": 2}, price=5000000), "2026-10-01", "2026-10-31"),
    _dated(P("C2", "Combo Bravo Nha Trang", "combo", "Nha Trang", {"nights": 2}, price=5000000), "2026-11-01", "2026-11-30"),
    P("F1", "Vé máy bay Hà Nội - Cam Ranh", "flight", "Nha Trang",
      {"level": "route", "originCity": "Hà Nội", "destinationCity": "Nha Trang"}, price=None),
]


@pytest.fixture(scope="module")
def cat(tmp_path_factory):
    d = tmp_path_factory.mktemp("stay")
    (d / "products.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in ROWS), encoding="utf-8")
    emb = FakeEmbedder()
    index, vectors = InMemoryVectorStore(str(d / "products.jsonl"), emb, str(d / ".emb")).load()
    return {"index": index, "vectors": vectors, "emb": emb}


def _engine(cat, **kw):
    kw.setdefault("cutoff", -1.0)
    kw.setdefault("today", lambda: TODAY)
    return SearchProducts(cat["index"], cat["vectors"], cat["emb"], **kw)


def _ids(r):
    return {x["productId"] for x in r["results"]}


def _by_id(r):
    return {x["productId"]: x for x in r["results"]}


def _search(cat, q="Nha Trang", **kw):
    return _engine(cat)(q, limit=50, **kw)


def test_without_dates_nothing_is_filtered(cat):
    r = _search(cat)
    assert {"HA", "HB", "HC", "HD", "HE", "HF", "AT1", "AT2", "AT3", "C1", "C2", "F1"} <= _ids(r)
    assert "appliedFilters" not in r and "date" not in r["diagnostics"].get("queryPlan", {})


def test_hotels_are_dropped_only_when_every_room_is_known_closed(cat):
    r = _search(cat, check_in=date(2026, 10, 10), check_out=date(2026, 10, 13))   # đêm 10, 11, 12 (chỉ số 9, 10, 11)
    ids = _ids(r)
    assert {"HA", "HC", "HD", "HE"} <= ids       # HC còn phòng mở; HD không có phòng và HE chưa có lịch → không biết → giữ
    assert "HB" not in ids and "HF" not in ids   # mọi hạng phòng có lịch đều kín


def test_a_night_outside_the_calendar_counts_as_unknown(cat):
    r = _search(cat, check_in=date(2026, 10, 30), check_out=date(2026, 11, 3))     # lịch hết ở 10-30
    assert {"HA", "HB", "HC", "HF"} <= _ids(r)
    r = _search(cat, check_in=date(2026, 10, 11), check_out=date(2026, 10, 12))    # chỉ đêm 10-11 (kín với HB, HC.1, HF)
    assert "HB" not in _ids(r) and "HF" not in _ids(r) and "HC" in _ids(r)


def test_check_in_alone_means_one_night_for_hotels(cat):
    ids = _ids(_search(cat, check_in=date(2026, 10, 11)))
    assert "HB" not in ids and "HA" in ids
    assert "HB" in _ids(_search(cat, check_in=date(2026, 10, 12)))


def test_hotel_booking_window_applies_to_search(cat):
    assert not any(i.startswith("H") for i in _ids(_search(cat, check_in=date(2026, 10, 6))))    # quá khứ
    assert not any(i.startswith("H") for i in _ids(_search(cat, check_in=date(2027, 1, 8))))     # quá 3 tháng
    assert not any(i.startswith("H") for i in _ids(_search(cat, check_in=date(2026, 10, 10), check_out=date(2026, 11, 10))))  # 31 đêm
    assert "HA" in _ids(_search(cat, check_in=date(2026, 10, 7)))                                 # hôm nay được


def test_attractions_use_sales_window_and_the_calendar_of_the_day(cat):
    ids = _ids(_search(cat, check_in=date(2026, 10, 10)))     # AT2 kín ngày 10-10 (chỉ số 9)
    assert "AT1" in ids and "AT2" not in ids and "AT3" not in ids
    assert "AT2" in _ids(_search(cat, check_in=date(2026, 10, 12)))
    assert "AT3" in _ids(_search(cat, check_in=date(2026, 11, 5)))   # trong cửa sổ, ngoài khoảng lịch (AT3 không có lịch)


def test_combos_use_sales_window_and_flights_are_not_filtered(cat):
    ids = _ids(_search(cat, check_in=date(2026, 10, 10)))
    assert "C1" in ids and "C2" not in ids and "F1" in ids
    assert {"C2", "F1"} <= _ids(_search(cat, check_in=date(2026, 11, 5)))


def test_declares_the_filter_in_applied_filters_and_query_plan(cat):
    r = _search(cat, check_in=date(2026, 10, 10), check_out=date(2026, 10, 13))
    assert r["appliedFilters"] == {"hard": {"checkIn": "2026-10-10", "checkOut": "2026-10-13", "dateSource": "param"}, "soft": {}}
    assert r["diagnostics"]["queryPlan"]["date"] == {"checkIn": "2026-10-10", "checkOut": "2026-10-13", "source": "param"}
    one = _search(cat, check_in=date(2026, 10, 10))
    assert one["appliedFilters"]["hard"] == {"checkIn": "2026-10-10", "dateSource": "param"}
    assert one["diagnostics"]["queryPlan"]["date"]["checkOut"] is None


def test_facets_and_total_stay_consistent_after_the_date_filter(cat):
    r = _search(cat, check_in=date(2026, 10, 10), check_out=date(2026, 10, 13))
    assert r["total"] == len(r["results"]) and sum(r["facets"]["taxonomy"].values()) == r["total"]
    assert r["diagnostics"]["queryPlan"].get("revalidatedDrops", 0) == 0


def test_empty_result_from_dates_reports_date(cat):
    r = _search(cat, taxonomy="hotel", check_in=date(2027, 1, 8))
    assert r["total"] == 0 and r["diagnostics"]["queryPlan"]["emptyReason"] == "date"


def test_date_and_party_must_hold_on_the_same_room(cat):
    stay = dict(check_in=date(2026, 10, 10), check_out=date(2026, 10, 13))
    assert "HG" in _ids(_search(cat, **stay)) and "HG" in _ids(_search(cat, adults=4))      # mỗi điều kiện riêng đều có phòng
    both = _search(cat, adults=4, **stay)
    assert "HG" not in _ids(both)         # phòng 4 người kín lịch, phòng còn lịch chỉ 2 người: không phòng nào thoả cả hai
    ok = _search(cat, adults=2, **stay)
    assert "HG" in _ids(ok) and _by_id(ok)["HG"]["matchedChildren"] == ["RG2"]
    assert "revalidatedDrops" not in both["diagnostics"].get("queryPlan", {})


def test_hotel_without_a_sellable_room_is_dropped_once_a_room_level_filter_applies(cat):
    assert "HH" in _ids(_search(cat, taxonomy="hotel"))       # không điều kiện cấp phòng: như trước
    assert "HH" not in _ids(_search(cat, taxonomy="hotel", check_in=date(2026, 10, 10)))
    assert "HH" not in _ids(_search(cat, taxonomy="hotel", adults=2))
    assert "HH" not in _ids(_search(cat, taxonomy="hotel", price_max=9_000_000))


def test_matched_children_list_the_rooms_open_for_the_dates(cat):
    r = _search(cat, taxonomy="hotel", check_in=date(2026, 10, 10), check_out=date(2026, 10, 13))
    kids = {x["productId"]: x.get("matchedChildren") for x in r["results"]}
    assert kids["HA"] == ["RA1", "RA2"] and kids["HC"] == ["RC2"] and kids["HG"] == ["RG2"]
    assert "matchedChildren" not in _search(cat, taxonomy="hotel")["results"][0]


def test_dates_combine_with_party_and_price(cat):
    r = _search(cat, taxonomy="hotel", adults=2, price_max=3000000, check_in=date(2026, 10, 10), check_out=date(2026, 10, 13))
    assert {"HA", "HC"} <= _ids(r) and "HB" not in _ids(r)
    assert r["appliedFilters"]["hard"]["minOccupancy"] == 2 and r["appliedFilters"]["hard"]["checkIn"] == "2026-10-10"
