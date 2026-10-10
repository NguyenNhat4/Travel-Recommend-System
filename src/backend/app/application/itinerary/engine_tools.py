"""Tool itinerary gọi thẳng engine Search/Recommendation/Similar/Catalog trong cùng tiến trình (`ITINERARY_DATA_MODE=inprocess`).

Vì sao có adapter này: engine đã nằm sẵn trên `app.state`, nên agent không cần gọi ngược HTTP API của chính
Backend như `ItineraryHttpClients`. Adapter chỉ điều phối use case có sẵn (architecture §6.3.3); không SDK,
không DB, không HTTP.

- Mỗi tham số engine là một provider `() -> engine | None`, đọc lại ở MỖI lời gọi: `RecsysRefresher` thay engine
  theo chu kỳ, và itinerary clients được nối trước khi RecSys nạp xong. Engine None → `SEARCH_UNAVAILABLE` 503
  retryable (khác route công khai: route vẫn trả trang rỗng).
- Output đi qua đúng helper hậu xử lý của route (`search_tool_payload`, `recommendation_response`,
  `destination_list`), rồi round-trip JSON: vừa là deep copy (`hit()` dùng chung dict `attributes` của index),
  vừa chặn NaN/kiểu lạ như Starlette ở http mode. Similar chỉ thêm `requestId` như route `/products/{id}/similar`.
- Token chỉ được đọc ở đây, lúc `get_recommendations` chạy, qua `application/auth/bearer.py` — cùng resolver với
  `api/deps.py`. Token hỏng là 401, không bao giờ hạ thành khách; header rỗng là khách, giống http mode. Token không
  vào state, log hay kết quả.
- Engine đồng bộ chạy trên pool riêng do composition root truyền vào; mỗi job chạy trong bản sao contextvars nên
  giữ được X-Request-ID. Không truyền pool (test) thì dùng `asyncio.to_thread`.
"""
from __future__ import annotations

import asyncio
import contextvars
import functools
import json
import logging
import time
import traceback
from collections.abc import Callable, Coroutine
from concurrent.futures import Executor
from typing import Any

from src.backend.app.application.auth.bearer import principal_from_header
from src.backend.app.application.auth.errors import AuthError
from src.backend.app.application.auth.principal import AuthPrincipal
from src.backend.app.application.catalog.errors import CatalogError
from src.backend.app.application.catalog.views import destination_list
from src.backend.app.application.ports.call_telemetry import CallTelemetry
from src.backend.app.application.ports.embedder import EmbeddingUnavailableError
from src.backend.app.application.ports.itinerary_tools import ToolError
from src.backend.app.application.recommendation.responses import recommendation_response
from src.backend.app.application.search.responses import search_tool_payload
from src.backend.app.core.call_context import call_scope
from src.backend.app.core.request_context import current_request_id

logger = logging.getLogger("uvicorn.error")

Provider = Callable[[], Any]

#: Tham số `SearchRequest` → tham số engine, giống route POST /search (adapter HTTP gửi đúng body đó). Search không bao giờ
#: nhận danh tính. `sort`, `includeVariants`, `availabilityMode`, ngày của `travelContext` engine chưa nhận nên không chuyển.
SEARCH_ENGINE_ARGUMENTS = {"taxonomy": "taxonomy", "destination": "destination", "limit": "limit", "offset": "offset",
                           "origin": "origin", "priceMin": "price_min", "priceMax": "price_max",
                           "starRatingMin": "star_min", "availableOnly": "available_only"}


def search_engine_kwargs(request: dict[str, Any]) -> dict[str, Any]:
    """kwargs của engine Search cho một `SearchRequest`; số khách (`travelContext.guests`) là filter sức chứa (1.16.0)."""
    kwargs = {target: request[key] for key, target in SEARCH_ENGINE_ARGUMENTS.items() if request.get(key) is not None}
    guests = (request.get("travelContext") or {}).get("guests") or {}
    kwargs.update({key: guests[key] for key in ("adults", "children") if guests.get(key) is not None})
    return kwargs


def _unavailable() -> ToolError:
    return ToolError("SEARCH_UNAVAILABLE", retryable=True, http_status=503)


