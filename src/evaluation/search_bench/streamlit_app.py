"""App Streamlit cho gold của search bench — bốn chế độ:

- Soát câu hỏi: review query ứng viên của Role A (KEEP / REJECT / NEEDS_EDIT), chưa phải relevance label 0/1/2.
- Bộ câu đã chọn: drafts.txt = mọi câu người soát chọn (luật 28/09, mỗi slice ≥ gold.min_per_slice), thêm câu chưa
  chọn, thay / viết lại / loại từng câu → `gold/overrides.tsv`; ghi lại drafts.txt (`draft_selection.py`).
- Bổ sung câu hỏi: mỗi slice một box — xem các ý định đã có (và trạng thái trong drafts.txt), thêm ý định mới vào
  `gold/drafts_raw.tsv` (+ KEEP trong `gold/overrides.tsv`), kiểm grounding trước khi ghi (`draft_authoring.py`).
- Gán nhãn 0/1/2: người gán A hoặc B gán relevance cho pool_X.csv → gold/labels/labels_X.csv (`labeling_core.py`,
  docs/spec/bench/prompts/may2-label-app.md).
- Tra cứu catalog: điểm đến có dữ liệu, tìm sản phẩm (dựng filter / source_refs), tiện ích theo điểm đến, kiểm tra
  địa danh ngoài catalog (`catalog_lookup.py`, đọc dữ liệu `sb catalog build`).

Chạy từ gốc repo: `streamlit run src/evaluation/search_bench/streamlit_app.py`.
"""
from __future__ import annotations

import hmac
import json
import os
import sys
from collections import Counter, defaultdict
from html import escape
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent
SRC = ROOT.parents[1]
if str(SRC) not in sys.path:                                  # để import evaluation.search_bench.* (gold, catalog)
    sys.path.insert(0, str(SRC))

from labeling import (  # noqa: E402
    REJECTION_REASONS,
    VERDICTS,
    JsonlLabelStore,
    consensus,
    latest_by_annotator,
    latest_events_csv,
    load_cases,
    new_label_event,
)

GOLD_DIR = Path(os.getenv("SBENCH_GOLD_DIR") or ROOT / "gold")
CASES_PATH = GOLD_DIR / "drafts_raw.tsv"


def _labels_path() -> Path:
    """Kho nhãn của chế độ soát: LABEL_STORE_PATH, mặc định `<repo>/bench_out/search/labels/labels.jsonl` (qua
    `paths.sbench_home()`, không phụ thuộc thư mục chạy `streamlit run`)."""
    env = os.getenv("LABEL_STORE_PATH")
    if env:
        return Path(env)
    from evaluation.search_bench import paths
    return paths.sbench_home() / "labels" / "labels.jsonl"


LOCAL_LABELS_PATH = _labels_path()
DATASET = os.getenv("SBENCH_DATASET", "jsonl")
MODE_REVIEW, MODE_SELECTED, MODE_AUTHOR, MODE_LABEL, MODE_CATALOG = (
    "Soát câu hỏi", "Bộ câu đã chọn", "Bổ sung câu hỏi", "Gán nhãn 0/1/2", "Tra cứu catalog")
MODES = (MODE_REVIEW, MODE_SELECTED, MODE_AUTHOR, MODE_LABEL, MODE_CATALOG)
KEEP_AS_IS = "(giữ nguyên)"
OOC = "out_of_catalog"
MULTI = "multi_constraint"

st.set_page_config(page_title="V-OTA Search Labeling", page_icon="🔎", layout="wide")
st.html(
    """
    <style>
    .block-container {max-width: 1280px; padding-top: 2rem;}
    .query-card {border: 1px solid #d8dee8; border-radius: 12px; padding: 1.25rem 1.4rem; background: #ffffff;}
    .query-card h2 {font-size: 1.55rem; line-height: 1.35; margin: 0.35rem 0 0.25rem;}
    .case-meta {color: #5f6b7a; font-size: 0.9rem;}
    </style>
    """
)


def _stamp(p: Path) -> tuple[int, int]:
    s = p.stat()
    return s.st_mtime_ns, s.st_size


@st.cache_data
def _cases(path: str, stamp: tuple[int, int]):
    return load_cases(Path(path))


def cases():
    """Khoá cache theo mtime + size: thêm dòng vào drafts_raw.tsv thì thấy ngay, không phải khởi động lại app."""
    return _cases(str(CASES_PATH), _stamp(CASES_PATH))


@st.cache_resource
def store():
    return JsonlLabelStore(LOCAL_LABELS_PATH)


@st.cache_resource
def _config():
    from evaluation.search_bench.config import load_config
    return load_config()


@st.cache_resource(show_spinner="Đang nạp catalog…")
def _catalog(dataset: str, stamp: tuple[int, int]):
    from evaluation.search_bench.catalog_lookup import load_catalog
    return load_catalog(dataset)


def catalog():
    """(Catalog, None) hoặc (None, lý do) — không có dữ liệu bench thì hai chế độ mới vẫn chạy, chỉ bỏ phần kiểm grounding."""
    from evaluation.search_bench import paths
    p = paths.data_dir(DATASET, create=False) / paths.ITEMS
    if not p.exists():
        return None, f"chưa có {p} — chạy `python -m evaluation.search_bench catalog build` từ `src/` trước"
    try:
        return _catalog(DATASET, _stamp(p)), None
    except Exception as exc:                                  # dữ liệu hỏng / thiếu vocab: báo, không làm sập app
        return None, str(exc)


def require_password() -> None:
    try:
        expected = str(st.secrets.get("labeling", {}).get("app_password", ""))
    except Exception:
        expected = os.getenv("LABELING_APP_PASSWORD", "")
    if not expected:
        return
    supplied = st.sidebar.text_input("Mật khẩu nhóm", type="password", key="app_password")
    if not hmac.compare_digest(supplied, expected):
        st.info("Nhập mật khẩu nhóm ở sidebar để bắt đầu gán nhãn.")
        st.stop()


def next_case_id(visible_ids: list[str], current_id: str, direction: int = 1) -> str:
    if not visible_ids:
        return current_id
    try:
        position = visible_ids.index(current_id)
    except ValueError:
        position = -1 if direction > 0 else 0
    return visible_ids[(position + direction) % len(visible_ids)]


