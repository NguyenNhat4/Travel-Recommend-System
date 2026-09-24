"""CLI chạy tay một lượt qua Itinerary Agent với LLM thật. Bộ đánh giá tự động 50 case chấm
theo docs/prd/test-plan.md §2.4 nằm ở `src/evaluation/agent/golden.py` (`python -m
src.evaluation.agent.golden`), không qua CLI này."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Annotated

import typer

from src.backend.app.agents.graph import build_graph
from src.backend.app.infrastructure.persistence.langgraph_checkpointer import build_checkpointer

app = typer.Typer(no_args_is_help=True)


@app.command("itinerary")
def run_itinerary(
    message: Annotated[str, typer.Option("--message")],
    output: Annotated[Path, typer.Option("--output")] = Path("/tmp/itinerary-run.json"),
    api_base_url: Annotated[str | None, typer.Option("--api-base-url")] = None,
) -> None:
    """Run one request with a real configured LLM; write response and safe trace."""
    import os
    import uuid
    import httpx
    from src.backend.app.agents.tools.itinerary_gateway import ItineraryToolGateway
    from src.backend.app.core.config import get_settings
    from src.backend.app.infrastructure.clients.itinerary_fixture_clients import FixtureItineraryClients
    from src.backend.app.infrastructure.clients.itinerary_http_clients import ItineraryHttpClients
    from src.backend.app.infrastructure.llm import build_chat_model

    # Dựng client một lần như composition root; None khi ITINERARY_USE_LLM=false, lúc đó node
    # classify trả LLM_UNAVAILABLE và lệnh thoát với mã 1.
    try:
        llm = build_chat_model(get_settings())
    except RuntimeError as exc:
        typer.echo(str(exc))
        raise typer.Exit(1)

    async def run():
        async with httpx.AsyncClient(base_url=(api_base_url or "http://unused.local/").rstrip("/") + "/", timeout=1) as http:
            clients = ItineraryHttpClients(http) if api_base_url else FixtureItineraryClients()
            authorization = os.getenv("ITINERARY_AUTHORIZATION")
            gateway = ItineraryToolGateway(clients, clients, clients, recommendation_authorization=authorization)
            graph = build_graph(tools=gateway, checkpointer=build_checkpointer(), llm=llm,
                                require_recommendations=bool(authorization))
            run_id = uuid.uuid4().hex
            return await asyncio.wait_for(graph.ainvoke({"query": message, "request_id": run_id},
                    {"configurable": {"thread_id": run_id}}), timeout=5)
    try:
        state = asyncio.run(run())
    except TimeoutError:
        typer.echo("Request exceeded the 5-second deadline.")
        raise typer.Exit(1)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    typer.echo(f"Wrote response and trace to {output}")
    if state["http_status"] != 200:
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
