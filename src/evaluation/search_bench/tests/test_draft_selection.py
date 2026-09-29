from __future__ import annotations

from datetime import date

import pytest

from evaluation.search_bench import draft_selection as S
from evaluation.search_bench import gold
from evaluation.search_bench.labeling import JsonlLabelStore, LabelEvent

HEADER = "case_id\tquery\tslice\tfilter_json\texpected_no_result\tsource_refs\treview_note"
OV_HEADER = "case_id\tverdict\tedited_query\treason\tnote"
QUOTA = {"dest_type": 3}
IDS = {f"c{n:04d}" for n in range(1, 13)}


def _event(cid: str, verdict: str, reason: str = "", edited: str = "", who: str = "qanh") -> LabelEvent:
    return LabelEvent(event_id=f"e-{cid}-{who}", case_id=cid, annotator=who, verdict=verdict, rejection_reason=reason,
                      edited_query=edited, notes="", updated_at="2026-09-24T09:00:00+00:00", case_slice="dest_type",
                      original_query="q")


@pytest.fixture()
def gdir(tmp_path):
    """4 ý định dest_type (mỗi ý định 3 cách nói): I0 KEEP · I1 KEEP · I2 bị loại vì cách nói (→ --fill) · I3 chưa gán."""
    d = tmp_path / "gold"
    d.mkdir()
    rows = []
    for n in range(1, 13):
        intent = (n - 1) // 3
        rows.append(f"c{n:04d}\tkhách sạn ý định {intent} cách {n}\tdest_type\t\t\tp1\thotel:nơi {intent}")
    (d / "drafts_raw.tsv").write_bytes(("\n".join([HEADER, *rows]) + "\n").encode("utf-8"))
    (d / "overrides.tsv").write_bytes((OV_HEADER + "\n").encode("utf-8"))
    store = JsonlLabelStore(tmp_path / "labels.jsonl")
    for e in (_event("c0001", "KEEP"), _event("c0004", "KEEP"), _event("c0007", "REJECT", "duplicate"),
              _event("c0008", "REJECT", "duplicate"), _event("c0009", "REJECT", "duplicate")):
        store.append(e)
    return d


def _sel(gdir):
    return S.compute(gdir, gdir.parent / "labels.jsonl", QUOTA)


def test_chosen_only_and_fill_suggestions(gdir):
    """Luật 28/09: chỉ lấy câu người soát chọn; câu --fill sẽ lấp chỉ là gợi ý. fill=True vẫn dùng được (CLI --fill)."""
    sel = _sel(gdir)
    t = {r["case_id"]: r for r in S.selected_table(sel)}
    assert list(t) == ["c0001", "c0004"]
    assert t["c0001"]["nguồn"] == S.SOURCE_HUMAN and "qanh" in t["c0001"]["chi tiết"]
    assert sel.suggested == {"c0007": "loại vì cách nói (duplicate)"}
    status = {s["slice"]: s for s in S.slice_status(sel, 3)}["dest_type"]
    assert (status["đã chọn"], status["đạt"], status["gợi ý --fill"], status["có thể thêm"]) == (2, False, 1, 2)
    cands = S.candidates(sel, "dest_type")
    assert [c.case_id for c in cands] == ["c0007", "c0010"] and "⭐ gợi ý --fill" in cands[0].status
    filled = S.compute(gdir, gdir.parent / "labels.jsonl", QUOTA, fill=True)
    assert [r["case_id"] for r in filled.rows] == ["c0001", "c0004", "c0007"] and filled.filled_ids == {
        "c0007": "loại vì cách nói (duplicate)"}
    removed, added = S.diff_with_file(sel, gdir / "drafts.txt")
    assert removed == [] and len(added) == 2                             # chưa có drafts.txt
    S.write_drafts(sel, gdir / "drafts.txt")
    assert S.diff_with_file(sel, gdir / "drafts.txt") == ([], [])
    assert b"\r" not in (gdir / "drafts.txt").read_bytes()


def test_no_cap_takes_all_chosen(gdir):
    store = JsonlLabelStore(gdir.parent / "labels.jsonl")
    store.append(_event("c0010", "KEEP"))
    sel = S.compute(gdir, gdir.parent / "labels.jsonl", {"dest_type": 2})      # mục tiêu 2 nhưng chọn 3 → lấy cả 3
    assert [r["case_id"] for r in sel.rows] == ["c0001", "c0004", "c0010"]


def test_alternatives(gdir):
    sel = _sel(gdir)
    alts = S.alternatives(sel, "c0007")
    assert [(a.kind, a.case_id) for a in alts] == [(S.KIND_PHRASING, "c0008"), (S.KIND_PHRASING, "c0009"),
                                                   (S.KIND_INTENT, "c0010")]
    assert alts[0].status.startswith("REJECT (duplicate)") and not alts[0].blocked
    assert alts[2].status == "chưa gán"
    assert all(a.case_id not in ("c0001", "c0004") for a in S.alternatives(sel, "c0001"))   # không đề xuất ý định đã chọn


