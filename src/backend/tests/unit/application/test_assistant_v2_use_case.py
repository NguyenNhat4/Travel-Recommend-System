"""Use case v2: chỉ câu trả lời hợp lệ được ghi; lỗi trả mã ngắn và nhả khoá; nút chỉ nhận lệnh server đã cấp."""
import asyncio

import pytest

from src.backend.app.application.itinerary.v2_use_cases import RunAssistantV2, V2TurnError
from src.backend.app.infrastructure.persistence.assistant_v2_store import InMemoryAssistantV2Store


def request(turn="t1", **fields):
    return {"clientTurnId": turn, "basePlanRevision": None, "message": "Chào bạn", **fields}


class Runner:
    def __init__(self, outcome, seen):
        self.outcome, self.seen = outcome, seen

    async def run(self, inputs):
        self.seen.append(inputs)
        if "final" not in self.outcome:
            return self.outcome
        return {**self.outcome, "final": {**self.outcome["final"], "conversationId": inputs["conversation_id"]}}


def use_case(outcome, store=None):
    seen = []
    store = store or InMemoryAssistantV2Store()
    return RunAssistantV2(store, lambda **turn: Runner(outcome, seen)), store, seen


def answer(actions=None):
    return {"final": {"conversationId": "c", "runId": "r", "turnKind": "answer", "message": "Xin chào",
                      "planEffect": "keep", "planRevision": 0, "itinerary": None},
            "patch": {"destination": "Huế"}, "memory": {"shown": {}, "actions": actions or {}}}


def test_valid_final_commits_once_and_replays():
    async def run():
        case, store, seen = use_case(answer())
        first = await case.run(request(), owner="user:1")
        assert await case.run(request(), owner="user:1") == first and len(seen) == 1
        saved = await store.load("user:1", first["conversationId"])
        assert saved["context"] == {"destination": "Huế"} and saved["turns"][0]["message"] == "Chào bạn"
        with pytest.raises(V2TurnError, match="IDEMPOTENCY_CONFLICT"):
            await case.run(request(message="khác"), owner="user:1")
    asyncio.run(run())


def test_failure_maps_to_contract_error_and_releases_the_turn():
    async def run():
        case, store, _ = use_case({"failure": "LLM_UNAVAILABLE"})
        with pytest.raises(V2TurnError) as error:
            await case.run(request(), owner="o")
        assert (error.value.code, error.value.status) == ("LLM_UNAVAILABLE", 503)
        blocked, _, _ = use_case({"failure": "VALIDATION_ERROR", "failure_message": "Không hỗ trợ"}, store)
        with pytest.raises(V2TurnError) as error:
            await blocked.run(request(), owner="o")
        assert (error.value.status, error.value.message) == (400, "Không hỗ trợ")
    asyncio.run(run())


def test_unknown_conversation_and_forged_button_are_rejected():
    async def run():
        case, _, seen = use_case(answer({"a1": {"type": "fare_query", "label": "Đắt nhất?", "query": {}}}))
        with pytest.raises(V2TurnError, match="CONVERSATION_NOT_FOUND"):
            await case.run(request(conversationId="missing"), owner="o")
        first = await case.run(request(), owner="o")
        forged = {"type": "fare_query", "actionId": "nope"}
        with pytest.raises(V2TurnError, match="VALIDATION_ERROR"):
            await case.run(request("t2", conversationId=first["conversationId"], message=None, uiAction=forged),
                           owner="o")
        clicked = {"type": "fare_query", "actionId": "a1"}
        await case.run(request("t3", conversationId=first["conversationId"], message=None, uiAction=clicked),
                       owner="o")
        assert seen[-1]["ui_action"] == {"id": "a1", "type": "fare_query", "label": "Đắt nhất?", "query": {}}
    asyncio.run(run())
