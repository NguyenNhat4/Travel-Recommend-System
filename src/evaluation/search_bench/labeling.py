"""Draft-query review model and append-only label stores."""
from __future__ import annotations

import csv
import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Protocol
from uuid import uuid4


VERDICTS = ("KEEP", "REJECT", "NEEDS_EDIT")
REJECTION_REASONS = (
    "fabricated_entity",
    "duplicate",
    "unnatural",
    "wrong_slice",
    "bad_grounding",
    "invalid_filter",
    "other",
)
LABEL_COLUMNS = (
    "event_id",
    "case_id",
    "annotator",
    "verdict",
    "rejection_reason",
    "edited_query",
    "notes",
    "updated_at",
    "case_slice",
    "original_query",
)


@dataclass(frozen=True)
class SearchCase:
    case_id: str
    query: str
    slice: str
    filter_json: str
    expected_no_result: str
    source_refs: str
    review_note: str


@dataclass(frozen=True)
class LabelEvent:
    event_id: str
    case_id: str
    annotator: str
    verdict: str
    rejection_reason: str
    edited_query: str
    notes: str
    updated_at: str
    case_slice: str
    original_query: str

    def row(self) -> list[str]:
        data = asdict(self)
        return [data[column] for column in LABEL_COLUMNS]


class LabelStore(Protocol):
    def load_events(self) -> list[LabelEvent]: ...

    def append(self, event: LabelEvent) -> None: ...


def load_cases(path: Path) -> list[SearchCase]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        required = {field.name for field in SearchCase.__dataclass_fields__.values()}
        missing = required.difference(reader.fieldnames or ())
        if missing:
            raise ValueError(f"Draft file is missing columns: {sorted(missing)}")
        cases = [SearchCase(**{name: row[name] for name in required}) for row in reader]
    if not cases:
        raise ValueError("Draft file contains no cases")
    return cases


def new_label_event(
    case: SearchCase,
    *,
    annotator: str,
    verdict: str,
    rejection_reason: str = "",
    edited_query: str = "",
    notes: str = "",
) -> LabelEvent:
    annotator = annotator.strip()
    verdict = verdict.strip().upper()
    rejection_reason = rejection_reason.strip()
    edited_query = edited_query.strip()
    notes = notes.strip()
    if not annotator:
        raise ValueError("Annotator is required")
    if verdict not in VERDICTS:
        raise ValueError(f"Unsupported verdict: {verdict}")
    if verdict == "REJECT" and rejection_reason not in REJECTION_REASONS:
        raise ValueError("A valid rejection reason is required for REJECT")
    if verdict != "REJECT" and rejection_reason:
        raise ValueError("Rejection reason is only valid for REJECT")
    if verdict == "NEEDS_EDIT" and not edited_query:
        raise ValueError("Edited query is required for NEEDS_EDIT")
    if verdict != "NEEDS_EDIT" and edited_query:
        raise ValueError("Edited query is only valid for NEEDS_EDIT")
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return LabelEvent(
        event_id=str(uuid4()),
        case_id=case.case_id,
        annotator=annotator,
        verdict=verdict,
        rejection_reason=rejection_reason,
        edited_query=edited_query,
        notes=notes,
        updated_at=now,
        case_slice=case.slice,
        original_query=case.query,
    )


def latest_by_annotator(events: Iterable[LabelEvent]) -> dict[tuple[str, str], LabelEvent]:
    latest: dict[tuple[str, str], LabelEvent] = {}
    for event in events:
        if event.event_id.startswith("__") or not event.case_id or not event.annotator:
            continue
        key = (event.case_id, event.annotator.casefold())
        current = latest.get(key)
        if current is None or (event.updated_at, event.event_id) > (current.updated_at, current.event_id):
            latest[key] = event
    return latest


def consensus(latest: Iterable[LabelEvent]) -> str:
    verdicts = [event.verdict for event in latest]
    if not verdicts:
        return "UNLABELED"
    if len(set(verdicts)) > 1:
        return "CONFLICT"
    return verdicts[0]


def latest_events_csv(events: Iterable[LabelEvent]) -> str:
    from io import StringIO

    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=LABEL_COLUMNS)
    writer.writeheader()
    for event in sorted(events, key=lambda item: (item.case_id, item.annotator.casefold())):
        writer.writerow(asdict(event))
    return output.getvalue()


class JsonlLabelStore:
    """Append-only shared store for the lightweight Streamlit deployment."""

    def __init__(self, path: Path):
        self.path = path

    def load_events(self) -> list[LabelEvent]:
        if not self.path.exists():
            return []
        events: list[LabelEvent] = []
        with self.path.open(encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    events.append(LabelEvent(**json.loads(line)))
        return events

    def append(self, event: LabelEvent) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(asdict(event), ensure_ascii=False) + "\n"
        flags = os.O_APPEND | os.O_CREAT | os.O_WRONLY
        descriptor = os.open(self.path, flags, 0o600)
        try:
            os.write(descriptor, line.encode("utf-8"))
        finally:
            os.close(descriptor)
