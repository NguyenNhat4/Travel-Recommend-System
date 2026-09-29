"""Golden dataset runner cho Itinerary Agent.

Chấm theo docs/prd/test-plan.md §2.4: Tool Calling Accuracy ≥ 95%, Grounding Rate 100%,
Structured Output Integrity 100%. Dataset: src/evaluation/datasets/itinerary_agent_golden.yaml.
Chi tiết luật chấm và cách chạy: src/evaluation/agent/README.md.

Cần trước khi chạy:
  - `docker compose up -d --wait postgres` (đã seed)
  - Backend đã nạp RecSys, chạy `ITINERARY_DATA_MODE=inprocess` (hoặc `http`; không để `fixture`, vì
    `productCount` của biên bản lấy từ `/assistant/status` của backend)
  - `.env` có DATABASE_URL (hoặc SEED_DATABASE_URL) đọc được `cdp.products`, và key LLM thật

Dựng graph **in-process** (không đi qua route FastAPI) để đọc được `tool_plan`, `intent`,
`candidates`, `events` — HTTP client chỉ dùng để agent tự gọi Search/Recommendation/ProductDetail/
destinations của backend đang chạy, giống cách `_itinerary_runtime` ở `src/backend/app/main.py`
dựng dependency ở mode `http`. Runner luôn đi đường HTTP này, bất kể mode của backend.

Usage:
    .venv/bin/python -m src.evaluation.agent.golden \\
        --dataset src/evaluation/datasets/itinerary_agent_golden.yaml \\
        --api-base-url http://127.0.0.1:8000 [--only G-051,G-062] [--sweep] [--repeat N] \\
        [--trace-project claude-golden]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import statistics
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx
import yaml

from src.backend.app.agents.runtime_dependencies import RuntimeAgentDependencies
from src.backend.app.agents.steps.classification import vietnam_today
from src.backend.app.agents.tools.itinerary_gateway import ItineraryToolGateway
from src.backend.app.application.itinerary.contracts import valid
from src.backend.app.core.config import get_settings
from src.backend.app.domain.itinerary.planning import (
    MAX_ACTIVITIES_PER_DAY, SLOT_TAXONOMIES, STAY_TAXONOMY, _stay_order,
)
from src.backend.app.infrastructure.clients.itinerary_http_clients import ItineraryHttpClients
from src.backend.app.infrastructure.llm import build_chat_model
from src.backend.app.infrastructure.persistence.conversation_store import InMemoryConversationStore
from src.evaluation.agent.grounding import check_product_grounding, products_in_response

REPO_ROOT = Path(__file__).resolve().parents[3]
BOOKING_CLAIM_PHRASES = ("đã đặt", "đã thanh toán", "đặt thành công", "booking confirmed")
SECRET_PATTERNS = [
    re.compile(pattern, re.IGNORECASE) for pattern in (
        r"sk-[a-zA-Z0-9]{10,}", r"bearer\s+[a-zA-Z0-9._-]{10,}", r"AIzaSy[a-zA-Z0-9_-]{10,}",
    )
]


# ----------------------------------------------------------------------------------------- dates

# `{today}`, `{today+7}`, `{today-1}` → dd/mm/yyyy (câu người dùng gõ); thêm `:iso` → yyyy-mm-dd (để so `intent.startDate`).
# Runner đổi lúc chạy theo ngày ở Việt Nam, cùng nguồn với mốc `today` của agent (`vietnam_today`), nên ngày luôn nằm
# gần hôm nay và trong cửa sổ đặt chỗ 30 ngày của catalog mới nạp; câu gửi đi là ngày tường minh, LLM không phải đoán.
DATE_PLACEHOLDER = re.compile(r"\{today([+-]\d+)?(:iso)?\}")


def resolve_dates(value: Any, today: date) -> Any:
    """Thay placeholder ngày trong chuỗi, kể cả lồng trong dict/list (dùng cho message và expect)."""
    if isinstance(value, str):
        def replace(match: re.Match[str]) -> str:
            day = today + timedelta(days=int(match.group(1) or 0))
            return day.isoformat() if match.group(2) else day.strftime("%d/%m/%Y")
        return DATE_PLACEHOLDER.sub(replace, value)
    if isinstance(value, dict):
        return {key: resolve_dates(item, today) for key, item in value.items()}
    if isinstance(value, list):
        return [resolve_dates(item, today) for item in value]
    return value


# --------------------------------------------------------------------------------------- dataset


@dataclass
class Turn:
    message: str
    expect: dict[str, Any] = field(default_factory=dict)
    language: str | None = None          # context.language của request; None = backend tự chọn (vi)
    conversation_id: str | None = None   # ép conversationId cho lượt này, ví dụ id không tồn tại


# Runner từng bỏ qua khoá lạ, nên gõ nhầm tên khoá làm case PASS mà không kiểm gì. Giờ nạp dataset
# sẽ báo lỗi ngay; thêm khoá mới thì thêm tên vào đây cùng lúc với nhánh kiểm trong dataset_findings.
TURN_KEYS = {"message", "expect", "language", "conversationId"}
EXPECT_KEYS = {
    "httpStatus", "status", "errorCode", "intent", "missingFieldsInclude", "toolCalled", "nodesInclude",
    "nodesExclude", "forbiddenText", "excludeProductsFromTurn", "minActivities", "hasStay", "warningsExclude",
    "toolsInclude",
}


@dataclass
class Case:
    id: str
    category: str
    fr: list[str]
    turns: list[Turn]


def load_dataset(path: Path) -> list[Case]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    if not isinstance(raw, list) or not raw:
        raise ValueError(f"{path}: dataset rỗng hoặc không phải danh sách")
    cases: list[Case] = []
    seen_ids: set[str] = set()
    for item in raw:
        case_id = item["id"]
        if case_id in seen_ids:
            raise ValueError(f"Trùng id case: {case_id}")
        seen_ids.add(case_id)
        turns = []
        for t in item["turns"]:
            unknown = (set(t) - TURN_KEYS) | (set(t.get("expect") or {}) - EXPECT_KEYS)
            if unknown:
                raise ValueError(f"{case_id}: khoá không được hỗ trợ {sorted(unknown)}")
            turns.append(Turn(message=t["message"], expect=t.get("expect") or {},
                              language=t.get("language"), conversation_id=t.get("conversationId")))
        if not turns:
            raise ValueError(f"{case_id}: không có turn nào")
        cases.append(Case(id=case_id, category=item["category"], fr=list(item.get("fr", [])), turns=turns))
    return cases


# ------------------------------------------------------------------------------------------ runtime


def build_runtime(http_client: httpx.AsyncClient):
    settings = get_settings()
    llm = build_chat_model(settings)
    if llm is None:
        raise RuntimeError("Không dựng được LLM (build_chat_model trả None) — kiểm tra .env, ITINERARY_LLM_MODEL/key.")
    clients = ItineraryHttpClients(http_client)
    catalog = clients if getattr(clients, "supports_catalog", False) else None
    gateway = ItineraryToolGateway(clients, clients, catalog, recommendation_authorization=None, similar=clients)
    store = InMemoryConversationStore(ttl_seconds=settings.itinerary_conversation_ttl_seconds)
    runtime = RuntimeAgentDependencies(
        gateway, store, llm, authorization=None,
        tool_timeout_seconds=settings.itinerary_tool_timeout_seconds,
        llm_timeout_seconds=settings.itinerary_llm_timeout_seconds,
    )
    return runtime, settings


def conversation_of(response: dict[str, Any]) -> str | None:
    """`conversationId` để gửi ở lượt sau, giống frontend: response 200 để ở cấp ngoài cùng, lỗi có
    thể tiếp tục (ví dụ `UNSUPPORTED_DESTINATION`) để trong `error.details`."""
    details = (response.get("error") or {}).get("details") or {}
    return response.get("conversationId") or details.get("conversationId")


def enable_tracing(settings: Any, project: str) -> None:
    """Gửi trace của lượt chạy lên LangSmith project `project`, dùng key trong Settings.

    Runner không đi qua `lifespan` của FastAPI nên `_forward_langsmith_env` (main.py) không chạy; nếu không
    đặt biến ở đây thì không lượt golden nào có trace. Phải gọi trước lời gọi LangChain đầu tiên: SDK
    cache cờ bật/tắt tracing.
    """
    if not settings.langsmith_api_key:
        raise RuntimeError("--trace-project cần LANGSMITH_API_KEY trong .env")
    os.environ["LANGSMITH_TRACING"] = "true"
    os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key
    os.environ["LANGSMITH_ENDPOINT"] = settings.langsmith_endpoint
    os.environ["LANGSMITH_PROJECT"] = project


def trace_config(case: "Case", turn_index: int, message: str, request_id: str) -> dict[str, Any]:
    """Tên, tag và metadata để lọc từng lượt golden trong LangSmith; vô hại khi tracing tắt."""
    label = " ".join(message.split())[:60]
    return {
        "run_name": f"{case.id}#{turn_index} {label}",
        "tags": ["golden", case.id, case.category],
        "metadata": {"case_id": case.id, "turn": turn_index, "category": case.category,
                     "fr": case.fr, "request_id": request_id},
    }


async def run_turn(planner, message: str, conversation_id: str | None, timeout: float,
                   config: dict[str, Any] | None = None, request_id: str | None = None,
                   language: str | None = None) -> dict[str, Any]:
    request_id = request_id or uuid.uuid4().hex
    inputs = {
        "query": message, "conversation_id": conversation_id, "intent_override": {},
        "language": language, "request_id": request_id,
    }
    config = {**(config or {}), "configurable": {"thread_id": request_id}}
    return await asyncio.wait_for(planner.ainvoke(inputs, config=config), timeout=timeout)


# ------------------------------------------------------------------------------------------ grading
#
# Bốn nhóm quy tắc (mục A/B/C/D bàn với người dùng trước khi code):
#   A — gate cứng, áp dụng cho MỌI lượt, không cần dataset khai báo.
#   B — cấu trúc lịch trình khi status=COMPLETED, suy trực tiếp từ response.
#   C — kỳ vọng tính từ `candidates` nội bộ (chỉ có được vì graph chạy in-process).
#   D — kỳ vọng do case tự khai báo trong `expect`.


def _text_blob(response: dict[str, Any]) -> str:
    return json.dumps(response, ensure_ascii=False)


def gate_schema(response: dict[str, Any]) -> list[str]:
    name = "ErrorResponse" if "error" in response else "ItineraryResponse"
    return [] if valid(name, response) else [f"response không khớp schema {name}"]


def gate_grounding(response: dict[str, Any], dsn: str | None) -> tuple[list[str], int]:
    failures: list[str] = []
    items = products_in_response(response)
    destination = (response.get("intent") or {}).get("destination")
    for where, product in items:
        error = check_product_grounding(where, product, dsn)
        if error:
            failures.append(error)
        elif destination and product.get("destination") != destination:
            failures.append(
                f"{where} {product['productId']} sai điểm đến: mong {destination!r}, có {product['destination']!r}"
            )
    return failures, len(items)


def gate_secrets(response: dict[str, Any], settings: Any) -> list[str]:
    blob = _text_blob(response)
    failures = [f"lộ chuỗi giống secret khớp mẫu {p.pattern}" for p in SECRET_PATTERNS if p.search(blob)]
    for name, value in (
        ("OPENAI_API_KEY", settings.openai_api_key), ("GEMINI_API_KEY", settings.gemini_api_key),
        ("ANTHROPIC_API_KEY", settings.anthropic_api_key), ("LANGSMITH_API_KEY", settings.langsmith_api_key),
    ):
        if value and value in blob:
            failures.append(f"lộ {name} trong response")
    return failures


def gate_no_booking_claim(response: dict[str, Any]) -> list[str]:
    blob = _text_blob(response).lower()
    return [f"tuyên bố đã thực hiện hành động: chứa {phrase!r}" for phrase in BOOKING_CLAIM_PHRASES if phrase in blob]


def gate_no_tool_before_info(response: dict[str, Any], events: list[dict[str, Any]]) -> list[str]:
    if response.get("status") != "NEEDS_CLARIFICATION" or not (response.get("missingFields") or []):
        return []
    if "tool" in {e.get("node") for e in events}:
        return ["gọi tool trước khi đủ destination/days (missingFields không rỗng)"]
    return []


def _product_ids(response: dict[str, Any], role: str) -> set[str]:
    itinerary = response.get("itinerary") or {}
    ids: set[str] = set()
    if stay := (itinerary.get("stay") or {}).get("product"):
        ids.add(stay["productId"])
    if role == "stay":
        return ids
    for day in itinerary.get("days", []):
        for slot in day.get("slots", []):
            if product := slot.get("product"):
                ids.add(product["productId"])
    return ids


def schedule_findings(response: dict[str, Any], candidates: dict[str, dict[str, Any]]) -> list[str]:
    """Nhóm B (cấu trúc) + C1 (chỗ ở rẻ nhất) — chỉ áp dụng khi status=COMPLETED."""
    if response.get("status") != "COMPLETED":
        return []
    failures: list[str] = []
    itinerary = response.get("itinerary") or {}
    days = itinerary.get("days") or []
    intent_days = (response.get("intent") or {}).get("days")
    if intent_days is not None and len(days) != intent_days:
        failures.append(f"itinerary.days có {len(days)} ngày, khác intent.days={intent_days}")

    seen_ids: set[str] = set()
    stay = (itinerary.get("stay") or {}).get("product")
    if stay:
        if stay.get("taxonomy") != STAY_TAXONOMY:
            failures.append(f"stay taxonomy={stay.get('taxonomy')!r}, phải là {STAY_TAXONOMY!r}")
        seen_ids.add(stay["productId"])
        hotel_candidates = [p for p in candidates.values() if p.get("taxonomy") == STAY_TAXONOMY]
        if hotel_candidates:
            cheapest = min(hotel_candidates, key=_stay_order)
            if stay["productId"] != cheapest["productId"]:
                failures.append(f"stay={stay['productId']} nhưng hotel rẻ nhất là {cheapest['productId']}")

    for day in days:
        slots = day.get("slots") or []
        products = [s["product"] for s in slots if s.get("product")]
        if not products:
            warnings = response.get("warnings") or []
            if not any(w.get("code") == "DAY_WITHOUT_PRODUCTS" for w in warnings):
                failures.append(f"ngày {day.get('day')} không có sản phẩm nhưng thiếu warning DAY_WITHOUT_PRODUCTS")
            continue
        if len(products) > MAX_ACTIVITIES_PER_DAY:
            failures.append(f"ngày {day.get('day')} có {len(products)} hoạt động, vượt trần {MAX_ACTIVITIES_PER_DAY}")
        for product in products:
            if product["taxonomy"] not in SLOT_TAXONOMIES and product["taxonomy"] != STAY_TAXONOMY:
                failures.append(f"slot ngày {day.get('day')} taxonomy={product['taxonomy']!r} không hợp lệ")
            if product["productId"] in seen_ids:
                failures.append(f"productId {product['productId']} lặp lại trong itinerary")
            seen_ids.add(product["productId"])
        times = [s.get("time") for s in slots if s.get("product")]
        if times and times[0] != "MORNING":
            failures.append(f"ngày {day.get('day')} hoạt động đầu ở {times[0]!r}, phải là MORNING")
        if len(times) >= 2 and times[1] != "AFTERNOON":
            failures.append(f"ngày {day.get('day')} hoạt động thứ hai ở {times[1]!r}, phải là AFTERNOON")
    return failures


def expected_tool_call(response: dict[str, Any]) -> bool | None:
    """Suy quyết định gọi tool đúng ra sao từ chính response — dùng cho Tool Calling Accuracy.

    None nghĩa là không đủ căn cứ để khẳng định (ví dụ constraint_clarification: tool đã chạy
    nhưng NEEDS_CLARIFICATION), loại khỏi mẫu số thay vì đoán.
    """
    status = response.get("status")
    if status == "NEEDS_CLARIFICATION":
        return False if (response.get("missingFields") or []) else None
    if status in {"COMPLETED", "FALLBACK", "NO_RESULTS"}:
        return True
    code = (response.get("error") or {}).get("code")
    if code == "UNSUPPORTED_DESTINATION":
        return True
    if code == "VALIDATION_ERROR":
        return False
    return None


def _get_path(obj: dict[str, Any], path: str) -> tuple[Any, bool]:
    node: Any = obj
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            return None, False
        node = node[part]
    return node, True


def dataset_findings(
    response: dict[str, Any], http_status: int, events: list[dict[str, Any]],
    expect: dict[str, Any], previous_products: dict[int, dict[str, set[str]]],
    planned_tools: set[str] = frozenset(),
) -> list[str]:
    """`planned_tools`: tên tool trong `tool_plan` cuối của lượt (sau `validated_plan`, lời gọi bị bỏ không có mặt)."""
    failures: list[str] = []
    if "httpStatus" in expect and http_status != expect["httpStatus"]:
        failures.append(f"httpStatus={http_status}, kỳ vọng {expect['httpStatus']}")
    if "status" in expect and response.get("status") not in expect["status"]:
        failures.append(f"status={response.get('status')!r}, kỳ vọng một trong {expect['status']}")
    if "errorCode" in expect:
        code = (response.get("error") or {}).get("code")
        if code != expect["errorCode"]:
            failures.append(f"errorCode={code!r}, kỳ vọng {expect['errorCode']!r}")
    if "intent" in expect:
        intent = response.get("intent") or response.get("knownIntent") or {}
        for path, expected_value in expect["intent"].items():
            value, found = _get_path(intent, path)
            if not found:
                failures.append(f"intent.{path} không có (kỳ vọng {expected_value!r})")
            elif value != expected_value:
                failures.append(f"intent.{path}={value!r}, kỳ vọng {expected_value!r}")
    if "missingFieldsInclude" in expect:
        missing = set(response.get("missingFields") or [])
        for name in expect["missingFieldsInclude"]:
            if name not in missing:
                failures.append(f"missingFields thiếu {name!r}, có {sorted(missing)}")
    nodes = {e.get("node") for e in events}
    if "toolCalled" in expect and ("tool" in nodes) != expect["toolCalled"]:
        failures.append(f"tool {'không' if expect['toolCalled'] else 'có'} chạy, mong ngược lại")
    for name in expect.get("nodesInclude", []):
        if name not in nodes:
            failures.append(f"thiếu node {name!r} trong trace")
    for name in expect.get("nodesExclude", []):
        if name in nodes:
            failures.append(f"node {name!r} không được chạy nhưng có trong trace")
    for name in expect.get("toolsInclude", []):
        if name not in planned_tools:
            failures.append(f"tool plan thiếu {name!r}, có {sorted(planned_tools)}")
    if "forbiddenText" in expect:
        blob = _text_blob(response).lower()
        for phrase in expect["forbiddenText"]:
            if str(phrase).lower() in blob:
                failures.append(f"response chứa chuỗi cấm {phrase!r}")
    if "excludeProductsFromTurn" in expect:
        spec = expect["excludeProductsFromTurn"]
        prior = previous_products.get(spec["turn"], {}).get(spec["role"], set())
        overlap = prior & _product_ids(response, spec["role"])
        if overlap:
            failures.append(f"sản phẩm lượt {spec['turn']} ({spec['role']}) vẫn xuất hiện lại: {sorted(overlap)}")
    itinerary = response.get("itinerary") or {}
    if "minActivities" in expect:
        count = sum(1 for day in itinerary.get("days", []) for slot in day.get("slots", []) if slot.get("product"))
        if count < expect["minActivities"]:
            failures.append(f"lịch có {count} hoạt động, kỳ vọng ít nhất {expect['minActivities']}")
    if "hasStay" in expect:
        has_stay = bool((itinerary.get("stay") or {}).get("product"))
        if has_stay != expect["hasStay"]:
            failures.append(f"lịch {'có' if has_stay else 'không có'} chỗ ở, mong ngược lại")
    for code in expect.get("warningsExclude", []):
        if any(w.get("code") == code for w in response.get("warnings") or []):
            failures.append(f"response có warning {code!r} không được phép")
    return failures


# -------------------------------------------------------------------------------------------- run


@dataclass
class TurnResult:
    case_id: str
    turn_index: int
    message: str
    http_status: int
    status: str | None
    latency_ms: int
    grounding_checked: int
    tool_called: bool
    tool_expected: bool | None
    findings: list[str]

    @property
    def passed(self) -> bool:
        return not self.findings


async def run_case(
    case: Case, planner, dsn: str | None, settings: Any, timeout: float,
) -> list[TurnResult]:
    results: list[TurnResult] = []
    conversation_id: str | None = None
    previous_products: dict[int, dict[str, set[str]]] = {}
    today = vietnam_today()
    for index, turn in enumerate(case.turns, start=1):
        message = resolve_dates(turn.message, today)
        expect = resolve_dates(turn.expect, today)
        started = time.perf_counter()
        request_id = uuid.uuid4().hex
        try:
            state = await run_turn(planner, message, turn.conversation_id or conversation_id, timeout,
                                   trace_config(case, index, message, request_id), request_id,
                                   turn.language)
        except TimeoutError:
            results.append(TurnResult(
                case.id, index, message, 503, "TIMEOUT", 0, 0, False, None,
                [f"vượt timeout {timeout}s"],
            ))
            break
        latency_ms = round((time.perf_counter() - started) * 1000)
        response = state["response"]
        http_status = state["http_status"]
        events = state.get("events", [])
        candidates = state.get("candidates", {})
        conversation_id = conversation_of(response) or conversation_id

        findings: list[str] = []
        findings += gate_schema(response)
        grounding_failures, grounding_checked = gate_grounding(response, dsn)
        findings += grounding_failures
        findings += gate_secrets(response, settings)
        findings += gate_no_booking_claim(response)
        findings += gate_no_tool_before_info(response, events)
        findings += schedule_findings(response, candidates)
        findings += dataset_findings(response, http_status, events, expect, previous_products,
                                     {call.get("name") for call in state.get("tool_plan") or []})

        tool_called = "tool" in {e.get("node") for e in events}
        tool_expected = expected_tool_call(response)
        if tool_expected is not None and tool_called != tool_expected:
            findings.append(f"quyết định gọi tool sai: đã {'gọi' if tool_called else 'không gọi'}, "
                            f"mong {'gọi' if tool_expected else 'không gọi'}")

        previous_products[index] = {
            "stay": _product_ids(response, "stay"), "any": _product_ids(response, "any"),
        }
        results.append(TurnResult(
            case.id, index, message, http_status, response.get("status") or
            (response.get("error") or {}).get("code"), latency_ms, grounding_checked,
            tool_called, tool_expected, findings,
        ))
        # Lượt đầu sai vẫn chạy tiếp các lượt sau (không dừng sớm): silent-skip che mất lỗi ở
        # những lượt kế, và excludeProductsFromTurn cần previous_products của mọi lượt đã chạy.
    return results


async def run_sweep(planner, dsn: str | None, settings: Any, timeout: float, http: httpx.AsyncClient) -> list[TurnResult]:
    """Nhóm A/B/C cho MỌI điểm đến hiện có trong catalog — không cần ai viết case."""
    listed = (await http.get("destinations", timeout=30)).json()["destinations"]
    results: list[TurnResult] = []
    for item in listed:
        destination = item["destination"]
        case = Case(id=f"SWEEP-{destination}", category="sweep", fr=["FR-AGT-04"],
                    # Chưa nêu ngày đi thì agent hỏi ngày (AC-AGT-01); lượt thứ hai trả lời để chạm tới truy xuất.
                    turns=[Turn(message=f"{destination} 2 ngày", expect={}),
                           Turn(message="chưa chốt ngày đi", expect={})])
        results += await run_case(case, planner, dsn, settings, timeout)
    return results


# ----------------------------------------------------------------------------------------- report


def build_report(results: list[TurnResult], settings: Any, mode: str, product_count: int | None) -> dict[str, Any]:
    total = len(results)
    schema_ok = sum(1 for r in results if not any("schema" in f for f in r.findings))
    grounding_failures = sum(1 for r in results if any(
        "không có trong cdp.products" in f or "lệch DB" in f or "sai điểm đến" in f for f in r.findings
    ))
    grounding_checked = sum(1 for r in results if r.grounding_checked > 0)
    tool_scored = [r for r in results if r.tool_expected is not None]
    tool_correct = sum(1 for r in tool_scored if r.tool_called == r.tool_expected)
    passed = sum(1 for r in results if r.passed)
    latencies = [r.latency_ms for r in results if r.latency_ms]
    return {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "model": settings.itinerary_llm_model or settings.model_name,
        # Runner luôn gọi backend qua ItineraryHttpClients (build_runtime), bất kể ITINERARY_DATA_MODE của máy chạy.
        "dataMode": "http",
        "productCount": product_count,
        "totals": {"turns": total, "passed": passed, "failed": total - passed},
        "metrics": {
            "structuredOutputIntegrity": schema_ok / total if total else None,
            "groundingRate": (grounding_checked - grounding_failures) / grounding_checked if grounding_checked else None,
            "toolCallingAccuracy": tool_correct / len(tool_scored) if tool_scored else None,
            "toolCallingScoredTurns": len(tool_scored),
        },
        "latencyMs": {
            "p50": round(statistics.median(latencies)) if latencies else None,
            "p95": round(statistics.quantiles(latencies, n=20)[18]) if len(latencies) >= 5 else None,
            "max": max(latencies) if latencies else None,
        },
        "turns": [
            {"caseId": r.case_id, "turn": r.turn_index, "message": r.message, "httpStatus": r.http_status,
             "status": r.status, "latencyMs": r.latency_ms, "passed": r.passed, "findings": r.findings}
            for r in results
        ],
    }


def render_markdown(report: dict[str, Any], commit_sha: str) -> str:
    metrics = report["metrics"]

    def pct(value: float | None) -> str:
        return "chưa đo được" if value is None else f"{value:.1%}"

    lines = [
        "# Golden dataset — Itinerary Agent",
        "",
        f"- Commit: `{commit_sha}`",
        f"- Chạy lúc: {report['generatedAt']}",
        f"- Model: `{report['model']}` · dataMode: `{report['dataMode']}` · mode: `{report['mode']}`",
        f"- productCount: {report['productCount']}",
        f"- LangSmith project: `{report.get('traceProject') or 'không bật'}`",
        "",
        "## Ba chỉ số PRD (test-plan.md §2.4)",
        "",
        "| Chỉ số | Ngưỡng | Đo được |",
        "|---|---|---|",
        f"| Grounding Rate | 100% | {pct(metrics['groundingRate'])} |",
        f"| Structured Output Integrity | 100% | {pct(metrics['structuredOutputIntegrity'])} |",
        f"| Tool Calling Accuracy | ≥ 95% | {pct(metrics['toolCallingAccuracy'])} "
        f"(trên {metrics['toolCallingScoredTurns']} lượt tính được) |",
        "",
        f"Latency: p50={report['latencyMs']['p50']}ms, p95={report['latencyMs']['p95']}ms, "
        f"max={report['latencyMs']['max']}ms (mục tiêu < 5000ms, không gate).",
        "",
        f"Tổng {report['totals']['turns']} lượt, PASS {report['totals']['passed']}, "
        f"FAIL {report['totals']['failed']}.",
        "",
        "## Lượt FAIL",
        "",
    ]
    failed = [t for t in report["turns"] if not t["passed"]]
    if not failed:
        lines.append("Không có.")
    else:
        for turn in failed:
            lines.append(f"### {turn['caseId']} lượt {turn['turn']} — {turn['message']!r}")
            lines.append(f"httpStatus={turn['httpStatus']} status={turn['status']} latency={turn['latencyMs']}ms")
            for finding in turn["findings"]:
                lines.append(f"- {finding}")
            lines.append("")
    return "\n".join(lines)


# -------------------------------------------------------------------------------------------- cli


def _commit_sha() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True,
                              check=True, cwd=REPO_ROOT).stdout.strip()
    except Exception:
        return "unknown"


async def _main_async(args: argparse.Namespace) -> int:
    cases = load_dataset(Path(args.dataset))
    if args.only:
        wanted = set(args.only.split(","))
        cases = [c for c in cases if c.id in wanted]
        if not cases:
            print(f"Không case nào khớp --only {args.only}", file=sys.stderr)
            return 2

    if args.trace_project:
        enable_tracing(get_settings(), args.trace_project)

    base_url = args.api_base_url.rstrip("/") + "/api/v1/"
    async with httpx.AsyncClient(base_url=base_url, timeout=30) as http:
        runtime, settings = build_runtime(http)
        planner = runtime.planner()
        dsn = args.dsn or settings.database_url or None

        status = await http.get("assistant/status", timeout=10)
        product_count = status.json().get("productCount") if status.status_code == 200 else None

        results: list[TurnResult] = []
        for repetition in range(max(1, args.repeat)):
            for case in cases:
                results += await run_case(case, planner, dsn, settings, args.timeout)
        if args.sweep:
            results += await run_sweep(planner, dsn, settings, args.timeout, http)

    if args.trace_project:
        from langchain_core.tracers.langchain import wait_for_all_tracers
        wait_for_all_tracers()  # trace gửi nền; không chờ thì tiến trình thoát trước khi gửi xong

    mode = "dataset+sweep" if args.sweep else "dataset"
    report = build_report(results, settings, mode, product_count)
    report["traceProject"] = args.trace_project
    commit_sha = _commit_sha()

    reports_dir = REPO_ROOT / "src/evaluation/reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.now(timezone.utc).date().isoformat()
    json_path = reports_dir / f"eval-{today}-golden.json"
    md_path = reports_dir / f"eval-{today}-golden.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(report, commit_sha), encoding="utf-8")
    print(f"Đã ghi {json_path} và {md_path}")

    metrics = report["metrics"]
    print(f"Grounding Rate: {metrics['groundingRate']}")
    print(f"Structured Output Integrity: {metrics['structuredOutputIntegrity']}")
    print(f"Tool Calling Accuracy: {metrics['toolCallingAccuracy']} ({metrics['toolCallingScoredTurns']} lượt)")
    print(f"PASS {report['totals']['passed']}/{report['totals']['turns']}")

    gate_ok = (metrics["groundingRate"] in (None, 1.0) and metrics["structuredOutputIntegrity"] in (None, 1.0))
    tool_ok = metrics["toolCallingAccuracy"] is None or metrics["toolCallingAccuracy"] >= 0.95
    return 0 if (gate_ok and tool_ok and report["totals"]["failed"] == 0) else 1


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dataset", default="src/evaluation/datasets/itinerary_agent_golden.yaml")
    parser.add_argument("--api-base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--dsn", default=None, help="Mặc định dùng DATABASE_URL từ Settings.")
    parser.add_argument("--only", default=None, help="Danh sách id case, phân tách bằng dấu phẩy.")
    parser.add_argument("--sweep", action="store_true", help="Thêm một lượt Nhóm A/B/C cho mọi điểm đến thật.")
    parser.add_argument("--repeat", type=int, default=1, help="Chạy lại toàn bộ case đã chọn N lần để đo ổn định.")
    parser.add_argument("--timeout", type=float, default=90.0)
    parser.add_argument("--trace-project", default=None,
                        help="Gửi trace từng lượt lên LangSmith project này (key lấy từ .env).")
    args = parser.parse_args()
    sys.exit(asyncio.run(_main_async(args)))


if __name__ == "__main__":
    main()
