"""Chuẩn hóa điểm đến theo catalog, lập tool plan và thực thi các lời gọi Search/Recommendation/Similar."""
from __future__ import annotations

import asyncio
import json
import logging

from src.backend.app.application.itinerary.contracts import valid
from src.backend.app.application.itinerary.tool_contracts import (
    SIMILAR_PRODUCTS, argument_names, contracts, normalize_arguments, validate,
)
from src.backend.app.application.ports.itinerary_tools import ToolError, ToolExecutorPort
from src.backend.app.domain.itinerary.normalization import match_destination

from ..models import DestinationChoice
from .history import llm_context
from .messages import chat_model, event, failure, message
from .prompts import DESTINATION_PROMPT, SIMILAR_HINT, TOOL_PLAN_PROMPT

logger = logging.getLogger("uvicorn.error")

MAX_CALLS = 5
MAX_SIMILAR_CALLS = 2  # mỗi lượt, mỗi anchor một lần; vẫn nằm trong MAX_CALLS


async def catalog_destinations(tools: ToolExecutorPort, timeout_seconds: float) -> list[str] | None:
    """Danh sách điểm đến có trong catalog, nhiều sản phẩm nhất trước (cùng số thì theo tên); None khi không lấy được."""
    try:
        listing = await asyncio.wait_for(tools.list_destinations(), timeout_seconds)
    except Exception:
        # Listing failure cannot prove a destination unsupported. Search may still succeed.
        return None
    if valid("DestinationListResponse", listing):
        ranked = sorted(listing["destinations"], key=lambda item: (-item["productCount"], item["destination"]))
        return [item["destination"] for item in ranked]
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


def _similar_limit() -> int:
    """`limit` của Similar do server cố định ở mức tối đa hợp đồng: engine không lọc điểm đến, kết quả lệch
    điểm đến bị bỏ sau truy xuất, nên lấy nhiều nhất có thể để còn phương án cùng điểm đến."""
    return contracts()[SIMILAR_PRODUCTS]["arguments"]["properties"]["limit"]["maximum"]


def _similar_dropped(state: dict, reason: str) -> None:
    # Chỉ ghi lý do: productId do LLM viết có thể là id bịa hoặc chép từ nội dung người dùng.
    logger.warning("itinerary.tool_plan.similar_dropped requestId=%s reason=%s",
                   state.get("request_id", "unknown"), reason)


def _allowed_similar_calls(state: dict, plan: list, offered: frozenset[str] | None) -> list:
    """Bỏ lời gọi Similar không hợp lệ, TRƯỚC khi đếm độ dài plan; lời gọi tool khác giữ nguyên.

    Anchor chỉ được lấy từ `previous_selection` (sản phẩm đã hiển thị, lưu phía server), mỗi anchor một lần,
    tối đa `MAX_SIMILAR_CALLS`. `offered` None (plan đã lưu, chạy lại) thì bỏ qua kiểm "có được mời không".
    """
    anchors = {item.get("productId") for item in state.get("previous_selection", [])}
    kept, seen = [], set()
    for call in plan:
        if call["name"] != SIMILAR_PRODUCTS:
            kept.append(call)
            continue
        anchor = (call.get("args") or {}).get("productId")
        if offered is not None and SIMILAR_PRODUCTS not in offered:
            reason = "not_offered"
        elif not isinstance(anchor, str) or anchor not in anchors:
            reason = "unknown_anchor"
        elif anchor in seen:
            reason = "duplicate_anchor"
        elif len(seen) >= MAX_SIMILAR_CALLS:
            reason = "similar_limit"
        else:
            seen.add(anchor)
            kept.append(call)
            continue
        _similar_dropped(state, reason)
    return kept


def _destination_search(state: dict) -> dict:
    """Lời gọi search tất định theo điểm đến đã chuẩn hóa — cùng giá trị fallback `query` ở `_validated_args`."""
    destination = state.get("intent", {}).get("destination")
    if not destination:
        raise ToolError("INVALID_TOOL_PLAN")
    return {"name": "search_products", "args": {"query": destination}}


def _pop_last_similar(state: dict, calls: list) -> bool:
    """Nhường chỗ trong trần `MAX_CALLS`: Similar là best-effort nên bị bỏ trước mọi tool khác."""
    for index in range(len(calls) - 1, -1, -1):
        if calls[index]["name"] == SIMILAR_PRODUCTS:
            del calls[index]
            _similar_dropped(state, "call_budget")
            return True
    return False


