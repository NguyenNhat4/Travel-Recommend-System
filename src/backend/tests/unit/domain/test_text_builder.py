import json
import pathlib

import pytest

from src.backend.app.domain.catalog import Product, build_text, enrich
from conftest import ROWS

CASES = json.loads((pathlib.Path(__file__).parents[1] / "fixtures" / "embed_text_cases.json").read_text(encoding="utf-8"))["cases"]


def test_property_text_has_name_first_and_room_vocab():
    prods = {r["productId"]: Product.from_cdp(r) for r in ROWS}
    t = build_text(prods["H1"], [prods["R1"]])
    assert t.startswith("Vinpearl Resort Nha Trang — khu nghỉ dưỡng 5 sao")
    assert "Deluxe Ocean View" in t and "3400000" not in t

def test_roles():
    prods = {r["productId"]: Product.from_cdp(r) for r in ROWS}
    assert prods["H1"].is_search_unit and not prods["H1"].is_bookable
    assert not prods["R1"].is_search_unit and prods["R1"].is_bookable
    assert not prods["A2"].is_bookable


def _p(pid, name, tax, dest="Nha Trang", attrs=None, price=100000, desc="") -> Product:
    return Product(product_id=pid, name=name, taxonomy=tax, destination=dest, description=desc, attributes=attrs or {}, unit_price=price)


def _room(pid, name, **attrs) -> Product:
    return _p(pid, f"Khách sạn A - {name}", "hotel", attrs={"level": "room", "parentProductId": "H", "roomName": name, **attrs})


def _children(parent: Product, children: list[dict]) -> list[Product]:
    """Fixture giữ con ở dạng gọn (chỉ các trường template đọc + unitPrice); productId, taxonomy, level, parentProductId điền ở đây."""
    level = "room" if parent.variant == "hotel_property" else "flight"
    return [Product(product_id=f"{parent.product_id}:{i}", name=f"{parent.name} - {c.get('roomName') or c.get('flightNumber')}",
                    taxonomy=parent.taxonomy, destination=parent.destination, description="",
                    attributes={"level": level, "parentProductId": parent.product_id, **{k: v for k, v in c.items() if k != "unitPrice"}},
                    unit_price=c.get("unitPrice")) for i, c in enumerate(children)]


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_fixture_cases_match_template(case):
    """Fixture là dữ liệu thật rút gọn (collected → enriched → embed_text): đổi template thì phải cập nhật embed_text_cases.json."""
    p = Product.from_cdp(case["collected"])
    kids = _children(p, case.get("children", []))
    items = case.get("combo_items", [])
    assert enrich(p, kids, items) == case["enriched"]
    assert build_text(p, kids, combo_items=items) == case["embed_text"]


def test_rooms_and_flights_have_no_text():
    prods = {r["productId"]: Product.from_cdp(r) for r in ROWS}
    for pid in ("R1", "FL1"):
        assert build_text(prods[pid], []) == ""
        assert not any(enrich(prods[pid], []).values())


def test_rollup_carries_room_only_features_up_to_the_property():
    hotel = _p("H", "Khách sạn A", "hotel", attrs={"level": "property"})
    rooms = [_room("R1", "Villa", amenities=["Hồ bơi riêng", "Bồn tắm hoặc vòi sen"]), _room("R2", "Deluxe", amenities=["Ban công"])]
    t = build_text(hotel, rooms)
    assert "hồ bơi riêng" in t and "ban công" in t
    assert "bồn tắm" not in t          # "bồn tắm hoặc vòi sen" chỉ là tuỳ chọn, không phải bồn tắm


def test_text_does_not_depend_on_children_order():
    hotel = _p("H", "Khách sạn A", "hotel", attrs={"level": "property"})
    rooms = [_room(f"R{i}", n, bed=b, maxOccupancy=o) for i, (n, b, o) in
             enumerate([("Deluxe", "1 giường đôi lớn", 2), ("Suite Gia Đình", "2 giường đơn", 4), ("Studio", "1 giường đôi", 2)])]
    assert build_text(hotel, rooms) == build_text(hotel, rooms[::-1]) == build_text(hotel, [rooms[1], rooms[2], rooms[0]])


def test_bed_types_are_deduplicated():
    hotel = _p("H", "Khách sạn A", "hotel", attrs={"level": "property"})
    rooms = [_room("R1", "A", bed="1 giường đôi lớn"), _room("R2", "B", bed="1 giường đôi cực lớn\n\nvà\n\n1 giường đôi lớn")]
    assert build_text(hotel, rooms).count("1 giường đôi") == 1


