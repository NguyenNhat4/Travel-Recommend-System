"""CLI của harness RecSys offline. Chạy từ gốc repo (Windows đặt `PYTHONUTF8=1`):

    python -m src.evaluation.recsys_bench doctor
    python -m src.evaluation.recsys_bench load
    python -m src.evaluation.recsys_bench split --kind llbo --freeze          # đóng băng vào frozen/ (B2)
    python -m src.evaluation.recsys_bench run --arm random --split llbo --split-file src/evaluation/recsys_bench/frozen/split-llbo-asof20260922.json
    python -m src.evaluation.recsys_bench run --arm random --arm engine --split llbo --vectors weaviate
    python -m src.evaluation.recsys_bench user --id VP0000001
    python -m src.evaluation.recsys_bench http-latency --base-url https://v-ota.duckdns.org   # p95 guest path (Day 2 C)

Mã thoát: 0 ok · 1 lỗi môi trường/dữ liệu. Số đo và giới hạn: `docs/spec/bench/recsys-offline-eval.md`.
"""
from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
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
          refresh: bool = typer.Option(False, "--refresh"),
          freeze: bool = typer.Option(False, "--freeze", help="đóng băng split vào frozen/split-<kind>-asof<YYYYMMDD>.json (commit)"),
          freeze_path: Optional[str] = typer.Option(None, "--freeze-path", help="đường dẫn khác cho --freeze"),
          force: bool = typer.Option(False, "--force", help="cho phép --freeze đè file đã có với sha khác")):
    """Chia train/test và in số khách, target, cờ giải thích. `--freeze` ghi bản đóng băng (sha256 của event đầu vào +
    từng target) để `run --split-file` từ chối khi DB hoặc tham số đổi."""
    from . import data_source
    from .paths import FROZEN_DIR, recsys_home
    with _prepared(as_of, refresh, "none") as (index, _, kept, _, snapshot, _):
        result = _make_split(kind, kept, index, cutoff, min_purchases, min_trips)
    summary = result.summary()
    path = recsys_home() / f"split-{kind}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    typer.echo(json.dumps({k: v for k, v in summary.items() if k != "targets"}, ensure_ascii=False, indent=2))
    typer.echo(f"→ {path}")
    if freeze or freeze_path:
        target = Path(freeze_path) if freeze_path else FROZEN_DIR / f"split-{kind}-asof{snapshot:%Y%m%d}.json"
        if target.exists() and not force:
            try:
                old = json.loads(target.read_text(encoding="utf-8")).get("sha256")
            except (OSError, ValueError, AttributeError):
                old = None
            if old != result.frozen_sha256():
                _fail(f"{target} đã có với sha {str(old)[:12]} ≠ {result.frozen_sha256()[:12]} — bản đóng băng là mốc đã commit; "
                      "muốn thay thì --force (và ghi bảng mới trong spec)")
        sha = result.freeze(target, db_as_of=snapshot.isoformat(), dsn_label=data_source.dsn_label(data_source.eval_cdp_url()))
        typer.echo(f"đóng băng sha256 {sha} → {target}")


