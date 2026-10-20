"""Working memory v2: ghi đúng một lần, revision chặn ghi đè lịch, hội thoại v1 mở tiếp được."""
import asyncio

from src.backend.app.infrastructure.persistence.assistant_v2_store import InMemoryAssistantV2Store, from_v1


def final(effect="keep", message="Xin chào", itinerary=None):
    return {"conversationId": "c", "runId": "r", "turnKind": "itinerary" if effect == "replace" else "answer",
            "message": message, "planEffect": effect, "planRevision": 0, "itinerary": itinerary}


def change(**fields):
    return {"final": final(), "patch": {}, "memory": {"shown": {}, "actions": {}}, "message": "chào",
            "base_revision": None, **fields}


def test_claim_replay_conflict_and_single_commit():
    async def run():
        store = InMemoryAssistantV2Store()
        first = await store.claim("o", "c", "t1", "hash")
        assert first["status"] == "claimed"
        assert (await store.claim("o", "c", "t1", "hash"))["status"] == "in_progress"
        assert (await store.claim("o", "c", "t1", "other"))["status"] == "conflict"
        saved = await store.finish("o", "c", "t1", first["run_id"], state={}, **change())
        assert saved["planRevision"] == 0
        assert (await store.claim("o", "c", "t1", "hash")) == {"status": "replay", "run_id": first["run_id"],
                                                                "final": saved}
        assert await store.finish("o", "c", "t1", first["run_id"], state={}, **change()) is None
        assert await store.load("someone-else", "c") is None
    asyncio.run(run())


def test_g12_stale_revision_cannot_replace_the_plan():
    async def run():
        store = InMemoryAssistantV2Store()
        plan = {"days": []}
        one = await store.claim("o", "c", "t1", "h1")
        saved = await store.finish("o", "c", "t1", one["run_id"], state={},
                                   **change(final=final("replace", itinerary=plan)))
        assert saved["planRevision"] == 1
        two = await store.claim("o", "c", "t2", "h2")
        assert await store.finish("o", "c", "t2", two["run_id"], state={},
                                  **change(final=final("replace", itinerary=plan), base_revision=0)) is None
        assert (await store.claim("o", "c", "t2", "h2"))["status"] == "claimed"  # khoá đã nhả, gửi lại được
        assert (await store.load("o", "c"))["revision"] == 1
    asyncio.run(run())


def test_failed_turn_releases_claim_and_keeps_state():
    async def run():
        store = InMemoryAssistantV2Store()
        claim = await store.claim("o", "c", "t1", "h")
        await store.release("o", "c", "t1", claim["run_id"])
        assert await store.load("o", "c") is None
        assert (await store.claim("o", "c", "t1", "h"))["status"] == "claimed"
    asyncio.run(run())


def test_v1_conversation_keeps_trip_refs_and_history():
    state = from_v1({"intent": {"destination": "Huế", "days": 2, "party": {"adults": 2, "children": 0}},
                     "plan_consent": True,
                     "shown": {"items": [{"ref": "#3", "productId": "x", "name": "Đại Nội", "taxonomy": "attraction"}]},
                     "conversation_history": [{"role": "user", "content": "Huế có gì"},
                                              {"role": "assistant", "content": "Có Đại Nội"}]})
    assert state["context"] == {"destination": "Huế", "days": 2, "adults": 2, "children": 0,
                                "planning_consent": True}
    assert state["shown"] == {"p3": {"productId": "x", "name": "Đại Nội", "taxonomy": "attraction"}}
    assert state["turns"] == [{"message": "Huế có gì", "answer": "Có Đại Nội", "refs": []}]
