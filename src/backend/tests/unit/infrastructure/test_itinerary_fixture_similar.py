"""Similar của bộ fixture 50 sản phẩm (`ITINERARY_DATA_MODE=fixture`): cùng hình dạng và quy tắc với engine.

Cùng taxonomy, còn chỗ, loại cả cụm của anchor (sản phẩm cha và mọi con của nó); id lạ là 404; kết quả qua đúng
hợp đồng `getSimilarProducts` mà gateway kiểm.
"""
import asyncio
import json
from pathlib import Path

import pytest

from src.backend.app.agents.tools.itinerary_gateway import ItineraryToolGateway
from src.backend.app.application.itinerary.tool_contracts import validate
from src.backend.app.application.ports.itinerary_tools import ToolError
from src.backend.app.infrastructure.clients.itinerary_fixture_clients import FixtureItineraryClients

FIXTURE = Path(__file__).resolve().parents[4] / "shared/mocks/itinerary-agent/products.json"
PRODUCTS = json.loads(FIXTURE.read_text(encoding="utf-8"))


def parent(product: dict) -> str | None:
    return product.get("attributes", {}).get("parentProductId")


def cluster_of(product: dict) -> set[str]:
    root = parent(product) or product["productId"]
    return {root} | {p["productId"] for p in PRODUCTS if parent(p) == root}


def similar(product_id: str, limit: int = 20) -> dict:
    return asyncio.run(FixtureItineraryClients().get_similar_products(product_id, limit))


def has_neighbour(product: dict) -> bool:
    """Có sản phẩm cùng loại, cùng điểm đến, còn chỗ, ngoài cụm: kiểm được thứ tự cùng điểm đến trước."""
    return any(q["taxonomy"] == product["taxonomy"] and q["destination"] == product["destination"]
               and q["available"] and q["productId"] not in cluster_of(product) for q in PRODUCTS)


# Hạng phòng có ít nhất một anh em: kiểm được cả việc loại khách sạn cha lẫn các phòng cùng cha.
ROOM = next(p for p in PRODUCTS
            if parent(p) and sum(parent(q) == parent(p) for q in PRODUCTS) > 1 and has_neighbour(p))
PROPERTY = next(p for p in PRODUCTS if p["productId"] == parent(ROOM))


@pytest.mark.parametrize("anchor", [ROOM, PROPERTY], ids=["room", "property"])
def test_same_taxonomy_without_the_anchor_cluster(anchor):
    result = similar(anchor["productId"])
    ids = [item["productId"] for item in result["results"]]
    assert result["productId"] == anchor["productId"] and result["strategy"] == "same_taxonomy"
    assert ids and not set(ids) & cluster_of(anchor)
    assert {item["taxonomy"] for item in result["results"]} == {anchor["taxonomy"]}
    assert all(item["available"] and item["score"] == 1.0 for item in result["results"])
    validate("get_similar_products", result, "response")


def test_same_destination_comes_first_and_limit_is_respected():
    result = similar(ROOM["productId"], limit=3)
    assert len(result["results"]) == 3
    destinations = [item["destination"] == ROOM["destination"] for item in similar(ROOM["productId"])["results"]]
    # Cùng điểm đến trước, khác điểm đến sau; có cả hai nhóm nên thứ tự thật sự được kiểm.
    assert destinations[0] and not destinations[-1]
    assert destinations == sorted(destinations, reverse=True)


def test_unknown_product_is_404():
    with pytest.raises(ToolError) as caught:
        similar("khong-co")
    assert (caught.value.code, caught.value.retryable, caught.value.http_status) == ("PRODUCT_NOT_FOUND", False, 404)


def test_fixture_similar_passes_the_gateway_contract_check():
    clients = FixtureItineraryClients()
    gateway = ItineraryToolGateway(clients, clients, clients, similar=clients)
    result = asyncio.run(gateway.execute({"id": "a", "name": "get_similar_products",
                                          "args": {"productId": ROOM["productId"]}}))
    assert "error" not in result and len(result["data"]["results"]) <= 8
