"""HTTP and SSE boundaries for the read-only itinerary agent."""
from __future__ import annotations

import asyncio
import json
import logging
from time import perf_counter
import uuid
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse

from src.backend.app.api.deps import (
    client_ip,
    conversation_owner,
    current_principal,
    get_conversation_history,
    get_plan_itinerary,
)
from src.backend.app.application.auth.errors import RateLimited
from src.backend.app.application.auth.principal import AuthPrincipal
from src.backend.app.application.itinerary.history import ConversationHistory
from src.backend.app.api.v1.schemas.itinerary import ItineraryRequestModel
from src.backend.app.application.itinerary.contracts import error_response, valid
from src.backend.app.application.itinerary.use_cases import PlanItinerary
from src.backend.app.core.logging_config import log_event
from src.backend.app.core.request_context import current_request_id

router = APIRouter(tags=["assistant"])
logger = logging.getLogger("uvicorn.error")


def _conversation_label(payload: ItineraryRequestModel) -> str:
    return (payload.conversationId or "new")[:64].replace("\n", "_").replace("\r", "_")


async def _rate_limited(request: Request, owner: str | None, ip: str) -> JSONResponse | None:
    """Giới hạn số tin gửi trợ lý (NFR-SEC-04): theo cdp_user_id, khách thì theo IP. App chưa dựng
    limiter (test không chạy lifespan) thì bỏ qua."""
    limiter = getattr(request.app.state, "rate_limiter", None)
    if limiter is None:
        return None
    try:
        await limiter.hit("assistant:sender", owner or f"ip:{ip}")
    except RateLimited as exc:
        body = error_response(
            "TOO_MANY_ATTEMPTS", f"Bạn gửi tin hơi nhanh. Vui lòng thử lại sau {exc.retry_after_seconds} giây.",
            current_request_id() or uuid.uuid4().hex, True,
        )
        body["error"]["details"] = exc.details
        return JSONResponse(status_code=429, content=body,
                            headers={"Retry-After": str(exc.retry_after_seconds)})
    return None


def _unavailable(request_id: str) -> JSONResponse:
    return JSONResponse(status_code=503, content=error_response(
        "SEARCH_UNAVAILABLE", "Dịch vụ dữ liệu lịch trình chưa được cấu hình.", request_id, True
    ))


async def _run(payload: ItineraryRequestModel, request: Request, authorization: str | None,
               owner: str | None, use_case: PlanItinerary):
    request_id = current_request_id() or uuid.uuid4().hex
    conversation = _conversation_label(payload)
    started = perf_counter()
    log_event(logger, "assistant.run.start", conversation_id=conversation, transport="json")
    if not valid("ItineraryRequest", payload.model_dump(exclude_none=True)):
        return JSONResponse(status_code=422, content=error_response(
            "VALIDATION_ERROR", "Yêu cầu lịch trình không hợp lệ.", request_id
        ))
    planner = use_case.planner(authorization, owner)
    if planner is None:
        return _unavailable(request_id)
    try:
        state = await use_case.run(planner, payload.model_dump(), request_id, config=use_case.trace_config(
            payload.message, request_id, conversation, transport="json"))
    except TimeoutError:
        log_event(logger, "assistant.run.end", "WARNING", conversation_id=conversation, transport="json",
                  status="TIMEOUT", http_status=503, duration_ms=round((perf_counter() - started) * 1000))
        return JSONResponse(status_code=503, content=error_response(
            "SEARCH_UNAVAILABLE", "Yêu cầu vượt quá thời gian xử lý. Vui lòng thử lại.", request_id, True
        ))
    except Exception:
        log_event(logger, "assistant.run.end", "ERROR", exc_info=True, conversation_id=conversation,
                  transport="json", status="FAILED", http_status=500,
                  duration_ms=round((perf_counter() - started) * 1000))
        return JSONResponse(status_code=500, content=error_response(
            "INTERNAL_ERROR", "Không thể xử lý yêu cầu lúc này.", request_id
        ))
    request.state.itinerary_metrics = {
        "latencyMs": state["latency_ms"], "retryCount": state["attempt"],
        "status": state["response"].get("status"), "validationIssues": state["validation_issues"],
    }
    for index, item in enumerate(state.get("events", []), 1):
        log_event(logger, "assistant.node", conversation_id=conversation, transport="json", sequence=index,
                  node=item.get("node", "unknown"), outcome=item.get("event_type", "completed"),
                  duration_ms=item.get("latency_ms"))
    log_event(logger, "assistant.run.end", conversation_id=state["response"].get("conversationId", conversation),
              transport="json", status=state["response"].get("status", "ERROR"), http_status=state["http_status"],
              duration_ms=state["latency_ms"], retry_count=state["attempt"])
    return JSONResponse(status_code=state["http_status"], content=state["response"])


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _observed_duration_ms(started_at: float, finished_at: float | None = None) -> int:
    return max(1, round(((finished_at if finished_at is not None else perf_counter()) - started_at) * 1000))


