"""Một lượt assistant v2: khoá lượt, chạy orc, ghi câu trả lời hợp lệ đúng một lần (PRD architecture §3, §13 plan).

Lỗi (model, hết ngân sách, đầu vào bị chặn) trả thông báo ngắn và không ghi gì: lịch và trí nhớ hội thoại giữ nguyên.
"""
from __future__ import annotations

from hashlib import sha256
import json
from typing import Any
from uuid import NAMESPACE_URL, uuid5

#: Mã lỗi orc trả về → HTTP status theo contract.
FAILURE_STATUS = {"VALIDATION_ERROR": 400, "LLM_UNAVAILABLE": 503, "ITINERARY_VALIDATION_FAILED": 500}


class V2TurnError(Exception):
    def __init__(self, code: str, status: int, message: str | None = None, *, retry_after: int | None = None):
        super().__init__(code)
        self.code, self.status, self.message = code, status, message
        # Đang có lượt cùng mã chạy dở: gửi lại sau 1 giây.
        self.retry_after = retry_after or (1 if code == "TURN_IN_PROGRESS" else None)


class RunAssistantV2:
    def __init__(self, store, runner_factory):
        self.store = store
        self.runner_factory = runner_factory

    async def run(self, payload: dict[str, Any], *, owner: str, authorization: str | None = None) -> dict[str, Any]:
        return await self.execute(await self.prepare(payload, owner=owner, authorization=authorization))

    async def prepare(self, payload: dict[str, Any], *, owner: str, authorization: str | None = None) -> dict:
        """Khoá lượt trước khi trả header, để gửi trùng nhận 409 chứ không phải lỗi giữa luồng SSE."""
        turn_id = payload["clientTurnId"]
        conversation_id = payload.get("conversationId") or str(uuid5(NAMESPACE_URL, f"assistant-v2:{owner}:{turn_id}"))
        state = await self.store.load(owner, conversation_id)
        if payload.get("conversationId") and state is None:
            raise V2TurnError("CONVERSATION_NOT_FOUND", 404)
        content = sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        claim = await self.store.claim(owner, conversation_id, turn_id, content)
        if claim["status"] == "in_progress":
            raise V2TurnError("TURN_IN_PROGRESS", 409)
        if claim["status"] == "conflict":
            raise V2TurnError("IDEMPOTENCY_CONFLICT", 409)
        turn = {"owner": owner, "conversation_id": conversation_id, "turn_id": turn_id, "payload": payload,
                "state": state or {}, "authorization": authorization, "run_id": claim["run_id"],
                "replay": claim.get("final"), "ui_action": None}
        action = payload.get("uiAction")
        if action is not None and turn["replay"] is None:
            # Chỉ nhận nút server đã phát ở lượt trước; trình duyệt không gửi được giá hay sản phẩm tuỳ ý.
            issued = (turn["state"].get("actions") or {}).get(action["actionId"])
            if not issued or issued["type"] != action["type"] or \
                    issued.get("alternativeId") != action.get("alternativeId"):
                await self._release(turn)
                raise V2TurnError("VALIDATION_ERROR", 422)
            turn["ui_action"] = {"id": action["actionId"], **issued}
        return turn

    async def execute(self, turn: dict[str, Any], *, progress=None) -> dict[str, Any]:
        if turn["replay"] is not None:
            return turn["replay"]
        payload, state = turn["payload"], turn["state"]
        runner = self.runner_factory(
            owner=turn["owner"], conversation_id=turn["conversation_id"], run_id=turn["run_id"],
            known_refs={ref: item["productId"] for ref, item in (state.get("shown") or {}).items()},
            authorization=turn["authorization"], progress=progress)
        if runner is None:
            await self._release(turn)
            raise V2TurnError("LLM_UNAVAILABLE", 503)
        message = payload.get("message") or (turn["ui_action"] or {}).get("label") or ""
        try:
            outcome = await runner.run({
                "message": payload.get("message") or "", "ui_action": turn["ui_action"],
                "intent_override": payload.get("intentOverride"),
                "language": (payload.get("context") or {}).get("language", "vi"),
                "context": state.get("context") or {}, "plan": state.get("plan"),
                "turns": state.get("turns") or [], "shown": state.get("shown") or {},
                "conversation_id": turn["conversation_id"], "run_id": turn["run_id"]})
        except Exception as exc:
            await self._release(turn)
            raise V2TurnError("INTERNAL_ERROR", 500) from exc
        if outcome.get("failure"):
            await self._release(turn)
            raise V2TurnError(outcome["failure"], FAILURE_STATUS[outcome["failure"]], outcome.get("failure_message"))
        final = await self.store.finish(turn["owner"], turn["conversation_id"], turn["turn_id"], turn["run_id"],
                                        state=state, final=outcome["final"], patch=outcome["patch"],
                                        memory=outcome["memory"], message=message,
                                        base_revision=payload["basePlanRevision"])
        if final is None:
            raise V2TurnError("PLAN_REVISION_CONFLICT", 409)
        return final

    async def _release(self, turn: dict[str, Any]) -> None:
        await self.store.release(turn["owner"], turn["conversation_id"], turn["turn_id"], turn["run_id"])
