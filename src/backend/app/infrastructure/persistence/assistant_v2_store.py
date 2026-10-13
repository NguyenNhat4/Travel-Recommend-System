"""Working memory của assistant v2: trạng thái hội thoại và khoá theo lượt (clientTurnId), TTL 24 giờ.

Lượt chỉ được ghi khi có câu trả lời hợp lệ, đúng một lần (PRD architecture §3). Khoá lượt chặn gửi trùng: cùng
nội dung nhận lại câu trả lời đã có, đang chạy thì TURN_IN_PROGRESS, khác nội dung thì IDEMPOTENCY_CONFLICT.
Đổi lịch (`planEffect=replace`) chỉ khi revision khách đang xem khớp revision đã lưu.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from time import monotonic
from typing import Any
from uuid import uuid4

from redis.exceptions import WatchError

MAX_TURNS = 10


def new_state() -> dict[str, Any]:
    return {"schema_version": 2, "revision": 0, "context": {}, "plan": None, "shown": {}, "turns": [], "actions": {}}


def from_v1(value: dict[str, Any]) -> dict[str, Any]:
    """Hội thoại v1 (chưa có schema_version): giữ chuyến đi, thẻ đã xem và lịch sử chat; giá phải tra lại."""
    intent = value.get("intent") or {}
    party = intent.get("party") or {}
    state = new_state()
    state["context"] = {key: val for key, val in {
        "destination": intent.get("destination"), "start_date": intent.get("startDate"), "days": intent.get("days"),
        "adults": party.get("adults"), "children": party.get("children"), "origin": intent.get("origin"),
        "trip_budget_vnd": intent.get("budget"), "planning_consent": value.get("plan_consent")}.items()
        if val is not None}
    for item in (value.get("shown") or {}).get("items") or []:
        if str(item.get("ref", "")).startswith("#") and item.get("productId"):
            state["shown"]["p" + item["ref"][1:]] = {key: item.get(key) for key in ("productId", "name", "taxonomy")}
    history = value.get("conversation_history") or []
    state["turns"] = [{"message": user.get("content", ""), "answer": assistant.get("content", ""), "refs": []}
                      for user, assistant in zip(history[::2], history[1::2])][-MAX_TURNS:]
    return state


def commit(state: dict[str, Any], *, final: dict[str, Any], patch: dict[str, Any], memory: dict[str, Any],
           message: str, base_revision: int | None) -> dict[str, Any] | None:
    """Ghi một câu trả lời hợp lệ vào `state`; trả final kèm revision mới, hoặc None khi revision lệch."""
    if final["planEffect"] == "replace":
        if (base_revision or 0) != state["revision"]:
            return None
        state["revision"] += 1
        state["plan"] = deepcopy(final["itinerary"])
    final = {**final, "planRevision": state["revision"]}
    state["context"].update(patch)
    state["shown"].update(memory["shown"])
    state["actions"] = memory["actions"]
    state["turns"] = [*state["turns"], {"message": message, "answer": final["message"],
                                        "refs": list(memory["shown"])}][-MAX_TURNS:]
    return final


def _base(state: dict[str, Any]) -> dict[str, Any]:
    """Bản gốc khi chưa có bản lưu: hội thoại mới, hoặc bản chuyển từ v1 mà lượt đã nạp."""
    return deepcopy(state) if state else new_state()


def _claim(content_hash: str, run_id: str) -> dict[str, Any]:
    return {"status": "pending", "hash": content_hash, "run_id": run_id}


def _answer(claim: dict[str, Any] | None, content_hash: str) -> dict[str, Any] | None:
    """Kết quả khi lượt đã có khoá; None khi chưa có ai giữ."""
    if claim is None:
        return None
    if claim["hash"] != content_hash:
        return {"status": "conflict"}
    if claim["status"] == "final":
        return {"status": "replay", "run_id": claim["run_id"], "final": claim["final"]}
    return {"status": "in_progress"}


class InMemoryAssistantV2Store:
    """Bản trong tiến trình cho dev/test. Không có await giữa đọc và ghi nên mỗi thao tác là nguyên tử."""

    def __init__(self, *, ttl_seconds: int = 86_400, legacy_store=None, clock=monotonic):
        self.ttl_seconds, self.legacy_store, self.clock = ttl_seconds, legacy_store, clock
        self._states: dict[tuple[str, str], tuple[float, dict]] = {}
        self._claims: dict[tuple[str, str, str], tuple[float, dict]] = {}

    def _get(self, table: dict, key: tuple) -> dict | None:
        found = table.get(key)
        if found and self.clock() - found[0] <= self.ttl_seconds:
            return deepcopy(found[1])
        table.pop(key, None)
        return None

    async def load(self, owner: str, conversation_id: str) -> dict[str, Any] | None:
        state = self._get(self._states, (owner, conversation_id))
        if state is None and self.legacy_store is not None:
            legacy = await self.legacy_store.load(conversation_id, owner)
            state = from_v1(legacy) if legacy else None
        return state

    async def claim(self, owner: str, conversation_id: str, turn_id: str, content_hash: str) -> dict[str, Any]:
        key = (owner, conversation_id, turn_id)
        found = _answer(self._get(self._claims, key), content_hash)
        if found:
            return found
        run_id = uuid4().hex
        self._claims[key] = (self.clock(), _claim(content_hash, run_id))
        return {"status": "claimed", "run_id": run_id}

    async def finish(self, owner: str, conversation_id: str, turn_id: str, run_id: str, *,
                     state: dict[str, Any], **change) -> dict[str, Any] | None:
        """Ghi lượt; `state` là bản đã nạp ở đầu lượt, dùng khi chưa có bản lưu (hội thoại mới hoặc từ v1)."""
        claim = self._get(self._claims, (owner, conversation_id, turn_id))
        if not claim or claim["status"] != "pending" or claim["run_id"] != run_id:
            return None
        current = self._get(self._states, (owner, conversation_id)) or _base(state)
        final = commit(current, **change)
        if final is None:
            self._claims.pop((owner, conversation_id, turn_id), None)
            return None
        self._states[(owner, conversation_id)] = (self.clock(), current)
        self._claims[(owner, conversation_id, turn_id)] = (self.clock(), {**claim, "status": "final", "final": final})
        return final

    async def release(self, owner: str, conversation_id: str, turn_id: str, run_id: str) -> None:
        claim = self._get(self._claims, (owner, conversation_id, turn_id))
        if claim and claim["status"] == "pending" and claim["run_id"] == run_id:
            self._claims.pop((owner, conversation_id, turn_id), None)


_RELEASE = "if redis.call('GET', KEYS[1]) == ARGV[1] then return redis.call('DEL', KEYS[1]) end return 0"


class RedisAssistantV2Store:
    """Bản dùng chung giữa các worker: khoá lượt bằng SET NX, ghi lượt bằng WATCH/MULTI."""

    def __init__(self, client, *, ttl_seconds: int = 86_400, legacy_store=None):
        self.client, self.ttl_seconds, self.legacy_store = client, ttl_seconds, legacy_store

    @staticmethod
    def _key(kind: str, *parts: str) -> str:
        return f"assistant:v2:{kind}:" + sha256(json.dumps(parts).encode()).hexdigest()

    async def load(self, owner: str, conversation_id: str) -> dict[str, Any] | None:
        raw = await self.client.get(self._key("conversation", owner, conversation_id))
        if raw is not None:
            return json.loads(raw)
        if self.legacy_store is None:
            return None
        legacy = await self.legacy_store.load(conversation_id, owner)
        return from_v1(legacy) if legacy else None

    async def claim(self, owner: str, conversation_id: str, turn_id: str, content_hash: str) -> dict[str, Any]:
        key = self._key("turn", owner, conversation_id, turn_id)
        run_id = uuid4().hex
        if await self.client.set(key, json.dumps(_claim(content_hash, run_id)), nx=True, ex=self.ttl_seconds):
            return {"status": "claimed", "run_id": run_id}
        raw = await self.client.get(key)
        return _answer(json.loads(raw) if raw else None, content_hash) or {"status": "in_progress"}

    async def finish(self, owner: str, conversation_id: str, turn_id: str, run_id: str, *,
                     state: dict[str, Any], **change) -> dict[str, Any] | None:
        state_key = self._key("conversation", owner, conversation_id)
        claim_key = self._key("turn", owner, conversation_id, turn_id)
        async with self.client.pipeline(transaction=True) as pipe:
            while True:
                try:
                    await pipe.watch(state_key, claim_key)
                    raw_claim, raw_state = await pipe.get(claim_key), await pipe.get(state_key)
                    claim = json.loads(raw_claim) if raw_claim else None
                    if not claim or claim["status"] != "pending" or claim["run_id"] != run_id:
                        return None
                    current = json.loads(raw_state) if raw_state else _base(state)
                    final = commit(current, **change)
                    pipe.multi()
                    if final is None:
                        pipe.delete(claim_key)
                    else:
                        pipe.set(state_key, json.dumps(current, ensure_ascii=False), ex=self.ttl_seconds)
                        pipe.set(claim_key, json.dumps({**claim, "status": "final", "final": final},
                                                       ensure_ascii=False), ex=self.ttl_seconds)
                    await pipe.execute()
                    return final
                except WatchError:
                    continue

    async def release(self, owner: str, conversation_id: str, turn_id: str, run_id: str) -> None:
        key = self._key("turn", owner, conversation_id, turn_id)
        raw = await self.client.get(key)
        claim = json.loads(raw) if raw else None
        if claim and claim["status"] == "pending" and claim["run_id"] == run_id:
            await self.client.eval(_RELEASE, 1, key, raw)
