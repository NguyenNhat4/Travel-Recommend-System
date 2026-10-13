"""Mã sản phẩm của một lượt v2: một productId một mã, mã lịch sử phải tra lại, con trỏ gắn đúng truy vấn."""
import pytest

from src.backend.app.application.itinerary.product_registry import ProductRegistry
from src.backend.app.application.ports.itinerary_tools import ToolError
from src.backend.tests.fakes.orc_tools import product


def test_same_product_from_two_sources_keeps_one_ref_and_latest_data():
    registry = ProductRegistry({"p7": "old"})
    first = registry.add(product("a", price=100))
    again = registry.add(product("a", price=120))
    assert first == again == "p8"
    assert registry.fact("p8", "unitPrice") == 120


def test_history_ref_identifies_but_needs_refresh_before_use():
    registry = ProductRegistry({"p3": "hue-1"})
    assert registry.identify("p3") == "hue-1"
    with pytest.raises(ToolError, match="STALE_REF"):
        registry.product("p3")
    with pytest.raises(ToolError, match="UNKNOWN_REF"):
        registry.identify("p99")
    assert registry.add(product("hue-1")) == "p3"
    assert registry.product("p3")["productId"] == "hue-1"


def test_view_drops_unknown_fields_and_keeps_facts_for_the_orc():
    registry = ProductRegistry()
    ref = registry.add(product("a", price=None, pool=True, openingHours="07:00-17:00", images=["x.jpg"]))
    view = registry.view(ref)
    assert "unitPrice" not in view and view["pool"] is True and "images" not in view
    assert registry.fact(ref, "openingHours") == "07:00-17:00"
    assert registry.fact(ref, "missing") is None


def test_cursor_only_continues_the_same_query():
    registry = ProductRegistry()
    args = {"query": "biển", "destination": None, "cursor": None}
    cursor = registry.issue_cursor(args, 20)
    assert registry.cursor_offset(cursor, {**args, "cursor": cursor}) == 20
    assert registry.cursor_offset(cursor, {**args, "cursor": cursor, "limit": 50, "exclude_refs": ["p1"]}) == 20
    with pytest.raises(ToolError, match="CURSOR_MISMATCH"):
        registry.cursor_offset(cursor, {**args, "destination": "Huế", "cursor": cursor})
