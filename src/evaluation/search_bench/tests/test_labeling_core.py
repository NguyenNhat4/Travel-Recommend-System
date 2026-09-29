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
