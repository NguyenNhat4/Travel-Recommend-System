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

Phase A (05/10): `load_env` gắn thêm cột RAM `origin_city` / `destination_city` / `features` vào items (không đổi
`ITEM_SCHEMA` / items.parquet — `items_sha256` đã ghim theo collection Weaviate) cho metric forbidden / direction, và gắn
`forbidden_filter` chẩn đoán từ `metrics.forbidden_overrides` cho câu gold chưa có. `score_arm` / `rescore_arm` đưa
`extra` (diagnostics arm APP) vào `evaluate_query` (parse_ok) và `rescore` giữ lại cột `extra`.

06/10: `load_env` gắn nhãn theo câu từ `metrics.annotations` (query_annotations.yaml; gold thắng; qid phải có trong
gold/gold.jsonl) rồi mới tới `forbidden_overrides` (annotations thắng), và gắn `block` (v3 / v4 theo tag gold_v3 —
`rubric_v3_qids`). results.json thêm `by_block` / `by_family`. Thêm phần đọc cho `sb compare --split`, `sb guards`,
`sb weak-results`: `attach_query_meta` (block / family cho dòng per_query cũ), `resolve_split`, `query_vectors_from_cache`
(đọc cache embed sqlite chỉ-đọc, không gọi model), `weak_entries`.
"""
from __future__ import annotations

import functools
import hashlib
import json
import re
import sqlite3
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Any, Callable

import numpy as np
import pandas as pd
import structlog

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


log = structlog.get_logger("sbench.runner")


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
    projection: dict[str, Any] = field(default_factory=lambda: {"enabled": False})   # chiếu rubric v4 (metrics.rubric_v4_projection)

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


def _backend_amenity_keys():
    """`amenity_keys` của backend (`src.backend.app.domain.search.amenities`) — import kiểu `app_adapter._backend()` để bench
    và backend dùng MỘT từ vựng khoá tiện ích."""
    import sys
    root = str(paths.repo_root())
    if root not in sys.path:
        sys.path.insert(0, root)
    try:
        from src.backend.app.domain.search.amenities import amenity_keys
    except Exception as e:  # noqa: BLE001
        raise RunnerError(f"không import được từ vựng tiện ích backend (src.backend.app.domain.search.amenities): "
                          f"{type(e).__name__}: {e}") from None
    return amenity_keys


def _amenity_strings(a: dict) -> list[str]:
    raw = a.get("amenities")
    return [x for x in raw if isinstance(x, str)] if isinstance(raw, (list, tuple)) else []


def attach_unit_columns(items: pd.DataFrame, records: list[dict], cfg: SBenchConfig) -> pd.DataFrame:
    """Cột RAM Phase A trên `items` (index product_id): `origin_city` / `destination_city` từ `attributes` của tuyến bay
    ("" khi thiếu — như `UnitAttributes` của backend) và `features` = danh sách khoá tiện ích của BACKEND
    (`amenity_keys`) trên chuỗi tiện ích của unit + phòng/chuyến con. Với `amenity_scope: property_plus_rooms` cột
    `amenities_raw` đã gộp phòng con nên dùng thẳng; scope khác thì gộp lại từ `records` qua `group_children`."""
    amenity_keys = _backend_amenity_keys()
    attrs = {r["productId"]: (r.get("attributes") or {}) for r in records}
    ids = items["product_id"].tolist()

    def city(pid: str, key: str) -> str:
        v = attrs.get(pid, {}).get(key)
        return v if isinstance(v, str) else ""

    items["origin_city"] = [city(pid, "originCity") for pid in ids]
    items["destination_city"] = [city(pid, "destinationCity") for pid in ids]
    if cfg.catalog.amenity_scope == "property_plus_rooms":
        strings = {pid: (list(raw) if raw is not None else []) for pid, raw in zip(ids, items["amenities_raw"])}
    else:
        _, children, _, _ = catalog.group_children(records, cfg.catalog.search_unit_variants)
        strings = {pid: _amenity_strings(attrs.get(pid, {})) + [x for k in children.get(pid, []) for x in _amenity_strings(k.get("attributes") or {})]
                   for pid in ids}
    items["features"] = [sorted(amenity_keys(strings[pid])) for pid in ids]
    return items


@functools.lru_cache(maxsize=1)
def _rubric_v3_qids_cached() -> frozenset[str] | None:
    from .holes import gold_at
    try:
        return frozenset(r.qid for r in gold_at(M.RUBRIC_V3_TAG))
    except Exception as e:  # noqa: BLE001 — không có git / tag thì dùng ngưỡng qid dự phòng
        log.warning("không đọc được gold.jsonl của tag — khối rubric dùng ngưỡng qid dự phòng", tag=M.RUBRIC_V3_TAG,
                    fallback=f"qid <= {M.RUBRIC_V3_MAX_QID} là v3", error=f"{type(e).__name__}: {str(e)[:160]}")
        return None


def rubric_v3_qids() -> frozenset[str] | None:
    """qid trong gold.jsonl của tag `gold_v3` (`git show gold_v3:…` qua `holes.gold_at`, đọc một lần mỗi tiến trình); None khi
    không đọc được (không git / không tag) → `metrics.block_of` dùng ngưỡng `RUBRIC_V3_MAX_QID` và log cảnh báo."""
    return _rubric_v3_qids_cached()


def gold_file_qids(path: Path) -> set[str]:
    """Mọi qid trong một gold.jsonl (kể cả retired) — chỉ đọc trường qid."""
    out = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                out.add(str(json.loads(line)["qid"]))
            except (ValueError, KeyError, TypeError):
                continue
    return out


def annotate_gold(gold: list[M.GoldQuery], cfg: SBenchConfig, gold_path: Path) -> dict[str, int]:
    """Nhãn theo câu (`metrics.annotations`, rồi `metrics.forbidden_overrides` cũ — annotations thắng vì gắn trước, cả hai chỉ
    gắn trường gold chưa có) và khối rubric. qid của annotations phải có trong gold/gold.jsonl (gold chuẩn, mọi trạng thái —
    bắt qid gõ sai); câu không có trong gold đang chấm (fixture, gold cũ) chỉ bị bỏ qua. Trả {trường: số câu được gắn}."""
    n: dict[str, int] = {}
    if cfg.metrics.annotations:
        ann = M.load_annotations(paths.PKG_DIR / cfg.metrics.annotations)
        canon = paths.GOLD_JSONL if paths.GOLD_JSONL.exists() else gold_path
        n = M.apply_annotations(gold, ann, known_qids=gold_file_qids(canon) | gold_file_qids(gold_path))
    if cfg.metrics.forbidden_overrides:   # chẩn đoán cũ cho gold_v3 (05/10) — chỉ câu chưa có spec cấm
        n["forbidden_overrides"] = M.apply_forbidden_overrides(
            gold, M.load_forbidden_overrides(paths.PKG_DIR / cfg.metrics.forbidden_overrides))
    v3 = rubric_v3_qids()
    for g in gold:
        g.block = M.block_of(g.qid, v3)
    return n


def load_env(cfg: SBenchConfig, dataset: str, gold_path: Path, *, run_id: str, allow_untagged: bool = False) -> RunEnv:
    if not gold_path.exists():
        raise RunnerError(f"không thấy gold {gold_path} — chạy `sb gold import` trước")
    items = catalog.read_items(dataset).set_index("product_id", drop=False)
    items = attach_unit_columns(items, catalog.reload_records(cfg, dataset), cfg)
    key_to_id = load_key_index(paths.data_dir(dataset) / paths.AMENITY_VOCAB)
    gold = M.load_gold(gold_path, gold_fields=cfg.metrics.gold_fields)
    if not gold:
        raise RunnerError(f"{gold_path}: không có câu active nào")
    annotate_gold(gold, cfg, gold_path)
    projection: dict[str, Any] = {"enabled": bool(cfg.metrics.rubric_v4_projection)}
    if cfg.metrics.rubric_v4_projection:                      # 06/10 (b): nhãn ≥ 1 sai loại cốt lõi → 0 lúc chấm, gold không đổi
        variant_of = items["variant"].to_dict()
        per_q = {g.qid: M.project_rubric_v4(g, variant_of) for g in gold}
        projection.update(pairs=sum(per_q.values()), queries=sum(1 for v in per_q.values() if v),
                          annotated_queries=sum(1 for g in gold if g.allowed_variants))
        log.info("chiếu rubric v4", pairs=projection["pairs"], queries=projection["queries"],
                 annotated=projection["annotated_queries"], gold=len(gold))
    return RunEnv(cfg=cfg, dataset=dataset, run_id=run_id, gold_path=gold_path,
                  gold_version=gold_version_for(gold_path, allow_untagged=allow_untagged),
                  gold_sha256=file_sha256(gold_path), gold=gold, ctx=M.EvalContext(cfg.metrics, items, key_to_id),
                  n_items=len(items), projection=projection)


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
        row = M.evaluate_query(g, r.top_ids, env.ctx, top_scores=r.top_scores, applied_filter=r.applied_filter,
                               extra=r.extra or None)
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
            "rubric_v4_projection": env.projection,
            "resolved_config_hash": config_hash(arm), "stale": False, "model": arm.model, "text_variant": arm.text_variant,
            "collection": collection, "dataset": env.dataset, "n_items": env.n_items, "k": env.k,
            "created_at": datetime.now().astimezone().replace(microsecond=0).isoformat(),
            "overall": agg["overall"], "by_slice": agg["by_slice"], "by_block": agg.get("by_block"),
            "by_family": agg.get("by_family"), "n_queries": agg["n_queries"],
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


def extra_of(row: dict) -> dict | None:
    """Cột `extra` của per_query (JSON diagnostics arm APP) → dict; None / rỗng / hỏng → None."""
    v = row.get("extra")
    if isinstance(v, dict):
        return v or None
    if not isinstance(v, str) or not v:
        return None
    try:
        d = json.loads(v)
    except ValueError:
        return None
    return d if isinstance(d, dict) and d else None


def rescore_row(g: M.GoldQuery, old: dict, env: RunEnv) -> dict:
    """Một dòng per_query chấm lại từ dòng cũ: `top_ids`, `applied_filter`, `extra` giữ nguyên, metric tính lại trên gold
    của `env`. Cột `extra` được giữ (05/10 — trước đây rescore làm rơi diagnostics arm APP)."""
    applied = json.loads(old["applied_filter"]) if old.get("applied_filter") else None
    row = M.evaluate_query(g, list(old["top_ids"] or []), env.ctx, top_scores=old.get("top_scores"), applied_filter=applied,
                           extra=extra_of(old))
    M.add_condensed_metrics(row, g, env.cfg.metrics)
    row["applied_filter"] = old.get("applied_filter")
    row["latency_ms"] = old.get("latency_ms")
    row["extra"] = old.get("extra") if isinstance(old.get("extra"), str) else (
        json.dumps(old["extra"], ensure_ascii=False, default=str) if old.get("extra") else None)
    return row


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
        rows.append(rescore_row(g, r, env))
    if not rows:
        raise RunnerError(f"{arm_id}: không có câu nào chung giữa run {run_id} và gold {env.gold_version}")
    agg = M.aggregate(rows, env.cfg.metrics, hub_score_max=old["overall"].get("hub_score_max"))
    condensed = M.aggregate_condensed(rows, env.cfg.metrics)
    results = {**old, "gold_version": env.gold_version, "gold_sha256": env.gold_sha256, "gold_path": paths_rel(env.gold_path),
            "rubric_v4_projection": env.projection,
               "rescored_from": old.get("gold_version"), "rescored_at": datetime.now().astimezone().replace(microsecond=0).isoformat(),
               "overall": agg["overall"], "by_slice": agg["by_slice"], "by_block": agg["by_block"], "by_family": agg["by_family"],
               "n_queries": agg["n_queries"], "n_defined": agg["n_defined"], "condensed": condensed,
               "needs_labels": judged_gate(agg, env.cfg), "vs_parent": None, "queries_missing_in_run": missing}
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


# ------------------------------------------------------------------ 06/10: đọc kết quả đã lưu cho compare --split / guards / weak-results
def attach_query_meta(rows: list[dict], gold: list[M.GoldQuery] | None = None) -> list[dict]:
    """Điền `block` (và `family` khi truyền `gold` đã gắn annotations) cho dòng per_query chưa có — artifact chạy trước 06/10
    không có hai cột này. Giá trị đã có trong dòng được giữ. Sửa tại chỗ và trả lại `rows`."""
    fam = {g.qid: g.family for g in gold} if gold is not None else {}
    need_block = any(not r.get("block") for r in rows)
    v3 = rubric_v3_qids() if need_block else None
    for r in rows:
        if not r.get("block"):
            r["block"] = M.block_of(r["qid"], v3)
        if gold is not None and not r.get("family"):
            r["family"] = fam.get(r["qid"])
    return rows


def _split_version_key(p: Path) -> int:
    m = re.match(r"^devtest@gold_v(\d+)\.json$", p.name)
    return int(m.group(1)) if m else -1


def resolve_split(gold_version: str | None, qids: set[str], *, split_file: Path | None = None,
                  splits_dir: Path | None = None) -> tuple[dict, Path, str | None]:
    """File phân chia dev/test cho một lượt so: (dữ liệu, đường dẫn, ghi chú hoặc None).
    1. `split_file` truyền tường minh → dùng nguyên văn.
    2. `devtest@<gold_version>.json` có sẵn → dùng (devtest.filter_rows sẽ báo nếu thiếu câu).
    3. Dự phòng (gold chưa tag / chưa chia): file `devtest@gold_v*.json` MỚI NHẤT có assignment phủ đủ `qids` — kèm ghi chú
       để CLI in ra. Không file nào phủ đủ → DevTestError."""
    from . import devtest as DT
    sd = splits_dir or DT.SPLITS_DIR

    def _read(p: Path) -> dict:
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            raise DT.DevTestError(f"không đọc được {p}: {e}") from None
        if not isinstance(data, dict) or not isinstance(data.get("assignment"), dict):
            raise DT.DevTestError(f"{p}: thiếu assignment {{qid: dev|test}}")
        data.setdefault("gold_version", p.stem.split("@", 1)[-1])
        return data

    if split_file is not None:
        if not split_file.exists():
            raise DT.DevTestError(f"không thấy --split-file {split_file}")
        return _read(split_file), split_file, None
    if gold_version and DT.split_path(gold_version, sd).exists():
        p = DT.split_path(gold_version, sd)
        return _read(p), p, None
    for p in sorted(sd.glob("devtest@gold_v*.json"), key=_split_version_key, reverse=True):
        data = _read(p)
        if qids <= set(data["assignment"]):
            return data, p, (f"gold {gold_version or 'chưa tag'} chưa có file phân chia — dùng {p.name} (bản mới nhất phủ đủ "
                             f"{len(qids)} câu)")
    raise DT.DevTestError(f"không có devtest@{gold_version}.json và không file devtest@gold_v*.json nào trong {sd} phủ đủ "
                          f"{len(qids)} câu — truyền --split-file")


def canonical_query_text(text: str) -> str:
    """= `canonical_query` của backend (`application/search/use_cases.py`): gộp khoảng trắng — chuỗi đi vào embed và là khoá
    cache vector truy vấn. Chép lại (một dòng) để đọc cache không cần import backend."""
    return re.sub(r"\s+", " ", text).strip()


def embedded_query_text(gold_text: str, extra: dict | None) -> str:
    """Chuỗi arm APP đã embed cho một câu: câu đã chuẩn hoá (`diagnostics.normalizedQuery`, chỉ có khi bước chuẩn hoá đổi
    chữ) hoặc câu gốc, sau `canonical_query_text`."""
    nq = (extra or {}).get("normalizedQuery")
    return canonical_query_text(nq if isinstance(nq, str) and nq.strip() else gold_text)


def query_vectors_from_cache(cfg: SBenchConfig, model: str, texts: list[str], *,
                             cache_path: Path | None = None) -> dict[str, np.ndarray]:
    """{text: vector query} lấy từ cache embed sqlite của bench (khoá `embed.cache_key(<tên embedder>, "query", text)`,
    `embedder_name` không nạp model) — mở CHỈ-ĐỌC, không gọi model / API. Text chưa có trong cache không có trong kết quả."""
    from .embed import cache_key, embedder_name
    p = cache_path or paths.cache_dir(create=False) / paths.EMBED_CACHE
    if not p.exists():
        return {}
    name = embedder_name(cfg, model)
    keys = {cache_key(name, "query", t): t for t in dict.fromkeys(texts)}
    db = sqlite3.connect(f"file:{p.as_posix()}?mode=ro", uri=True)
    out: dict[str, np.ndarray] = {}
    try:
        ks = list(keys)
        for i in range(0, len(ks), 500):
            chunk = ks[i:i + 500]
            for k, d, blob in db.execute(f"SELECT key, dim, vec FROM embeddings WHERE key IN ({','.join('?' * len(chunk))})",
                                         chunk):
                v = np.frombuffer(blob, dtype=np.float32)
                if v.shape[0] == d:
                    out[keys[k]] = v
    finally:
        db.close()
    return out


def weak_entries(rows: list[dict], gold: dict[str, M.GoldQuery], doc_vecs: np.ndarray,
                 qvecs: dict[str, np.ndarray], *, top_source: str = "top_scores") -> list[dict]:
    """Mỗi câu một dòng cho `metrics.weak_grid`: top = max(top_scores) đã lưu (cosine — trường `score` của contract; None khi
    rỗng) hoặc, với `top_source="diagnostics"`, `diagnostics.topScore` của arm APP (= topScore của response: max trên cả R,
    có thể nằm ngoài top-k; thiếu thì dùng top_scores); background = trung vị cosine giữa vector truy vấn và MỌI vector
    document (F = cả catalog: phân tích này không dựng lại filter của arm); margin = top − background (None khi thiếu vector
    truy vấn hoặc rỗng). Vector được L2-normalise lại."""
    docs = np.asarray(doc_vecs, dtype=np.float32)
    docs = docs / np.clip(np.linalg.norm(docs, axis=1, keepdims=True), 1e-12, None)
    out = []
    for r in rows:
        g = gold.get(r["qid"])
        extra = extra_of(r)
        text = embedded_query_text(g.text if g else "", extra)
        scores = [float(x) for x in (r.get("top_scores") or []) if x is not None and not np.isnan(x)]
        scores_top = max(scores) if scores else None
        diag_top = (extra or {}).get("topScore")
        diag_top = float(diag_top) if isinstance(diag_top, (int, float)) and not isinstance(diag_top, bool) else None
        top = diag_top if (top_source == "diagnostics" and diag_top is not None and scores_top is not None) else scores_top
        q = qvecs.get(text)
        bg = None
        if q is not None and q.shape[0] == docs.shape[1]:
            q = q / max(float(np.linalg.norm(q)), 1e-12)
            bg = float(np.median(docs @ q))
        out.append({"qid": r["qid"], "slice": r.get("slice"), "ooc": bool(r.get("expected_no_result")), "text": text,
                    "top": top, "background": bg, "margin": (top - bg) if (top is not None and bg is not None) else None,
                    "scores_top": scores_top, "diag_top": diag_top})
    return out
