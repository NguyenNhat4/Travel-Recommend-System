"""Part 8 runner: truy xuất (store / embedder giả) → chấm → ghi → đọc lại → so sánh, trên `gold_small.jsonl` + catalog
`sample`. Số kỳ vọng lấy từ `test_metrics.py` (arm A của `run_small.json`): FakeStore trả đúng top-10 của arm A, nên
`sb run --arm B0` phải ra cùng overall với `test_aggregate_arm_a`. "Done khi" của spec Part 8: so một arm với chính nó
→ Δ = 0, p = 0,5.
"""
from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path

import numpy as np
import pytest
from typer.testing import CliRunner

from evaluation.search_bench import catalog, paths, runner as R
from evaluation.search_bench.__main__ import app
from evaluation.search_bench.arms import load_arm
from evaluation.search_bench.store import filters as F
from evaluation.search_bench.store.weaviate_store import Hit

FX = Path(__file__).parent / "fixtures"
GOLD = FX / "gold_small.jsonl"
APPROX = dict(rel=0, abs=1e-12)
runner_cli = CliRunner()


@pytest.fixture()
def sample_home(cfg, home):
    catalog.build_catalog(cfg, "sample")
    return home


@pytest.fixture()
def run_small():
    d = json.loads((FX / "run_small.json").read_text(encoding="utf-8"))
    return d["ids"], d["arms"]


class FakeStore:
    """Trả top-10 của arm A trong run_small.json cho mọi câu (theo qid của text); ghi lại filter được gửi xuống."""

    def __init__(self, ids: dict[str, str], arm: dict[str, list[str]], gold_text_to_qid: dict[str, str], *, dist: float = 0.3):
        self.ids, self.arm, self.q, self.dist = ids, arm, gold_text_to_qid, dist
        self.calls: list[tuple] = []
        self._i = 0
        self.order = list(arm)

    def _hits(self, qid, limit):
        names = self.arm.get(qid, [])[:limit]
        return [Hit(rank=i, product_id=self.ids[n], name=n, destination="", taxonomy="", variant="", distance=self.dist,
                    score=1.0 / i) for i, n in enumerate(names, 1)]

    def dense(self, physical, qvec, limit, filters=None):
        qid = self.order[self._i % len(self.order)]
        self._i += 1
        self.calls.append(("dense", qid, filters))
        return self._hits(qid, limit)

    def bm25(self, physical, query, limit, *, fold_mode, filters=None):
        qid = self.q[query]
        self.calls.append(("bm25", qid, filters))
        return self._hits(qid, limit)

    # dùng khi test CLI (thay _store)
    def check_ready(self, physical, items_sha256=None, expected=None):
        return {"cache_model": "fake", "ascii_fold_mode": "analyzer", "n": 26}

    def description(self, physical):
        return self.check_ready(physical)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return None


class FakeEmb:
    name, dim = "fake", 4

    def __init__(self):
        self.n_new = self.n_cached = 0
        self.stats = None

    def embed(self, texts, input_type):
        self.n_cached += len(texts)
        return np.zeros((len(texts), self.dim), dtype="float32")

    def close(self):
        pass


def _env(cfg, run_id="t1"):
    return R.load_env(cfg, "sample", GOLD, run_id=run_id)


def _store(run_small, env):
    ids, arms = run_small
    return FakeStore(ids, arms["A"], {g.text: g.qid for g in env.gold})


def test_env_fixture_gold_gets_fixture_version(cfg, sample_home):
    env = _env(cfg)
    assert env.gold_version.startswith("fixture:") and len(env.gold) == 10 and env.n_items == 26
    assert env.gold_sha256 and env.k == 10


def test_run_b0_matches_hand_numbers_and_roundtrips(cfg, sample_home, run_small):
    env = _env(cfg)
    st = _store(run_small, env)
    results, rows = R.run_arm(env, load_arm("B0"), store=st, embedder_factory=lambda a: FakeEmb(), physical="P",
                              collection="products__T3+R__cohere_v3", fold_mode="analyzer")
    o = results["overall"]
    assert o["recall@10"] == pytest.approx(0.7129629629629629, **APPROX)      # test_metrics.test_aggregate_arm_a
    assert o["ndcg@10"] == pytest.approx(0.555104909681827, **APPROX)
    assert o["judged@10"] == pytest.approx(3.4 / 8, **APPROX) and o["zero_result_out_of_catalog"] == 1.0
    assert results["arm"] == "B0" and results["gold_version"].startswith("fixture:") and results["stale"] is False
    assert results["resolved_config_hash"] == R.config_hash(load_arm("B0")) and results["vs_parent"] is None
    assert results["embed"] == {"model": "fake", "input_type": "query", "n_new": 0, "n_cached": 10, "usd": 0.0, "n_calls": 0}
    assert all(c[2] is None for c in st.calls)                                # B0: không filter
    assert results["needs_labels"]                                            # judged 0,425 < 0,80 trên fixture
    # đọc lại: top_ids giữ nguyên thứ tự, None giữ None
    back = R.read_rows("t1", "B0")
    assert [r["top_ids"] for r in back] == [r["top_ids"] for r in rows]
    assert [r["qid"] for r in back] == [g.qid for g in env.gold]
    assert back[8]["recall@10"] is None and back[8]["top_ids"] == []          # q009 out_of_catalog: không kết quả
    assert R.read_results("t1", "B0")["overall"]["recall@10"] == pytest.approx(o["recall@10"], **APPROX)
    assert (R.arm_dir("t1", "B0", create=False) / R.PER_QUERY).exists()
    assert R.latest_run_id() == "t1"


