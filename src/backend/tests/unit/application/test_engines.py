import json

def test_search_total_equals_facets(services):
    r = services["search"]("nghỉ dưỡng biển cho gia đình", destination="Nha Trang", limit=5)
    assert r["total"] == sum(r["facets"]["taxonomy"].values()) == r["diagnostics"]["relevantCount"]
    d = r["diagnostics"]
    assert (d["searchMode"], d["approximate"], d["totalExact"], d["facetsExact"]) == ("ANN_CANDIDATE_SCORE", True, False, False)
    assert {"description", "attributes", "currency", "priceUnit", "available",
            "availableFrom", "availableTo"} <= r["results"][0].keys()
    json.dumps(r)

def test_similar_excludes_self_and_siblings(services):
    names = [x["name"] for x in services["similar"]("R1", k=5)]
    assert "Vinpearl Resort Nha Trang" not in names and all("Deluxe" not in n for n in names)

def test_cross_vertical_with_because(services):
    r = services["recommend"]("P1", k=3, now=services["now"])
    assert r["strategy"] == "cross_vertical" and r["diagnostics"]["excludedVerticals"] == ["hotel"]
    assert all(x["taxonomy"] != "hotel" for x in r["recommendations"])
    assert any(x["because"] for x in r["recommendations"])
    assert all(isinstance(reason["daysAgo"], int)
               for item in r["recommendations"] for reason in item["because"])
    json.dumps(r)

def test_dormant(services):
    assert services["recommend"]("P3", k=2, now=services["now"])["strategy"] == "dormant"

def test_new_user_sections(services):
    r = services["recommend"](None, k=4, now=services["now"])
    assert r["strategy"] == "popular" and r["sections"]
    assert {s["reason"]["type"] for s in r["sections"]} <= {"top_month", "season"}
    assert all(x["because"] == [] for x in r["recommendations"])
    json.dumps(r)

def test_recommendations_can_be_scoped_to_requested_destination(services):
    r = services["recommend"](None, k=4, now=services["now"], destination="Phú Quốc")
    assert r["destination"] == "Phú Quốc"
    assert all(x["destination"] == "Phú Quốc" for x in r["recommendations"])


def test_search_prefilters_ids_before_top_k(services):
    """Filter đi trước top-K: ứng viên ngoài destination không chiếm chỗ trong pool."""
    r = services["search"]("resort", destination="Phú Quốc", limit=50)
    assert r["results"] and all(x["destination"] == "Phú Quốc" for x in r["results"])
    assert r["total"] <= r["diagnostics"]["filteredCount"]


def test_search_total_and_facets_stable_across_pages(services):
    first = services["search"]("biển", limit=1, offset=0)
    second = services["search"]("biển", limit=1, offset=1)
    assert first["total"] == second["total"] and first["facets"] == second["facets"]
    assert first["results"][0]["productId"] != second["results"][0]["productId"]


def test_search_total_is_bounded_by_candidate_pool(services):
    from src.backend.app.application.search import SearchProducts

    small = SearchProducts(services["index"], services["vectors"], services["search"].embedder, cutoff=-1.0, candidate_k=2)
    r = small("biển", limit=10)
    assert r["total"] == len(r["results"]) == 2


def test_similar_same_taxonomy_only(services):
    anchor_taxonomy = services["index"].taxonomy[services["index"].resolve("R1")]
    assert all(x["taxonomy"] == anchor_taxonomy for x in services["similar"]("R1", k=5))


def test_popular_units_fill_the_pool_when_vector_neighbours_lack_variety(services):
    """W_POP đủ lớn để món phổ biến xa profile vẫn lọt top; top-K theo vector một mình sẽ bỏ sót và trả thiếu k."""
    from src.backend.app.application.recommendation import RecommendForUser

    rec = services["recommend"]

    class OneNeighbour:  # kho vector chỉ trả 1 hàng xóm, như khi mọi ứng viên gần profile cùng một loại
        dimension = rec.vectors.dimension

        def near_vector(self, vector, allowed, limit, *, with_vectors=False):
            return rec.vectors.near_vector(vector, allowed, 1, with_vectors=with_vectors)

        def vectors(self, product_ids):
            return rec.vectors.vectors(product_ids)

    class EveryUnitPopular:
        def unit_scores(self, destination=None):
            return {i: 1.0 for i in range(len(rec.index.units))}

    def run(popular_k):
        return RecommendForUser(rec.index, OneNeighbour(), rec.cdp, EveryUnitPopular(), popular_k=popular_k)(
            "P3", k=4, now=services["now"])

    assert len(run(0)["recommendations"]) == 1
    assert len(run(50)["recommendations"]) > 1


def _booking_history(uid, room, using_date, now):
    """Khách xem, thêm giỏ rồi mua một hạng phòng — khuôn AC-REC-02 (`docs/prd/requirements.md` §3) trên catalog giả."""
    t = lambda h: (now.replace(microsecond=0) - __import__("datetime").timedelta(hours=h)).isoformat()
    return [
        {"cdpUserId": uid, "eventName": "product_view", "productId": room, "timestamp": t(30), "eventGroupId": None},
        {"cdpUserId": uid, "eventName": "add_to_cart", "productId": room, "timestamp": t(29), "usingDate": using_date},
        {"cdpUserId": uid, "eventName": "purchase", "productId": room, "timestamp": t(28), "usingDate": using_date,
         "eventGroupId": "AC02"},
    ]


def test_ac_rec_02_booking_prioritises_flights_and_activities_at_the_destination(services):
    """AC-REC-02: vừa đặt phòng tại X (chuyến chưa diễn ra) → trang xác nhận (khoá destination) và trang chủ (không khoá)
    đều ưu tiên vé máy bay đến X và hoạt động tại X, không có khách sạn, mỗi món có because[]. Bản trên catalog thật:
    src/evaluation/recsys_bench/tests/test_ac_rec02_danang.py."""
    now = services["now"]
    history = _booking_history("AC02", "R1", "2026-10-01", now)
    for destination in ("Nha Trang", None):
        r = services["recommend"]("AC02", k=4, now=now, events=history, destination=destination)
        recs = r["recommendations"]
        assert r["strategy"] == "cross_vertical" and r["destination"] == "Nha Trang"
        assert r["diagnostics"]["excludedVerticals"] == ["hotel"]
        assert recs and all(x["destination"] == "Nha Trang" and x["taxonomy"] != "hotel" for x in recs)
        assert "H1" not in {x["productId"] for x in recs}
        taxonomies = {x["taxonomy"] for x in recs}
        assert "flight" in taxonomies and taxonomies & {"attraction", "combo", "golf"}, taxonomies
        assert all(x["because"] for x in recs)
