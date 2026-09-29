"""Helper hậu xử lý dùng chung cho route và tool itinerary: recommendation, search, destinations."""
import numpy as np

from src.backend.app.application.catalog.views import destination_list
from src.backend.app.application.itinerary.contracts import valid
from src.backend.app.application.recommendation.responses import recommendation_response
from src.backend.app.application.search.responses import SEARCH_ENGINE_ONLY_FIELDS, search_tool_payload


# --- recommendation_response --------------------------------------------------------------------

def test_recommendation_response_forwards_arguments_and_adds_identity_and_latency():
    calls = []

    def recommend(cdp_user_id, **kwargs):
        calls.append((cdp_user_id, kwargs))
        return {"strategy": "popular", "recommendations": [], "diagnostics": {"eventsUsed": 0}}

    result = recommendation_response(recommend, "VP0000001", k=3, destination="Nha Trang")
    assert calls == [("VP0000001", {"k": 3, "destination": "Nha Trang"})]
    assert result["cdpUserId"] == "VP0000001"
    assert result["diagnostics"]["eventsUsed"] == 0
    assert isinstance(result["diagnostics"]["latencyMs"], int) and result["diagnostics"]["latencyMs"] >= 0


def test_recommendation_response_creates_diagnostics_when_missing():
    result = recommendation_response(lambda cdp_user_id, **_: {"recommendations": []}, None, k=5, destination=None)
    assert result["cdpUserId"] is None
    assert set(result["diagnostics"]) == {"latencyMs"}


def test_recommendation_response_matches_contract_for_guest_and_member(services):
    guest = recommendation_response(services["recommend"], None, k=5, destination=None)
    member = recommendation_response(services["recommend"], "P1", k=5, destination="Nha Trang")
    assert valid("RecommendationResponse", guest) and guest["cdpUserId"] is None
    assert valid("RecommendationResponse", member) and member["cdpUserId"] == "P1"


# --- search_tool_payload ------------------------------------------------------------------------

def test_search_tool_payload_drops_engine_only_fields_without_mutating_input():
    data = {"results": [], "total": 0, "limit": 20, "offset": 0, "topScore": None, "cutoff": 0.62,
            "facets": {"taxonomy": {}, "destination": {}}, "diagnostics": {"latencyMs": 3}}
    payload = search_tool_payload(data)
    assert SEARCH_ENGINE_ONLY_FIELDS == {"cutoff", "diagnostics"}
    assert payload == {"results": [], "total": 0, "limit": 20, "offset": 0, "topScore": None,
                       "facets": {"taxonomy": {}, "destination": {}}}
    assert "cutoff" in data and "diagnostics" in data


def test_search_tool_payload_of_engine_result_matches_contract(services):
    payload = search_tool_payload(services["search"]("resort biển", destination="Nha Trang", limit=5, offset=0))
    assert payload["results"]
    assert not SEARCH_ENGINE_ONLY_FIELDS & payload.keys()
    assert valid("SearchResponse", payload)


# --- destination_list ---------------------------------------------------------------------------

def test_destination_list_counts_and_sorts_by_name():
    body = destination_list(["Phú Quốc", "Nha Trang", "Nha Trang", "Đà Nẵng"])
    assert body == {"destinations": [{"destination": "Nha Trang", "productCount": 2},
                                     {"destination": "Phú Quốc", "productCount": 1},
                                     {"destination": "Đà Nẵng", "productCount": 1}]}
    assert destination_list([]) == {"destinations": []}


def test_destination_list_stringifies_index_values(services):
    # index.destination là mảng numpy; tên phải ra str thuần để JSON hoá và khớp contract.
    body = destination_list(np.array(["Nha Trang", "Nha Trang"], dtype=object))
    assert body == {"destinations": [{"destination": "Nha Trang", "productCount": 2}]}
    body = destination_list(services["index"].destination)
    assert valid("DestinationListResponse", body)
    assert sum(item["productCount"] for item in body["destinations"]) == len(services["index"].units)
    assert all(type(item["destination"]) is str for item in body["destinations"])
