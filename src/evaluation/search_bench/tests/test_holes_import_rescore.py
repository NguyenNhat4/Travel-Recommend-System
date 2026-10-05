"""Part 11 (nửa sau): `gold holes` → gán → `holes import` → `verify-append` → `rescore`, đúng tình huống "Done khi" của spec:
3 cặp chưa gán trong top-10 (1 thuộc câu out_of_catalog) → file hole 2 dòng + 1 auto_ooc; import tăng version và
verify-append xanh; sửa tay một nhãn cũ → verify-append đỏ; rescore đưa judged@10 về 1,0 và metric khớp chạy lại từ đầu.
Catalog `sample` (26 unit) trong SBENCH_HOME tạm; PoolView dựng thẳng từ items.parquet (không cần text parquet)."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pytest
import yaml
from typer.testing import CliRunner

from evaluation.search_bench import catalog, gold as G, holes as H, paths, runner as R
from evaluation.search_bench.__main__ import app
from evaluation.search_bench.arms import load_arm
from evaluation.search_bench.gold import RuleViolation, check_gold
from evaluation.search_bench.gold_schema import LabelRow, read_gold_jsonl, read_pool_csv, read_pool_meta, write_labels_csv
from evaluation.search_bench.store.weaviate_store import Hit

FX = Path(__file__).parent / "fixtures"
GOLD = FX / "gold_small.jsonl"
runner_cli = CliRunner()


def assert_exit(res, code, *msgs):
    assert res.exit_code == code, res.output + repr(res.exception)
    for m in msgs:
        assert m in res.output, (m, res.output)


@pytest.fixture()
def sample_home(cfg, home):
    catalog.build_catalog(cfg, "sample")
    return home


def _view(cfg) -> G.PoolView:
    items = catalog.read_items("sample")
    vocab = json.loads((paths.data_dir("sample") / paths.AMENITY_VOCAB).read_text(encoding="utf-8"))
    rows = {}
    for r in items[["product_id", "name", "variant", "destination", "star_rating", "amenity_ids"]].to_dict("records"):
        star = r["star_rating"]
        r["star_rating"] = None if star is None or np.isnan(star) else round(float(star), 1)
        r["amenity_ids"] = [int(x) for x in (r["amenity_ids"] if r["amenity_ids"] is not None else [])]
        rows[r["product_id"]] = r
    return G.PoolView(items=rows, snippets={p: f"snippet {p[:6]}" for p in rows}, children={},
                      amenity_label={int(i): e["label"] for i, e in vocab.items()},
                      amenity_order={int(i): (0, -int(e.get("freq") or 0), int(i)) for i, e in vocab.items()},
                      key_to_id={e["key"]: int(i) for i, e in vocab.items()})


def _unlabeled(records, qid, n, view):
    judged = set(next(r for r in records if r.qid == qid).judgments)
    return [p for p in sorted(view.items) if p not in judged][:n]


# ------------------------------------------------------------------ find + write + import + verify (hàm)
def test_holes_done_when_scenario(cfg, sample_home, tmp_path, monkeypatch):
    records = read_gold_jsonl(GOLD)
    view = _view(cfg)
    by = {r.qid: r for r in records}
    top_q1 = list(by["q001"].judgments)[:3] + _unlabeled(records, "q001", 1, view)     # 1 hole ở câu thường
    top_q2 = list(by["q002"].judgments)[:2] + _unlabeled(records, "q002", 1, view)     # 1 hole ở câu thường
    top_q9 = _unlabeled(records, "q009", 1, view)                                       # 1 hole ở câu out_of_catalog
    rows = [{"qid": "q001", "top_ids": top_q1}, {"qid": "q002", "top_ids": top_q2}, {"qid": "q009", "top_ids": top_q9},
            {"qid": "q003", "top_ids": list(by["q003"].judgments)}]
    to_label, auto = H.find_holes(records, {"B0": rows, "X": rows[:1]}, k=10)
    assert [(h.qid, h.product_id) for h in to_label] == [("q001", top_q1[-1]), ("q002", top_q2[-1])]  # q001 trước: 2 arm thấy
    assert to_label[0].arms == ["B0", "X"] and to_label[0].best_rank == 4 and to_label[1].arms == ["B0"]
    assert [(h.qid, h.product_id) for h in auto] == [("q009", top_q9[0])]

    out = tmp_path / "holes" / "fixture__B0"
    s = H.write_holes(to_label, auto, records, view, out, seed=42, split=False, snapshot="2026-09-23", collection="c", k=10,
                      run_id="t", arms=["B0", "X"], gold_version="fixture:x", tag="B0")
    assert s["n_to_label"] == 2 and s["n_auto_ooc"] == 1 and s["n_queries"] == 2 and list(s["files"]) == ["A"]
    meta = read_pool_meta(out / "pool_meta.json")
    pool = read_pool_csv(out / "pool_A.csv")
    assert [(r.qid, r.product_id) for r in pool] == [(h.qid, h.product_id) for h in to_label]
    assert pool[0].query == by["q001"].text and pool[0].slice == "dest_type" and pool[0].source == "dense" and pool[0].rank_dense == 4
    assert pool[0].snippet.startswith("snippet") and pool[0].name and not pool[0].is_overlap
    assert (out / "meta.csv").read_text(encoding="utf-8-sig").splitlines()[1].startswith("q001,")
    assert "q009" in (out / "auto_ooc.csv").read_text(encoding="utf-8-sig")
    # app gán nhãn mở được thư mục hole như một pool
    from evaluation.search_bench import labeling_core as L
    sess = L.open_session(out / "pool_meta.json", "A")
    assert sess.qids == ["q001", "q002"] and sess.labels_path == out / "labels" / "labels_A.csv"

    # gán nhãn → import
    now = datetime.now().astimezone()
    write_labels_csv([LabelRow(qid=r.qid, product_id=r.product_id, label=lab, labeler="A", labeled_at=now, pool_sha=meta.files["A"].sha256)
                      for r, lab in zip(pool, (2, 1))], out / "labels" / "labels_A.csv")
    new, stats = H.import_holes(records, out, version="gold_v2", tag="B0")
    assert stats == {"human": 2, "auto_ooc": 1, "queries": 3}
    nb = {r.qid: r for r in new}
    assert nb["q001"].judgments[top_q1[-1]] == 2 and nb["q001"].provenance[top_q1[-1]] == "holes:B0@gold_v2"
    assert nb["q002"].judgments[top_q2[-1]] == 1 and nb["q009"].judgments[top_q9[0]] == 0
    assert nb["q009"].provenance[top_q9[0]] == "auto_ooc:B0@gold_v2"
    assert H.verify_append(records, new) == []
    # check_gold: không thêm lỗi nào ở các câu vừa nhận hole (fixture gold_small.jsonl cũ vốn thiếu expected_children ở q005)
    assert not [p for p in check_gold(new, 1, list(cfg.gold.slices)).problems if p.split()[0].split("/")[0] in ("q001", "q002", "q009")]
    # import lần hai: cặp đã có nhãn → từ chối (gold chỉ thêm)
    with pytest.raises(RuleViolation) as e:
        H.import_holes(new, out, version="gold_v3", tag="B0")
    assert any("đã có nhãn" in p for p in e.value.problems)
    # thiếu nhãn → từ chối trừ partial
    write_labels_csv([LabelRow(qid=pool[0].qid, product_id=pool[0].product_id, label=2, labeler="A", labeled_at=now,
                               pool_sha=meta.files["A"].sha256)], out / "labels" / "labels_A.csv")
    with pytest.raises(RuleViolation) as e:
        H.import_holes(records, out, version="gold_v2", tag="B0")
    assert any("chưa gán" in p for p in e.value.problems)
    part, st2 = H.import_holes(records, out, version="gold_v2", tag="B0", partial=True)
    assert st2["human"] == 1 and st2["auto_ooc"] == 1
    # 05/10: nhãn máy (provenance) — chưa duyệt → từ chối; duyệt giữ nguyên → provenance `holes:<tag>:machine@…`
    k0, k1 = (pool[0].qid, pool[0].product_id), (pool[1].qid, pool[1].product_id)
    write_labels_csv([LabelRow(qid=r.qid, product_id=r.product_id, label=lab, labeler="A", labeled_at=now, pool_sha=meta.files["A"].sha256)
                      for r, lab in zip(pool, (2, 1))], out / "labels" / "labels_A.csv")
    with pytest.raises(RuleViolation) as e:
        H.import_holes(records, out, version="gold_v2", tag="B0", sources={k0: "machine_unreviewed"})
    assert any("nhãn máy chưa duyệt" in p for p in e.value.problems)
    mach, st3 = H.import_holes(records, out, version="gold_v2", tag="B0", sources={k0: "machine_accepted", k1: "machine_edited"})
    assert st3 == {"human": 1, "auto_ooc": 1, "queries": 3, "machine": 1, "machine_unreviewed": 0}
    mb = {r.qid: r for r in mach}
    assert mb[k0[0]].provenance[k0[1]] == "holes:B0:machine@gold_v2" and mb[k1[0]].provenance[k1[1]] == "holes:B0@gold_v2"
    _, st4 = H.import_holes(records, out, version="gold_v2", tag="B0", sources={k0: "machine_unreviewed"}, accept_unreviewed=True)
    assert st4["machine_unreviewed"] == 1
    # sửa tay nhãn cũ → verify-append đỏ
    tampered = [r.model_copy(update={"judgments": {**r.judgments, list(r.judgments)[0]: 0}}) if r.qid == "q001" else r for r in new]
    assert H.verify_append(records, tampered)


def test_cap_holes_balances_queries_and_is_deterministic():
    records = [
        G.GoldRecord(qid="q1", text="a", slice="s1", judgments={"old": 2}, provenance={"old": "human"}),
        G.GoldRecord(qid="q2", text="b", slice="s2", judgments={"old": 2}, provenance={"old": "human"}),
    ]
    holes = [
        H.Hole("q1", f"a{i}", ["A", "B"] if i == 0 else ["A"], i + 1) for i in range(5)
    ] + [H.Hole("q2", f"b{i}", ["A"], i + 1) for i in range(5)]
    got = H.cap_holes(holes, records, 4, seed=42)
    assert got == H.cap_holes(holes, records, 4, seed=42)
    assert {h.qid for h in got} == {"q1", "q2"}
    assert any(h.product_id == "a0" for h in got)


def test_write_holes_split_alternates_queries(cfg, sample_home, tmp_path):
    records = read_gold_jsonl(GOLD)
    view = _view(cfg)
    rows = [{"qid": q, "top_ids": _unlabeled(records, q, 2, view)} for q in ("q001", "q002", "q003")]
    to_label, auto = H.find_holes(records, {"B0": rows}, k=10)
    out = tmp_path / "h"
    s = H.write_holes(to_label, auto, records, view, out, seed=1, split=True, snapshot="s", collection="c", k=10, run_id="t",
                      arms=["B0"], gold_version=None, tag="t")
    assert s["files"]["A"]["n_queries"] == 2 and s["files"]["B"]["n_queries"] == 1
    qa = {r.qid for r in read_pool_csv(out / "pool_A.csv")}
    qb = {r.qid for r in read_pool_csv(out / "pool_B.csv")}
    assert qa & qb == set() and qa | qb == {"q001", "q002", "q003"}


# ------------------------------------------------------------------ rescore + CLI
class _Store:
    """Trả top-10 = nhãn của câu + 1 ứng viên chưa nhãn (để có hole), theo thứ tự câu của gold."""

    def __init__(self, records, view):
        self.by = {r.qid: r for r in records}
        self.view, self.i, self.order = view, 0, [r.qid for r in records]

    def dense(self, physical, qvec, limit, filters=None):
        q = self.order[self.i % len(self.order)]
        self.i += 1
        ids = list(self.by[q].judgments)[:limit - 1] + _unlabeled(list(self.by.values()), q, 1, self.view)
        return [Hit(rank=i, product_id=p, name="", destination="", taxonomy="", variant="", distance=0.2) for i, p in enumerate(ids, 1)]

    def check_ready(self, *a, **k):
        return {"cache_model": "fake", "ascii_fold_mode": "analyzer", "n": 26}

    description = check_ready

    def __enter__(self):
        return self

    def __exit__(self, *e):
        return None


class _Emb:
    name, dim, n_new, n_cached, stats = "fake", 4, 0, 0, None

    def embed(self, texts, input_type):
        return np.zeros((len(texts), 4), dtype="float32")

    def close(self):
        pass


def test_rescore_after_holes_restores_judged_and_matches_fresh_run(cfg, sample_home, tmp_path, monkeypatch):
    records = read_gold_jsonl(GOLD)
    view = _view(cfg)
    env = R.load_env(cfg, "sample", GOLD, run_id="t1")
    st = _Store(records, view)
    res0, _ = R.run_arm(env, load_arm("B0"), store=st, embedder_factory=lambda a: _Emb(), physical="P", collection="c", fold_mode="analyzer")
    assert res0["overall"]["judged@10"] < 1.0 and res0["needs_labels"]
    rows = R.read_rows("t1", "B0")
    to_label, auto = H.find_holes(records, {"B0": rows}, k=10)
    out = tmp_path / "holes"
    H.write_holes(to_label, auto, records, view, out, seed=42, split=False, snapshot="s", collection="c", k=10, run_id="t1",
                  arms=["B0"], gold_version=env.gold_version, tag="B0")
    meta = read_pool_meta(out / "pool_meta.json")
    pool = read_pool_csv(out / "pool_A.csv")
    now = datetime.now().astimezone()
    write_labels_csv([LabelRow(qid=r.qid, product_id=r.product_id, label=1, labeler="A", labeled_at=now, pool_sha=meta.files["A"].sha256)
                      for r in pool], out / "labels" / "labels_A.csv")
    new, _ = H.import_holes(records, out, version="gold_v2", tag="B0")
    g2 = tmp_path / "gold2.jsonl"
    H.write_gold(new, g2)
    env2 = R.load_env(cfg, "sample", g2, run_id="t1")
    res, rows2, info = R.rescore_arm(env2, "t1", "B0")
    assert res["overall"]["judged@10"] == 1.0 and res["needs_labels"] == [] and info["missing"] == []
    assert res["condensed"]["mode"] == "condensed" and res["condensed"]["coverage"]["retained_ratio"] == 1.0
    assert res["rescored_from"] == env.gold_version and res["gold_version"] == env2.gold_version and res["latency_ms"] == res0["latency_ms"]
    # metric khớp chạy lại từ đầu trên gold mới
    st2 = _Store(records, view)
    fresh, _ = R.run_arm(env2.__class__(**{**env2.__dict__, "run_id": "t2"}), load_arm("B0"), store=st2,
                         embedder_factory=lambda a: _Emb(), physical="P", collection="c", fold_mode="analyzer")
    for m in ("recall@10", "ndcg@10", "mrr@10", "judged@10"):
        assert res["overall"][m] == pytest.approx(fresh["overall"][m], abs=1e-12)
    vers = R.available_versions("t1", "B0")
    assert set(vers) == {env.gold_version, env2.gold_version}
    got, stored_rows, gv = R.read_results_at("t1", "B0", env2.gold_version)
    assert gv == env2.gold_version and got["rescored_from"] == env.gold_version
    assert R.compare(stored_rows, stored_rows, cfg, condensed=True)["verdict"] == "TIE"
    assert R.read_results_at("t1", "B0")[2] == max(vers, key=R._version_key)
    with pytest.raises(R.RunnerError, match="không có kết quả trên gold"):
        R.read_results_at("t1", "B0", "gold_v99")


def test_cli_holes_import_rescore(cfg, sample_home, tmp_path, monkeypatch):
    import evaluation.search_bench.__main__ as main
    import evaluation.search_bench.embed as E
    from contextlib import contextmanager
    records = read_gold_jsonl(GOLD)
    view = _view(cfg)
    st = _Store(records, view)

    @contextmanager
    def fake_store(_cfg):
        yield st
    monkeypatch.setattr(main, "_store", fake_store)
    monkeypatch.setattr(E, "make_embedder", lambda *a, **k: _Emb())
    monkeypatch.setattr(G, "load_pool_view", lambda cfg_, ds, variant: view)
    gold_p = tmp_path / "g" / "gold.jsonl"
    gold_p.parent.mkdir()
    gold_p.write_bytes(GOLD.read_bytes())
    res = runner_cli.invoke(app, ["--dataset", "sample", "--run-id", "t7", "run", "--arm", "B0", "--gold", str(gold_p), "--model", "fake"])
    assert_exit(res, 0)
    out = tmp_path / "holes"
    res = runner_cli.invoke(app, ["--dataset", "sample", "--run-id", "t7", "gold", "holes", "--arms", "B0", "--gold", str(gold_p),
                                  "--out-dir", str(out), "--tag", "M2"])
    assert_exit(res, 0, "cặp cần gán", "hole out_of_catalog tự gán 0", "holes import")
    meta = read_pool_meta(out / "pool_meta.json")
    pool = read_pool_csv(out / "pool_A.csv")
    now = datetime.now().astimezone()
    write_labels_csv([LabelRow(qid=r.qid, product_id=r.product_id, label=1, labeler="A", labeled_at=now, pool_sha=meta.files["A"].sha256)
                      for r in pool], out / "labels" / "labels_A.csv")       # nhãn 1: nhãn 2 ở parent_child phải tick hạng phòng
    monkeypatch.setattr(H, "list_gold_tags", lambda: ["gold_v1"])
    res = runner_cli.invoke(app, ["gold", "holes", "import", str(out), "--gold", str(gold_p)])
    assert_exit(res, 0, "nhãn người", "auto_ooc", "version gold_v2")
    log = yaml.safe_load((gold_p.parent / "changelog.yaml").read_text(encoding="utf-8"))
    assert log[-1]["action"] == "holes_import" and log[-1]["tag"] == "M2" and log[-1]["new_labels_by_source"]["human"] == len(pool)
    assert_exit(runner_cli.invoke(app, ["gold", "verify-append", str(GOLD), str(gold_p)]), 0, "verify-append xanh")
    res = runner_cli.invoke(app, ["--dataset", "sample", "--run-id", "t7", "rescore", "--gold", str(gold_p)])
    assert_exit(res, 0, "B0:", "judged@10 1.000")
    assert (R.arm_dir("t7", "B0", create=False) / f"results@fixture_{H.file_sha256(gold_p)[:8]}.json").exists()   # ':' → '_' (Windows)
    latest = runner_cli.invoke(app, ["--run-id", "t7", "compare", "B0", "B0"])
    assert_exit(latest, 0, "TIE", "judged@10", "1.000")
    version = R.read_results_at("t7", "B0")[2]
    assert_exit(runner_cli.invoke(app, ["--run-id", "t7", "compare", "B0", "B0", "--gold", version]),
                0, "TIE", "1.000")
    assert_exit(runner_cli.invoke(app, ["--run-id", "t7", "compare", "B0", "B0", "--gold", "gold_v99"]),
                2, "không có kết quả trên gold gold_v99")
    # không còn hole → exit 1
    assert_exit(runner_cli.invoke(app, ["--dataset", "sample", "--run-id", "t7", "gold", "holes", "--arms", "B0", "--gold", str(gold_p),
                                        "--out-dir", str(tmp_path / "h2")]), 1, "không có hole")


def test_cli_holes_qids_and_new_since(cfg, sample_home, tmp_path, monkeypatch):
    """05/10 (gold_v4): `--qids` / `--new-since` chỉ quét các câu được chọn — cap không bị loãng bởi câu cũ."""
    import evaluation.search_bench.__main__ as main
    import evaluation.search_bench.embed as E
    from contextlib import contextmanager
    records = read_gold_jsonl(GOLD)
    view = _view(cfg)
    st = _Store(records, view)

    @contextmanager
    def fake_store(_cfg):
        yield st
    monkeypatch.setattr(main, "_store", fake_store)
    monkeypatch.setattr(E, "make_embedder", lambda *a, **k: _Emb())
    monkeypatch.setattr(G, "load_pool_view", lambda cfg_, ds, variant: view)
    gold_p = tmp_path / "g" / "gold.jsonl"
    gold_p.parent.mkdir()
    gold_p.write_bytes(GOLD.read_bytes())
    assert_exit(runner_cli.invoke(app, ["--dataset", "sample", "--run-id", "t8", "run", "--arm", "B0", "--gold", str(gold_p),
                                        "--model", "fake"]), 0)
    base = ["--dataset", "sample", "--run-id", "t8", "gold", "holes", "--arms", "B0", "--gold", str(gold_p)]
    full = tmp_path / "full"
    assert_exit(runner_cli.invoke(app, [*base, "--out-dir", str(full)]), 0)
    with_holes = sorted({r.qid for r in read_pool_csv(full / "pool_A.csv")})
    one = with_holes[0]
    out = tmp_path / "one"
    res = runner_cli.invoke(app, [*base, "--out-dir", str(out), "--qids", one])
    assert_exit(res, 0, f"chỉ quét 1/{len(records)} câu")
    assert {r.qid for r in read_pool_csv(out / "pool_A.csv")} == {one}
    assert_exit(runner_cli.invoke(app, [*base, "--out-dir", str(tmp_path / "x"), "--qids", "c0000"]), 2,
                "--qids không có trong gold: c0000")
    assert_exit(runner_cli.invoke(app, [*base, "--out-dir", str(tmp_path / "y"), "--new-since", str(gold_p)]), 2,
                "không còn câu nào")
    assert_exit(runner_cli.invoke(app, [*base, "--out-dir", str(tmp_path / "z"), "--qids", ""]), 2, "--qids rỗng")
    bad = tmp_path / "bad.jsonl"
    bad.write_text("{not json}\n", encoding="utf-8")
    for ref in (bad, tmp_path):                                             # file hỏng, thư mục
        assert_exit(runner_cli.invoke(app, [*base, "--out-dir", str(tmp_path / "w"), "--new-since", str(ref)]), 2,
                    "--new-since")
