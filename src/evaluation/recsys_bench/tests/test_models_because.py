"""Day 5 Phase B — `because[]` cho scorer registry (FR-REC-03): bước `finalize` y hệt `profile.explain`, phân rã theo hàng (cooc / ease),
`star_blend_a1` ≡ `content_profile`, ials cộng lại đúng điểm, BPR rỗng, `AlgoArm --because-k K` và luật contract."""
from __future__ import annotations

import json
from types import SimpleNamespace

import numpy as np
import pytest

from src.backend.app.domain.recommendation import profile as P
from src.backend.app.domain.recommendation.profile import ResolvedEvent
from src.evaluation.recsys_bench.engine import OfflineEngine
from src.evaluation.recsys_bench.events import filter_events
from src.evaluation.recsys_bench.models import because as BC
from src.evaluation.recsys_bench.models.bpr_numpy import BprNumpy
from src.evaluation.recsys_bench.models.content import ContentProfile
from src.evaluation.recsys_bench.models.cooc import CoocTrip
from src.evaluation.recsys_bench.models.data import build
from src.evaluation.recsys_bench.models.ease import Ease
from src.evaluation.recsys_bench.models.funnel import AlgoArm, CtxCache, FunnelCfg
from src.evaluation.recsys_bench.models.star import StarBlend
from src.evaluation.recsys_bench.splits import leave_last_booking_out
from src.evaluation.recsys_bench.tests import synthetic_world as SW
from src.evaluation.recsys_bench.tests.test_arms_metrics import AS_OF
from src.evaluation.recsys_bench.tests.test_models_registry_cli import ALGOS_OK, _summary, _write, cli_env  # noqa: F401 — fixture

CONTRACT_KEYS = {"productId", "productName", "event", "daysAgo", "contribution", "kind"}


def _ev(unit, name="purchase", days=1.0):
    return ResolvedEvent(unit=unit, event_name=name, days_ago=days, trip_id="t", product_id=f"p{unit}")


def test_finalize_matches_engine_rule_on_toy_cooc():
    e0, e1, e2 = _ev(0), _ev(1, "add_to_cart", 3.4), _ev(2)
    # TOY (test_models_itemitem): R[0,2] = 0,23328, R[1,2] = 0,06804; seed w = [1, 3], Σw = 4, item 2
    raw = [(1 * 0.23328 / 4, e0, "cooc"), (3 * 0.06804 / 4, e1, "cooc")]
    out = BC.finalize(raw)
    assert [(b["unit"], b["contribution"], b["kind"]) for b in out] == [(0, 0.53, "cooc"), (1, 0.47, "cooc")]
    assert out[1]["event"] == "add_to_cart" and out[1]["daysAgo"] == 3
    # âm bị loại, phần nhỏ < 0,15 bị lọc, tối đa 3
    assert [b["contribution"] for b in BC.finalize([(-0.1, e0, "cooc"), (0.3, e1, "cooc"), (0.05, e2, "cooc")])] == [0.86]
    assert len(BC.finalize([(0.2, _ev(i), "cooc") for i in range(5)])) == 3
    assert BC.finalize([]) == [] and BC.finalize([(-1.0, e0, "cooc")]) == []


def _world_ctx(world, events):
    index, vs = world["index"], world["vectors"]
    kept, _ = filter_events(events, index, AS_OF)
    split = leave_last_booking_out(kept, index)
    engine = OfflineEngine(index, vs, split.train_purchases)
    data = build(kept, split, index, vs)
    return index, vs, split, data, CtxCache(data, engine)


def _synthetic_ctx():
    index, vs = SW.build_world()
    kept, _ = filter_events(SW.build_events(index), index, SW.AS_OF)
    split = leave_last_booking_out(kept, index)
    engine = OfflineEngine(index, vs, split.train_purchases, candidate_k=10, popular_k=3)
    data = build(kept, split, index, vs)
    return index, vs, split, data, CtxCache(data, engine)