class InProcessItineraryTools:
    supports_catalog = True
    supports_similar = True

    def __init__(self, *, search: Provider, recommend: Provider, index: Provider, product_detail: Provider,
                 similar_products: Provider, token_verifier: Provider, revoked_tokens: Provider,
                 list_products: Provider | None = None,
                 executor: Executor | None = None, telemetry: CallTelemetry | None = None):
        self._search = search
        self._recommend = recommend
        self._index = index
        self._product_detail = product_detail
        self._similar_products = similar_products
        self._list_products = list_products or (lambda: None)
        self._token_verifier = token_verifier
        self._revoked_tokens = revoked_tokens
        self._executor = executor
        self._telemetry = telemetry  # đo lần gọi nguồn `agent` (docs/prd/deployment-plan.md §5)

    @property
    def product_count(self) -> int | None:
        index = self._index()
        return len(index.units) if index is not None else None

    async def search_products(self, request: dict[str, Any]) -> dict[str, Any]:
        return await self._guard("search_products", self._search_products(request))

    async def get_recommendations(self, request: dict[str, Any], authorization: str | None = None) -> dict[str, Any]:
        return await self._guard("get_recommendations", self._get_recommendations(request, authorization))

    async def get_similar_products(self, product_id: str, limit: int) -> dict[str, Any]:
        return await self._guard("get_similar_products", self._get_similar_products(product_id, limit))

    async def get_product_detail(self, product_id: str) -> dict[str, Any]:
        return await self._guard("get_product_detail", self._get_product_detail(product_id))

    async def list_products(self, params: dict[str, Any]) -> dict[str, Any]:
        return await self._guard("list_products", self._list_products_page(params))

    async def list_destinations(self) -> dict[str, Any]:
        # Index None → 503: agent bỏ qua bước kiểm điểm đến thay vì báo mọi điểm đến là ngoài catalog.
        return await self._guard("list_destinations", self._list_destinations())

    async def _search_products(self, request: dict[str, Any]) -> dict[str, Any]:
        engine = self._require("search_products", self._search)
        return search_tool_payload(await self._run(engine, request["query"].strip(), **search_engine_kwargs(request)))

    async def _get_recommendations(self, request: dict[str, Any], authorization: str | None) -> dict[str, Any]:
        principal = await self._principal(authorization)  # kiểm token trước engine: 401 thắng 503
        engine = self._require("get_recommendations", self._recommend)
        return await self._run(recommendation_response, engine, principal.cdp_user_id if principal else None,
                               k=request.get("k", 5), destination=request.get("destination"))

    async def _get_similar_products(self, product_id: str, limit: int) -> dict[str, Any]:
        # GetSimilarProducts tự đẩy lookup Weaviate đồng bộ sang executor mặc định (asyncio.to_thread), không qua
        # pool itinerary. Ngoại lệ đã chấp nhận: lookup không embed nên bị chặn bởi timeout Weaviate, và planner
        # gọi similar tối đa 2 lần mỗi lượt.
        use_case = self._require("get_similar_products", self._similar_products)
        return {**await use_case(product_id, limit=limit), "requestId": current_request_id() or "similar"}

    async def _get_product_detail(self, product_id: str) -> dict[str, Any]:
        return await self._require("get_product_detail", self._product_detail)(product_id)

    async def _list_products_page(self, params: dict[str, Any]) -> dict[str, Any]:
        use_case = self._require("list_products", self._list_products)
        result = await use_case(destination=params.get("destination"), taxonomy=params.get("taxonomy"),
                                available_only=bool(params.get("availableOnly")), sort=params.get("sort", "popular"),
                                limit=params.get("limit", 20), offset=params.get("offset", 0),
                                parent_product_id=params.get("parentProductId"))
        return {**result, "requestId": current_request_id() or "catalog"}

    async def _list_destinations(self) -> dict[str, Any]:
        return destination_list(self._require("list_destinations", self._index).destination)

    async def _principal(self, authorization: str | None) -> AuthPrincipal | None:
        if not authorization:  # header vắng hoặc rỗng: khách, giống adapter HTTP không gửi Authorization
            return None
        verifier = self._require("get_recommendations", self._token_verifier)
        try:
            return await principal_from_header(authorization, verifier, self._revoked_tokens())
        except AuthError as exc:
            raise ToolError(exc.code, http_status=exc.http_status or 401) from None

    def _require(self, tool: str, provider: Provider) -> Any:
        engine = provider()
        if engine is None:
            logger.warning("itinerary.tool.unavailable requestId=%s name=%s reason=not_ready",
                           current_request_id() or "unknown", tool)
            raise _unavailable()
        return engine

    async def _run(self, fn: Callable[..., Any], /, *args: Any, **kwargs: Any) -> Any:
        if self._executor is None:
            return await asyncio.to_thread(fn, *args, **kwargs)
        job = functools.partial(contextvars.copy_context().run, fn, *args, **kwargs)
        return await asyncio.get_running_loop().run_in_executor(self._executor, job)

    async def _guard(self, tool: str, call: Coroutine[Any, Any, Any]) -> dict[str, Any]:
        """Mỗi lời gọi công cụ là một lần gọi nguồn `agent`: tên công cụ, kết quả, thời gian và chi tiết use case."""
        started, status = time.perf_counter(), "ok"
        with call_scope("agent") as detail:
            try:
                return await self._mapped(tool, call)
            except ToolError as exc:
                status = f"error:{exc.code}"
                raise
            except BaseException:  # CancelledError khi agent hết giờ
                status = "cancelled"
                raise
            finally:
                if self._telemetry is not None:
                    self._telemetry.record({"source": "agent", "kind": "tool", "name": tool, "status": status,
                                            "ms": round((time.perf_counter() - started) * 1000, 1), **detail})

    async def _mapped(self, tool: str, call: Coroutine[Any, Any, Any]) -> dict[str, Any]:
        """Một chỗ map lỗi. CancelledError không phải Exception nên timeout của agent vẫn huỷ được lời gọi."""
        try:
            result = await call
        except ToolError:
            raise
        except CatalogError as exc:
            raise ToolError(exc.code, retryable=exc.retryable, http_status=exc.http_status) from None
        except EmbeddingUnavailableError as exc:  # adapter embedding đã log lỗi; lý do đi tiếp vào trace
            raise ToolError("SEARCH_UNAVAILABLE", retryable=exc.retryable, http_status=503,
                            reason=f"embed:{exc.reason}") from None
        except Exception as exc:
            # Tên kiểu lỗi và các frame traceback (chỉ file, dòng, mã nguồn), không kèm thông điệp: thông điệp có thể
            # chứa câu truy vấn của người dùng. Frame đủ để lần ra bug, vì lỗi này bị thử lại chứ không nổi lên 500.
            logger.warning("itinerary.tool.unavailable requestId=%s name=%s reason=%s\n%s",
                           current_request_id() or "unknown", tool, type(exc).__name__,
                           "".join(traceback.format_tb(exc.__traceback__)).rstrip())
            raise _unavailable() from None
        try:
            return json.loads(json.dumps(result, allow_nan=False))
        except (TypeError, ValueError):
            raise ToolError("INVALID_TOOL_RESPONSE") from None