# ------------------------------------------------------------------ chế độ 1: soát câu hỏi (KEEP / REJECT / NEEDS_EDIT)
def render_review() -> None:
    all_cases = cases()
    case_by_id = {item.case_id: item for item in all_cases}

    st.title("Search query labeling")
    st.caption(f"Review {len(all_cases)} query ứng viên của Role A. Đây chưa phải relevance label 0/1/2 và chưa phải gold_v1.")

    with st.sidebar:
        st.header("Phiên gán nhãn")
        annotator = st.text_input("Tên annotator", placeholder="Ví dụ: khoi", key="annotator").strip()
        selected_slice = st.selectbox("Slice", ["Tất cả", *sorted({item.slice for item in all_cases})])
        review_filter = st.radio("Trạng thái của tôi", ["Chưa gán", "Đã gán", "Tất cả"], horizontal=False)
        search_text = st.text_input("Tìm query / case ID").strip().casefold()
        st.caption(f"Kho nhãn: `{LOCAL_LABELS_PATH}` (JSONL dùng chung, không commit)")
        st.warning("Hãy tải CSV định kỳ; dữ liệu có thể mất khi app được redeploy hoặc restart.")

    try:
        events = store().load_events()
    except Exception as exc:
        st.error(f"Không đọc được kho nhãn: {exc}")
        st.stop()

    latest_map = latest_by_annotator(events)
    my_latest = {
        case_id: event
        for (case_id, owner), event in latest_map.items()
        if annotator and owner == annotator.casefold()
    }
    team_by_case = defaultdict(list)
    for event in latest_map.values():
        team_by_case[event.case_id].append(event)

    filtered = []
    for item in all_cases:
        if selected_slice != "Tất cả" and item.slice != selected_slice:
            continue
        if search_text and search_text not in f"{item.case_id} {item.query}".casefold():
            continue
        mine = item.case_id in my_latest
        if review_filter == "Chưa gán" and mine:
            continue
        if review_filter == "Đã gán" and not mine:
            continue
        filtered.append(item)

    visible_ids = [item.case_id for item in filtered]
    if "case_id" not in st.session_state or st.session_state.case_id not in case_by_id:
        st.session_state.case_id = visible_ids[0] if visible_ids else all_cases[0].case_id
    if visible_ids and st.session_state.case_id not in visible_ids:
        st.session_state.case_id = visible_ids[0]

    metric_cols = st.columns(4)
    metric_cols[0].metric("Tổng case", len(all_cases))
    metric_cols[1].metric("Bạn đã gán", len(my_latest))
    metric_cols[2].metric("Team đã chạm", len(team_by_case))
    conflicts = sum(consensus(items) == "CONFLICT" for items in team_by_case.values())
    metric_cols[3].metric("Case bất đồng", conflicts)

    if not visible_ids:
        st.success("Không còn case phù hợp với bộ lọc hiện tại.")
        st.stop()

    nav_left, nav_select, nav_right = st.columns([1, 5, 1])
    with nav_left:
        if st.button("← Trước", width="stretch"):
            st.session_state.case_id = next_case_id(visible_ids, st.session_state.case_id, -1)
            st.rerun()
    with nav_select:
        selected = st.selectbox(
            "Case",
            visible_ids,
            index=visible_ids.index(st.session_state.case_id),
            format_func=lambda case_id: f"{case_id} · {case_by_id[case_id].query}",
            label_visibility="collapsed",
        )
        if selected != st.session_state.case_id:
            st.session_state.case_id = selected
            st.rerun()
    with nav_right:
        if st.button("Sau →", width="stretch"):
            st.session_state.case_id = next_case_id(visible_ids, st.session_state.case_id, 1)
            st.rerun()

    current = case_by_id[st.session_state.case_id]
    current_team = team_by_case.get(current.case_id, [])
    st.html(
        f'<div class="query-card"><div class="case-meta">{escape(current.case_id)} · {escape(current.slice)}</div>'
        f'<h2>{escape(current.query)}</h2><div class="case-meta">Team consensus: {escape(consensus(current_team))}</div></div>'
    )

    with st.expander("Grounding và dữ liệu kỹ thuật", expanded=False):
        st.write("**Source refs:**", current.source_refs or "—")
        st.write("**Review note:**", current.review_note or "—")
        st.write("**Expected no result:**", current.expected_no_result or "false")
        if current.filter_json:
            st.code(current.filter_json, language="json")

    previous = my_latest.get(current.case_id)
    if previous:
        st.info(f"Nhãn gần nhất của bạn: **{previous.verdict}** · {previous.updated_at}")

    default_verdict = previous.verdict if previous else "KEEP"
    default_reason = previous.rejection_reason if previous else REJECTION_REASONS[0]
    with st.form(f"label-form-{current.case_id}", clear_on_submit=False):
        verdict = st.radio("Quyết định", VERDICTS, index=VERDICTS.index(default_verdict), horizontal=True)
        reason = st.selectbox(
            "Lý do loại",
            REJECTION_REASONS,
            index=REJECTION_REASONS.index(default_reason) if default_reason in REJECTION_REASONS else 0,
            help="Chỉ được lưu khi quyết định là REJECT.",
        )
        edited_query = st.text_area(
            "Query đã sửa",
            value=previous.edited_query if previous and previous.verdict == "NEEDS_EDIT" else "",
            help="Bắt buộc khi quyết định là NEEDS_EDIT.",
            placeholder="Nhập query thay thế khi chọn NEEDS_EDIT",
        )
        notes = st.text_area("Ghi chú", value=previous.notes if previous else "", placeholder="Không bắt buộc")
        save, save_next = st.columns(2)
        submitted = save.form_submit_button("Lưu", width="stretch")
        submitted_next = save_next.form_submit_button("Lưu và case tiếp theo", type="primary", width="stretch")

    if submitted or submitted_next:
        if not annotator:
            st.error("Hãy nhập tên annotator trước khi lưu.")
        else:
            try:
                event = new_label_event(
                    current,
                    annotator=annotator,
                    verdict=verdict,
                    rejection_reason=reason if verdict == "REJECT" else "",
                    edited_query=edited_query if verdict == "NEEDS_EDIT" else "",
                    notes=notes,
                )
                store().append(event)
                st.toast(f"Đã lưu {current.case_id}: {verdict}", icon="✅")
                if submitted_next:
                    remaining = [case_id for case_id in visible_ids if case_id != current.case_id]
                    st.session_state.case_id = remaining[0] if review_filter == "Chưa gán" and remaining else next_case_id(visible_ids, current.case_id)
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
            except Exception as exc:
                st.error(f"Không lưu được nhãn: {exc}")

    with st.expander("Tiến độ team và export", expanded=False):
        verdict_counts = Counter(event.verdict for event in latest_map.values())
        st.write({key: verdict_counts.get(key, 0) for key in VERDICTS})
        latest_events = list(latest_map.values())
        st.download_button(
            "Tải CSV nhãn mới nhất",
            latest_events_csv(latest_events).encode("utf-8-sig"),
            file_name="search_draft_labels_latest.csv",
            mime="text/csv",
            width="stretch",
        )


def _author_box(key: str, label: str) -> str:
    """Ô tên người sửa ở sidebar; giữ tên qua các chế độ bằng khoá thường `author` (state của widget bị xoá khi đổi
    chế độ)."""
    with st.sidebar:
        st.header("Người sửa")
        v = st.text_input(label, key=key, value=st.session_state.get("author", ""), placeholder="ví dụ: QAnh")
    st.session_state["author"] = v.strip()
    return v.strip()


# ------------------------------------------------------------------ chế độ: bộ 200 câu đã chọn + thay thế
def _selection():
    from evaluation.search_bench import draft_selection as S
    cat, _ = catalog()
    return S.compute(GOLD_DIR, LOCAL_LABELS_PATH, dict(_config().gold.slices), cat.items if cat else None)


_TOAST_ICON = {"success": "✅", "error": "🚫", "warning": "⚠️", "info": "ℹ️"}


def _flash(kind: str, text: str, where: str) -> None:
    """Thông báo sau một thao tác: hiện ở đầu trang, ngay dưới nút vừa bấm (`where`) và dạng toast nổi — không bị
    khuất khi đang cuộn xuống dưới."""
    st.session_state["sel_msg"] = (kind, text, where)
    st.toast(text if len(text) <= 220 else text[:217] + "…", icon=_TOAST_ICON.get(kind))


def _show_flash(where: str) -> None:
    msg = st.session_state.get("_sel_msg_now")
    if msg and msg[2] == where:
        getattr(st, msg[0])(msg[1])


def _need_author_note() -> None:
    st.warning("Nhập **tên người sửa** ở sidebar để bật nút — tên được ghi vào note của overrides.tsv.", icon="✍️")


def _apply_choice(cid: str) -> None:
    """Callback: ghi quyết định của dropdown vào overrides.tsv, chuyển sang câu thay thế."""
    from evaluation.search_bench import draft_selection as S
    ss = st.session_state
    action, chosen = ss.get(f"altopts-{cid}", {}).get(ss.get(f"alt-{cid}"), (None, None))
    author = (ss.get("author_sel") or ss.get("author") or "").strip()
    if action is None:
        _flash("info", "Chưa chọn thay đổi nào.", "case")
        return
    if not author:
        _flash("error", "Chưa ghi gì: nhập tên người sửa ở sidebar trước khi áp dụng.", "case")
        return
    try:
        sel = _selection()
        rows = S.decision_rows(sel, cid, action, chosen=chosen, author=author, note=ss.get(f"altnote-{cid}", ""))
        S.upsert_overrides(GOLD_DIR / "overrides.tsv", rows, set(sel.by_id))
        removed, added = S.diff_with_file(_selection(), GOLD_DIR / "drafts.txt")
    except Exception as exc:
        _flash("error", f"Không ghi được overrides.tsv: {exc}", "case")
        return
    done = ", ".join(f"{r['case_id']} {r['verdict']}" for r in rows)
    _flash("success", f"Đã ghi vào gold/overrides.tsv: {done}. drafts.txt sẽ bỏ {len(removed)} và thêm {len(added)} "
                      "dòng — bấm “Ghi drafts.txt” ở đầu trang khi xong.", "case")
    ss[f"alt-{cid}"] = KEEP_AS_IS
    ss[f"altnote-{cid}"] = ""
    if chosen:
        ss["sel_case"] = chosen


