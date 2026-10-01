"""R4 — gate G1/G2 trên fixture (không DB): `content_profile` qua funnel `pool engine` phải ra đúng list của arm engine.

Hai world: `world` 11 sản phẩm (pool = mask, kiểm mask / tie-break) và `synthetic_world` 60 unit với `OfflineEngine(candidate_k=10,
popular_k=3)` để pool **bị cắt thật** (kiểm `engine_pool` tái tạo đúng ANN ∪ popular, thứ tự chèn, sort ổn định)."""
from __future__ import annotations

import numpy as np
import pytest

from src.backend.app.domain.recommendation import profile as P
from src.evaluation.recsys_bench.arms import EngineArm, EngineNoMmrArm
from src.evaluation.recsys_bench.ceiling import engine_view, unreachable
from src.evaluation.recsys_bench.engine import OfflineEngine
from src.evaluation.recsys_bench.events import filter_events
from src.evaluation.recsys_bench.models.content import ContentProfile
from src.evaluation.recsys_bench.models.data import assert_no_leak, build
from src.evaluation.recsys_bench.models.funnel import AlgoArm, CtxCache, FunnelCfg, engine_mask, rank_none, raw_mask
from src.evaluation.recsys_bench.splits import leave_last_booking_out, temporal_split
from src.evaluation.recsys_bench.tests import synthetic_world as SW
from src.evaluation.recsys_bench.tests.test_arms_metrics import AS_OF


def _setup(index, vs, kept, split, *, candidate_k=200, popular_k=50):
    engine = OfflineEngine(index, vs, split.train_purchases, candidate_k=candidate_k, popular_k=popular_k)
    data = build(kept, split, index, vs)
    assert_no_leak(data, split)
    ctx = CtxCache(data, engine)
    content = ContentProfile()
    content.fit(data)
    mk = lambda rerank, pool="engine": AlgoArm("content_profile", content, FunnelCfg(pool=pool, rerank=rerank, pool_k=candidate_k,  # noqa: E731
                                                                                     popular_k=popular_k), ctx, vs)
    return engine, data, ctx, content, mk


def _gate(index, vs, kept, split, **kw):
    engine, data, ctx, content, mk = _setup(index, vs, kept, split, **kw)
    arm_mmr, arm_none, eng, nommr = mk("mmr"), mk("none"), EngineArm(engine), EngineNoMmrArm(engine)
    mismatches, compared, truncated = [], 0, 0
    for u in sorted(split.targets):
        as_of, ev = split.as_of_by_user[u], split.train_by_user[u]
        a, b = arm_mmr.recommend(u, as_of, 20, ev), eng.recommend(u, as_of, 20, ev)
        if b.meta["strategy"] == "popular":                 # engine đi _cold_start: funnel không mô phỏng section
            assert a.meta["strategy"] == "popular"
            continue
        compared += 1
        truncated += a.meta["poolTruncated"]
        if a.product_ids != b.product_ids or a.meta["strategy"] != b.meta["strategy"] or a.meta["destination"] != b.meta["destination"] \
                or a.meta["excludedVerticals"] != (b.meta["excludedVerticals"] or []):
            mismatches.append((u, a.meta["strategy"], b.meta["strategy"], a.product_ids[:6], b.product_ids[:6]))
        c, d = arm_none.recommend(u, as_of, 20, ev), nommr.recommend(u, as_of, 20, ev)
        assert set(c.product_ids) == set(d.product_ids[:20]), (u, c.product_ids, d.product_ids[:20])   # G2 modulo hoà
        if c.product_ids and d.product_ids:
            assert c.product_ids[0] == d.product_ids[0], u
    assert not mismatches, mismatches
    return compared, truncated


def test_g1_g2_on_fixture_world_llbo_and_temporal(world, events):
    index, vs = world["index"], world["vectors"]
    kept, _ = filter_events(events, index, AS_OF)
    for split in (leave_last_booking_out(kept, index), temporal_split(kept, index)):
        compared, truncated = _gate(index, vs, kept, split)
        # 11 sản phẩm: pool = mask, không bao giờ cắt; LLBO 4 khách đều có trip, temporal chỉ 1 khách không rơi vào popular
        assert compared >= (4 if split.kind == "llbo" else 1) and truncated == 0, (split.kind, compared)


def test_g1_g2_on_synthetic_world_with_truncated_pool():
    index, vs = SW.build_world()
    events = SW.build_events(index)
    kept, _ = filter_events(events, index, SW.AS_OF)
    llbo = leave_last_booking_out(kept, index)
    assert len(llbo.targets) >= 8
    compared, truncated = _gate(index, vs, kept, llbo, candidate_k=10, popular_k=3)
    assert compared >= 8 and truncated >= 3, (compared, truncated)       # pool thật sự bị cắt ở nhiều khách
    strategies = {u: v for u, v in ((u, engine_view(llbo.train_by_user[u], index, llbo.as_of_by_user[u]).strategy) for u in llbo.targets)}
    assert len(set(strategies.values())) >= 2, strategies                 # có cả nhánh mở lẫn long_term/dormant
    temporal = temporal_split(kept, index)
    if temporal.targets:
        _gate(index, vs, kept, temporal, candidate_k=10, popular_k=3)


