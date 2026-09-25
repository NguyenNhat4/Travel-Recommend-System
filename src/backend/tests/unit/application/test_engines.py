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