def test_replace_with_other_intent(gdir):
    sel = _sel(gdir)
    rows = S.decision_rows(sel, "c0007", "replace", chosen="c0010", author="tester", note="rõ hơn", today=date(2026, 9, 28))
    assert [(r["case_id"], r["verdict"], r.get("reason", "")) for r in rows] == [("c0007", "REJECT", "other"),
                                                                                 ("c0010", "KEEP", "")]
    S.upsert_overrides(gdir / "overrides.tsv", rows, IDS)
    sel2 = _sel(gdir)
    assert [r["case_id"] for r in sel2.rows] == ["c0001", "c0004", "c0010"]
    t = {r["case_id"]: r for r in S.selected_table(sel2)}
    assert t["c0010"]["nguồn"] == S.SOURCE_OVERRIDE and "thay cho c0007" in t["c0010"]["chi tiết"]
    assert "tester" in t["c0010"]["chi tiết"] and "2026-09-28" in t["c0010"]["chi tiết"]


def test_replace_phrasing_add_and_drop(gdir):
    sel = _sel(gdir)
    S.upsert_overrides(gdir / "overrides.tsv", S.decision_rows(sel, "c0001", "replace", chosen="c0002", author="t"), IDS)
    assert [r["case_id"] for r in _sel(gdir).rows] == ["c0002", "c0004"]      # cùng ý định: REJECT duplicate + KEEP
    sel = _sel(gdir)
    S.upsert_overrides(gdir / "overrides.tsv", S.decision_rows(sel, "c0007", "add", author="t"), IDS)
    t = {r["case_id"]: r for r in S.selected_table(_sel(gdir))}
    assert list(t) == ["c0002", "c0004", "c0007"]
    assert t["c0007"]["nguồn"] == S.SOURCE_OVERRIDE and "thêm vào bộ" in t["c0007"]["chi tiết"]
    assert "gợi ý --fill" in t["c0007"]["chi tiết"]
    sel = _sel(gdir)
    S.upsert_overrides(gdir / "overrides.tsv", S.decision_rows(sel, "c0007", "drop", author="t"), IDS)
    assert [r["case_id"] for r in _sel(gdir).rows] == ["c0002", "c0004"]      # loại: không tự lấp
    ov = gold.read_overrides(gdir / "overrides.tsv", {f"c{n:04d}" for n in range(1, 13)})
    assert ov["c0007"]["verdict"] == "REJECT"                              # thay dòng cũ, không ghi đè hai lần
    assert (gdir / "overrides.tsv").read_bytes().count(b"\nc0007\t") == 1


def test_replace_keeps_needs_edit_of_chosen(gdir):
    store = JsonlLabelStore(gdir.parent / "labels.jsonl")
    store.append(_event("c0010", "NEEDS_EDIT", edited="khách sạn ý định 3 đã sửa"))
    sel = _sel(gdir)
    rows = S.decision_rows(sel, "c0007", "replace", chosen="c0010", author="t")
    assert rows[1]["verdict"] == "NEEDS_EDIT" and rows[1]["edited_query"] == "khách sạn ý định 3 đã sửa"
    S.upsert_overrides(gdir / "overrides.tsv", rows, IDS)
    assert any(r["query"] == "khách sạn ý định 3 đã sửa" for r in _sel(gdir).rows)


def test_upsert_rejects_invalid_and_keeps_file(gdir):
    before = (gdir / "overrides.tsv").read_bytes()
    with pytest.raises(gold.GoldError):
        S.upsert_overrides(gdir / "overrides.tsv", [{"case_id": "c9999", "verdict": "KEEP", "note": "x"}], IDS)
    assert (gdir / "overrides.tsv").read_bytes() == before
    with pytest.raises(ValueError):
        S.decision_rows(_sel(gdir), "c0007", "replace", chosen=None)


def test_rewrite_same_intent_needs_edit(gdir):
    sel = _sel(gdir)
    assert S.check_rewrite(sel, "c0007", "") == ["nhập câu thay thế"]
    assert any("đã có" in e for e in S.check_rewrite(sel, "c0007", "khách sạn ý định 0 cách 1"))
    assert S.check_rewrite(sel, "c0007", "khách sạn ý định 2 viết lại") == []
    rows = S.decision_rows(sel, "c0007", "rewrite", edited="khách sạn ý định 2 viết lại", author="t")
    assert rows == [{"case_id": "c0007", "verdict": "NEEDS_EDIT", "edited_query": "khách sạn ý định 2 viết lại",
                     "note": rows[0]["note"]}] and "cùng ý định" in rows[0]["note"]
    S.upsert_overrides(gdir / "overrides.tsv", rows, IDS)
    sel2 = _sel(gdir)
    t = {r["case_id"]: r for r in S.selected_table(sel2)}
    assert t["c0007"]["query"] == "khách sạn ý định 2 viết lại" and t["c0007"]["nguồn"] == S.SOURCE_OVERRIDE


def test_replace_with_new_written_intent(gdir, cfg):
    """Viết ý định mới: append_intent (KEEP) + REJECT câu cũ → câu mới vào bộ thay chỗ câu cũ."""
    from evaluation.search_bench import draft_authoring as D
    sel = _sel(gdir)
    state = D.load_state(gdir, QUOTA)
    new = D.NewIntent(slice="dest_type", phrasings=["resort ở nơi mới"], review_note="resort:nơi mới", source_refs=["p1"])
    ids = D.append_intent(state, new, author="t", keep=True)
    assert ids == ["c0013"]
    S.upsert_overrides(gdir / "overrides.tsv", S.decision_rows(sel, "c0007", "replace_new", chosen=ids[0], author="t"),
                       IDS | set(ids))
    assert [r["case_id"] for r in _sel(gdir).rows] == ["c0001", "c0004", "c0013"]
    with pytest.raises(ValueError):
        S.decision_rows(sel, "c0007", "rewrite", edited=" ")
