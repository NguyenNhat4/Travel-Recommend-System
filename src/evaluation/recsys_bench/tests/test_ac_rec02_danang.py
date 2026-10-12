"""AC-REC-02 (`docs/prd/requirements.md` §3) mã hoá bằng lịch sử tổng hợp trên catalog thật — không ghi DB.

Kịch bản: khách xem, thêm giỏ rồi mua một hạng phòng tại Đà Nẵng, ngày nhận phòng 10 ngày sau `as_of` (chuyến đang mở).
Kỳ vọng: `cross_vertical`, `excludedVerticals == ["hotel"]`, không có khách sạn, có ≥ 1 chuyến bay đến Đà Nẵng và ≥ 1 hoạt
động tại Đà Nẵng (Bà Nà nằm trong đó), mỗi món có `because[]`; đúng cả khi request khoá `destination="Đà Nẵng"` (trang xác
nhận) lẫn khi không (trang chủ).

Phần "tour Hội An" của AC-REC-02 **không kiểm ở đây**: Hội An là điểm đến riêng trong catalog, luật khoá điểm đến của
FR-REC-02 loại nó theo thiết kế — đề xuất sửa câu AC ở `docs/prd/update/2026-10-08-recsys-loai-san-pham-da-mua-va-combo.md`.

Cần DB catalog (`DATABASE_URL`) và vector (`RECSYS_VEC`, dạng `npy:<prefix>`); thiếu thì skip (CI không có).
Chạy: RECSYS_VEC=npy:/path/vec_prodcopy_e5s pytest src/evaluation/recsys_bench/tests/test_ac_rec02_danang.py -q
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import pytest

VEC = os.environ.get("RECSYS_VEC")
AS_OF = datetime(2026, 10, 8, tzinfo=timezone.utc)
DEST = "Đà Nẵng"

pytestmark = pytest.mark.skipif(not VEC or not os.environ.get("DATABASE_URL"),
                                reason="cần DATABASE_URL (catalog) và RECSYS_VEC=npy:<prefix>")


@pytest.fixture(scope="module")
def world():
    from src.evaluation.recsys_bench.data_source import load_events, load_index
    from src.evaluation.recsys_bench.engine import OfflineEngine
    idx, vec = load_index(VEC)
    purchases = [e for e in load_events() if e["eventName"] == "purchase"]
    return idx, OfflineEngine(idx, vec, purchases, mode="prod")


def _danang_room(idx):
    """Một hạng phòng Đà Nẵng có cha là khách sạn gợi ý được (mua phòng → engine resolve về khách sạn)."""
    for u in idx.units:
        if u.taxonomy == "hotel" and u.destination == DEST and idx.recommendable[idx.idx[u.product_id]]:
            for child, parent in idx.parent_of.items():
                if parent == u.product_id:
                    return child, u.product_id
    pytest.skip("catalog không có phòng Đà Nẵng")


def _history(uid, room_id):
    t = lambda d, h=0: (AS_OF - timedelta(days=d, hours=h)).isoformat()
    using = (AS_OF + timedelta(days=10)).date().isoformat()
    return [
        {"cdpUserId": uid, "eventName": "product_view", "timestamp": t(1, 6), "productId": room_id, "taxonomy": "hotel",
         "eventGroupId": None, "quantity": None, "unitPrice": None, "usingDate": None},
        {"cdpUserId": uid, "eventName": "add_to_cart", "timestamp": t(1, 5), "productId": room_id, "taxonomy": "hotel",
         "eventGroupId": None, "quantity": 1, "unitPrice": None, "usingDate": using},
        {"cdpUserId": uid, "eventName": "purchase", "timestamp": t(1, 4), "productId": room_id, "taxonomy": "hotel",
         "eventGroupId": "ACREC02-T1", "quantity": 1, "unitPrice": None, "usingDate": using},
    ]


@pytest.mark.parametrize("pin_destination", [True, False], ids=["trang-xac-nhan", "trang-chu"])
def test_booking_in_danang_prioritises_flights_and_activities_there(world, pin_destination):
    idx, eng = world
    room, hotel = _danang_room(idx)
    res = eng.recommend("ACREC02", AS_OF, 4, _history("ACREC02", room),
                        ) if not pin_destination else _recommend_pinned(eng, idx, room)
    recs = res["recommendations"]
    assert res["strategy"] == "cross_vertical"
    assert res["destination"] == DEST
    assert res["diagnostics"]["excludedVerticals"] == ["hotel"]
    assert recs, "danh sách rỗng"
    assert all(r["destination"] == DEST for r in recs), [r["destination"] for r in recs]
    assert all(r["taxonomy"] != "hotel" for r in recs)
    assert hotel not in {r["productId"] for r in recs}
    taxonomies = {r["taxonomy"] for r in recs}
    assert "flight" in taxonomies, taxonomies
    assert taxonomies & {"attraction", "combo", "golf"}, taxonomies
    assert all(r["because"] for r in recs), [(r["name"], r["because"]) for r in recs]


def _recommend_pinned(eng, idx, room):
    """Trang xác nhận gửi `destination=<điểm đến của đơn>`; OfflineEngine không có tham số đó nên gọi thẳng RecommendForUser."""
    from src.backend.app.application.recommendation.use_cases import RecommendForUser
    from src.backend.app.domain.recommendation.profile import MAX_PER_VERTICAL
    engine = RecommendForUser(eng.index, eng.vectors, eng.reader_at(AS_OF), eng.popularity_at(AS_OF),
                              candidate_k=eng.candidate_k, popular_k=eng.popular_k, max_per_vertical=MAX_PER_VERTICAL)
    return engine("ACREC02", k=4, now=AS_OF, events=_history("ACREC02", room), destination=DEST)


def test_bana_items_exist_and_are_recommendable(world):
    """Tiền đề của AC: catalog có hoạt động Bà Nà tại Đà Nẵng và chúng gợi ý được."""
    idx, _ = world
    bana = [u for u in idx.units if "Bà Nà" in u.name and u.destination == DEST]
    assert bana, "không có sản phẩm Bà Nà tại Đà Nẵng"
    assert any(idx.recommendable[idx.idx[u.product_id]] for u in bana)