def test_volatile_numbers_stay_out_of_the_text():
    hotel = _p("H", "Khách sạn A", "hotel", attrs={"level": "property", "reviewScore": 8.6, "reviewCount": 1225}, price=5180000,
               desc="Điểm đánh giá 8.6/10 từ 1225 lượt đánh giá. Giá từ 2.072.896₫ mỗi đêm. Khu nghỉ dưỡng nằm sát biển, có hồ bơi và nhà hàng.")
    t = build_text(hotel, [])
    assert "sát biển" in t
    assert not any(x in t for x in ("8.6", "1225", "2.072.896", "5180000"))
    route = _p("F", "Vé máy bay A - B", "flight", attrs={"level": "route", "originCity": "A", "destinationCity": "B"},
               desc="Vé một chiều từ A (CXR) đến B (SGN). Giá một chiều từ 634.000₫. Tháng rẻ nhất: 2027-01.")
    assert not any(x in build_text(route, []) for x in ("634", "2027", "CXR"))


def test_property_kind_is_inferred_from_name_and_never_defaults_to_hotel():
    def kind(name, **attrs):
        return build_text(_p("H", name, "hotel", attrs={"level": "property", **attrs}), [])
    assert "— homestay" in kind("Sunrise Homestay")
    assert "— cơ sở lưu trú" in kind("Bình Yên") and "khách sạn" not in kind("Bình Yên")
    assert "— căn hộ" in kind("X Hotel", propertyType="căn hộ")        # nguồn khai thì ưu tiên hơn suy từ tên


def test_excerpt_drops_seo_heading_and_section_titles():
    desc = ("X Resort tại Huế: Tất cả những gì bạn cần biếtX Resort mang đến không gian yên tĩnh cho kỳ nghỉ thư thả. "
            "Chỗ Nghỉ Thanh Lịch:\nCó hồ bơi ngoài trời và nhà hàng phục vụ bữa sáng.")
    t = build_text(_p("H", "X Resort", "hotel", attrs={"level": "property"}, desc=desc), [])
    assert "mang đến không gian yên tĩnh" in t and "nhà hàng phục vụ bữa sáng" in t
    assert "Tất cả những gì" not in t and "Thanh Lịch" not in t


def test_attraction_is_public_only_when_the_source_says_ticketed_false():
    prods = {r["productId"]: Product.from_cdp(r) for r in ROWS}
    assert "công cộng, không bán vé" in build_text(prods["A2"], [])           # cờ ticketed=false của nguồn
    assert "công cộng" not in build_text(prods["A1"], []) and "Phù hợp: gia đình" in build_text(prods["A1"], [])
    # không giá ≠ công cộng: trip.com có 244/299 điểm null giá là isFree=false, nên không được suy ra từ unitPrice
    assert "công cộng" not in build_text(_p("A", "Bãi biển B", "attraction", price=None), [])


def test_combo_lists_items_in_position_order():
    prods = {r["productId"]: Product.from_cdp(r) for r in ROWS}
    items = [{"position": 2, "label": "Buffet sáng"}, {"position": 1, "label": "Vé VinWonders"}]
    t = build_text(prods["C1"], [], combo_items=items)
    assert "combo hai đêm" in t and "Gồm: Vé VinWonders; Buffet sáng." in t
    assert "Gồm:" not in build_text(prods["C1"], [])


def test_route_rollup_summarises_flights():
    route = _p("F", "Vé máy bay A - B", "flight", attrs={"level": "route", "originCity": "A", "destinationCity": "B", "durationMinutes": 95})
    fl = [_p(f"L{i}", f"L{i}", "flight", attrs={"level": "flight", "parentProductId": "F", "airline": a, "departureTimeLocal": t, "nonstop": n})
          for i, (a, t, n) in enumerate([("VietJet Air", "05:00", False), ("VietJet Air", "07:00", False), ("Vietnam Airlines", "19:30", True)])]
    t = build_text(route, fl)
    assert "Hãng bay: VietJet Air, Vietnam Airlines." in t         # không có route.airlines thì lấy từ các chuyến, xếp theo chữ cái
    assert "Có cả chuyến bay thẳng và nối chuyến." in t
    assert "Khung giờ khởi hành: sáng sớm, sáng, tối." in t and "05:00" not in t
    assert "Thời gian bay khoảng 1 giờ 35 phút." in t
