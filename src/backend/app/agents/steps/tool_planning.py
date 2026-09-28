"""Chuẩn hóa điểm đến theo catalog, lập tool plan và thực thi các lời gọi Search/Recommendation."""
from __future__ import annotations

import asyncio
import json
import logging

from src.backend.app.application.itinerary.contracts import valid
from src.backend.app.application.itinerary.tool_contracts import argument_names, normalize_arguments, validate
from src.backend.app.application.ports.itinerary_tools import ToolError, ToolExecutorPort
from src.backend.app.domain.itinerary.normalization import match_destination

from ..models import DestinationChoice
from .history import llm_context
from .messages import chat_model, event, failure, message
from .prompts import DESTINATION_PROMPT, TOOL_PLAN_PROMPT

logger = logging.getLogger("uvicorn.error")

MAX_CALLS = 5


async def catalog_destinations(tools: ToolExecutorPort, timeout_seconds: float) -> list[str] | None:
    """Danh sách điểm đến có trong catalog; None khi không lấy được."""
    try:
        listing = await asyncio.wait_for(tools.list_destinations(), timeout_seconds)
    except Exception:
        # Listing failure cannot prove a destination unsupported. Search may still succeed.
        return None
    if valid("DestinationListResponse", listing):
        return [item["destination"] for item in listing["destinations"]]
    return None


async def _choose_destination(state: dict, value: str, supported: list[str], llm,
                              timeout_seconds: float) -> str | None:
    """Let the model pick from the catalog's own destination names; the answer is verified against them."""
    payload = {"user_destination": value, "catalog_destinations": supported, **llm_context(state)}
    result = await asyncio.wait_for(chat_model(llm).with_structured_output(DestinationChoice).ainvoke([
        ("system", DESTINATION_PROMPT), ("human", json.dumps(payload, ensure_ascii=False))]),
        timeout_seconds)
    chosen = DestinationChoice.model_validate(result).destination
    return chosen if chosen in supported else None


async def canonical_destination(state: dict, intent: dict, changed: list, supported: list[str],
                                llm, llm_timeout_seconds: float) -> dict | None:
    """Ghi tên điểm đến chuẩn vào `intent`; trả update lỗi khi LLM hỏng hoặc điểm đến ngoài catalog."""
    canonical = match_destination(intent["destination"], supported)
    if canonical is None:
        try:
            canonical = await _choose_destination(state, intent["destination"], supported, llm, llm_timeout_seconds)
        except Exception:
            logger.exception("itinerary.llm_failed requestId=%s node=tool step=destination",
                             state.get("request_id", "unknown"))
            return {**failure(state, "LLM_UNAVAILABLE", message(state, "llm_understand"), retryable=True),
                    "tool_plan": [], "tool_results": [], "events": [event("tool", "LLM_UNAVAILABLE")]}
    if canonical is None:
        text = message(state, "unsupported", destination=intent["destination"], destinations=", ".join(supported))
        update = failure(state, "UNSUPPORTED_DESTINATION", text, 422)
        update["response"]["error"]["details"] = {"destination": intent["destination"],
                                                  "supportedDestinations": supported,
                                                  "conversationId": state["conversation_id"]}
        return {**update, "tool_plan": [], "tool_results": [],
                "events": [event("tool", "UNSUPPORTED_DESTINATION")]}
    if canonical != intent["destination"]:
        changed.insert(0, "destination")
    intent["destination"] = canonical
    return None