@pytest.mark.parametrize("setup", ["world", "synthetic"])
def test_content_equals_engine_explain_and_star_a1_equals_content(setup, request):
    if setup == "world":
        index, vs, split, data, ctx = _world_ctx(request.getfixturevalue("world"), request.getfixturevalue("events"))
    else:
        index, vs, split, data, ctx = _synthetic_ctx()
    content, star1, star5 = ContentProfile(), StarBlend(a=1.0), StarBlend(a=0.5)
    for s in (content, star1, star5):
        s.fit(data)
    checked = 0
    for u in sorted(split.targets):
        c = ctx.get(u, split.as_of_by_user[u], split.train_by_user[u])
        if not c.profile.trips:
            continue
        items = np.flatnonzero(index.mask(only_recommendable=True))[:8]
        got = content.explain(c, items)
        engine = [P.explain(c.profile, int(x), data.E) for x in items]
        assert [[{k: v for k, v in b.items() if k != "kind"} for b in bs] for bs in got] == engine
        assert all(b["kind"] == "semantic" for bs in got for b in bs)
        assert star1.explain(c, items) == got                                   # a = 1 → trùng bit
        for bs in star5.explain(c, items):                                       # a = 0,5: luật chung
            assert len(bs) <= 3 and all(b["contribution"] >= 0.15 for b in bs) and all(b["kind"] in ("semantic", "cooc") for b in bs)
            assert [b["contribution"] for b in bs] == sorted((b["contribution"] for b in bs), reverse=True)
        checked += 1
    assert checked >= 2


def test_row_scorers_decompose_by_event_weights_and_drop_negative():
    index, vs, split, data, ctx = _synthetic_ctx()
    cooc, ease = CoocTrip(beta=5.0, top_k=50), Ease(lam=5.0)
    cooc.fit(data)
    ease.fit(data)
    found = 0
    for u in sorted(split.targets):
        c = ctx.get(u, split.as_of_by_user[u], split.train_by_user[u])
        if not c.profile.trips:
            continue
        contribs, Z = BC.event_weights(c.profile)
        items = np.flatnonzero(index.mask(only_recommendable=True))
        bec = cooc.explain(c, items)
        for x, bs in zip(items.tolist(), bec):
            raw = [(w * float((cooc.row(e.unit) if cooc.row(e.unit) is not None else np.zeros(data.n_items))[x]) / Z, e) for w, e in contribs]
            pos = [(v, e) for v, e in raw if v > 0]
            if not pos:
                assert bs == []
                continue
            tot = sum(v for v, _ in pos)
            expect = sorted(((round(v / tot, 2), e.unit) for v, e in pos), key=lambda t: -t[0])
            assert [(b["contribution"], b["unit"]) for b in bs] == [t for t in expect if t[0] >= 0.15][:3]
            found += bool(bs)
        for bs in ease.explain(c, items):
            assert all(b["contribution"] > 0 and b["kind"] == "cooc" for b in bs)
    assert found > 0
    # popular (không trip) → []
    empty = SimpleNamespace(profile=SimpleNamespace(trips={}, active_trip=None))
    assert cooc.explain(empty, np.array([0, 1])) == [[], []]


def test_ials_contributions_sum_to_score_and_map_to_events():
    pytest.importorskip("implicit")
    from src.evaluation.recsys_bench.models.mf_implicit import Bpr, Ials
    index, vs, split, data, ctx = _synthetic_ctx()
    ials = Ials(factors=8, iterations=5, seed=1)
    ials.fit(data)
    checked = 0
    for u in sorted(split.targets):
        c = ctx.get(u, split.as_of_by_user[u], split.train_by_user[u])
        if c.user_row is None:
            continue
        items = np.flatnonzero(index.mask(only_recommendable=True))[:5]
        for x in items.tolist():
            parts = ials.item_contributions(c, x)
            assert abs(sum(s for _, s in parts) - float(ials.score(c, np.array([x]))[0])) < 1e-3
        for bs in ials.explain(c, items):
            assert all(b["kind"] == "latent" and b["event"] in ("purchase", "add_to_cart") for b in bs)
        checked += 1
    assert checked >= 3
    assert Bpr().explain(None, np.array([3, 4])) == [[], []] and BprNumpy().explain(None, np.array([3])) == [[]]


