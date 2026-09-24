"""Part 5 (ngày 1): nhãn của app soát draft → gold/drafts.txt."""
from __future__ import annotations

import pytest

from evaluation.search_bench.gold import (GoldError, intent_key, parse_drafts, read_draft_cases, resolve_decisions,
                                          select_drafts, write_drafts)
from evaluation.search_bench.labeling import LabelEvent

QUOTA = {"dest_type": 2, "out_of_catalog": 2}
HEADER = "case_id\tquery\tslice\tfilter_json\texpected_no_result\tsource_refs\treview_note"


def _case(n: int, slice_: str, query: str, filter_json: str = "", eno: str = "") -> str:
    # review_note khác nhau từng case: ở dest_type/out_of_catalog nó là khoá ý định, trùng note = trùng ý định
    return f"c{n:04d}\t{query}\t{slice_}\t{filter_json}\t{eno}\tp1\tnote-{n}"


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


def test_fill_lay_lai_y_dinh_chua_gan_va_y_dinh_loai_vi_cach_noi(raw_tsv):
    cases = read_draft_cases(raw_tsv)
    events = [
        _event("c0001", "khoi", "KEEP", at="2026-09-24T01:00:00+00:00"),
        # cả 3 dòng của ý định c0004-c0006 bị loại vì cách nói → --fill lấy lại dòng gốc
        *[_event(f"c{n:04d}", "khoi", "REJECT", at="2026-09-24T01:00:00+00:00", reason="duplicate") for n in (4, 5, 6)],
    ]
    decisions, _ = resolve_decisions(events)
    rows, report = select_drafts(cases, decisions, QUOTA, fill=True)
    got = [r["case_id"] for r in rows]
    assert got == ["c0001", "c0004", "c0007", "c0008"]        # c0004 lấy lại, c0007/c0008 là ý định chưa gán
    kinds = {f["case_id"]: f["kind"] for f in report["filled"]}
    assert kinds["c0004"].startswith("loại vì cách nói")
    assert kinds["c0007"] == "chưa gán"


def test_fill_khong_dung_y_dinh_bi_loai_vi_loi_that(raw_tsv):
    cases = read_draft_cases(raw_tsv)
    events = [_event(f"c{n:04d}", "khoi", "REJECT", at="2026-09-24T01:00:00+00:00", reason="fabricated_entity")
              for n in (1, 2, 3)]
    decisions, _ = resolve_decisions(events)
    rows, report = select_drafts(cases, decisions, QUOTA, fill=True)
    assert "c0001" not in [r["case_id"] for r in rows]
    assert any(s["case_id"] == "c0001" and "lỗi thật" in s["why"] for s in report["skipped_fill"])


def test_fill_ton_trong_fill_guard(raw_tsv):
    cases = read_draft_cases(raw_tsv)
    rows, report = select_drafts(cases, {}, QUOTA, fill=True,
                                 fill_guard=lambda r: "nguồn đã chết" if r["case_id"] == "c0001" else None)
    assert [r["case_id"] for r in rows] == ["c0004", "c0007", "c0008"]
    assert any(s["case_id"] == "c0001" and s["why"] == "nguồn đã chết" for s in report["skipped_fill"])


