"""Giao diện chạy bộ test case của Itinerary Agent: chọn case, xem tiến độ, đọc lý do fail, so các lần chạy, thêm case.

Chạy: `make agent-eval` (bật backend nếu chưa có) hoặc
`.venv/bin/python -m streamlit run src/evaluation/agent/eval_app.py --server.port 8503` khi backend đã chạy.
Mỗi lần chạy là tiến trình `python -m src.evaluation.agent.golden` (eval_runs.py), nên luật chấm y hệt CLI.
Hướng dẫn: docs/spec/agent/golden-run.md mục "Chạy bằng giao diện".
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:  # `streamlit run` chỉ thêm thư mục của script vào sys.path
    sys.path.insert(0, str(REPO_ROOT))

import httpx  # noqa: E402
import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402
import yaml  # noqa: E402

from src.backend.app.agents.steps.classification import vietnam_today  # noqa: E402
from src.evaluation.agent import case_builder as cb  # noqa: E402
from src.evaluation.agent import eval_runs as er  # noqa: E402
from src.evaluation.agent.golden import load_dataset, resolve_dates  # noqa: E402

API_BASE = os.getenv("EVAL_API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
DATASET = Path(os.getenv("AGENT_EVAL_DATASET") or cb.DATASET_PATH)
HISTORY_LIMIT = 30

st.set_page_config(page_title="Agent Eval", page_icon="🧪", layout="wide")


# ------------------------------------------------------------------------------------------ data


@st.cache_data(show_spinner=False)
def _load_cases(path: str, mtime: float):
    return load_dataset(Path(path))


@st.cache_data(show_spinner=False)
def _load_raw(path: str, mtime: float) -> dict[str, dict]:
    return {item["id"]: item for item in yaml.safe_load(Path(path).read_text(encoding="utf-8")) or []}


def dataset_cases():
    return _load_cases(str(DATASET), DATASET.stat().st_mtime)


def dataset_raw() -> dict[str, dict]:
    return _load_raw(str(DATASET), DATASET.stat().st_mtime)


@st.cache_data(ttl=5, show_spinner=False)
def backend_status(api: str) -> dict | None:
    try:
        return httpx.get(f"{api}/api/v1/assistant/status", timeout=2).json()
    except Exception:
        return None


@st.cache_data(ttl=300, show_spinner=False)
def destinations(api: str) -> list[str]:
    try:
        listed = httpx.get(f"{api}/api/v1/destinations", timeout=5).json()["destinations"]
        return sorted(item["destination"] for item in listed)
    except Exception:
        return []


@st.cache_data(show_spinner=False)
def fr_codes() -> list[str]:
    return cb.fr_codes()


def recent_views() -> list[er.RunView]:
    return [er.load_run(run_id) for run_id in er.list_runs()[:HISTORY_LIMIT]]


def rel(path: Path | str) -> str:
    path = Path(path)
    return str(path.relative_to(REPO_ROOT)) if path.is_relative_to(REPO_ROOT) else str(path)


def pct(value) -> str:
    return "—" if value is None else f"{value:.0%}"


# ------------------------------------------------------------------------------------------ run


def start(case_ids: list[str] | None, official: bool = False) -> None:
    if er.active_run():
        st.toast("Đang có một lần chạy; đợi xong hoặc bấm Dừng trước.", icon="⏳")
        return
    options = er.RunOptions(
        case_ids=case_ids, repeat=st.session_state.opt_repeat, sweep=st.session_state.opt_sweep,
        trace_project=st.session_state.opt_trace.strip() or None,
        judge_model=st.session_state.opt_judge.strip() or None, timeout=float(st.session_state.opt_timeout),
        api_base_url=API_BASE, official_report=official, dataset=str(DATASET),
    )
    st.session_state.view_run = er.start_run(options)
    st.toast(f"Đã bắt đầu chạy {', '.join(case_ids) if case_ids else 'cả bộ'}", icon="▶️")


def render_turn(turn: dict) -> None:
    repetition = f" · lần {turn['repetition']}" if turn.get("repetition", 1) > 1 else ""
    icon = "✅" if turn["passed"] else "❌"
    st.markdown(f"{icon} **Lượt {turn['turn']}/{turn.get('turns', '?')}**{repetition} · `{turn.get('status')}` · "
                f"HTTP {turn.get('httpStatus')} · {turn.get('latencyMs', 0):,} ms")
    with st.chat_message("user"):
        st.markdown(turn["message"])
    with st.chat_message("assistant"):
        st.markdown(turn.get("reply") or "_(không có câu trả lời)_")
    rules = [f for f in turn["findings"] if not f.startswith("[judge]")]
    judged = [f.removeprefix("[judge]").strip() for f in turn["findings"] if f.startswith("[judge]")]
    if rules:
        st.error("**Kiểm tra tất định không đạt**\n\n" + "\n".join(f"- {f}" for f in rules))
    if judged:
        st.warning("**LLM giám khảo chấm không đạt** (tiêu chí: lý do)\n\n" + "\n".join(f"- {f}" for f in judged))
    if turn.get("dropped"):
        st.info("**Đã loại** (trùng trước khi xếp lịch)\n\n" + "\n".join(
            f"- {item.get('name')} → trùng với {item.get('duplicateOfName')} (`{item.get('by')}`)"
            for item in turn["dropped"]))
    details = []
    if turn.get("intent"):
        intent = {k: v for k, v in turn["intent"].items() if v not in (None, [], {})}
        details.append(f"intent: `{intent}`")
    if turn.get("missingFields"):
        details.append(f"missingFields: `{turn['missingFields']}`")
    if turn.get("traceName"):
        details.append(f"trace LangSmith: `{turn['traceName']}`")
    if details:
        st.caption(" · ".join(details))


def render_case(case: er.CaseView, current: dict | None) -> None:
    running = current is not None and current.get("caseId") == case.case_id
    if case.passed is True:
        icon = "✅"
    elif case.passed is False:
        icon = "❌"
    elif running or case.turns:
        icon = "⏳"
    else:
        icon = "⚪"
    passed = sum(1 for t in case.turns if t["passed"])
    title = f"{icon} {case.case_id} · {case.category} · {passed}/{len(case.turns)} lượt đạt"
    with st.expander(title, expanded=case.passed is False or running):
        if not case.turns and not running:
            st.caption("Chưa chạy tới case này.")
        for turn in case.turns:
            render_turn(turn)
            st.divider()
        if running:
            st.info(f"Đang chạy lượt {current['turn']}/{current['turns']}: «{current['message']}»")


def run_panel(run_id: str, live: bool) -> None:
    view = er.load_run(run_id)
    if live and view.state != er.RUNNING:
        st.rerun(scope="app")  # vừa xong: vẽ lại cả trang để bảng case và lịch sử cập nhật
    meta, options = view.meta, view.meta.get("options", {})
    chosen = ", ".join(options.get("case_ids") or []) or "cả bộ"
    extras = [f"lặp {options['repeat']} lần" if options.get("repeat", 1) > 1 else "",
              "kèm sweep" if options.get("sweep") else "",
              f"trace `{options['trace_project']}`" if options.get("trace_project") else "không gửi trace"]
    dirty = " (working tree có thay đổi chưa commit)" if meta.get("dirty") else ""
    st.markdown(f"**{er.STATE_LABELS[view.state].capitalize()}** · bắt đầu {meta.get('startedAt', '?')} · "
                f"commit `{meta.get('commit', '?')}`{dirty} · case: {chosen} · {' · '.join(e for e in extras if e)}")

    total = max(view.total_turns, view.finished_turns, 1)
    st.progress(min(view.finished_turns / total, 1.0),
                text=f"{view.finished_turns}/{view.total_turns or '?'} lượt · ✅ {view.passed_turns} đạt · "
                     f"❌ {view.failed_turns} không đạt")
    if view.state == er.RUNNING:
        left, right = st.columns([4, 1])
        if view.current:
            left.info(f"Đang chạy **{view.current['caseId']}** · lượt {view.current['turn']}/"
                      f"{view.current['turns']}: «{view.current['message']}»")
        else:
            left.info("Đang khởi động runner (nạp LLM, gọi backend)…")
        right.button("⏹ Dừng", key=f"stop_{run_id}", on_click=er.stop_run, args=(run_id,), width="stretch")
    if view.error:
        st.error(view.error)
    if view.state in (er.FAILED, er.STOPPED) or view.error:
        with st.expander("Log của runner (stdout.log)", expanded=view.state == er.FAILED):
            st.code(er.stdout_tail(run_id) or "(trống)", language="text")
    if view.done:
        metrics, latency = view.done["metrics"], view.done.get("latencyMs") or {}
        cols = st.columns(5)
        cols[0].metric("Lượt đạt", f"{view.done['totals']['passed']}/{view.done['totals']['turns']}")
        cols[1].metric("Grounding (100%)", pct(metrics.get("groundingRate")))
        cols[2].metric("Structured Output (100%)", pct(metrics.get("structuredOutputIntegrity")))
        cols[3].metric("Tool Calling (≥95%)", pct(metrics.get("toolCallingAccuracy")))
        cols[4].metric("Latency p50 / max", f"{latency.get('p50') or '—'} / {latency.get('max') or '—'} ms")
        st.caption(f"Model `{view.done.get('model')}` · giám khảo `{view.done.get('judgeModel') or 'không dùng'}` · "
                   f"biên bản `{rel(view.done['reportMd']) if view.done.get('reportMd') else '?'}`")

    ordered = sorted(view.cases.values(), key=lambda c: (c.passed is not False, c.passed is True))
    for case in ordered:
        render_case(case, view.current)


def run_tab(ready: bool) -> None:
    cases = dataset_cases()
    views = recent_views()
    latest = er.latest_results(views)
    active = er.active_run()

    rows = []
    for case in cases:
        result = latest.get(case.id)
        rows.append({
            "Case": case.id, "Nhóm": case.category, "FR": ", ".join(case.fr), "Lượt": len(case.turns),
            "Câu đầu": case.turns[0].message,
            "Lần gần nhất": "—" if result is None else ("✅ PASS" if result[0] else "❌ FAIL"),
            "Lý do fail đầu tiên": (result[2] or "") if result else "",
        })
    st.markdown("**Chọn case** (bấm vào hàng, giữ Ctrl/Shift để chọn nhiều) rồi bấm chạy.")
    event = st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch", on_select="rerun",
                         selection_mode="multi-row", key="case_table",
                         column_config={"Câu đầu": st.column_config.TextColumn(width="large"),
                                        "Lý do fail đầu tiên": st.column_config.TextColumn(width="large")})
    selected = [rows[i]["Case"] for i in event.selection.rows]
    failed_last = [case.id for case in cases if latest.get(case.id, (True,))[0] is False]

    blocked = not ready or active is not None
    c1, c2, c3, c4 = st.columns([2, 2, 2, 2])
    if c1.button(f"▶️ Chạy {len(selected)} case đã chọn", disabled=blocked or not selected, width="stretch"):
        start(selected)
        st.rerun()
    official = c4.checkbox("Ghi biên bản chính thức", key="opt_official",
                           help="Chỉ áp dụng cho 'Chạy tất cả': ghi đè src/evaluation/reports/eval-<ngày>-"
                                "agent-test-cases.md như chạy CLI (để commit). Không tick thì biên bản nằm trong "
                                "thư mục của lần chạy, không đụng biên bản đã commit.")
    if c2.button("⏩ Chạy tất cả", disabled=blocked, width="stretch"):
        start(None, official=official)
        st.rerun()
    if c3.button(f"🔁 Chạy lại {len(failed_last)} case FAIL", disabled=blocked or not failed_last, width="stretch",
                 help="Các case FAIL ở lần gần nhất có chạy chúng."):
        start(failed_last)
        st.rerun()
    if not ready:
        st.caption("Nút chạy bị khoá vì backend chưa sẵn sàng (xem sidebar).")

    st.divider()
    run_ids = er.list_runs()
    if not run_ids:
        st.info("Chưa có lần chạy nào. Chọn case rồi bấm chạy.")
        return
    default = st.session_state.get("view_run")
    labels = {v.run_id: f"{v.run_id} · {er.STATE_LABELS[v.state]} · "
                        f"{', '.join(v.meta.get('options', {}).get('case_ids') or []) or 'cả bộ'}" for v in views}
    run_id = st.selectbox("Xem lần chạy", run_ids[:HISTORY_LIMIT],
                          index=run_ids.index(default) if default in run_ids[:HISTORY_LIMIT] else 0,
                          format_func=lambda rid: labels.get(rid, rid))
    st.session_state.view_run = run_id
    if er.load_run(run_id).state == er.RUNNING:
        st.fragment(run_every="2s")(run_panel)(run_id, True)
    else:
        run_panel(run_id, False)


# -------------------------------------------------------------------------------------- history


def history_tab() -> None:
    views = recent_views()
    if not views:
        st.info("Chưa có lần chạy nào.")
        return
    st.markdown("Mỗi cột là một lần chạy (mới nhất bên trái). **Hồi quy** = case đạt ở lần trước nhưng không đạt ở "
                "lần gần nhất có chạy nó — dấu hiệu tune làm hỏng case cũ.")
    count = st.slider("Số lần chạy để so", 2, len(views), min(8, len(views))) if len(views) > 2 else len(views)
    shown = [v for v in views[:count] if v.state != er.RUNNING]
    rows = er.compare_runs(shown)
    regressions = [row["caseId"] for row in rows if row["change"] == er.REGRESSION]
    fixed = [row["caseId"] for row in rows if row["change"] == er.FIXED]
    if regressions:
        st.error(f"Hồi quy: {', '.join(regressions)}")
    if fixed:
        st.success(f"Đã sửa được: {', '.join(fixed)}")
    if not regressions and not fixed and rows:
        st.info("Không case nào đổi kết quả giữa hai lần chạy gần nhất của nó.")
    only_changed = st.checkbox("Chỉ hiện case đổi kết quả")
    table = []
    for row in rows:
        if only_changed and not row["change"]:
            continue
        line = {"Case": row["caseId"],
                "Thay đổi": {er.REGRESSION: "🔴 hồi quy", er.FIXED: "🟢 đã sửa"}.get(row["change"], "")}
        for view in shown:
            value = row["results"].get(view.run_id)
            line[view.run_id] = "" if value is None else ("✅" if value else "❌")
        table.append(line)
    if table:
        st.dataframe(pd.DataFrame(table), hide_index=True, width="stretch")

    st.subheader("Các lần chạy")
    summary = []
    for view in views:
        options = view.meta.get("options", {})
        failed = [cid for cid, ok in view.case_results().items() if not ok]
        summary.append({
            "Lần chạy": view.run_id, "Trạng thái": er.STATE_LABELS[view.state],
            "Commit": view.meta.get("commit", "?") + (" *" if view.meta.get("dirty") else ""),
            "Case": ", ".join(options.get("case_ids") or []) or "cả bộ",
            "Lượt đạt": f"{view.passed_turns}/{view.finished_turns}", "Case FAIL": ", ".join(failed),
        })
    st.dataframe(pd.DataFrame(summary), hide_index=True, width="stretch")
    st.caption("Commit có dấu * = chạy trên working tree có thay đổi chưa commit. Dữ liệu ở "
               f"`{rel(er.runs_dir())}`.")


# ------------------------------------------------------------------------------------- new case

LIST_KEYS = {"status", "missingFieldsInclude", "nodesInclude", "nodesExclude", "toolsInclude", "warningsExclude",
             "warningsInclude", "cardTaxonomies"}
LINES_KEYS = {"forbiddenText", "judge", "textIncludes"}
INT_KEYS = {"minActivities", "cardsMin", "cardsMax", "suggestionsMin"}
#: Taxonomy của thẻ (`cardTaxonomies`), theo enum taxonomy của contract Search.
CARD_TAXONOMIES = ["attraction", "hotel", "flight", "golf", "combo", "hotel_room"]
BOOL_KEYS = {"toolCalled", "hasStay", "titleFirstLine"}


def _k(uid: int, name: str) -> str:
    return f"nc_{uid}_{name}"


def _reset_form() -> None:
    for key in [k for k in st.session_state if str(k).startswith("nc_") and k != "nc_template"]:
        del st.session_state[key]


def _new_turn() -> int:
    uid = st.session_state.get("nc_next_uid", 0)
    st.session_state.nc_next_uid = uid + 1
    st.session_state.setdefault("nc_turns", []).append(uid)
    return uid


def _remove_turn(uid: int) -> None:
    st.session_state.nc_turns.remove(uid)


def _load_template() -> None:
    template = st.session_state.get("nc_template")
    _reset_form()
    if not template or template == "(trống)":
        return
    raw = dataset_raw()[template]
    st.session_state.nc_category = raw.get("category", "")
    st.session_state.nc_fr = [code for code in raw.get("fr", []) if code in fr_codes()]
    st.session_state.nc_turns = []
    for turn in raw.get("turns", []):
        uid = _new_turn()
        st.session_state[_k(uid, "message")] = turn.get("message", "")
        st.session_state[_k(uid, "language")] = turn.get("language") or "(mặc định)"
        for key, value in (turn.get("expect") or {}).items():
            if key == "intent":
                st.session_state[_k(uid, "intent_on")] = True
                for path, item in value.items():
                    st.session_state[_k(uid, f"intent.{path}_on")] = True
                    st.session_state[_k(uid, f"intent.{path}")] = item
                continue
            st.session_state[_k(uid, f"{key}_on")] = True
            if key in LINES_KEYS:
                st.session_state[_k(uid, key)] = "\n".join(map(str, value))
            elif key == "excludeProductsFromTurn":
                st.session_state[_k(uid, "excl_turn")] = value.get("turn", 1)
                st.session_state[_k(uid, "excl_role")] = value.get("role", "stay")
            elif key != "formMatchesAnswer":
                st.session_state[_k(uid, key)] = value


def _toggle_raw() -> None:
    if st.session_state.get("nc_raw_mode"):
        st.session_state.nc_raw = st.session_state.get("nc_generated", "")


def _expect_widget(uid: int, key: str, index: int, dest_options: list[str]) -> None:
    """Một khoá expect: ô tick bật khoá + widget giá trị. Không tick thì khoá không vào YAML."""
    info = cb.FIELD_HELP[key]
    on = st.checkbox(f"{info.label}", key=_k(uid, f"{key}_on"), help=info.tooltip())
    if not on:
        return
    value_key = _k(uid, key)
    with st.container(border=True):
        if key == "httpStatus":
            st.session_state.setdefault(value_key, 200)
            st.selectbox("Mã HTTP", cb.HTTP_STATUSES, key=value_key, accept_new_options=True,
                         label_visibility="collapsed")
        elif key == "status":
            st.multiselect("status", cb.STATUSES, key=value_key, label_visibility="collapsed",
                           placeholder="Chọn một hoặc nhiều status hợp lệ")
        elif key == "errorCode":
            st.selectbox("errorCode", cb.error_codes(), key=value_key, label_visibility="collapsed")
        elif key == "intent":
            for field in cb.intent_fields():
                _intent_widget(uid, field, dest_options)
        elif key == "missingFieldsInclude":
            st.multiselect("missingFields", cb.missing_field_values(), key=value_key, label_visibility="collapsed")
        elif key in BOOL_KEYS:
            st.session_state.setdefault(value_key, key != "toolCalled")
            st.radio(key, [True, False], key=value_key, horizontal=True, label_visibility="collapsed",
                     format_func=lambda v: "true — có" if v else "false — không")
        elif key == "formMatchesAnswer":
            st.caption("Bật khoá này = ghi `formMatchesAnswer: true`.")
        elif key in ("nodesInclude", "nodesExclude"):
            st.multiselect(key, cb.node_names(), key=value_key, label_visibility="collapsed")
        elif key == "toolsInclude":
            st.multiselect(key, cb.tool_names(), key=value_key, label_visibility="collapsed")
        elif key in ("warningsExclude", "warningsInclude"):
            current = st.session_state.get(value_key) or []
            st.multiselect(key, sorted(set(cb.WARNING_CODES) | set(current)), key=value_key,
                           accept_new_options=True, label_visibility="collapsed")
        elif key in INT_KEYS:
            st.session_state.setdefault(value_key, 2)
            st.number_input(key, min_value=0, max_value=14, key=value_key, label_visibility="collapsed")
        elif key == "cardTaxonomies":
            st.multiselect(key, CARD_TAXONOMIES, key=value_key, label_visibility="collapsed")
        elif key == "phraseMaxCount":
            st.text_area(key, key=value_key, label_visibility="collapsed", placeholder="mỗi dòng: cụm=số lần tối đa")
        elif key == "excludeProductsFromTurn":
            if index == 1:
                st.caption("Chỉ dùng từ lượt 2 trở đi.")
                return
            st.session_state.setdefault(_k(uid, "excl_turn"), 1)
            st.number_input("Không lặp sản phẩm của lượt số", min_value=1, max_value=index - 1,
                            key=_k(uid, "excl_turn"))
            st.radio("So", ["stay", "any"], key=_k(uid, "excl_role"), horizontal=True,
                     format_func=lambda v: "stay — chỉ chỗ ở" if v == "stay" else "any — chỗ ở và hoạt động")
        elif key in LINES_KEYS:
            st.text_area(key, key=value_key, label_visibility="collapsed",
                         placeholder="Mỗi dòng một " + ("tiêu chí" if key == "judge" else "chuỗi"))


def _intent_widget(uid: int, field: cb.IntentField, dest_options: list[str]) -> None:
    on_key, value_key = _k(uid, f"intent.{field.path}_on"), _k(uid, f"intent.{field.path}")
    left, right = st.columns([2, 3])
    if not left.checkbox(f"{field.label} (`{field.path}`)", key=on_key, help=field.help):
        return
    if field.kind == "text":
        st.session_state.setdefault(value_key, None)
        current = st.session_state[value_key]
        options = sorted(set(dest_options) | ({current} if current else set()))
        right.selectbox(field.label, options, key=value_key, accept_new_options=True,
                        placeholder="Chọn hoặc gõ tên điểm đến", label_visibility="collapsed")
    elif field.kind == "int":
        st.session_state.setdefault(value_key, {"days": 3, "party.adults": 2, "budget": 5_000_000}.get(field.path, 0))
        right.number_input(field.label, min_value=0, step=1_000_000 if field.path == "budget" else 1,
                           key=value_key, label_visibility="collapsed")
    elif field.kind == "date":
        st.session_state.setdefault(value_key, "{today+7:iso}")
        right.text_input(field.label, key=value_key, label_visibility="collapsed")
        resolved = resolve_dates(st.session_state[value_key], vietnam_today())
        right.caption(f"Hôm nay sẽ so với: `{resolved}`")
    elif field.kind == "enum":
        right.selectbox(field.label, field.options, key=value_key, label_visibility="collapsed")


def _collect_case(case_id: str) -> dict:
    turns = []
    for uid in st.session_state.get("nc_turns", []):
        turn: dict = {"message": st.session_state.get(_k(uid, "message"), "").strip()}
        language = st.session_state.get(_k(uid, "language"))
        if language and language != "(mặc định)":
            turn["language"] = language
        expect: dict = {}
        for _, keys in cb.EXPECT_GROUPS:
            for key in keys:
                if not st.session_state.get(_k(uid, f"{key}_on")):
                    continue
                value = st.session_state.get(_k(uid, key))
                if key == "intent":
                    intent = {f.path: st.session_state.get(_k(uid, f"intent.{f.path}"))
                              for f in cb.intent_fields() if st.session_state.get(_k(uid, f"intent.{f.path}_on"))}
                    intent = {path: v for path, v in intent.items() if v not in (None, "")}
                    if intent:
                        expect["intent"] = intent
                elif key == "formMatchesAnswer":
                    expect[key] = True
                elif key == "excludeProductsFromTurn":
                    if _k(uid, "excl_turn") in st.session_state:
                        expect[key] = {"turn": int(st.session_state[_k(uid, "excl_turn")]),
                                       "role": st.session_state.get(_k(uid, "excl_role"), "stay")}
                elif key == "phraseMaxCount":
                    pairs = [line.rsplit("=", 1) for line in str(value or "").splitlines() if "=" in line]
                    counts = {phrase.strip(): int(limit) for phrase, limit in pairs
                              if phrase.strip() and limit.strip().isdigit()}
                    if counts:
                        expect[key] = counts
                elif key in LINES_KEYS:
                    lines = [line.strip() for line in str(value or "").splitlines() if line.strip()]
                    if lines:
                        expect[key] = lines
                elif key in LIST_KEYS:
                    if value:
                        expect[key] = list(value)
                elif key == "httpStatus":
                    try:
                        expect[key] = int(value)
                    except (TypeError, ValueError):
                        expect[key] = value
                elif value is not None:
                    expect[key] = int(value) if key in INT_KEYS else value
        turn["expect"] = expect
        turns.append(turn)
    return {"id": case_id, "category": st.session_state.get("nc_category", "").strip(),
            "fr": list(st.session_state.get("nc_fr", [])), "turns": turns}


def new_case_tab(ready: bool) -> None:
    cases = dataset_cases()
    ids = [case.id for case in cases]
    today = vietnam_today()
    st.markdown(
        "Điền form → **Kiểm tra** → **Lưu vào dataset** → **Chạy thử**. Khoá nào không tick thì không ghi vào YAML. "
        "Rê chuột vào dấu ⓘ để xem hướng dẫn từng khoá; bảng đầy đủ ở tab **📖 Hướng dẫn**. Nguyên tắc: chỉ ghi điều "
        "**luôn đúng** với mọi catalog — không ghi productId, tên sản phẩm hay giá.")
    with st.expander("Runner đã tự kiểm ở mọi lượt (không cần khai báo)"):
        st.markdown(
            "- Mọi `productId` có thật trong `cdp.products`, tên/giá/điểm đến/`available` khớp DB, đúng điểm đến.\n"
            "- Response khớp schema contract; không lộ API key; không câu \"đã đặt\", \"đã thanh toán\".\n"
            "- Thiếu điểm đến/số ngày thì không được gọi tool; quyết định gọi tool đúng loại response.\n"
            "- Lượt `COMPLETED`: số ngày bằng `intent.days`, chỗ ở là hotel rẻ nhất, tối đa 2 hoạt động/ngày "
            "(sáng → chiều), ngày trống có warning `DAY_WITHOUT_PRODUCTS`, không trùng sản phẩm.")

    top = st.columns([3, 1, 1])
    top[0].selectbox("Bắt đầu từ", ["(trống)", *ids], key="nc_template",
                     help="Chọn một case có sẵn làm mẫu rồi bấm 'Nạp mẫu'; id mới vẫn được gợi ý riêng.")
    top[1].button("Nạp mẫu", on_click=_load_template, width="stretch")
    top[2].button("Xoá form", on_click=_reset_form, width="stretch")

    suggested = cb.next_case_id(ids)
    st.session_state.setdefault("nc_id", suggested)
    if st.session_state.nc_id in ids:
        st.session_state.nc_id = suggested
    head = st.columns([1, 2, 3])
    head[0].text_input("Id", key="nc_id", help="Dạng TC-NN, tiếp theo số lớn nhất hiện có. Không dùng lại id của case "
                                               "đã xoá: biên bản và trace LangSmith cũ còn tham chiếu tới nó.")
    head[1].text_input("Nhóm (category)", key="nc_category", placeholder="vd. change_date",
                       help="snake_case, tự đặt theo loại lỗi; cũng thành tag trong LangSmith.")
    head[2].multiselect("Mã FR/NFR", fr_codes(), key="nc_fr",
                        help="Yêu cầu trong docs/prd/requirements.md mà case kiểm. Agent: FR-AGT-01..05; "
                             "grounding: NFR-REL-01.")
    st.text_area("Lỗi gốc / mong đợi (thành comment YAML phía trên case)", key="nc_comment", height=80,
                 placeholder="TC-11 — Tiêu đề ngắn. Lỗi gốc: ... Mong đợi: ...")

    with st.expander("Cách ghi ngày trong câu và kỳ vọng"):
        sample = [("{today+7}", "câu người dùng gõ"), ("{today+7:dm}", "câu gõ, không năm"),
                  ("{today+7:vi}", "câu gõ, dạng chữ"), ("{today+7:iso}", "giá trị trong kỳ vọng, vd. intent.startDate"),
                  ("{today}", "hôm nay"), ("{today-1}", "hôm qua")]
        st.dataframe(pd.DataFrame([{"Viết": code, "Hôm nay thành": resolve_dates(code, today), "Dùng cho": use}
                                   for code, use in sample]), hide_index=True)
        st.caption("Runner thay theo ngày ở Việt Nam lúc chạy, nên case không cũ đi và luôn nằm trong cửa sổ đặt chỗ 30 "
                   "ngày. Đừng ghi ngày cứng như 20/10.")

    if not st.session_state.get("nc_turns"):
        _new_turn()
    dest_options = destinations(API_BASE)
    for index, uid in enumerate(list(st.session_state.nc_turns), start=1):
        with st.container(border=True):
            title, remove = st.columns([6, 1])
            title.markdown(f"#### Lượt {index}")
            if len(st.session_state.nc_turns) > 1:
                remove.button("Xoá lượt", key=_k(uid, "remove"), on_click=_remove_turn, args=(uid,))
            msg_col, lang_col = st.columns([5, 1])
            msg_col.text_area("Câu người dùng gõ", key=_k(uid, "message"), height=68,
                              help="Chép nguyên văn từ lỗi thật. Lượt sau tự nối vào cùng hội thoại như frontend.")
            lang_col.selectbox("Ngôn ngữ", ["(mặc định)", "vi", "en"], key=_k(uid, "language"),
                               help="context.language của request; mặc định backend dùng tiếng Việt.")
            message = st.session_state.get(_k(uid, "message"), "")
            if "{today" in message:
                msg_col.caption(f"Gửi đi hôm nay: «{resolve_dates(message, today)}»")
            st.markdown("**Kỳ vọng** — tick khoá cần kiểm")
            groups = st.columns(3)
            for position, (group, keys) in enumerate(cb.EXPECT_GROUPS):
                with groups[position % 3]:
                    st.markdown(f"*{group}*")
                    for key in keys:
                        _expect_widget(uid, key, index, dest_options)
    st.button("➕ Thêm lượt", on_click=_new_turn)

    case = _collect_case(st.session_state.nc_id.strip())
    generated = cb.case_to_yaml(case, st.session_state.get("nc_comment", ""))
    st.session_state.nc_generated = generated
    st.subheader("YAML sẽ nối vào dataset")
    raw_mode = st.toggle("Sửa YAML thô", key="nc_raw_mode", on_change=_toggle_raw,
                         help="Cho người quen YAML: sửa trực tiếp khối dưới đây; form phía trên bị bỏ qua.")
    if raw_mode:
        text = st.text_area("YAML", key="nc_raw", height=360, label_visibility="collapsed")
    else:
        st.code(generated, language="yaml")
        text = generated

    actions = st.columns([1, 1, 2])
    check = actions[0].button("🔍 Kiểm tra", width="stretch")
    save = actions[1].button("💾 Lưu vào dataset", type="primary", width="stretch")
    if check or save:
        errors, warnings = cb.validate_block(text, DATASET, today, dest_options)
        for warning in warnings:
            st.warning(warning)
        if errors:
            st.error("Chưa lưu được:\n\n" + "\n".join(f"- {e}" for e in errors))
        elif check:
            st.success("Hợp lệ. Bấm 'Lưu vào dataset' để nối vào cuối file.")
        else:
            cb.append_case(text, DATASET)
            st.session_state.nc_saved = cb.parse_case_block(text)["id"]
            st.cache_data.clear()
    saved = st.session_state.get("nc_saved")
    if saved:
        st.success(f"Đã nối {saved} vào `{rel(DATASET)}`. "
                   "Nhớ chạy `pytest src/evaluation/tests/test_golden.py` và ghi entry history khi commit.")
        run_col, reset_col = st.columns(2)
        if run_col.button(f"▶️ Chạy thử {saved}", disabled=not ready or er.active_run() is not None):
            start([saved])
            st.rerun()
        if reset_col.button("Tạo case khác", on_click=_reset_form):
            st.rerun()


# ----------------------------------------------------------------------------------------- guide


def guide_tab() -> None:
    st.markdown("Nguồn: `docs/spec/agent/golden-dataset-how-to-add-more-case.md` (mục 4–6). Mọi khoá đều tuỳ chọn; "
                "runner chỉ kiểm khoá có mặt và từ chối khoá gõ sai tên.")
    st.dataframe(pd.DataFrame([{"Khoá": key, "Tên": info.label, "Kiểm gì": info.checks, "Khi nào dùng": info.when,
                                "Ví dụ": info.example} for key, info in cb.FIELD_HELP.items()]),
                 hide_index=True, width="stretch",
                 column_config={"Kiểm gì": st.column_config.TextColumn(width="large"),
                                "Khi nào dùng": st.column_config.TextColumn(width="large")})
    st.subheader("Trường của intent")
    st.dataframe(pd.DataFrame([{"Đường dẫn": f.path, "Tên": f.label, "Ghi chú": f.help,
                                "Giá trị": ", ".join(f.options)} for f in cb.intent_fields()]), hide_index=True)
    st.subheader("Giá trị hợp lệ (lấy từ contract và code)")
    st.markdown(
        f"- **status:** {', '.join(cb.STATUSES)}\n"
        f"- **missingFields:** {', '.join(cb.missing_field_values())}\n"
        f"- **node:** {', '.join(cb.node_names())}\n"
        f"- **tool:** {', '.join(cb.tool_names())}\n"
        f"- **errorCode:** {', '.join(cb.error_codes())}")
    st.subheader("Chọn độ chặt của kỳ vọng")
    st.markdown(
        "- Luồng có spec rõ thì khoá chặt (điểm đến ngoài catalog → `httpStatus: 422` + `errorCode`).\n"
        "- Luồng code cho phép nhiều nhánh hợp lệ thì chỉ khoá điều cốt lõi (vd. chỉ `nodesExclude: [tool]`).\n"
        "- Kết quả phụ thuộc dữ liệu thì `status` dạng tập: `[COMPLETED, FALLBACK]`.\n"
        "- Chỉ khoá trường intent mà câu nhập nói rõ.\n"
        "- `judge` chỉ cho điều khó viết thành luật; kết luận LLM dao động, đọc lý do trước khi kết luận.\n"
        "- Case fail: phân biệt kỳ vọng sai, lỗi agent hay nhiễu LLM (tài liệu mục 8) trước khi sửa.")


# ----------------------------------------------------------------------------------------- page


def sidebar_progress(live: bool) -> None:
    run_id = er.active_run()
    if live and run_id is None:
        st.rerun(scope="app")  # lần chạy vừa xong
    if run_id is None:
        st.caption("Không có lần chạy nào đang chạy.")
        return
    view = er.load_run(run_id)
    total = max(view.total_turns, 1)
    st.progress(min(view.finished_turns / total, 1.0),
                text=f"{run_id}: {view.finished_turns}/{view.total_turns or '?'} lượt · ❌ {view.failed_turns}")
    if view.current:
        st.caption(f"Đang chạy {view.current['caseId']} · lượt {view.current['turn']}/{view.current['turns']}")
    st.button("⏹ Dừng", key="sidebar_stop", on_click=er.stop_run, args=(run_id,))


with st.sidebar:
    st.header("🧪 Agent Eval")
    status = backend_status(API_BASE)
    ready = bool(status) and status.get("status") == "ready"
    st.caption(f"Backend `{API_BASE}`")
    if status is None:
        st.error("Không kết nối được backend. Chạy `make agent-eval` (tự bật backend) hoặc "
                 "`.venv/bin/uvicorn src.backend.app.main:app --port 8000`.")
    else:
        st.success(f"{status.get('status')} · data `{status.get('dataMode')}` · LLM `{status.get('llmMode')}` · "
                   f"{status.get('productCount') or '?'} sản phẩm")
        if status.get("dataMode") == "fixture":
            st.warning("Backend đang ở mode `fixture`: runner vẫn chạy nhưng biên bản không phản ánh catalog thật.")
        if status.get("llmMode") not in (None, "live"):
            st.warning("LLM không ở chế độ live; runner cần key LLM thật trong .env.")
    if st.button("Kiểm tra lại backend"):
        backend_status.clear()
        destinations.clear()
        st.rerun()

    st.subheader("Tuỳ chọn chạy")
    st.number_input("Lặp mỗi case (--repeat)", 1, 10, 1, key="opt_repeat",
                    help="Mặc định 1. Chỉ tăng khi một case lúc đạt lúc không, để đo tỷ lệ.")
    st.checkbox("Kèm sweep mọi điểm đến (--sweep)", key="opt_sweep",
                help="Thêm 2 lượt cho mỗi điểm đến trong catalog (~70 lượt); chạy trước demo hoặc commit.")
    st.text_input("LangSmith project (--trace-project)", value=os.getenv("EVAL_TRACE_PROJECT", ""), key="opt_trace",
                  help="Để trống thì không gửi trace. Có tên thì mỗi lượt là trace `TC-NN#lượt <câu>`.")
    st.text_input("Model giám khảo (--judge-model)", key="opt_judge", placeholder="mặc định = model của agent")
    st.number_input("Timeout mỗi lượt (giây)", 10, 600, 90, key="opt_timeout")

    st.subheader("Lần chạy hiện tại")
    if er.active_run():
        st.fragment(run_every="3s")(sidebar_progress)(True)
    else:
        sidebar_progress(False)

st.title("Đánh giá Itinerary Agent")
st.caption(f"Dataset `{rel(DATASET)}` · luật chấm "
           "của `src/evaluation/agent/golden.py` · docs/spec/agent/golden-run.md")
run_t, history_t, new_t, guide_t = st.tabs(["▶️ Chạy", "📈 Lịch sử & so sánh", "➕ Thêm case", "📖 Hướng dẫn"])
with run_t:
    run_tab(ready)
with history_t:
    history_tab()
with new_t:
    new_case_tab(ready)
with guide_t:
    guide_tab()
