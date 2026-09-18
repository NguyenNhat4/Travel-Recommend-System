"""HTTP boundary for the read-only itinerary agent."""
import asyncio
import uuid

from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse

from src.backend.app.agents.runtime_dependencies import RuntimeAgentDependencies
from src.backend.app.agents.tools.itinerary_gateway import ItineraryToolGateway
from src.backend.app.application.itinerary.contracts import error_response, valid
from src.backend.app.core.request_context import current_request_id
from src.backend.app.domain.itinerary.schemas import ChatRequest, ChatResponse, ItineraryRequestModel

router = APIRouter(tags=["assistant"])


async def _run(payload: ItineraryRequestModel, request: Request, authorization: str | None):
    request_id = current_request_id() or uuid.uuid4().hex
    body = payload.model_dump(exclude_none=True)
    if not valid("ItineraryRequest", body):
        return JSONResponse(status_code=422, content=error_response("VALIDATION_ERROR", "Yêu cầu lịch trình không hợp lệ.", request_id))
    clients = getattr(request.app.state, "itinerary_http_clients", None)
    store = getattr(request.app.state, "itinerary_conversation_store", None)
    if clients is None or store is None:
        return JSONResponse(status_code=503, content=error_response("SEARCH_UNAVAILABLE", "Dịch vụ dữ liệu lịch trình chưa được cấu hình.", request_id, True))
    gateway = ItineraryToolGateway(clients, clients, clients, recommendation_authorization=authorization)
    runtime = RuntimeAgentDependencies(gateway, store, getattr(request.app.state, "itinerary_llm", None), authorization)
    try:
        state = await asyncio.wait_for(runtime.graph().ainvoke({
            "query": payload.message or "", "conversation_id": payload.conversationId,
            "intent_override": payload.intentOverride or {}, "request_id": request_id,
        }), timeout=5)
    except TimeoutError:
        return JSONResponse(status_code=503, content=error_response("SEARCH_UNAVAILABLE", "Yêu cầu vượt quá thời gian xử lý. Vui lòng thử lại.", request_id, True))
    except Exception:
        return JSONResponse(status_code=500, content=error_response("INTERNAL_ERROR", "Không thể xử lý yêu cầu lúc này.", request_id))
    # Safe trace is accessible to local integration tests/observability, not added to the shared API.
    request.state.itinerary_metrics = {"latencyMs": state["latency_ms"], "retryCount": state["attempt"],
                                      "status": state["response"].get("status"), "validationIssues": state["validation_issues"]}
    return JSONResponse(status_code=state["http_status"], content=state["response"])


@router.post("/assistant/itineraries")
async def create_itinerary(payload: ItineraryRequestModel, request: Request,
                           authorization: str | None = Header(default=None)):
    return await _run(payload, request, authorization)


@router.post("/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest, request: Request, authorization: str | None = Header(default=None)):
    if len(payload.message) > 1000:
        return JSONResponse(status_code=422, content=error_response("VALIDATION_ERROR", "Tin nhắn lịch trình tối đa 1000 ký tự.", current_request_id() or ""))
    response = await _run(ItineraryRequestModel(message=payload.message), request, authorization)
    if response.status_code != 200:
        return response
    import json
    body = json.loads(response.body)
    text = body.get("question", body.get("message")) or json.dumps(body["itinerary"], ensure_ascii=False)
    return ChatResponse(response=text)


@router.get("/status")
async def agent_status(request: Request):
    return {"status": "ready" if getattr(request.app.state, "itinerary_http_clients", None) is not None else "not_configured",
            "agent": "Itinerary LangGraph Agent"}