def test_violations_contract_rules():
    old, new = {"daysAgo": 120}, {"daysAgo": 10}
    assert BC.violations("popular", False, [[]]) == [] and BC.violations("popular", False, [[new]]) == ["popular_has_because"]
    assert BC.violations("cross_vertical", True, [[new]]) == ["cold_start_has_because"]
    assert BC.violations("dormant", False, [[new], []]) == ["dormant_without_old_event"] and BC.violations("dormant", False, [[old]]) == []
    assert BC.violations("cross_vertical", False, [[new], []]) == []


def test_algo_arm_because_top_k_meta_and_coverage(world, events):
    index, vs, split, data, ctx = _world_ctx(world, events)
    content = ContentProfile()
    content.fit(data)
    for k_because in (2, 5):
        arm = AlgoArm("content_profile", content, FunnelCfg(pool="mask", rerank="none"), ctx, vs, because_k=k_because)
        assert "becauseCoverage" in arm.mean_meta and "becauseViolations" in arm.mean_meta
        for u in sorted(split.targets):
            r = arm.recommend(u, split.as_of_by_user[u], 20, split.train_by_user[u])
            bec = r.meta["because"]
            assert len(bec) == min(k_because, len(r.product_ids))
            for bs in bec:
                assert len(bs) <= 3 and all(set(b) == CONTRACT_KEYS for b in bs)
                assert all(b["contribution"] >= 0.15 for b in bs)
            assert isinstance(r.meta["coldStart"], bool)
            if r.meta["strategy"] == "popular":
                assert "becauseCoverage" not in r.meta
            else:
                assert r.meta["becauseCoverage"] == pytest.approx(np.mean([bool(b) for b in bec]))
            expect = BC.violations(r.meta["strategy"], r.meta["coldStart"], bec)
            assert r.meta["becauseViolations"] == int(bool(expect)) and r.meta["becauseViolationRules"] == expect
    off = AlgoArm("content_profile", content, FunnelCfg(pool="mask", rerank="none"), ctx, vs)
    u = sorted(split.targets)[0]
    r = off.recommend(u, split.as_of_by_user[u], 20, split.train_by_user[u])
    assert "because" not in r.meta and "becauseCoverage" not in r.meta
    with pytest.raises(ValueError):
        AlgoArm("content_profile", content, FunnelCfg(pool="mask", rerank="none"), ctx, vs, because_k=-1)


def test_cli_because_k_columns_and_per_user(cli_env):
    env = cli_env
    y = _write(env.tmp, "algos.yaml", ALGOS_OK)
    base = ["run", "--algos", str(y), "--only", "content_profile", "--only", "cooc_trip", "--funnel-rerank", "none", "--split", "llbo",
            "--vectors", "numpy", "--split-file", str(env.frozen)]
    r = env.runner.invoke(env.cli.app, base + ["--run-id", "b", "--because-k", "5"])
    assert r.exit_code == 0, r.output
    s = _summary(env, "b")
    assert s["because"]["k"] == 5 and "dormant" in s["because"]["rules"] and s["history"][0]["params"]["becauseK"] == 5
    rows = {row["arm"]: row for row in s["rows"]}
    assert "because_coverage" in rows["content_profile"] and "because_violations" in rows["cooc_trip"]
    assert "Because@5" in r.output and "Vi phạm because" in r.output
    per_user = [json.loads(x) for x in (env.home / "runs" / "b" / "per_user.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    assert all("because" in p for p in per_user)
    r = env.runner.invoke(env.cli.app, base + ["--run-id", "b10", "--because-k", "10"])
    assert r.exit_code == 0 and "Because@10" in r.output and _summary(env, "b10")["because"]["k"] == 10
    r = env.runner.invoke(env.cli.app, base + ["--run-id", "b0"])
    assert r.exit_code == 0 and "because" not in _summary(env, "b0") and "because_coverage" not in _summary(env, "b0")["rows"][0]
    assert env.runner.invoke(env.cli.app, base + ["--run-id", "bx", "--because-k", "25"]).exit_code == 1        # > k
    # cùng run-id, chạy lại cùng arm với because → thay hàng (cùng algosHash)
    r = env.runner.invoke(env.cli.app, base + ["--run-id", "b0", "--because-k", "5"])
    assert r.exit_code == 0 and "because_coverage" in _summary(env, "b0")["rows"][0]
