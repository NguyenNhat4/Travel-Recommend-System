import asyncio
from types import SimpleNamespace
from unittest.mock import patch

import httpx

from src.backend.app.agents.tools.itinerary_gateway import ItineraryToolGateway
from src.backend.app.api.v1.routes import recommendations, search
from src.backend.app.application.itinerary.tool_contracts import contracts
from src.backend.app.infrastructure.clients.itinerary_http_clients import ItineraryHttpClients
from jsonschema import Draft202012Validator


def test_agent_gateway_consumes_enriched_backend_endpoints(services):
    responses = []
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(
        search=services["search"], recommend=services["recommend"]
    )))

    async def handler(http_request):
        if http_request.url.path.endswith("/search"):
            body = search.search(
                request, q=http_request.url.params["q"],
                taxonomy=http_request.url.params.get("taxonomy"),
                destination=http_request.url.params.get("destination"),
                limit=int(http_request.url.params.get("limit", 20)),
                offset=int(http_request.url.params.get("offset", 0)),
            )
        else:
            body = recommendations.recommendations(
                request, k=int(http_request.url.params.get("k", 5)),
                destination=http_request.url.params.get("destination"), authorization=None,
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

    with patch(
        "src.backend.app.api.v1.routes.recommendations.get_settings",
        return_value=SimpleNamespace(jwt_secret="", jwt_algorithm="HS256"),
    ):
        search_result, recommendation_result = asyncio.run(scenario())

    assert "error" not in search_result, responses[0]
    assert "error" not in recommendation_result
    assert search_result["data"]["results"]
    product = search_result["data"]["results"][0]
    assert {"description", "attributes", "currency", "priceUnit", "available",
            "availableFrom", "availableTo"} <= product.keys()
    assert all(item["destination"] == "Nha Trang"
               for item in recommendation_result["data"]["recommendations"])
