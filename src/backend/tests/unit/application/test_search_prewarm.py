"""Prewarm cache vector truy vấn: khử trùng theo khoá chuẩn hoá, bỏ câu đã có, pacing theo câu/phút, dừng giữa hai lô."""
import re
import threading
from pathlib import Path

from src.backend.app.application.search.prewarm import PrewarmReport, prewarm, read_query_file

FROZEN = Path(__file__).resolve().parents[3] / "data" / "search_prewarm_queries.txt"


class _Search:
    def query_text(self, q):
        return " ".join(q.split()).lower()


class _Emb:
    def __init__(self):
        self.seen = set()
        self.calls = []

    def embed_queries(self, texts):
        new = [t for t in texts if t not in self.seen]
        self.seen.update(new)
        self.calls.append(len(texts))
        return len(new)


def test_prewarm_dedupes_batches_paces_and_skips_cached():
    emb, sleeps = _Emb(), []
    queries = [f"câu {i}" for i in range(190)] + ["CÂU 1", "câu  2", "", "  "]
    r = prewarm(_Search(), emb, queries, batch=96, inputs_per_minute=2000, sleep=sleeps.append)
    assert isinstance(r, PrewarmReport) and (r.queries, r.unique, r.embedded, r.skipped, r.batches) == (192, 190, 190, 0, 2)
    assert emb.calls == [96, 94] and sleeps == [60.0 * 96 / 2000] and not r.stopped and r.error is None
    again = prewarm(_Search(), emb, queries, batch=96, inputs_per_minute=2000, sleep=sleeps.append)
    assert (again.embedded, again.skipped, again.batches) == (0, 190, 0) and len(sleeps) == 1
    assert set(r.as_dict()) == {"queries", "unique", "embedded", "skipped", "batches", "seconds", "stopped", "error"}


def test_prewarm_stops_between_batches():
    emb, stop = _Emb(), threading.Event()
    r = prewarm(_Search(), emb, [f"q{i}" for i in range(300)], batch=96, inputs_per_minute=0, stop=stop,
                sleep=lambda s: None) if False else None
    # stop được bật trong lúc ngủ sau lô đầu → lô hai không chạy
    r = prewarm(_Search(), emb, [f"q{i}" for i in range(300)], batch=96, inputs_per_minute=2000, stop=stop,
                sleep=lambda s: stop.set())
    assert r.stopped and r.embedded == 96 and emb.calls == [96]


def test_prewarm_without_batch_api_reports_error_instead_of_raising():
    r = prewarm(_Search(), object(), ["a"])
    assert r.embedded == 0 and r.error and "embed_queries" in r.error


def test_read_query_file_skips_comments_and_blank_lines(tmp_path):
    p = tmp_path / "q.txt"
    p.write_text("# header\n\n  câu một  \n#x\ncâu hai\n", encoding="utf-8")
    assert read_query_file(p) == ["câu một", "câu hai"] and read_query_file(tmp_path / "missing.txt") == []


def test_frozen_prewarm_list_is_well_formed():
    lines = FROZEN.read_text(encoding="utf-8").splitlines()
    m = re.match(r"^# gold_v\d+ [0-9a-f]{64} \d{4}-\d{2}-\d{2} — (\d+) câu ", lines[0])   # sinh lại mỗi khi gold đổi tag
    assert m, lines[0]
    n = int(m.group(1))
    queries = read_query_file(FROZEN)
    assert len(queries) == n and len(set(queries)) == n and all(q == " ".join(q.split()) for q in queries)