@app.command()
def run(arms: List[str] = typer.Option(["random"], "--arm", help="random | most_popular | most_popular_in_destination | "
                                                                   "engine (mode eval, đủ k món) | engine_prod (cap 2 / taxonomy)"),
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
        run_id: Optional[str] = typer.Option(None, "--run-id"),
        split_file: Optional[str] = typer.Option(None, "--split-file", help="bản đóng băng (split --freeze); luôn đọc lại CDP "
                                                                          "(bỏ cache event) rồi đối chiếu; lệch → dừng, mã 1")):
    """Chạy các arm trên cùng split, in bảng markdown, ghi bench_out/recsys/runs/<run_id>/ (summary.json có modelVersion,
    engineConfig, configHash, vectorsMissing; per_user.jsonl có ids top-k, targetProductId, rankStrict)."""
    from . import data_source
    from .arms import EngineArm, MostPopularArm, MostPopularInDestinationArm, RandomArm
    from .bench import aggregate, evaluate
    from .engine import OfflineEngine, config_hash, engine_config
    from .paths import run_dir
    from .report import header, markdown_table, write_run
    from .splits import SplitMismatch

    unknown = set(arms) - {"random", "most_popular", "most_popular_in_destination", "engine", "engine_prod"}
    if unknown:
        _fail(f"arm không hỗ trợ: {sorted(unknown)}")
    need_vec = {"engine", "engine_prod"} & set(arms)
    mode = vectors or ("weaviate" if need_vec else "none")
    if need_vec and mode == "none":
        _fail("arm engine / engine_prod cần --vectors weaviate hoặc numpy")
    run_id = run_id or f"{datetime.now():%Y%m%d-%H%M%S}-{kind}"
    refresh = refresh or bool(split_file)   # bản đóng băng phải đối chiếu với DB thật, không với cache JSONL (review 01/10)
    with _prepared(as_of, refresh, mode) as (index, vector_search, kept, report, snapshot, _):
        result = _make_split(kind, kept, index, cutoff, min_purchases, min_trips)
        frozen_sha = None
        if split_file:
            try:
                frozen_sha = result.verify(split_file)
            except (SplitMismatch, OSError, KeyError, ValueError, TypeError) as exc:
                _fail(f"--split-file: {exc}")
            typer.echo(f"split khớp bản đóng băng {split_file} (sha {frozen_sha[:12]})")
        users = sorted(result.targets)[:limit_users] if limit_users else None
        rows, raw_rows, per_user = [], [], []
        # popularity của baseline và engine cùng nguồn: purchase < as_of của từng khách (OfflineEngine.popularity_at)
        engine = OfflineEngine(index, vector_search, result.train_purchases,
                               candidate_k=data_source.settings().recommend_candidate_k)
        if "random" in arms:
            seed_rows = []
            for seed in (int(x) for x in seeds.split(",") if x.strip()):
                row, users_rows = evaluate(RandomArm(index, seed), result, index, k, users)
                seed_rows.append(row)
                per_user += users_rows
            raw_rows += seed_rows
            rows.append(aggregate(seed_rows))
        for name, cls in (("most_popular", MostPopularArm), ("most_popular_in_destination", MostPopularInDestinationArm)):
            if name in arms:
                row, users_rows = evaluate(cls(index, engine), result, index, k, users)
                raw_rows.append(row)
                rows.append(row)
                per_user += users_rows
        if "engine" in arms:                      # mode eval: bỏ cap 2 món / taxonomy để đủ k món (quyết định 30/09)
            row, users_rows = evaluate(EngineArm(engine), result, index, k, users)
            raw_rows.append(row)
            rows.append(row)
            per_user += users_rows
        if "engine_prod" in arms:                 # đúng list production (cap MAX_PER_VERTICAL): khách thật sự thấy gì
            prod = OfflineEngine(index, vector_search, result.train_purchases,
                                 candidate_k=data_source.settings().recommend_candidate_k, mode="prod")
            row, users_rows = evaluate(EngineArm(prod), result, index, k, users)
            raw_rows.append(row)
            rows.append(row)
            per_user += users_rows
        cfg = engine_config(engine)
        summary = {"runId": run_id, "modelVersion": index.model_version, "engineConfig": cfg, "configHash": config_hash(cfg),
                   "asOf": snapshot.isoformat(), "k": k, "vectors": mode,
                   "searchUnits": len(index.units), "recommendable": int(index.recommendable.sum()),
                   "vectorsMissing": _vectors_missing(index, vector_search),
                   "limitUsers": limit_users, "usersEvaluated": len(users) if users is not None else len(result.targets),
                   "filter": report.as_dict(),
                   "split": {**{kw: v for kw, v in result.summary().items() if kw != "targets"},
                             "frozenSha256": frozen_sha, "splitFile": split_file},
                   "rows": rows, "rawRows": raw_rows}
        if "engine_prod" in arms:
            cfg_prod = engine_config(prod)
            summary["engineConfigProd"], summary["configHashProd"] = cfg_prod, config_hash(cfg_prod)
    directory = write_run(run_dir(run_id), summary, per_user)
    typer.echo(header(summary))
    for line in report.lines():
        typer.echo(line)
    typer.echo(json.dumps(summary["split"], ensure_ascii=False))
    typer.echo(markdown_table(rows))
    for row in rows:
        if row.get("strategies"):
            typer.echo(f"{row['arm']} strategy: {row['strategies']}")
    typer.echo(f"→ {directory}")


