"""`PreloadedVectorSearch` (2026-10-12): tra vector theo id từ RAM nạp ở nền; ANN vẫn qua kho vector."""
from __future__ import annotations

import threading
from types import SimpleNamespace

import numpy as np
import pytest

from src.backend.app.application.ports import VectorHit
from src.backend.app.infrastructure.vectors.preloaded_vector_search import PreloadedVectorSearch


def meta(model="m", text="t"):
    return SimpleNamespace(model_version=model, text_hash=text)


class FakeInner:
    """Kho vector giả: ghi lại mọi lời gọi; `objects` = productId → (vector, model, textHash)."""

    def __init__(self, objects):
        self.objects = objects
        self.dimension = 2
        self.calls = []

    def vectors(self, ids):
        self.calls.append(("vectors", tuple(ids)))
        return {pid: np.asarray(self.objects[pid][0], dtype=np.float32) for pid in ids if pid in self.objects}

    def vectors_with_metadata(self, ids):
        self.calls.append(("vectors_with_metadata", tuple(ids)))
        return {pid: (np.asarray(v, dtype=np.float32), meta(m, t)) for pid, (v, m, t) in self.objects.items() if pid in ids}

    def near_vector(self, vector, allowed, limit, *, with_vectors=False):
        self.calls.append(("near_vector", with_vectors))
        return [VectorHit(pid, 0.9, np.asarray(v, dtype=np.float32) if with_vectors else None)
                for pid, (v, _, _) in list(self.objects.items())[:limit]]

    def bm25(self, query, allowed, limit, *, with_vectors=False):
        self.calls.append(("bm25", with_vectors))
        return []

    def metadata(self, ids):
        return {pid: meta(m, t) for pid, (_, m, t) in self.objects.items() if pid in ids}

    def close(self):
        self.calls.append(("close",))


OBJECTS = {"A": ([1.0, 0.0], "m", "ta"), "B": ([0.0, 1.0], "m", "tb"), "C": ([0.6, 0.8], "m", "tc")}


def loaded(objects=OBJECTS, desired=("A", "B", "C", "GHOST"), chunk_size=1000):
    inner = FakeInner(dict(objects))
    search = PreloadedVectorSearch(inner, chunk_size=chunk_size)
    search.expect(desired, inner.metadata(list(desired)))
    return search, inner


def test_before_preload_everything_goes_to_the_inner_store():
    search, inner = loaded()
    assert set(search.vectors(["A", "B"])) == {"A", "B"}
    assert search.near_vector(np.zeros(2), None, 2, with_vectors=True)[0].vector is not None
    assert inner.calls == [("vectors", ("A", "B")), ("near_vector", True)]


def test_after_preload_ids_are_served_from_ram_read_only():
    search, inner = loaded()
    report = search.preload()
    assert (report["outcome"], report["vectors"], report["complete"]) == ("done", 3, True)
    inner.calls.clear()
    got = search.vectors(["A", "C", "GHOST"])          # GHOST không có object: không hỏi kho
    assert inner.calls == [] and set(got) == {"A", "C"}
    assert got["A"].tolist() == [1.0, 0.0] and not got["A"].flags.writeable
    with pytest.raises(ValueError):
        got["A"][0] = 5.0


def test_near_vector_asks_without_vectors_and_attaches_them_from_ram():
    search, inner = loaded()
    search.preload()
    inner.calls.clear()
    hits = search.near_vector(np.zeros(2), ["A", "B"], 2, with_vectors=True)
    assert inner.calls == [("near_vector", False)]
    assert [h.product_id for h in hits] == ["A", "B"] and hits[1].vector.tolist() == [0.0, 1.0]
    assert search.near_vector(np.zeros(2), None, 1)[0].vector is None   # không xin vector thì như cũ


def test_changed_text_hash_drops_the_entry_and_the_next_preload_fetches_only_it():
    search, inner = loaded()
    search.preload()
    inner.objects["B"] = ([0.5, 0.5], "m", "tb2")       # job index ghi lại B với text mới
    search.expect(["A", "B", "C"], inner.metadata(["A", "B", "C"]))
    assert not search.snapshot.complete and "B" not in search.snapshot.table
    inner.calls.clear()
    assert search.vectors(["B"])["B"].tolist() == [0.5, 0.5] and inner.calls == [("vectors", ("B",))]
    inner.calls.clear()
    search.preload()
    assert inner.calls == [("vectors_with_metadata", ("B",))] and search.snapshot.complete


def test_metadata_mismatch_during_preload_is_not_stored():
    search, inner = loaded()
    inner.objects["C"] = ([0.6, 0.8], "m", "changed-after-load")   # đổi giữa lần nạp và lần tải vector
    report = search.preload()
    assert report["outcome"] == "partial" and "C" not in search.snapshot.table


def test_stop_halts_between_chunks():
    search, inner = loaded(chunk_size=1)
    stop = threading.Event()
    stop.set()
    assert search.preload(stop)["outcome"] == "stopped" and inner.calls == []


def test_bm25_metadata_close_and_dimension_are_delegated():
    search, inner = loaded()
    assert search.dimension == 2 and hasattr(search, "bm25")
    search.bm25("q", None, 3, with_vectors=True)
    search.close()
    assert ("bm25", True) in inner.calls and ("close",) in inner.calls
    assert set(search.metadata(["A"])) == {"A"}


def test_concurrent_reads_during_preload_are_consistent():
    objects = {f"P{i}": ([float(i), 1.0], "m", f"t{i}") for i in range(200)}
    search, _ = loaded(objects, desired=list(objects), chunk_size=10)
    errors = []

    def read():
        try:
            for _ in range(200):
                got = search.vectors(["P1", "P150"])
                assert got["P1"].tolist() == [1.0, 1.0] and got["P150"].tolist() == [150.0, 1.0]
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    readers = [threading.Thread(target=read) for _ in range(4)]
    for t in readers:
        t.start()
    search.preload()
    for t in readers:
        t.join()
    assert errors == [] and search.snapshot.complete
