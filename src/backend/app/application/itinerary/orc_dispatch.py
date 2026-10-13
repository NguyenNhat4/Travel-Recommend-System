"""Thực thi đúng các tool orc gọi (assistant v2), trong ngân sách request nguồn của lượt.

Không tự thêm lời gọi, không tự lấy trang tiếp, không chọn sản phẩm: kết quả (kể cả lỗi) trả nguyên cho orc. Mỗi
request tới nguồn tốn một suất ngân sách; lỗi tạm thời thử lại đúng một lần cùng tham số (PRD architecture §3).
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import json
import logging
from time import monotonic
from typing import Any, Callable

from src.backend.app.application.ports.itinerary_tools import ToolError
from src.backend.app.domain.itinerary.draft_validation import check_draft, cost_mode

from .flight_lookup import lookup_flights
from .orc_contracts import TOOLS
from .product_registry import ProductRegistry

logger = logging.getLogger(__name__)
VIETNAM = timezone(timedelta(hours=7))
CATALOG_TOOLS = ("get_product_detail", "list_destinations", "list_products", "lookup_flights")


class SourceBudget:
    """Tối đa `limit` request tới nguồn, và không request nào sau `deadline` (giây monotonic)."""

    def __init__(self, *, deadline: float, limit: int = 10):
        self.deadline, self.limit, self.used = deadline, limit, 0

    def take(self) -> None:
        # Không có await giữa kiểm và tăng, nên các lời gọi chạy song song không vượt được trần.
        if monotonic() >= self.deadline:
            raise ToolError("TIME_LIMIT")
        if self.used >= self.limit:
            raise ToolError("TOOL_LIMIT")
        self.used += 1


class OrcToolDispatcher:
    def __init__(self, tools, registry: ProductRegistry, budget: SourceBudget, *, timeout_seconds: float,
                 now: Callable[[], datetime] = lambda: datetime.now(VIETNAM)):
        self.tools, self.registry, self.budget, self.timeout, self.now = tools, registry, budget, timeout_seconds, now
        self.plans: dict[str, dict[str, Any]] = {}     # plan_result_id (= call_id) → lịch đã kiểm
        self.results: dict[str, dict[str, Any]] = {}   # call_id → kết quả, để tra dữ kiện orc trích
        self._cache: dict[str, Any] = {}
        available = {definition["name"] for definition in tools.definitions()} | {"build_itinerary"}
        if getattr(tools, "supports_catalog", False):
            available |= set(CATALOG_TOOLS)
        self.allowed = [name for name in TOOLS if name in available]

    async def run(self, call: dict[str, Any]) -> dict[str, Any]:
        """Một lời gọi đã qua kiểm schema. Lỗi của lời gọi này không ảnh hưởng các lời gọi khác cùng lượt."""
        result = {"call_id": call["call_id"], "tool": call["name"], "status": "ok", "refs": [], "coverage": None,
                  "data": None, "error": None}
        try:
            if call["name"] not in self.allowed:
                raise ToolError("TOOL_NOT_ALLOWED")
            await getattr(self, "_" + call["name"])(call["arguments"], result)
        except ToolError as exc:
            result.update(status="error", refs=[], error={"code": exc.code, "retryable": exc.retryable})
        except Exception:
            logger.exception("itinerary.v2.tool_failed tool=%s", call["name"])
            result.update(status="error", refs=[], error={"code": "TOOL_FAILED", "retryable": False})
        self.results[result["call_id"]] = result
        # Không ghi tham số: chúng mang câu người dùng.
        logger.info("itinerary.v2.tool name=%s status=%s code=%s refs=%s", call["name"], result["status"],
                    (result["error"] or {}).get("code", "-"), len(result["refs"]))
        return result

    async def source(self, kind: str, params: Any) -> Any:
        """Một request tới nguồn; kết quả thành công cùng tham số dùng lại trong lượt mà không tốn thêm suất."""
        key = json.dumps([kind, params], sort_keys=True, ensure_ascii=False)
        if key in self._cache:
            return self._cache[key]
        for attempt in (1, 2):
            self.budget.take()
            seconds = max(0.001, min(self.timeout, self.budget.deadline - monotonic()))
            try:
                data = await asyncio.wait_for(self._request(kind, params), seconds)
            except (ToolError, TimeoutError) as exc:
                error = exc if isinstance(exc, ToolError) else ToolError("TOOL_TIMEOUT", retryable=True)
                if attempt == 2 or not error.retryable:
                    raise error from None
                continue
            self._cache[key] = data
            return data

    async def _request(self, kind: str, params: Any) -> Any:
        if kind == "detail":
            return await self.tools.get_product_detail(params)
        if kind == "destinations":
            return await self.tools.list_destinations()
        if kind == "list":
            return await self.tools.list_products(params)
        output = await self.tools.execute({"id": kind, "name": kind, "args": params})
        if output.get("error"):
            raise ToolError(output["error"]["code"], retryable=output["error"].get("retryable", False))
        return output["data"]

    def _offset(self, args: dict[str, Any]) -> int:
        return self.registry.cursor_offset(args["cursor"], args) if args["cursor"] else 0

    def _page(self, result: dict, args: dict, products: list[dict], total: int | None, offset: int) -> None:
        """Ghi một trang: loại mã orc muốn loại và (free_only) sản phẩm không có căn cứ miễn phí."""
        excluded = {self.registry.identify(ref) for ref in args["exclude_refs"]}
        dropped = {"paid": 0, "unknown_price": 0}
        for product in products:
            if product["productId"] in excluded:
                continue
            if args["free_only"] and cost_mode(product) != "free":
                dropped["paid" if cost_mode(product) == "paid" else "unknown_price"] += 1
                continue
            result["refs"].append(self.registry.add(product))
        more = bool(products) and total is not None and offset + len(products) < total
        result["coverage"] = {"checked": len(products), "total": total,
                              "next_cursor": self.registry.issue_cursor(args, offset + len(products)) if more else None}
        if args["free_only"]:
            result["data"] = {"dropped_not_free": dropped}
        if not result["refs"]:
            result["status"] = "empty"

    async def _search_products(self, args: dict, result: dict) -> None:
        travel = {"checkIn": args["check_in"], "checkOut": args["check_out"],
                  "guests": {"adults": args["guests"]} if args["guests"] else None}
        params = {"query": args["query"], "destination": args["destination"], "taxonomy": args["taxonomy"],
                  "priceMin": args["price_min"], "priceMax": args["price_max"],
                  "starRatingMin": args["star_rating_min"], "limit": args["limit"] or 20, "offset": self._offset(args),
                  "travelContext": {key: value for key, value in travel.items() if value is not None} or None}
        data = await self.source("search_products", {key: value for key, value in params.items() if value is not None})
        self._page(result, args, data["results"], data.get("total"), params["offset"])

    async def _get_recommendations(self, args: dict, result: dict) -> None:
        params = {key: value for key, value in (("k", args["k"]), ("destination", args["destination"]))
                  if value is not None}
        data = await self.source("get_recommendations", params)
        result["refs"] = [self.registry.add(product) for product in data["recommendations"]]
        result["coverage"] = {"checked": len(result["refs"]), "total": None, "next_cursor": None}
        result["data"] = {"strategy": data["strategy"],
                          "because": {ref: product.get("because") or []
                                      for ref, product in zip(result["refs"], data["recommendations"])}}
        if not result["refs"]:
            result["status"] = "empty"

    async def _get_similar_products(self, args: dict, result: dict) -> None:
        data = await self.source("get_similar_products",
                                 {"productId": self.registry.identify(args["product_ref"]), "limit": args["limit"] or 8})
        result["refs"] = [self.registry.add(product) for product in data["results"]]
        result["coverage"] = {"checked": len(result["refs"]), "total": None, "next_cursor": None}
        if not result["refs"]:
            result["status"] = "empty"

    async def _get_product_detail(self, args: dict, result: dict) -> None:
        product = await self.source("detail", self.registry.identify(args["product_ref"]))
        result["refs"] = [self.registry.add(product)]

    async def _list_destinations(self, args: dict, result: dict) -> None:
        data = await self.source("destinations", None)
        result["data"] = {"destinations": [row["destination"] for row in data["destinations"]]}

    async def _list_products(self, args: dict, result: dict) -> None:
        params = {"destination": args["destination"], "taxonomy": args["taxonomy"], "sort": args["sort"],
                  "parentProductId": self.registry.identify(args["parent_ref"]) if args["parent_ref"] else None,
                  "availableOnly": args["available_only"], "limit": args["limit"] or 20, "offset": self._offset(args)}
        data = await self.source("list", {key: value for key, value in params.items() if value is not None})
        self._page(result, args, data["results"], data["total"], params["offset"])

    async def _lookup_flights(self, args: dict, result: dict) -> None:
        await lookup_flights(self, args, result)

    async def _build_itinerary(self, args: dict, result: dict) -> None:
        """Kiểm lịch orc phác với dữ kiện tra trong lượt; ref chỉ có trong lịch sử thì STALE_REF (phải tra lại)."""
        refs = list(dict.fromkeys([a["product_ref"] for day in args["plan_days"] for a in day["activities"]]
                                  + [stay["product_ref"] for stay in args["stays"]]
                                  + [flight["product_ref"] for flight in args["flights"]]))
        products = {ref: self.registry.product(ref) for ref in refs}
        checked = check_draft(args, products)
        self.plans[result["call_id"]] = {"plan_result_id": result["call_id"], "draft": args, "products": products,
                                         **checked}
        result["refs"] = refs
        result["data"] = {"plan_result_id": result["call_id"], "feasibility": checked["feasibility"],
                          "nights": checked["nights"], "violations": checked["violations"],
                          "warnings": checked["warnings"], "changes": checked["changes"], **checked["costs"]}