def _vectors_missing(index, vector_search) -> Optional[int]:
    """Số search unit không có vector đúng model trong kho (engine bỏ qua chúng) — None khi kho không khai metadata."""
    metadata = getattr(vector_search, "metadata", None)
    if metadata is None:
        ids = getattr(vector_search, "ids", None)          # NumpyVectorSearch: ids = unit có vector đúng model
        return None if ids is None else len(index.units) - len({p.product_id for p in index.units} & set(ids))
    try:
        have = metadata([p.product_id for p in index.units])
    except Exception:  # noqa: BLE001 — chỉ là số phụ trong summary
        return None
    return sum(1 for p in index.units if p.product_id not in have or have[p.product_id].model_version != index.model_version)


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
                               candidate_k=data_source.settings().recommend_candidate_k, mode="prod")   # như production
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


@app.command("http-latency")
def http_latency(base_url: str = typer.Option(..., "--base-url", help="vd https://v-ota.duckdns.org hoặc http://127.0.0.1:8000"),
                 runs: int = typer.Option(3, "--runs"),
                 drop_first: bool = typer.Option(True, "--drop-first/--keep-first", help="bỏ lượt 1 khỏi p50/p95"),
                 k: int = typer.Option(5, "--k", help="k của /recommendations; guest path lặp k GET mỗi lượt"),
                 timeout_s: float = typer.Option(30.0, "--timeout"),
                 users: Optional[str] = typer.Option(None, "--users", help="JSON {\"users\": [{\"cdpUserId\": …}]} → "
                                                                          "/internal/recommendations với X-Service-Token"),
                 token_env: str = typer.Option("AUTH_SERVICE_TOKEN", "--token-env", help="tên biến môi trường chứa token (không in)"),
                 run_id: Optional[str] = typer.Option(None, "--run-id")):
    """p50/p95 `/recommendations` qua HTTP (Day 2 C). Mặc định **guest path** (không cookie → popular) — đường duy nhất đo
    được từ ngoài trên Cloud; `--users` đi `/internal/recommendations` khi có tunnel IAP / backend local. Ghi
    bench_out/recsys/runs/<run_id>/http_latency.json. Mã thoát 1 khi không có mẫu 200."""
    from pathlib import Path

    from . import http_latency as H
    from .paths import run_dir

    try:
        user_ids = H.load_users(Path(users)) if users else None
    except (H.HttpLatencyError, OSError, ValueError) as e:
        _fail(str(e))
    run_id = run_id or f"{datetime.now():%Y%m%d-%H%M%S}-http-{'users' if user_ids else 'guest'}"
    typer.echo(f"http-latency · {base_url} · {'users ' + str(len(user_ids)) if user_ids else 'guest path (popular)'} · "
               f"{runs} lượt · k={k} · drop_first {drop_first}")
    try:
        samples = H.measure(base_url, runs=runs, k=k, timeout_s=timeout_s, users=user_ids, token_env=token_env,
                            progress=lambda s: typer.echo(f"  lỗi lượt {s.run} {s.user or 'guest'}: {s.error}") if s.error else None)
    except H.HttpLatencyError as e:
        _fail(str(e))
    summary = H.summarize(samples, drop_first=drop_first)
    lat, cli = summary["latency_ms"], summary["client_ms"]

    def _p(v):
        return "-" if v is None else f"{v:.0f}"
    typer.echo(f"| đường | n | latencyMs p50 | p95 | client p50 | p95 | strategy |")
    typer.echo(f"|---|---:|---:|---:|---:|---:|---|")
    typer.echo(f"| {summary['path']} | {lat['n']} | {_p(lat['p50'])} | {_p(lat['p95'])} | {_p(cli['p50'])} | {_p(cli['p95'])} | "
               f"{summary['strategies']} |")
    typer.echo(f"mẫu {summary['n_ok']}/{summary['n_samples']} OK · items tối thiểu {summary['n_items_min']} · "
               f"{'guest path: một khách popular, không phải 60 khách' if not user_ids else 'users: /internal'}")
    p = H.write(run_dir(run_id), base_url=base_url, samples=samples, summary=summary,
                meta={"runId": run_id, "runs": runs, "k": k, "users": len(user_ids) if user_ids else 0})
    typer.echo(f"→ {p}")
    if summary["n_ok"] == 0:
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