def test_engine_mask_matches_ceiling_unreachable_and_raw_mask(world, events):
    index, vs = world["index"], world["vectors"]
    kept, _ = filter_events(events, index, AS_OF)
    split = leave_last_booking_out(kept, index)
    engine, data, ctx, content, mk = _setup(index, vs, kept, split)
    for u in split.targets:
        as_of, train = split.as_of_by_user[u], split.train_by_user[u]
        c = ctx.get(u, as_of, train)
        if not c.profile.trips:
            continue
        mask, dest, done = engine_mask(index, c.profile)
        view = engine_view(train, index, as_of)
        target = split.targets[u]
        assert (unreachable(target, view, index) == []) == bool(mask[index.idx[target]]), (u, unreachable(target, view, index))
        assert dest == view.destination and done == view.excluded
        raw = raw_mask(index, c.profile)
        assert raw.sum() >= mask.sum() and not any(raw[b] for b in c.bought)
        assert (raw == (index.mask(only_recommendable=True) & ~np.isin(np.arange(len(index.units)), list(c.bought)))).all()


def test_mmr_pool_on_mask_uses_score_pop_id_order_for_zero_scorers(world, events):
    """Scorer toàn điểm 0 (như cooc khi không có láng giềng): ứng viên vào MMR là món phổ biến nhất, món đầu = pop_D cao nhất."""
    index, vs = world["index"], world["vectors"]
    kept, _ = filter_events(events, index, AS_OF)
    split = leave_last_booking_out(kept, index)
    engine, data, ctx, content, mk = _setup(index, vs, kept, split)

    class Zero:
        name, needs_vectors, rows = "zero", False, "none"

        def fit(self, d):
            return {}

        def score(self, c, cand):
            return np.zeros(len(cand), dtype=np.float32)

        def collab_part(self, c, cand):
            return None

    arm = AlgoArm("zero", Zero(), FunnelCfg(pool="mask", rerank="mmr", pool_k=3), ctx, vs)
    for u in split.targets:
        c = ctx.get(u, split.as_of_by_user[u], split.train_by_user[u])
        mask, _, _ = engine_mask(index, c.profile)
        cand = np.flatnonzero(mask)
        if len(cand) <= 3:
            continue
        r = arm.recommend(u, split.as_of_by_user[u], 20, split.train_by_user[u])
        top3 = rank_none(np.zeros(len(index.units), dtype=np.float32), cand, c.pop, data.product_ids, 3)
        assert set(index.idx[p] for p in r.product_ids) == set(top3) and index.idx[r.product_ids[0]] == top3[0]


def test_rank_none_tiebreak_score_then_pop_then_id():
    score = np.array([1.0, 1.0, 1.0, 0.5], dtype=np.float32)
    pop = np.array([0.2, 0.9, 0.9, 1.0], dtype=np.float32)
    ids = np.array(["z", "b", "a", "c"])
    assert rank_none(score, np.arange(4), pop, ids, 3) == [2, 1, 0]     # điểm bằng → pop cao trước → id nhỏ trước


def test_override_changes_content_scores_like_engine(world, events, monkeypatch):
    index, vs = world["index"], world["vectors"]
    kept, _ = filter_events(events, index, AS_OF)
    split = leave_last_booking_out(kept, index)
    engine, data, ctx, content, mk = _setup(index, vs, kept, split)
    u = "u1"
    c = ctx.get(u, split.as_of_by_user[u], split.train_by_user[u])
    cand = np.flatnonzero(index.mask(only_recommendable=True))
    before = content.score(c, cand).copy()
    monkeypatch.setattr(P, "W_SHORT", 0.1)
    after = content.score(c, cand)
    assert not np.allclose(before, after)
    assert before.dtype == np.float32 and after.shape == cand.shape


def test_algo_arm_requires_vectors_for_engine_pool(world, events):
    index, vs = world["index"], world["vectors"]
    kept, _ = filter_events(events, index, AS_OF)
    split = leave_last_booking_out(kept, index)
    engine, data, ctx, content, mk = _setup(index, vs, kept, split)
    with pytest.raises(ValueError, match="pool=engine"):
        AlgoArm("content_profile", content, FunnelCfg(pool="engine"), ctx, None)
    with pytest.raises(ValueError, match="không hợp lệ"):
        FunnelCfg(rerank="both")
    arm = AlgoArm("content_profile", content, FunnelCfg(mode="raw", pool="mask", rerank="none"), ctx, None)
    r = arm.recommend("u1", split.as_of_by_user["u1"], 20, split.train_by_user["u1"])
    assert r.meta["mode"] == "raw" and r.meta["pool"] == "mask" and len(r.product_ids) <= 20 and arm.key == "content_profile"
    assert AlgoArm("x", content, FunnelCfg(rerank="mmr"), ctx, None).key == "x+mmr"