def _add_candidates() -> None:
    """Callback: thêm các câu chưa chọn (multiselect) vào bộ — KEEP (hoặc giữ NEEDS_EDIT) trong overrides.tsv."""
    from evaluation.search_bench import draft_selection as S
    ss = st.session_state
    ids = list(ss.get("add_pick") or [])
    author = (ss.get("author_sel") or ss.get("author") or "").strip()
    if not ids:
        _flash("info", "Chưa chọn câu nào để thêm.", "add")
        return
    if not author:
        _flash("error", "Chưa ghi gì: nhập tên người sửa ở sidebar trước khi thêm.", "add")
        return
    try:
        sel = _selection()
        rows = [r for c in ids for r in S.decision_rows(sel, c, "add", author=author, note=ss.get("add_note", ""))]
        S.upsert_overrides(GOLD_DIR / "overrides.tsv", rows, set(sel.by_id))
        removed, added = S.diff_with_file(_selection(), GOLD_DIR / "drafts.txt")
    except Exception as exc:
        _flash("error", f"Không ghi được overrides.tsv: {exc}", "add")
        return
    _flash("success", f"Đã thêm {len(ids)} câu vào bộ ({', '.join(ids)}). drafts.txt sẽ bỏ {len(removed)} và thêm "
                      f"{len(added)} dòng — bấm “Ghi drafts.txt” ở đầu trang khi xong.", "add")
    ss["add_pick"] = []
    ss["add_note"] = ""
    ss["sel_case"] = ids[0]
    ss["sel_slice"] = "Tất cả"


def _copy_local_edits(case_ids: list[str]) -> None:
    """Callback: chép nguyên câu NEEDS_EDIT chỉ có trong kho nhãn local sang overrides.tsv (drafts.txt không đổi)."""
    from evaluation.search_bench import draft_selection as S
    from evaluation.search_bench import gold
    author = (st.session_state.get("author_sel") or st.session_state.get("author") or "").strip()
    if not author:
        _flash("error", "Chưa ghi gì: nhập tên người sửa ở sidebar trước.", "local")
        return
    try:
        sel = _selection()
        rows = [r for c in case_ids for r in S.decision_rows(sel, c, "copy_local", author=author)]
        S.upsert_overrides(GOLD_DIR / "overrides.tsv", rows, set(sel.by_id))
        after = _selection()
        left = gold.local_only_edits(after.rows, after.cases, after.overrides)
        removed, added = S.diff_with_file(after, GOLD_DIR / "drafts.txt")
    except Exception as exc:
        _flash("error", f"Không ghi được overrides.tsv: {exc}", "local")
        return
    _flash("success" if not left else "warning",
           f"Đã chép {len(rows)} câu vào gold/overrides.tsv ({', '.join(case_ids)}); còn {len(left)} câu chỉ có ở kho "
           f"local; drafts.txt {'khớp' if not (removed or added) else f'lệch {len(removed)}/{len(added)} dòng'}.", "local")


def _write_drafts_file() -> None:
    from evaluation.search_bench import draft_selection as S
    sel = _selection()
    S.write_drafts(sel, GOLD_DIR / "drafts.txt")
    _flash("success", f"Đã ghi gold/drafts.txt: {len(sel.rows)} dòng.", "write")


def _next_fill(ids: list[str], fill_ids: set[str]) -> None:
    ss = st.session_state
    cur = ss.get("sel_case")
    start = ids.index(cur) + 1 if cur in ids else 0
    nxt = next((c for c in ids[start:] + ids[:start] if c in fill_ids and c != cur), None)
    if nxt:
        ss["sel_case"] = nxt


def render_selection() -> None:
    from evaluation.search_bench import draft_selection as S
    from evaluation.search_bench import gold

    ss = st.session_state
    n_min = int(_config().gold.min_per_slice)
    st.title("Bộ câu đã chọn (drafts.txt)")
    st.caption(f"Luật 28/09: drafts.txt = **mọi câu người soát đã chọn** (KEEP / NEEDS_EDIT ở chế độ Soát câu hỏi hoặc "
               f"trong `gold/overrides.tsv`) — không cần đủ 200, không tự lấp; mỗi slice cần **≥ {n_min} câu**. Thêm / "
               "thay / loại ghi vào overrides.tsv (thắng nhãn của app); drafts.txt chỉ đổi khi bấm “Ghi drafts.txt”.")
    author = _author_box("author_sel", "Tên người sửa (ghi vào note của overrides.tsv)")
    if not LOCAL_LABELS_PATH.exists():
        st.warning(f"Không thấy kho nhãn `{LOCAL_LABELS_PATH}` — chỉ tính được từ overrides.tsv.")
    try:
        sel = _selection()
    except Exception as exc:
        st.error(f"Không tính được bộ câu: {exc}")
        st.stop()
    msg = ss.pop("sel_msg", None)
    ss["_sel_msg_now"] = msg
    if msg:
        getattr(st, msg[0])(msg[1])

    table = S.selected_table(sel)
    status = S.slice_status(sel, n_min)
    stat = {s["slice"]: s for s in status}
    short = [s["slice"] for s in status if not s["đạt"]]
    by_src = Counter(r["nguồn"] for r in table)
    m = st.columns(4)
    m[0].metric("Câu đã chọn", len(table))
    m[1].metric(f"Slice đạt ≥ {n_min} câu", f"{len(status) - len(short)}/{len(status)}")
    m[2].metric("Người soát / overrides", f"{by_src.get(S.SOURCE_HUMAN, 0)} / {by_src.get(S.SOURCE_OVERRIDE, 0)}")
    m[3].metric("Gợi ý --fill chưa chọn", len(sel.suggested or {}))
    st.caption(f"Kho nhãn: {sel.n_events} lượt gán · bất đồng chưa xử lý: {len(sel.conflicts)}"
               + (f" ({', '.join(sel.conflicts[:8])})" if sel.conflicts else ""))
    if short:
        st.error(f"{len(short)} slice dưới {n_min} câu: " + ", ".join(f"`{s}` ({stat[s]['đã chọn']})" for s in short)
                 + " — thêm câu ở mục “➕ Thêm câu chưa chọn” bên dưới hoặc ở chế độ Bổ sung câu hỏi.")

    removed, added = S.diff_with_file(sel, GOLD_DIR / "drafts.txt")
    if removed or added:
        st.warning(f"gold/drafts.txt chưa khớp lựa chọn hiện tại: sẽ bỏ {len(removed)} dòng, thêm {len(added)} dòng.")
        with st.expander("Xem thay đổi của drafts.txt"):
            c = st.columns(2)
            c[0].markdown("**Bỏ**")
            c[0].code("\n".join(removed) or "—", language=None)
            c[1].markdown("**Thêm**")
            c[1].code("\n".join(added) or "—", language=None)
        st.button("Ghi drafts.txt", type="primary", on_click=_write_drafts_file)
        _show_flash("write")
    else:
        st.success("gold/drafts.txt khớp lựa chọn hiện tại.", icon="✔")
    local = gold.local_only_edits(sel.rows, sel.cases, sel.overrides)
    if local:
        st.warning(f"{len(local)} câu sửa chỉ có trong kho nhãn local (không commit): `sb gold pool --qid case` và máy "
                   "khác không map được sang case_id. Bấm nút dưới để chép nguyên các câu này thành dòng NEEDS_EDIT của "
                   "overrides.tsv (drafts.txt không đổi): " + ", ".join(f"`{r['case_id']}` {r['query']}" for r in local))
        st.button("Chép vào overrides.tsv", on_click=_copy_local_edits, args=([r["case_id"] for r in local],),
                  disabled=not author)
        if not author:
            _need_author_note()
        _show_flash("local")

    with st.expander("Số câu theo slice", expanded=bool(short)):
        st.dataframe(status, hide_index=True, width="stretch",
                     column_config={"đạt": st.column_config.CheckboxColumn("đạt"),
                                    "mục tiêu": st.column_config.NumberColumn("mục tiêu (tham khảo)")})
    with st.expander("➕ Thêm câu chưa chọn vào bộ", expanded=bool(short)):
        slices = list(sel.quota)
        if ss.get("add_slice") not in slices:
            ss["add_slice"] = short[0] if short else next((s["slice"] for s in status if s["gợi ý --fill"]), slices[0])
        sl_add = st.selectbox("Slice", slices, key="add_slice",
                              format_func=lambda s: f"{s} — đã chọn {stat[s]['đã chọn']}, có thể thêm "
                                                    f"{stat[s]['có thể thêm']} (⭐ {stat[s]['gợi ý --fill']})")
        cands = {a.case_id: a.label() for a in S.candidates(sel, sl_add)}
        ss["add_pick"] = [c for c in ss.get("add_pick", []) if c in cands]
        st.multiselect("Câu để thêm — ⭐ = câu `--fill` sẽ tự lấp · ⚠ = từng bị loại (chọn lại là mở lại quyết định)",
                       list(cands), key="add_pick", format_func=lambda c: cands[c])
        st.text_input("Lý do / ghi chú", key="add_note")
        st.button("Thêm vào bộ", type="primary", on_click=_add_candidates, disabled=not ss.get("add_pick") or not author)
        if not author:
            _need_author_note()
        _show_flash("add")
        st.caption("Không có câu phù hợp: viết câu mới ở chế độ “Bổ sung câu hỏi”, hoặc dùng “✎ Viết câu thay thế” "
                   "của một câu bên dưới.")

    c = st.columns([2, 3, 3])
    pick_slice = c[0].selectbox("Slice", ["Tất cả", *sel.quota], key="sel_slice")
    src_opts = ["Tất cả", "Người soát chọn", "overrides.tsv"] + (["Chỉ câu --fill"] if by_src.get(S.SOURCE_FILL) else [])
    pick_src = c[1].radio("Nguồn", src_opts, horizontal=True, key="sel_src")
    text = c[2].text_input("Tìm câu / case_id", key="sel_q").strip().casefold()
    src_map = {"Chỉ câu --fill": S.SOURCE_FILL, "Người soát chọn": S.SOURCE_HUMAN, "overrides.tsv": S.SOURCE_OVERRIDE}
    rows = [r for r in table
            if (pick_slice == "Tất cả" or r["slice"] == pick_slice)
            and (pick_src == "Tất cả" or r["nguồn"] == src_map[pick_src])
            and (not text or text in f"{r['case_id']} {r['query']}".casefold())]
    st.dataframe(rows, hide_index=True, width="stretch", height=min(38 + 35 * max(len(rows), 1), 420),
                 column_config={"#": st.column_config.NumberColumn("#", width="small")})
    if not rows:
        st.info("Không có câu nào khớp bộ lọc.")
        return

    ids = [r["case_id"] for r in rows]
    by_id = {r["case_id"]: r for r in rows}
    fill_ids = {r["case_id"] for r in rows if r["nguồn"] == S.SOURCE_FILL}
    if ss.get("sel_case") not in ids:
        ss["sel_case"] = next(iter(sorted(fill_ids, key=ids.index)), ids[0])
    st.subheader("Xem, thay hoặc loại từng câu")
    b = st.columns([6, 1])
    b[0].selectbox("Câu đang xem", ids, key="sel_case",
                   format_func=lambda x: f"#{by_id[x]['#']} {x} · {by_id[x]['query']} [{by_id[x]['nguồn']}]")
    if fill_ids:
        b[1].button("Câu --fill kế →", on_click=_next_fill, args=(ids, fill_ids), width="stretch")
    cid = ss["sel_case"]
    row, raw = by_id[cid], sel.by_id[cid]
    st.html(
        f'<div class="query-card"><div class="case-meta">{escape(cid)} · {escape(row["slice"])} · nguồn: '
        f'{escape(row["nguồn"])} — {escape(row["chi tiết"])}</div><h2>{escape(row["query"])}</h2>'
        f'<div class="case-meta">ý định (review_note): {escape(raw.get("review_note") or "—")}</div></div>')
    if raw.get("filter_json"):
        st.code(raw["filter_json"], language="json")
    _show_refs(raw)

    alts = S.alternatives(sel, cid)
    opts: dict[str, tuple] = {KEEP_AS_IS: (None, None)}
    if row["nguồn"] == S.SOURCE_FILL:
        opts["✔ Giữ câu này — đã soát (ghi KEEP)"] = ("keep", None)
    for a in alts:
        opts[a.label()] = ("replace", a.case_id)
    opts[REWRITE_OPT] = ("rewrite", None)
    opts["✖ Loại câu này — để --fill lấp ý định khác"] = ("drop", None)
    ss[f"altopts-{cid}"] = opts
    choice = st.selectbox("Thay bằng", list(opts), key=f"alt-{cid}",
                          help="Cách nói khác của cùng ý định đứng trước, rồi ý định khác cùng slice chưa có trong bộ. "
                               "⚠ = từng bị loại vì lỗi thật hoặc trong overrides — chọn lại nghĩa là mở lại quyết định. "
                               "Không có câu phù hợp thì chọn “✎ Viết câu thay thế”.")
    st.caption(f"{sum(a.kind == S.KIND_PHRASING for a in alts)} cách nói khác · "
               f"{sum(a.kind == S.KIND_INTENT for a in alts)} ý định khác cùng slice có thể thay.")
    if choice == REWRITE_OPT:
        _rewrite_panel(cid, raw)
        return
    st.text_input("Lý do / ghi chú (ghi vào overrides.tsv)", key=f"altnote-{cid}")
    st.button("Áp dụng", type="primary", on_click=_apply_choice, args=(cid,), disabled=choice == KEEP_AS_IS or not author)
    if not author:
        _need_author_note()
    _show_flash("case")


