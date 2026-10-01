"""Test bắt buộc của app gán nhãn 0/1/2 (docs/spec/bench/prompts/may2-label-app.md) — trên fixture gold_small, trong tmp."""
from __future__ import annotations

import builtins
import shutil
from datetime import datetime
from pathlib import Path

import pytest

from evaluation.search_bench import labeling_core as L
from evaluation.search_bench.gold_schema import read_labels_csv

FX = Path(__file__).parent / "fixtures" / "gold_small"


@pytest.fixture()
def pools(tmp_path):
    """Bản sao byte-nguyên pool_A/B + meta (không có file nhãn — app tạo ra)."""
    d = tmp_path / "gold"
    d.mkdir()
    for f in ("pool_A.csv", "pool_B.csv", "pool_meta.json"):
        shutil.copyfile(FX / f, d / f)
    return d


def _label_all(s: L.LabelSession, answer: Path) -> None:
    """Gán toàn bộ pool qua core theo thứ tự app (câu, rồi ứng viên theo file), dùng đúng nhãn trong file đáp án."""
    want = {r.key: r for r in read_labels_csv(answer)}
    for qid in s.qids:
        for r in s.by_qid[qid]:
            a = want[r.key]
            assert L.save_label(s, qid, r.product_id, a.label, a.children_ok, a.note) == []


def _without_time(path: Path) -> list[dict]:
    return [r.model_dump(exclude={"labeled_at"}) for r in read_labels_csv(path)]


@pytest.mark.parametrize("who", ["A", "B"])
def test_labeling_whole_pool_reproduces_fixture(pools, who):
    s = L.open_session(pools / "pool_meta.json", who)
    assert s.labels_path == pools / "labels" / f"labels_{who}.csv"
    _label_all(s, FX / f"labels_{who}.csv")
    assert _without_time(s.labels_path) == _without_time(FX / f"labels_{who}.csv")
    assert all(r.labeled_at.tzinfo is not None for r in read_labels_csv(s.labels_path))
    p = L.progress(s, L.load_labels(s))
    assert p["done_q"] == p["total_q"] == 5 and p["done_pairs"] == p["total_pairs"]
    assert L.resume_qid(s, L.load_labels(s)) is None


def test_resume_after_two_questions(pools):
    s = L.open_session(pools / "pool_meta.json", "A")
    assert L.resume_qid(s, {}) == s.qids[0] == "c9001"
    want = {r.key: r for r in read_labels_csv(FX / "labels_A.csv")}
    for qid in s.qids[:2]:
        for r in s.by_qid[qid]:
            assert L.save_label(s, qid, r.product_id, want[r.key].label) == []
    labels = L.load_labels(s)
    assert L.resume_qid(s, labels) == s.qids[2] == "c9005"
    assert L.next_unfinished(s, labels, "c9005") == "c9006"
    p = L.progress(s, labels)
    assert (p["done_q"], p["total_q"]) == (2, 5) and p["dist"] == {0: 5, 1: 1, 2: 1}


def test_tampered_pool_is_blocked(pools):
    b = bytearray((pools / "pool_A.csv").read_bytes())
    b[b.index(b"Nha Trang")] = ord("n")
    (pools / "pool_A.csv").write_bytes(bytes(b))
    with pytest.raises(L.SessionError, match="sha"):
        L.open_session(pools / "pool_meta.json", "A")
    L.open_session(pools / "pool_meta.json", "B")                       # pool B không bị đụng → vẫn mở được


def test_parent_child_2_needs_room(pools):
    s = L.open_session(pools / "pool_meta.json", "A")
    errs = L.save_label(s, "c9005", "P003", 2)
    assert errs and "hạng phòng" in errs[0]
    assert not s.labels_path.exists()                                    # không lưu
    assert L.save_label(s, "c9005", "P003", 2, ["R0033", "R0032"]) == []
    assert read_labels_csv(s.labels_path)[0].children_ok == ["R0032", "R0033"]   # theo thứ tự trong pool
    assert "không thuộc" in L.save_label(s, "c9005", "P003", 2, ["R0011"])[0]
    assert L.save_label(s, "c9005", "P003", 1, ["R0033"]) == []          # nhãn khác 2: bỏ hạng phòng
    assert read_labels_csv(s.labels_path)[0].children_ok == []
    assert L.save_label(s, "c9001", "P999", 1) and L.save_label(s, "c9001", "P001", 3)


