"""Lưới snapshot hành vi của Itinerary Agent (plan `docs/plan/2026-10-11-refactor-agent-giu-hanh-vi.md`).

Chạy các hội thoại trong `scenarios.json` qua đúng graph mà runtime dùng (`RuntimeAgentDependencies`), với:
- tool (Search, Recommendation, Similar, Catalog) phát lại từ `tools.json.gz`, ghi từ chế độ `inprocess` trên dữ liệu thật
  (Postgres + Weaviate local), khoá theo tên tool và tham số;
- LLM phát lại từ `cassette.json`, khoá theo hash của schema và toàn bộ payload gửi LLM;
- "hôm nay" cố định `FROZEN_TODAY` và `conversationId` tất định.

Phát lại không cần mạng hay DB, nên chạy được trong CI và không lệch khi catalog được nạp lại. Payload gửi LLM hoặc tham số
gọi tool đổi thì không có bản ghi: lượt đó ghi vào `cassetteMiss`/`toolMiss` và test fail. Vì vậy lưới bắt cả thay đổi ở
câu trả lời lẫn thay đổi ở đầu vào LLM và tool.

Ghi lại (gọi `inprocess` và LLM thật theo `.env`; cần `docker compose up -d postgres weaviate`), chỉ khi chủ ý đổi prompt,
hành vi hoặc dữ liệu:

    .venv/bin/python -m src.backend.tests.unit.agents.behavior_snapshot.record
"""
from __future__ import annotations

import asyncio
import contextvars
import gzip
import hashlib
import json
import re
from contextlib import contextmanager
from datetime import date, datetime, time, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest import mock

from src.backend.app.agents import nodes
from src.backend.app.agents.runtime_dependencies import RuntimeAgentDependencies
from src.backend.app.agents.steps import classification, fares
from src.backend.app.agents.tools.itinerary_gateway import ItineraryToolGateway
from src.backend.app.application.itinerary.use_cases import PlanItinerary
from src.backend.app.application.ports.itinerary_tools import ToolError
from src.backend.app.infrastructure.persistence.conversation_store import InMemoryConversationStore

HERE = Path(__file__).resolve().parent
SCENARIOS = HERE / "scenarios.json"
CASSETTE = HERE / "cassette.json"
TOOLS = HERE / "tools.json.gz"
SNAPSHOT = HERE / "snapshot.json"

#: Ngày ghi snapshot. Ngày đi trong kịch bản tính theo ngày này. Engine `inprocess` lọc theo ngày thật, nên ghi lại vào
#: ngày khác thì đổi ngày này và ngày trong `scenarios.json` cho khớp.
FROZEN_TODAY = date(2026, 10, 11)
#: 09:00 giờ Việt Nam: tránh khoảng 0h–7h mà ngày UTC lệch ngày Việt Nam.
FROZEN_NOW = datetime.combine(FROZEN_TODAY, time(2, 0), tzinfo=timezone.utc)
LLM_TIMEOUT_SECONDS = 120.0
TOOL_TIMEOUT_SECONDS = 10.0
#: Số kịch bản chạy song song khi ghi bằng LLM thật; mỗi kịch bản có store và uuid riêng nên thứ tự không ảnh hưởng.
CONCURRENCY = 6
#: Bộ đếm uuid của kịch bản đang chạy (mỗi task asyncio một bản).
_UUIDS: contextvars.ContextVar[list[int]] = contextvars.ContextVar("snapshot_uuids")
#: Lời gọi LLM của kịch bản đang chạy; dùng chung một danh sách thì các kịch bản song song trộn vào nhau.
_CALLS: contextvars.ContextVar[list[str]] = contextvars.ContextVar("snapshot_llm_calls")
#: Lời gọi tool của kịch bản đang chạy.
_TOOL_CALLS: contextvars.ContextVar[list[str]] = contextvars.ContextVar("snapshot_tool_calls")
#: Khoá chỉ đo thời gian: bỏ khỏi snapshot vì đổi theo máy.
_TIMING_KEY = re.compile(r"(latency|duration|elapsed)(_?ms|_?seconds)?$|^ms$", re.IGNORECASE)


class CassetteMiss(RuntimeError):
    """Payload gửi LLM không có trong cassette: hành vi hoặc đầu vào LLM đã đổi."""


def _message_text(message: Any) -> list[str]:
    if isinstance(message, (tuple, list)) and len(message) == 2:
        return [str(message[0]), str(message[1])]
    return [str(getattr(message, "type", type(message).__name__)), str(getattr(message, "content", message))]


def _prompt_key(kind: str, extra: Any, prompt: Any) -> str:
    messages = prompt if isinstance(prompt, list) else [prompt]
    payload = json.dumps([kind, extra, [_message_text(m) for m in messages]], ensure_ascii=False, sort_keys=True,
                         default=str)
    return f"{kind}:{hashlib.sha256(payload.encode()).hexdigest()[:24]}"