def validated_plan(state: dict, plan: list, *, require_recommendations: bool = False) -> list:
    """Ép tool plan của LLM về đúng hợp đồng tool; sai cấu trúc thì ném `ToolError`."""
    if not isinstance(plan, list) or not 1 <= len(plan) <= MAX_CALLS:
        raise ToolError("INVALID_TOOL_PLAN")
    validated = []
    intent, constraints = state.get("intent", {}), state.get("constraints", {})
    for index, call in enumerate(plan):
        args = dict(call.get("args", {}))
        # Planner thỉnh thoảng bỏ quên `query` dù SearchRequest bắt buộc. Điểm đến đã chuẩn hóa là
        # đúng thứ nó điền ở các lần chạy thành công, nên dùng làm fallback tất định thay vì hỏng cả request.
        if call["name"] == "search_products" and not str(args.get("query") or "").strip():
            args["query"] = intent.get("destination") or state.get("query", "")
        # Planner đôi khi tự thêm tham số hợp đồng không có — ví dụ `excludeProducts` khi constraints
        # có `exclude_products`. Bỏ khóa lạ thay vì huỷ cả plan: sản phẩm bị loại đã được lọc sau
        # truy xuất ở `retrieval.collect`, nên không mất hành vi nào.
        known = argument_names(call["name"])
        args = {key: value for key, value in args.items() if key in known}
        args = normalize_arguments(call["name"], args)
        if intent.get("destination"):
            # Tên catalog đã chuẩn hóa mới là nguồn sự thật; planner viết "Hồ Chí Minh" thay vì
            # "TP. Hồ Chí Minh" là cách diễn đạt khác, không phải chuyến đi khác.
            args["destination"] = intent["destination"]
        if call["name"] == "search_products":
            if args.get("taxonomy") in constraints.get("exclude_taxonomies", []):
                raise ToolError("INVALID_ARGUMENTS")
            if args.get("taxonomy") == "hotel":
                for source, target in (("hotel_price_max", "priceMax"), ("star_rating_min", "starRatingMin")):
                    if constraints.get(source) is not None:
                        args[target] = constraints[source]
            # A total-trip budget cannot be translated into a per-unit filter.
            if constraints.get("hotel_price_max") is None:
                args.pop("priceMin", None)
                args.pop("priceMax", None)
        args = normalize_arguments(call["name"], args)
        validated.append({"id": f"call-{index}", "name": call["name"], "args": args})
    if require_recommendations and not any(call["name"] == "get_recommendations" for call in validated):
        if len(validated) >= MAX_CALLS:
            raise ToolError("INVALID_TOOL_PLAN")
        validated.append({"id": f"call-{len(validated)}", "name": "get_recommendations",
                          "args": normalize_arguments("get_recommendations", {"destination": intent["destination"]})})
    return validated


async def build_plan(state: dict, intent: dict, constraints: dict, *, tools: ToolExecutorPort | None, llm,
                     llm_timeout_seconds: float, require_recommendations: bool) -> tuple[list, dict | None]:
    """Tool plan đã kiểm; phần tử thứ hai là update lỗi khi không lập được plan hợp lệ."""
    try:
        if tools is None:
            raise ToolError("ITINERARY_TOOLS_NOT_CONFIGURED")
        plan = state.get("tool_plan")
        if not plan:
            response = await asyncio.wait_for(chat_model(llm).bind_tools(tools.definitions()).ainvoke([
                ("system", TOOL_PLAN_PROMPT),
                ("human", json.dumps({"message": state.get("query", ""),
                                      **llm_context(state, intent=intent, constraints=constraints),
                                      # Tên khoá cũ mà TOOL_PLAN_PROMPT nhắc tới: intent đã chuẩn hóa là nguồn chính.
                                      "intent": intent,
                                      "constraints": constraints}, ensure_ascii=False))]),
                llm_timeout_seconds)
            plan = response.tool_calls
        plan = validated_plan({**state, "intent": intent, "constraints": constraints}, plan,
                              require_recommendations=require_recommendations)
    except ToolError as exc:
        return [], {"tool_plan": [], "tool_results": [{"error": exc.as_dict()}], "events": [event("tool", exc.code)]}
    except TimeoutError:
        # LLM chậm trả lời là sự cố tạm thời, không phải plan sai cấu trúc; phải cho retry_node thử lại.
        return [], {"tool_plan": [], "tool_results": [{"error": ToolError("INVALID_TOOL_PLAN", retryable=True).as_dict()}],
                    "events": [event("tool", "LLM_TIMEOUT")]}
    except Exception:
        logger.exception("itinerary.llm_failed requestId=%s node=tool step=plan", state.get("request_id", "unknown"))
        return [], {"tool_plan": [], "tool_results": [{"error": ToolError("INVALID_TOOL_PLAN").as_dict()}],
                    "events": [event("tool", "INVALID_TOOL_PLAN")]}
    return plan, None


async def run_calls(state: dict, plan: list, tools: ToolExecutorPort, timeout_seconds: float) -> list:
    """Chạy song song các lời gọi; kết quả cũ không retryable được dùng lại thay vì gọi lần nữa."""
    previous = {item.get("tool_call_id"): item for item in state.get("tool_results", [])}

    async def execute(call):
        old = previous.get(call["id"])
        if old and ("error" not in old or not old["error"]["retryable"]):
            return old
        try:
            result = await asyncio.wait_for(tools.execute(call), timeout_seconds)
            if "data" in result:
                validate(call["name"], result["data"], "response")
            elif not isinstance(result.get("error"), dict):
                raise ToolError("INVALID_TOOL_RESPONSE")
            return {**result, "tool_call_id": call["id"], "name": call["name"], "arguments": call["args"]}
        except TimeoutError:
            error = ToolError("TOOL_TIMEOUT", retryable=True)
        except ToolError as exc:
            error = exc
        except Exception:
            error = ToolError("TOOL_EXECUTION_FAILED")
        return {"tool_call_id": call["id"], "name": call["name"], "error": error.as_dict()}

    return list(await asyncio.gather(*(execute(call) for call in plan)))