def test_core_never_opens_other_labelers_file(pools, monkeypatch):
    (pools / "labels").mkdir()
    sentinel = pools / "labels" / "labels_B.csv"
    sentinel.write_bytes(b"not a csv - must stay untouched\n")
    opened: list[str] = []
    real_open = builtins.open

    def spy(file, *a, **kw):
        opened.append(str(file))
        return real_open(file, *a, **kw)

    monkeypatch.setattr(builtins, "open", spy)
    s = L.open_session(pools / "pool_meta.json", "A")
    _label_all(s, FX / "labels_A.csv")
    L.progress(s, L.load_labels(s))
    L.clear_label(s, "c9001", "P001")
    assert not any(Path(p).name == "labels_B.csv" for p in opened), opened
    assert sentinel.read_bytes() == b"not a csv - must stay untouched\n"
    with pytest.raises(L.SessionError, match="người gán khác"):
        L.open_session(pools / "pool_meta.json", "A", labels_path=sentinel)


def test_clear_label_and_candidate_rows(pools):
    s = L.open_session(pools / "pool_meta.json", "A")
    assert L.save_label(s, "c9005", "P003", 2, ["R0033"], note="villa hồ bơi riêng",
                        now=datetime(2026, 9, 28, 9, 0)) == []
    rows = L.candidate_rows(s, "c9005", L.load_labels(s))
    assert [set(r) for r in rows][0] >= {"nhãn", "ghi chú", "name", "taxonomy", "amenities", "snippet", "hạng phòng"}
    assert not any(k in r for r in rows for k in ("product_id", "from", "rank_dense", "rank_lex", "is_overlap"))
    p003 = next(r for r in rows if r["name"] == "Resort Rừng Dừa Phú Quốc")
    assert p003["nhãn"] == "2" and p003["hạng phòng đúng (đã tick)"] == "Villa Hồ Bơi Riêng"
    assert "hạng phòng" not in L.candidate_rows(s, "c9001", {})[0]      # children chỉ hiện ở parent_child
    h = L.header(s, "c9002")
    assert h["expected_no_result"] and h["slice"] == "out_of_catalog"
    assert L.clear_label(s, "c9005", "P003") == [] and L.load_labels(s) == {}



