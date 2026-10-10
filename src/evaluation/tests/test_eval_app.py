"""Smoke test eval_app.py bằng AppTest: backend tắt, dataset là bản sao trong tmp, thư mục lần chạy trong tmp."""

import json
from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

from src.evaluation.agent import case_builder as cb  # noqa: E402

APP = Path(__file__).resolve().parents[1] / "agent" / "eval_app.py"


@pytest.fixture()
def env(tmp_path, monkeypatch):
    dataset = tmp_path / "cases.yaml"
    dataset.write_text(cb.DATASET_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setenv("AGENT_EVAL_DATASET", str(dataset))
    monkeypatch.setenv("AGENT_EVAL_RUNS_DIR", str(tmp_path / "runs"))
    monkeypatch.setenv("EVAL_API_BASE_URL", "http://127.0.0.1:9")  # không có gì lắng nghe
    return tmp_path


def _run(at: AppTest) -> AppTest:
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def _finished_run(root: Path) -> None:
    run_dir = root / "runs" / "20261005-100000"
    run_dir.mkdir(parents=True)
    (run_dir / "meta.json").write_text(json.dumps({
        "runId": run_dir.name, "pid": None, "startedAt": "2026-10-05T10:00:00", "commit": "abc1234",
        "options": {"case_ids": ["TC-01"], "repeat": 1}}), encoding="utf-8")
    events = [
        {"event": "start", "repeat": 1, "turns": 1, "cases": [{"id": "TC-01", "category": "change_date", "turns": 1}]},
        {"event": "turn_done", "caseId": "TC-01", "turn": 1, "turns": 1, "repetition": 1, "message": "Đổi ngày",
         "status": "COMPLETED", "httpStatus": 200, "latencyMs": 1200, "passed": False, "reply": "Đã xong.",
         "findings": ["status='COMPLETED', kỳ vọng một trong ['NEEDS_CLARIFICATION']",
                      "[judge] Trợ lý hỏi ngày mới: trả lời 'Đã xong.'"], "traceName": "TC-01#1 Đổi ngày"},
        {"event": "case_done", "caseId": "TC-01", "repetition": 1, "turns": 1, "turnsRun": 1, "passed": False},
        {"event": "done", "exitCode": 1, "totals": {"turns": 1, "passed": 0, "failed": 1},
         "metrics": {"groundingRate": None, "structuredOutputIntegrity": 1.0, "toolCallingAccuracy": 1.0},
         "latencyMs": {"p50": 1200, "max": 1200}, "model": "m", "reportMd": str(run_dir / "x.md")},
    ]
    (run_dir / "progress.jsonl").write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in events),
                                            encoding="utf-8")


def test_renders_without_backend_or_runs(env):
    at = _run(AppTest.from_file(str(APP), default_timeout=60))
    assert any("Không kết nối được backend" in e.value for e in at.sidebar.error)
    assert any("Chưa có lần chạy nào" in i.value for i in at.info)
    run_buttons = [b for b in at.button if "Chạy tất cả" in b.label]
    assert run_buttons and run_buttons[0].disabled


def test_failed_run_shows_rule_and_judge_findings(env):
    _finished_run(env)
    at = _run(AppTest.from_file(str(APP), default_timeout=60))
    assert any("kỳ vọng một trong" in e.value for e in at.error)
    assert any("Trợ lý hỏi ngày mới" in w.value for w in at.warning)
    assert any("❌ TC-01" in e.label for e in at.expander)


def test_new_case_form_builds_yaml_and_saves(env):
    at = _run(AppTest.from_file(str(APP), default_timeout=60))
    at.text_input(key="nc_category").set_value("thu_nghiem")
    at.multiselect(key="nc_fr").set_value(["FR-AGT-01"])
    uid = at.session_state["nc_turns"][0]
    at.text_area(key=f"nc_{uid}_message").set_value("Đi Huế 2 ngày từ {today+5}")
    at.checkbox(key=f"nc_{uid}_status_on").check()
    _run(at)
    at.multiselect(key=f"nc_{uid}_status").set_value(["NEEDS_CLARIFICATION"])
    _run(at)
    preview = [c.value for c in at.code if "- id: TC-" in c.value][0]
    assert "status: [NEEDS_CLARIFICATION]" in preview and "Đi Huế 2 ngày từ {today+5}" in preview

    next(b for b in at.button if "Lưu vào dataset" in b.label).click()
    _run(at)
    saved = Path(env / "cases.yaml").read_text(encoding="utf-8")
    assert "category: thu_nghiem" in saved
    assert any("Đã nối" in s.value for s in at.success)


@pytest.mark.parametrize("case_id", ["TC-01", "TC-02", "TC-03", "TC-04", "TC-10", "TC-11"])
def test_loading_a_case_as_template_reproduces_its_turns(env, case_id):
    at = _run(AppTest.from_file(str(APP), default_timeout=60))
    at.selectbox(key="nc_template").set_value(case_id)
    next(b for b in at.button if b.label == "Nạp mẫu").click()
    _run(at)
    preview = cb.parse_case_block([c.value for c in at.code if "- id: TC-" in c.value][0])
    original = cb.dataset_raw_case(case_id, env / "cases.yaml")
    assert preview["id"] != case_id
    assert [(t["message"], t.get("expect")) for t in preview["turns"]] == \
        [(t["message"], t.get("expect") or {}) for t in original["turns"]]
