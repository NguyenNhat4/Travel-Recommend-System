"""HTTP implementations of the itinerary read-only ports."""

from typing import Any
from urllib.parse import quote

import httpx

from src.backend.app.application.itinerary.tool_contracts import upstream_error_code
from src.backend.app.application.ports.itinerary_tools import ToolError
from src.backend.app.application.search.responses import search_tool_payload
from src.backend.app.core.request_context import REQUEST_ID_HEADER, current_request_id


class ItineraryHttpClients:
    # `/destinations` và `/products/{id}` đều có route. Search và Recommendation đã trả đủ
    # DETAIL_FIELDS nên `hydrate()` thường không cần gọi tới `get_product_detail`.
    supports_catalog = True
    supports_similar = True

    def __init__(self, http: httpx.AsyncClient):
        self._http = http

    async def search_products(self, request: dict[str, Any]) -> dict[str, Any]:
        # POST /search: chỉ route này nhận số khách (`travelContext.guests`); cùng bộ tham số với adapter inprocess
        # (`engine_tools.SEARCH_ENGINE_ARGUMENTS`) để mọi mode nhận cùng ứng viên.
        supported = {"taxonomy", "destination", "limit", "offset", "origin", "priceMin", "priceMax", "starRatingMin",
                     "availableOnly"}
        body = {"query": request["query"], **{key: value for key, value in request.items()
                                              if key in supported and value is not None}}
        guests = (request.get("travelContext") or {}).get("guests")
        if guests:
            body["travelContext"] = {"guests": guests}
        # Route có metadata engine riêng (cutoff, diagnostics); search_tool_payload bỏ phần đó.
        return search_tool_payload(await self._request("POST", "/search", json=body))

    async def get_recommendations(self, request: dict[str, Any], authorization: str | None = None) -> dict[str, Any]:
        return await self._request("GET", "/recommendations", params=request,
                                   headers={"Authorization": authorization} if authorization else {})

    async def get_similar_products(self, product_id: str, limit: int) -> dict[str, Any]:
        # Similar không cá nhân hoá: như search, không bao giờ gửi Authorization.
        return await self._request("GET", f"/products/{quote(product_id, safe='')}/similar", params={"limit": limit})

    async def get_product_detail(self, product_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/products/{quote(product_id, safe='')}")

    async def list_destinations(self) -> dict[str, Any]:
        return await self._request("GET", "/destinations")

    async def list_products(self, params: dict[str, Any]) -> dict[str, Any]:
        query = {key: str(value).lower() if isinstance(value, bool) else value
                 for key, value in params.items() if value is not None}
        return await self._request("GET", "/products", params=query)

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