SOURCE_REFS_HELP = ("**source_refs** là `product_id` của những sản phẩm (search unit) trong catalog **thoả câu hỏi** — "
                    "bằng chứng câu có đáp án thật. Dùng để người soát kiểm grounding, và để `--fill` bỏ câu khi mọi "
                    "sản phẩm này biến mất khỏi catalog. Không phải nhãn gold (nhãn 0/1/2 gán sau trên pool) và không "
                    "ghi vào drafts.txt. Câu out_of_catalog không có source_refs.")


def _refs_of(raw: dict) -> list[str]:
    return [r.strip() for r in (raw.get("source_refs") or "").split("|") if r.strip()]


def _show_refs(raw: dict) -> None:
    from evaluation.search_bench import catalog_lookup as C
    refs = _refs_of(raw)
    with st.expander(f"source_refs của câu này ({len(refs)}) — là gì?", expanded=bool(refs)):
        st.markdown(SOURCE_REFS_HELP)
        cat, err = catalog()
        if not refs:
            st.caption("Câu này không có source_refs.")
        elif cat is None:
            st.code(" | ".join(refs), language=None)
            st.caption(f"Không hiện được thông tin sản phẩm: {err}")
        else:
            info = C.describe(cat, refs)
            st.dataframe(info, hide_index=True, width="stretch")
            gone = [r for r in refs if r not in set(info["product_id"])]
            if gone:
                st.warning(f"Không còn trong catalog: {', '.join(gone)}")


REWRITE_OPT = "✎ Viết câu thay thế (không có câu phù hợp trong danh sách)"
RW_SAME = "Cùng ý định — chỉ sửa câu chữ (NEEDS_EDIT; giữ mã case, filter, source_refs)"
RW_NEW = "Ý định mới — tạo case mới (chọn source_refs, filter; câu hiện tại bị REJECT)"


def _rewrite_panel(cid: str, raw: dict) -> None:
    ss = st.session_state
    sl = raw["slice"]
    with st.container(border=True):
        mode = st.radio("Kiểu thay thế", [RW_SAME, RW_NEW], key=f"rw-mode-{cid}")
        st.text_input("Câu thay thế", key=f"rw-q-{cid}", placeholder=raw["query"])
        if mode == RW_NEW:
            if sl == OOC:
                st.text_input("Điểm đến không có trong catalog", key=f"rw-place-{cid}",
                              help="review_note tự ghi là “absent destination:<điểm đến>”; app kiểm catalog không nhắc tới nó.")
            else:
                ss.setdefault(f"rw-note-{cid}", raw.get("review_note") or "")
                ss.setdefault(f"rw-flt-{cid}", raw.get("filter_json") or "")
                st.text_input("review_note — ý định (đang điền sẵn ý định cũ, sửa cho khớp câu mới)", key=f"rw-note-{cid}")
                st.text_area("filter_json (bắt buộc với multi_constraint)", key=f"rw-flt-{cid}", height=68)
                _refs_picker(cid, raw)
        else:
            st.caption("Câu mới giữ nguyên mã case, filter và source_refs của câu hiện tại (bảng source_refs ở trên) — "
                       "chỉ dùng khi câu mới hỏi đúng cùng một thứ.")
        st.text_input("Lý do / ghi chú (ghi vào overrides.tsv)", key=f"rw-why-{cid}")
        c = st.columns(2)
        c[0].button("Kiểm tra", on_click=_rewrite_action, args=(cid, False), width="stretch")
        author = (ss.get("author_sel") or ss.get("author") or "").strip()
        c[1].button("Áp dụng câu thay thế", type="primary", on_click=_rewrite_action, args=(cid, True), width="stretch",
                    disabled=not author)
        if not author:
            _need_author_note()
    msg = ss.get(f"rw-msg-{cid}")
    if msg:
        for w in msg.get("warns", []):
            st.warning(w, icon="⚠️")
        for e in msg.get("errors", []):
            st.error(e, icon="✖")
        if msg.get("ok"):
            st.success(msg["ok"], icon="✔")


