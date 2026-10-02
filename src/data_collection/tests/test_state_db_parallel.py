"""Nhiều site (tiến trình crawl.py) mở cùng file trạng thái SQLite của lượt trong cùng một giây."""
import multiprocessing
import tempfile
import unittest
from pathlib import Path

from collectors.common import Paths, StateDB


def open_state(root: str, source: str, start, errors) -> None:
    start.wait()
    try:
        state = StateDB(Paths(Path(root)).ensure())
        state.add_many(source, [(f"https://example.test/{source}/{i}", i) for i in range(20)])
        state.close()
    except Exception as exc:  # báo về tiến trình test
        errors.put(f"{source}: {type(exc).__name__}: {exc}")


class StateDbParallelTests(unittest.TestCase):
    def test_sites_starting_together_share_the_run_state_file(self):
        ctx = multiprocessing.get_context("fork")
        for _ in range(5):  # lỗi phụ thuộc thời điểm: lặp để bắt được
            with tempfile.TemporaryDirectory() as tmp:
                start, errors = ctx.Event(), ctx.Queue()
                procs = [ctx.Process(target=open_state, args=(tmp, f"s{i}", start, errors)) for i in range(8)]
                for p in procs:
                    p.start()
                start.set()
                for p in procs:
                    p.join(60)
                found = []
                while not errors.empty():
                    found.append(errors.get())
                self.assertEqual(found, [])
                state = StateDB(Paths(Path(tmp)).ensure())
                self.assertEqual(sum(c.get("pending", 0) for c in state.counts().values()), 160)
                state.close()


if __name__ == "__main__":
    unittest.main()
