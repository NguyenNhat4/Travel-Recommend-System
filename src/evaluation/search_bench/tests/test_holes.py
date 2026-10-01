"""Part 11 (nửa đầu): `retire`, `verify-append`, changelog và version gold theo tag git — trên fixture `gold_small/`.

Mã thoát nhóm `sb gold`: 0 đạt · 1 vi phạm luật · 2 lỗi đầu vào. Phần version theo git chạy trong một repo tạm (git init
trong tmp_path) để không phụ thuộc tag của repo thật; bỏ qua nếu máy không có `git`.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from evaluation.search_bench import holes as H
from evaluation.search_bench.__main__ import app
from evaluation.search_bench.gold import RuleViolation
from evaluation.search_bench.gold_schema import read_gold_jsonl, write_gold_jsonl

FX = Path(__file__).parent / "fixtures" / "gold_small"
runner = CliRunner()


def run(*args):
    return runner.invoke(app, ["gold", *map(str, args)])


def assert_exit(res, code: int, *msgs: str):
    assert res.exit_code == code, res.output + repr(res.exception)
    if code:
        assert isinstance(res.exception, SystemExit), repr(res.exception)
    for m in msgs:
        assert m in res.output, (m, res.output)


@pytest.fixture()
def gold(tmp_path):
    p = tmp_path / "gold" / "gold.jsonl"
    p.parent.mkdir()
    shutil.copyfile(FX / "gold_expected.jsonl", p)
    return p


# ------------------------------------------------------------------ retire (hàm)
def test_retire_only_flips_status_and_keeps_labels():
    recs = read_gold_jsonl(FX / "gold_expected.jsonl")
    out = H.retire(recs, "c9001")
    by = {r.qid: r for r in out}
    assert by["c9001"].status == "retired" and by["c9001"].judgments == {r.qid: r for r in recs}["c9001"].judgments
    assert [r.status for r in out if r.qid != "c9001"] == ["active"] * (len(recs) - 1)
    with pytest.raises(RuleViolation) as e:
        H.retire(out, "c9001")
    assert e.value.problems == ["c9001: đã retired"]
    with pytest.raises(RuleViolation) as e:
        H.retire(recs, "c0000")
    assert e.value.problems == ["c0000: không có trong gold"]


# ------------------------------------------------------------------ verify-append (hàm)
def test_verify_append_accepts_additions_and_retire():
    old = read_gold_jsonl(FX / "gold_expected.jsonl")
    assert H.verify_append(old, old) == []
    new = [r.model_copy(update={"judgments": {**r.judgments, "P999": 1}, "provenance": {**r.provenance, "P999": "holes:B0@gold_v2"}})
           if r.qid == "c9001" else r for r in old]
    new = H.retire(new, "c9004")
    new.append(old[0].model_copy(update={"qid": "c9999"}))
    assert H.verify_append(old, new) == []


@pytest.mark.parametrize("edit, msg", [
    (lambda rs: [r for r in rs if r.qid != "c9001"], "c9001: có trong bản cũ nhưng mất"),
    (lambda rs: [r.model_copy(update={"judgments": {**r.judgments, "P002": 2}}) if r.qid == "c9001" else r for r in rs],
     "c9001/P002: nhãn đổi 1 → 2"),
    (lambda rs: [r.model_copy(update={"judgments": {k: v for k, v in r.judgments.items() if k != "P004"},
                                      "provenance": {k: v for k, v in r.provenance.items() if k != "P004"}})
                 if r.qid == "c9001" else r for r in rs], "c9001/P004: nhãn cũ bị xoá"),
    (lambda rs: [r.model_copy(update={"provenance": {**r.provenance, "P001": "khac"}}) if r.qid == "c9001" else r for r in rs],
     "c9001/P001: provenance đổi"),
    (lambda rs: [r.model_copy(update={"text": "khác"}) if r.qid == "c9001" else r for r in rs], "c9001: text bị đổi"),
    (lambda rs: [r.model_copy(update={"expected_children": {}}) if r.qid == "c9005" else r for r in rs],
     "c9005/P003: expected_children bị đổi"),
    (lambda rs: rs + [rs[0]], "c9001: qid trùng trong bản mới"),
])
def test_verify_append_rejects_edits(edit, msg):
    old = read_gold_jsonl(FX / "gold_expected.jsonl")
    assert any(msg in p for p in H.verify_append(old, edit(list(old)))), H.verify_append(old, edit(list(old)))


def test_verify_append_rejects_unretire():
    old = H.retire(read_gold_jsonl(FX / "gold_expected.jsonl"), "c9001")
    new = [r.model_copy(update={"status": "active"}) if r.qid == "c9001" else r for r in old]
    assert H.verify_append(old, new) == ["c9001: retired → active không được phép"]


# ------------------------------------------------------------------ version theo tag
def test_version_helpers():
    assert H.version_number("gold_v12") == 12
    assert H.next_version([]) == "gold_v1" and H.next_version(["gold_v1", "gold_v3"]) == "gold_v4"
    with pytest.raises(Exception, match="gold_vN"):
        H.version_number("v1")


@pytest.mark.skipif(shutil.which("git") is None, reason="cần git")
def test_gold_version_of_matches_tag_blob(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    (repo / "gold").mkdir(parents=True)
    g = repo / "gold" / "gold.jsonl"
    shutil.copyfile(FX / "gold_expected.jsonl", g)
    env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@x", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@x"}
    for cmd in (["git", "init", "-q"], ["git", "add", "."], ["git", "-c", "commit.gpgsign=false", "commit", "-q", "-m", "g"],
                ["git", "tag", "gold_v1"]):
        subprocess.run(cmd, cwd=repo, check=True, env={**__import__("os").environ, **env})
    monkeypatch.setattr(H.paths, "repo_root", lambda: repo)
    assert H.list_gold_tags() == ["gold_v1"]
    assert H.gold_version_of(g) == "gold_v1"
    assert [r.qid for r in H.gold_at("gold_v1", g)] == [r.qid for r in read_gold_jsonl(g)]
    write_gold_jsonl(H.retire(read_gold_jsonl(g), "c9001"), g)
    assert H.gold_version_of(g) is None                    # đã đổi sau tag → chưa có version
    assert H.verify_append(H.gold_at("gold_v1", g), read_gold_jsonl(g)) == []


# ------------------------------------------------------------------ CLI
def test_cli_retire_writes_status_and_changelog(gold, monkeypatch):
    monkeypatch.setattr(H, "list_gold_tags", lambda: [])
    res = run("retire", "c9002", "--reason", "pool_miss: thử", "--gold", gold)
    assert_exit(res, 0, "c9002 active → retired", "còn 6/7 câu active", "changelog gold_v1")
    assert {r.qid: r.status for r in read_gold_jsonl(gold)}["c9002"] == "retired"
    log = yaml.safe_load((gold.parent / "changelog.yaml").read_text(encoding="utf-8"))
    assert log[0]["version"] == "gold_v1" and log[0]["action"] == "retire" and log[0]["retired"] == [
        {"qid": "c9002", "reason": "pool_miss: thử"}] and log[0]["n_queries_active"] == 6 and log[0]["n_labels"] == 25
    assert_exit(run("retire", "c9002", "--reason", "x", "--gold", gold), 1, "c9002: đã retired")
    assert_exit(run("retire", "c0000", "--reason", "x", "--gold", gold), 1, "c0000: không có trong gold")
    assert_exit(run("retire", "c9001", "--reason", "x", "--gold", gold.parent / "none.jsonl"), 2, "không thấy")
    assert_exit(run("retire", "c9001", "--reason", "x", "--gold", gold, "--version", "gold_v7"), 0, "changelog gold_v7")
    assert len(yaml.safe_load((gold.parent / "changelog.yaml").read_text(encoding="utf-8"))) == 2
    assert_exit(run("check", gold, "--min-per-slice", "1"), 0)        # câu retired không vào check


def test_cli_verify_append_on_files(gold, tmp_path):
    new = tmp_path / "new.jsonl"
    write_gold_jsonl(H.retire(read_gold_jsonl(gold), "c9003"), new)
    assert_exit(run("verify-append", gold, new), 0, "verify-append xanh", "+1 retired")
    write_gold_jsonl([r.model_copy(update={"judgments": {**r.judgments, "P002": 0}}) if r.qid == "c9001" else r
                      for r in read_gold_jsonl(gold)], new)
    assert_exit(run("verify-append", gold, new), 1, "c9001/P002: nhãn đổi 1 → 0")
    assert_exit(run("verify-append", gold, tmp_path / "none.jsonl"), 2, "không đọc được")


def test_cli_import_appends_changelog(tmp_path, monkeypatch):
    monkeypatch.setattr(H, "list_gold_tags", lambda: ["gold_v1"])
    out = tmp_path / "g" / "gold.jsonl"
    res = run("import", FX / "merged_resolved.csv", "--meta", FX / "pool_meta.json", "--catalog", FX / "catalog_small.jsonl",
              "-o", out)
    assert_exit(res, 0, "7 câu")
    log = yaml.safe_load((out.parent / "changelog.yaml").read_text(encoding="utf-8"))
    assert [e["action"] for e in log] == ["import"] and log[0]["version"] == "gold_v2" and log[0]["source"] == "pool@gold_v1"
    assert_exit(run("import", FX / "merged_resolved.csv", "--meta", FX / "pool_meta.json", "--catalog",
                    FX / "catalog_small.jsonl", "-o", out), 0, "không đổi")
    assert len(yaml.safe_load((out.parent / "changelog.yaml").read_text(encoding="utf-8"))) == 1   # không đổi → không ghi