@router.post("/assistant/itineraries")
async def create_itinerary(payload: ItineraryRequestModel, request: Request,
                           authorization: str | None = Header(default=None),
                           owner: str | None = Depends(conversation_owner),
                           ip: str = Depends(client_ip),
                           use_case: PlanItinerary = Depends(get_plan_itinerary)):
    if (limited := await _rate_limited(request, owner, ip)) is not None:
        return limited
    return await _run(payload, request, authorization, owner, use_case)


@router.post("/assistant/itineraries/stream")
async def stream_itinerary(payload: ItineraryRequestModel, request: Request,
                           authorization: str | None = Header(default=None),
                           owner: str | None = Depends(conversation_owner),
                           ip: str = Depends(client_ip),
                           use_case: PlanItinerary = Depends(get_plan_itinerary)):
    if (limited := await _rate_limited(request, owner, ip)) is not None:
        return limited
    request_id = current_request_id() or uuid.uuid4().hex
    if not valid("ItineraryRequest", payload.model_dump(exclude_none=True)):
        return JSONResponse(status_code=422, content=error_response(
            "VALIDATION_ERROR", "Yêu cầu lịch trình không hợp lệ.", request_id
        ))
    planner = use_case.planner(authorization, owner)
    if planner is None:
        return _unavailable(request_id)
    run_id = uuid.uuid4().hex
    conversation = _conversation_label(payload)
    started = perf_counter()
    log_event(logger, "assistant.run.start", run_id=run_id, conversation_id=conversation, transport="sse")
    log_event(logger, "assistant.stream.open", run_id=run_id, conversation_id=conversation, transport="sse")

    async def events() -> AsyncIterator[str]:
        try:
            async for chunk in _events():
                yield chunk
        finally:  # kể cả khi client ngắt giữa chừng (GeneratorExit/CancelledError)
            log_event(logger, "assistant.stream.close", run_id=run_id, conversation_id=conversation,
                      transport="sse", duration_ms=round((perf_counter() - started) * 1000))

    async def _events() -> AsyncIterator[str]:
        yield _sse("run.started", {"runId": run_id, "requestId": request_id})
        yield _sse("graph.topology", planner.topology())
        emitted = 0
        last_node_at = perf_counter()
        final_state: dict[str, Any] | None = None
        try:
            async with asyncio.timeout(use_case.request_timeout_seconds):
                async for state in planner.astream(
                    use_case.inputs(payload.model_dump(), request_id),
                    config=use_case.trace_config(payload.message, request_id, conversation,
                                                 transport="sse", run_id=run_id),
                ):
                    final_state = state
                    new_events = state.get("events", [])[emitted:]
                    if not new_events:
                        continue
                    observed_duration_ms = _observed_duration_ms(last_node_at)
                    for index, item in enumerate(new_events):
                        duration_ms = item.get("latency_ms") or (observed_duration_ms if index == 0 else 1)
                        log_event(logger, "assistant.node", run_id=run_id, conversation_id=conversation,
                                  transport="sse", sequence=emitted + 1, node=item.get("node", "unknown"),
                                  outcome=item.get("event_type", "completed"), duration_ms=duration_ms)
                        yield _sse("node.completed", {
                            "sequence": emitted + 1, "nodeId": item.get("node", "unknown"),
                            "outcome": item.get("event_type", "completed"),
                            "message": item.get("message", ""), "durationMs": duration_ms,
                        })
                        emitted += 1
                    last_node_at = perf_counter()
            if final_state is None or "response" not in final_state:
                raise RuntimeError("graph ended without a response")
            if final_state["http_status"] >= 400:
                # Hợp đồng: lỗi nghiệp vụ (404 hội thoại hết hạn, 422 điểm đến ngoài catalog...) là
                # run.failed mang Error Envelope; run.completed chỉ dành cho AssistantResponse hợp lệ.
                yield _sse("run.failed", {
                    "runId": run_id, "httpStatus": final_state["http_status"],
                    "error": final_state["response"],
                })
            else:
                yield _sse("run.completed", {
                    "runId": run_id, "httpStatus": final_state["http_status"],
                    "response": final_state["response"],
                })
            log_event(logger, "assistant.run.end", run_id=run_id,
                      conversation_id=final_state["response"].get("conversationId", conversation), transport="sse",
                      status=final_state["response"].get("status", "ERROR"), http_status=final_state["http_status"],
                      duration_ms=final_state.get("latency_ms", 0), retry_count=final_state.get("attempt", 0))
        except TimeoutError:
            log_event(logger, "assistant.run.end", "WARNING", run_id=run_id, conversation_id=conversation,
                      transport="sse", status="TIMEOUT", http_status=503,
                      duration_ms=round((perf_counter() - started) * 1000))
            yield _sse("run.failed", {"runId": run_id, "httpStatus": 503, "error": error_response(
                "SEARCH_UNAVAILABLE", "Yêu cầu vượt quá thời gian xử lý. Vui lòng thử lại.", request_id, True
            )})
        except Exception:
            log_event(logger, "assistant.run.end", "ERROR", exc_info=True, run_id=run_id,
                      conversation_id=conversation, transport="sse", status="FAILED", http_status=500,
                      duration_ms=round((perf_counter() - started) * 1000))
            yield _sse("run.failed", {"runId": run_id, "httpStatus": 500, "error": error_response(
                "INTERNAL_ERROR", "Không thể xử lý yêu cầu lúc này.", request_id
            )})

    return StreamingResponse(events(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache", "X-Accel-Buffering": "no",
    })


