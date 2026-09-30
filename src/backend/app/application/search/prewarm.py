"""Nạp sẵn cache vector truy vấn (prewarm) — chạy nền sau lần nạp catalog đầu tiên, không chặn startup.

Nguồn câu: file câu gold đóng băng dưới `src/backend/data/` (Docker chỉ COPY `src/backend`) và head query của
`app.search_logs` (port `SearchLogReader`). Mỗi câu đi qua `SearchProducts.query_text` (chuẩn hoá + gộp khoảng trắng) để
khoá cache trùng với lúc request thật; câu đã có trong cache thì bỏ qua. Pacing theo số câu / phút để không đụng trần
Cohere (`inputs_per_minute`); `stop` (threading.Event) để shutdown cắt ngang giữa hai lô.
"""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Iterable


@dataclass
class PrewarmReport:
    queries: int          # số câu đầu vào (kể cả trùng)
    unique: int           # số khoá sau chuẩn hoá + khử trùng
    embedded: int         # số câu vừa gọi Cohere
    skipped: int          # đã có trong cache
    batches: int
    seconds: float
    stopped: bool = False
    error: str | None = None

    def as_dict(self) -> dict:
        return asdict(self)


def read_query_file(path: Path | str) -> list[str]:
    """Mỗi dòng một câu; dòng trống và dòng bắt đầu bằng '#' bỏ qua."""
    p = Path(path)
    if not p.exists():
        return []
    return [line.strip() for line in p.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")]


def prewarm(search: Any, embedder: Any, queries: Iterable[str], *, batch: int = 96, inputs_per_minute: int = 2000,
            stop: Any = None, sleep: Callable[[float], None] = time.sleep) -> PrewarmReport:
    started = time.monotonic()
    raw = [q for q in queries if q and q.strip()]
    texts = list(dict.fromkeys(search.query_text(q) for q in raw))
    embed_queries = getattr(embedder, "embed_queries", None)
    if embed_queries is None:
        return PrewarmReport(len(raw), len(texts), 0, 0, 0, round(time.monotonic() - started, 1),
                             error="embedder không có embed_queries (SEARCH_EMBED_CACHE tắt?)")
    embedded = batches = 0
    stopped = False
    step = max(1, batch)
    for i in range(0, len(texts), step):
        if stop is not None and stop.is_set():
            stopped = True
            break
        n = int(embed_queries(texts[i : i + step]))
        if n:
            embedded += n
            batches += 1
            if inputs_per_minute and i + step < len(texts):
                sleep(60.0 * n / inputs_per_minute)
    return PrewarmReport(len(raw), len(texts), embedded, len(texts) - embedded if not stopped else max(0, len(texts) - embedded),
                         batches, round(time.monotonic() - started, 1), stopped=stopped)
