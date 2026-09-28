"""Contract-validated tool dispatch; request credentials stay outside graph state."""
from time import monotonic
from typing import Any

from src.backend.app.application.ports.itinerary_tools import (
    CatalogPort, RecommendationPort, SearchProductsPort, ToolError,
)
from src.backend.app.application.itinerary.tool_contracts import definitions, normalize_arguments, validate
from src.backend.app.application.itinerary.contracts import valid
from src.backend.app.domain.itinerary.types import ToolCall, ToolDefinition, ToolResult


class ItineraryToolGateway:
    def __init__(self, search: SearchProductsPort, recommendations: RecommendationPort,
                 catalog: CatalogPort | None = None, recommendation_authorization: str | None = None):
        self._search = search
        self._recommendations = recommendations
        self._catalog = catalog
        self.supports_catalog = catalog is not None
        self._recommendation_authorization = recommendation_authorization

    def definitions(self) -> list[ToolDefinition]:
        return definitions()

    async def get_product_detail(self, product_id: str) -> dict[str, Any]:
        if self._catalog is None:
            raise ToolError("CATALOG_NOT_CONFIGURED")
        data = await self._catalog.get_product_detail(product_id)
        if not valid("ProductDetail", data) or data["productId"] != product_id:
            raise ToolError("INVALID_TOOL_RESPONSE")
        return data

    async def list_destinations(self) -> dict[str, Any]:
        if self._catalog is None:
            raise ToolError("CATALOG_NOT_CONFIGURED")
        data = await self._catalog.list_destinations()
        if not valid("DestinationListResponse", data):
            raise ToolError("INVALID_TOOL_RESPONSE")
        return data

    async def call_tool(self, name: str, arguments: dict[str, Any], authorization: str | None = None) -> dict[str, Any]:
        # Catalog helpers remain callable by application code, never exposed to the planner.
        if name == "get_product_detail" and self._catalog is not None:
            if set(arguments) != {"productId"} or not isinstance(arguments["productId"], str) or not arguments["productId"]:
                raise ToolError("INVALID_ARGUMENTS")
            return await self.get_product_detail(arguments["productId"])
        if name == "list_destinations" and self._catalog is not None:
            if arguments:
                raise ToolError("INVALID_ARGUMENTS")
            return await self.list_destinations()
        args = normalize_arguments(name, arguments)
        if name == "search_products":
            data = await self._search.search_products(args)
        else:
            data = await self._recommendations.get_recommendations(args, self._recommendation_authorization)
        validate(name, data, "response")
        return data

    async def execute(self, call: ToolCall) -> ToolResult:
        started = monotonic()
        # Validate before recording arguments; invalid values cannot leak credentials.
        result: ToolResult = {"tool_call_id": call.get("id"), "name": call.get("name"), "arguments": {}}
        try:
            args = normalize_arguments(call.get("name"), call.get("args", {}))
            result["arguments"] = args
            result["data"] = await self.call_tool(call["name"], args)
        except ToolError as exc:
            result["error"] = exc.as_dict()
        except TimeoutError:
            result["error"] = ToolError("TOOL_TIMEOUT", retryable=True).as_dict()
        except Exception:
            result["error"] = ToolError("TOOL_EXECUTION_FAILED").as_dict()
        result["duration_ms"] = int((monotonic() - started) * 1000)
        return result
