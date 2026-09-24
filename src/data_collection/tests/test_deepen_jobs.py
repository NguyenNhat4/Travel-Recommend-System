import contextlib
import io
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

import batch
import deepen_jobs as dj
from collectors.common import Paths, StateDB


def make_old_job(root: Path, city: str, done: int, pending: int) -> Path:
    spec = dj.city_spec(city, "2026-10-15", 100)
    folder = root / batch.job_id(spec)
    paths = Paths(folder).ensure()
    (folder / "job.json").write_text(json.dumps(spec), encoding="utf-8")
    state = StateDB(paths)
    urls = [f"https://www.booking.com/hotel/vn/h{i}.vi.html" for i in range(done + pending)]
    state.add_many("booking_hotels", [(u, i) for i, u in enumerate(urls)])
    for u in urls[:done]:
        state.mark("booking_hotels", u, "done")
    state.mark_discovered("booking_hotels", "search2:Hanoi:100:2026-10-15", done + pending)
    state.close()
    return folder


def counts(folder: Path) -> dict:
    with sqlite3.connect(folder / "state" / "crawl_state.sqlite") as c:
        return dict(c.execute("SELECT status, COUNT(*) FROM items GROUP BY status"))


class DeepenTests(unittest.TestCase):
    def test_new_job_reuses_finished_pages_and_keeps_pending_ones(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old = make_old_job(root, "Hà Nội", done=6, pending=2)
            rows = dj.plan(root, "Hà Nội", "2026-10-15", 100, 200)
            self.assertEqual([r["action"] for r in rows], ["clone"])
            self.assertEqual(dj.clone_state(rows[0], 100), 6)
            new = rows[0]["newDir"]
            self.assertNotEqual(new, old)
            self.assertEqual(counts(new), {"skipped": 6, "pending": 2})  # 6 trang đã cào không bị cào lại
            self.assertEqual(counts(old), {"done": 6, "pending": 2})  # job cũ giữ nguyên
            new_spec = json.loads((new / "job.json").read_text())
            self.assertEqual(new_spec["args"][new_spec["args"].index("--per-destination") + 1], "200")
            self.assertEqual(new_spec, dj.city_spec("Hà Nội", "2026-10-15", 200))  # đúng spec mà batch.py sẽ sinh ra
            note = sqlite3.connect(new / "state" / "crawl_state.sqlite").execute(
                "SELECT last_error FROM items WHERE status='skipped' LIMIT 1").fetchone()[0]
            self.assertIn(old.name, note)

    def test_never_overwrites_an_existing_deeper_job_and_skips_missing_or_running(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_old_job(root, "Hà Nội", done=3, pending=0)
            first = dj.plan(root, "Hà Nội", "2026-10-15", 100, 200)[0]
            dj.clone_state(first, 100)
            again = dj.plan(root, "Hà Nội", "2026-10-15", 100, 200)[0]
            self.assertIn("đã có", again["action"])
            missing = dj.plan(root, "Đà Nẵng", "2026-10-15", 100, 200)[0]
            self.assertIn("chưa có job", missing["action"])

    def test_dry_run_creates_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_old_job(root, "Hà Nội", done=2, pending=0)
            before = sorted(p.name for p in root.iterdir())
            with contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(dj.main(["--root", str(root), "--cities", "Hà Nội"]), 0)
            self.assertIn("xem trước", out.getvalue())
            self.assertEqual(before, sorted(p.name for p in root.iterdir()))


if __name__ == "__main__":
    unittest.main()
