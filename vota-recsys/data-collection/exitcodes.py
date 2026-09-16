"""The single exit-code table for every command.

Shell wrappers and the Wednesday fallback decision branch on these numbers, so
they live in exactly one place. In particular: a fetch run that finished with
per-item failures exits OK, because spec section 8 treats item failures as the
expected case ("Lỗi cấp item: ... đi tiếp"). Only a run that could not proceed
at all is non-zero.
"""

from __future__ import annotations

OK = 0
"""Completed. May include per-item failures (spec section 8)."""

UNEXPECTED = 1
"""Unhandled exception. A bug, not a condition."""

USAGE = 2
"""Bad arguments, unknown source, mutually exclusive flags."""

CONFIG_OR_DB = 3
"""config.yaml invalid, DATABASE_URL unreachable, migration missing, lock held.
Also: quote_contexts.anchor_date not pinned."""

BLOCKED = 4
"""Anti-bot block detected, or the source is latched in source_state.

This is the code the fallback branches on:

    python -m cli fetch --source booking
    if ($LASTEXITCODE -eq 4) { python -m cli fetch --source amadeus }

Never retry past this. Spec section 1: "Nếu bị chặn → không tìm cách vượt
anti-bot, chuyển sang fallback."
"""

ROBOTS_UNAVAILABLE = 5
"""robots.txt could not be fetched and robots.on_unavailable = abort.
We do not assume allow."""

BUDGET = 6
"""A configured call/page budget was exhausted before the work finished."""

GATE_FAILED = 7
"""A quality gate said no: report --strict DoD check, sanity-check band,
seed catalogue precondition, truncate guard."""

INTERRUPTED = 130
"""Ctrl-C. The run row is marked failed with interrupted=true so a half
finished crawl is never mistaken for a complete one."""

NAMES = {
    OK: "ok",
    UNEXPECTED: "unexpected-error",
    USAGE: "usage-error",
    CONFIG_OR_DB: "config-or-db-error",
    BLOCKED: "blocked-by-anti-bot",
    ROBOTS_UNAVAILABLE: "robots-unavailable",
    BUDGET: "budget-exhausted",
    GATE_FAILED: "gate-failed",
    INTERRUPTED: "interrupted",
}


def name(code: int) -> str:
    return NAMES.get(code, f"unknown({code})")
