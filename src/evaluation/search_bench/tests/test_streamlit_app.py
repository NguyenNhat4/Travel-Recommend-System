"""Smoke test app Streamlit (3 chế độ) bằng AppTest — trên bản sao gold/ trong tmp và catalog sample."""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

from evaluation.search_bench import gold, paths  # noqa: E402

APP = Path(__file__).resolve().parents[1] / "streamlit_app.py"


@pytest.fixture()
def env(tmp_path, monkeypatch, cfg, home):
    from evaluation.search_bench import catalog
    catalog.build_catalog(cfg, "sample")
    g = tmp_path / "gold"
    g.mkdir()
    for f in ("drafts_raw.tsv", "overrides.tsv", "drafts.txt"):
        shutil.copyfile(paths.GOLD_DIR / f, g / f)
    monkeypatch.setenv("SBENCH_GOLD_DIR", str(g))
    monkeypatch.setenv("SBENCH_DATASET", "sample")
    monkeypatch.setenv("LABEL_STORE_PATH", str(tmp_path / "labels.jsonl"))
    monkeypatch.delenv("LABELING_APP_PASSWORD", raising=False)
    return g


def _run(at: AppTest) -> AppTest:
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def test_three_modes_render(env):
    at = _run(AppTest.from_file(str(APP), default_timeout=90))
    assert at.title[0].value == "Search query labeling"
    at.sidebar.radio(key="mode").set_value("Tra cứu catalog")
    _run(at)
    assert at.title[0].value == "Tra cứu catalog" and len(at.dataframe) >= 2
    at.sidebar.radio(key="mode").set_value("Bổ sung câu hỏi")
    _run(at)
    assert at.title[0].value == "Bổ sung câu hỏi theo ý định"
    assert len(at.expander) >= 13                                      # mỗi slice một box


def test_add_intent_through_form(env):
    at = _run(AppTest.from_file(str(APP), default_timeout=90))
    at.sidebar.radio(key="mode").set_value("Bổ sung câu hỏi")
    _run(at)
    at.sidebar.text_input(key="author_name").set_value("tester")
    at.text_input(key="p0-out_of_catalog").set_value("resort ở Côn Sơn")
    at.text_input(key="place-out_of_catalog").set_value("Côn Sơn")
    save = next(b for b in at.button if b.label == "Lưu ý định" and "out_of_catalog" in str(b.id))
    save.click()
    _run(at)
    rows = {r["case_id"]: r for r in gold.read_draft_cases(env / "drafts_raw.tsv")}
    assert rows["c0673"]["query"] == "resort ở Côn Sơn" and rows["c0673"]["review_note"] == "absent destination:Côn Sơn"
    assert any("Đã thêm c0673" in s.value for s in at.success)
    assert at.text_input(key="p0-out_of_catalog").value == ""             # form được xoá sau khi lưu


def test_selection_mode_replace_and_write(env):
    at = _run(AppTest.from_file(str(APP), default_timeout=120))
    at.sidebar.radio(key="mode").set_value("Bộ câu đã chọn")
    _run(at)
    assert at.title[0].value.startswith("Bộ câu đã chọn")
    at.sidebar.text_input(key="author_sel").set_value("tester")
    _run(at)
    cid = at.selectbox(key="sel_case").value
    alt = at.selectbox(key=f"alt-{cid}")
    target = next(o for o in alt.options if o.startswith(("cách nói khác", "ý định khác")))
    chosen = target.split(": ", 1)[1].split(" · ", 1)[0]
    alt.set_value(target)
    _run(at)
    next(b for b in at.button if b.label == "Áp dụng").click()
    _run(at)
    assert any("Đã ghi vào gold/overrides.tsv" in s.value for s in at.success), [s.value for s in at.success]
    ov = (env / "overrides.tsv").read_text(encoding="utf-8")
    assert f"\n{cid}\tREJECT\t" in ov and f"\n{chosen}\t" in ov and "tester" in ov
    assert at.selectbox(key="sel_case").value == chosen                   # chuyển sang câu thay thế
    next(b for b in at.button if b.label == "Ghi drafts.txt").click()
    _run(at)
    assert any("gold/drafts.txt khớp" in s.value for s in at.success)
    assert b"\r" not in (env / "drafts.txt").read_bytes()


