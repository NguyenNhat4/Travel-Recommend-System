"""HTTP implementations of the itinerary read-only ports."""

from typing import Any
from urllib.parse import quote

import httpx

from src.backend.app.application.itinerary.tool_contracts import upstream_error_code
from src.backend.app.application.ports.itinerary_tools import ToolError
from src.backend.app.core.request_context import REQUEST_ID_HEADER, current_request_id


class ItineraryHttpClients:
    # `/destinations` có thật; `/products/{id}` chưa, nhưng Search và Recommendation trả đủ
    # DETAIL_FIELDS nên `hydrate()` không bao giờ gọi tới `get_product_detail`.
    supports_catalog = True

    def __init__(self, http: httpx.AsyncClient):
        self._http = http

    async def search_products(self, request: dict[str, Any]) -> dict[str, Any]:
        supported = {"taxonomy", "destination", "limit", "offset"}
        params = {"q": request["query"], **{key: value for key, value in request.items()
                                             if key in supported and value is not None}}
        data = await self._request("GET", "/search", params=params)
        # GET compatibility endpoint có metadata engine riêng. Tool chỉ giữ các
        # trường SearchResponse ổn định mà Agent thực sự tiêu thụ.
        return {key: value for key, value in data.items() if key not in {"cutoff", "diagnostics"}}

    async def get_recommendations(self, request: dict[str, Any], authorization: str | None = None) -> dict[str, Any]:
        return await self._request("GET", "/recommendations", params=request,
                                   headers={"Authorization": authorization} if authorization else {})

    async def get_product_detail(self, product_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/products/{quote(product_id, safe='')}")

    async def list_destinations(self) -> dict[str, Any]:
        return await self._request("GET", "/destinations")

    async def _request(self, method: str, url: str, **kwargs: Any) -> dict[str, Any]:
        headers = dict(kwargs.pop("headers", {}))
        if request_id := current_request_id():
            headers[REQUEST_ID_HEADER] = request_id
        request = httpx.Request(method, self._http.base_url.join(url.lstrip("/")), headers=headers, **kwargs)
        try:
            response = await self._http.send(request, auth=None)
        except httpx.TimeoutException as exc:
            raise ToolError("TOOL_TIMEOUT", retryable=True) from exc
        except httpx.HTTPError as exc:
            raise ToolError("TOOL_HTTP_ERROR", retryable=True) from exc
        try:
            body = response.json()
        except ValueError as exc:
            raise ToolError("INVALID_TOOL_RESPONSE", http_status=response.status_code) from exc
        if response.is_success:
            if not isinstance(body, dict):
                raise ToolError("INVALID_TOOL_RESPONSE")
            return body
        code = upstream_error_code(body) or "TOOL_HTTP_ERROR"
        raise ToolError(code, retryable=response.status_code >= 500, http_status=response.status_code)