def _refs_picker(cid: str, raw: dict) -> None:
    """Chọn source_refs cho câu mới: lọc theo điểm đến / loại / từ khoá, xem thông tin từng sản phẩm đã chọn."""
    from evaluation.search_bench import catalog_lookup as C
    ss = st.session_state
    st.markdown("**Chọn source_refs** — 1–3 sản phẩm trong catalog thoả **câu mới**.")
    with st.expander("source_refs là gì?"):
        st.markdown(SOURCE_REFS_HELP)
    cat, err = catalog()
    if cat is None:
        st.warning(f"Không nạp được catalog nên không tìm được sản phẩm: {err}")
        st.text_input("source_refs (product_id, cách nhau bằng |)", key=f"rw-refs-txt-{cid}")
        return
    cur = [r for r in _refs_of(raw) if r in cat.items.index]
    dest0, var0 = C.context_of(cat, cur)
    ss.setdefault(f"rw-dest-{cid}", dest0)
    ss.setdefault(f"rw-var-{cid}", [var0] if var0 else [])
    ss.setdefault(f"rw-refs-{cid}", cur)
    dests = sorted(cat.items["destination"].dropna().unique())
    c = st.columns([2, 2, 3])
    dest = c[0].selectbox("Điểm đến", [None, *dests], key=f"rw-dest-{cid}",
                          format_func=lambda x: "tất cả" if x is None else x)
    variants = c[1].multiselect("Loại", C.VARIANTS, key=f"rw-var-{cid}")
    text = c[2].text_input("Tên / từ khoá (không dấu cũng được)", key=f"rw-text-{cid}")
    res = C.search(cat, text=text, filter_ast=C.criteria_filter(destinations=[dest] if dest else [], variants=variants),
                   limit=200)
    options = list(dict.fromkeys([*ss.get(f"rw-refs-{cid}", []), *res["product_id"]]))
    st.multiselect(f"source_refs ({len(res)} sản phẩm khớp bộ lọc, hiện tối đa 200)", options, key=f"rw-refs-{cid}",
                   format_func=lambda pid: C.short_label(cat, pid))
    picked = ss.get(f"rw-refs-{cid}", [])
    if picked:
        st.caption("Thông tin các sản phẩm đã chọn — kiểm lại chúng thật sự thoả câu mới:")
        st.dataframe(C.describe(cat, picked), hide_index=True, width="stretch")
    with st.expander("Xem bảng sản phẩm khớp bộ lọc"):
        st.dataframe(res, hide_index=True, width="stretch", height=320)


def _rewrite_action(cid: str, save: bool) -> None:
    """Callback của khung viết câu thay thế: kiểm, rồi (nếu save) ghi overrides / drafts_raw."""
    from evaluation.search_bench import draft_authoring as D
    from evaluation.search_bench import draft_selection as S
    ss = st.session_state
    author = (ss.get("author_sel") or ss.get("author") or "").strip()
    sel = _selection()
    raw = sel.by_id[cid]
    q = (ss.get(f"rw-q-{cid}") or "").strip()
    why = ss.get(f"rw-why-{cid}") or ""
    errors: list[str] = []
    warns: list[str] = []
    new = None
    if ss.get(f"rw-mode-{cid}", RW_SAME) == RW_SAME:
        errors = S.check_rewrite(sel, cid, q)
    else:
        state = D.load_state(GOLD_DIR, dict(_config().gold.slices))
        refs = ss.get(f"rw-refs-{cid}") or [x for x in (ss.get(f"rw-refs-txt-{cid}") or "").split("|") if x.strip()]
        new = D.NewIntent(slice=raw["slice"], phrasings=[q], review_note=ss.get(f"rw-note-{cid}") or "",
                          filter_json=ss.get(f"rw-flt-{cid}") or "", source_refs=list(refs),
                          place=ss.get(f"rw-place-{cid}") or "")
        cat, _ = catalog()
        errors, warns = D.validate(state, new, cat)
        warns = [w for w in warns if "đủ quota" not in w]                 # thay 1 câu: số câu của slice không đổi
    if save and not errors and not author:
        errors.append("nhập tên người sửa ở sidebar trước khi áp dụng")
    if errors or not save:
        ss[f"rw-msg-{cid}"] = {"errors": errors, "warns": warns,
                               "ok": None if errors else "Hợp lệ — bấm “Áp dụng câu thay thế” để ghi."}
        return
    try:
        if new is None:
            rows = S.decision_rows(sel, cid, "rewrite", edited=q, author=author, note=why)
            S.upsert_overrides(GOLD_DIR / "overrides.tsv", rows, set(sel.by_id))
            target = cid
        else:
            ids = D.append_intent(D.load_state(GOLD_DIR, dict(_config().gold.slices)), new, author=author, keep=True)
            rows = S.decision_rows(sel, cid, "replace_new", chosen=ids[0], author=author, note=why)
            S.upsert_overrides(GOLD_DIR / "overrides.tsv", rows, set(sel.by_id) | set(ids))
            _cases.clear()
            target = ids[0]
        after = _selection()
        removed, added = S.diff_with_file(after, GOLD_DIR / "drafts.txt")
    except Exception as exc:
        ss[f"rw-msg-{cid}"] = {"errors": [f"Không ghi được: {exc}"], "warns": warns, "ok": None}
        return
    in_set = target in after.selected_ids()
    _flash("success" if in_set else "warning",
                     f"Đã ghi câu thay thế cho {cid} → {target} (“{q}”). drafts.txt sẽ bỏ {len(removed)} và thêm "
                     f"{len(added)} dòng — bấm “Ghi drafts.txt” khi xong."
                     + ("" if in_set else " Câu mới CHƯA vào bộ: slice có ý định KEEP khác vượt quota đứng trước "
                                          "(mã nhỏ hơn) — xem bảng hoặc nâng quota."), "case")
    ss[f"alt-{cid}"] = KEEP_AS_IS
    for k in ("rw-q", "rw-why", "rw-msg"):
        ss.pop(f"{k}-{cid}", None)
    if in_set:
        ss["sel_case"] = target


# ------------------------------------------------------------------ chế độ: gán nhãn relevance 0/1/2 (may2-label-app.md)
LABEL_OPTIONS = ["2", "1", "0"]
GUIDE_SHORT = """
**2** = đúng thứ khách tìm · **1** = liên quan một phần (đúng nơi nhưng sai loại, hoặc thiếu điều kiện) · **0** = không
liên quan hoặc **sai nơi** (câu có nêu nơi mà sản phẩm ở nơi khác → 0 kể cả đúng loại).
- Không chấm giá, ngày, số khách: điều kiện ghi "(kiểm ở cấp room)" máy tự kiểm. Chỉ dựa vào thông tin trên màn hình.
- parent_child: nhãn 2 phải tick hạng phòng đúng loại; không có hạng đúng → 0; gần đúng → 1, không tick.
- Tiện ích "không ghi nhận" vẫn có thể được 2; câu phủ định mà sản phẩm có ghi nhận tiện ích bị loại → tối đa 1.
- out_of_catalog: ứng viên thường là 0; gặp sản phẩm đúng thật thì gán theo luật chung, ghi chú và báo lại.
Đầy đủ: `docs/spec/bench/gold-guide.md`.
"""


def _label_paths() -> tuple[Path, str, Path | None, Path | None]:
    ss = st.session_state
    pool = (ss.get("lbl_pool") or "").strip()
    labels = (ss.get("lbl_labels") or "").strip()
    return (Path((ss.get("lbl_meta") or "").strip()), ss.get("lbl_who") or "", Path(pool) if pool else None,
            Path(labels) if labels else None)


@st.cache_resource(show_spinner="Đang mở pool…")
def _label_session_cached(meta: str, who: str, pool: str, labels: str, stamp: tuple):
    from evaluation.search_bench import labeling_core as L
    return L.open_session(Path(meta), who, pool_path=Path(pool) if pool else None,
                          labels_path=Path(labels) if labels else None)


def _label_session():
    """Phiên gán của người đang chọn — cache theo mtime + size của meta và pool (pool đổi là mở lại, kiểm lại sha)."""
    from evaluation.search_bench import labeling_core as L
    meta, who, pool, labels = _label_paths()
    dpool, _ = L.default_paths(meta, who)
    p = pool or dpool
    stamp = (_stamp(meta), _stamp(p) if p.exists() else None)
    return _label_session_cached(str(meta), who, str(pool or ""), str(labels or ""), stamp)


def _use_label_fixture() -> None:
    """Callback: chép pool_A/B + meta của fixture gold_small vào bench_out (không đụng fixture) để thử app."""
    import shutil

    from evaluation.search_bench import paths
    d = paths.sbench_home() / "label_try"
    d.mkdir(parents=True, exist_ok=True)
    src = ROOT / "tests" / "fixtures" / "gold_small"
    for f in ("pool_A.csv", "pool_B.csv", "pool_meta.json"):
        shutil.copyfile(src / f, d / f)
    ss = st.session_state
    ss["lbl_meta"] = str(d / "pool_meta.json")
    ss["lbl_pool"] = ""
    ss["lbl_labels"] = ""
    ss.pop("lbl_qid", None)


