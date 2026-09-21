"""Report generation helper.

TODO(student): implement report rendering using MetricsReport data
and the template in reports/lab_report_template.md.
"""

from __future__ import annotations

from pathlib import Path

from .metrics import MetricsReport


def render_report(metrics: MetricsReport) -> str:
    """Render a complete lab report from metrics data.

    TODO(student): Generate a report that includes:
    1. Metrics summary table (total scenarios, success rate, retries)
    2. Per-scenario results table
    3. Architecture explanation (your graph design, state schema, reducers)
    4. Failure analysis (at least two failure modes you considered)
    5. Improvement plan

    Use reports/lab_report_template.md as your guide.

    Return: formatted markdown string
    """
    def pct(value: float) -> str:
        return f"{value:.1%}"

    rows = []
    for item in metrics.scenario_metrics:
        rows.append(
            "| {id} | {expected} | {actual} | {success} | {retries} |".format(
                id=item.scenario_id,
                expected=item.expected_route,
                actual=item.actual_route or "-",
                success="PASS" if item.success else "FAIL",
                retries=item.retry_count,
            )
        )
    scenario_table = "\n".join(rows) or "| - | - | - | - | - |"
    failed = [item for item in metrics.scenario_metrics if not item.success]
    resume_status = "PASS" if metrics.resume_success else "Not demonstrated"
    failure_note = (
        "All recorded scenarios passed."
        if not failed
        else "Failed scenarios: " + ", ".join(item.scenario_id for item in failed) + "."
    )

    return f"""# Day 08 Lab Report

## 1. Team / student

- Name: Nguyen Minh Nhat
- Repo/commit: local working tree
- Date: 2026-08-25

## 2. Architecture

The workflow is a LangGraph `StateGraph` with a single entry path:
`START -> intake -> classify`. Classification then branches to `converse` for
chit-chat and refusals, `tool` for product lookup, `clarify` when trip details
are missing, or `dead_letter` on error. Tool results pass through `evaluate`
and reach `compose`, which builds the itinerary with fixed rules; transient
failures go through bounded `retry` back to `tool`, while exhausted retries go
to `dead_letter`. Every branch ends at `finalize -> END`.

## 3. State schema

| Field | Reducer | Why |
|---|---|---|
| `messages` | append | Keep conversational trace entries. |
| `tool_results` | append | Preserve every tool attempt for evaluation and audit. |
| `errors` | append | Preserve retry and failure history. |
| `events` | append | Record every visited node and outcome. |
| `route`, `attempt`, `evaluation_result` | overwrite | Store the current routing state. |
| `final_answer`, `pending_question` | overwrite | Store the current decision or user-facing result. |

## 4. Scenario results

| Scenario | Expected route | Actual route | Success | Retries |
|---|---|---|---:|---:|
{scenario_table}

### Summary

| Metric | Value |
|---|---:|
| Total scenarios | {metrics.total_scenarios} |
| Success rate | {pct(metrics.success_rate)} |
| Average nodes visited | {metrics.avg_nodes_visited:.2f} |
| Total retries | {metrics.total_retries} |
| Resume success | {resume_status} |

## 5. Failure analysis

1. Retry or tool failure: a tool result containing `ERROR` becomes
   `needs_retry`. The retry node increments `attempt`; once `attempt >=
   max_attempts`, the graph routes to `dead_letter`, preventing an infinite loop.
2. Missing information: vague requests do not receive an invented answer;
   `clarify` creates a pending question and then finalizes the audit trail.

{failure_note}

## 6. Persistence / recovery evidence

The scenario run uses a per-scenario `thread_id` in the LangGraph config. The
default lab configuration uses the in-memory checkpointer, which supports
thread-scoped state during one process. Crash-resume and durable SQLite
evidence were not part of this Phase 4 run.

## 7. Extension work

The graph retains the bounded retry/dead-letter path from the lab.

## 8. Improvement plan

First, add a SQLite checkpointer run with state-history output and a regression
test for restart recovery. Next, replace the mock tool with authenticated,
observable integrations and add latency/error metrics per node. Finally, add a
state-history UI for inspecting workflow execution.
"""


def write_report(metrics: MetricsReport, output_path: str | Path) -> None:
    """Write the rendered report to a file."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_report(metrics), encoding="utf-8")