def _swapped_taxonomies(state: dict, plan: list) -> list[str]:
    """Loại (taxonomy) của các sản phẩm gốc planner đề xuất đổi, theo thứ tự, không trùng.

    Chỉ anchor có trong `previous_selection` mới biết loại; anchor bịa không đóng góp gì. Loại người dùng đã
    loại trừ bị bỏ vì search theo loại đó là tham số sai (`_validated_args`).
    """
    known = {item.get("productId"): item.get("taxonomy") for item in state.get("previous_selection", [])}
    excluded = state.get("constraints", {}).get("exclude_taxonomies", [])
    taxonomies = []
    for call in plan:
        anchor = (call.get("args") or {}).get("productId") if call["name"] == SIMILAR_PRODUCTS else None
        taxonomy = known.get(anchor) if isinstance(anchor, str) else None
        if taxonomy and taxonomy not in excluded and taxonomy not in taxonomies:
            taxonomies.append(taxonomy)
    return taxonomies


def _has_room(state: dict, validated: list) -> bool:
    """Còn chỗ trong trần `MAX_CALLS`, hoặc nhường được chỗ bằng cách bỏ lời gọi Similar cuối."""
    return len(validated) < MAX_CALLS or _pop_last_similar(state, validated)


def _append_search(state: dict, validated: list, taxonomy: str | None) -> None:
    """Thêm search tất định theo điểm đến (và loại, nếu biết); nơi gọi đã dành chỗ bằng `_has_room`."""
    search = _destination_search(state)
    if taxonomy:
        search["args"]["taxonomy"] = taxonomy
    validated.append({"name": search["name"], "args": _validated_args(state, search)})


def _validated_args(state: dict, call: dict) -> dict:
    """Ép args một lời gọi về đúng hợp đồng tool; sai cấu trúc thì ném `ToolError`."""
    intent, constraints = state.get("intent", {}), state.get("constraints", {})
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
    if call["name"] == SIMILAR_PRODUCTS:
        args["limit"] = _similar_limit()
    args = normalize_arguments(call["name"], args)
    if intent.get("destination") and "destination" in known:
        # Tên catalog đã chuẩn hóa mới là nguồn sự thật; planner viết "Hồ Chí Minh" thay vì
        # "TP. Hồ Chí Minh" là cách diễn đạt khác, không phải chuyến đi khác. Similar không có tham số này.
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
    return normalize_arguments(call["name"], args)


def validated_plan(state: dict, plan: list, *, require_recommendations: bool = False,
                   offered: frozenset[str] | None = None) -> list:
    """Ép tool plan của LLM về đúng hợp đồng tool; sai cấu trúc thì ném `ToolError`.

    `offered` là tên tool đã đưa cho planner ở lượt lập plan mới; None khi chạy lại plan đã lưu.
    Chạy lại một plan đã kiểm cho ra đúng plan đó, kể cả id, nên retry dùng lại được kết quả cũ theo id.
    """
    if not isinstance(plan, list):
        raise ToolError("INVALID_TOOL_PLAN")
    calls = _allowed_similar_calls(state, plan, offered)
    if plan and not calls:
        # Plan chỉ có anchor bịa: tìm theo điểm đến thay vì huỷ cả lượt.
        calls = [_destination_search(state)]
    # Similar tính vào trần MAX_CALLS nhưng là best-effort: quá trần vì Similar thì bỏ Similar, không huỷ cả lượt.
    while len(calls) > MAX_CALLS and _pop_last_similar(state, calls):
        pass
    if not 1 <= len(calls) <= MAX_CALLS:
        raise ToolError("INVALID_TOOL_PLAN")
    validated = [{"name": call["name"], "args": _validated_args(state, call)} for call in calls]
    if require_recommendations and not any(call["name"] == "get_recommendations" for call in validated):
        if not _has_room(state, validated):
            raise ToolError("INVALID_TOOL_PLAN")
        destination = state["intent"]["destination"]
        validated.append({"name": "get_recommendations",
                          "args": normalize_arguments("get_recommendations", {"destination": destination})})
    if any(call["name"] == SIMILAR_PRODUCTS for call in plan):
        # Lưới an toàn: Similar là best-effort (lỗi mềm, kết quả lệch điểm đến bị bỏ), nên plan có Similar (kể cả
        # lời gọi vừa bị bỏ) giữ một search cho mỗi loại đang đổi; search không lọc loại cũng tính, và Similar
        # nhường chỗ cho search. Hết chỗ mà không còn Similar để bỏ thì plan đã như plan không có Similar: giữ
        # nguyên thay vì huỷ lượt. Anchor bịa không cho biết loại: chỉ cần một search theo điểm đến, và plan không
        # còn search nào thì vẫn sai. Plan không đụng tới Similar giữ nguyên như trước.
        for taxonomy in _swapped_taxonomies(state, plan):
            if not any(call["name"] == "search_products" and call["args"].get("taxonomy") in (None, taxonomy)
                       for call in validated) and _has_room(state, validated):
                _append_search(state, validated, taxonomy)
        if not any(call["name"] == "search_products" for call in validated):
            if not _has_room(state, validated):
                raise ToolError("INVALID_TOOL_PLAN")
            _append_search(state, validated, None)
    # Đánh số sau cùng để id liên tục dù đã bỏ lời gọi Similar.
    return [{"id": f"call-{index}", **call} for index, call in enumerate(validated)]