def _lbl_step(qids: list[str], d: int) -> None:
    ss = st.session_state
    cur = ss.get("lbl_qid")
    i = qids.index(cur) if cur in qids else 0
    ss["lbl_qid"] = qids[(i + d) % len(qids)]


def _lbl_next_unfinished() -> None:
    from evaluation.search_bench import labeling_core as L
    ss = st.session_state
    s = _label_session()
    nxt = L.next_unfinished(s, L.load_labels(s), ss.get("lbl_qid"))
    if nxt:
        ss["lbl_qid"] = nxt
    else:
        ss[f"lbl-err-{ss.get('lbl_qid')}"] = ["Đã gán xong mọi câu của pool này."]


def _lbl_edit(key: str, qid: str, pids: list[str]) -> None:
    """Callback của bảng: lưu ngay mọi dòng vừa sửa (nhãn / ghi chú); nhãn 2 ở parent_child chờ chọn hạng phòng."""
    from evaluation.search_bench import labeling_core as L
    ss = st.session_state
    s = _label_session()
    labels = L.load_labels(s)
    pend = set(ss.get(f"lbl-pend-{qid}") or set())
    errors: list[str] = []
    for idx, change in (ss.get(key) or {}).get("edited_rows", {}).items():
        pid = pids[int(idx)]
        row = s.by_key[(qid, pid)]
        cur = labels.get((qid, pid))
        lab = change["nhãn"] if "nhãn" in change else (str(cur.label) if cur else None)
        note = change.get("ghi chú", cur.note if cur else "") or ""
        if lab in (None, ""):
            pend.discard(pid)
            errors += L.clear_label(s, qid, pid) if cur else []
            if note.strip() and not cur:
                errors.append(f"{row.name}: chọn nhãn trước rồi mới ghi chú")
            continue
        children = cur.children_ok if cur and cur.label == 2 else []
        errs = L.save_label(s, qid, pid, int(lab), children, note)
        if errs and int(lab) == 2 and row.children and not children:
            pend.add(pid)
            ss[f"lbl-pendnote-{qid}-{pid}"] = note
            errors.append(f"{row.name}: nhãn 2 — tick hạng phòng đúng loại ở bên dưới để lưu")
        elif errs:
            errors += [f"{row.name}: {e}" for e in errs]
        else:
            pend.discard(pid)
    ss[f"lbl-pend-{qid}"] = pend
    ss[f"lbl-err-{qid}"] = errors
    ss[f"lbl-ver-{qid}"] = ss.get(f"lbl-ver-{qid}", 0) + 1                 # bảng mới dựng từ file nhãn vừa ghi


def _lbl_children(qid: str, pid: str, key: str) -> None:
    """Callback ô hạng phòng: lưu nhãn 2 kèm hạng phòng đã tick (thứ tự theo pool)."""
    from evaluation.search_bench import labeling_core as L
    ss = st.session_state
    s = _label_session()
    cur = L.load_labels(s).get((qid, pid))
    ids = list(ss.get(key) or [])
    note = cur.note if cur else ss.get(f"lbl-pendnote-{qid}-{pid}", "")
    if not ids:
        ss[f"lbl-err-{qid}"] = [f"{s.by_key[(qid, pid)].name}: nhãn 2 cần ít nhất một hạng phòng — không có hạng đúng "
                                "loại thì đổi nhãn thành 0 (gần đúng thì 1)"]
        ss[f"lbl-ver-{qid}"] = ss.get(f"lbl-ver-{qid}", 0) + 1
        return
    errs = L.save_label(s, qid, pid, 2, ids, note)
    ss[f"lbl-err-{qid}"] = [f"{s.by_key[(qid, pid)].name}: {e}" for e in errs]
    if not errs:
        pend = set(ss.get(f"lbl-pend-{qid}") or set())
        pend.discard(pid)
        ss[f"lbl-pend-{qid}"] = pend
    ss[f"lbl-ver-{qid}"] = ss.get(f"lbl-ver-{qid}", 0) + 1


def render_labeling() -> None:
    import pandas as pd

    from evaluation.search_bench import labeling_core as L
    ss = st.session_state
    st.title("Gán nhãn relevance 0/1/2")
    ss.setdefault("lbl_meta", str(GOLD_DIR / "pool_meta.json"))
    with st.sidebar:
        st.header("Người gán")
        st.radio("Bạn là người gán", ["A", "B"], index=None, key="lbl_who", horizontal=True,
                 help="Cố định trong phiên: app chỉ mở pool_X.csv và labels/labels_X.csv của bạn, không bao giờ đọc "
                      "nhãn của người kia (25 câu chung phải gán độc lập).")
        st.text_input("pool_meta.json", key="lbl_meta")
        with st.expander("Đường dẫn khác / thử với fixture"):
            st.text_input("pool_X.csv (trống = theo meta)", key="lbl_pool")
            st.text_input("labels_X.csv (trống = labels/ cạnh meta)", key="lbl_labels")
            st.button("Dùng bản thử fixture gold_small", on_click=_use_label_fixture,
                      help="Chép pool của fixture vào bench_out/search/label_try/ rồi mở — nhãn ghi ở đó, không đụng gold/.")
        st.button("Tải lại file", on_click=_label_session_cached.clear)
    with st.expander("Luật gán nhãn (tóm tắt gold-guide.md)"):
        st.markdown(GUIDE_SHORT)
    who = ss.get("lbl_who")
    if not who:
        st.info("Chọn người gán (A hoặc B) ở sidebar để bắt đầu.")
        return
    meta = Path(ss["lbl_meta"].strip())
    if not meta.exists():
        st.info(f"Chưa có `{meta}`. Pool thật có sau khi chốt drafts.txt rồi chạy `gold pool` và `gold split`. Muốn thử "
                "app: sidebar → “Dùng bản thử fixture gold_small”.")
        return
    try:
        s = _label_session()
        labels = L.load_labels(s)
    except (L.SessionError, ValueError, KeyError) as exc:
        st.error(str(exc))
        return

    p = L.progress(s, labels)
    m = st.columns(4)
    m[0].metric("Câu đã xong", f"{p['done_q']}/{p['total_q']}")
    m[1].metric("Cặp đã gán", f"{p['done_pairs']}/{p['total_pairs']}")
    m[2].metric("Nhãn 2 · 1 · 0", f"{p['dist'][2]} · {p['dist'][1]} · {p['dist'][0]}")
    m[3].metric("Người gán", who)
    st.caption(f"Pool: `{s.pool_path}` · nhãn ghi vào: `{s.labels_path}` (lưu ngay sau mỗi lần sửa).")

    if ss.get("lbl_qid") not in s.qids:
        ss["lbl_qid"] = L.resume_qid(s, labels) or s.qids[0]
    only = st.toggle("Chỉ câu chưa xong", key="lbl_only")
    shown = [q for q in s.qids if not only or q == ss["lbl_qid"] or not L.question_done(s, labels, q)]

    def fmt(q: str) -> str:
        n = sum(r.key in labels for r in s.by_qid[q])
        return f"{q} · {s.by_qid[q][0].query} — {n}/{len(s.by_qid[q])}{' ✔' if n == len(s.by_qid[q]) else ''}"

    c = st.columns([1, 6, 1, 2])
    c[0].button("← Trước", on_click=_lbl_step, args=(s.qids, -1), width="stretch")
    c[1].selectbox("Câu", shown, key="lbl_qid", format_func=fmt, label_visibility="collapsed")
    c[2].button("Sau →", on_click=_lbl_step, args=(s.qids, 1), width="stretch")
    c[3].button("Câu chưa xong tiếp theo", on_click=_lbl_next_unfinished, type="primary", width="stretch")

    qid = ss["lbl_qid"]
    h = L.header(s, qid)
    st.html(f'<div class="query-card"><div class="case-meta">{escape(qid)} · {escape(h["slice"])}</div>'
            f'<h2>{escape(h["query"])}</h2><div class="case-meta">{escape(h["filter_text"] or "không có điều kiện lọc")}'
            '</div></div>')
    if h["expected_no_result"]:
        st.warning("Câu ngoài catalog — ứng viên thường là 0. Gặp sản phẩm đúng thật thì gán theo luật chung, ghi chú "
                   "và báo lại (câu có thể không còn ngoài catalog).")

    pids = [r.product_id for r in s.by_qid[qid]]
    ver = ss.get(f"lbl-ver-{qid}", 0)
    key = f"lbl-ed-{who}-{qid}-{ver}"
    df = pd.DataFrame(L.candidate_rows(s, qid, labels))
    st.data_editor(
        df, key=key, hide_index=True, width="stretch", num_rows="fixed", on_change=_lbl_edit, args=(key, qid, pids),
        disabled=[col for col in df.columns if col not in ("nhãn", "ghi chú")],
        column_config={
            "nhãn": st.column_config.SelectboxColumn("nhãn", options=LABEL_OPTIONS, width="small",
                                                     help="2 đúng · 1 một phần · 0 không liên quan · trống = chưa gán"),
            "ghi chú": st.column_config.TextColumn("ghi chú", width="medium"),
            "name": st.column_config.TextColumn("tên", width="medium"),
            "taxonomy": "loại", "destination": "điểm đến",
            "star_rating": st.column_config.NumberColumn("sao", format="%.1f", width="small"),
            "amenities": st.column_config.TextColumn("tiện ích", width="medium"),
            "snippet": st.column_config.TextColumn("mô tả", width="large"),
        })
    for e in ss.get(f"lbl-err-{qid}", []):
        st.error(e)
    if h["children_visible"]:
        pend = ss.get(f"lbl-pend-{qid}") or set()
        need = [r for r in s.by_qid[qid] if (labels.get(r.key) and labels[r.key].label == 2) or r.product_id in pend]
        if need:
            st.markdown("**Hạng phòng đúng loại** — bắt buộc tick ít nhất một hạng với nhãn 2.")
        for r in need:
            k = f"lbl-ch-{qid}-{r.product_id}-{ver}"
            cur = labels.get(r.key)
            if k not in ss:
                ss[k] = list(cur.children_ok) if cur else []
            names = {ch.id: ch.name for ch in r.children}
            st.multiselect(r.name, list(names), key=k, format_func=lambda i, n=names: n.get(i, i),
                           on_change=_lbl_children, args=(qid, r.product_id, k))


