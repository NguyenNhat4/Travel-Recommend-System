"""FR-REC-02 (chốt 2026-10-09, đề xuất `update-archive/2026-10-08-recsys-loai-san-pham-da-mua-va-combo.md`): không gợi lại
sản phẩm đã mua (mọi lần mua, theo search unit) và combo ↔ thành phần coi là cùng một lần mua, hai chiều, một bậc.

Ba tầng: `combo_members_of` (dòng mapping nào được tin), `UnitIndex.purchase_closure` (đóng một bậc theo search unit) và
`RecommendForUser` (mask ứng viên, cả nhánh chuyến mở lẫn chuyến đã xong). AC-REC-03."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from src.backend.app.application.ports import UnitIndex
from src.backend.app.application.recommendation import BuildPopularity, RecommendForUser
from src.backend.app.application.recommendation.use_cases import bought_units
from src.backend.app.domain.catalog import Product
from src.backend.app.infrastructure.vectors.postgres_store import combo_members_of
from src.backend.tests.conftest import EVENTS, ROWS, FakeEmbedder, P

# Catalog test: C1 = combo gồm phòng R1 (→ khách sạn H1) + vé A1; C2 = combo gồm A1 + golf G1 (chung A1 với C1); C3 chưa map.
COMBO_ROWS = ROWS + [
    P("C2", "Combo VinWonders + Golf", "combo", "Nha Trang", {}, price=3000000),
    P("C3", "Combo chưa map", "combo", "Nha Trang", {}, price=2000000),
]
COMBO_ITEMS = [
    {"combo_product_id": "C1", "position": 1, "label": "Phòng Deluxe", "item_kind": "hotel", "item_product_id": "R1",
     "source": "description_parse", "confidence": 0.95},
    {"combo_product_id": "C1", "position": 2, "label": "Vé VinWonders", "item_kind": "attraction", "item_product_id": "A1",
     "source": "manual", "confidence": 0.6},
    {"combo_product_id": "C2", "position": 1, "label": "Vé VinWonders", "item_kind": "attraction", "item_product_id": "A1",
     "source": "description_parse", "confidence": 0.9},
    {"combo_product_id": "C2", "position": 2, "label": "Golf", "item_kind": "golf", "item_product_id": "G1",
     "source": "description_parse", "confidence": 0.8},
    # chỉ khớp địa điểm (0,60), không sửa tay → không tin
    {"combo_product_id": "C3", "position": 1, "label": "Vé", "item_kind": "attraction", "item_product_id": "A1",
     "source": "description_parse", "confidence": 0.6},
    {"combo_product_id": "C3", "position": 2, "label": "Bữa tối", "item_kind": "meal", "item_product_id": None,
     "source": "description_parse", "confidence": None},
]


def test_combo_members_of_keeps_only_trusted_mapping_rows():
    by_combo = {}
    for it in COMBO_ITEMS:
        by_combo.setdefault(it["combo_product_id"], []).append(it)
    members = combo_members_of(by_combo)
    assert members == {"C1": ("R1", "A1"), "C2": ("A1", "G1")}        # C3: 0,60 tự động + chưa map → không có
    assert combo_members_of({}) == {}


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    d = tmp_path_factory.mktemp("combo")
    (d / "products.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in COMBO_ROWS), encoding="utf-8")
    (d / "combo_items.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in COMBO_ITEMS), encoding="utf-8")
    (d / "events.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in EVENTS), encoding="utf-8")
    from src.backend.tests.fakes.in_memory_vector_store import InMemoryVectorStore
    from src.backend.tests.fakes.jsonl_cdp_reader import JsonlCdpReader
    index, vectors = InMemoryVectorStore(str(d / "products.jsonl"), FakeEmbedder(), str(d / ".embcache")).load()
    cdp = JsonlCdpReader(str(d / "events.jsonl"))
    now = datetime(2026, 9, 21, tzinfo=timezone.utc)
    return {"index": index, "vectors": vectors, "cdp": cdp, "now": now,
            "recommend": RecommendForUser(index, vectors, cdp, BuildPopularity(index, cdp)(now=now))}


def test_unit_index_resolves_combo_relations_to_search_units(world):
    ix: UnitIndex = world["index"]
    u = ix.idx
    assert ix.components_of[u["C1"]] == {u["H1"], u["A1"]}            # phòng R1 → khách sạn H1
    assert ix.components_of[u["C2"]] == {u["A1"], u["G1"]}
    assert u["C3"] not in ix.components_of
    assert ix.combos_with[u["A1"]] == {u["C1"], u["C2"]} and ix.combos_with[u["H1"]] == {u["C1"]}


def test_purchase_closure_is_two_way_and_one_hop(world):
    ix: UnitIndex = world["index"]
    u = ix.idx
    # mua thành phần → combo chứa nó
    assert ix.purchase_closure({u["H1"]}) == {u["H1"], u["C1"]}
    assert ix.purchase_closure({u["A1"]}) == {u["A1"], u["C1"], u["C2"]}
    # mua combo → các thành phần, nhưng KHÔNG kéo theo combo khác chung thành phần (một bậc: C1 ∌ C2)
    assert ix.purchase_closure({u["C1"]}) == {u["C1"], u["H1"], u["A1"]}
    # combo chưa map và unit thường không kéo theo gì
    assert ix.purchase_closure({u["C3"]}) == {u["C3"]} and ix.purchase_closure({u["F1"]}) == {u["F1"]}
    assert ix.purchase_closure(set()) == set()


def test_bought_units_reads_raw_events_by_search_unit(world):
    ix: UnitIndex = world["index"]
    u = ix.idx
    events = [{"eventName": "purchase", "productId": "R1"}, {"eventName": "product_view", "productId": "A1"},
              {"eventName": "purchase", "productId": "ngoai-catalog"}, {"eventName": "add_to_cart", "productId": "C2"}]
    assert bought_units(ix, events) == {u["H1"], u["C1"]}             # view / cart / ngoài catalog không tính


def _history(uid, product, now, *, bought_at_days, using_date, group="G1"):
    t = (now - timedelta(days=bought_at_days)).isoformat()
    return [{"cdpUserId": uid, "eventName": "purchase", "productId": product, "timestamp": t, "usingDate": using_date,
             "eventGroupId": group}]


def _ids(r):
    return {x["productId"] for x in r["recommendations"]}


def test_buying_a_component_hides_combos_containing_it_in_open_trip(world):
    """AC-REC-02 / AC-REC-03: vừa đặt phòng R1 (chuyến mở tại Nha Trang) → không gợi H1 (đã mua) lẫn C1 (combo chứa phòng)."""
    now = world["now"]
    r = world["recommend"]("U1", k=6, now=now, events=_history("U1", "R1", now, bought_at_days=2, using_date="2026-10-05"))
    assert r["strategy"] == "cross_vertical"
    assert not _ids(r) & {"H1", "C1"}
    assert "C2" in _ids(r)                                           # combo không chứa phòng vẫn được gợi


def test_buying_a_combo_hides_its_components_but_not_sibling_combo(world):
    """AC-REC-03: đã mua combo C1 (chuyến đã xong) → không gợi C1, H1, A1; C2 (chung A1) và các món khác vẫn còn."""
    now = world["now"]
    r = world["recommend"]("U2", k=8, now=now, events=_history("U2", "C1", now, bought_at_days=120, using_date="2026-06-10"))
    assert r["strategy"] in ("long_term", "dormant") and r["diagnostics"]["excludedVerticals"] == []
    assert not _ids(r) & {"C1", "H1", "A1"}
    assert _ids(r) & {"C2", "G1", "F1", "H2", "H3"}


def test_buying_a_single_ticket_hides_every_combo_containing_it(world):
    now = world["now"]
    r = world["recommend"]("U3", k=8, now=now, events=_history("U3", "A1", now, bought_at_days=200, using_date="2026-03-01"))
    assert not _ids(r) & {"A1", "C1", "C2"} and "C3" in _ids(r)     # C3 chưa map tin cậy nên không bị kéo theo


def test_exclusion_applies_to_every_past_purchase_not_only_open_trip(world):
    """Mọi lần mua: chuyến cũ đã xong mua R1 + chuyến mở mới ở Phú Quốc → H1 và C1 vẫn không xuất hiện khi trang chủ mở rộng."""
    now = world["now"]
    old = _history("U4", "R1", now, bought_at_days=300, using_date="2025-12-01", group="OLD")
    new = _history("U4", "R3", now, bought_at_days=1, using_date="2026-10-01", group="NEW")
    r = world["recommend"]("U4", k=6, now=now, events=old + new)
    assert r["strategy"] == "cross_vertical" and r["destination"] == "Phú Quốc"
    assert not _ids(r) & {"H1", "C1", "H3"}


def test_purchase_without_vector_is_still_excluded(world):
    """Mua món chưa có vector (ngoài kho vector nhưng trong catalog) vẫn bị loại: tập đã mua tính từ event thô."""
    ix, store, cdp, now = world["index"], world["vectors"], world["cdp"], world["now"]

    class NoVectorForC1:
        dimension = store.dimension

        def vectors(self, ids):
            return {k: v for k, v in store.vectors(ids).items() if k != "C1"}

        def near_vector(self, *a, **kw):
            return [h for h in store.near_vector(*a, **kw) if h.product_id != "C1"]

    rec = RecommendForUser(ix, NoVectorForC1(), cdp, BuildPopularity(ix, cdp)(now=now))
    events = _history("U5", "C1", now, bought_at_days=100, using_date="2026-06-10") + \
        _history("U5", "FL1", now, bought_at_days=90, using_date="2026-06-25", group="G2")
    r = rec("U5", k=8, now=now, events=events)
    assert r["strategy"] != "popular" and not _ids(r) & {"C1", "H1", "A1", "F1"}
