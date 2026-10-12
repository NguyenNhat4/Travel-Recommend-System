"""Cold-start tối đa 2 món mỗi taxonomy (search-recommendation §4.8, chốt 2026-10-12).

Lượt mua chuyến bay dồn về tuyến nên, khi không có trần, 2–3 món đầu của "phổ biến tại điểm đến" đều là tuyến bay.
Trần áp cho cả ba đường cold-start: có `destination`, ghép từ các section điểm đến, và xếp theo reviewCount khi chưa có
bảng phổ biến. `max_per_vertical=None` (harness eval) thì không có trần.
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone

import pytest

from src.backend.app.application.recommendation import BuildPopularity, RecommendForUser
from src.backend.tests.conftest import FakeEmbedder, P


def route(pid, dest, reviews=0):
    return [P(pid, f"Vé máy bay Hà Nội - {dest} {pid}", "flight", dest, {"level": "route", "reviewCount": reviews}, price=None),
            P(f"{pid}-x", f"Vé máy bay Hà Nội - {dest} {pid} VN1", "flight", dest,
              {"level": "flight", "parentProductId": pid}, price=1_500_000)]


def hotel(pid, dest, reviews=0):
    return [P(pid, f"Khách sạn {dest} {pid}", "hotel", dest, {"level": "property", "reviewCount": reviews}, price=None),
            P(f"{pid}-r", f"Khách sạn {dest} {pid} - Deluxe", "hotel", dest,
              {"level": "room", "parentProductId": pid}, price=2_000_000)]


ROWS = [
    # Đà Nẵng: ba tuyến bay được mua nhiều nhất, rồi khách sạn và vé tham quan.
    *route("F41", "Đà Nẵng", 900), *route("F42", "Đà Nẵng", 800), *route("F43", "Đà Nẵng", 700),
    *hotel("H41", "Đà Nẵng", 50),
    P("A41", "Bà Nà Hills", "attraction", "Đà Nẵng", {"reviewCount": 40}, price=900_000),
    # Đà Lạt chỉ có tuyến bay; Sa Pa có tuyến bay và một khách sạn — để kiểm trần trên danh sách ghép từ nhiều section.
    *route("F21", "Đà Lạt"), *route("F22", "Đà Lạt"),
    *route("F31", "Sa Pa"), *route("F32", "Sa Pa"), *hotel("H31", "Sa Pa"),
]


def purchase(uid, pid, day):
    return {"cdpUserId": uid, "eventName": "purchase", "productId": pid,
            "timestamp": f"2026-09-{day:02d}T10:00:00Z", "eventGroupId": f"{uid}-{pid}"}


# Đà Nẵng: F41 ×3, F42 ×3, F43 ×2, H41 ×1, A41 ×1 (ngoài 30 ngày gần nhất để không lập section tháng).
# Đà Lạt (5 lượt) và Sa Pa (3 lượt) trong 30 ngày gần nhất → hai section "điểm đến được đặt nhiều tháng 9".
EVENTS = (
    [purchase(f"u{n}", "F41-x", 1) for n in range(3)] + [purchase(f"v{n}", "F42-x", 1) for n in range(3)]
    + [purchase(f"w{n}", "F43-x", 1) for n in range(2)] + [purchase("h1", "H41-r", 1), purchase("a1", "A41", 1)]
)


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    from src.backend.tests.fakes.in_memory_vector_store import InMemoryVectorStore
    from src.backend.tests.fakes.jsonl_cdp_reader import JsonlCdpReader

    now = datetime(2026, 9, 21, tzinfo=timezone.utc)
    recent = ([purchase(f"d{n}", "F21-x", 15) for n in range(3)] + [purchase(f"e{n}", "F22-x", 15) for n in range(2)]
              + [purchase(f"s{n}", "F31-x", 16) for n in range(2)] + [purchase("s9", "F32-x", 16)])
    old = [{**e, "timestamp": e["timestamp"].replace("2026-09-01", "2026-08-01")} for e in EVENTS]
    d = tmp_path_factory.mktemp("coldcap")
    (d / "products.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in ROWS), encoding="utf-8")
    (d / "events.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in old + recent),
                                    encoding="utf-8")
    index, vectors = InMemoryVectorStore(str(d / "products.jsonl"), FakeEmbedder(), str(d / ".embcache")).load()
    cdp = JsonlCdpReader(str(d / "events.jsonl"))
    return {"index": index, "vectors": vectors, "cdp": cdp, "now": now, "pop": BuildPopularity(index, cdp)(now=now)}


def taxonomies(result):
    return Counter(x["taxonomy"] for x in result["recommendations"])


def test_destination_cold_start_keeps_at_most_two_flights_in_popular_order(world):
    rec = RecommendForUser(world["index"], world["vectors"], world["cdp"], world["pop"])
    r = rec(None, k=4, now=world["now"], destination="Đà Nẵng")
    ids = [x["productId"] for x in r["recommendations"]]
    assert r["strategy"] == "popular" and len(ids) == 4
    assert ids[:2] == ["F41", "F42"]                         # hai tuyến bay mua nhiều nhất vẫn đứng đầu
    assert taxonomies(r)["flight"] == 2 and "F43" not in ids  # tuyến thứ ba nhường chỗ cho khách sạn / vé tham quan
    assert {"H41", "A41"} <= set(ids)


def test_eval_mode_without_cap_keeps_the_old_order(world):
    rec = RecommendForUser(world["index"], world["vectors"], world["cdp"], world["pop"], max_per_vertical=None)
    ids = [x["productId"] for x in rec(None, k=4, now=world["now"], destination="Đà Nẵng")["recommendations"]]
    assert ids[:3] == ["F41", "F42", "F43"]


def test_flat_list_from_several_sections_is_capped_too(world):
    rec = RecommendForUser(world["index"], world["vectors"], world["cdp"], world["pop"])
    r = rec(None, k=4, now=world["now"])
    assert r["sections"] and taxonomies(r)["flight"] <= 2
    assert "H31" in {x["productId"] for x in r["recommendations"]}
    assert [x["rank"] for x in r["recommendations"]] == list(range(1, len(r["recommendations"]) + 1))


def test_review_count_fallback_without_popularity_is_capped(world):
    rec = RecommendForUser(world["index"], world["vectors"], world["cdp"], None)
    r = rec(None, k=4, now=world["now"])
    assert r["diagnostics"]["popularitySource"] == "reviewCount"
    assert taxonomies(r)["flight"] == 2 and len(r["recommendations"]) == 4
