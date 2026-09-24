"""Part 5 (ngày 1): nhãn của app soát draft → gold/drafts.txt."""
from __future__ import annotations

import pytest

from evaluation.search_bench.gold import (GoldError, intent_key, parse_drafts, read_draft_cases, resolve_decisions,
                                          select_drafts, write_drafts)
from evaluation.search_bench.labeling import LabelEvent

QUOTA = {"dest_type": 2, "out_of_catalog": 2}
HEADER = "case_id\tquery\tslice\tfilter_json\texpected_no_result\tsource_refs\treview_note"


def _case(n: int, slice_: str, query: str, filter_json: str = "", eno: str = "") -> str:
    return f"c{n:04d}\t{query}\t{slice_}\t{filter_json}\t{eno}\tp1\tnote"


def _event(case_id: str, annotator: str, verdict: str, *, at: str, edited: str = "", reason: str = "",
           slice_: str = "dest_type") -> LabelEvent:
    return LabelEvent(event_id=f"e-{case_id}-{annotator}", case_id=case_id, annotator=annotator, verdict=verdict,
                      rejection_reason=reason, edited_query=edited, notes="", updated_at=at,
                      case_slice=slice_, original_query="q")


@pytest.fixture()
def raw_tsv(tmp_path):
    rows = [_case(i, "dest_type", f"khách sạn ở nơi {i}") for i in range(1, 7)]
    rows += [_case(i, "out_of_catalog", f"resort ở nơi vắng {i}", eno="true") for i in range(7, 10)]
    p = tmp_path / "drafts_raw.tsv"
    p.write_text("\n".join([HEADER, *rows]) + "\n", encoding="utf-8")
    return p


def test_intent_key_gom_ba_cach_noi_tru_out_of_catalog():
    assert intent_key("c0001", "dest_type") == intent_key("c0003", "dest_type")
    assert intent_key("c0004", "dest_type") != intent_key("c0003", "dest_type")
    # out_of_catalog: 3 dòng liền nhau là 3 taxonomy khác nhau → 3 ý định
    assert intent_key("c0574", "out_of_catalog") != intent_key("c0575", "out_of_catalog")


def test_resolve_decisions_lay_nhan_moi_nhat_va_bao_bat_dong():
    events = [
        _event("c0001", "khoi", "KEEP", at="2026-09-24T01:00:00+00:00"),
        _event("c0001", "khoi", "REJECT", at="2026-09-24T02:00:00+00:00", reason="duplicate"),
        _event("c0002", "khoi", "KEEP", at="2026-09-24T01:00:00+00:00"),
        _event("c0002", "qanh", "REJECT", at="2026-09-24T03:00:00+00:00", reason="unnatural"),
    ]
    decisions, conflicts = resolve_decisions(events)
    assert decisions["c0001"]["verdict"] == "REJECT"       # cùng annotator: bản mới nhất thắng
    assert conflicts == ["c0002"]                          # khác annotator, khác verdict: không chọn
    assert "c0002" not in decisions


def test_select_giu_mot_cach_noi_moi_y_dinh_va_ap_needs_edit(raw_tsv):
    cases = read_draft_cases(raw_tsv)
    events = [
        _event("c0001", "khoi", "KEEP", at="2026-09-24T01:00:00+00:00"),
        _event("c0002", "khoi", "KEEP", at="2026-09-24T01:00:00+00:00"),        # cùng ý định với c0001
        _event("c0004", "khoi", "NEEDS_EDIT", at="2026-09-24T01:00:00+00:00", edited="khách sạn Huế"),
        _event("c0006", "khoi", "REJECT", at="2026-09-24T01:00:00+00:00", reason="unnatural"),
    ]
    decisions, _ = resolve_decisions(events)
    rows, report = select_drafts(cases, decisions, QUOTA)
    assert [r["case_id"] for r in rows] == ["c0001", "c0004"]
    assert rows[1]["query"] == "khách sạn Huế"                                   # NEEDS_EDIT thay câu
    assert report["dropped_duplicate"] == ["c0002"]
    assert report["reject_reasons"] == {"unnatural": 1}
    assert report["per_slice"]["dest_type"]["ungraded_rows"] == 2               # c0003, c0005
    assert report["per_slice"]["out_of_catalog"]["shortfall"] == 2


def test_select_cat_theo_quota_va_bao_thua(raw_tsv):
    cases = read_draft_cases(raw_tsv)
    events = [_event(f"c{n:04d}", "khoi", "KEEP", at="2026-09-24T01:00:00+00:00") for n in (7, 8, 9)]
    decisions, _ = resolve_decisions(events)
    rows, report = select_drafts(cases, decisions, QUOTA)
    assert [r["case_id"] for r in rows] == ["c0007", "c0008"]                    # quota 2, lấy case_id nhỏ trước
    assert report["over_quota"]["out_of_catalog"] == ["c0009"]


def test_select_tu_choi_query_trung_trong_cung_slice(raw_tsv):
    cases = read_draft_cases(raw_tsv)
    events = [
        _event("c0001", "khoi", "KEEP", at="2026-09-24T01:00:00+00:00"),
        _event("c0004", "khoi", "NEEDS_EDIT", at="2026-09-24T01:00:00+00:00", edited="khách sạn ở nơi 1"),
    ]
    decisions, _ = resolve_decisions(events)
    with pytest.raises(GoldError, match="trùng"):
        select_drafts(cases, decisions, QUOTA)


def test_drafts_txt_doc_lai_duoc_bang_parse_drafts(tmp_path, raw_tsv):
    cases = read_draft_cases(raw_tsv)
    flt = '{"and":[{"eq":["destination","Huế"]},{"eq":["variant","hotel_property"]}]}'
    cases[0]["filter_json"] = flt
    events = [_event("c0001", "khoi", "KEEP", at="2026-09-24T01:00:00+00:00"),
              _event("c0007", "khoi", "KEEP", at="2026-09-24T01:00:00+00:00", slice_="out_of_catalog")]
    decisions, _ = resolve_decisions(events)
    rows, _ = select_drafts(cases, decisions, QUOTA)
    out = tmp_path / "drafts.txt"
    write_drafts(out, rows)
    drafts = parse_drafts(out, list(QUOTA), {})
    assert [d.qid for d in drafts] == ["q001", "q002"]
    assert drafts[0].filter is not None and drafts[0].filter_raw == flt
    assert drafts[1].expected_no_result is True and drafts[1].filter is None
