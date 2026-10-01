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
    python -m src.evaluation.recsys_bench compare --run-id <run> --base engine --ref most_popular_in_destination   # Δ hit@k / NDCG + CI95 bootstrap (Day 4 R6)
    python -m src.evaluation.recsys_bench report --run-id <run> [--run-id <run2>] [--out <file.md>]   # markdown gộp bảng + ceiling / phân khúc / so cặp (Day 4 R6)
    python -m src.evaluation.recsys_bench run --algos src/evaluation/recsys_bench/algos_v1.yaml --mode funnel --split llbo --vectors numpy --split-file …   # R3–R5: registry scorer qua funnel chung
    python -m src.evaluation.recsys_bench regress --run-id <run> [--ref-run-id 2026-10-01-llbo-v5] --base content_profile+mmr --ref engine   # R4 gate: ids theo khách 100 %
    python -m src.evaluation.recsys_bench baseline --run-id <run gate-numpy> --note "…"   # Day 5: ghi frozen/baseline_v1-<split>-asof<YYYYMMDD>.json
    python -m src.evaluation.recsys_bench regress --run-id <run mới> --baseline auto      # Day 5: so với baseline_v1 (mã 0/1/2/3)

Mã thoát: 0 ok (regress --baseline: PASS/WARN) · 1 lỗi môi trường/dữ liệu hoặc regress FAIL · 2 regress --baseline: không so được
(meta / arm / khách khác baseline) · 3 regress --baseline: INCONCLUSIVE (arm canary đổi — môi trường khác). Số đo và giới hạn:
`docs/spec/bench/recsys-offline-eval.md`.
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
def run(arms: List[str] = typer.Option([], "--arm", help="random | most_popular | most_popular_in_destination | "
                                                           "engine (mode eval, đủ k món) | engine_prod (cap 2 / taxonomy) | "
                                                           "engine_nommr (pool 200 theo score, không MMR — chẩn đoán); mặc định random "
                                                           "khi không có --algos"),
        algos: Optional[str] = typer.Option(None, "--algos", help="algos_v1.yaml — registry scorer (R3–R5, spec recsys-algos-v1); "
                                                                   "bắt buộc --vectors numpy|weaviate"),
        algo_mode: str = typer.Option("funnel", "--mode", help="funnel (mask engine) | raw (recommendable trừ đã mua) — chỉ với --algos"),
        only: List[str] = typer.Option([], "--only", help="chỉ chạy các algo này (lặp cờ); không có → mọi algo tier ≤ --max-tier, status run"),
        max_tier: int = typer.Option(1, "--max-tier"),
        funnel_pool: Optional[str] = typer.Option(None, "--funnel-pool", help="engine | mask — ghi đè common.funnel.pool (gate dùng engine)"),
        funnel_rerank: List[str] = typer.Option([], "--funnel-rerank", help="none | mmr (lặp cờ) — ghi đè common.funnel.rerank"),
        because_k: int = typer.Option(0, "--because-k", help="--algos: ghi because[] cho top-K mỗi khách (K = 5, 10, 15, 20 …; 0 = tắt; "
                                                             "≤ --k) + cột Because@K / Vi phạm because — không đổi ids, không vào algosHash"),
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
    from .ceiling import engine_view
    from .engine import OfflineEngine, config_hash, engine_config
    from .paths import run_dir
    from .report import RunConflict, footnote, header, markdown_table, read_run, write_run
    from .splits import SplitMismatch

    if not arms and not algos:
        arms = ["random"]
    unknown = set(arms) - {"random", "most_popular", "most_popular_in_destination", "engine", "engine_prod", "engine_nommr"}
    if unknown:
        _fail(f"arm không hỗ trợ: {sorted(unknown)}")
    # --algos: nạp + validate YAML, kiểm thư viện TRƯỚC khi chạm DB (lỗi cấu hình → mã 1 ngay)
    algos_cfg = specs = None
    reranks: List[str] = []
    if algos:
        from .models.funnel import MODES, POOLS, RERANKS
        from .models.registry import AlgosError, load_algos, missing_libs, rerank_list, select
        try:
            algos_cfg = load_algos(algos)
            if algo_mode not in MODES:
                raise AlgosError(f"--mode {algo_mode!r}: chỉ {MODES}")
            if funnel_pool and funnel_pool not in POOLS:
                raise AlgosError(f"--funnel-pool {funnel_pool!r}: chỉ {POOLS}")
            reranks = list(dict.fromkeys(funnel_rerank or rerank_list(algos_cfg.common.funnel)))
            bad = [r for r in reranks if r not in RERANKS]
            if bad:
                raise AlgosError(f"--funnel-rerank {bad}: chỉ {RERANKS}")
            specs = select(algos_cfg, only or None, max_tier)
            if not specs:
                raise AlgosError("--algos: không có algo nào được chọn (kiểm --only / --max-tier / status)")
            missing = missing_libs(specs)
            if missing:
                raise AlgosError(f"thiếu thư viện cho {missing} — pip install -r src/evaluation/requirements.txt, hoặc --only bỏ các algo này")
        except AlgosError as exc:
            _fail(str(exc))
    if because_k < 0 or because_k > k:
        _fail(f"--because-k {because_k}: phải trong [0, --k = {k}]")
    if because_k and not algos:
        _fail("--because-k chỉ dùng với --algos (arm registry)")
    need_vec = bool({"engine", "engine_prod", "engine_nommr"} & set(arms)) or algos is not None
    mode = vectors or ("weaviate" if need_vec else "none")
    if need_vec and mode == "none":
        _fail("arm engine / engine_prod / --algos cần --vectors weaviate hoặc numpy")
    run_id_given = run_id
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
        # chuyến mở tại as_of của từng khách (cùng luật engine; bỏ unit chưa có vector như engine) → hai cột cross-cat chuyến mở (R2)
        vector_ids = _vector_ids(index, vector_search)
        views = {u: engine_view(result.train_by_user[u], index, result.as_of_by_user[u], has_vector=vector_ids)
                 for u in (users if users is not None else sorted(result.targets))}
        # popularity của baseline và engine cùng nguồn: purchase < as_of của từng khách (OfflineEngine.popularity_at)
        engine = OfflineEngine(index, vector_search, result.train_purchases,
                               candidate_k=data_source.settings().recommend_candidate_k)
        if "random" in arms:
            seed_rows = []
            for seed in (int(x) for x in seeds.split(",") if x.strip()):
                row, users_rows = evaluate(RandomArm(index, seed), result, index, k, users, views=views)
                seed_rows.append(row)
                per_user += users_rows
            raw_rows += seed_rows
            rows.append(aggregate(seed_rows))
        for name, cls in (("most_popular", MostPopularArm), ("most_popular_in_destination", MostPopularInDestinationArm)):
            if name in arms:
                row, users_rows = evaluate(cls(index, engine), result, index, k, users, views=views)
                raw_rows.append(row)
                rows.append(row)
                per_user += users_rows
        if "engine" in arms:                      # mode eval: bỏ cap 2 món / taxonomy để đủ k món (quyết định 30/09)
            row, users_rows = evaluate(EngineArm(engine), result, index, k, users, views=views)
            raw_rows.append(row)
            rows.append(row)
            per_user += users_rows
        if "engine_prod" in arms:                 # đúng list production (cap MAX_PER_VERTICAL): khách thật sự thấy gì
            prod = OfflineEngine(index, vector_search, result.train_purchases,
                                 candidate_k=data_source.settings().recommend_candidate_k, mode="prod")
            row, users_rows = evaluate(EngineArm(prod), result, index, k, users, views=views)
            raw_rows.append(row)
            rows.append(row)
            per_user += users_rows
        if "engine_nommr" in arms:                # pool ứng viên xếp theo score, không MMR: chẩn đoán pool_miss / mmr_demoted
            row, users_rows = evaluate(EngineNoMmrArm(engine), result, index, k, users, views=views)
            raw_rows.append(row)
            rows.append(row)
            per_user += users_rows
        cfg = engine_config(engine)
        algo_summary: dict = {}
        expect_failed: list[dict] = []
        if algos_cfg is not None:                 # R3–R5: registry scorer qua funnel chung (models/)
            from .engine import LeakageError
            from .models.data import assert_no_leak, build
            from .models.funnel import CtxCache
            from .models.registry import algos_hash, build_arms, lib_versions
            from .models.regress import compare_ids, ids_by_arm
            libs = lib_versions()
            ah = algos_hash(algos_cfg, specs, cfg, mode=algo_mode, reranks=reranks, pool=funnel_pool, k=k, libs=libs)
            if not run_id_given:
                run_id = f"{run_id}-{ah}"
            data = build(kept, result, index, vector_search, algos_cfg.common.matrix)
            try:
                leak = assert_no_leak(data, result)
            except LeakageError as exc:
                _fail(str(exc))
            ctx_cache = CtxCache(data, engine)
            try:
                built = build_arms(algos_cfg, specs, mode=algo_mode, reranks=reranks, pool=funnel_pool, k=k, ctx=ctx_cache,
                                   vector_search=vector_search, because_k=because_k)
            except Exception as exc:  # noqa: BLE001 — AlgosError / ValueError của scorer
                _fail(str(exc))
            fit_log: dict = {}
            family_rows: dict[str, list[dict]] = {}
            for spec, scorer, algo_arms in built:
                t0 = perf_counter()
                try:
                    log = scorer.fit(data)
                except RuntimeError as exc:
                    _fail(f"algos.{spec.name}: {exc}")
                fit_seconds = perf_counter() - t0
                fit_log.setdefault(spec.name, []).append({**log, "fitSeconds": round(fit_seconds, 3), "seed": getattr(scorer, "seed", None)})
                typer.echo(f"fit {spec.name}{f' seed {scorer.seed}' if getattr(scorer, 'seed', None) is not None else ''}: {fit_seconds:.1f} s", err=True)
                for arm in algo_arms:
                    row, users_rows = evaluate(arm, result, index, k, users, views=views)
                    row.update({"fit_seconds": fit_seconds, "params": spec.params, "tier": spec.tier, "algo": spec.name,
                                "funnel": arm.cfg.as_dict()})
                    if because_k:
                        row["because_k"] = because_k
                        unmapped = getattr(scorer, "because_unmapped", None)
                        if unmapped is not None:
                            row["because_unmapped"] = unmapped
                    family_rows.setdefault(arm.family, []).append(row)
                    per_user += users_rows
            by_arm = ids_by_arm(per_user)
            expectations = {}
            for spec in specs:
                if not spec.expect_equal_to:
                    continue
                for r in reranks:
                    suffix = "+mmr" if r == "mmr" else ""
                    target = spec.expect_equal_to
                    ref_arm = (target + suffix) if target in algos_cfg.algos else ("engine" if r == "mmr" else "engine_nommr")
                    base_arm = spec.name + suffix
                    if base_arm not in by_arm or ref_arm not in by_arm:
                        expectations[base_arm] = {"ref": ref_arm, "skipped": "arm tham chiếu không có trong run"}
                        continue
                    res = compare_ids(by_arm[base_arm], by_arm[ref_arm], k=k)
                    expectations[base_arm] = {"ref": ref_arm, **{kw: v for kw, v in res.items() if kw != "mismatches"},
                                              "examples": res["mismatches"][:5]}
                    if not res["pass"]:
                        expect_failed.append({"arm": base_arm, "ref": ref_arm, "equal": res["equal"], "n": res["n"], "examples": res["mismatches"][:5]})
            dropped = {f["arm"].split("+")[0] for f in expect_failed}
            for family, frows in family_rows.items():
                if family.split("+")[0] in dropped:
                    continue
                raw_rows += frows
                rows.append(aggregate(frows) if len(frows) > 1 else frows[0])
            if dropped:
                per_user = [r for r in per_user if r["arm"].split("+")[0].split("-s")[0] not in dropped]
            algo_summary = {"algosFile": algos_cfg.source, "algosHash": ah, "algoMode": algo_mode,
                            "funnel": {"pool": funnel_pool or algos_cfg.common.funnel.get("pool", "mask"), "reranks": reranks},
                            "algosConfig": {**algos_cfg.resolved(), "selected": [s.name for s in specs]},
                            "fitLog": fit_log, "matrixStats": data.stats, "leakCheck": leak, "libs": libs,
                            "expectations": expectations, "expectFailed": expect_failed}
            if because_k:
                algo_summary["because"] = {"k": because_k, "rules": "popular ⟹ [], coldStart ⟹ [], dormant ⟹ ∃ daysAgo > 90 (contract)"}
        summary = {"runId": run_id, "modelVersion": index.model_version, "engineConfig": cfg, "configHash": config_hash(cfg),
                   "overrides": overrides,
                   "asOf": snapshot.isoformat(), "k": k, "vectors": mode,
                   "searchUnits": len(index.units), "recommendable": int(index.recommendable.sum()),
                   "vectorsMissing": None if vector_ids is None else len(index.units) - len(vector_ids),
                   "limitUsers": limit_users, "usersEvaluated": len(users) if users is not None else len(result.targets),
                   "filter": report.as_dict(),
                   "split": {**{kw: v for kw, v in result.summary().items() if kw != "targets"},
                             "splitSha256": result.frozen_sha256(), "frozenSha256": frozen_sha, "splitFile": split_file},
                   "rows": rows, "rawRows": raw_rows}
        if "engine_prod" in arms:
            cfg_prod = engine_config(prod)
            summary["engineConfigProd"], summary["configHashProd"] = cfg_prod, config_hash(cfg_prod)
        # provenance (Day 4 R6): commit + tham số của lượt này; `merge_run` nối `history`, `gitDescribe` là của lượt mới nhất
        git_describe = _git_describe()
        summary["openTripAssumesAllVectors"] = vector_ids is None
        summary["gitDescribe"] = git_describe
        summary["history"] = [{"at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "gitDescribe": git_describe,
                               "arms": list(arms) + ([f"algos:{s.name}" for s in specs] if specs else []),
                               "params": {"split": kind, "k": k, "seeds": seeds, "vectors": mode, "splitFile": split_file,
                                          "overrides": overrides, "limitUsers": limit_users, "asOf": as_of,
                                          "algos": algos, "algoMode": algo_mode if algos else None, "only": list(only),
                                          "funnelPool": funnel_pool, "funnelRerank": reranks, "becauseK": because_k}}]
        summary.update(algo_summary)
    try:
        directory = write_run(run_dir(run_id), summary, per_user, merge=True)   # --run-id đã có → gộp arm mới vào
    except RunConflict as exc:
        _fail(str(exc))
    for failed in expect_failed:
        typer.secho(f"expect_equal_to THẤT BẠI: {failed['arm']} ≠ {failed['ref']} ({failed['equal']}/{failed['n']} khách khớp) — "
                    f"bỏ mọi hàng của {failed['arm'].split('+')[0]} khỏi bảng; ví dụ: {failed['examples'][:2]}", fg=typer.colors.RED, err=True)
    written, _ = read_run(directory)
    describes = {str(h.get("gitDescribe")) for h in (written or {}).get("history", [])}
    if len(describes) > 1:
        typer.secho(f"cảnh báo: run {run_id} gộp arm từ nhiều commit {sorted(describes)} — cùng configHash nên vẫn so được, "
                    "nhưng ghi rõ khi trích", fg=typer.colors.YELLOW, err=True)
    typer.echo(header(summary))
    for line in report.lines():
        typer.echo(line)
    typer.echo(json.dumps(summary["split"], ensure_ascii=False))
    typer.echo(markdown_table(rows))
    if footnote(rows):
        typer.echo(footnote(rows))
    for row in rows:
        if row.get("strategies"):
            typer.echo(f"{row['arm']} strategy: {row['strategies']}")
    typer.echo(f"→ {directory}")
    if expect_failed:
        raise typer.Exit(1)


@app.command()
def baseline(run_id: str = typer.Option(..., "--run-id", help="run nguồn — mặc định run gate `<ngày>-<split>-gate-numpy` (pool engine, numpy)"),
             note: str = typer.Option(..., "--note", help="bắt buộc: vì sao ghi (mốc, run, entry history)"),
             arm: List[str] = typer.Option([], "--arm", help="chỉ các arm này (lặp cờ); mặc định mọi arm trong run"),
             role: List[str] = typer.Option([], "--role", help="ARM=primary|scorer|canary (lặp cờ) — ghi đè vai trò mặc định"),
             out: Optional[str] = typer.Option(None, "--out", help="mặc định frozen/baseline_v1-<split>-asof<YYYYMMDD>.json (commit)"),
             with_ids: bool = typer.Option(False, "--with-ids", help="lưu đủ ids[:k] theo khách cho arm primary (file lớn hơn)"),
             force: bool = typer.Option(False, "--force", help="đè baseline đã có với fingerprint khác / nhận run gộp nhiều lượt")):
    """Day 5: ghi baseline_v1 (metric + idsSha256 + rank theo khách + nhãn phân khúc của `analyze` + cặp G1/G2) từ một run đủ khách,
    split đóng băng. Ghi lại cùng run → không đổi file. Không cần DB / Weaviate."""
    from .models import baseline as BL
    from .paths import run_dir
    from .report import read_run

    directory = run_dir(run_id)
    summary, rows = read_run(directory)
    if summary is None or not rows:
        _fail(f"{directory}: chưa có summary.json / per_user.jsonl")
    roles = {}
    for item in role:
        name, _, value = item.partition("=")
        if not value:
            _fail(f"--role {item!r}: dạng ARM=primary|scorer|canary")
        roles[name] = value
    seg = directory / "segments.json"
    labels = json.loads(seg.read_text(encoding="utf-8")).get("labels") if seg.exists() else None
    if labels is None:
        typer.secho("cảnh báo: run chưa có segments.json (chạy analyze trước) — baseline không có nhãn phân khúc, regress bỏ luật slice",
                    fg=typer.colors.YELLOW, err=True)
    try:
        doc = BL.build(summary, rows, labels, note=note, arms=list(arm) or None, roles=roles, with_ids=with_ids,
                       git_describe=summary.get("gitDescribe"), force=force)
        target = Path(out) if out else BL.default_path(summary)
        state = BL.write(doc, target, force=force)
    except BL.BaselineError as exc:
        _fail(str(exc))
    arms_text = ", ".join(f"{name}:{entry['role']}" for name, entry in doc["arms"].items())
    typer.echo(f"baseline {state}: {target} · fingerprint {doc['fingerprint'][:12]} · run {run_id} · {len(doc['arms'])} arm ({arms_text})")


@app.command()
def regress(run_id: str = typer.Option(..., "--run-id", help="run có arm --base"),
            ref_run_id: Optional[str] = typer.Option(None, "--ref-run-id", help="run có arm --ref; mặc định cùng run"),
            base: str = typer.Option("content_profile+mmr", "--base", help="arm bị xét (vd content_profile+mmr, star_blend_a1)"),
            ref: str = typer.Option("engine", "--ref", help="arm tham chiếu (vd engine, engine_nommr, content_profile)"),
            k: int = typer.Option(20, "--k"),
            tie_tolerant: bool = typer.Option(False, "--tie-tolerant", help="khớp theo tập (bỏ qua hoà điểm) thay vì theo thứ tự"),
            baseline_path: Optional[str] = typer.Option(None, "--baseline", help="auto | đường dẫn baseline_v1-*.json — so cả run với "
                                                                                 "baseline (bỏ --base/--ref/--ref-run-id)"),
            allow_subset: bool = typer.Option(False, "--allow-subset", help="--baseline: cho phép run subset / thiếu arm (WARN)"),
            max_drop: Optional[float] = typer.Option(None, "--max-drop", help="--baseline: điểm tụt tối đa (mặc định của baseline, 1,0)"),
            min_users_drop: Optional[int] = typer.Option(None, "--min-users-drop"),
            p_max: Optional[float] = typer.Option(None, "--p-max"),
            max_slice_drop: Optional[float] = typer.Option(None, "--max-slice-drop"),
            min_slice_n: Optional[int] = typer.Option(None, "--min-slice-n")):
    """R4 gate G1/G2: so `ids[:k]` theo khách của hai arm (cùng run hoặc hai run — vd với run v5 `2026-10-01-llbo-v5`). Cảnh báo khi
    hai run khác configHash / frozenSha256 / vectors. 100 % khớp → mã 0, khác → mã 1. Không cần DB / Weaviate.

    `--baseline auto|PATH` (Day 5): so mọi arm của baseline_v1 với run — mã 0 PASS/WARN · 1 FAIL · 2 không so được · 3 INCONCLUSIVE."""
    from .models.regress import compare_ids, ids_by_arm, markdown
    from .paths import run_dir
    from .report import read_run

    summary_a, rows_a = read_run(run_dir(run_id))
    if summary_a is None or not rows_a:
        _fail(f"{run_dir(run_id)}: chưa có summary.json / per_user.jsonl")
    if baseline_path:
        _regress_baseline(run_id, summary_a, rows_a, baseline_path, k=k, allow_subset=allow_subset,
                          thresholds={"maxDropPoints": max_drop, "minUsersDrop": min_users_drop, "pMax": p_max,
                                      "maxSliceDropPoints": max_slice_drop, "minSliceN": min_slice_n})
        return
    if ref_run_id and ref_run_id != run_id:
        summary_b, rows_b = read_run(run_dir(ref_run_id))
        if summary_b is None or not rows_b:
            _fail(f"{run_dir(ref_run_id)}: chưa có summary.json / per_user.jsonl")
        for key, get in (("configHash", lambda s: s.get("configHash")), ("frozenSha256", lambda s: (s.get("split") or {}).get("frozenSha256")),
                         ("vectors", lambda s: s.get("vectors")), ("k", lambda s: s.get("k"))):
            if get(summary_a) != get(summary_b):
                typer.secho(f"cảnh báo: hai run khác {key}: {get(summary_a)!r} vs {get(summary_b)!r}", fg=typer.colors.YELLOW, err=True)
    else:
        rows_b = rows_a
    a, b = ids_by_arm(rows_a), ids_by_arm(rows_b)
    for name, src in ((base, a), (ref, b)):
        if name not in src:
            _fail(f"không có arm {name!r} (có: {sorted(src)})")
    result = compare_ids(a[base], b[ref], k=k, tie_tolerant=tie_tolerant)
    typer.echo(markdown(result, base, ref))
    out = run_dir(run_id) / f"regress-{base}-vs-{ref}{'@' + ref_run_id if ref_run_id and ref_run_id != run_id else ''}.json"
    out.write_text(json.dumps({"runId": run_id, "refRunId": ref_run_id, "base": base, "ref": ref, **result}, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    typer.echo(f"→ {out}", err=True)
    if not result["pass"]:
        raise typer.Exit(1)


def _regress_baseline(run_id: str, summary: dict, rows: list[dict], baseline_path: str, *, k: int, allow_subset: bool,
                      thresholds: dict) -> None:
    from .models import baseline as BL
    from .paths import run_dir

    path = BL.default_path(summary) if baseline_path == "auto" else Path(baseline_path)
    if not path.exists():
        typer.secho(f"không có baseline {path} — ghi bằng `baseline --run-id <run gate> --note …`", fg=typer.colors.RED, err=True)
        raise typer.Exit(2)
    try:
        doc = BL.load(path)
        if k != int(doc["meta"].get("k") or 20):
            raise BL.NotComparable(f"--k {k} ≠ k của baseline {doc['meta'].get('k')}")
        result = BL.check(doc, summary, rows, allow_subset=allow_subset, git_describe=summary.get("gitDescribe"), thresholds=thresholds)
    except BL.NotComparable as exc:
        typer.secho(f"regress --baseline: KHÔNG SO ĐƯỢC — {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(2)
    text = BL.markdown(result)
    typer.echo(text)
    directory = run_dir(run_id)
    (directory / "regress-baseline.json").write_text(json.dumps({"baselineFile": str(path), **result}, ensure_ascii=False, indent=1,
                                                                default=str), encoding="utf-8")
    (directory / "regress-baseline.md").write_text(f"Baseline: `{path.name}`\n\n{text}\n", encoding="utf-8")
    typer.echo(f"→ {directory / 'regress-baseline.md'}", err=True)
    if result["exit"]:
        raise typer.Exit(result["exit"])


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
    arms_order = [a for a in ("engine", "engine_prod", "engine_nommr", ref, "most_popular") if a in rows_by_arm and a != ref]
    arms_order += sorted(a for a in rows_by_arm if a not in arms_order and a != ref and not a.startswith("random"))   # scorer registry
    arms_order += [ref]
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


def _vector_ids(index, vector_search) -> Optional[set]:
    """productId của search unit có vector đúng model trong kho (engine bỏ event của unit khác) — None khi kho không khai
    metadata (coi mọi unit đều có, như `analyze`). Dùng cho `vectorsMissing` và `has_vector` của `engine_view` (R2)."""
    unit_ids = {p.product_id for p in index.units}
    metadata = getattr(vector_search, "metadata", None)
    if metadata is None:
        ids = getattr(vector_search, "ids", None)          # NumpyVectorSearch: ids = unit có vector đúng model
        return None if ids is None else unit_ids & set(ids)
    try:
        have = metadata([p.product_id for p in index.units])
    except Exception:  # noqa: BLE001 — chỉ là số phụ trong summary
        return None
    return {pid for pid in unit_ids if pid in have and have[pid].model_version == index.model_version}


def _vectors_missing(index, vector_search) -> Optional[int]:
    """Số search unit không có vector đúng model trong kho — None khi kho không khai metadata."""
    ids = _vector_ids(index, vector_search)
    return None if ids is None else len(index.units) - len(ids)


def _git_describe() -> Optional[str]:
    """`git describe --tags --always --dirty` của checkout đang chạy (provenance trong summary.json); không có git → None."""
    import subprocess

    from .paths import repo_root
    try:
        r = subprocess.run(["git", "describe", "--tags", "--always", "--dirty"], cwd=repo_root(), capture_output=True,
                           text=True, timeout=5, check=False)
    except Exception:  # noqa: BLE001 — máy không có git / không phải repo: run vẫn phải chạy
        return None
    return (r.stdout.strip() or None) if r.returncode == 0 else None


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
              "destination": r["destination"], "because": len(r.get("because") or []),
              "becauseDaysAgo": [b.get("daysAgo") for b in (r.get("because") or [])]}
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
    if cdp_user_id == "VP0000003":   # P3 dormant (MOCK_DATA_SPEC: chuyến cuối as_of − 190) — kiểm sau M6 (Day 4 R7)
        from src.backend.app.domain.recommendation import profile
        diagnostics = response.get("diagnostics") or {}
        days = [d for i in items for d in i["becauseDaysAgo"] if d is not None]
        out["p3Check"] = {
            "strategy == dormant": response.get("strategy") == "dormant",
            "excludedVerticals == []": diagnostics.get("excludedVerticals") == [],
            "coldStart == False": diagnostics.get("coldStart") is False,
            f"because có và mọi daysAgo > DORMANT_AFTER_DAYS ({profile.DORMANT_AFTER_DAYS})":
                bool(days) and all(d > profile.DORMANT_AFTER_DAYS for d in days),
        }
    typer.echo(json.dumps(out, ensure_ascii=False, indent=2))


@app.command()
def compare(run_id: str = typer.Option(..., "--run-id", help="run đã có per_user.jsonl của cả hai arm"),
            base: str = typer.Option("engine", "--base", help="arm bị xét (Δ = base − ref)"),
            ref: str = typer.Option("most_popular_in_destination", "--ref", help="baseline đối chiếu; random là random-s<seed>"),
            n_boot: int = typer.Option(10_000, "--n-boot"),
            seed: int = typer.Option(42, "--seed")):
    """Day 4 R6: so cặp arm trên cùng run — Δ hit@5/10/20 và NDCG@5/10 theo khách (điểm phần trăm), CI95 paired bootstrap,
    p một phía. Ghi compare-<base>-vs-<ref>.json/.md vào thư mục run; không cần DB / Weaviate."""
    from collections import defaultdict

    from . import compare as C
    from .paths import run_dir
    from .report import read_run

    directory = run_dir(run_id)
    summary, rows = read_run(directory)
    if summary is None or not rows:
        _fail(f"{directory}: chưa có summary.json / per_user.jsonl — chạy `run --run-id {run_id}` trước")
    rows_by_arm: dict = defaultdict(dict)
    for r in rows:
        rows_by_arm[r["arm"]][r["user"]] = r
    try:
        result = C.compare_arms(rows_by_arm, base, ref, n_boot=n_boot, seed=seed)
    except C.CompareError as exc:
        _fail(str(exc))
    result = {"runId": run_id, "configHash": summary.get("configHash"), "split": (summary.get("split") or {}).get("kind"),
              "frozenSha256": (summary.get("split") or {}).get("frozenSha256"), **result}
    stem = f"compare-{base}-vs-{ref}"
    (directory / f"{stem}.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    md = C.compare_markdown(result)
    (directory / f"{stem}.md").write_text(md + "\n", encoding="utf-8")
    if result["usersOnlyOneArm"]:
        typer.secho(f"cảnh báo: {result['usersOnlyOneArm']} khách chỉ có ở một arm — hai arm không cùng tập khách?", fg=typer.colors.YELLOW, err=True)
    typer.echo(f"run {run_id} · {base} vs {ref} · n {result['n']}")
    typer.echo(md)
    typer.echo(f"→ {directory / (stem + '.md')}")


@app.command()
def report(run_ids: List[str] = typer.Option(..., "--run-id", help="một hoặc nhiều run đã có summary.json (lặp cờ)"),
           out: Optional[str] = typer.Option(None, "--out", help="ghi thêm bản gộp mọi run ra file này (bản nháp report)")):
    """Day 4 R6: sinh markdown của run từ summary.json + ceiling.md / segments.md / strict.md / compare-*.md nếu đã có (sau
    `analyze` / `compare`); ghi report.md vào từng thư mục run và in ra; không tính lại gì, không cần DB / Weaviate."""
    from . import report as R
    from .paths import run_dir

    blocks = []
    for rid in run_ids:
        d = run_dir(rid)
        summary, _ = R.read_run(d)
        if summary is None:
            _fail(f"{d}: chưa có summary.json — chạy `run --run-id {rid}` trước")
        extras = {}
        for title, name in (("Ceiling", "ceiling.md"), ("Phân khúc", "segments.md"), ("Strict / lenient", "strict.md")):
            if (d / name).exists():
                extras[title] = (d / name).read_text(encoding="utf-8")
        for p in sorted(d.glob("compare-*.md")):
            extras[f"So cặp {p.stem[len('compare-'):]}"] = p.read_text(encoding="utf-8")
        md = R.run_markdown(summary, extras)
        (d / "report.md").write_text(md + "\n", encoding="utf-8")
        blocks.append(md)
        typer.echo(f"→ {d / 'report.md'}", err=True)
    text = "\n\n".join(blocks) + "\n"
    if out:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(text, encoding="utf-8")
        typer.echo(f"→ {out}", err=True)
    typer.echo(text)


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
