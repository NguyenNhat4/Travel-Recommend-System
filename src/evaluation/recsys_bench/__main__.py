"""CLI của harness RecSys offline. Chạy từ gốc repo (Windows đặt `PYTHONUTF8=1`):

    python -m src.evaluation.recsys_bench doctor
    python -m src.evaluation.recsys_bench load
    python -m src.evaluation.recsys_bench split --kind llbo
    python -m src.evaluation.recsys_bench run --arm random --split llbo
    python -m src.evaluation.recsys_bench run --arm random --arm engine --split llbo --vectors weaviate
    python -m src.evaluation.recsys_bench user --id VP0000001

Mã thoát: 0 ok · 1 lỗi môi trường/dữ liệu. Số đo và giới hạn: `docs/spec/bench/recsys-offline-eval.md`.
"""
from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import datetime, timezone
from time import perf_counter
from typing import List, Optional

import typer

app = typer.Typer(add_completion=False, no_args_is_help=True,
                  help="recsys_bench — đánh giá offline engine Recommendation trên DB đã seed")

AS_OF_HELP = "mốc snapshot ISO (vd 2026-09-24); mặc định 00:00 UTC ngày sau event cuối"


def _fail(message: str) -> None:
    typer.secho(message, fg=typer.colors.RED, err=True)
    raise typer.Exit(1)


