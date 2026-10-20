"""Thực thi đúng các tool orc gọi (assistant v2), trong ngân sách request nguồn của lượt.

Không tự thêm lời gọi, không tự lấy trang tiếp, không chọn sản phẩm: kết quả (kể cả lỗi) trả nguyên cho orc. Mỗi
request tới nguồn tốn một suất ngân sách; lỗi tạm thời thử lại đúng một lần cùng tham số (PRD architecture §3).
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from time import monotonic
from typing import Any

from src.backend.app.application.ports.itinerary_tools import ToolError
from src.backend.app.domain.itinerary.draft_validation import (
    available_on,
    cost_mode,
    plan_slots,
)
from src.backend.app.domain.itinerary.normalization import fold
from src.backend.app.domain.itinerary.orc_guardrails import unconfirmed_trip_fields

from .flight_lookup import lookup_flights
from .orc_contracts import TOOLS, tool_errors
from .product_registry import ProductRegistry

logger = logging.getLogger(__name__)
VIETNAM = timezone(timedelta(hours=7))
CATALOG_TOOLS = ("get_products", "lookup_flights")


class SourceBudget:
    """Không request nào sau `deadline` (giây monotonic); `limit` là trần số request, None là không giới hạn."""

    def __init__(self, *, deadline: float, limit: int | None = None):
        self.deadline, self.limit, self.used = deadline, limit, 0

    def take(self) -> None:
        # Không có await giữa kiểm và tăng, nên các lời gọi chạy song song không vượt được trần.
        if monotonic() >= self.deadline:
            raise ToolError("TIME_LIMIT")
        if self.limit is not None and self.used >= self.limit:
            raise ToolError("TOOL_LIMIT")
        self.used += 1


class OrcToolDispatcher:
    def __init__(self, tools, registry: ProductRegistry, budget: SourceBudget, *, timeout_seconds: float,
                 now: Callable[[], datetime] = lambda: datetime.now(VIETNAM)):
        self.tools, self.registry, self.budget, self.timeout, self.now = tools, registry, budget, timeout_seconds, now
        self.plans: dict[str, dict[str, Any]] = {}     # plan_result_id (= call_id) → lịch đã kiểm
        self.results: dict[str, dict[str, Any]] = {}   # call_id → kết quả, để tra dữ kiện orc trích
        self._cache: dict[str, Any] = {}
        definitions = {definition["name"] for definition in tools.definitions()}
        available = {"plan_itinerary"}
        if "search_products" in definitions or getattr(tools, "supports_catalog", False):
            available.add("find_products")
        if {"get_recommendations", "get_similar_products"} & definitions:
            available.add("recommend")
        if getattr(tools, "supports_catalog", False):
            available |= set(CATALOG_TOOLS)
        self.allowed = [name for name in TOOLS if name in available]

    async def run(self, call: dict[str, Any], *, context: dict | None = None) -> dict[str, Any]:
        """Một lời gọi đã qua kiểm schema. Lỗi của lời gọi này không ảnh hưởng các lời gọi khác cùng lượt."""
        result = {"call_id": call["call_id"], "tool": call["name"], "status": "ok", "refs": [], "coverage": None,
                  "data": None, "error": None}
        try:
            if call["name"] not in self.allowed:
                raise ToolError("TOOL_NOT_ALLOWED")
            errors = tool_errors(call["name"], call["arguments"])
            if errors:
                raise ToolError("INVALID_ARGUMENTS")
            args = {key: value for key, value in call["arguments"].items() if value is not None and key != "why"}
            if call["name"] == "plan_itinerary":
                # Latest explicit constraints persist even if model omits them in a subsequent tool call.
                for key, source in (("free_only", "free_only"), ("budget_vnd", "trip_budget_vnd")):
                    if source in (context or {}):
                        args[key] = context[source]
            await getattr(self, "_" + call["name"])(args, result)
            if call["name"] == "plan_itinerary":
                consent = bool((context or {}).get("planning_consent")) and not (context or {}).get("stopped")
                # Trường bắt buộc khách chưa nói (hoặc khác giá trị đã lưu) thì chưa được lưu lịch (AC-AGT-01).
                missing = unconfirmed_trip_fields(args, context or {})
                result["data"]["needs_update_trip"] = ([] if consent else ["planning_consent"]) + missing
                result["data"]["commit_allowed"] = not result["data"]["needs_update_trip"]
        except ToolError as exc:
            result.update(status="error", refs=[], error={"code": exc.code, "retryable": exc.retryable,
                          **({"reason": exc.reason} if exc.reason else {})})
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


    @staticmethod
    def _filters(product: dict, args: dict, *, room=False) -> bool:
        from datetime import date
        if not room:
            excluded = {fold(place) for place in args.get("excluded_destinations") or []}
            if fold(product.get("destination") or "") in excluded:
                return False
            name = args.get("name_contains")
            if name:
                def words(text: str) -> str:
                    return " ".join(re.findall(r"\w+", fold(text)))
                needle = words(name)
                if not needle or f" {needle} " not in f" {words(product.get('name') or '')} ":
                    return False
        if product.get("available") is False and cost_mode(product) != "free":
            return False
        if args.get("price_max") is not None and (product.get("unitPrice") is None or product["unitPrice"] > args["price_max"]):
            return False
        stars = product.get("starRating") or (product.get("attributes") or {}).get("starRating")
        if args.get("star_rating_min") is not None and (stars is None or stars < args["star_rating_min"]):
            return False
        if args.get("check_in"):
            start = date.fromisoformat(args["check_in"])
            end = date.fromisoformat(args.get("check_out") or args["check_in"])
            count = max(1, (end - start).days) if room else 1
            if any(available_on(product, start + timedelta(days=n)) is False for n in range(count)):
                return False
        return True

    async def _rooms(self, refs: list[str], args: dict, result: dict) -> None:
        rooms, coverage, errors = {}, {}, {}
        for ref in refs:
            product = self.registry.product(ref)
            if product["taxonomy"] != "hotel" or (product.get("attributes") or {}).get("parentProductId"):
                continue
            try:
                data = await self.source("list", {"parentProductId": product["productId"], "taxonomy": "hotel",
                                                 "availableOnly": True, "sort": "price_asc", "limit": 20, "offset": 0})
                # No continuation unless orc explicitly requests parent_ref + cursor.
                rows = [p for p in data["results"] if self._filters(p, {**args, "star_rating_min": None}, room=True)]
                rooms[ref] = [self.registry.add(p) for p in rows]
                coverage[ref] = {"checked": len(data["results"]), "total": data.get("total"),
                                 "complete": len(data["results"]) >= data.get("total", len(data["results"]))}
            except ToolError as exc:
                errors[ref] = exc.code
            except Exception as exc:  # noqa: BLE001 - room lookup failure must preserve retrieved hotel cards
                logger.warning("itinerary.v2.rooms_failed reason=%s", type(exc).__name__)
                errors[ref] = "TOOL_FAILED"
        result["data"] = {**(result.get("data") or {}), "rooms": rooms, "room_errors": errors}
        result["coverage"] = {**(result.get("coverage") or {}), "rooms": coverage}
        if errors or any(not row["complete"] for row in coverage.values()):
            result["status"] = "partial"

    async def _find_products(self, args: dict, result: dict) -> None:
        args = {"cursor": None, "exclude_refs": [], "free_only": False, "destination": None,
                "parent_ref": None, "sort": "popular", "limit": 10, **args}
        if args.get("check_out") and (not args.get("check_in") or args["check_out"] <= args["check_in"]):
            raise ToolError("INVALID_STAY_DATES")
        offset = self._offset(args)
        if args.get("parent_ref"):
            params = {"parentProductId": self.registry.identify(args["parent_ref"]), "availableOnly": True,
                      "sort": "price_asc" if args["sort"] == "relevance" else args["sort"],
                      "limit": args["limit"], "offset": offset,
                      **({"freeOnly": True} if args["free_only"] else {})}
            data = await self.source("list", params)
        elif args.get("query"):
            params = {"query": args["query"], "taxonomy": args["taxonomy"], "limit": args["limit"], "offset": offset,
                      **({"destination": args["destination"]} if args["destination"] else {})}
            for key, target in (("price_max", "priceMax"), ("star_rating_min", "starRatingMin")):
                if args.get(key) is not None:
                    params[target] = args[key]
            data = await self.source("search_products", params)
        else:
            if not getattr(self.tools, "supports_catalog", False):
                raise ToolError("CATALOG_UNAVAILABLE")
            data = await self.source("list", {"taxonomy": args["taxonomy"], "availableOnly": True,
                 "sort": "popular" if args["sort"] == "relevance" else args["sort"],
                 "limit": args["limit"], "offset": offset,
                 **({"freeOnly": True} if args["free_only"] else {}),
                 **({"destination": args["destination"]} if args["destination"] else {})})
        raw = data["results"]
        rows = [p for p in raw if self._filters(p, args, room=bool(args["parent_ref"]))]
        if args.get("query") and args["sort"] in ("price_asc", "price_desc"):
            known = [p for p in rows if p.get("unitPrice") is not None]
            unknown = [p for p in rows if p.get("unitPrice") is None]
            rows = sorted(known, key=lambda p: p["unitPrice"], reverse=args["sort"] == "price_desc") + unknown
        self._page(result, args, rows, None, offset)
        more = bool(raw) and data.get("total") is not None and offset + len(raw) < data["total"]
        result["coverage"] = {"checked": len(raw), "total": data.get("total"),
            "scope": "search_page" if args.get("query") else "catalog_page",
            "filtered": len(raw) - len(rows),
            "next_cursor": self.registry.issue_cursor(args, offset + len(raw)) if more else None}
        if args["taxonomy"] == "hotel" and not args["parent_ref"] and getattr(self.tools, "supports_catalog", False):
            await self._rooms(result["refs"], args, result)

    async def _get_products(self, args: dict, result: dict) -> None:
        refs = list(dict.fromkeys(args["refs"]))
        async def fetch(ref):
            try:
                return await self.source("detail", self.registry.identify(ref))
            except ToolError as exc:
                return exc.code
            except Exception as exc:  # noqa: BLE001 - one adapter failure must not cancel other product refreshes
                logger.warning("itinerary.v2.detail_failed reason=%s", type(exc).__name__)
                return "TOOL_FAILED"
        rows = await asyncio.gather(*(fetch(ref) for ref in refs))
        errors = {}
        for ref, row in zip(refs, rows):
            if isinstance(row, str):
                errors[ref] = row
            else:
                result["refs"].append(self.registry.add(row))
        result["coverage"] = {"checked": len(refs), "total": len(refs), "next_cursor": None}
        result["data"] = {"errors": errors}
        if errors:
            result["status"] = "partial" if result["refs"] else "error"
            if not result["refs"]:
                result["error"] = {"code": "PRODUCT_REFRESH_FAILED", "retryable": False}
        if args.get("include_rooms"):
            await self._rooms(result["refs"], {}, result)

    async def _recommend(self, args: dict, result: dict) -> None:
        if args.get("like_ref"):
            data = await self.source("get_similar_products", {"productId": self.registry.identify(args["like_ref"]),
                                                              "limit": args.get("k", 5)})
            products = data["results"]
            result["data"] = {"strategy": "similar"}
        else:
            data = await self.source("get_recommendations", {key: args[key] for key in ("k", "destination") if args.get(key) is not None})
            products = data["recommendations"]
            result["data"] = {"strategy": data["strategy"]}
        excluded = {self.registry.identify(ref) for ref in args.get("exclude_refs") or []}
        eligible = [p for p in products if p["productId"] not in excluded and
                    (not args.get("taxonomy") or p["taxonomy"] == args["taxonomy"]) and
                    (not args.get("destination") or p.get("destination") == args["destination"])]
        result["refs"] = [self.registry.add(p) for p in eligible]
        result["data"]["because"] = {ref: p.get("because") or [] for ref, p in zip(result["refs"], eligible)}
        result["coverage"] = {"checked": len(products), "total": None, "next_cursor": None,
                              "filtered": len(products) - len(eligible)}
        if not result["refs"]:
            result["status"] = "empty"

    async def _lookup_flights(self, args: dict, result: dict) -> None:
        values = {key: None for key in ("origin", "destination", "date", "time_of_day", "sort", "limit")}
        await lookup_flights(self, {**values, **args}, result)

    async def _plan_itinerary(self, args: dict, result: dict) -> None:
        refs = list(dict.fromkeys([ref for day in args["schedule"] for slot in ("morning", "afternoon", "evening")
                                   for ref in [day.get(slot)] if ref]
                                 + [stay["room_ref"] for stay in args.get("stays") or []]
                                 + [ref for ref in (args.get("flights") or {}).values() if ref]))
        products = {ref: self.registry.product(ref) for ref in refs}
        checked = plan_slots(args, products, self.registry.fetched())
        logger.info("itinerary.v2.plan_checked call=%s feasibility=%s violations=%s", result["call_id"],
                    checked["feasibility"], ",".join(issue["code"] for issue in checked["violations"]))
        self.plans[result["call_id"]] = {"plan_result_id": result["call_id"], "products": products, **checked}
        result["refs"] = refs
        result["data"] = {"plan_result_id": result["call_id"], "feasibility": checked["feasibility"],
            "nights": checked["nights"], "days": checked["plan_days"], "stays": checked["stays"],
            "violations": checked["violations"], "warnings": checked["warnings"],
            "savings": checked["savings"], "costs": checked["costs"], **checked["costs"]}
