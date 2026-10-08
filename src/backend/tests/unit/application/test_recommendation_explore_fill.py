"""Ô khám phá khi có chuyến mở — FR-REC-02 (chốt 2026-10-09, đề xuất `update-archive/2026-10-08-recsys-o-kham-pha-khi-co-chuyen-mo.md`).

Chỉ lấp ô còn trống sau khi hết món tại X; món ở điểm đến khác theo cos(u_long), mỗi điểm đến tối đa 1 món, chỉ
hotel / attraction / combo, không gồm món đã mua (kể cả closure combo); xếp sau món tại X; `strategy` / `nextVertical`
tính trên món tại X; không gọi thêm `near_vector` khi đã đủ k; tắt cờ hoặc không chuyến mở → không lấp."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from src.backend.app.application.recommendation import BuildPopularity, RecommendForUser
from src.backend.tests.conftest import EVENTS, ROWS, FakeEmbedder, P

# Nha Trang (X) có đúng 4 món không phải khách sạn: F1, A1, C1, G1 (mỗi taxonomy 1 → MAX_PER_VERTICAL không cắt).
# Điểm đến khác: Phú Quốc H3 (+ phòng R3), A5 Grand World, F5 (tuyến bay — không thuộc whitelist); Đà Nẵng A6, C6; Hội An H7.
EXTRA = [
    P("A5", "Grand World Phú Quốc", "attraction", "Phú Quốc", {}, price=500000),
    P("F5", "Vé máy bay Hà Nội - Phú Quốc", "flight", "Phú Quốc", {"level": "route"}, price=None),
    P("FL5", "Vé máy bay Hà Nội - Phú Quốc VJ555", "flight", "Phú Quốc", {"level": "flight", "parentProductId": "F5"}, price=1500000),
    P("A6", "Bà Nà Hills", "attraction", "Đà Nẵng", {}, price=900000),
    P("C6", "Combo Đà Nẵng 3N2Đ", "combo", "Đà Nẵng", {}, price=7000000),
    P("H7", "Hội An Resort", "hotel", "Hội An", {"level": "property"}, price=None),
    P("R7", "Hội An Resort - Garden", "hotel", "Hội An", {"level": "room", "parentProductId": "H7"}, price=2000000),
]
COMBO_ITEMS = [{"combo_product_id": "C6", "position": 1, "label": "Bà Nà", "item_kind": "attraction", "item_product_id": "A6",
                "source": "manual", "confidence": 0.9}]


class CountingVectors:
    """Bọc kho vector để đếm số lượt near_vector (chi phí của ô khám phá)."""

    def __init__(self, inner):
        self.inner, self.calls = inner, 0
        self.dimension = inner.dimension

    def vectors(self, ids):
        return self.inner.vectors(ids)

    def near_vector(self, *a, **kw):
        self.calls += 1
        return self.inner.near_vector(*a, **kw)


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    d = tmp_path_factory.mktemp("explore")
    (d / "products.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in ROWS + EXTRA), encoding="utf-8")
    (d / "combo_items.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in COMBO_ITEMS), encoding="utf-8")
    (d / "events.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in EVENTS), encoding="utf-8")
    from src.backend.tests.fakes.in_memory_vector_store import InMemoryVectorStore
    from src.backend.tests.fakes.jsonl_cdp_reader import JsonlCdpReader
    index, vectors = InMemoryVectorStore(str(d / "products.jsonl"), FakeEmbedder(), str(d / ".embcache")).load()
    cdp = JsonlCdpReader(str(d / "events.jsonl"))
    now = datetime(2026, 9, 21, tzinfo=timezone.utc)
    return {"index": index, "vectors": vectors, "cdp": cdp, "now": now, "pop": BuildPopularity(index, cdp)(now=now)}


def _engine(world, **kw):
    vec = CountingVectors(world["vectors"])
    return RecommendForUser(world["index"], vec, world["cdp"], world["pop"], **kw), vec


def _open_trip(now, extra=()):
    """Đặt phòng R1 Nha Trang, chuyến chưa diễn ra; `extra` = event cũ để u_long có hướng."""
    t = (now - timedelta(days=2)).isoformat()
    return list(extra) + [{"cdpUserId": "U", "eventName": "purchase", "productId": "R1", "timestamp": t,
                           "usingDate": "2026-10-05", "eventGroupId": "OPEN"}]


def test_fills_only_empty_slots_after_destination_items(world):
    now = world["now"]
    rec, vec = _engine(world)
    r = rec("U", k=6, now=now, events=_open_trip(now))
    recs = r["recommendations"]
    assert r["strategy"] == "cross_vertical" and r["destination"] == "Nha Trang"
    at_x = [x for x in recs if x["destination"] == "Nha Trang"]
    explore = [x for x in recs if x["destination"] != "Nha Trang"]
    assert {x["productId"] for x in at_x} == {"F1", "A1", "C1", "G1"}            # món tại X không bị thay
    assert len(explore) == 2 and r["diagnostics"]["exploreFilled"] == 2
    assert recs[:4] == at_x and [x["rank"] for x in recs] == [1, 2, 3, 4, 5, 6]   # xếp sau, rank liên tục
    assert all(x["taxonomy"] in ("hotel", "attraction", "combo") for x in explore)
    assert len({x["destination"] for x in explore}) == 2                        # mỗi điểm đến tối đa 1 món
    # lý do theo u_long; vector giả ngẫu nhiên nên chỉ đòi because[] ở món có cos(u_long) > 0 (score của ô khám phá)
    assert all(x["because"] for x in explore if x["score"] > 0)
    assert r["nextVertical"] in {"flight", "attraction", "combo", "golf"}        # tính trên món tại X
    assert vec.calls == 3                                                        # u_short + u_long + 1 lượt khám phá


def test_no_extra_vector_call_when_destination_already_fills_k(world):
    now = world["now"]
    rec, vec = _engine(world)
    r = rec("U", k=4, now=now, events=_open_trip(now))
    assert all(x["destination"] == "Nha Trang" for x in r["recommendations"])
    assert r["diagnostics"]["exploreFilled"] == 0 and vec.calls == 2


def test_explore_skips_bought_units_and_their_combos(world):
    """Đã mua vé A6 (Đà Nẵng) ở chuyến cũ → ô khám phá không lấy A6 lẫn combo C6 chứa nó, Đà Nẵng vẫn có thể góp món khác."""
    now = world["now"]
    old = [{"cdpUserId": "U", "eventName": "purchase", "productId": "A6", "timestamp": (now - timedelta(days=200)).isoformat(),
            "usingDate": "2026-03-10", "eventGroupId": "OLD"}]
    rec, _ = _engine(world)
    r = rec("U", k=8, now=now, events=_open_trip(now, old))
    ids = {x["productId"] for x in r["recommendations"]}
    assert not ids & {"A6", "C6", "H1"}
    explore = [x for x in r["recommendations"] if x["destination"] != "Nha Trang"]
    assert explore and len({x["destination"] for x in explore}) == len(explore)
    assert "F5" not in ids                                                       # tuyến bay không thuộc whitelist


def test_flag_off_returns_pre_pr_a_list(world):
    now = world["now"]
    rec_off, vec = _engine(world, explore_fill=False)
    r = rec_off("U", k=6, now=now, events=_open_trip(now))
    assert all(x["destination"] == "Nha Trang" for x in r["recommendations"]) and len(r["recommendations"]) == 4
    assert r["diagnostics"]["exploreFilled"] == 0 and vec.calls == 2


def test_no_fill_without_open_trip(world):
    now = world["now"]
    rec, vec = _engine(world)
    done = [{"cdpUserId": "U", "eventName": "purchase", "productId": "R1", "timestamp": (now - timedelta(days=100)).isoformat(),
             "usingDate": "2026-07-01", "eventGroupId": "DONE"}]
    r = rec("U", k=6, now=now, events=done)
    assert r["strategy"] == "long_term" and r["diagnostics"]["exploreFilled"] == 0 and vec.calls == 1


def test_locked_destination_request_still_fills(world):
    """Trang xác nhận khoá destination=X: món tại X đứng trước, ô trống vẫn lấp bằng điểm đến khác (spec §4.7)."""
    now = world["now"]
    rec, _ = _engine(world)
    r = rec("U", k=6, now=now, events=_open_trip(now), destination="Nha Trang")
    recs = r["recommendations"]
    assert r["destination"] == "Nha Trang" and all(x["destination"] == "Nha Trang" for x in recs[:4])
    assert r["diagnostics"]["exploreFilled"] == 2 and all(x["destination"] != "Nha Trang" for x in recs[4:])