def _planner_input(state: dict, intent: dict, constraints: dict,
                   definitions: list) -> tuple[list, list, frozenset[str]]:
    """(definitions đưa cho LLM, messages, tên tool được mời).

    Payload luôn mang ngữ cảnh chung của mọi lượt gọi LLM (`llm_context`). Similar chỉ được mời khi lượt có
    `previous_selection` và gateway có port Similar; khi đó mới thêm gợi ý prompt và `previous_selection` chỉ còn
    `productId`/`name`/`taxonomy`. Lượt còn lại thấy đúng bộ tool và prompt như trước khi có Similar.
    """
    selection = state.get("previous_selection") or []
    offer_similar = bool(selection) and any(d["name"] == SIMILAR_PRODUCTS for d in definitions)
    if not offer_similar:
        definitions = [d for d in definitions if d["name"] != SIMILAR_PRODUCTS]
    payload = {"message": state.get("query", ""),
               **llm_context(state, intent=intent, constraints=constraints),
               # Tên khoá cũ mà TOOL_PLAN_PROMPT nhắc tới: intent đã chuẩn hóa là nguồn chính.
               "intent": intent,
               "constraints": constraints}
    if offer_similar:
        payload["previous_selection"] = [{key: item[key] for key in ("productId", "name", "taxonomy") if key in item}
                                         for item in selection]
    system = f"{TOOL_PLAN_PROMPT} {SIMILAR_HINT}" if offer_similar else TOOL_PLAN_PROMPT
    messages = [("system", system), ("human", json.dumps(payload, ensure_ascii=False))]
    return definitions, messages, frozenset(d["name"] for d in definitions)


async def build_plan(state: dict, intent: dict, constraints: dict, *, tools: ToolExecutorPort | None, llm,
                     llm_timeout_seconds: float, require_recommendations: bool) -> tuple[list, dict | None]:
    """Tool plan đã kiểm; phần tử thứ hai là update lỗi khi không lập được plan hợp lệ."""
    try:
        if tools is None:
            raise ToolError("ITINERARY_TOOLS_NOT_CONFIGURED")
        plan, offered = state.get("tool_plan"), None
        if not plan:  # plan đã lưu (lần retry) chạy lại nguyên trạng, không hỏi LLM và không đọc definitions()
            definitions, prompt, offered = _planner_input(state, intent, constraints, tools.definitions())
            response = await asyncio.wait_for(chat_model(llm).bind_tools(definitions).ainvoke(prompt),
                                              llm_timeout_seconds)
            plan = response.tool_calls
        plan = validated_plan({**state, "intent": intent, "constraints": constraints}, plan,
                              require_recommendations=require_recommendations, offered=offered)
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
            # Tên lấy từ plan đã qua `validated_plan`; không log arguments.
            logger.warning("itinerary.tool.timeout requestId=%s name=%s",
                           state.get("request_id", "unknown"), call["name"])
            error = ToolError("TOOL_TIMEOUT", retryable=True)
        except ToolError as exc:
            error = exc
        except Exception:
            error = ToolError("TOOL_EXECUTION_FAILED")
        return {"tool_call_id": call["id"], "name": call["name"], "error": error.as_dict()}

    return list(await asyncio.gather(*(execute(call) for call in plan)))
