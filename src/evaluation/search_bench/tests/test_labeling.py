from __future__ import annotations

import csv
import sys
import tempfile
import unittest
from pathlib import Path


MODULE_ROOT = Path(__file__).resolve().parents[1]
if str(MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(MODULE_ROOT))

from labeling import (  # noqa: E402
    JsonlLabelStore,
    LabelEvent,
    SearchCase,
    consensus,
    latest_by_annotator,
    latest_events_csv,
    new_label_event,
)


class LabelingTest(unittest.TestCase):
    def setUp(self) -> None:
        self.case = SearchCase("c0001", "khách sạn ở Huế", "dest_type", "", "", "p1", "hotel:Huế")

    def test_validation_requires_reason_and_edit(self) -> None:
        with self.assertRaisesRegex(ValueError, "rejection reason"):
            new_label_event(self.case, annotator="A", verdict="REJECT")
        with self.assertRaisesRegex(ValueError, "Edited query"):
            new_label_event(self.case, annotator="A", verdict="NEEDS_EDIT")
        event = new_label_event(
            self.case,
            annotator="A",
            verdict="NEEDS_EDIT",
            edited_query="khách sạn tại Huế",
        )
        self.assertEqual(event.edited_query, "khách sạn tại Huế")

    def test_latest_is_per_case_and_annotator(self) -> None:
        base = dict(
            case_id="c0001",
            verdict="KEEP",
            rejection_reason="",
            edited_query="",
            notes="",
            case_slice="dest_type",
            original_query="khách sạn ở Huế",
        )
        events = [
            LabelEvent(event_id="1", annotator="A", updated_at="2026-09-23T01:00:00+00:00", **base),
            LabelEvent(event_id="2", annotator="A", updated_at="2026-09-23T02:00:00+00:00", **{**base, "verdict": "REJECT", "rejection_reason": "duplicate"}),
            LabelEvent(event_id="3", annotator="B", updated_at="2026-09-23T01:30:00+00:00", **base),
        ]
        latest = latest_by_annotator(events)
        self.assertEqual(latest[("c0001", "a")].verdict, "REJECT")
        self.assertEqual(latest[("c0001", "b")].verdict, "KEEP")
        self.assertEqual(consensus(latest.values()), "CONFLICT")

    def test_jsonl_round_trip_and_csv(self) -> None:
        event = new_label_event(self.case, annotator="A", verdict="KEEP", notes="ổn")
        with tempfile.TemporaryDirectory() as directory:
            store = JsonlLabelStore(Path(directory) / "labels.jsonl")
            store.append(event)
            self.assertEqual(store.load_events(), [event])
        rows = list(csv.DictReader(latest_events_csv([event]).splitlines()))
        self.assertEqual(rows[0]["case_id"], "c0001")
        self.assertEqual(rows[0]["notes"], "ổn")


if __name__ == "__main__":
    unittest.main()
