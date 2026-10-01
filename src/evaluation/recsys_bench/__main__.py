"""CLI của harness RecSys offline. Chạy từ gốc repo (Windows đặt `PYTHONUTF8=1`):

    python -m src.evaluation.recsys_bench doctor
    python -m src.evaluation.recsys_bench load
    python -m src.evaluation.recsys_bench split --kind llbo --freeze          # đóng băng vào frozen/ (B2)
    python -m src.evaluation.recsys_bench run --arm random --split llbo --split-file src/evaluation/recsys_bench/frozen/split-llbo-asof20260922.json
    python -m src.evaluation.recsys_bench run --arm random --arm engine --split llbo --vectors weaviate
    python -m src.evaluation.recsys_bench user --id VP0000001
    python -m src.evaluation.recsys_bench http-latency --base-url https://v-ota.duckdns.org   # p95 guest path (Day 2 C)
    python -m src.evaluation.recsys_bench run --arm engine_nommr --split llbo --vectors weaviate --run-id <run>   # thêm arm vào run đã có
    python -m src.evaluation.recsys_bench analyze --run-id <run>   # ceiling, phân khúc, strict/lenient, 20 ca (B5–B8), không cần Weaviate
    python -m src.evaluation.recsys_bench sanity [--json]           # kiểm dữ liệu seed: lifecycle, chuyến, cạnh lộn xộn, phổ biến (B1)
    python -m src.evaluation.recsys_bench parity --make-users       # frozen/users60.json; rồi parity --base-url http://127.0.0.1:8000 (B9)

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
                   f"as_of suy ra {data_source.derive_as_of(events).date().isoformat()} · xoá {cleared} cache CDP (event + profile)")
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
                                                                   "engine (mode eval, đủ k món) | engine_prod (cap 2 / taxonomy) | "
                                                                   "engine_nommr (pool 200 theo score, không MMR — chẩn đoán)"),
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
                                                                          "(bỏ cache event) rồi đối chiếu; lệch → dừng, mã 1"),
        override: List[str] = typer.Option([], "--override", help="KEY=VALUE hằng của domain/recommendation/profile.py đọc lúc "
                                                                  "chạy (MMR_LAMBDA, W_SHORT, W_POP, W_LONG, H_SHORT_DAYS, "
                                                                  "H_LONG_DAYS, ACTIVE_TRIP_MAX_AGE_DAYS, DORMANT_AFTER_DAYS, "
                                                                  "MAX_REPEAT_PER_TRIP; W_TYPE dạng JSON) — chỉ trong tiến trình "
                                                                  "này, vào configHash (M7, chỉ chạy trên temporal)")):
    """Chạy các arm trên cùng split, in bảng markdown, ghi bench_out/recsys/runs/<run_id>/ (summary.json có modelVersion,
    engineConfig, configHash, vectorsMissing; per_user.jsonl có ids top-k, targetProductId, rankStrict)."""
    from . import data_source
    from .arms import EngineArm, EngineNoMmrArm, MostPopularArm, MostPopularInDestinationArm, RandomArm
    from .bench import aggregate, evaluate
    from .engine import OfflineEngine, config_hash, engine_config
    from .paths import run_dir
    from .report import RunConflict, header, markdown_table, write_run
    from .splits import SplitMismatch

    unknown = set(arms) - {"random", "most_popular", "most_popular_in_destination", "engine", "engine_prod", "engine_nommr"}
    if unknown:
        _fail(f"arm không hỗ trợ: {sorted(unknown)}")
    need_vec = {"engine", "engine_prod", "engine_nommr"} & set(arms)
    mode = vectors or ("weaviate" if need_vec else "none")
    if need_vec and mode == "none":
        _fail("arm engine / engine_prod cần --vectors weaviate hoặc numpy")
    run_id = run_id or f"{datetime.now():%Y%m%d-%H%M%S}-{kind}"
    refresh = refresh or bool(split_file)   # bản đóng băng phải đối chiếu với DB thật, không với cache JSONL (review 01/10)
    try:
        overrides = _parse_overrides(override)
    except ValueError as exc:
        _fail(str(exc))
    with _overridden(overrides), _prepared(as_of, refresh, mode) as (index, vector_search, kept, report, snapshot, _):
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
        if "engine_nommr" in arms:                # pool ứng viên xếp theo score, không MMR: chẩn đoán pool_miss / mmr_demoted
            row, users_rows = evaluate(EngineNoMmrArm(engine), result, index, k, users)
            raw_rows.append(row)
            rows.append(row)
            per_user += users_rows
        cfg = engine_config(engine)
        summary = {"runId": run_id, "modelVersion": index.model_version, "engineConfig": cfg, "configHash": config_hash(cfg),
                   "overrides": overrides,
                   "asOf": snapshot.isoformat(), "k": k, "vectors": mode,
                   "searchUnits": len(index.units), "recommendable": int(index.recommendable.sum()),
                   "vectorsMissing": _vectors_missing(index, vector_search),
                   "limitUsers": limit_users, "usersEvaluated": len(users) if users is not None else len(result.targets),
                   "filter": report.as_dict(),
                   "split": {**{kw: v for kw, v in result.summary().items() if kw != "targets"},
                             "splitSha256": result.frozen_sha256(), "frozenSha256": frozen_sha, "splitFile": split_file},
                   "rows": rows, "rawRows": raw_rows}
        if "engine_prod" in arms:
            cfg_prod = engine_config(prod)
            summary["engineConfigProd"], summary["configHashProd"] = cfg_prod, config_hash(cfg_prod)
    try:
        directory = write_run(run_dir(run_id), summary, per_user, merge=True)   # --run-id đã có → gộp arm mới vào
    except RunConflict as exc:
        _fail(str(exc))
    typer.echo(header(summary))
    for line in report.lines():
        typer.echo(line)
    typer.echo(json.dumps(summary["split"], ensure_ascii=False))
    typer.echo(markdown_table(rows))
    for row in rows:
        if row.get("strategies"):
            typer.echo(f"{row['arm']} strategy: {row['strategies']}")
    typer.echo(f"→ {directory}")


@app.command()
def analyze(run_id: str = typer.Option(..., "--run-id", help="run đã có engine + baseline (per_user.jsonl)"),
            split_file: Optional[str] = typer.Option(None, "--split-file", help="mặc định lấy từ summary.json"),
            base: str = typer.Option("engine", "--base", help="arm bị xét: engine | engine_prod"),
            ref: str = typer.Option("most_popular_in_destination", "--ref", help="baseline đối chiếu"),
            n_cases: int = typer.Option(20, "--cases"),
            refresh: bool = typer.Option(False, "--refresh")):
    """B5–B8: ceiling (trần recall theo bộ lọc engine), phân khúc, strict/lenient theo taxonomy, 20 ca engine trượt mà baseline
    trúng. Đọc `per_user.jsonl` của run + split tính lại từ CDP (đối chiếu bản đóng băng của run); không cần Weaviate.
    Ghi ceiling.json, segments.json/.md, cases.json/.md, strict.md vào thư mục run."""
    from collections import defaultdict

    from .analysis import cases, cases_markdown, segments, segments_markdown, strict_lenient, strict_markdown, user_labels
    from .ceiling import ceiling, ceiling_markdown, engine_view
    from .paths import run_dir
    from .report import read_run
    from .splits import SplitMismatch

    directory = run_dir(run_id)
    summary, rows = read_run(directory)
    if summary is None or not rows:
        _fail(f"{directory}: chưa có summary.json / per_user.jsonl — chạy `run --run-id {run_id}` trước")
    rows_by_arm: dict = defaultdict(dict)
    for r in rows:
        rows_by_arm[r["arm"]][r["user"]] = r
    for arm in (base, ref):
        if arm not in rows_by_arm:
            _fail(f"run {run_id} không có arm {arm} (có: {sorted(rows_by_arm)}) — chạy thêm `run --arm {arm} --run-id {run_id}`")
    sp = summary.get("split") or {}
    kind, k = sp.get("kind", "llbo"), int(summary.get("k") or 20)
    missing = summary.get("vectorsMissing")
    if missing != 0:   # engine bỏ event và không thể trả unit không có vector; ceiling/engine_view coi mọi unit đều có
        _fail(f"run {run_id} có vectorsMissing={missing!r} — ceiling/engine_view giả định mọi unit có vector; chạy index (Weaviate) "
              "rồi chạy lại run, hoặc chạy run với --vectors weaviate để summary có vectorsMissing")
    split_file = split_file or sp.get("splitFile")
    # temporal: run chọn T theo phân vị (quantile != None) thì tính lại theo phân vị để params khớp bản đóng băng;
    # chỉ truyền --T khi run đã dùng T tường minh.
    cutoff = sp.get("T") if kind == "temporal" and sp.get("quantile") is None else None
    with _prepared(summary.get("asOf"), refresh or bool(split_file), "none") as (index, _, kept, _, _, _):
        result = _make_split(kind, kept, index, cutoff, int(sp.get("minPurchases") or 2), int(sp.get("minTrips") or 1))
    if split_file:
        try:
            sha = result.verify(split_file)
        except (SplitMismatch, OSError, KeyError, ValueError, TypeError) as exc:
            _fail(f"--split-file: {exc}")
        if sp.get("frozenSha256") and sha != sp["frozenSha256"]:
            _fail(f"split của run ({sp['frozenSha256'][:12]}) ≠ bản đóng băng {split_file} ({sha[:12]})")
    else:
        typer.echo("cảnh báo: run không có bản đóng băng — split tính lại có thể khác lúc chạy run")
    views = {u: engine_view(result.train_by_user[u], index, result.as_of_by_user[u]) for u in result.targets}
    engine_rows = rows_by_arm.get("engine") or rows_by_arm[base]
    ceil = ceiling(rows_by_arm[base], result, index, views, k=k)
    mpd_row = next((r for r in summary.get("rows", []) if r.get("arm") == ref), None)
    labels = user_labels(result, index, engine_rows, views)
    arms_order = [a for a in ("engine", "engine_prod", "engine_nommr", ref, "most_popular") if a in rows_by_arm and a != ref] + [ref]
    seg = segments({a: rows_by_arm[a] for a in arms_order}, labels, k=k)
    sl = strict_lenient({a: rows_by_arm[a] for a in arms_order if a != "engine_nommr"}, result, index, k=k)
    cs = cases(rows_by_arm, ceil["perUser"], views, result, index, base=base, ref=ref, n=n_cases, k=k)
    (directory / "ceiling.json").write_text(json.dumps({**ceil, "base": base, "vectorsMissing": missing, "assumesAllVectors": True,
                                                        "note": "cold_start = engine đi _cold_start (popular theo điểm đến / mùa), "
                                                                "không mô phỏng — recall của nhóm này có thể vượt ceiling"},
                                                       ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    (directory / "segments.json").write_text(json.dumps({"labels": labels, "segments": seg}, ensure_ascii=False, indent=1), encoding="utf-8")
    (directory / "cases.json").write_text(json.dumps(cs, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    md_ceiling = ceiling_markdown(ceil, mpd_recall=(mpd_row or {}).get(f"recall@{k}"))
    md_seg, md_sl, md_cases = segments_markdown(seg, arms_order, k=k), strict_markdown(sl, [a for a in arms_order if a != "engine_nommr"], k=k), cases_markdown(cs)
    (directory / "segments.md").write_text(md_seg, encoding="utf-8")
    (directory / "strict.md").write_text(md_sl, encoding="utf-8")
    (directory / "cases.md").write_text(md_cases, encoding="utf-8")
    (directory / "ceiling.md").write_text(md_ceiling, encoding="utf-8")
    typer.echo(f"run {run_id} · split {kind} · {len(result.targets)} khách · base {base} · ref {ref}")
    typer.echo("\n## Ceiling\n" + md_ceiling)
    typer.echo("\n## Strict / lenient\n" + md_sl)
    typer.echo("\n## Phân khúc\n" + md_seg)
    typer.echo("\n## 20 ca\n" + md_cases)
    typer.echo(f"→ {directory}")


@app.command()
def sanity(as_json: bool = typer.Option(False, "--json", help="in JSON thay vì bảng"),
           refresh: bool = typer.Option(False, "--refresh", help="đọc lại event và profile, bỏ cache")):
    """B1: kiểm dữ liệu seed trước khi tin số đo — lifecycle 25/45/20/10 và tính lại từ event, chuyến ≥ 2 vertical ≈ 65 %,
    mỗi chuyến 1 điểm đến, cạnh lộn xộn 2 % / 3 %, phổ biến (chỉ báo). Ghi bench_out/recsys/sanity.json; mã 1 khi kiểm tra cứng hỏng."""
    from . import data_source, sanity as S
    from .paths import FROZEN_DIR, recsys_home

    events = data_source.load_events(None, refresh=refresh)
    profiles = data_source.load_profiles(refresh=refresh)
    index, _ = data_source.load_index("none")
    snapshot = data_source.derive_as_of(events)
    checks = S.run_all(profiles, events, index, snapshot, FROZEN_DIR)
    result = {"dsn": data_source.dsn_label(data_source.eval_cdp_url()), "asOf": snapshot.isoformat(), "events": len(events),
              "profiles": len(profiles), "searchUnits": len(index.units), **S.summary(checks)}
    out = recsys_home() / "sanity.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    if as_json:
        typer.echo(json.dumps(result, ensure_ascii=False, indent=1, default=str))
    else:
        typer.echo(f"sanity · {result['dsn']} · as_of {snapshot.date().isoformat()} · {len(events):,} event · {len(profiles):,} profile · "
                   f"{len(index.units):,} search unit")
        typer.echo(S.markdown(checks))
        typer.echo(("PASS" if result["pass"] else f"FAIL: {result['hardFailed']}") + f" → {out}")
    if not result["pass"]:
        raise typer.Exit(1)


@app.command()
def parity(base_url: Optional[str] = typer.Option(None, "--base-url", help="backend local, vd http://127.0.0.1:8000"),
           users: Optional[str] = typer.Option(None, "--users", help="mặc định frozen/users60.json"),
           k: int = typer.Option(5, "--k", help="list production = 5"),
           make_users: bool = typer.Option(False, "--make-users", help="sinh frozen/users60.json (4 persona + 56 khách phân tầng)"),
           seed: int = typer.Option(42, "--seed"),
           token_env: str = typer.Option("AUTH_SERVICE_TOKEN", "--token-env", help="biến môi trường chứa X-Service-Token (không in)"),
           vectors: str = typer.Option("weaviate", "--vectors", help="weaviate | numpy — phải cùng kho với backend đang chạy"),
           popularity_now: Optional[str] = typer.Option(None, "--popularity-now", help="mốc ISO backend dựng bảng phổ biến (lúc "
                                                                                      "khởi động / nạp lại 900 s); mặc định = generatedAt"),
           run_id: Optional[str] = typer.Option(None, "--run-id"),
           refresh: bool = typer.Option(False, "--refresh")):
    """B9: offline = HTTP. `--make-users` ghi frozen/users60.json; không có cờ đó thì gọi backend local
    `/api/v1/internal/recommendations` cho từng khách và so với `OfflineEngine(mode="prod")` tại đúng `generatedAt`.
    Backend phải chạy từ cùng checkout, APP_ENV=development, INTERNAL_API_ENABLED=true, cùng Postgres / Weaviate. Mã 1 khi không 60/60."""
    import os
    from pathlib import Path

    from . import data_source, parity as P
    from .engine import OfflineEngine
    from .paths import FROZEN_DIR, run_dir

    users_path = Path(users) if users else FROZEN_DIR / "users60.json"
    if make_users:
        events = data_source.load_events(None, refresh=refresh)
        snapshot = data_source.derive_as_of(events)
        try:
            payload = P.make_users(events, snapshot, seed=seed, profiles=data_source.load_profiles(refresh=refresh))
        except P.ParityError as exc:
            _fail(str(exc))
        users_path.parent.mkdir(parents=True, exist_ok=True)
        users_path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
        typer.echo(f"{len(payload['users'])} khách (4 persona + {len(payload['users']) - 4} phân tầng {payload['quota']}, tầng theo "
                   f"{payload['stageSource']}, {payload['zeroEventUsers']} khách không có event) → {users_path}")
        return
    if not base_url:
        _fail("cần --base-url (backend local) hoặc --make-users")
    token = os.environ.get(token_env, "")
    if len(token) < 32:
        _fail(f"{token_env} phải có trong môi trường (≥ 32 ký tự) — backend từ chối token ngắn hơn")
    try:
        user_ids = P.load_users(users_path)
    except (P.ParityError, OSError, ValueError) as exc:
        _fail(str(exc))
    run_id = run_id or f"{datetime.now():%Y%m%d-%H%M%S}-parity"
    events = data_source.load_events(None, refresh=refresh)
    index, vector_search = data_source.load_index(vectors)
    try:
        purchases = [e for e in events if e.get("eventName") == "purchase"]
        engine = OfflineEngine(index, vector_search, purchases, candidate_k=data_source.settings().recommend_candidate_k, mode="prod")
        typer.echo(f"parity · {base_url} · {len(user_ids)} khách · k={k} · {data_source.dsn_label(data_source.eval_cdp_url())} · vectors {vectors}")
        try:
            rows = P.parity_http(base_url, user_ids, engine, events, k=k, token=token, popularity_now=_parse_as_of(popularity_now))
        except P.ParityError as exc:
            _fail(str(exc))
    finally:
        if vector_search is not None and hasattr(vector_search, "close"):
            vector_search.close()
    result = P.verdict(rows)
    typer.echo(P.markdown(rows, result, k=k))
    p = P.write_parity(run_dir(run_id), base_url=base_url, rows=rows, result=result,
                       meta={"runId": run_id, "k": k, "users": str(users_path), "vectors": vectors, "modelVersion": index.model_version,
                             "candidateK": engine.candidate_k, "popularK": engine.popular_k, "popularityNow": popularity_now,
                             "note": "bảng phổ biến production neo ở lúc backend khởi động / nạp lại (900 s), offline neo ở --popularity-now "
                                     "(mặc định generatedAt) — khởi động lại backend ngay trước khi đo hoặc truyền mốc khởi động"})
    typer.echo(("PASS" if result["pass"] else "FAIL") + f" {result['equal']}/{result['n']} → {p}")
    if not result["pass"]:
        raise typer.Exit(1)


#: Hằng của profile.py được đọc lúc gọi (module global) nên ghi đè được trong tiến trình; MAX_PER_VERTICAL bị bind làm mặc định
#: tham số lúc định nghĩa class nên không nằm trong danh sách (dùng mode eval/prod).
OVERRIDABLE = ("W_TYPE", "H_SHORT_DAYS", "H_LONG_DAYS", "ACTIVE_TRIP_MAX_AGE_DAYS", "DORMANT_AFTER_DAYS", "MAX_REPEAT_PER_TRIP",
               "W_SHORT", "W_POP", "W_LONG", "MMR_LAMBDA")


def _parse_overrides(items: List[str]) -> dict:
    """`KEY=VALUE` → {KEY: value} với kiểu theo hằng gốc (int / float / dict JSON)."""
    from src.backend.app.domain.recommendation import profile
    out = {}
    for item in items:
        if "=" not in item:
            raise ValueError(f"--override phải là KEY=VALUE, gặp {item!r}")
        key, raw = item.split("=", 1)
        key = key.strip()
        if key not in OVERRIDABLE:
            raise ValueError(f"--override {key}: chỉ nhận {', '.join(OVERRIDABLE)}")
        current = getattr(profile, key)
        try:
            if isinstance(current, dict):
                value = json.loads(raw)
                if not isinstance(value, dict):
                    raise ValueError
            elif isinstance(current, bool):
                raise ValueError
            elif isinstance(current, int):
                value = int(raw)
            else:
                value = float(raw)
        except ValueError:
            raise ValueError(f"--override {key}: giá trị {raw!r} không hợp kiểu {type(current).__name__}") from None
        out[key] = value
    return out


@contextmanager
def _overridden(overrides: dict):
    """Đặt hằng của `profile.py` trong tiến trình này rồi trả lại nguyên trạng — production không đổi."""
    from src.backend.app.domain.recommendation import profile
    saved = {k: getattr(profile, k) for k in overrides}
    for k, v in overrides.items():
        setattr(profile, k, v)
    try:
        yield
    finally:
        for k, v in saved.items():
            setattr(profile, k, v)


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