class CassetteLlm:
    """Chat model giả: phát lại câu trả lời đã ghi; `inner` khác None thì gọi model thật và ghi lại.

    Hiện thực đúng hai cách agent gọi LLM: `with_structured_output(schema).ainvoke/invoke` và
    `bind_tools(definitions, tool_choice).ainvoke`.
    """

    def __init__(self, records: dict[str, Any], inner: Any | None = None):
        self.records = records
        self.inner = inner

    def _lookup(self, key: str) -> Any:
        _CALLS.get().append(key)
        if key not in self.records:
            raise CassetteMiss(key)
        return self.records[key]

    def with_structured_output(self, schema, *args, **kwargs):
        name = schema.__name__
        live = self.inner.with_structured_output(schema, *args, **kwargs) if self.inner is not None else None

        async def ainvoke(prompt, *a, **k):
            key = _prompt_key(f"structured:{name}", None, prompt)
            if live is not None and key not in self.records:
                result = await live.ainvoke(prompt, *a, **k)
                self.records[key] = result.model_dump(mode="json") if hasattr(result, "model_dump") else result
            return schema.model_validate(self._lookup(key))

        def invoke(prompt, *a, **k):
            key = _prompt_key(f"structured:{name}", None, prompt)
            if live is not None and key not in self.records:
                result = live.invoke(prompt, *a, **k)
                self.records[key] = result.model_dump(mode="json") if hasattr(result, "model_dump") else result
            return schema.model_validate(self._lookup(key))

        return SimpleNamespace(ainvoke=ainvoke, invoke=invoke)

    def bind_tools(self, definitions, tool_choice=None, **kwargs):
        extra = {"tools": definitions, "tool_choice": tool_choice}
        live = self.inner.bind_tools(definitions, tool_choice=tool_choice, **kwargs) if self.inner is not None else None

        async def ainvoke(prompt, *a, **k):
            key = _prompt_key("tools", extra, prompt)
            if live is not None and key not in self.records:
                response = await live.ainvoke(prompt, *a, **k)
                self.records[key] = {"tool_calls": [dict(call) for call in response.tool_calls]}
            return SimpleNamespace(tool_calls=json.loads(json.dumps(self._lookup(key)["tool_calls"])))

        return SimpleNamespace(ainvoke=ainvoke)


#: Tool mà agent gọi qua `ItineraryToolGateway` (port Search, Recommendation, Similar, Catalog).
TOOL_METHODS = ("search_products", "get_recommendations", "get_similar_products", "get_product_detail",
                "list_products", "list_destinations")


def _tool_key(method: str, args: tuple) -> str:
    payload = json.dumps([method, list(args)], ensure_ascii=False, sort_keys=True, default=str)
    return f"{method}:{hashlib.sha256(payload.encode()).hexdigest()[:24]}"


class ToolCassette:
    """Tool giả: phát lại kết quả đã ghi; `inner` khác None (adapter `inprocess`) thì gọi thật và ghi lại.

    Lỗi `ToolError` cũng được ghi và phát lại. Không có bản ghi thì trả `ToolError("CASSETTE_MISS")`: agent xử lý như lỗi
    tool, câu trả lời lệch snapshot và lượt đó có `toolMiss`.
    """
    supports_catalog = True
    supports_similar = True

    def __init__(self, records: dict[str, Any], inner: Any | None = None):
        self.records = records
        self.inner = inner
        for method in TOOL_METHODS:
            setattr(self, method, self._tool(method))

    def _tool(self, method: str):
        async def call(*args, **kwargs):
            if kwargs.get("authorization") is not None:
                raise AssertionError("snapshot chỉ chạy khách chưa đăng nhập")
            key = _tool_key(method, args)
            _TOOL_CALLS.get().append(key)
            if self.inner is not None and key not in self.records:
                try:
                    self.records[key] = {"result": await getattr(self.inner, method)(*args, **kwargs)}
                except ToolError as exc:
                    self.records[key] = {"error": {"code": exc.code, "retryable": exc.retryable,
                                                   "http_status": exc.http_status, "reason": exc.reason}}
            record = self.records.get(key)
            if record is None:
                raise ToolError("CASSETTE_MISS")
            if "error" in record:
                raise ToolError(**record["error"])
            return json.loads(json.dumps(record["result"]))
        return call