@router.get("/assistant/status")
async def agent_status(request: Request):
    clients = getattr(request.app.state, "itinerary_http_clients", None)
    return {
        "status": "ready" if clients is not None else "not_configured",
        "agent": "Itinerary LangGraph Agent", "graphVersion": "1.4.0",
        "dataMode": getattr(request.app.state, "itinerary_data_mode", "disabled"),
        "llmMode": getattr(request.app.state, "itinerary_llm_mode", "unavailable"),
        "productCount": getattr(clients, "product_count", None) if clients else None,
    }


@router.get("/assistant/conversations")
async def list_conversations(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, alias="pageSize", ge=1, le=50),
    principal: AuthPrincipal = Depends(current_principal),
    history: ConversationHistory = Depends(get_conversation_history),
):
    return await history.list(principal.cdp_user_id, page=page, page_size=page_size)


@router.get("/assistant/conversations/{conversationId}")
async def get_conversation(
    conversationId: str,
    principal: AuthPrincipal = Depends(current_principal),
    history: ConversationHistory = Depends(get_conversation_history),
):
    result = await history.get(conversationId, principal.cdp_user_id)
    if result is None:
        return JSONResponse(status_code=404, content=error_response(
            "CONVERSATION_NOT_FOUND", "Không tìm thấy cuộc hội thoại.",
            current_request_id() or uuid.uuid4().hex,
        ))
    return result
