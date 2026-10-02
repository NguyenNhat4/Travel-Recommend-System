import asyncio
from time import time

from src.backend.app.agents.nodes import finalize_node_async, intake_node_async
from src.backend.app.domain.itinerary.planning import empty_intent


CONVERSATION_ID = "3fa85f64-5717-4562-b3fc-2c963f66afa6"


class Store:
    def __init__(self):
        self.value = None

    async def load(self, conversation_id, owner="anonymous"):
        return self.value

    async def save(self, conversation_id, value, owner="anonymous"):
        self.value = value


class Archive:
    def __init__(self, restored=None, fail_record=False):
        self.restored = restored
        self.fail_record = fail_record
        self.recorded = []

    async def restore(self, conversation_id, cdp_user_id):
        return self.restored

    async def record_turn(self, conversation_id, cdp_user_id, state):
        if self.fail_record:
            raise RuntimeError("database unavailable")
        self.recorded.append((conversation_id, cdp_user_id, state))


def final_state():
    return {
        "conversation_id": CONVERSATION_ID,
        "request_id": "request-1",
        "query": "Nha Trang 3 ngày",
        "response": {
            "status": "NEEDS_CLARIFICATION",
            "conversationId": CONVERSATION_ID,
            "question": "Bạn muốn đi ngày nào?",
        },
        "http_status": 200,
        "intent": empty_intent(),
        "constraints": {},
        "conversation_history": [],
        "previous_selection": [],
        "start_date_asked": True,
        "language": "vi",
        "candidates": {},
        "sources": {},
        "started_at": time(),
    }


def test_finalize_caches_and_archives_authenticated_turn():
    store, archive = Store(), Archive()
    result = asyncio.run(finalize_node_async(
        final_state(), store=store, owner="user:VP1", archive=archive, cdp_user_id="VP1"))

    assert result["http_status"] == 200
    assert store.value["start_date_asked"] is True
    assert archive.recorded[0][0:2] == (CONVERSATION_ID, "VP1")
    assert archive.recorded[0][2]["response"]["status"] == "NEEDS_CLARIFICATION"


def test_archive_failure_does_not_fail_a_valid_turn():
    result = asyncio.run(finalize_node_async(
        final_state(), store=Store(), owner="user:VP1",
        archive=Archive(fail_record=True), cdp_user_id="VP1"))
    assert result["http_status"] == 200


def test_intake_restores_archive_on_cache_miss_and_repopulates_cache():
    restored = {
        "intent": {**empty_intent(), "destination": "Nha Trang", "days": 3},
        "constraints": {}, "conversation_history": [], "previous_selection": [],
        "start_date_asked": True, "language": "vi",
    }
    store = Store()
    result = asyncio.run(intake_node_async(
        {"conversation_id": CONVERSATION_ID, "query": "đổi thành 4 ngày"},
        store=store, owner="user:VP1", archive=Archive(restored), cdp_user_id="VP1"))

    assert result["intent"]["destination"] == "Nha Trang"
    assert result["intent"]["days"] == 3
    assert store.value == restored
