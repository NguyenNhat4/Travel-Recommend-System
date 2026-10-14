"""Working memory assistant v2 trên Redis thật: khoá lượt, ghi đúng một lần, revision, mảng rỗng giữ nguyên.

Chạy: RUN_REDIS_INTEGRATION=1 (docker compose up -d redis).
"""
import asyncio
import os
import uuid

import pytest

from src.backend.app.infrastructure.persistence.assistant_v2_store import RedisAssistantV2Store

REDIS_URL = os.getenv("ITINERARY_REDIS_URL", "redis://:devpass@localhost:6379/2")

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_REDIS_INTEGRATION") != "1", reason="set RUN_REDIS_INTEGRATION=1 to test against local Redis"
)


def final(effect="keep"):
    return {"conversationId": "c", "runId": "r", "turnKind": "itinerary" if effect == "replace" else "answer",
            "message": "Xin chào", "planEffect": effect, "planRevision": 0, "alternatives": [], "warnings": [],
            "itinerary": {"days": [], "stays": []} if effect == "replace" else None}


async def cleanup(client, store, owner, conversation):
    """Chỉ xoá khoá test này tạo ra; Redis có thể đang được tiến trình khác dùng."""
    keys = [store._key("conversation", owner, conversation),
            *(store._key("turn", owner, conversation, f"t{i}") for i in range(6))]
    await client.delete(*keys)
    await client.aclose()


def test_claims_commit_once_and_keep_empty_arrays():
    import redis.asyncio as redis_asyncio

    async def scenario():
        client = redis_asyncio.from_url(REDIS_URL)
        store = RedisAssistantV2Store(client, ttl_seconds=60)
        owner, conversation = f"it-{uuid.uuid4().hex}", str(uuid.uuid4())
        change = {"patch": {}, "memory": {"shown": {}, "actions": {}}, "message": "chào", "base_revision": None}
        try:
            first = await store.claim(owner, conversation, "t1", "h")
            assert (await store.claim(owner, conversation, "t1", "h"))["status"] == "in_progress"
            assert (await store.claim(owner, conversation, "t1", "x"))["status"] == "conflict"
            saved = await store.finish(owner, conversation, "t1", first["run_id"], state={},
                                       final=final("replace"), **change)
            assert saved["planRevision"] == 1 and saved["alternatives"] == [] and saved["warnings"] == []
            replay = await store.claim(owner, conversation, "t1", "h")
            assert replay["status"] == "replay" and replay["final"] == saved
            second = await store.claim(owner, conversation, "t2", "h2")
            stale = await store.finish(owner, conversation, "t2", second["run_id"], state={},
                                       final=final("replace"), **{**change, "base_revision": 0})
            assert stale is None and (await store.claim(owner, conversation, "t2", "h2"))["status"] == "claimed"
            state = await store.load(owner, conversation)
            assert state["revision"] == 1 and state["plan"] == {"days": [], "stays": []}
        finally:
            await cleanup(client, store, owner, conversation)

    asyncio.run(scenario())


def test_concurrent_turns_in_one_conversation_keep_both_histories():
    import redis.asyncio as redis_asyncio

    async def scenario():
        client = redis_asyncio.from_url(REDIS_URL)
        store = RedisAssistantV2Store(client, ttl_seconds=60)
        owner, conversation = f"it-{uuid.uuid4().hex}", str(uuid.uuid4())
        try:
            claims = [await store.claim(owner, conversation, f"t{i}", f"h{i}") for i in range(5)]
            await asyncio.gather(*(store.finish(owner, conversation, f"t{i}", claim["run_id"], state={},
                                                final=final(), patch={}, memory={"shown": {}, "actions": {}},
                                                message=f"m{i}", base_revision=None)
                                   for i, claim in enumerate(claims)))
            state = await store.load(owner, conversation)
            assert sorted(turn["message"] for turn in state["turns"]) == [f"m{i}" for i in range(5)]
        finally:
            await cleanup(client, store, owner, conversation)

    asyncio.run(scenario())