def test_fill_chi_khu_trung_theo_review_note_o_slice_co_khoa(tmp_path):
    """dest_type: note là khoá (loại × địa danh) → chặn trùng. Slice khác: note chỉ là khuôn → không chặn."""
    rows_txt = [
        "c0001\tkhách sạn ở Huế\tdest_type\t\t\tp1\thotel:Huế",
        "c0002\ttìm khách sạn ở Huế\tdest_type\t\t\tp1\thotel:Huế",
        "c0003\tkhách sạn ở Huế, còn chỗ nào?\tdest_type\t\t\tp1\thotel:Huế",
        "c0004\tkhách sạn tại Huế\tdest_type\t\t\tp2\thotel:Huế",          # cùng khoá với c0001
        "c0005\ttìm khách sạn tại Huế\tdest_type\t\t\tp2\thotel:Huế",
        "c0006\tkhách sạn tại Huế nhé\tdest_type\t\t\tp2\thotel:Huế",
        "c0007\tkhách sạn 3 sao Đà Nẵng dưới 1 triệu\tmulti_constraint\t\t\tp3\tstar=3;price<=1000000",
        "c0008\ttìm khách sạn 3 sao Đà Nẵng dưới 1 triệu\tmulti_constraint\t\t\tp3\tstar=3;price<=1000000",
        "c0009\tkhách sạn 3 sao Đà Nẵng dưới 1 triệu?\tmulti_constraint\t\t\tp3\tstar=3;price<=1000000",
        "c0010\tkhách sạn 3 sao Hà Nội dưới 1 triệu\tmulti_constraint\t\t\tp4\tstar=3;price<=1000000",  # khác điểm đến
        "c0011\ttìm khách sạn 3 sao Hà Nội dưới 1 triệu\tmulti_constraint\t\t\tp4\tstar=3;price<=1000000",
        "c0012\tkhách sạn 3 sao Hà Nội dưới 1 triệu?\tmulti_constraint\t\t\tp4\tstar=3;price<=1000000",
    ]
    p = tmp_path / "raw.tsv"
    p.write_text("\n".join([HEADER, *rows_txt]) + "\n", encoding="utf-8")
    cases = read_draft_cases(p)
    rows, report = select_drafts(cases, {}, {"dest_type": 2, "multi_constraint": 2}, fill=True)
    got = [r["case_id"] for r in rows]
    assert "c0004" not in got                                  # dest_type: cùng khoá hotel:Huế → chặn
    assert got == ["c0001", "c0007", "c0010"]                  # multi_constraint: khác điểm đến → vẫn lấy
    assert any(s["case_id"] == "c0004" and "trùng khoá" in s["why"] for s in report["skipped_fill"])


def _overrides(tmp_path, *lines: str):
    p = tmp_path / "overrides.tsv"
    p.write_text("\n".join(["case_id\tverdict\tedited_query\treason\tnote", *lines]) + "\n", encoding="utf-8")
    return p


def test_override_keep_mo_lai_y_dinh_da_loai(tmp_path, raw_tsv):
    from evaluation.search_bench.gold import apply_overrides, read_overrides

    cases = read_draft_cases(raw_tsv)
    events = [_event(f"c{n:04d}", "qanh", "REJECT", at="2026-09-24T01:00:00+00:00", reason="fabricated_entity")
              for n in (1, 2, 3)]
    decisions, conflicts = resolve_decisions(events)
    ov = read_overrides(_overrides(tmp_path, "c0001\tKEEP\t\t\tthực thể có thật"), {r["case_id"] for r in cases})
    decisions, conflicts = apply_overrides(decisions, conflicts, ov)
    rows, _ = select_drafts(cases, decisions, QUOTA)
    assert [r["case_id"] for r in rows] == ["c0001"]
    assert rows[0]["annotator"] == "override"


def test_override_thang_ca_bat_dong(tmp_path, raw_tsv):
    from evaluation.search_bench.gold import apply_overrides, read_overrides

    cases = read_draft_cases(raw_tsv)
    events = [_event("c0001", "khoi", "KEEP", at="2026-09-24T01:00:00+00:00"),
              _event("c0001", "qanh", "REJECT", at="2026-09-24T02:00:00+00:00", reason="unnatural")]
    decisions, conflicts = resolve_decisions(events)
    assert conflicts == ["c0001"]
    ov = read_overrides(_overrides(tmp_path, "c0001\tREJECT\t\tbad_grounding\tđiểm đến đã hết sản phẩm"),
                        {r["case_id"] for r in cases})
    decisions, conflicts = apply_overrides(decisions, conflicts, ov)
    assert conflicts == [] and decisions["c0001"]["verdict"] == "REJECT"


@pytest.mark.parametrize("line, msg", [
    ("c9999\tKEEP\t\t\tghi chú", "không có trong drafts_raw"),
    ("c0001\tMAYBE\t\t\tghi chú", "verdict phải thuộc"),
    ("c0001\tNEEDS_EDIT\t\t\tghi chú", "edited_query"),
    ("c0001\tKEEP\t\t\t", "cần ghi note"),
])
def test_override_tu_choi_dong_sai(tmp_path, raw_tsv, line, msg):
    from evaluation.search_bench.gold import read_overrides

    with pytest.raises(GoldError, match=msg):
        read_overrides(_overrides(tmp_path, line), {r["case_id"] for r in read_draft_cases(raw_tsv)})
