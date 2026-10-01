"""`sb gold kappa | merge | import | check | split` trên fixture `gold_small/` (đáp án ở expected.json) và các ca âm.

Mã thoát của nhóm lệnh gold: 0 đạt · 1 dữ liệu vi phạm luật · 2 lỗi đầu vào. Ca exit 1 luôn kiểm cả thông báo và
`SystemExit`, để một exception chưa bắt (CliRunner cũng trả exit 1) không bị tính là "đúng luật".
File tạm ghi bằng bytes hoặc bằng writer của gold_schema — `Path.write_text` trên Windows sinh CRLF.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from evaluation.search_bench.__main__ import app
from evaluation.search_bench.gold_schema import (read_gold_jsonl, read_labels_csv, read_merged_csv, write_gold_jsonl,
                                                 write_labels_csv, write_merged_csv, write_pool_csv)

FX = Path(__file__).parent / "fixtures" / "gold_small"
EXPECTED = json.loads((FX / "expected.json").read_text(encoding="utf-8"))
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
def fx(tmp_path):
    """Bản sao byte-nguyên của fixture để sửa trong từng ca âm."""
    d = tmp_path / "fx"
    shutil.copytree(FX, d)
    return d


def _edit_labels(path: Path, fn):
    rows = read_labels_csv(path)
    write_labels_csv([r for r in (fn(r) for r in rows) if r is not None], path)


# ------------------------------------------------------------------ kappa
def test_kappa_matches_expected():
    res = run("kappa", FX / "labels_A.csv", FX / "labels_B.csv", "--meta", FX / "pool_meta.json")
    assert_exit(res, 0, f"{EXPECTED['kappa']['linear']:.6f}", f"{EXPECTED['kappa']['unweighted']:.6f}",
                f"{EXPECTED['kappa']['quadratic']:.6f}", f"{EXPECTED['kappa']['n_pairs']} cặp chung",
                "lệch 2 bậc: c9007/P003 A=2 B=0")
    for i, row in enumerate(EXPECTED["kappa"]["confusion_A_rows_B_cols"]):
        assert f"A={i}: " + "  ".join(f"{v:>4}" for v in row) in res.output


def test_kappa_below_min():
    res = run("kappa", FX / "labels_A.csv", FX / "labels_B.csv", "--meta", FX / "pool_meta.json", "--min", "0.8")
    assert_exit(res, 1, "< 0.8")


def test_kappa_low_after_flipping_b(fx):
    flip = {0: 2, 2: 0, 1: 1}
    _edit_labels(fx / "labels_B.csv", lambda r: r.model_copy(update={"label": flip[r.label], "children_ok": []})
                 if r.qid in EXPECTED["overlap_qids"] else r)
    res = run("kappa", fx / "labels_A.csv", fx / "labels_B.csv", "--meta", fx / "pool_meta.json")
    assert_exit(res, 1, "κ linear")


def test_kappa_missing_overlap_label(fx):
    _edit_labels(fx / "labels_B.csv", lambda r: None if r.key == ("c9006", "P010") else r)
    res = run("kappa", fx / "labels_A.csv", fx / "labels_B.csv", "--meta", fx / "pool_meta.json")
    assert_exit(res, 1, "c9006/P010 thiếu nhãn của B")


# ------------------------------------------------------------------ merge
def test_merge_matches_expected_bytes(tmp_path):
    out = tmp_path / "labels" / "merged.csv"
    res = run("merge", FX / "labels_A.csv", FX / "labels_B.csv", "-o", out, "--meta", FX / "pool_meta.json")
    assert_exit(res, 0, "needs_discussion 1", "c9007/P003")
    assert out.read_bytes() == (FX / "merged_expected.csv").read_bytes()


@pytest.mark.parametrize("edit, msg", [
    (lambda r: None if r.key == ("c9001", "P002") else r, "c9001/P002 chưa gán"),
    (lambda r: r.model_copy(update={"product_id": "P999"}) if r.key == ("c9001", "P004") else r, "c9001/P999 không có trong pool_A"),
    (lambda r: r.model_copy(update={"children_ok": ["R9999"]}) if r.key == ("c9005", "P003") else r, "R9999"),
    (lambda r: r.model_copy(update={"children_ok": []}) if r.key == ("c9005", "P003") else r, "phải tick"),
])
def test_merge_rule_violations(fx, tmp_path, edit, msg):
    _edit_labels(fx / "labels_A.csv", edit)
    out = tmp_path / "m.csv"
    res = run("merge", fx / "labels_A.csv", fx / "labels_B.csv", "-o", out, "--meta", fx / "pool_meta.json")
    assert_exit(res, 1, msg)
    assert not out.exists()


def test_merge_input_errors(fx, tmp_path):
    out = tmp_path / "m.csv"
    meta = fx / "pool_meta.json"
    res = run("merge", fx / "labels_B.csv", fx / "labels_A.csv", "-o", out, "--meta", meta)
    assert_exit(res, 2, "đảo thứ tự A/B")
    _edit_labels(fx / "labels_A.csv", lambda r: r.model_copy(update={"pool_sha": "0" * 64}) if r.qid == "c9001" else r)
    res = run("merge", fx / "labels_A.csv", fx / "labels_B.csv", "-o", out, "--meta", meta)
    assert_exit(res, 2, "gắn với pool khác")
    res = run("kappa", fx / "none.csv", fx / "labels_B.csv", "--meta", meta)
    assert_exit(res, 2, "không thấy")


def test_tampered_pool_blocks_every_command(fx, tmp_path):
    b = bytearray((fx / "pool_A.csv").read_bytes())
    i = b.index("Nha Trang".encode())
    b[i] = ord("n")
    (fx / "pool_A.csv").write_bytes(bytes(b))
    meta = fx / "pool_meta.json"
    for args in (("kappa", fx / "labels_A.csv", fx / "labels_B.csv"),
                 ("merge", fx / "labels_A.csv", fx / "labels_B.csv", "-o", tmp_path / "m.csv"),
                 ("import", fx / "merged_resolved.csv", "--catalog", fx / "catalog_small.jsonl", "-o", tmp_path / "g.jsonl")):
        assert_exit(run(*args, "--meta", meta), 2, "sha")


# ------------------------------------------------------------------ import
def test_import_refuses_needs_discussion(tmp_path):
    out = tmp_path / "gold.jsonl"
    res = run("import", FX / "merged_expected.csv", "--meta", FX / "pool_meta.json",
              "--catalog", FX / "catalog_small.jsonl", "-o", out)
    assert_exit(res, 1, "c9007/P003: còn needs_discussion")
    assert not out.exists()


def test_import_resolved_matches_expected_bytes(tmp_path):
    out = tmp_path / "gold.jsonl"
    args = ("import", FX / "merged_resolved.csv", "--meta", FX / "pool_meta.json", "--catalog", FX / "catalog_small.jsonl",
            "-o", out)
    assert_exit(run(*args), 0, "7 câu")
    assert out.read_bytes() == (FX / "gold_expected.jsonl").read_bytes()
    assert_exit(run(*args), 0, "không đổi")                              # chạy lại y hệt: không lỗi


def test_import_refuses_overwriting_different_gold(tmp_path):
    out = tmp_path / "gold.jsonl"
    out.write_bytes(b'{"qid":"old"}\n')
    args = ("import", FX / "merged_resolved.csv", "--meta", FX / "pool_meta.json", "--catalog", FX / "catalog_small.jsonl",
            "-o", out)
    assert_exit(run(*args), 2, "chỉ được thêm")
    assert out.read_bytes() == b'{"qid":"old"}\n'
    assert_exit(run(*args, "--overwrite"), 0)
    assert out.read_bytes() == (FX / "gold_expected.jsonl").read_bytes()


def _merged_variant(fx: Path, edit) -> Path:
    rows = [r for r in (edit(r) for r in read_merged_csv(fx / "merged_resolved.csv")) if r is not None]
    p = fx / "merged_edit.csv"
    write_merged_csv(rows, p)
    return p


@pytest.mark.parametrize("edit, catalog_drop, msg", [
    (lambda r: None if r.key == ("c9004", "P008") else r, None, "c9004/P008: thiếu trong merged.csv"),
    (lambda r: r.model_copy(update={"product_id": "P010"}) if r.key == ("c9004", "P008") else r, None,
     "c9004/P010: không có trong pool"),
    (lambda r: r, "P007", "c9004/P007: không có trong catalog"),
    (lambda r: r.model_copy(update={"children_ok": ["R0011"]}) if r.key == ("c9005", "P003") else r, None,
     "hạng phòng R0011 không phải con của P003"),
])
def test_import_rule_violations(fx, tmp_path, edit, catalog_drop, msg):
    merged = _merged_variant(fx, edit)
    cat = fx / "catalog_small.jsonl"
    if catalog_drop:
        lines = [ln for ln in cat.read_bytes().splitlines(keepends=True) if f'"{catalog_drop}"'.encode() not in ln]
        cat.write_bytes(b"".join(lines))
    out = tmp_path / "gold.jsonl"
    res = run("import", merged, "--meta", fx / "pool_meta.json", "--catalog", cat, "-o", out)
    assert_exit(res, 1, msg)
    assert not out.exists()


# ------------------------------------------------------------------ check
def test_check_expected():
    assert_exit(run("check", FX / "gold_expected.jsonl", "--min-per-slice", "1"), 0, "git tag gold_v1")
    assert_exit(run("check", FX / "gold_expected.jsonl", "--min-per-slice", "10"), 1, "1 câu < 10")  # expected.json
    assert_exit(run("check", FX / "gold_expected.jsonl"), 1, "1 câu < 3")          # mặc định config: 3 (28/09)


@pytest.mark.parametrize("edit, msg", [
    (lambda r: r.model_copy(update={"judgments": {p: 0 for p in r.judgments}, "expected_children": {}})
     if r.qid == "c9001" else r, "c9001 [dest_type]: không có nhãn 2"),
    (lambda r: r.model_copy(update={"judgments": {**r.judgments, "P001": 2}}) if r.qid == "c9002" else r,
     "c9002: out_of_catalog nhưng có nhãn 2"),
    (lambda r: r.model_copy(update={"judgments": {}, "provenance": {}}) if r.qid == "c9002" else r,
     "c9002: không có nhãn"),
    (lambda r: r.model_copy(update={"expected_no_result": False}) if r.qid == "c9002" else r,
     "c9002: out_of_catalog thiếu expected_no_result"),
    (lambda r: r.model_copy(update={"expected_children": {}}) if r.qid == "c9005" else r,
     "c9005/P003: nhãn 2 ở parent_child thiếu expected_children"),
    (lambda r: r.model_copy(update={"slice": "khong_co"}) if r.qid == "c9004" else r, "slice lạ"),
    (lambda r: r.model_copy(update={"qid": "c9001"}) if r.qid == "c9004" else r, "qid trùng"),
])
def test_check_rule_violations(tmp_path, edit, msg):
    p = tmp_path / "gold.jsonl"
    recs = [edit(r) for r in read_gold_jsonl(FX / "gold_expected.jsonl")]
    write_gold_jsonl(recs, p)
    assert_exit(run("check", p, "--min-per-slice", "1"), 1, msg)


def test_check_skips_retired(tmp_path):
    p = tmp_path / "gold.jsonl"
    recs = [r.model_copy(update={"status": "retired", "judgments": {k: 0 for k in r.judgments}, "expected_children": {}})
            if r.qid == "c9001" else r for r in read_gold_jsonl(FX / "gold_expected.jsonl")]
    write_gold_jsonl(recs, p)
    assert_exit(run("check", p, "--min-per-slice", "1"), 0)


# ------------------------------------------------------------------ split (CLI) trên pool dựng tay
def test_split_cli_writes_contract_and_checks_pool_sha(tmp_path):
    from evaluation.search_bench import gold
    from evaluation.search_bench.tests.test_gold import _build, _synthetic_rows
    rows = _synthetic_rows({"dest_type": 6, "parent_child": 4})
    pool = tmp_path / "pool.csv"
    write_pool_csv(rows, pool)
    gold.write_pool_build(_build(pool), gold.pool_build_path(pool))
    out = tmp_path / "out"
    out.mkdir()
    res = run("split", "--pool", pool, "--overlap", 3, "--out-dir", out)
    assert_exit(res, 0, "chung 3")
    ps = gold.load_pool_set(out / "pool_meta.json")
    assert ps.meta.snapshot == "2026-09-23" and len(ps.meta.overlap_qids) == 3
    pool.write_bytes(pool.read_bytes() + b"\n")
    assert_exit(run("split", "--pool", pool, "--overlap", 3, "--out-dir", out), 2, "đã đổi sau khi")


def test_split_cli_hides_shared_qids_by_default(tmp_path):
    """Người chạy `split` có thể là người gán: mặc định chỉ in số câu chung, không in qid; `--show-shared` mới in."""
    from evaluation.search_bench import gold
    from evaluation.search_bench.tests.test_gold import _build, _synthetic_rows
    rows = _synthetic_rows({"dest_type": 6, "parent_child": 4, "named_entity": 5})
    pool = tmp_path / "pool.csv"
    write_pool_csv(rows, pool)
    gold.write_pool_build(_build(pool), gold.pool_build_path(pool))
    out = tmp_path / "out"
    out.mkdir()
    res = run("split", "--pool", pool, "--overlap", 4, "--out-dir", out)
    assert_exit(res, 0, "chung 4 câu")
    shared = gold.load_pool_set(out / "pool_meta.json").meta.overlap_qids
    assert not any(q in res.output for q in shared) and "--show-shared" in res.output
    assert "B ở slice" in res.output and "lệch số cặp" in res.output
    res = run("split", "--pool", pool, "--overlap", 4, "--out-dir", out, "--show-shared")
    assert_exit(res, 0, "qid câu chung")
    assert all(q in res.output for q in shared)
    one = _synthetic_rows({"named_entity": 8})
    write_pool_csv(one, pool)
    gold.write_pool_build(_build(pool), gold.pool_build_path(pool))
    assert_exit(run("split", "--pool", pool, "--overlap", 2, "--out-dir", out), 0, "không lệch nhau được nửa vòng")


def test_share_dry_run_writes_launcher_outside_git_and_codes(tmp_path, monkeypatch):
    """`sb gold share`: launcher ngoài repo git (Streamlit không gửi được thông tin git), mã truy cập tạo một lần, đủ mạnh;
    thư mục launcher nằm trong repo git thì từ chối."""
    from evaluation.search_bench import paths
    g = tmp_path / "gold"
    g.mkdir()
    (g / "pool_meta.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(paths, "GOLD_DIR", g)
    codes, ldir = tmp_path / "share" / "codes.env", tmp_path / "launcher"
    res = run("share", "--dry-run", "--codes", codes, "--launcher-dir", ldir)
    assert_exit(res, 0, "cloudflared tunnel --url http://127.0.0.1:8502")
    kv = dict(ln.split("=", 1) for ln in codes.read_text(encoding="utf-8").split())
    assert set(kv) == {"LABELING_CODE_A", "LABELING_CODE_B"} and kv["LABELING_CODE_A"] != kv["LABELING_CODE_B"]
    assert all(len(v) >= 20 for v in kv.values()) and not any(v in res.output for v in kv.values())   # không in mã
    assert (ldir / "app.py").exists() and "--server.address 127.0.0.1" in res.output
    assert_exit(run("share", "--dry-run", "--codes", codes), 0, "vota-label-share")                  # dùng lại mã cũ
    assert dict(ln.split("=", 1) for ln in codes.read_text(encoding="utf-8").split()) == kv
    assert_exit(run("share", "--dry-run", "--codes", codes, "--launcher-dir", paths.PKG_DIR / "x"), 2, "repo git")
    codes.write_text("LABELING_CODE_A=ngan\nLABELING_CODE_B=ngan\n", encoding="utf-8")
    assert_exit(run("share", "--dry-run", "--codes", codes, "--launcher-dir", ldir), 2, "≥ 12 ký tự")


def test_machine_import_cli_refuses_while_app_listens_and_writes_when_stopped(tmp_path):
    import json
    import socket
    import shutil
    from evaluation.search_bench import labeling_core as L
    g = tmp_path / "gold"
    g.mkdir()
    for f in ("pool_A.csv", "pool_B.csv", "pool_meta.json"):
        shutil.copyfile(FX / f, g / f)
    s = L.open_session(g / "pool_meta.json", "A")
    free = next(r for q in s.qids for r in s.by_qid[q] if not r.is_overlap and r.slice != "parent_child")
    src = tmp_path / "m.json"
    src.write_text(json.dumps([{"labeler": "A", "qid": free.qid, "product_id": free.product_id, "label": 1,
                                "children_ok": [], "note": "một phần"}], ensure_ascii=False), encoding="utf-8")
    with socket.socket() as srv:                                   # giả app đang chạy
        srv.bind(("127.0.0.1", 0))
        srv.listen(1)
        port = srv.getsockname()[1]
        assert_exit(run("machine-import", src, "--model", "t", "--meta", g / "pool_meta.json", "--port", port), 2,
                    "dừng app dùng chung")
    assert not (g / "labels").exists()
    res = run("machine-import", src, "--model", "t", "--meta", g / "pool_meta.json", "--port", port)
    assert_exit(res, 0, "ghi 1 nhãn máy")
    assert L.load_labels(s)[free.key].label == 1 and L.load_provenance(s)[free.key]["source"] == "machine"
