"""CLI for the lab."""

from __future__ import annotations

import asyncio

import json
from pathlib import Path
from typing import Annotated

import typer
import yaml

from .graph import build_graph
from .metrics import MetricsReport, metric_from_state, summarize_metrics, write_metrics
from .persistence import build_checkpointer
from .report import write_report
from .scenarios import load_scenarios
from .state import initial_state

app = typer.Typer(no_args_is_help=True)


@app.command("run-scenarios")
def run_scenarios(
    config: Annotated[Path, typer.Option("--config")],
    output: Annotated[Path, typer.Option("--output")],
) -> None:
    """Run all grading scenarios and write metrics JSON."""
    cfg = yaml.safe_load(config.read_text(encoding="utf-8"))
    scenarios = load_scenarios(cfg["scenarios_path"])
    checkpointer = build_checkpointer(cfg.get("checkpointer", "memory"), cfg.get("database_url"))
    graph = build_graph(checkpointer=checkpointer)
    metrics = []
    for scenario in scenarios:
        state = initial_state(scenario)
        run_config = {"configurable": {"thread_id": state["thread_id"]}}
        final_state = asyncio.run(graph.ainvoke(state, config=run_config))
        metrics.append(metric_from_state(final_state, scenario.expected_route.value))
    report = summarize_metrics(metrics)
    write_metrics(report, output)
    if cfg.get("report_path"):
        write_report(report, cfg["report_path"])
    typer.echo(f"Wrote metrics to {output}")


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
    from src.backend.app.infrastructure.clients.itinerary_fixture_clients import FixtureItineraryClients
    from src.backend.app.infrastructure.clients.itinerary_http_clients import ItineraryHttpClients

    async def run():
        async with httpx.AsyncClient(base_url=(api_base_url or "http://unused.local/").rstrip("/") + "/", timeout=1) as http:
            clients = ItineraryHttpClients(http) if api_base_url else FixtureItineraryClients()
            authorization = os.getenv("ITINERARY_AUTHORIZATION")
            gateway = ItineraryToolGateway(clients, clients, clients, recommendation_authorization=authorization)
            graph = build_graph(tools=gateway, checkpointer=build_checkpointer(),
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


@app.command("validate-metrics")
def validate_metrics(metrics: Annotated[Path, typer.Option("--metrics")]) -> None:
    """Validate metrics JSON schema for grading."""
    payload = json.loads(metrics.read_text(encoding="utf-8"))
    report = MetricsReport.model_validate(payload)
    if report.total_scenarios < 6:
        raise typer.BadParameter("Expected at least 6 scenarios")
    typer.echo(f"Metrics valid. success_rate={report.success_rate:.2%}")


if __name__ == "__main__":
    app()
