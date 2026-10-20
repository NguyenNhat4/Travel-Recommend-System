"""Use case v2: chỉ câu trả lời hợp lệ được ghi; lỗi trả mã ngắn và nhả khoá; nút chỉ nhận lệnh server đã cấp."""
import asyncio

import pytest

from src.backend.app.application.itinerary.v2_use_cases import (
    RunAssistantV2,
    V2TurnError,
)
from src.backend.app.infrastructure.persistence.assistant_v2_store import (
    InMemoryAssistantV2Store,
)


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


def test_date_party_duration_survive_real_runtime_and_store_between_turns():
    """Exercise actual final patch validation and persistence, without claiming LLM interpretation coverage."""
    import json

    from langchain_core.messages import AIMessage

    from src.backend.app.agents.orc_v2 import OrcV2Runtime
    from src.backend.tests.fakes.orc_tools import FakeTools, ScriptedModel, respond

    async def run():
        turns = [
            ('Lên kế hoạch Hà Nội', {'destination': 'Hà Nội', 'planning_consent': True}),
            ('t6 tuần này', {'start_date': '2026-10-16'}),
            ('3 người lớn', {'adults': 3}),
            ('đi 2 ngày', {'days': 2}),
        ]
        models = []
        def factory(**kw):
            message, values = turns[len(models)]
            args = {k: v for k, v in respond('Mình đã ghi nhận.', turn_kind='clarification').items() if k != 'action'}
            args['context_patch'] = {**values, 'evidence': message}
            model = ScriptedModel([AIMessage(content='', tool_calls=[{'id': 'r', 'name': 'respond', 'args': args}])])
            models.append(model)
            return OrcV2Runtime(tools=FakeTools(), llm=model, known_refs=kw['known_refs'],
                                request_timeout_seconds=60, tool_timeout_seconds=1, model_timeout_seconds=10)
        store = InMemoryAssistantV2Store()
        case = RunAssistantV2(store, factory)
        cid = None
        for i, (message, _) in enumerate(turns):
            final = await case.run(request(str(i), message=message, **({'conversationId': cid} if cid else {})), owner='o')
            cid = final['conversationId']
        saved = await store.load('o', cid)
        assert saved['context'] == {'destination': 'Hà Nội', 'planning_consent': True,
                                    'start_date': '2026-10-16', 'adults': 3, 'days': 2}
        last = json.loads(models[-1].payloads[0][1].content)
        assert last['context']['start_date'] == '2026-10-16'
        assert last['context']['adults'] == 3
        assert [t['user'] for t in last['history']][-2:] == ['t6 tuần này', '3 người lớn']
    asyncio.run(run())