def _pack(value: Any, products: dict[str, Any]) -> Any:
    """Sản phẩm (dict có `productId`) lặp lại ở nhiều lời gọi tool chỉ lưu một lần, tham chiếu bằng hash."""
    if isinstance(value, dict):
        packed = {k: _pack(v, products) for k, v in value.items()}
        if "productId" in value and len(value) > 3:
            ref = hashlib.sha256(json.dumps(packed, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:20]
            products[ref] = packed
            return {"$product": ref}
        return packed
    if isinstance(value, list):
        return [_pack(v, products) for v in value]
    return value


def _unpack(value: Any, products: dict[str, Any]) -> Any:
    if isinstance(value, dict):
        if set(value) == {"$product"}:
            return _unpack(products[value["$product"]], products)
        return {k: _unpack(v, products) for k, v in value.items()}
    if isinstance(value, list):
        return [_unpack(v, products) for v in value]
    return value


def load_tools() -> dict[str, Any]:
    if not TOOLS.exists():
        return {}
    data = json.loads(gzip.decompress(TOOLS.read_bytes()).decode("utf-8"))
    return {key: _unpack(record, data["products"]) for key, record in data["calls"].items()}


def dump_tools(records: dict[str, Any]) -> None:
    products: dict[str, Any] = {}
    calls = {key: _pack(record, products) for key, record in sorted(records.items())}
    raw = json.dumps({"calls": calls, "products": dict(sorted(products.items()))}, ensure_ascii=False,
                     sort_keys=True, separators=(",", ":"))
    TOOLS.write_bytes(gzip.compress(raw.encode("utf-8"), mtime=0))


class _FrozenDatetime(datetime):
    @classmethod
    def now(cls, tz=None):
        return FROZEN_NOW.astimezone(tz) if tz is not None else FROZEN_NOW.replace(tzinfo=None)


@contextmanager
def frozen_world():
    """Cố định "hôm nay" ở hai chỗ agent đọc giờ (`classification.vietnam_today`, `fares.answer`) và uuid hội thoại.

    uuid đánh số theo kịch bản (`_UUIDS`), nên chạy song song hay tuần tự đều ra cùng `conversationId`.
    """
    def next_uuid():
        scenario = _UUIDS.get()
        scenario[1] += 1
        return f"00000000-0000-4000-{scenario[0]:04d}-{scenario[1]:012d}"

    with mock.patch.object(classification, "datetime", _FrozenDatetime), \
            mock.patch.object(fares, "datetime", _FrozenDatetime), \
            mock.patch.object(nodes, "uuid", SimpleNamespace(uuid4=next_uuid)):
        yield


def scrub(value: Any) -> Any:
    """Bỏ khoá đo thời gian; giữ mọi thứ khác nguyên văn."""
    if isinstance(value, dict):
        return {k: scrub(v) for k, v in value.items() if not _TIMING_KEY.search(str(k))}
    if isinstance(value, list):
        return [scrub(v) for v in value]
    return value


def _request(turn: Any, conversation_id: str | None) -> dict[str, Any]:
    request = {"message": turn} if isinstance(turn, str) else dict(turn)
    if conversation_id:
        request["conversationId"] = conversation_id
    return request


async def run_scenario(scenario: dict[str, Any], llm: CassetteLlm, tools: ToolCassette) -> list[dict[str, Any]]:
    """Một hội thoại; mỗi lượt ghi request, HTTP status, node đã đi, response, lời gọi LLM, tool và state đã lưu."""
    _UUIDS.set([scenario["index"], 0])
    calls, tool_calls = _CALLS.get(), _TOOL_CALLS.get()
    store = InMemoryConversationStore()
    gateway = ItineraryToolGateway(tools, tools, tools, similar=tools)
    runtime = RuntimeAgentDependencies(gateway, store, llm, None, owner=None, archive=None,
                                       tool_timeout_seconds=TOOL_TIMEOUT_SECONDS,
                                       llm_timeout_seconds=LLM_TIMEOUT_SECONDS)
    planner = runtime.planner()
    conversation_id = None
    turns = []
    for index, turn in enumerate(scenario["turns"], start=1):
        request = _request(turn, conversation_id)
        start, tool_start = len(calls), len(tool_calls)
        state = await planner.ainvoke(PlanItinerary.inputs(request, f"{scenario['id']}-{index}"))
        conversation_id = state.get("conversation_id") or conversation_id
        stored = await store.load(conversation_id, runtime.owner) if conversation_id else None
        turns.append(scrub({
            "request": request,
            "httpStatus": state.get("http_status"),
            "nodes": [item["node"] for item in state.get("events", [])],
            "events": [{"node": item["node"], "message": item.get("message")} for item in state.get("events", [])],
            "llmCalls": calls[start:],
            "cassetteMiss": [key for key in calls[start:] if key not in llm.records],
            # Search và tra vé chạy song song trong `tool`: thứ tự theo độ trễ thật, không phải hành vi.
            "toolCalls": sorted(tool_calls[tool_start:]),
            "toolMiss": [key for key in tool_calls[tool_start:] if key not in tools.records],
            "response": state.get("response"),
            "stored": stored,
        }))
    return turns


def load_json(path: Path, default: Any) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def dump_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")


async def run_all(llm: CassetteLlm, tools: ToolCassette,
                  only: set[str] | None = None) -> dict[str, list[dict[str, Any]]]:
    scenarios = [{**scenario, "index": index} for index, scenario in enumerate(load_json(SCENARIOS, []), start=1)
                 if not only or scenario["id"] in only]
    gate = asyncio.Semaphore(CONCURRENCY)

    async def one(scenario):
        async with gate:
            _CALLS.set([])
            _TOOL_CALLS.set([])
            return scenario["id"], await run_scenario(scenario, llm, tools)

    with frozen_world():
        done = await asyncio.gather(*(one(scenario) for scenario in scenarios))
    return dict(done)


def replay(only: set[str] | None = None) -> dict[str, list[dict[str, Any]]]:
    return asyncio.run(run_all(CassetteLlm(load_json(CASSETTE, {})), ToolCassette(load_tools()), only))
