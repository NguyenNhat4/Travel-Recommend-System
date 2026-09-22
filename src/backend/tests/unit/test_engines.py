import json

def test_search_total_equals_facets(services):
    r = services["search"]("nghỉ dưỡng biển cho gia đình", destination="Nha Trang", limit=5)
    assert r["total"] == sum(r["facets"]["taxonomy"].values()) == r["diagnostics"]["relevantCount"]
    assert r["diagnostics"]["totalExact"] is True
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
