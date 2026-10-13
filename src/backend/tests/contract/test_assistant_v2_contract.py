"""HTTP và SSE của assistant v2 khớp contract: cùng câu trả lời, sự kiện có thứ tự, lỗi theo Error Envelope."""
import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator

from src.backend.app.api.v2.router import api_router
from src.backend.app.application.itinerary.product_registry import ProductRegistry
from src.backend.app.application.itinerary.v2_final import render_final
from src.backend.app.application.itinerary.v2_use_cases import RunAssistantV2
from src.backend.app.infrastructure.persistence.assistant_v2_store import InMemoryAssistantV2Store
from src.backend.tests.fakes.orc_tools import respond
from src.shared.contracts.scripts.bundle_openapi import bundle

COMPONENTS = bundle(Path(__file__).resolve().parents[3] / "shared/contracts/assistant-v2.openapi.yaml")["components"]


def valid(schema: str, value) -> bool:
    return Draft202012Validator({"$ref": f"#/components/schemas/{schema}", "components": COMPONENTS}).is_valid(value)


class Runner:
    def __init__(self, progress):
        self.progress = progress

    async def run(self, inputs):
        if self.progress:
            await self.progress("activity", {"groupId": "think:1", "kind": "think", "status": "completed",
                "taxonomy": None, "explanation": "Mình sẽ tra lựa chọn phù hợp.",
                "counts": {"found": 0, "eligible": 0, "selected": 0, "displayed": 0}})
            activity = {"groupId": "c1", "kind": "search", "status": "running", "taxonomy": "hotel",
                        "counts": {"found": 0, "eligible": 0, "selected": 0, "displayed": 0}}
            await self.progress("activity", activity)
            await self.progress("tool-completed", {**activity, "status": "completed"})
        final, memory = render_final(respond("Xin chào!"), registry=ProductRegistry(), plans={}, results={},
                                     conversation_id=inputs["conversation_id"], run_id=inputs["run_id"])
        return {"final": final, "memory": memory, "patch": {}}


def client() -> TestClient:
    app = FastAPI()
    app.include_router(api_router, prefix="/api/v2")
    app.state.token_verifier = None
    app.state.rate_limiter = None
    app.state.run_assistant_v2 = RunAssistantV2(InMemoryAssistantV2Store(), lambda progress=None, **_: Runner(progress))
    return TestClient(app)


def events(text: str) -> list[dict]:
    rows = []
    for block in text.strip().split("\n\n"):
        name, data = block.split("\n", 1)
        envelope = json.loads(data.removeprefix("data: "))
        assert name == "event: " + envelope["event"] and valid("AssistantV2Event", envelope)
        rows.append(envelope)
    return rows


def body(turn="t1", **fields):
    return {"clientTurnId": turn, "basePlanRevision": None, "message": "Xin chào", **fields}


def test_stream_reports_progress_then_exactly_one_final_and_json_replays_it():
    with client() as api:
        stream = api.post("/api/v2/assistant/itineraries/stream", json=body())
        assert stream.status_code == 200
        rows = events(stream.text)
        assert [row["event"] for row in rows] == ["start", "activity", "activity", "tool-completed", "final"]
        assert rows[1]["data"]["kind"] == "think" and rows[1]["data"]["explanation"]
        assert [row["sequence"] for row in rows] == [1, 2, 3, 4, 5] and len({row["runId"] for row in rows}) == 1
        replay = api.post("/api/v2/assistant/itineraries", json=body())
        assert replay.status_code == 200 and replay.json() == rows[-1]["data"]
        assert valid("AssistantV2Final", replay.json())


def test_invalid_request_conflicting_turn_and_unknown_conversation_are_envelopes():
    with client() as api:
        invalid = api.post("/api/v2/assistant/itineraries", json={"message": "hi"})
        assert invalid.status_code == 422 and invalid.json()["error"]["code"] == "VALIDATION_ERROR"
        assert api.post("/api/v2/assistant/itineraries", json=body()).status_code == 200
        conflict = api.post("/api/v2/assistant/itineraries/stream", json=body(message="Khác"))
        assert conflict.status_code == 409 and conflict.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"
        missing = api.post("/api/v2/assistant/itineraries", json=body("t2", conversationId="nope"))
        assert missing.status_code == 404 and valid("ErrorResponse", missing.json())
