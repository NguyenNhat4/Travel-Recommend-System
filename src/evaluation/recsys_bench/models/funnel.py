"""Funnel chung cho mọi scorer (Day 4–5 R4; spec `recsys-algos-v1.md` §0.4): mask → pool → score → rerank → top-k.

Mirror phần glue của `RecommendForUser.__call__` (`use_cases.py:131-169`) với chỉ số toàn cục; công thức dùng thẳng hàm domain
(`build_profile`, `mmr_select`). Hai knob cấp run:

- `pool`: `engine` = tái tạo đúng pool của engine (ANN top-`pool_k` quanh u_short [và u_long khi có trip mở] ∪ top-`popular_k` phổ biến
  trong mask, giữ thứ tự chèn, sort ổn định theo điểm, cắt `pool_k`) — dùng cho gate "= v5"; `mask` = chấm toàn mask — dùng cho bảng
  so scorer (công bằng giữa scorer; khác engine ở khách có mask > pool_k).
- `rerank`: `none` = khoá `(score↓, pop_D↓, item_id↑)`; `mmr` = `mmr_select` λ `MMR_LAMBDA` không cap trên `pool_k` ứng viên đầu
  (như engine cắt `candidate_k` trước MMR). Với `pool engine` thứ tự vào MMR là của engine (score ổn định, hoà theo thứ tự chèn);
  với `pool mask` là khoá `(score↓, pop_D↓, item_id↑)` để scorer có nhiều điểm 0 không đưa 200 unit "chỉ số nhỏ nhất" vào MMR.

`mode`: `noexcl` (05/10) = mask engine bỏ riêng category exclusion (ablation Day 7); `funnel` = mask engine (có trip mở: destination ∧ taxonomy ∉ đã mua ∧ recommendable/available, mask rỗng → bỏ destination; không
trip mở: recommendable/available; luôn bỏ bought_units); `raw` = recommendable/available trừ bought_units. Khách không có trip nào
(engine đi `_cold_start`): funnel xếp mask theo pop_D toàn cục, `strategy = popular` — không mô phỏng section của `_cold_start`.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from time import perf_counter

import numpy as np

from src.backend.app.application.ports import UnitIndex, VectorSearchPort
from src.backend.app.domain.recommendation import profile as P
from src.backend.app.domain.recommendation.profile import Profile

from ..arms import Ranked
from ..engine import OfflineEngine
from . import because as BC
from .base import Scorer, TrainData, UserCtx
from .seeds import profile_for, resolved_events, seeds_for

POOLS = ("engine", "mask")
RERANKS = ("none", "mmr")
MODES = ("funnel", "raw", "noexcl")   # noexcl (05/10, ablation Day 7): mask engine nhưng không loại taxonomy đã mua trong trip mở


@dataclass(frozen=True)
class FunnelCfg:
    mode: str = "funnel"
    pool: str = "mask"
    rerank: str = "none"
    pool_k: int = 200          # = RecommendForUser.candidate_k
    popular_k: int = 50        # = RecommendForUser.popular_k
    k: int = 20

    def __post_init__(self):
        if self.mode not in MODES or self.pool not in POOLS or self.rerank not in RERANKS:
            raise ValueError(f"funnel không hợp lệ: mode={self.mode!r} pool={self.pool!r} rerank={self.rerank!r}")

    def as_dict(self) -> dict:
        return {"mode": self.mode, "pool": self.pool, "rerank": self.rerank, "poolK": self.pool_k, "popularK": self.popular_k, "k": self.k}


def engine_mask(index: UnitIndex, profile: Profile, *, exclude_taxonomy: bool = True) -> tuple[np.ndarray, str | None, set[str]]:
    """Mirror `use_cases.py:131-142` với `destination=None` (harness). Trả (mask, dest, taxonomy bị loại).
    `exclude_taxonomy=False` (mode `noexcl`): giữ khoá điểm đến của trip mở và bỏ món đã mua, chỉ tắt category exclusion."""
    if profile.active_trip is not None:
        t = profile.active_trip
        dest, done = t.destination, set(t.purchased_taxonomies) if exclude_taxonomy else set()
        m = index.mask(destination=dest, only_recommendable=True) & ~np.isin(index.taxonomy, list(done))
        if not m.any():
            m = index.mask(only_recommendable=True) & ~np.isin(index.taxonomy, list(done))
    else:
        dest, done = None, set()
        m = index.mask(only_recommendable=True)
    for u in profile.bought_units:
        m[u] = False
    return m, dest, done


def raw_mask(index: UnitIndex, profile: Profile) -> np.ndarray:
    m = index.mask(only_recommendable=True)
    for u in profile.bought_units:
        m[u] = False
    return m


def engine_pool(index: UnitIndex, vector_search: VectorSearchPort, pop_scores: dict[int, float], profile: Profile,
                mask: np.ndarray, has_vec: np.ndarray, cfg: FunnelCfg) -> list[int]:
    """Mirror `use_cases.py:144-164`: ANN quanh u_short (và u_long khi có trip mở) trong mask, rồi popular trong mask; giữ thứ tự chèn."""
    allowed = index.allowed_ids(mask)
    u_short = profile.active_trip.vec if profile.active_trip is not None else profile.u_long
    queries = [u_short] if profile.active_trip is None else [u_short, profile.u_long]
    cand: list[int] = []
    seen: set[int] = set()
    for q in queries:
        for h in vector_search.near_vector(q, allowed, cfg.pool_k, with_vectors=False):
            g = index.idx.get(h.product_id)
            if g is not None and has_vec[g] and g not in seen:
                seen.add(g)
                cand.append(g)
    popular = [g for g in sorted(pop_scores, key=lambda g: -pop_scores[g]) if mask[g]][: cfg.popular_k]
    for g in popular:
        if has_vec[g] and g not in seen:
            seen.add(g)
            cand.append(g)
    return cand


def rank_none(score_full: np.ndarray, cand: np.ndarray, pop: np.ndarray, product_ids: np.ndarray, k: int) -> list[int]:
    """Khoá spec §0.4: điểm giảm dần, pop_D giảm dần, item_id tăng dần (lexsort: khoá cuối là khoá chính)."""
    order = np.lexsort((product_ids[cand], -pop[cand], -score_full[cand]))
    return [int(cand[i]) for i in order[:k]]


def rank_mmr(score_full: np.ndarray, E: np.ndarray, cand_sorted: list[int], taxonomy: np.ndarray, k: int) -> list[int]:
    """`mmr_select` của engine, không cap (mode eval); λ đọc từ `profile.MMR_LAMBDA` lúc gọi."""
    return [int(i) for i in P.mmr_select(score_full, E, cand_sorted, taxonomy, k, max_per_vertical=None)]


class CtxCache:
    """Ngữ cảnh khách tính một lần cho mọi AlgoArm trong run: profile (engine), seeds, pop_D tại as_of."""

    def __init__(self, data: TrainData, engine: OfflineEngine):
        self.data, self.engine = data, engine
        self._cache: dict[str, UserCtx] = {}

    def pop_scores(self, as_of: datetime, destination: str | None) -> dict[int, float]:
        return self.engine.popularity_at(as_of).unit_scores(destination)

    def get(self, user: str, as_of: datetime, events: list[dict]) -> UserCtx:
        ctx = self._cache.get(user)
        if ctx is not None and ctx.as_of == as_of:
            return ctx
        data = self.data
        profile = profile_for(resolved_events(events, data.index, as_of, data.has_vec), data, as_of)
        dest = profile.active_trip.destination if profile.active_trip is not None else None
        excluded = set(profile.active_trip.purchased_taxonomies) if profile.active_trip is not None else set()
        pop_dict = self.pop_scores(as_of, dest)
        pop = np.zeros(data.n_items, dtype=np.float32)
        for g, s in pop_dict.items():
            pop[g] = s
        ctx = UserCtx(user=user, as_of=as_of, profile=profile, seeds=seeds_for(profile), pop=pop, pop_dict=pop_dict, destination=dest,
                      excluded=excluded, bought=set(profile.bought_units), user_row=data.user_rows.get(user))
        self._cache[user] = ctx
        return ctx


class AlgoArm:
    """Bọc một scorer thành arm của `bench.evaluate` (key, family, recommend → Ranked). `key = name` hoặc `name+mmr`."""

    mean_meta = ("collabCoverage", "poolTruncated", "maskSize", "poolSize", "becauseCoverage", "becauseViolations")

    def __init__(self, name: str, scorer: Scorer, cfg: FunnelCfg, ctx_cache: CtxCache, vector_search: VectorSearchPort | None,
                 *, seed: int | None = None, because_k: int = 0):
        """`seed` (ials/bpr nhiều seed): key `name-s<seed>[+mmr]`, family `name[+mmr]` → `bench.aggregate` gộp như arm random.
        `because_k` > 0: ghi because[] (dạng contract + `kind`) cho `ids[:because_k]` vào meta, cùng `becauseCoverage` (tỉ lệ item có
        ≥ 1 lý do; chỉ khách không phải popular) và `becauseViolations` (0/1 theo luật contract) — không đổi ids / metric chính."""
        if because_k < 0:
            raise ValueError(f"because_k={because_k}: phải ≥ 0")
        self.name, self.scorer, self.cfg, self.ctx, self.vector_search, self.seed = name, scorer, cfg, ctx_cache, vector_search, seed
        self.because_k = int(because_k)
        suffix = "+mmr" if cfg.rerank == "mmr" else ""
        self.family = name + suffix
        self.key = (f"{name}-s{seed}" if seed is not None else name) + suffix
        self.data = ctx_cache.data
        self.index = self.data.index
        if cfg.pool == "engine" and vector_search is None:
            raise ValueError("pool=engine cần vector_search (near_vector)")

    def recommend(self, cdp_user_id: str, as_of: datetime, k: int, events: list[dict]) -> Ranked:
        started = perf_counter()
        cfg, data, index = self.cfg, self.data, self.index
        ctx = self.ctx.get(cdp_user_id, as_of, events)
        profile = ctx.profile
        if cfg.mode == "raw":
            mask, dest, done = raw_mask(index, profile), ctx.destination, ctx.excluded
        else:
            mask, dest, done = engine_mask(index, profile, exclude_taxonomy=cfg.mode != "noexcl")
        pool_truncated = 0
        if cfg.pool == "engine" and profile.trips:
            cand = np.asarray(engine_pool(index, self.vector_search, ctx.pop_dict, profile, mask, data.has_vec, cfg), dtype=np.int64)
        else:
            cand = np.flatnonzero(mask).astype(np.int64)
        meta = {"strategy": ctx.strategy, "destination": dest, "excludedVerticals": sorted(done), "seedBranch": ctx.seeds.branch,
                "maskSize": int(mask.sum()), "poolSize": int(len(cand)), "pool": cfg.pool, "rerank": cfg.rerank, "mode": cfg.mode}
        if len(cand) == 0:
            meta["poolTruncated"] = 0
            if self.because_k:
                self._because(ctx, [], meta)
            return Ranked([], (perf_counter() - started) * 1000, meta)
        scores = np.asarray(self.scorer.score(ctx, cand), dtype=np.float32)
        score_full = np.full(data.n_items, -np.inf, dtype=np.float32)
        score_full[cand] = scores
        if cfg.pool == "engine":
            # như engine: sorted(cand, key=-score) ổn định (hoà theo thứ tự chèn ANN → popular), cắt candidate_k, rồi MMR
            cand_sorted = cand[np.argsort(-scores, kind="stable")]
            pool_truncated = int(len(cand_sorted) > cfg.pool_k)
            cand_sorted = cand_sorted[: cfg.pool_k]
            cand = cand_sorted
        else:
            # pool mask: thứ tự theo khoá spec (score↓, pop_D↓, item_id↑) — scorer có nhiều điểm 0 (cooc/ease/knn) thì 200 ứng viên
            # vào MMR là các món phổ biến nhất trong số điểm cao nhất, không phải chỉ số unit nhỏ nhất
            cand_sorted = np.asarray(rank_none(score_full, cand, ctx.pop, data.product_ids, len(cand)), dtype=np.int64)
        if cfg.rerank == "mmr":
            chosen = rank_mmr(score_full, data.E, [int(i) for i in cand_sorted[: cfg.pool_k]], index.taxonomy, k)
        else:
            chosen = rank_none(score_full, cand, ctx.pop, data.product_ids, k)
        meta["poolTruncated"] = pool_truncated
        collab = self.scorer.collab_part(ctx, np.asarray(chosen, dtype=np.int64)) if chosen else None
        if collab is not None:
            meta["collabCoverage"] = float(np.mean(np.asarray(collab) > 0)) if len(collab) else 0.0
        if self.because_k:
            self._because(ctx, chosen[: self.because_k], meta)
        return Ranked([index.units[g].product_id for g in chosen], (perf_counter() - started) * 1000, meta)

    def _because(self, ctx: UserCtx, top: list[int], meta: dict) -> None:
        """because[] cho top-K (FR-REC-03): `scorer.explain` nếu có, không thì rỗng; luật contract tính trên đúng top-K đó."""
        explain = getattr(self.scorer, "explain", None)
        items = np.asarray(top, dtype=np.int64)
        raw = explain(ctx, items) if (explain is not None and len(items)) else [[] for _ in top]
        bec = [BC.contract_items(self.index, b) for b in raw]
        cold = int(getattr(ctx.profile, "n_events", 0)) < 3
        meta["because"], meta["coldStart"] = bec, cold
        if ctx.strategy != "popular" and bec:
            meta["becauseCoverage"] = float(np.mean([bool(b) for b in bec]))
        rules = BC.violations(ctx.strategy, cold, bec)
        meta["becauseViolations"], meta["becauseViolationRules"] = int(bool(rules)), rules
