"""Bản giả cho test assistant v2: nguồn sản phẩm (cổng tool) và model trả quyết định viết sẵn."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from langchain_core.messages import AIMessage

from src.backend.app.application.itinerary.orc_contracts import (
    BUILD,
    CONTROL_TOOLS,
    TAXONOMIES,
    TOOLS,
)
from src.backend.app.application.ports.itinerary_tools import ToolError


def product(product_id: str, taxonomy: str = "attraction", *, destination: str = "Huế", price: int | None = 100_000,
            unit: str = "PER_PERSON", **attributes) -> dict[str, Any]:
    return {"productId": product_id, "name": f"Sản phẩm {product_id}", "taxonomy": taxonomy,
            "destination": destination, "unitPrice": price, "currency": "VND", "priceUnit": unit, "available": True,
            "attributes": attributes}


class FakeTools:
    """Cổng tool giả: ghi lại mọi request, trả dữ liệu cấu hình sẵn; `failures` là số lần lỗi tạm thời đầu tiên."""

    supports_catalog = True

    def __init__(self, products: list[dict] | None = None, *, total: int | None = None, failures: int = 0,
                 listing: dict[str, list[dict]] | None = None):
        self.products = products or []
        self.total = len(self.products) if total is None else total
        self.failures = failures
        self.listing = listing or {}
        self.calls: list[tuple[str, Any]] = []

    def definitions(self) -> list[dict]:
        return [{"name": name} for name in ("search_products", "get_recommendations", "get_similar_products")]

    def _fail(self) -> None:
        if self.failures:
            self.failures -= 1
            raise ToolError("SEARCH_UNAVAILABLE", retryable=True)

    async def execute(self, call: dict) -> dict:
        self.calls.append((call["name"], deepcopy(call["args"])))
        try:
            self._fail()
        except ToolError as exc:
            return {"error": {"code": exc.code, "retryable": exc.retryable}}
        if call["name"] == "get_recommendations":
            return {"data": {"strategy": "popular", "recommendations": [{**p, "because": []} for p in self.products]}}
        if call["name"] == "get_similar_products":
            return {"data": {"productId": call["args"]["productId"], "requestId": "r",
                             "results": [{**p, "score": 0.5} for p in self.products]}}
        offset = call["args"].get("offset", 0)
        page = self.products[offset:offset + call["args"].get("limit", 20)]
        return {"data": {"results": [{**p, "score": 0.5} for p in page], "total": self.total}}

    async def get_product_detail(self, product_id: str) -> dict:
        self.calls.append(("detail", product_id))
        self._fail()
        return next({**p, "description": "Chi tiết"} for p in self.products if p["productId"] == product_id)

    async def list_destinations(self) -> dict:
        self.calls.append(("destinations", None))
        return {"destinations": [{"destination": "Huế", "productCount": 3}]}

    async def list_products(self, params: dict) -> dict:
        self.calls.append(("list", deepcopy(params)))
        self._fail()
        rows = self.listing.get(params.get("parentProductId") or params.get("destination") or "",
                                [] if params.get("parentProductId") else self.products)
        offset, limit = params.get("offset", 0), params.get("limit", 20)
        return {"results": rows[offset:offset + limit], "total": len(rows)}


def arguments(tool: str, **values) -> dict:
    """Tham số đủ field của một tool (field không nêu là null/[]/false/none), như model strict mode trả về."""
    def empty(schema: dict):
        kind = schema.get("type")
        kinds = kind if isinstance(kind, list) else [kind]
        if "null" in kinds:
            return None
        return {"array": [], "boolean": False}.get(kinds[0], "none" if "enum" in schema else None)
    schema = TOOLS.get(tool) or CONTROL_TOOLS.get(tool) or BUILD
    return dict(values) if tool in TOOLS or tool in CONTROL_TOOLS else {key: values[key] if key in values else empty(prop) for key, prop in schema["properties"].items()}


def call(tool: str, call_id: str = "c1", **values) -> dict:
    """Một lời gọi đã có mã server đánh (dùng thẳng cho dispatcher)."""
    return {"call_id": call_id, "name": tool, "arguments": arguments(tool, **({"why": "Tra dữ liệu cần cho yêu cầu."} if tool in TOOLS else {}), **values)}


def respond(text: str = "Mình đã tìm theo yêu cầu.", **fields) -> dict:
    decision = {"action": "respond", "explanation": None, "context_patch": None, "turn_kind": "answer",
                "answer": [{"type": "text", "text": text}], "cards": {t: [] for t in TAXONOMIES},
                "alternatives": [], "plan_result_id": None, "plan_effect": "keep", "disclosures": [],
                "suggestions": []}
    for key, value in fields.items():
        if key in TAXONOMIES:
            decision["cards"][key] = value
        else:
            decision[key] = value
    return decision


def execute(*calls: dict, patch: dict | None = None, explanation: str | None = None) -> dict:
    """Quyết định execute như model trả: không có mã lời gọi."""
    return {"action": "execute", "explanation": explanation, "context_patch": patch,
            "calls": [{"name": item["name"], "arguments": item["arguments"]} for item in calls]}


class ScriptedModel:
    """Model giả: trả lần lượt các quyết định cho sẵn; ghi lại payload và schema nhận được."""

    def __init__(self, decisions: list[dict]):
        self.decisions = deepcopy(decisions)
        self.payloads: list[list] = []
        self.schemas: list[dict] = []

    def bind_tools(self, tools, **kwargs):
        self.schemas.append(deepcopy(tools))
        return self

    async def ainvoke(self, messages):
        self.payloads.append(list(messages))
        decision = self.decisions.pop(0)
        if isinstance(decision, Exception):
            raise decision
        if isinstance(decision, AIMessage):
            return decision
        calls = []
        if decision.get("context_patch"):
            patch = {k: v for k, v in decision["context_patch"].items() if v is not None}
            if "trip_budget_vnd" in patch:
                patch["budget_vnd"] = patch.pop("trip_budget_vnd")
            calls.append({"name": "update_trip", "args": patch})
        if decision["action"] == "respond":
            calls.append({"name": "respond", "args": {k: v for k, v in decision.items()
                                                       if k not in ("action", "context_patch")}})
        else:
            for c in decision["calls"]:
                calls.append({"name": c["name"], "args": {"why": decision.get("explanation") or "Tra dữ liệu cần cho yêu cầu.", **c["arguments"]}})
        return AIMessage(content="", tool_calls=[{**c, "id": f"native-{len(self.payloads)}-{i}"} for i, c in enumerate(calls)])