# ------------------------------------------------------------------ chế độ 2: bổ sung câu hỏi theo ý định
def _form_values(sl: str):
    from evaluation.search_bench.draft_authoring import NewIntent
    ss = st.session_state
    refs = [r for r in (ss.get(f"refs-{sl}") or "").split("|")]
    return NewIntent(slice=sl, phrasings=[ss.get(f"p{i}-{sl}") or "" for i in range(3)],
                     review_note=ss.get(f"note-{sl}") or "", filter_json=ss.get(f"flt-{sl}") or "",
                     source_refs=refs, place=ss.get(f"place-{sl}") or "")


def _check_or_save(sl: str, save: bool) -> None:
    """Callback của form: chạy trước lượt vẽ lại nên được phép xoá ô nhập sau khi lưu."""
    from evaluation.search_bench import draft_authoring as D
    ss = st.session_state
    state = D.load_state(GOLD_DIR, dict(_config().gold.slices))
    new = _form_values(sl)
    cat, _ = catalog()
    errors, warns = D.validate(state, new, cat)
    author = (ss.get("author_name") or ss.get("author") or "").strip()
    if save and not errors and not author:
        errors.append("nhập tên người thêm ở sidebar trước khi lưu")
    ss[f"msg-{sl}"] = {"errors": errors, "warns": warns, "ok": None}
    if errors or not save:
        if not errors:
            ss[f"msg-{sl}"]["ok"] = "Hợp lệ — bấm “Lưu ý định” để ghi."
        return
    ids = D.append_intent(state, new, author=author, keep=bool(ss.get(f"keep-{sl}", True)))
    _cases.clear()
    ss[f"msg-{sl}"]["ok"] = (f"Đã thêm {', '.join(ids)} vào gold/drafts_raw.tsv"
                             + (" và KEEP vào gold/overrides.tsv." if ss.get(f"keep-{sl}", True) else "."))
    for k in [f"p{i}-{sl}" for i in range(3)] + [f"note-{sl}", f"place-{sl}"]:
        ss[k] = ""


def _add_form(sl: str, examples: list[str]) -> None:
    ooc = sl == OOC
    with st.form(f"add-{sl}", clear_on_submit=False, border=True):
        st.markdown("**Thêm ý định mới** — 1 đến 3 cách nói của cùng một ý định (câu đầu nên là dạng gốc, ngắn nhất).")
        cols = st.columns(3)
        for i in range(3):
            cols[i].text_input(f"Cách nói {i + 1}", key=f"p{i}-{sl}",
                               placeholder=examples[i] if i < len(examples) else "")
        if ooc:
            st.text_input("Điểm đến không có trong catalog", key=f"place-{sl}", placeholder="ví dụ: Côn Sơn",
                          help="review_note tự ghi là “absent destination:<điểm đến>”; app kiểm catalog không nhắc tới nó.")
        else:
            st.text_input("review_note — ý định", key=f"note-{sl}",
                          placeholder=f"như các dòng cùng slice, vd: {examples[-1] if examples else ''}")
            st.text_area("filter_json (bắt buộc với multi_constraint, dựng ở Tra cứu catalog → Tìm sản phẩm)",
                         key=f"flt-{sl}", height=68)
            st.text_input("source_refs — product_id thoả câu hỏi, cách nhau bằng |", key=f"refs-{sl}",
                          help="Chọn sản phẩm ở Tra cứu catalog → Tìm sản phẩm rồi bấm “Mang sang Bổ sung câu hỏi”.")
        st.checkbox("Ghi KEEP vào overrides.tsv (tôi là người quyết định câu này)", value=True, key=f"keep-{sl}")
        b1, b2 = st.columns(2)
        b1.form_submit_button("Kiểm tra", width="stretch", on_click=_check_or_save, args=(sl, False))
        b2.form_submit_button("Lưu ý định", type="primary", width="stretch", on_click=_check_or_save, args=(sl, True))
    msg = st.session_state.get(f"msg-{sl}")
    if msg:
        for w in msg["warns"]:
            st.warning(w, icon="⚠️")
        for e in msg["errors"]:
            st.error(e, icon="✖")
        if msg["ok"]:
            st.success(msg["ok"], icon="✔")


def render_authoring() -> None:
    from evaluation.search_bench import draft_authoring as D

    cfg = _config()
    st.title("Bổ sung câu hỏi theo ý định")
    st.caption("Mỗi slice là một box: bảng các ý định đã có (cách nói, review_note, trạng thái trong drafts.txt) và ô thêm "
               "ý định mới. Ý định mới ghi vào gold/drafts_raw.tsv với mã c0673… theo khối 3 (3 mã = 1 ý định) và — nếu "
               "tick — KEEP vào gold/overrides.tsv (câu được chọn luôn vào bộ, không cắt theo mục tiêu). drafts.txt chỉ "
               "đổi khi bấm “Ghi drafts.txt” ở chế độ Bộ câu đã chọn (hoặc chạy `gold drafts`).")
    _author_box("author_name", "Tên người thêm (ghi vào note của overrides.tsv)")
    try:
        state = D.load_state(GOLD_DIR, dict(cfg.gold.slices))
    except Exception as exc:
        st.error(f"Không đọc được gold/: {exc}")
        st.stop()
    if state.drafts_error:
        st.warning(f"drafts.txt không map được sang case_id nên cột trạng thái có thể thiếu: {state.drafts_error}")
    _, cat_err = catalog()
    if cat_err:
        st.warning(f"Không kiểm được grounding (source_refs, filter, điểm đến ngoài catalog): {cat_err}")
    carried = st.session_state.get("carry_refs") or st.session_state.get("carry_filter")
    if carried:
        st.info(f"Đang mang theo từ Tra cứu catalog — source_refs: {st.session_state.get('carry_refs') or '—'} · "
                f"filter: {st.session_state.get('carry_filter') or '—'} (đã điền vào các box bên dưới)")

    summary = D.slice_summary(state, int(cfg.gold.min_per_slice))
    thin = [s["slice"] for s in summary if s["dưới tối thiểu"]]
    if thin:
        st.markdown(f"**{len(thin)} slice dưới {cfg.gold.min_per_slice} câu trong drafts.txt** (mở sẵn bên dưới): "
                    + ", ".join(f"`{s}`" for s in thin) + ". Thêm ý định mới ở box của slice đó.")
    st.dataframe(summary, hide_index=True, width="stretch",
                 column_config={"dưới tối thiểu": st.column_config.CheckboxColumn(f"dưới {cfg.gold.min_per_slice}")})
    st.caption("Trạng thái chỉ dựa trên drafts.txt và overrides.tsv; nhãn REJECT trong kho nhãn của chế độ soát "
               "(labels.jsonl) không được tính ở đây.")

    order = thin + [s["slice"] for s in summary if s["slice"] not in thin]
    by_slice = {s["slice"]: s for s in summary}
    for sl in order:
        s = by_slice[sl]
        its = D.intents(state, sl)
        with st.expander(f"{sl} · {s['trong drafts.txt']} trong drafts.txt (mục tiêu {s['mục tiêu']}) · {s['ý định có']} ý định · "
                         f"{s['chưa dùng']} chưa dùng", expanded=sl in thin):
            st.dataframe([{"mã": ", ".join(i.case_ids), "trạng thái": i.status, "cách nói": " | ".join(i.queries),
                           "ý định (review_note)": i.review_note, "filter_json": i.filter_json} for i in its],
                         hide_index=True, width="stretch", height=min(38 + 35 * len(its), 320))
            examples = [q for i in its[:3] for q in i.queries[:1]] + ([its[0].review_note] if its else [])
            _add_form(sl, examples)


