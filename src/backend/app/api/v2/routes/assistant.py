"""HTTP và SSE của assistant v2 (`/api/v2/assistant/itineraries`, contract `assistant-v2.openapi.yaml`)."""
from __future__ import annotations

import asyncio
from functools import lru_cache
from hashlib import sha256
import json
from pathlib import Path

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import JSONResponse, StreamingResponse
from jsonschema import Draft202012Validator, FormatChecker

from src.backend.app.api.deps import client_ip, conversation_owner, get_use_case
from src.backend.app.application.auth.errors import RateLimited
from src.backend.app.application.itinerary.contracts import error_response
from src.backend.app.application.itinerary.v2_use_cases import RunAssistantV2, V2TurnError
from src.backend.app.core.request_context import current_request_id
from src.shared.contracts.scripts.bundle_openapi import bundle

router = APIRouter(tags=["assistant"])
ENTRY = Path(__file__).resolve().parents[5] / "shared/contracts/assistant-v2.openapi.yaml"
RETRY_MESSAGE = "Trợ lý chưa trả lời được lúc này. Bạn thử lại sau ít phút nhé."
INVALID_MESSAGE = "Yêu cầu gửi trợ lý không hợp lệ hoặc đã thay đổi."


@lru_cache(maxsize=1)
def _request_validator() -> Draft202012Validator:
    components = bundle(ENTRY)["components"]
    return Draft202012Validator({"$ref": "#/components/schemas/AssistantV2Request", "components": components},
                                format_checker=FormatChecker())


def _error_body(error: V2TurnError) -> dict:
    retryable = error.status in (409, 429, 503) or error.status >= 500
    return error_response(error.code, error.message or (RETRY_MESSAGE if retryable else INVALID_MESSAGE),
                          current_request_id() or "unknown", retryable)


def _error(error: V2TurnError) -> JSONResponse:
    headers = {"Retry-After": str(error.retry_after)} if error.retry_after else None
    return JSONResponse(status_code=error.status, content=_error_body(error), headers=headers)


def _owner(owner: str | None, authorization: str | None) -> str:
    """Cùng cách xác định chủ hội thoại với v1 (`RuntimeAgentDependencies`), để hội thoại v1 mở được ở v2."""
    if owner:
        return f"user:{owner}"
    return f"token:{sha256(authorization.encode()).hexdigest()}" if authorization else "anonymous"


async def _checked(request: Request, owner: str | None, ip: str) -> dict:
    limiter = getattr(request.app.state, "rate_limiter", None)
    if limiter is not None:
        try:
            await limiter.hit("assistant:sender", owner or f"ip:{ip}")
        except RateLimited as exc:
            raise V2TurnError("TOO_MANY_ATTEMPTS", 429, retry_after=exc.retry_after_seconds) from exc
    try:
        payload = await request.json()
    except ValueError:
        payload = None
    if not isinstance(payload, dict) or not _request_validator().is_valid(payload):
        raise V2TurnError("VALIDATION_ERROR", 422)
    return payload


def _sse(event: str, run_id: str, sequence: int, data: dict) -> str:
    envelope = {"event": event, "runId": run_id, "sequence": sequence, "data": data}
    return f"event: {event}\ndata: {json.dumps(envelope, ensure_ascii=False, separators=(',', ':'))}\n\n"


@router.post("/assistant/itineraries")
async def create_itinerary(request: Request, authorization: str | None = Header(default=None),
                           owner: str | None = Depends(conversation_owner), ip: str = Depends(client_ip),
                           use_case: RunAssistantV2 = Depends(get_use_case("run_assistant_v2"))):
    try:
        payload = await _checked(request, owner, ip)
        return await use_case.run(payload, owner=_owner(owner, authorization), authorization=authorization)
    except V2TurnError as exc:
        return _error(exc)


@router.post("/assistant/itineraries/stream")
async def stream_itinerary(request: Request, authorization: str | None = Header(default=None),
                           owner: str | None = Depends(conversation_owner), ip: str = Depends(client_ip),
                           use_case: RunAssistantV2 = Depends(get_use_case("run_assistant_v2"))):
    try:
        payload = await _checked(request, owner, ip)
        turn = await use_case.prepare(payload, owner=_owner(owner, authorization), authorization=authorization)
    except V2TurnError as exc:
        return _error(exc)

    async def events():
        run_id, sequence = turn["run_id"], 1
        yield _sse("start", run_id, sequence, {"conversationId": turn["conversation_id"],
                                               "clientTurnId": turn["turn_id"],
                                               "planRevision": turn["state"].get("revision", 0)})
        queue: asyncio.Queue = asyncio.Queue()

        async def progress(kind: str, data: dict) -> None:
            await queue.put((kind, data))

        # Mất kết nối không huỷ lượt: lượt chạy xong và được ghi, gửi lại cùng clientTurnId sẽ nhận câu trả lời đó.
        task = asyncio.create_task(use_case.execute(turn, progress=progress))
        task.add_done_callback(lambda done: done.cancelled() or done.exception())
        while not task.done() or not queue.empty():
            getter = asyncio.create_task(queue.get())
            await asyncio.wait({task, getter}, return_when=asyncio.FIRST_COMPLETED)
            if getter.done():
                kind, data = getter.result()
                sequence += 1
                yield _sse(kind, run_id, sequence, data)
            else:
                getter.cancel()
        sequence += 1
        try:
            yield _sse("final", run_id, sequence, task.result())
        except V2TurnError as exc:
            yield _sse("error", run_id, sequence, _error_body(exc))

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})