def test_self_compare_is_zero_and_half(cfg, sample_home, run_small):
    env = _env(cfg)
    R.run_arm(env, load_arm("B0"), store=_store(run_small, env), embedder_factory=lambda a: FakeEmb(), physical="P",
              collection="c", fold_mode="analyzer")
    rows = R.read_rows("t1", "B0")
    cmp = R.compare(rows, rows, cfg)
    assert cmp["recall@10"]["delta"] == 0.0 and cmp["recall@10"]["p_one_sided"] == 0.5 and cmp["verdict"] == "TIE"


def test_cutoff_and_qu_filter(cfg, sample_home, run_small, monkeypatch):
    monkeypatch.setattr(F, "to_weaviate", lambda node: node)
    env = _env(cfg)
    arm = load_arm("B0").model_copy(update={"id": "X", "filters": {"qu": True, "amenity_must": "none"},
                                            "cutoff": {"max_vector_distance": 0.2}})
    st = _store(run_small, env)
    got = R.retrieve(arm, env, store=st, embedder=FakeEmb(), physical="P", fold_mode="analyzer")
    assert all(g.top_ids == [] for g in got)                                  # mọi hit distance 0,3 > cutoff 0,2
    sent = {qid: f for _, qid, f in st.calls}
    assert sent["q007"] is not None and sent["q008"] is not None and sent["q001"] is None   # chỉ câu có filter
    assert next(g for g in got if g.qid == "q007").applied_filter is not None
    st.dist = 0.1
    got = R.retrieve(arm, env, store=st, embedder=FakeEmb(), physical="P", fold_mode="analyzer")
    assert got[0].top_scores[0] == pytest.approx(0.9, **APPROX)


def test_bm25_arm_uses_query_text(cfg, sample_home, run_small):
    env = _env(cfg)
    arm = load_arm("B0").model_copy(update={"id": "S1", "retrieval": "bm25"})
    st = _store(run_small, env)
    got = R.retrieve(arm, env, store=st, embedder=None, physical="P", fold_mode="shadow")
    assert [c[0] for c in st.calls] == ["bm25"] * 10 and got[0].top_scores[0] == 1.0


def test_unsupported_retrieval_is_explicit(cfg, sample_home):
    env = _env(cfg)
    with pytest.raises(R.RunnerError, match="chưa cài"):
        R.retrieve(load_arm("B0").model_copy(update={"retrieval": "hybrid"}), env, store=None, embedder=None, physical="P",
                   fold_mode="analyzer")


def test_gold_in_gold_dir_requires_tag(cfg, sample_home, tmp_path, monkeypatch):
    from evaluation.search_bench import holes as H
    gdir = tmp_path / "gold"
    gdir.mkdir()
    g = gdir / "gold.jsonl"
    g.write_bytes(GOLD.read_bytes())
    monkeypatch.setattr(paths, "GOLD_DIR", gdir)
    monkeypatch.setattr(H, "gold_version_of", lambda p, tags=None: None)
    with pytest.raises(R.RunnerError, match="không khớp tag gold_v"):
        R.load_env(cfg, "sample", g, run_id="t")
    assert R.load_env(cfg, "sample", g, run_id="t", allow_untagged=True).gold_version is None
    monkeypatch.setattr(H, "gold_version_of", lambda p, tags=None: "gold_v1")
    assert R.load_env(cfg, "sample", g, run_id="t").gold_version == "gold_v1"


def test_config_hash_ignores_id_and_description():
    a = load_arm("B0")
    assert R.config_hash(a) == R.config_hash(a.model_copy(update={"id": "Z", "description": "khác", "stage": "S"}))
    assert R.config_hash(a) != R.config_hash(a.model_copy(update={"cutoff": {"max_vector_distance": 0.4}}))


def test_new_run_id_shape():
    from datetime import datetime
    rid = R.new_run_id(datetime(2026, 10, 1, 9, 5))
    assert rid.startswith("20261001-0905-") and len(rid) > len("20261001-0905-")


# ------------------------------------------------------------------ CLI (store + embedder giả thay Weaviate / Cohere)
def test_cli_run_and_compare(cfg, sample_home, run_small, monkeypatch):
    import evaluation.search_bench.__main__ as main
    import evaluation.search_bench.embed as E
    env = _env(cfg)
    st = _store(run_small, env)

    @contextmanager
    def fake_store(_cfg):
        yield st
    monkeypatch.setattr(main, "_store", fake_store)
    monkeypatch.setattr(E, "make_embedder", lambda *a, **k: FakeEmb())
    res = runner_cli.invoke(app, ["--dataset", "sample", "--run-id", "t9", "run", "--arm", "B0", "--gold", str(GOLD), "--model", "fake"])
    assert res.exit_code == 0, res.output + repr(res.exception)
    assert "overall" in res.output and "NEEDS_LABELS" in res.output and "0.713" in res.output
    res2 = runner_cli.invoke(app, ["--dataset", "sample", "--run-id", "t9", "run", "--arm", "B0", "--gold", str(GOLD), "--model", "fake"])
    assert res2.exit_code == 0 and "bỏ qua" in res2.output                    # cùng hash + gold_version → không chạy lại
    res3 = runner_cli.invoke(app, ["--run-id", "t9", "compare", "B0", "B0"])
    assert res3.exit_code == 0, res3.output + repr(res3.exception)
    assert "TIE" in res3.output and "+0.00" in res3.output and "0.500" in res3.output
    res4 = runner_cli.invoke(app, ["--run-id", "t9", "compare", "B0", "S9"])
    assert res4.exit_code == 2 and "chưa có kết quả S9" in res4.output
    res5 = runner_cli.invoke(app, ["--dataset", "sample", "--run-id", "t9", "run", "--arm", "KHONG_CO", "--gold", str(GOLD)])
    assert res5.exit_code == 2 and "không có arm" in res5.output
