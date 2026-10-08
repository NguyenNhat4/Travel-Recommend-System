import asyncio
from types import SimpleNamespace

import httpx

from src.backend.app.agents.graph import build_graph
from src.backend.app.agents.tools.itinerary_gateway import ItineraryToolGateway
from src.backend.app.api.v1.routes import recommendations, search
from src.backend.app.application.auth.principal import AuthenticatedUser
from src.backend.app.application.catalog.use_cases import GetProductDetail, GetSimilarProducts
from src.backend.app.application.itinerary.contracts import valid
from src.backend.app.application.itinerary.engine_tools import InProcessItineraryTools
from src.backend.app.application.itinerary.tool_contracts import contracts
from src.backend.app.infrastructure.auth.keys import generate_rsa_pem_pair
from src.backend.app.infrastructure.clients.itinerary_http_clients import ItineraryHttpClients
from src.backend.tests.conftest import ROWS
from src.backend.tests.fakes.auth import jwt_issuer
from src.backend.tests.fakes.catalog import InMemoryProductQuery
from src.backend.tests.unit.agents.test_itinerary_runtime import ScriptedLlm
from jsonschema import Draft202012Validator


def test_agent_gateway_consumes_enriched_backend_endpoints(services):
    responses = []
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(
        search=services["search"], recommend=services["recommend"]
    )))

    async def handler(http_request):
        if http_request.url.path.endswith("/search"):
            # Adapter HTTP gọi POST /search (route duy nhất nhận số khách), body là SearchRequest.
            body = search.search_post(search.SearchRequestPayload.model_validate_json(http_request.content),
                                      search_products=request.app.state.search)
        else:
            body = recommendations.recommendations(
                k=int(http_request.url.params.get("k", 5)),
                destination=http_request.url.params.get("destination"), principal=None,
                recommend=request.app.state.recommend,
            )
        responses.append(body)
        return httpx.Response(200, json=body)

    async def scenario():
        async with httpx.AsyncClient(
            base_url="http://backend.test/api/v1/",
            transport=httpx.MockTransport(handler),
        ) as http:
            clients = ItineraryHttpClients(http)
            normalized_search = await clients.search_products({
                "query": "nghỉ dưỡng biển", "destination": "Nha Trang", "limit": 20, "offset": 0,
            })
            errors = [error.message for error in Draft202012Validator(
                contracts()["search_products"]["response"]
            ).iter_errors(normalized_search)]
            assert not errors, errors
            gateway = ItineraryToolGateway(
                clients, clients, recommendation_authorization=None
            )
            search_result = await gateway.execute({
                "id": "search-1", "name": "search_products",
                "args": {"query": "nghỉ dưỡng biển", "destination": "Nha Trang"},
            })
            recommendation_result = await gateway.execute({
                "id": "rec-1", "name": "get_recommendations",
                "args": {"destination": "Nha Trang"},
            })
            return search_result, recommendation_result

    search_result, recommendation_result = asyncio.run(scenario())

    assert "error" not in search_result, responses[0]
    assert "error" not in recommendation_result
    assert search_result["data"]["results"]
    product = search_result["data"]["results"][0]
    assert {"description", "attributes", "currency", "priceUnit", "available",
            "availableFrom", "availableTo"} <= product.keys()
    assert all(item["destination"] == "Nha Trang"
               for item in recommendation_result["data"]["recommendations"])


# ---- ITINERARY_DATA_MODE=inprocess: cùng graph, tool gọi thẳng engine thay vì HTTP

PLAN = [{"name": "search_products", "args": {"query": "nghỉ dưỡng biển"}},
        {"name": "get_recommendations", "args": {}}]


def inprocess_tools(services=None, *, recommend=..., verifier=None, calls=None):
    """Provider như `main._inprocess_itinerary_tools`; `services` None nghĩa là RecSys chưa nạp."""
    def provide(name, value):
        def provider():
            if calls is not None:
                calls.append(name)
            return value
        return provider

    engines = services or {}
    return InProcessItineraryTools(
        search=provide("search", engines.get("search")),
        recommend=provide("recommend", engines.get("recommend") if recommend is ... else recommend),
        index=provide("index", engines.get("index")),
        product_detail=provide("detail", GetProductDetail(InMemoryProductQuery(ROWS)) if services else None),
        similar_products=provide("similar", GetSimilarProducts(InMemoryProductQuery(ROWS), engines["similar"])
                                 if services else None),
        token_verifier=lambda: verifier, revoked_tokens=lambda: None,
    )


def run_graph(tools, *, authorization=None, **kwargs):
    gateway = ItineraryToolGateway(tools, tools, tools, recommendation_authorization=authorization)
    graph = build_graph(tools=gateway, llm=ScriptedLlm(plan=PLAN), **kwargs)
    # Như run_graph của test_itinerary_runtime: coi như đã hỏi ngày đi/số người/ngân sách để tới được bước tool.
    result = asyncio.run(graph.ainvoke({"query": "2 ngày Nha Trang", "request_id": "inprocess-test",
                                        "start_date_asked": True}))
    assert result["events"][-1]["node"] == "finalize"
    assert valid("ItineraryResponse" if result["http_status"] == 200 else "ErrorResponse", result["response"])
    return result


def test_inprocess_graph_run_is_grounded_in_the_engine_catalog(services):
    result = run_graph(inprocess_tools(services))
    assert result["http_status"] == 200, result["response"]
    assert result["attempt"] == 0
    plan = result["response"]["itinerary"]
    returned = ([plan["stay"]["product"]] if plan.get("stay") else []) + [
        slot["product"] for day in plan["days"] for slot in day["slots"] if slot["product"]]
    assert returned
    catalog = {unit.product_id: unit for unit in services["index"].units}
    for item in returned:
        assert item["productId"] in catalog
        assert item["name"] == catalog[item["productId"]].name
        assert item["unitPrice"] == catalog[item["productId"]].unit_price


def test_inprocess_recsys_not_ready_fails_after_exactly_one_retry():
    calls = []
    result = run_graph(inprocess_tools(calls=calls))
    assert result["http_status"] == 503
    assert result["response"]["error"]["code"] == "SEARCH_UNAVAILABLE"
    assert result["response"]["error"]["retryable"] is True
    assert result["attempt"] == 1
    assert calls.count("search") == 2


def test_inprocess_forged_token_is_401_and_never_reaches_the_engine(services):
    recommended = []

    def recommend(cdp_user_id, **kwargs):
        recommended.append(cdp_user_id)
        return services["recommend"](cdp_user_id, **kwargs)

    # JWT đúng dạng nhưng ký bằng khoá lạ: 401 đến từ bước kiểm chữ ký.
    forged, _ = jwt_issuer(private_key=generate_rsa_pem_pair()[0]).issue_access_token(
        AuthenticatedUser("u-1", "p1@example.com", "x", "P1", "P1"), session_id=None, amr=("pwd",))
    tools = inprocess_tools(services, recommend=recommend, verifier=jwt_issuer())
    result = run_graph(tools, authorization=f"Bearer {forged}", require_recommendations=True)
    assert result["http_status"] == 401
    assert result["response"]["error"]["code"] == "INVALID_TOKEN"
    assert recommended == []
    assert forged not in str(result)
