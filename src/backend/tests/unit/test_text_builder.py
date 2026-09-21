from app.domain.catalog import Product, build_text
from conftest import ROWS

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
