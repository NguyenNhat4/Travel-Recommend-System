"""Contract-validated tool dispatch; request credentials stay outside graph state."""
import logging
from collections.abc import Awaitable, Callable
from time import monotonic
from typing import Any

from src.backend.app.application.ports.itinerary_tools import (
    CatalogPort, RecommendationPort, SearchProductsPort, SimilarProductsPort, ToolError,
)
from src.backend.app.application.itinerary.tool_contracts import (
    SIMILAR_PRODUCTS, contracts, definitions, normalize_arguments, validate,
)
from src.backend.app.application.itinerary.contracts import valid
from src.backend.app.core.request_context import current_request_id
from src.backend.app.domain.itinerary.types import ToolCall, ToolDefinition, ToolResult

logger = logging.getLogger("uvicorn.error")


class ItineraryToolGateway:
    def __init__(self, search: SearchProductsPort, recommendations: RecommendationPort,
                 catalog: CatalogPort | None = None, recommendation_authorization: str | None = None,
                 *, similar: SimilarProductsPort | None = None):
        self._search = search
        self._recommendations = recommendations
        self._catalog = catalog
        self.supports_catalog = catalog is not None
        self._recommendation_authorization = recommendation_authorization
        # Tool planner nhìn thấy → port xử lý, nhận args đã chuẩn hoá. Similar chỉ có khi composition root nối
        # port; không có thì tool bị ẩn khỏi definitions() và lời gọi tới nó là TOOL_NOT_ALLOWED.
        self._handlers: dict[str, Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]] = {
            "search_products": lambda args: self._search.search_products(args),
            "get_recommendations": lambda args: self._recommendations.get_recommendations(
                args, self._recommendation_authorization),
        }
        if similar is not None:
            self._handlers[SIMILAR_PRODUCTS] = lambda args: similar.get_similar_products(
                args["productId"], args["limit"])

    def definitions(self) -> list[ToolDefinition]:
        return [definition for definition in definitions() if definition["name"] in self._handlers]

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

    async def list_products(self, params: dict[str, Any]) -> dict[str, Any]:
        """Chuyến bay cho chặng bay của lịch trình (AC-AGT-02). Như `get_product_detail`: application gọi, planner không thấy."""
        if self._catalog is None:
            raise ToolError("CATALOG_NOT_CONFIGURED")
        allowed = {"parentProductId", "destination", "taxonomy", "availableOnly", "sort", "limit", "offset"}
        if not set(params) <= allowed:
            raise ToolError("INVALID_ARGUMENTS")
        data = await self._catalog.list_products(params)
        if not valid("ProductListResponse", data):
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
        handler = self._handlers.get(name)
        if handler is None:  # tool lạ, hoặc có trong hợp đồng nhưng chưa nối port
            raise ToolError("TOOL_NOT_ALLOWED")
        args = normalize_arguments(name, arguments)
        data = await handler(args)
        validate(name, data, "response")
        return data

    async def execute(self, call: ToolCall) -> ToolResult:
        started = monotonic()
        # Validate before recording arguments; invalid values cannot leak credentials.
        name = call.get("name")
        result: ToolResult = {"tool_call_id": call.get("id"), "name": name, "arguments": {}}
        try:
            if not isinstance(name, str) or name not in self._handlers:  # tool lạ/chưa nối port: không ghi arguments
                raise ToolError("TOOL_NOT_ALLOWED")
            args = normalize_arguments(name, call.get("args", {}))
            result["arguments"] = args
            result["data"] = await self.call_tool(name, args)
        except ToolError as exc:
            result["error"] = exc.as_dict()
        except TimeoutError:
            result["error"] = ToolError("TOOL_TIMEOUT", retryable=True).as_dict()
        except Exception:
            result["error"] = ToolError("TOOL_EXECUTION_FAILED").as_dict()
        result["duration_ms"] = int((monotonic() - started) * 1000)
        # One line per call replaces the access log that in-process tools no longer produce.
        # Never log arguments or data: they carry user text, and the name only if it is a known tool.
        error = result.get("error")
        logger.info("itinerary.tool requestId=%s name=%s outcome=%s code=%s retryable=%s durationMs=%s",
                    current_request_id() or "unknown",
                    name if isinstance(name, str) and name in contracts() else "unknown",
                    "error" if error else "ok", error["code"] if error else "-",
                    error["retryable"] if error else "-", result["duration_ms"])
        return result
