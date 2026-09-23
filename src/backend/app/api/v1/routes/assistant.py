"""HTTP and SSE boundaries for the read-only itinerary agent."""
from __future__ import annotations

import asyncio
import json
import logging
from time import perf_counter
import uuid
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import JSONResponse, StreamingResponse

from src.backend.app.api.deps import get_plan_itinerary
from src.backend.app.api.v1.schemas.itinerary import ItineraryRequestModel
from src.backend.app.application.itinerary.contracts import error_response, valid
from src.backend.app.application.itinerary.use_cases import PlanItinerary
from src.backend.app.core.request_context import current_request_id

router = APIRouter(tags=["assistant"])
logger = logging.getLogger("uvicorn.error")


def _conversation_label(payload: ItineraryRequestModel) -> str:
    return (payload.conversationId or "new")[:64].replace("\n", "_").replace("\r", "_")


def _unavailable(request_id: str) -> JSONResponse:
    return JSONResponse(status_code=503, content=error_response(
        "SEARCH_UNAVAILABLE", "Dịch vụ dữ liệu lịch trình chưa được cấu hình.", request_id, True
    ))


async def _run(payload: ItineraryRequestModel, request: Request, authorization: str | None,
               use_case: PlanItinerary):
    request_id = current_request_id() or uuid.uuid4().hex
    conversation = _conversation_label(payload)
    logger.info("itinerary.start requestId=%s conversationId=%s transport=json", request_id, conversation)
    if not valid("ItineraryRequest", payload.model_dump(exclude_none=True)):
        return JSONResponse(status_code=422, content=error_response(
            "VALIDATION_ERROR", "Yêu cầu lịch trình không hợp lệ.", request_id
        ))
    planner = use_case.planner(authorization)
    if planner is None:
        return _unavailable(request_id)
    try:
        state = await use_case.run(planner, payload.model_dump(), request_id, config=use_case.trace_config(
            payload.message, request_id, conversation, transport="json"))
    except TimeoutError:
        logger.warning("itinerary.timeout requestId=%s conversationId=%s transport=json", request_id, conversation)
        return JSONResponse(status_code=503, content=error_response(
            "SEARCH_UNAVAILABLE", "Yêu cầu vượt quá thời gian xử lý. Vui lòng thử lại.", request_id, True
        ))
    except Exception:
        logger.exception("itinerary.failed requestId=%s conversationId=%s transport=json", request_id, conversation)
        return JSONResponse(status_code=500, content=error_response(
            "INTERNAL_ERROR", "Không thể xử lý yêu cầu lúc này.", request_id
        ))
    request.state.itinerary_metrics = {
        "latencyMs": state["latency_ms"], "retryCount": state["attempt"],
        "status": state["response"].get("status"), "validationIssues": state["validation_issues"],
    }
    logger.info(
        "itinerary.completed requestId=%s conversationId=%s transport=json httpStatus=%s status=%s latencyMs=%s retryCount=%s",
        request_id, state["response"].get("conversationId", conversation), state["http_status"],
        state["response"].get("status", "ERROR"), state["latency_ms"], state["attempt"],
    )
    return JSONResponse(status_code=state["http_status"], content=state["response"])


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _observed_duration_ms(started_at: float, finished_at: float | None = None) -> int:
    return max(1, round(((finished_at if finished_at is not None else perf_counter()) - started_at) * 1000))


@router.post("/assistant/itineraries")
async def create_itinerary(payload: ItineraryRequestModel, request: Request,
                           authorization: str | None = Header(default=None),
                           use_case: PlanItinerary = Depends(get_plan_itinerary)):
    return await _run(payload, request, authorization, use_case)


@router.post("/assistant/itineraries/stream")
async def stream_itinerary(payload: ItineraryRequestModel, request: Request,
                           authorization: str | None = Header(default=None),
                           use_case: PlanItinerary = Depends(get_plan_itinerary)):
    request_id = current_request_id() or uuid.uuid4().hex
    if not valid("ItineraryRequest", payload.model_dump(exclude_none=True)):
        return JSONResponse(status_code=422, content=error_response(
            "VALIDATION_ERROR", "Yêu cầu lịch trình không hợp lệ.", request_id
        ))
    planner = use_case.planner(authorization)
    if planner is None:
        return _unavailable(request_id)
    run_id = uuid.uuid4().hex
    conversation = _conversation_label(payload)
    logger.info(
        "itinerary.start requestId=%s runId=%s conversationId=%s transport=sse",
        request_id, run_id, conversation,
    )

    async def events() -> AsyncIterator[str]:
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
                        logger.info(
                            "itinerary.node requestId=%s runId=%s sequence=%s node=%s outcome=%s durationMs=%s",
                            request_id, run_id, emitted + 1, item.get("node", "unknown"),
                            item.get("event_type", "completed"), duration_ms,
                        )
                        yield _sse("node.completed", {
                            "sequence": emitted + 1, "nodeId": item.get("node", "unknown"),
                            "outcome": item.get("event_type", "completed"),
                            "message": item.get("message", ""), "durationMs": duration_ms,
                        })
                        emitted += 1
                    last_node_at = perf_counter()
            if final_state is None or "response" not in final_state:
                raise RuntimeError("graph ended without a response")
            yield _sse("run.completed", {
                "runId": run_id, "httpStatus": final_state["http_status"],
                "response": final_state["response"],
            })
            logger.info(
                "itinerary.completed requestId=%s runId=%s conversationId=%s transport=sse httpStatus=%s status=%s latencyMs=%s retryCount=%s",
                request_id, run_id, final_state["response"].get("conversationId", conversation),
                final_state["http_status"], final_state["response"].get("status", "ERROR"),
                final_state.get("latency_ms", 0), final_state.get("attempt", 0),
            )
        except TimeoutError:
            logger.warning(
                "itinerary.timeout requestId=%s runId=%s conversationId=%s transport=sse",
                request_id, run_id, conversation,
            )
            yield _sse("run.failed", {"runId": run_id, "httpStatus": 503, "error": error_response(
                "SEARCH_UNAVAILABLE", "Yêu cầu vượt quá thời gian xử lý. Vui lòng thử lại.", request_id, True
            )})
        except Exception:
            logger.exception(
                "itinerary.failed requestId=%s runId=%s conversationId=%s transport=sse",
                request_id, run_id, conversation,
            )
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
