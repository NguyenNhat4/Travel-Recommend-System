"""Collaborative review UI for the 600 Role A search-query candidates."""
from __future__ import annotations

import hmac
import os
from collections import Counter, defaultdict
from html import escape
from pathlib import Path

import streamlit as st

from labeling import (
    REJECTION_REASONS,
    VERDICTS,
    JsonlLabelStore,
    consensus,
    latest_by_annotator,
    latest_events_csv,
    load_cases,
    new_label_event,
)


ROOT = Path(__file__).resolve().parent
CASES_PATH = ROOT / "gold" / "drafts_raw.tsv"
LOCAL_LABELS_PATH = Path(os.getenv("LABEL_STORE_PATH", "bench_out/search/labels/labels.jsonl"))

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


@st.cache_data
def cases():
    return load_cases(CASES_PATH)


@st.cache_resource
def store():
    return JsonlLabelStore(LOCAL_LABELS_PATH)


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


all_cases = cases()
case_by_id = {item.case_id: item for item in all_cases}
require_password()

st.title("Search query labeling")
st.caption("Review 600 query ứng viên của Role A. Đây chưa phải relevance label 0/1/2 và chưa phải gold_v1.")

with st.sidebar:
    st.header("Phiên gán nhãn")
    annotator = st.text_input("Tên annotator", placeholder="Ví dụ: khoi", key="annotator").strip()
    selected_slice = st.selectbox("Slice", ["Tất cả", *sorted({item.slice for item in all_cases})])
    review_filter = st.radio("Trạng thái của tôi", ["Chưa gán", "Đã gán", "Tất cả"], horizontal=False)
    search_text = st.text_input("Tìm query / case ID").strip().casefold()
    st.caption("Lưu trữ: file JSONL dùng chung trên instance Streamlit")
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
