"""Part 8 — chạy arm trên gold: truy xuất top-k cho từng câu, chấm bằng `metrics`, ghi `runs/<run_id>/<arm>/`.

Mỗi arm chạy trên **một** gold đã có version (spec §1.5: `gold.jsonl` phải khớp một tag `gold_v*`; `--allow-untagged`
chỉ để chạy thử — kết quả ghi `gold_version: null`, không được trích dẫn hay promote). Gold nằm ngoài `gold/` (fixture,
file thử) được ghi `fixture:<sha8>`.

Đầu ra (spec §1.4): `results.json` (arm, stage, parent, run_id, gold_version, gold_sha256, resolved_config_hash, stale,
model, text_variant, collection, overall, by_slice, n_queries, n_defined, latency_ms, cost_usd, vs_parent, embed) và
`per_query.parquet` (mỗi câu một dòng, **luôn giữ `top_ids`** để `rescore` tính lại khi gold thêm nhãn — Part 11).

Store và embedder được tiêm vào (`retrieve`) như `gold.build_pool`, nên test chạy bằng bản giả không cần Weaviate.
Cách truy xuất hôm nay: `dense` (có `cutoff.max_vector_distance`, filter của gold khi `filters.qu`), `bm25`; `hybrid` và
`dense+query_vec` báo `RunnerError` cho tới khi cài (P7).
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Any, Callable

import numpy as np
import pandas as pd

from . import catalog, metrics as M, paths
from .arms import Arm
from .config import SBenchConfig
from .gold import load_key_index
from .gold_schema import file_sha256
from .store import filters as F

RESULTS = "results.json"
PER_QUERY = "per_query.parquet"
# trường của arm quyết định hành vi truy xuất — id / stage / description / parent không đổi kết quả nên không vào hash
BEHAVIOUR_FIELDS = ("text_variant", "model", "embedding_types", "query_input_type", "retrieval", "query_vec", "fusion",
                    "bm25", "filters", "boost", "dedupe_parent", "query_preproc", "cutoff", "csls", "rerank",
                    "fallback_bm25_only", "phase", "engine", "app")


class RunnerError(RuntimeError):
    pass


# ------------------------------------------------------------------ môi trường một lượt chạy
@dataclass
class RunEnv:
    cfg: SBenchConfig
    dataset: str
    run_id: str
    gold_path: Path
    gold_version: str | None
    gold_sha256: str
    gold: list[M.GoldQuery]
    ctx: M.EvalContext
    n_items: int

    @property
    def k(self) -> int:
        return self.cfg.metrics.k


def git_short_sha() -> str:
    try:
        r = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=paths.repo_root(), capture_output=True, text=True,
                           timeout=5)
        return r.stdout.strip() or "nogit"
    except Exception:  # noqa: BLE001 — không có git thì run_id vẫn dùng được
        return "nogit"


def new_run_id(now: datetime | None = None) -> str:
    """`<YYYYMMDD-HHMM>-<git sha>` (spec §1.3)."""
    return f"{(now or datetime.now()):%Y%m%d-%H%M}-{git_short_sha()}"


def config_hash(arm: Arm) -> str:
    """sha1 của các trường hành vi (đã giải) — đổi cấu hình thì hash đổi, kết quả cũ thành stale (spec Part 8)."""
    payload = {f: getattr(arm, f) for f in BEHAVIOUR_FIELDS}
    return hashlib.sha1(json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")).hexdigest()


def gold_version_for(gold_path: Path, *, allow_untagged: bool) -> str | None:
    """Version của gold theo spec §1.5; gold ngoài `gold/` → `fixture:<sha8>` (chạy thử, không promote được)."""
    from .holes import gold_version_of
    p = gold_path.resolve()
    if p.parent != paths.GOLD_DIR.resolve():
        return f"fixture:{file_sha256(p)[:8]}"
    ver = gold_version_of(p)
    if ver is None and not allow_untagged:
        raise RunnerError(f"{gold_path} không khớp tag gold_v* nào — commit + `git tag gold_vN` trước (spec §1.5), hoặc "
                          "--allow-untagged để chạy thử (kết quả không được trích dẫn / promote)")
    return ver


def load_env(cfg: SBenchConfig, dataset: str, gold_path: Path, *, run_id: str, allow_untagged: bool = False) -> RunEnv:
    if not gold_path.exists():
        raise RunnerError(f"không thấy gold {gold_path} — chạy `sb gold import` trước")
    items = catalog.read_items(dataset).set_index("product_id", drop=False)
    key_to_id = load_key_index(paths.data_dir(dataset) / paths.AMENITY_VOCAB)
    gold = M.load_gold(gold_path)
    if not gold:
        raise RunnerError(f"{gold_path}: không có câu active nào")
    return RunEnv(cfg=cfg, dataset=dataset, run_id=run_id, gold_path=gold_path,
                  gold_version=gold_version_for(gold_path, allow_untagged=allow_untagged),
                  gold_sha256=file_sha256(gold_path), gold=gold, ctx=M.EvalContext(cfg.metrics, items, key_to_id),
                  n_items=len(items))


# ------------------------------------------------------------------ truy xuất
@dataclass
class Retrieved:
    qid: str
    top_ids: list[str]
    top_scores: list[float]
    applied_filter: dict | None = None
    latency_ms: float = 0.0
    extra: dict[str, Any] = field(default_factory=dict)


def _dense_scores(hits, cutoff: float | None) -> tuple[list[str], list[float]]:
    ids, scores = [], []
    for h in hits:
        if cutoff is not None and h.distance is not None and h.distance > cutoff:
            continue
        ids.append(h.product_id)
        scores.append(1.0 - h.distance if h.distance is not None else float("nan"))
    return ids, scores


def retrieve(arm: Arm, env: RunEnv, *, store: Any, embedder: Any, physical: str, fold_mode: str,
             limit: int | None = None, app_ctx: Any = None) -> list[Retrieved]:
    """Top-k theo cách truy xuất của arm, mỗi câu một `Retrieved`. Embed cả lô câu (cache) trước khi hỏi store.
    Arm `engine: app` đi qua `app_adapter.retrieve_app` (SearchProducts thật) với `app_ctx` đã mở."""
    k = limit or env.k
    if arm.engine == "app":
        if app_ctx is None:
            raise RunnerError(f"arm {arm.id}: engine app cần AppContext (ProductBench) — xem `sb app-load`")
        from .app_adapter import retrieve_app
        return retrieve_app(arm, env, app_ctx, embedder, limit=k)
    how = arm.retrieval
    if how not in ("dense", "bm25"):
        raise RunnerError(f"arm {arm.id}: retrieval {how} chưa cài (hôm nay: dense | bm25)")
    if arm.query_preproc.get("alias") or arm.query_preproc.get("symspell") or arm.rerank or arm.csls or arm.dedupe_parent:
        raise RunnerError(f"arm {arm.id}: query_preproc / rerank / csls / dedupe_parent chưa cài trong runner")
    use_filter = bool(arm.filters.get("qu"))
    cutoff = arm.cutoff.get("max_vector_distance")
    qvecs = embedder.embed([g.text for g in env.gold], arm.query_input_type) if how == "dense" else None
    out: list[Retrieved] = []
    for i, g in enumerate(env.gold):
        applied = env.ctx.resolve(g.filter) if use_filter else None
        wv = F.to_weaviate(applied) if applied is not None else None
        t0 = perf_counter()
        if how == "dense":
            ids, scores = _dense_scores(store.dense(physical, qvecs[i], k, wv), cutoff)
        else:
            hits = store.bm25(physical, g.text, k, fold_mode=fold_mode, filters=wv)
            ids, scores = [h.product_id for h in hits], [float(h.score) if h.score is not None else float("nan") for h in hits]
        out.append(Retrieved(qid=g.qid, top_ids=ids, top_scores=scores, applied_filter=applied,
                             latency_ms=(perf_counter() - t0) * 1000.0))
    return out


# ------------------------------------------------------------------ chấm + ghi
def score_arm(env: RunEnv, retrieved: list[Retrieved], *, hub_score_max: float | None = None) -> tuple[dict, list[dict]]:
    """per_query rows (metrics.evaluate_query) + aggregate; `applied_filter` ghi kèm để `rescore` tính lại được."""
    by = {r.qid: r for r in retrieved}
    missing = [g.qid for g in env.gold if g.qid not in by]
    if missing:
        raise RunnerError(f"thiếu kết quả truy xuất cho {len(missing)} câu, ví dụ {missing[:3]}")
    rows = []
    for g in env.gold:
        r = by[g.qid]
        row = M.evaluate_query(g, r.top_ids, env.ctx, top_scores=r.top_scores, applied_filter=r.applied_filter)
        M.add_condensed_metrics(row, g, env.cfg.metrics)
        row["applied_filter"] = json.dumps(r.applied_filter, ensure_ascii=False) if r.applied_filter is not None else None
        row["latency_ms"] = r.latency_ms
        row["extra"] = json.dumps(r.extra, ensure_ascii=False, default=str) if r.extra else None   # diagnostics của arm APP
        rows.append(row)
    agg = M.aggregate(rows, env.cfg.metrics, hub_score_max=hub_score_max)
    agg["condensed"] = M.aggregate_condensed(rows, env.cfg.metrics)
    return agg, rows


def latency_summary(rows: list[dict]) -> dict[str, float | None]:
    lat = np.asarray([r["latency_ms"] for r in rows if r.get("latency_ms") is not None], dtype=float)
    if lat.size == 0:
        return {"weaviate_p50": None, "weaviate_p95": None, "weaviate_p99": None}
    return {f"weaviate_p{q}": float(np.percentile(lat, q)) for q in (50, 95, 99)}


def judged_gate(agg: dict, cfg: SBenchConfig) -> list[str]:
    """Lý do NEEDS_LABELS (spec 12.3): judged@k < gold.judged_at_10_min hoặc slice < gold.judged_at_10_slice_min."""
    k = cfg.metrics.k
    problems = []
    j = agg["overall"].get(f"judged@{k}")
    if j is not None and j < cfg.gold.judged_at_10_min and not np.isclose(
            j, cfg.gold.judged_at_10_min, rtol=0.0, atol=1e-12):
        problems.append(f"judged@{k} {j:.3f} < {cfg.gold.judged_at_10_min}")
    for s, v in sorted(agg["by_slice"].items()):
        js = v.get(f"judged@{k}")
        if js is not None and js < cfg.gold.judged_at_10_slice_min and not np.isclose(
                js, cfg.gold.judged_at_10_slice_min, rtol=0.0, atol=1e-12):
            problems.append(f"slice {s}: judged@{k} {js:.3f} < {cfg.gold.judged_at_10_slice_min}")
    return problems


def arm_dir(run_id: str, arm_id: str, create: bool = True) -> Path:
    d = paths.run_dir(run_id, create=create) / arm_id
    if create:
        d.mkdir(parents=True, exist_ok=True)
    return d


def latest_run_id() -> str | None:
    """Run mới nhất (theo tên — run_id bắt đầu bằng thời điểm) có ít nhất một results.json."""
    root = paths.sbench_home() / "runs"
    if not root.exists():
        return None
    runs = [d.name for d in root.iterdir() if d.is_dir() and any(p.name == RESULTS for p in d.rglob(RESULTS))]
    return max(runs) if runs else None


def build_results(env: RunEnv, arm: Arm, agg: dict, rows: list[dict], *, collection: str, embed: dict | None,
                  vs_parent: dict | None) -> dict:
    return {"arm": arm.id, "stage": arm.stage, "parent": arm.parent, "run_id": env.run_id,
            "gold_version": env.gold_version, "gold_sha256": env.gold_sha256, "gold_path": paths_rel(env.gold_path),
            "resolved_config_hash": config_hash(arm), "stale": False, "model": arm.model, "text_variant": arm.text_variant,
            "collection": collection, "dataset": env.dataset, "n_items": env.n_items, "k": env.k,
            "created_at": datetime.now().astimezone().replace(microsecond=0).isoformat(),
            "overall": agg["overall"], "by_slice": agg["by_slice"], "n_queries": agg["n_queries"],
            "n_defined": agg["n_defined"], "condensed": agg["condensed"], "latency_ms": latency_summary(rows),
            "cost_usd": {"embed_docs": None, "embed_queries": (embed or {}).get("usd", 0.0), "rerank": 0.0},
            "embed": embed, "vs_parent": vs_parent, "needs_labels": judged_gate(agg, env.cfg)}


def paths_rel(p: Path) -> str:
    try:
        return p.resolve().relative_to(paths.repo_root().resolve()).as_posix()
    except ValueError:
        return str(p)


def write_arm(run_id: str, results: dict, rows: list[dict]) -> Path:
    from evaluation.vector_bench.results import dump_json
    d = arm_dir(run_id, results["arm"])
    dump_json(d / RESULTS, results)
    pd.DataFrame(rows).to_parquet(d / PER_QUERY, index=False)
    return d


def read_results(run_id: str, arm_id: str) -> dict:
    p = arm_dir(run_id, arm_id, create=False) / RESULTS
    if not p.exists():
        raise RunnerError(f"chưa có kết quả {arm_id} trong run {run_id} ({p}) — chạy `sb run --arm {arm_id}` trước")
    return json.loads(p.read_text(encoding="utf-8"))


def read_rows(run_id: str, arm_id: str) -> list[dict]:
    p = arm_dir(run_id, arm_id, create=False) / PER_QUERY
    if not p.exists():
        raise RunnerError(f"chưa có {p} — chạy `sb run --arm {arm_id}` trước")
    df = pd.read_parquet(p)
    rows = df.to_dict(orient="records")
    for r in rows:                                     # parquet trả ndarray / NaN — về list / None như lúc ghi
        for col in ("top_ids", "top_scores", "ranks_of_relevant", "condensed_top_ids"):
            v = r.get(col)
            r[col] = [x for x in v.tolist()] if isinstance(v, np.ndarray) else (list(v) if v is not None else None)
        for col, v in list(r.items()):
            if isinstance(v, float) and np.isnan(v):
                r[col] = None
    return rows


def compare(rows_a: list[dict], rows_b: list[dict], cfg: SBenchConfig, *, condensed: bool = False) -> dict:
    if condensed:
        rows_a, rows_b = M.condensed_view(rows_a, cfg.metrics), M.condensed_view(rows_b, cfg.metrics)
    return M.compare_rows(rows_a, rows_b, cfg.metrics, seed=cfg.run.seed)


def vs_parent_of(env: RunEnv, arm: Arm, rows: list[dict]) -> dict | None:
    """So với arm cha đã chạy trong cùng run (parent là id arm, không phải tham chiếu @)."""
    if not arm.parent or arm.parent.startswith("@"):
        return None
    p = arm_dir(env.run_id, arm.parent, create=False) / PER_QUERY
    if not p.exists():
        return None
    parent_results = read_results(env.run_id, arm.parent)
    if parent_results.get("gold_version") != env.gold_version:
        return {"parent_gold_version": parent_results.get("gold_version"), "note": "khác gold_version — cần rescore (Part 11)"}
    cmp = compare(read_rows(env.run_id, arm.parent), rows, env.cfg)
    k = env.k
    return {"delta_recall": cmp[f"recall@{k}"]["delta"], "ci95": cmp[f"recall@{k}"]["ci95"],
            "p_one_sided": cmp[f"recall@{k}"]["p_one_sided"], "delta_ndcg": cmp[f"ndcg@{k}"]["delta"],
            "verdict": cmp["verdict"], "reason": cmp["reason"]}


# ------------------------------------------------------------------ một arm từ đầu đến cuối
StoreFactory = Callable[[], Any]


def run_arm(env: RunEnv, arm: Arm, *, store: Any, embedder_factory: Callable[[Arm], Any], physical: str,
            collection: str, fold_mode: str, app_ctx: Any = None) -> tuple[dict, list[dict]]:
    """Truy xuất + chấm + ghi một arm. `embedder_factory(arm)` trả CachedEmbedder (có `.name`, `.n_new`, `.n_cached`,
    `.stats`, `.close()`); chỉ gọi khi arm cần vector truy vấn."""
    embed_info = None
    emb = embedder_factory(arm) if arm.retrieval in ("dense", "hybrid", "dense+query_vec") else None
    try:
        retrieved = retrieve(arm, env, store=store, embedder=emb, physical=physical, fold_mode=fold_mode, app_ctx=app_ctx)
        if emb is not None:
            st = getattr(emb, "stats", None)
            embed_info = {"model": emb.name, "input_type": arm.query_input_type, "n_new": emb.n_new,
                          "n_cached": emb.n_cached, "usd": float(getattr(st, "usd", 0.0) or 0.0),
                          "n_calls": int(getattr(st, "n_calls", 0) or 0)}
    finally:
        if emb is not None:
            emb.close()
    agg, rows = score_arm(env, retrieved)
    results = build_results(env, arm, agg, rows, collection=collection, embed=embed_info,
                            vs_parent=vs_parent_of(env, arm, rows))
    write_arm(env.run_id, results, rows)
    return results, rows


# ------------------------------------------------------------------ Part 11: kết quả theo gold_version, rescore
def _version_key(v: str | None) -> tuple:
    import re
    m = re.match(r"^gold_v(\d+)$", v or "")
    return (1, int(m.group(1))) if m else (0, v or "")


def safe_version(gv: str | None) -> str:
    """gold_version → phần tên file: `fixture:ab12` có dấu `:` (Windows hiểu là NTFS stream) → `fixture_ab12`."""
    import re
    return re.sub(r"[^A-Za-z0-9_.-]", "_", gv or "untagged")


def available_versions(run_id: str, arm_id: str) -> dict[str, tuple[Path, Path]]:
    """{gold_version: (results.json, per_query.parquet)} của một arm: bản gốc và các bản `results@<gv>.json` do rescore
    (`gold_version` đọc từ nội dung JSON, tên file chỉ là dạng đã làm sạch)."""
    d = arm_dir(run_id, arm_id, create=False)
    out: dict[str, tuple[Path, Path]] = {}
    if not d.exists():
        return out
    base = d / RESULTS
    if base.exists():
        gv = json.loads(base.read_text(encoding="utf-8")).get("gold_version")
        out[gv or "untagged"] = (base, d / PER_QUERY)
    for p in sorted(d.glob("results@*.json")):
        res = json.loads(p.read_text(encoding="utf-8"))
        gv = res.get("gold_version") or "untagged"
        out[gv] = (p, d / f"per_query@{safe_version(gv)}.parquet")
    return out


def read_results_at(run_id: str, arm_id: str, gold_version: str | None = None) -> tuple[dict, list[dict], str]:
    """(results, rows, gold_version): bản đúng `gold_version` nếu truyền, không thì bản có version cao nhất."""
    vers = available_versions(run_id, arm_id)
    if not vers:
        raise RunnerError(f"chưa có kết quả {arm_id} trong run {run_id} — chạy `sb run --arm {arm_id}` trước")
    gv = gold_version or max(vers, key=_version_key)
    if gv not in vers:
        raise RunnerError(f"{arm_id}: không có kết quả trên gold {gv} (có: {', '.join(sorted(vers, key=_version_key))}) — "
                          f"`sb rescore --run-id {run_id}`")
    rp, qp = vers[gv]
    return json.loads(rp.read_text(encoding="utf-8")), _rows_from_parquet(qp), gv


def _rows_from_parquet(p: Path) -> list[dict]:
    if not p.exists():
        raise RunnerError(f"chưa có {p}")
    rows = pd.read_parquet(p).to_dict(orient="records")
    for r in rows:
        for col in ("top_ids", "top_scores", "ranks_of_relevant", "condensed_top_ids"):
            v = r.get(col)
            r[col] = [x for x in v.tolist()] if isinstance(v, np.ndarray) else (list(v) if v is not None else None)
        for col, v in list(r.items()):
            if isinstance(v, float) and np.isnan(v):
                r[col] = None
    return rows


def rescore_arm(env: RunEnv, run_id: str, arm_id: str) -> tuple[dict, list[dict], dict]:
    """Chấm lại từ `top_ids` đã lưu (bản gốc results.json) trên gold của `env` → `results@<gv>.json` +
    `per_query@<gv>.parquet`. Không gọi Weaviate / Cohere. Câu mới thêm vào gold mà run chưa có → bỏ qua và đếm; câu đã
    retired → không vào metric."""
    old = read_results(run_id, arm_id)
    old_rows = {r["qid"]: r for r in read_rows(run_id, arm_id)}
    rows, missing = [], []
    for g in env.gold:
        r = old_rows.get(g.qid)
        if r is None:
            missing.append(g.qid)
            continue
        applied = json.loads(r["applied_filter"]) if r.get("applied_filter") else None
        row = M.evaluate_query(g, list(r["top_ids"] or []), env.ctx, top_scores=r.get("top_scores"), applied_filter=applied)
        M.add_condensed_metrics(row, g, env.cfg.metrics)
        row["applied_filter"] = r.get("applied_filter")
        row["latency_ms"] = r.get("latency_ms")
        rows.append(row)
    if not rows:
        raise RunnerError(f"{arm_id}: không có câu nào chung giữa run {run_id} và gold {env.gold_version}")
    agg = M.aggregate(rows, env.cfg.metrics, hub_score_max=old["overall"].get("hub_score_max"))
    condensed = M.aggregate_condensed(rows, env.cfg.metrics)
    results = {**old, "gold_version": env.gold_version, "gold_sha256": env.gold_sha256, "gold_path": paths_rel(env.gold_path),
               "rescored_from": old.get("gold_version"), "rescored_at": datetime.now().astimezone().replace(microsecond=0).isoformat(),
               "overall": agg["overall"], "by_slice": agg["by_slice"], "n_queries": agg["n_queries"], "n_defined": agg["n_defined"],
               "condensed": condensed, "needs_labels": judged_gate(agg, env.cfg), "vs_parent": None,
               "queries_missing_in_run": missing}
    from evaluation.vector_bench.results import dump_json
    d = arm_dir(run_id, arm_id)
    gv = safe_version(env.gold_version)
    dump_json(d / f"results@{gv}.json", results)
    pd.DataFrame(rows).to_parquet(d / f"per_query@{gv}.parquet", index=False)
    return results, rows, {"missing": missing}


def arms_in_run(run_id: str) -> list[str]:
    d = paths.run_dir(run_id, create=False)
    if not d.exists():
        return []
    return sorted(p.parent.name for p in d.glob(f"*/{RESULTS}"))