def _open_rewrite(at: AppTest, slice_: str) -> str:
    at.sidebar.radio(key="mode").set_value("Bộ câu đã chọn")
    _run(at)
    at.sidebar.text_input(key="author_sel").set_value("tester")
    at.selectbox(key="sel_slice").set_value(slice_)
    _run(at)
    cid = at.selectbox(key="sel_case").value
    alt = at.selectbox(key=f"alt-{cid}")
    alt.set_value(next(o for o in alt.options if o.startswith("✎ Viết câu thay thế")))
    _run(at)
    return cid


def test_rewrite_same_intent_through_app(env):
    at = _run(AppTest.from_file(str(APP), default_timeout=120))
    cid = _open_rewrite(at, "named_entity")          # slice có câu KEEP trong overrides.tsv (không có kho nhãn)
    at.text_input(key=f"rw-q-{cid}").set_value("khách sạn thử nghiệm viết lại")
    next(b for b in at.button if b.label == "Áp dụng câu thay thế").click()
    _run(at)
    ov = (env / "overrides.tsv").read_text(encoding="utf-8")
    assert f"\n{cid}\tNEEDS_EDIT\tkhách sạn thử nghiệm viết lại\t" in ov


def test_rewrite_new_intent_with_refs_picker(env):
    from evaluation.search_bench.catalog_lookup import load_catalog
    ref = load_catalog("sample").items.index[0]
    at = _run(AppTest.from_file(str(APP), default_timeout=120))
    cid = _open_rewrite(at, "named_entity")          # slice có câu KEEP trong overrides.tsv (không có kho nhãn)
    at.radio(key=f"rw-mode-{cid}").set_value(next(o for o in at.radio(key=f"rw-mode-{cid}").options
                                                 if o.startswith("Ý định mới")))
    _run(at)
    assert any("source_refs" in e.label for e in at.expander)            # có giải thích source_refs
    at.text_input(key=f"rw-q-{cid}").set_value("resort thử nghiệm ý định mới")
    at.text_input(key=f"rw-note-{cid}").set_value("resort:thử nghiệm")
    at.text_area(key=f"rw-flt-{cid}").set_value("")
    at.selectbox(key=f"rw-dest-{cid}").set_value(None)                  # bỏ lọc điểm đến → mọi sản phẩm sample
    at.multiselect(key=f"rw-var-{cid}").set_value([])
    _run(at)
    at.multiselect(key=f"rw-refs-{cid}").set_value([ref])                # giá trị phải nằm trong danh sách lựa chọn
    _run(at)
    assert at.session_state[f"rw-refs-{cid}"] == [ref]
    next(b for b in at.button if b.label == "Áp dụng câu thay thế").click()
    _run(at)
    raw = (env / "drafts_raw.tsv").read_text(encoding="utf-8")
    assert "\nc0673\tresort thử nghiệm ý định mới\tnamed_entity\t" in raw and ref in raw
    ov = (env / "overrides.tsv").read_text(encoding="utf-8")
    assert f"\n{cid}\tREJECT\t" in ov and "\nc0673\tKEEP\t" in ov


def _open_label_mode(at: AppTest, who: str = "A") -> AppTest:
    at.sidebar.radio(key="mode").set_value("Gán nhãn 0/1/2")
    _run(at)
    at.sidebar.radio(key="lbl_who").set_value(who)
    next(b for b in at.sidebar.button if b.label.startswith("Dùng bản thử fixture")).click()
    return _run(at)


def test_label_mode_resume_progress_and_children(env):
    from evaluation.search_bench import labeling_core as L
    from evaluation.search_bench import paths
    at = _open_label_mode(_run(AppTest.from_file(str(APP), default_timeout=120)))
    assert at.title[0].value == "Gán nhãn relevance 0/1/2"
    metrics = {m.label: m.value for m in at.metric}
    assert metrics["Câu đã xong"] == "0/5" and metrics["Cặp đã gán"] == "0/19"
    assert at.selectbox(key="lbl_qid").value == "c9001"
    meta = paths.sbench_home() / "label_try" / "pool_meta.json"
    s = L.open_session(meta, "A")
    for qid in ("c9001", "c9002"):
        for r in s.by_qid[qid]:
            assert L.save_label(s, qid, r.product_id, 0) == []
    assert L.save_label(s, "c9005", "P003", 2, ["R0033"]) == []
    at2 = _open_label_mode(_run(AppTest.from_file(str(APP), default_timeout=120)))
    assert at2.selectbox(key="lbl_qid").value == "c9005"                 # mở lại → câu chưa xong đầu tiên
    assert {m.label: m.value for m in at2.metric}["Câu đã xong"] == "2/5"
    ms = at2.multiselect(key="lbl-ch-c9005-P003-0")
    assert ms.value == ["R0033"]
    ms.set_value(["R0033", "R0032"])
    _run(at2)
    got = L.load_labels(s)
    assert got[("c9005", "P003")].children_ok == ["R0032", "R0033"]    # lưu ngay, theo thứ tự pool
    assert not (paths.GOLD_DIR / "labels").exists()                     # không ghi vào gold/ thật


