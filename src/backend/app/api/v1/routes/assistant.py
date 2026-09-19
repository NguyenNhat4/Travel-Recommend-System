"""HTTP and SSE boundaries for the read-only itinerary agent."""
from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse, StreamingResponse

from src.backend.app.agents.runtime_dependencies import RuntimeAgentDependencies
from src.backend.app.agents.tools.itinerary_gateway import ItineraryToolGateway
from src.backend.app.application.itinerary.contracts import error_response, valid
from src.backend.app.core.config import get_settings
from src.backend.app.core.request_context import current_request_id
from src.backend.app.domain.itinerary.schemas import ChatRequest, ChatResponse, ItineraryRequestModel

router = APIRouter(tags=["assistant"])


def _runtime(request: Request, authorization: str | None) -> RuntimeAgentDependencies | None:
    clients = getattr(request.app.state, "itinerary_http_clients", None)
    store = getattr(request.app.state, "itinerary_conversation_store", None)
    if clients is None or store is None:
        return None
    gateway = ItineraryToolGateway(clients, clients, clients, recommendation_authorization=authorization)
    return RuntimeAgentDependencies(gateway, store, getattr(request.app.state, "itinerary_llm", None), authorization)


def _input(payload: ItineraryRequestModel, request_id: str) -> dict[str, Any]:
    return {
        "query": payload.message or "",
        "conversation_id": payload.conversationId,
        "intent_override": payload.intentOverride or {},
        "language": payload.context.language if payload.context else None,
        "request_id": request_id,
    }


def _unavailable(request_id: str) -> JSONResponse:
    return JSONResponse(status_code=503, content=error_response(
        "SEARCH_UNAVAILABLE", "Dịch vụ dữ liệu lịch trình chưa được cấu hình.", request_id, True
    ))


async def _run(payload: ItineraryRequestModel, request: Request, authorization: str | None):
    request_id = current_request_id() or uuid.uuid4().hex
    if not valid("ItineraryRequest", payload.model_dump(exclude_none=True)):
        return JSONResponse(status_code=422, content=error_response(
            "VALIDATION_ERROR", "Yêu cầu lịch trình không hợp lệ.", request_id
        ))
    runtime = _runtime(request, authorization)
    if runtime is None:
        return _unavailable(request_id)
    try:
        state = await asyncio.wait_for(
            runtime.graph().ainvoke(_input(payload, request_id)),
            timeout=get_settings().itinerary_request_timeout_seconds,
        )
    except TimeoutError:
        return JSONResponse(status_code=503, content=error_response(
            "SEARCH_UNAVAILABLE", "Yêu cầu vượt quá thời gian xử lý. Vui lòng thử lại.", request_id, True
        ))
    except Exception:
        return JSONResponse(status_code=500, content=error_response(
            "INTERNAL_ERROR", "Không thể xử lý yêu cầu lúc này.", request_id
        ))
    request.state.itinerary_metrics = {
        "latencyMs": state["latency_ms"], "retryCount": state["attempt"],
        "status": state["response"].get("status"), "validationIssues": state["validation_issues"],
    }
    return JSONResponse(status_code=state["http_status"], content=state["response"])


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _topology(graph: Any) -> dict[str, Any]:
    drawing = graph.get_graph()
    nodes = [node_id for node_id in drawing.nodes if node_id not in {"__start__", "__end__"}]
    edges = [
        {"source": edge.source, "target": edge.target, "conditional": edge.conditional}
        for edge in drawing.edges
        if edge.source != "__start__" and edge.target != "__end__"
    ]
    return {"nodes": nodes, "edges": edges}


@router.post("/assistant/itineraries")
async def create_itinerary(payload: ItineraryRequestModel, request: Request,
                           authorization: str | None = Header(default=None)):
    return await _run(payload, request, authorization)


@router.post("/assistant/itineraries/stream")
async def stream_itinerary(payload: ItineraryRequestModel, request: Request,
                           authorization: str | None = Header(default=None)):
    request_id = current_request_id() or uuid.uuid4().hex
    if not valid("ItineraryRequest", payload.model_dump(exclude_none=True)):
        return JSONResponse(status_code=422, content=error_response(
            "VALIDATION_ERROR", "Yêu cầu lịch trình không hợp lệ.", request_id
        ))
    runtime = _runtime(request, authorization)
    if runtime is None:
        return _unavailable(request_id)
    graph = runtime.graph()
    run_id = uuid.uuid4().hex

    async def events() -> AsyncIterator[str]:
        yield _sse("run.started", {"runId": run_id, "requestId": request_id})
        yield _sse("graph.topology", _topology(graph))
        emitted = 0
        final_state: dict[str, Any] | None = None
        try:
            async with asyncio.timeout(get_settings().itinerary_request_timeout_seconds):
                async for state in graph.astream(_input(payload, request_id), stream_mode="values"):
                    final_state = state
                    for item in state.get("events", [])[emitted:]:
                        yield _sse("node.completed", {
                            "sequence": emitted + 1, "nodeId": item.get("node", "unknown"),
                            "outcome": item.get("event_type", "completed"),
                            "message": item.get("message", ""), "durationMs": item.get("latency_ms", 0),
                        })
                        emitted += 1
            if final_state is None or "response" not in final_state:
                raise RuntimeError("graph ended without a response")
            yield _sse("run.completed", {
                "runId": run_id, "httpStatus": final_state["http_status"],
                "response": final_state["response"],
            })
        except TimeoutError:
            yield _sse("run.failed", {"runId": run_id, "httpStatus": 503, "error": error_response(
                "SEARCH_UNAVAILABLE", "Yêu cầu vượt quá thời gian xử lý. Vui lòng thử lại.", request_id, True
            )})
        except Exception:
            yield _sse("run.failed", {"runId": run_id, "httpStatus": 500, "error": error_response(
                "INTERNAL_ERROR", "Không thể xử lý yêu cầu lúc này.", request_id
            )})

    return StreamingResponse(events(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache", "X-Accel-Buffering": "no",
    })


@router.post("/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest, request: Request, authorization: str | None = Header(default=None)):
    if len(payload.message) > 1000:
        return JSONResponse(status_code=422, content=error_response(
            "VALIDATION_ERROR", "Tin nhắn lịch trình tối đa 1000 ký tự.", current_request_id() or ""
        ))
    response = await _run(ItineraryRequestModel(message=payload.message), request, authorization)
    if response.status_code != 200:
        return response
    body = json.loads(response.body)
    text = body.get("question", body.get("message")) or json.dumps(body["itinerary"], ensure_ascii=False)
    return ChatResponse(response=text)


@router.get("/assistant/status")
async def agent_status(request: Request):
    clients = getattr(request.app.state, "itinerary_http_clients", None)
    return {
        "status": "ready" if clients is not None else "not_configured",
        "agent": "Itinerary LangGraph Agent", "graphVersion": "1.4.0",
        "dataMode": getattr(request.app.state, "itinerary_data_mode", "disabled"),
        "productCount": getattr(clients, "product_count", None) if clients else None,
    }