def _parse_as_of(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    from .events import parse_ts
    return parse_ts(value if "T" in value else f"{value}T00:00:00+00:00").astimezone(timezone.utc)


@contextmanager
def _prepared(as_of: Optional[str], refresh: bool, vectors: str):
    """(index, vector search, event đã lọc, báo cáo lọc, as_of, event thô); đóng kết nối Weaviate khi xong."""
    from . import data_source
    from .events import filter_events

    cut = _parse_as_of(as_of)
    events = data_source.load_events(cut, refresh=refresh)
    snapshot = cut or data_source.derive_as_of(events)
    index, vector_search = data_source.load_index(vectors)
    try:
        kept, report = filter_events(events, index, snapshot)
        yield index, vector_search, kept, report, snapshot, events
    finally:
        if vector_search is not None and hasattr(vector_search, "close"):
            vector_search.close()


def _make_split(kind: str, kept: list[dict], index, cutoff: Optional[str], min_purchases: int, min_trips: int):
    from .splits import leave_last_booking_out, temporal_split
    if kind == "llbo":
        return leave_last_booking_out(kept, index, min_purchases=min_purchases, min_trips=min_trips)
    if kind == "temporal":
        return temporal_split(kept, index, cutoff=_parse_as_of(cutoff))
    _fail("--kind phải là llbo hoặc temporal")


@app.command()
def doctor():
    """Kiểm kết nối: catalog (DATABASE_URL), CDP chỉ đọc (EVAL_DATABASE_URL), Weaviate."""
    from . import data_source
    s = data_source.settings()
    ok = True
    try:
        index, _ = data_source.load_index("none")
        typer.echo(f"catalog  OK  {data_source.dsn_label(s.database_url)} · {len(index.units):,} search unit · "
                   f"{int(index.recommendable.sum()):,} recommendable · model {index.model_version}")
    except Exception as exc:  # noqa: BLE001 — doctor in lỗi để người chạy sửa môi trường
        ok = False
        typer.echo(f"catalog  FAIL {type(exc).__name__}: {str(exc).splitlines()[0][:200]}")
    try:
        url = data_source.eval_cdp_url()
        cleared = data_source.clear_event_cache()   # sau khi seed lại, mọi cache theo as_of đều cũ
        events = data_source.load_events(None, refresh=True)
        typer.echo(f"cdp      OK  {data_source.dsn_label(url)} · {len(events):,} event · "
                   f"as_of suy ra {data_source.derive_as_of(events).date().isoformat()} · xoá {cleared} cache event")
    except Exception as exc:  # noqa: BLE001
        ok = False
        typer.echo(f"cdp      FAIL {type(exc).__name__}: {str(exc).splitlines()[0][:200]}")
    try:
        from src.backend.app.infrastructure.vectors.weaviate_store import WeaviateClient
        client = WeaviateClient(s.weaviate_url, collection=s.weaviate_collection, api_key=s.weaviate_api_key,
                                timeout_seconds=5)
        try:
            client.ready()
        finally:
            client.close()
        typer.echo(f"weaviate OK  {s.weaviate_url}")
    except Exception as exc:  # noqa: BLE001 — random arm không cần Weaviate
        typer.echo(f"weaviate FAIL {type(exc).__name__}: {str(exc).splitlines()[0][:200]} (arm random vẫn chạy được)")
    if not ok:
        raise typer.Exit(1)


@app.command()
def load(as_of: Optional[str] = typer.Option(None, "--as-of", help=AS_OF_HELP),
         refresh: bool = typer.Option(False, "--refresh", help="đọc lại CDP, bỏ cache JSONL")):
    """Đọc event, lọc purchase orphan / thiếu event_group_id, in số bị loại."""
    with _prepared(as_of, refresh, "none") as (_, _, _, report, _, _):
        for line in report.lines():
            typer.echo(line)


@app.command()
def split(kind: str = typer.Option("llbo", "--kind", help="llbo | temporal"),
          cutoff: Optional[str] = typer.Option(None, "--T", help="mốc T cho temporal (mặc định phân vị 80 % purchase)"),
          min_purchases: int = typer.Option(2, "--min-purchases"),
          min_trips: int = typer.Option(1, "--min-trips", help="2 = chọn khách như baseline trong seed"),
          as_of: Optional[str] = typer.Option(None, "--as-of", help=AS_OF_HELP),
          refresh: bool = typer.Option(False, "--refresh")):
    """Chia train/test và in số khách, target, cờ giải thích."""
    from .paths import recsys_home
    with _prepared(as_of, refresh, "none") as (index, _, kept, _, _, _):
        result = _make_split(kind, kept, index, cutoff, min_purchases, min_trips)
    summary = result.summary()
    path = recsys_home() / f"split-{kind}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    typer.echo(json.dumps({k: v for k, v in summary.items() if k != "targets"}, ensure_ascii=False, indent=2))
    typer.echo(f"→ {path}")


@app.command()
def run(arms: List[str] = typer.Option(["random"], "--arm", help="random | engine (lặp lại để chạy nhiều arm)"),
        kind: str = typer.Option("llbo", "--split", help="llbo | temporal"),
        k: int = typer.Option(20, "--k"),
        seeds: str = typer.Option("42,43,44", "--seeds", help="seed cho arm random"),
        vectors: Optional[str] = typer.Option(None, "--vectors", help="none | weaviate | numpy (engine cần vector)"),
        cutoff: Optional[str] = typer.Option(None, "--T"),
        min_purchases: int = typer.Option(2, "--min-purchases"),
        min_trips: int = typer.Option(1, "--min-trips"),
        limit_users: Optional[int] = typer.Option(None, "--limit-users", help="chỉ N khách đầu (chạy thử)"),
        as_of: Optional[str] = typer.Option(None, "--as-of", help=AS_OF_HELP),
        refresh: bool = typer.Option(False, "--refresh"),
        run_id: Optional[str] = typer.Option(None, "--run-id")):
    """Chạy các arm trên cùng split, in bảng markdown, ghi bench_out/recsys/runs/<run_id>/."""
    from . import data_source
    from .arms import EngineArm, RandomArm
    from .bench import aggregate, evaluate
    from .engine import OfflineEngine
    from .paths import run_dir
    from .report import markdown_table, write_run

    unknown = set(arms) - {"random", "engine"}
    if unknown:
        _fail(f"arm không hỗ trợ: {sorted(unknown)}")
    mode = vectors or ("weaviate" if "engine" in arms else "none")
    if "engine" in arms and mode == "none":
        _fail("arm engine cần --vectors weaviate hoặc numpy")
    run_id = run_id or f"{datetime.now():%Y%m%d-%H%M%S}-{kind}"
    with _prepared(as_of, refresh, mode) as (index, vector_search, kept, report, snapshot, _):
        result = _make_split(kind, kept, index, cutoff, min_purchases, min_trips)
        users = sorted(result.targets)[:limit_users] if limit_users else None
        rows, raw_rows, per_user = [], [], []
        if "random" in arms:
            seed_rows = []
            for seed in (int(x) for x in seeds.split(",") if x.strip()):
                row, users_rows = evaluate(RandomArm(index, seed), result, index, k, users)
                seed_rows.append(row)
                per_user += users_rows
            raw_rows += seed_rows
            rows.append(aggregate(seed_rows))
        if "engine" in arms:
            engine = OfflineEngine(index, vector_search, result.train_purchases,
                                   candidate_k=data_source.settings().recommend_candidate_k)
            row, users_rows = evaluate(EngineArm(engine), result, index, k, users)
            raw_rows.append(row)
            rows.append(row)
            per_user += users_rows
        summary = {"runId": run_id, "asOf": snapshot.isoformat(), "k": k, "vectors": mode,
                   "modelVersion": index.model_version, "searchUnits": len(index.units),
                   "recommendable": int(index.recommendable.sum()),
                   "filter": report.as_dict(), "split": {kw: v for kw, v in result.summary().items() if kw != "targets"},
                   "rows": rows, "rawRows": raw_rows}
    directory = write_run(run_dir(run_id), summary, per_user)
    for line in report.lines():
        typer.echo(line)
    typer.echo(json.dumps(summary["split"], ensure_ascii=False))
    typer.echo(markdown_table(rows))
    for row in rows:
        if row.get("strategies"):
            typer.echo(f"{row['arm']} strategy: {row['strategies']}")
    typer.echo(f"→ {directory}")


@app.command()
def user(cdp_user_id: str = typer.Option(..., "--id"),
         k: int = typer.Option(5, "--k"),
         vectors: str = typer.Option("weaviate", "--vectors", help="weaviate | numpy"),
         as_of: Optional[str] = typer.Option(None, "--as-of", help=AS_OF_HELP),
         refresh: bool = typer.Option(False, "--refresh")):
    """Gọi engine cho một khách với toàn bộ lịch sử trước as_of (như production), kiểm contract."""
    from jsonschema import Draft202012Validator

    from src.backend.app.application.itinerary.tool_contracts import contracts

    from . import data_source
    from .engine import OfflineEngine
    from .events import parse_ts

    with _prepared(as_of, refresh, vectors) as (index, vector_search, _, _, snapshot, events):
        history = [e for e in events if e.get("cdpUserId") == cdp_user_id and parse_ts(e["timestamp"]) < snapshot]
        purchases = [e for e in events if e.get("eventName") == "purchase"]
        engine = OfflineEngine(index, vector_search, purchases,
                               candidate_k=data_source.settings().recommend_candidate_k)
        started = perf_counter()
        response = engine.recommend(cdp_user_id, snapshot, k, history)
        response["cdpUserId"] = cdp_user_id
        response.setdefault("diagnostics", {})["latencyMs"] = max(0, round((perf_counter() - started) * 1000))
    errors = [e.message for e in Draft202012Validator(contracts()["get_recommendations"]["response"]).iter_errors(response)]
    items = [{"rank": r.get("rank"), "productId": r["productId"], "name": r["name"], "taxonomy": r["taxonomy"],
              "destination": r["destination"], "because": len(r.get("because") or [])}
             for r in response.get("recommendations", [])]
    out = {"asOf": snapshot.isoformat(), "user": cdp_user_id, "historyEvents": len(history),
           "strategy": response.get("strategy"), "destination": response.get("destination"),
           "nextVertical": response.get("nextVertical"), "diagnostics": response.get("diagnostics"),
           "extraFields": sorted(set(response) - {"cdpUserId", "generatedAt", "modelVersion", "strategy", "destination",
                                                  "nextVertical", "recommendations", "diagnostics"}),
           "items": items, "contractErrors": errors}
    if cdp_user_id == "VP0000001":   # kỳ vọng của lịch Day 1 C và tiêu chí 17 spec search-recommendation
        taxonomies = [i["taxonomy"] for i in items]
        out["day1Check"] = {
            "strategy == cross_vertical": response.get("strategy") == "cross_vertical",
            "excludedVerticals == ['hotel']": (response.get("diagnostics") or {}).get("excludedVerticals") == ["hotel"],
            "không có item hotel": "hotel" not in taxonomies,
            "nextVertical ∈ {flight, attraction}": response.get("nextVertical") in {"flight", "attraction"},
        }
    typer.echo(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    app()