def test_label_mode_blocks_tampered_pool(env):
    from evaluation.search_bench import paths
    at = _open_label_mode(_run(AppTest.from_file(str(APP), default_timeout=120)), "B")
    assert not at.error
    pool = paths.sbench_home() / "label_try" / "pool_B.csv"
    pool.write_bytes(pool.read_bytes() + b"\n")
    next(b for b in at.sidebar.button if b.label == "Tải lại file").click()
    _run(at)
    assert any("sha" in e.value for e in at.error)


def test_selection_buttons_need_author_and_show_feedback(env):
    """Chưa có tên người sửa: nút bị khoá kèm nhắc ngay cạnh nút (trước đây lỗi chỉ hiện ở đầu trang → tưởng không có
    gì xảy ra). Có tên: ghi overrides.tsv, thông báo cạnh nút + toast."""
    at = _run(AppTest.from_file(str(APP), default_timeout=120))
    at.sidebar.radio(key="mode").set_value("Bộ câu đã chọn")
    _run(at)
    cid = at.selectbox(key="sel_case").value
    alt = at.selectbox(key=f"alt-{cid}")
    alt.set_value(next(o for o in alt.options if o.startswith("✖")))
    _run(at)
    assert next(b for b in at.button if b.label == "Áp dụng").disabled
    assert any("tên người sửa" in w.value for w in at.warning)
    at.sidebar.text_input(key="author_sel").set_value("tester")
    _run(at)
    next(b for b in at.button if b.label == "Áp dụng").click()
    _run(at)
    assert f"\n{cid}\tREJECT\t" in (env / "overrides.tsv").read_text(encoding="utf-8")
    assert any("Đã ghi vào gold/overrides.tsv" in t.value for t in at.toast)
    assert sum("Đã ghi vào gold/overrides.tsv" in s.value for s in at.success) == 2       # đầu trang + cạnh nút


def test_selection_copies_local_only_edit_to_overrides(env, tmp_path):
    """Câu NEEDS_EDIT chỉ có trong kho nhãn local → cảnh báo + nút “Chép vào overrides.tsv” (cần tên người sửa); bấm thì
    ghi dòng NEEDS_EDIT đúng câu đó và hết cảnh báo."""
    from evaluation.search_bench.labeling import JsonlLabelStore, LabelEvent
    raw = gold.read_draft_cases(env / "drafts_raw.tsv")
    over = gold.read_overrides(env / "overrides.tsv", {r["case_id"] for r in raw})
    case = next(r for r in raw if r["slice"] == "dest_type" and r["case_id"] not in over
                and all(gold.intent_key(o, "dest_type") != gold.intent_key(r["case_id"], "dest_type") for o in over))
    edited = f"{case['query']} bản sửa thử"
    JsonlLabelStore(tmp_path / "labels.jsonl").append(LabelEvent(
        event_id="e-test", case_id=case["case_id"], annotator="qanh", verdict="NEEDS_EDIT", rejection_reason="",
        edited_query=edited, notes="", updated_at="2026-09-29T01:00:00+00:00", case_slice="dest_type",
        original_query=case["query"]))
    at = _run(AppTest.from_file(str(APP), default_timeout=120))
    at.sidebar.radio(key="mode").set_value("Bộ câu đã chọn")
    _run(at)
    assert any("chỉ có trong kho nhãn local" in w.value and case["case_id"] in w.value for w in at.warning)
    btn = next(b for b in at.button if b.label == "Chép vào overrides.tsv")
    assert btn.disabled
    at.sidebar.text_input(key="author_sel").set_value("tester")
    _run(at)
    next(b for b in at.button if b.label == "Chép vào overrides.tsv").click()
    _run(at)
    ov = (env / "overrides.tsv").read_text(encoding="utf-8")
    assert f"\n{case['case_id']}\tNEEDS_EDIT\t{edited}\t" in ov and "tester" in ov and "qanh" in ov
    assert not any("chỉ có trong kho nhãn local" in w.value for w in at.warning)
    assert any("Đã chép 1 câu" in s.value for s in at.success)
