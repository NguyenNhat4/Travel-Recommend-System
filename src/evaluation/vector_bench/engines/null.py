"""Engine giả "null" — trả ngay, không I/O. `vb perf null` dùng để đo overhead của harness (P99 < perf.harness_max_p99_ms)."""
from __future__ import annotations

import numpy as np

from .base import ALL_FILTER_OPS, BaseStore, Capabilities, Hit, StoreOptions


class NullStore(BaseStore):
    name = "null"

    def __init__(self, cfg=None, dim: int = 0, opts: StoreOptions | None = None):
        self.dim = dim

    def connect(self) -> None:
        pass

    def close(self) -> None:
        pass

    def server_version(self) -> str:
        return "null"

    def client_version(self) -> str:
        return "null"

    def capabilities(self) -> Capabilities:
        return Capabilities(exact_search=True, filter_ops=ALL_FILTER_OPS, geo="native", count_exact=True, facet="none",
                            lexical="none", vector_dtypes=frozenset({"f16"}), async_client=False, backup="none")

    def translate(self, filt):
        return filt

    def create(self, index) -> None:
        pass

    def upsert(self, ids, vecs, payloads) -> None:
        pass

    def finalize(self) -> float:
        return 0.0

    def search(self, q: np.ndarray, filt, k: int, qp: dict) -> list[Hit]:
        return []

    def ping(self) -> None:
        pass

    def count(self, filt):
        return 0, True

    def set_available(self, id, value) -> None:
        pass

    def delete_ids(self, ids) -> None:
        pass

    def delete_all(self) -> None:
        pass
