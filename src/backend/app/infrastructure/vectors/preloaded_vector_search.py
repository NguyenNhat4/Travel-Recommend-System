"""`VectorSearchPort` bọc `WeaviateVectorSearch`: tra vector **theo id** từ RAM, nạp ở nền (chốt 2026-10-12).

Truy vấn tương đồng (`near_vector`, `bm25`) vẫn đi qua index ANN của Weaviate (NFR-PERF-03). Chỉ phần tra vector theo id
(`vectors()`, và vector đính kèm hit của `near_vector`) lấy từ bảng trong RAM: bỏ được các lượt `fetch_objects` và phần
payload vector của mỗi lượt ANN, vốn đi qua mạng tới Weaviate Cloud khác vùng.

Vòng đời:
- `expect(desired_ids, stored)`: `WeaviateVectorStore.load()` gọi ở mỗi lần nạp, chỉ chạy cục bộ. `stored` là metadata
  Weaviate vừa trả; mục nào trong bảng có `modelVersion`/`textHash` khác thì bị bỏ ngay (dùng Weaviate cho tới lần nạp sau).
- `preload(stop)`: `RecsysRefresher` chạy ở nền sau mỗi lần nạp; chỉ lấy phần còn thiếu, theo khối, dừng được giữa hai khối.

Chưa nạp xong thì mọi lời gọi chuyển thẳng xuống Weaviate như trước. Bảng là một snapshot bất biến, thay nguyên khối
dưới khoá ghi; người đọc lấy snapshot một lần mỗi lời gọi, không cần khoá. Khoảng 4.000 × 384 float32 ≈ 6 MB mỗi tiến trình.
"""
from __future__ import annotations

import threading
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, replace
from time import perf_counter

import numpy as np

from src.backend.app.application.ports import LexicalHit, VectorHit

_Key = tuple[str, str]   # (modelVersion, textHash)


@dataclass(frozen=True)
class _Snapshot:
    table: Mapping[str, tuple[np.ndarray, _Key]]   # productId → (vector chỉ đọc, khoá metadata lúc nạp)
    expected: Mapping[str, _Key]                   # productId có object trong Weaviate ở lần `load()` gần nhất
    absent: frozenset[str]                         # search unit không có object nào (Weaviate cũng không trả)
    complete: bool                                 # bảng phủ hết `expected`


class PreloadedVectorSearch:
    def __init__(self, inner, *, chunk_size: int = 1000):
        self.inner = inner
        self.dimension = inner.dimension
        self._chunk = chunk_size
        self._state = _Snapshot({}, {}, frozenset(), False)
        self._write = threading.Lock()
        self._loading = threading.Lock()

    # --- truy vấn -------------------------------------------------------------------------------------------------

    def vectors(self, product_ids: Sequence[str]) -> dict[str, np.ndarray]:
        state = self._state
        out: dict[str, np.ndarray] = {}
        pending: list[str] = []
        for pid in dict.fromkeys(product_ids):
            entry = state.table.get(pid)
            if entry is not None:
                out[pid] = entry[0]
            elif pid not in state.absent:   # id không có object: Weaviate cũng không trả, khỏi hỏi
                pending.append(pid)
        if pending:
            out.update(self.inner.vectors(pending))
        return out

    def near_vector(self, vector: np.ndarray, allowed: Sequence[str] | None, limit: int,
                    *, with_vectors: bool = False) -> list[VectorHit]:
        state = self._state
        if not with_vectors or not state.complete:
            return self.inner.near_vector(vector, allowed, limit, with_vectors=with_vectors)
        hits = self.inner.near_vector(vector, allowed, limit, with_vectors=False)
        missing = [h.product_id for h in hits if h.product_id not in state.table]
        extra = self.inner.vectors(missing) if missing else {}
        out = []
        for h in hits:
            entry = state.table.get(h.product_id)
            out.append(replace(h, vector=entry[0] if entry is not None else extra.get(h.product_id)))
        return out

    def bm25(self, query: str, allowed: Sequence[str] | None, limit: int,
             *, with_vectors: bool = False) -> list[LexicalHit]:
        """Khai tường minh để `build_recsys` vẫn thấy kênh BM25 (`hasattr(vector_search, "bm25")`)."""
        return self.inner.bm25(query, allowed, limit, with_vectors=with_vectors)

    def metadata(self, product_ids: Sequence[str]):
        return self.inner.metadata(product_ids)

    def close(self) -> None:
        self.inner.close()

    # --- vòng đời -------------------------------------------------------------------------------------------------

    @property
    def snapshot(self) -> _Snapshot:
        return self._state

    def expect(self, desired_ids: Collection[str], stored: Mapping[str, object]) -> None:
        """Đặt tập vector cần có theo metadata Weaviate của lần nạp này; bỏ mục đã đổi `modelVersion`/`textHash`."""
        desired = set(desired_ids)
        expected = {pid: (str(meta.model_version), str(meta.text_hash)) for pid, meta in stored.items() if pid in desired}
        absent = frozenset(desired - expected.keys())
        with self._write:
            table = {pid: entry for pid, entry in self._state.table.items() if expected.get(pid) == entry[1]}
            self._state = _Snapshot(table, expected, absent, len(table) == len(expected))

    def preload(self, stop: threading.Event | None = None) -> dict:
        """Lấy vector còn thiếu theo khối `chunk_size`; chỉ giữ mục có metadata khớp `expected` lúc ghi. Một lượt mỗi lúc."""
        if not self._loading.acquire(blocking=False):
            return {"outcome": "busy"}
        started = perf_counter()
        outcome, fetched = "done", 0
        try:
            todo = [pid for pid in self._state.expected if pid not in self._state.table]
            for start in range(0, len(todo), self._chunk):
                if stop is not None and stop.is_set():
                    outcome = "stopped"
                    break
                got = self.inner.vectors_with_metadata(todo[start:start + self._chunk])
                fetched += len(got)
                with self._write:
                    current = self._state
                    table = dict(current.table)
                    for pid, (vector, meta) in got.items():
                        key = (str(meta.model_version), str(meta.text_hash))
                        if current.expected.get(pid) == key:
                            array = np.array(vector, dtype=np.float32)
                            array.setflags(write=False)
                            table[pid] = (array, key)
                    self._state = _Snapshot(table, current.expected, current.absent,
                                            len(table) == len(current.expected))
            state = self._state
            if outcome == "done" and not state.complete:
                outcome = "partial"
            return {"outcome": outcome, "vectors": len(state.table), "fetched": fetched, "complete": state.complete,
                    "seconds": round(perf_counter() - started, 3)}
        finally:
            self._loading.release()
