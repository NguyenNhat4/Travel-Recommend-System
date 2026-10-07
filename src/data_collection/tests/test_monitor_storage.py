"""Tab Dung lượng của monitor: đo đĩa và thư mục, dọn lượt cào cũ (người dùng yêu cầu 06/10)."""
from __future__ import annotations

import fcntl
import json
import tempfile
import unittest
from pathlib import Path

import monitor

RUNS = ["full-20261003T190007Z-1", "full-20261004T190007Z-2", "full-20261005T190007Z-3", "daily-20261006T010000Z-4"]


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.state, self.runs = root / "state", root / "fresh_runs"
        self.state.mkdir()
        (self.state / "trip_targets.json").write_text("{}", encoding="utf-8")
        for index, name in enumerate(RUNS):
            path = self.runs / name / "raw"
            path.mkdir(parents=True)
            (path / "page.json").write_bytes(b"x" * (1000 * (index + 1)))
        self.monitor = monitor.FreshMonitor(self.state, self.runs)

    def tearDown(self):
        self.tmp.cleanup()

    def test_reports_disk_dirs_and_runs_newest_first(self):
        data = self.monitor.storage()
        self.assertGreater(data["disk"]["total"], 0)
        self.assertEqual(data["path"], self.tmp.name)
        self.assertEqual({d["name"] for d in data["dirs"]}, {"state", "fresh_runs"})
        fresh = next(d for d in data["dirs"] if d["name"] == "fresh_runs")
        self.assertEqual(fresh["bytes"], 10_000)
        self.assertEqual([r["runId"] for r in data["runs"]],
                         ["daily-20261006T010000Z-4", "full-20261005T190007Z-3", "full-20261004T190007Z-2",
                          "full-20261003T190007Z-1"])
        self.assertFalse(any(r["running"] for r in data["runs"]))

    def test_cleanup_keeps_the_newest_runs(self):
        out = self.monitor.storage_cleanup(2)
        self.assertEqual(sorted(out["removed"]), ["full-20261003T190007Z-1", "full-20261004T190007Z-2"])
        self.assertEqual(sorted(p.name for p in self.runs.iterdir()), ["daily-20261006T010000Z-4", "full-20261005T190007Z-3"])
        self.assertTrue((self.state / "trip_targets.json").exists())  # state không bị đụng

    def test_running_run_is_never_deleted(self):
        running = "full-20261003T190007Z-1"
        (self.state / "running.json").write_text(json.dumps({"runId": running}), encoding="utf-8")
        with open(self.state / "fresh_catalog.lock", "a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.assertTrue(next(r for r in self.monitor.storage()["runs"] if r["runId"] == running)["running"])
            out = self.monitor.storage_cleanup(1)
        self.assertNotIn(running, out["removed"])
        self.assertTrue((self.runs / running).exists())

    def test_invalid_keep_is_rejected(self):
        for bad in (0, -1, 101, "2", True, None):
            with self.assertRaises(ValueError):
                self.monitor.storage_cleanup(bad)
        self.assertEqual(len(list(self.runs.iterdir())), 4)


if __name__ == "__main__":
    unittest.main()