# ------------------------------------------------------------------ chế độ 3: tra cứu catalog
def _carry(refs: list[str], flt: dict | None) -> None:
    """Callback: mang product_id đã chọn (+ filter) sang box Bổ sung câu hỏi rồi chuyển chế độ."""
    ss = st.session_state
    ss["carry_refs"] = "|".join(refs)
    ss["carry_filter"] = json.dumps(flt, ensure_ascii=False, separators=(",", ":")) if flt else ""
    for sl in _config().gold.slices:
        if sl != OOC:
            ss[f"refs-{sl}"] = ss["carry_refs"]
    ss[f"flt-{MULTI}"] = ss["carry_filter"]
    ss["mode"] = MODE_AUTHOR


def render_catalog() -> None:
    from evaluation.search_bench import catalog_lookup as C

    st.title("Tra cứu catalog")
    cat, err = catalog()
    if err:
        st.error(err)
        st.stop()
    items = cat.items
    st.caption(f"Dữ liệu bench `{DATASET}` ({len(items)} search unit). Chỉ dựa vào đây để soạn / gán nhãn — không tra web "
               "(gold-guide.md).")
    tabs = st.tabs(["Điểm đến có dữ liệu", "Tìm sản phẩm", "Tiện ích theo điểm đến", "Kiểm tra ngoài catalog"])

    with tabs[0]:
        vc = items["variant"].value_counts()
        m = st.columns(6)
        m[0].metric("Search unit", f"{len(items):,}".replace(",", "."))
        m[1].metric("Điểm đến", items["destination"].nunique())
        for col, (v, label) in zip(m[2:], [("hotel_property", "Khách sạn"), ("attraction", "Tham quan"),
                                           ("combo", "Combo"), ("flight_route", "Tuyến bay")]):
            col.metric(label, int(vc.get(v, 0)))
        t = C.destination_table(cat)
        top = int(t["tổng"].max()) if len(t) else 1
        st.dataframe(t, hide_index=True, width="stretch", height=min(38 + 35 * len(t), 620),
                     column_config={"tổng": st.column_config.ProgressColumn("tổng", min_value=0, max_value=top, format="%d")})
        st.caption("Điểm đến có trong bảng là nơi có dữ liệu. Câu dest_type / audience / amenity nên chọn điểm đến có đủ "
                   "sản phẩm đúng loại; điểm đến không có trong bảng là ứng viên out_of_catalog — kiểm lại ở tab cuối "
                   "(tên sản phẩm hoặc tỉnh vẫn có thể nhắc tới nó).")

    with tabs[1]:
        dests = sorted(items["destination"].dropna().unique())
        amen = sorted(cat.key_to_id, key=lambda k: (cat.vocab[cat.key_to_id[k]].get("source") != "seed",
                                                    -int(cat.vocab[cat.key_to_id[k]].get("freq") or 0)))
        amen_fmt = lambda k: f"{cat.amenity_label(cat.key_to_id[k])} ({k})"          # noqa: E731
        c = st.columns([2, 2, 2])
        text = c[0].text_input("Tên / địa danh (không dấu cũng được)", key="q_text")
        pick_dest = c[1].multiselect("Điểm đến", dests, key="q_dest")
        pick_var = c[2].multiselect("Loại", C.VARIANTS, key="q_var")
        c2 = st.columns([1, 1, 2, 2])
        star = c2[0].selectbox("Sao tối thiểu", [None, 1, 2, 3, 4, 5], key="q_star",
                               format_func=lambda x: "bất kỳ" if x is None else f"≥ {x}")
        price = c2[1].number_input("Giá tối đa (đ, 0 = bỏ)", min_value=0, step=100_000, key="q_price")
        a_all = c2[2].multiselect("Có tiện ích", amen, format_func=amen_fmt, key="q_amen")
        a_none = c2[3].multiselect("Không có tiện ích", amen, format_func=amen_fmt, key="q_amen_not")
        flt = C.criteria_filter(destinations=pick_dest, variants=pick_var, star_min=star,
                                price_max=price or None, amenities_all=a_all, amenities_none=a_none)
        n = int(C.filter_mask(cat, flt).sum())
        res = C.search(cat, text=text, filter_ast=flt, limit=300)
        st.markdown(f"**{n} sản phẩm khớp filter** · hiển thị {len(res)}" + (" (lọc thêm theo tên)" if text else "")
                    + " — multi_constraint nên khớp 5–40.")
        if flt:
            st.code(json.dumps(flt, ensure_ascii=False, separators=(",", ":")), language="json")
        ev = st.dataframe(res, hide_index=True, width="stretch", height=440, key="q_table", on_select="rerun",
                          selection_mode="multi-row",
                          column_config={"giá từ": st.column_config.NumberColumn("giá từ", format="%d đ"),
                                         "sao": st.column_config.NumberColumn("sao", format="%.1f")})
        picked = [res.iloc[i]["product_id"] for i in ev.selection.rows]
        st.caption(f"Đã chọn {len(picked)} sản phẩm: {', '.join(picked[:5])}{' …' if len(picked) > 5 else ''} — "
                   "tick ô đầu dòng để chọn sản phẩm thoả câu hỏi (source_refs).")
        st.button("Mang sang Bổ sung câu hỏi (source_refs + filter)", type="primary", on_click=_carry,
                  args=(picked, flt), disabled=not picked and flt is None)

    with tabs[2]:
        c = st.columns(2)
        dest = c[0].selectbox("Điểm đến", [None, *sorted(items["destination"].dropna().unique())], key="cov_dest",
                              format_func=lambda x: "Toàn catalog" if x is None else x)
        var = c[1].selectbox("Loại", C.VARIANTS, key="cov_var")
        cov = C.amenity_coverage(cat, dest, var)
        base = int(((items["variant"] == var) & ((items["destination"] == dest) if dest else True)).sum())
        cov["tỷ lệ có"] = cov["tỷ lệ có"] * 100
        st.markdown(f"**{base} sản phẩm** {var} {('tại ' + dest) if dest else 'trong toàn catalog'} · "
                    f"{len(cov)} tiện ích được ghi nhận.")
        st.caption("Gợi ý chọn tiện ích: phủ định → 40–70% sản phẩm KHÔNG có; off-taxonomy → khoá raw, 15–40% có; "
                   "tiện ích phủ > 80% thì câu hỏi gần như không lọc được gì (bài học c0430 wifi 91%).")
        st.dataframe(cov, hide_index=True, width="stretch", height=480,
                     column_config={"tỷ lệ có": st.column_config.ProgressColumn("tỷ lệ có", min_value=0, max_value=100,
                                                                                  format="%.0f%%")})

    with tabs[3]:
        place = st.text_input("Điểm đến / địa danh cần kiểm", key="ooc_place", placeholder="ví dụ: Mộc Châu")
        if place.strip():
            hits = C.place_hits(cat, place)
            if len(hits):
                st.error(f"Catalog có {len(hits)} sản phẩm nhắc tới “{place.strip()}” ở tên, điểm đến, tỉnh hoặc thành "
                         "phố — không dùng được cho out_of_catalog.")
                st.dataframe(hits, hide_index=True, width="stretch")
            else:
                st.success(f"Không sản phẩm nào nhắc tới “{place.strip()}” — dùng được cho out_of_catalog.")


# ------------------------------------------------------------------ main
require_password()
with st.sidebar:
    mode = st.radio("Chế độ", MODES, key="mode")
if mode == MODE_SELECTED:
    render_selection()
elif mode == MODE_AUTHOR:
    render_authoring()
elif mode == MODE_LABEL:
    render_labeling()
elif mode == MODE_CATALOG:
    render_catalog()
else:
    render_review()
