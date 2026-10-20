"""Đo FR-AGT-01/06, AC-AGT-01/07: mất hứng, dừng, câu phủ định theo ngữ cảnh.

Model thật theo Settings, tool thật qua HTTP/gateway, runtime/commit v2 thật. Không đi qua API/SSE của assistant.
Ngữ cảnh seed được ghi riêng; không được trình bày câu seed như output model thật. Không lưu reasoning/secret.
Chạy mỗi bản code ở process mới, cùng backend nguồn, --repeat và --out; xem report để đánh giá lời văn.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
from copy import deepcopy
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from time import monotonic
from uuid import uuid4

import httpx

from src.backend.app.agents import orc_v2
from src.backend.app.agents.tools.itinerary_gateway import ItineraryToolGateway
from src.backend.app.application.itinerary.destination_names import DestinationNames
from src.backend.app.core.config import Settings
from src.backend.app.infrastructure.clients.itinerary_http_clients import (
    ItineraryHttpClients,
)
from src.backend.app.infrastructure.llm import (
    build_chat_model,
    build_orchestrator_model,
)
from src.backend.app.infrastructure.persistence.assistant_v2_store import (
    commit,
    new_state,
)


def cases() -> dict:
    trip = {"destination": "Đà Nẵng", "start_date": "2026-10-17", "days": 1, "adults": 2,
            "planning_consent": True}
    kids = {"context": trip, "user": "Lập lịch Đà Nẵng ngày 17/10/2026, đi trong ngày, 2 người lớn.",
            "assistant": "Có trẻ em đi cùng không?"}
    offer = {"context": {"destination": "Đà Nẵng", "planning_consent": False},
             "user": "Đà Nẵng có gì chơi?", "assistant": "Bạn muốn mình lập lịch Đà Nẵng không?"}
    return {
        "lost-interest": {"messages": ["Gợi ý vài chỗ chơi ở Đà Nẵng.",
                                       "Chán quá, không muốn đi nữa.", "Thôi, không cần."]},
        "explicit-stop": {"messages": ["Gợi ý vài chỗ chơi ở Đà Nẵng.",
                                       "Dừng tư vấn, đừng gợi ý nữa."]},
        "kids-ko": {"seed": kids, "messages": ["ko"]},
        "kids-k": {"seed": kids, "messages": ["k"]},
        "offer-ko": {"seed": offer, "messages": ["ko", "Giới thiệu một điểm tham quan tự do ở Đà Nẵng."]},
        "offer-khong": {"seed": offer, "messages": ["không"]},
        "rest-then-no": {"messages": ["Không muốn đi chơi.", "ko"]},
    }


class RecordedModel:
    """Chỉ giữ function calls và usage; không thu chain-of-thought hoặc payload có credential."""

    def __init__(self, model):
        self.model = model
        self.calls = []
        self.usage = []

    def bind_tools(self, *args, **kwargs):
        bound = self.model.bind_tools(*args, **kwargs)
        recorder = self

        class Bound:
            async def ainvoke(self, messages):
                response = await bound.ainvoke(messages)
                recorder.calls.append(deepcopy(response.tool_calls))
                recorder.usage.append(response.usage_metadata)
                return response

        return Bound()


async def conversation(name, case, *, model, tools, settings, destinations, progress):
    state = new_state()
    seed = deepcopy(case.get("seed"))
    if seed:
        state["context"] = seed["context"]
        state["turns"] = [{"message": seed["user"], "answer": seed["assistant"], "refs": []}]
    result = {"name": name, "seed": seed, "turns": []}
    conversation_id = str(uuid4())
    for query in case["messages"]:
        started = monotonic()
        recorded = RecordedModel(model)
        runtime = orc_v2.OrcV2Runtime(
            tools=tools, llm=recorded,
            known_refs={ref: item["productId"] for ref, item in state["shown"].items()},
            request_timeout_seconds=settings.itinerary_request_timeout_seconds,
            tool_timeout_seconds=settings.itinerary_tool_timeout_seconds,
            model_timeout_seconds=settings.itinerary_llm_timeout_seconds, destinations=destinations)
        row = {"query": query, "context_before": deepcopy(state["context"])}
        try:
            outcome = await runtime.run({"message": query, "ui_action": None, "intent_override": None,
                                        "language": "vi", "context": state["context"], "plan": state["plan"],
                                        "turns": state["turns"], "shown": state["shown"],
                                        "conversation_id": conversation_id, "run_id": str(uuid4())})
            row["failure"] = outcome.get("failure")
            row["failure_message"] = outcome.get("failure_message")
            row["patch"] = outcome.get("patch")
            if outcome.get("final"):
                row["final"] = commit(state, final=outcome["final"], patch=outcome["patch"] or {},
                                      memory=outcome["memory"], message=query, base_revision=state["revision"])
            else:
                row["final"] = None
        except Exception as exc:  # noqa: BLE001 - record failure type without SDK text or credentials
            row.update(failure=type(exc).__name__, final=None)
        row.update(seconds=round(monotonic() - started, 2), calls=recorded.calls, usage=recorded.usage,
                   source_requests=runtime.dispatcher.budget.used, context_after=deepcopy(state["context"]))
        result["turns"].append(row)
        progress(result)
        final = row.get("final") or {}
        print(f'{name} turn={len(result["turns"])} {row.get("failure") or final.get("turnKind")} '
              f'{row["seconds"]}s requests={row["source_requests"]}', flush=True)
        if row.get("failure"):
            result["aborted"] = "Previous turn failed; no synthetic continuation."
            progress(result)
            break
    return result


async def main(args):
    if args.prompt_from:
        # Replay only the saved prompt; callers must still account for runtime/catalog changes.
        orc_v2.PROMPT = json.loads(args.prompt_from.read_text(encoding="utf-8"))["prompt"]
    settings = Settings()
    model = build_orchestrator_model(settings, build_chat_model(settings))
    if model is None:
        raise RuntimeError("LLM unavailable")
    chosen = cases()
    names = args.cases or list(chosen)
    unknown = set(names) - chosen.keys()
    if unknown:
        raise ValueError(f"Unknown cases: {sorted(unknown)}")
    commit_hash = await asyncio.to_thread(subprocess.check_output, ["git", "rev-parse", "HEAD"], text=True)
    output = {
        "variant": args.variant, "dataset": "sota-stop-review-v1", "repeat": args.repeat,
        "started_at": datetime.now().astimezone().isoformat(),
        "commit": commit_hash.strip(),
        "prompt_sha256": sha256(orc_v2.PROMPT.encode()).hexdigest(), "prompt": orc_v2.PROMPT,
        "model": settings.itinerary_orchestrator_model or settings.itinerary_llm_model,
        "provider": settings.itinerary_orchestrator_provider,
        "reasoning_effort": settings.itinerary_orchestrator_reasoning_effort,
        "timeouts": {"request": settings.itinerary_request_timeout_seconds,
                     "tool": settings.itinerary_tool_timeout_seconds, "model": settings.itinerary_llm_timeout_seconds},
        "data_mode": "http", "source_url": args.base_url, "results": {},
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)

    def save(result):
        output["results"][result["name"]] = result
        args.out.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")

    async with httpx.AsyncClient(base_url=args.base_url.rstrip("/") + "/api/v1/", timeout=30) as http:
        status = (await http.get("assistant/status")).json()
        if status.get("status") != "ready" or status.get("dataMode") not in ("inprocess", "http"):
            raise RuntimeError("Real catalog backend is not ready")
        output["source_status"] = status
        client = ItineraryHttpClients(http)
        tools = ItineraryToolGateway(client, client, client, similar=client)
        destinations = DestinationNames()
        await destinations.get(tools)
        gate = asyncio.Semaphore(args.parallel)

        async def run(name, attempt):
            async with gate:
                return await conversation(f"{name}#{attempt}", chosen[name], model=model, tools=tools,
                                          settings=settings, destinations=destinations, progress=save)

        await asyncio.gather(*(run(name, attempt) for attempt in range(1, args.repeat + 1) for name in names))
    output["finished_at"] = datetime.now().astimezone().isoformat()
    args.out.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cases", nargs="*")
    parser.add_argument("--base-url", default="http://127.0.0.1:8001")
    parser.add_argument("--variant", required=True)
    parser.add_argument("--prompt-from", type=Path, help="Dùng prompt trong JSON lần đo cũ; runtime vẫn là code hiện tại.")
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--parallel", type=int, default=2)
    parser.add_argument("--out", type=Path, required=True)
    asyncio.run(main(parser.parse_args()))