def test_concurrent_saves_do_not_lose_labels(pools):
    """App dùng chung: nhiều phiên / tab lưu cùng một file nhãn trong nhiều thread — khoá theo file giữ đủ mọi nhãn."""
    import threading

    s = L.open_session(pools / "pool_meta.json", "A")
    pairs = [(q, r.product_id) for q in s.qids for r in s.by_qid[q]]
    errors: list = []
    start = threading.Barrier(4)

    def work(chunk):
        start.wait()
        for q, p in chunk:
            errors.extend(L.save_label(s, q, p, 0))

    threads = [threading.Thread(target=work, args=(pairs[i::4],)) for i in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
    assert set(L.load_labels(s)) == set(pairs)


def test_note_too_long_is_rejected(pools):
    s = L.open_session(pools / "pool_meta.json", "A")
    qid, pid = s.qids[0], s.by_qid[s.qids[0]][0].product_id
    assert any("ghi chú dài quá" in e for e in L.save_label(s, qid, pid, 0, note="x" * (L.NOTE_MAX + 1)))
    assert L.save_label(s, qid, pid, 0, note="x" * L.NOTE_MAX) == []


def test_concurrent_reads_and_writes_do_not_fail(pools):
    """Hai tab cùng người: đọc (dựng lại bảng) trong lúc tab kia lưu — đọc cũng qua khoá + thử lại, không PermissionError."""
    import threading

    s = L.open_session(pools / "pool_meta.json", "A")
    pairs = [(q, r.product_id) for q in s.qids for r in s.by_qid[q]]
    failures: list = []
    done = threading.Event()

    def writer(chunk):
        for q, p in chunk:
            failures.extend(L.save_label(s, q, p, 0))

    def reader():
        while not done.is_set():
            try:
                L.load_labels(s)
            except Exception as e:                      # noqa: BLE001 — mọi lỗi đọc đều là lỗi của test này
                failures.append(repr(e))

    readers = [threading.Thread(target=reader) for _ in range(2)]
    writers = [threading.Thread(target=writer, args=(pairs[i::2],)) for i in range(2)]
    for t in readers + writers:
        t.start()
    for t in writers:
        t.join()
    done.set()
    for t in readers:
        t.join()
    assert failures == []
    assert set(L.load_labels(s)) == set(pairs)


def test_apply_changes_saves_valid_rows_and_reports_the_rest(pools):
    """Nút Lưu: một lượt nhiều dòng — dòng hợp lệ được ghi, dòng lỗi (nhãn 2 parent_child chưa tick phòng, ghi chú mà
    chưa có nhãn, id lạ) báo lỗi, không làm hỏng dòng khác; nhãn trống xoá nhãn cũ."""
    s = L.open_session(pools / "pool_meta.json", "A")
    q1 = s.qids[0]
    p1, p2 = [r.product_id for r in s.by_qid[q1]][:2]
    errs, saved = L.apply_changes(s, q1, {p1: {"label": "1", "note": "gần đúng"}, p2: {"label": None, "note": "x"},
                                          "khong-co": {"label": "0"}})
    assert saved == [p1] and len(errs) == 2 and any("chọn nhãn trước" in e for e in errs)
    got = L.load_labels(s)
    assert got[(q1, p1)].label == 1 and got[(q1, p1)].note == "gần đúng" and (q1, p2) not in got
    errs, saved = L.apply_changes(s, q1, {p1: {"label": "", "note": ""}})
    assert errs == [] and saved == [p1] and (q1, p1) not in L.load_labels(s)
    # parent_child: nhãn 2 cần hạng phòng — thiếu thì báo, có thì lưu (thứ tự theo pool)
    pc = next(q for q in s.qids if s.by_qid[q][0].slice == "parent_child")
    row = next(r for r in s.by_qid[pc] if r.children)
    errs, saved = L.apply_changes(s, pc, {row.product_id: {"label": "2", "note": ""}})
    assert saved == [] and errs and L.MSG_NEED_CHILDREN in errs[0]
    ids = [ch.id for ch in row.children]
    errs, saved = L.apply_changes(s, pc, {row.product_id: {"label": "2", "note": "", "children": ids[::-1]}})
    assert errs == [] and L.load_labels(s)[row.key].children_ok == ids


def test_machine_import_only_fills_free_private_pairs_and_tracks_review(pools):
    """Nhãn máy: chỉ cặp còn trống, không câu chung (κ), cặp người đã gán giữ nguyên; provenance ghi nguồn và duyệt."""
    s = L.open_session(pools / "pool_meta.json", "A")
    private = [r for q in s.qids for r in s.by_qid[q] if not r.is_overlap and r.slice != "parent_child"]
    shared = next(r for q in s.qids for r in s.by_qid[q] if r.is_overlap)
    human, free = private[0], private[1]
    assert L.save_label(s, human.qid, human.product_id, 1, note="người") == []
    rows = [{"labeler": "A", "qid": human.qid, "product_id": human.product_id, "label": 0, "note": "máy"},
            {"labeler": "A", "qid": free.qid, "product_id": free.product_id, "label": 2, "note": "đúng loại, đúng nơi"},
            {"labeler": "A", "qid": shared.qid, "product_id": shared.product_id, "label": 0},
            {"labeler": "B", "qid": free.qid, "product_id": free.product_id, "label": 0}]
    res = L.import_machine_labels(s, rows, model="test-model")
    assert res["written"] == [free.key] and res["skipped_labeled"] == [human.key]
    assert len(res["rejected"]) == 1 and "câu chung" in res["rejected"][0]
    labels = L.load_labels(s)
    assert labels[human.key].label == 1 and labels[free.key].label == 2 and shared.key not in labels
    prov = L.load_provenance(s)
    assert prov[free.key]["source"] == L.SOURCE_MACHINE and prov[free.key]["model"] == "test-model"
    assert prov[free.key]["machine_note"] == "đúng loại, đúng nơi" and human.key not in prov
    assert L.source_of(prov[free.key]) == "máy · chưa duyệt" and L.source_of(None) == "người"
    st = L.review_stats(s, labels, prov)
    assert st["machine"] == st["machine_unreviewed"] == 1 and st["human"] == 1
    L.record_review(s, [free.key], [], [], "QAnh")
    prov = L.load_provenance(s)
    assert prov[free.key]["review"] == L.REVIEW_ACCEPTED and L.source_of(prov[free.key]) == "máy · duyệt: QAnh"
    L.record_review(s, [], [free.key], [], "QAnh")
    assert L.source_of(L.load_provenance(s)[free.key]) == "máy → sửa: QAnh"
    L.record_review(s, [], [], [free.key], "QAnh")
    assert L.load_provenance(s)[free.key]["review"] == ""
    assert L.provenance_path(s).name == "provenance_A.csv" and b"\r\n" not in L.provenance_path(s).read_bytes()


def test_plan_save_splits_label_changes_and_review_actions(pools):
    s = L.open_session(pools / "pool_meta.json", "A")
    q = s.qids[0]
    p1, p2, p3 = [r.product_id for r in s.by_qid[q]][:3]
    assert L.save_label(s, q, p1, 1) == [] and L.save_label(s, q, p2, 2) == []
    L.update_provenance(s, {(q, p2): {"source": L.SOURCE_MACHINE, "machine_label": "2"}})
    labels, prov = L.load_labels(s), L.load_provenance(s)
    # chỉ tick p1 (nhãn người, không đổi nhãn) → không có thay đổi nhãn, cần tên người duyệt
    plan = L.plan_save(q, {p1: {"label": "1", "note": "", "tick": True}}, labels, prov)
    assert plan["label_changes"] == {} and plan["tick_on"] == [p1] and plan["needs_reviewer"]
    # đổi nhãn người p3 (chưa có nhãn) → không cần tên người duyệt
    plan = L.plan_save(q, {p3: {"label": "0", "note": ""}}, labels, prov)
    assert list(plan["label_changes"]) == [p3] and not plan["needs_reviewer"]
    # sửa nhãn máy p2 → là việc duyệt (sửa), cần tên
    plan = L.plan_save(q, {p2: {"label": "1", "note": ""}}, labels, prov)
    assert list(plan["label_changes"]) == [p2] and plan["machine"] == {p2} and plan["needs_reviewer"]
    # bỏ tick
    plan = L.plan_save(q, {p2: {"label": "2", "note": "", "tick": False}}, labels, prov)
    assert plan["tick_off"] == [p2] and plan["label_changes"] == {}


def test_accept_all_machine_only_touches_unreviewed_machine_labels(pools):
    s = L.open_session(pools / "pool_meta.json", "A")
    q = next(q for q in s.qids if not s.by_qid[q][0].is_overlap and s.by_qid[q][0].slice != "parent_child")
    rows = s.by_qid[q]
    human, *machine = rows
    assert L.save_label(s, q, human.product_id, 1) == []
    L.import_machine_labels(s, [{"labeler": "A", "qid": q, "product_id": r.product_id, "label": 0} for r in machine],
                            model="t")
    L.record_review(s, [], [machine[0].key], [], "X")                  # một nhãn máy đã sửa từ trước
    with pytest.raises(ValueError):
        L.accept_all_machine(s, q, " ")
    got = L.accept_all_machine(s, q, "QAnh")
    assert got == [r.key for r in machine[1:]]
    prov = L.load_provenance(s)
    assert prov[machine[0].key]["review"] == L.REVIEW_EDITED and prov[machine[0].key]["reviewed_by"] == "X"
    assert all(prov[k]["review"] == L.REVIEW_ACCEPTED and prov[k]["reviewed_by"] == "QAnh" for k in got)
    assert human.key not in prov and L.accept_all_machine(s, q, "QAnh") == []
