"""Hợp đồng chung cho mọi engine (spec Part 5 P5.1).

Filter mà engine không biểu diễn được → raise UnsupportedFilter, KHÔNG tự lọc phía client để giả vờ hỗ trợ (§1.7.5).
Tính năng chưa cài ở fast-track (lexical, facet, backup) → raise UnsupportedFeature.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Protocol, runtime_checkable

import numpy as np

Hit = tuple[str, float]                     # (id, score) — score càng cao càng giống


@dataclass(frozen=True)
class Capabilities:
    exact_search: bool
    filter_ops: frozenset[str]              # eq in range all any not or geo id_in
    geo: Literal["native", "emulated", "none"]
    count_exact: bool
    facet: Literal["exact", "approx", "none"]
    lexical: Literal["bm25", "ts_rank", "sparse_bm25", "none"]
    vector_dtypes: frozenset[str]           # f32 f16 int8 binary
    async_client: bool
    backup: Literal["native", "tool", "none"]
    acorn: bool = False
    notes: tuple[str, ...] = ()

    def to_json(self) -> dict[str, Any]:
        return {"exact_search": self.exact_search, "filter_ops": sorted(self.filter_ops), "geo": self.geo,
                "count_exact": self.count_exact, "facet": self.facet, "lexical": self.lexical,
                "vector_dtypes": sorted(self.vector_dtypes), "async_client": self.async_client, "backup": self.backup,
                "acorn": self.acorn, "notes": list(self.notes)}


class UnsupportedFilter(Exception):
    def __init__(self, op: str, detail: str = ""):
        super().__init__(f"filter không hỗ trợ: {op}" + (f" ({detail})" if detail else ""))
        self.op = op


class UnsupportedFeature(Exception):
    def __init__(self, feature: str, detail: str = ""):
        super().__init__(f"tính năng không hỗ trợ: {feature}" + (f" ({detail})" if detail else ""))
        self.feature = feature


class QueryTimeout(Exception):
    """Query vượt timeout (perf.timeout_ms) — tính vào phân vị với giá trị = timeout."""


ALL_FILTER_OPS = frozenset({"eq", "in", "range", "all", "any", "not", "and", "or", "geo", "id_in"})
PAYLOAD_FIELDS = ("variant", "taxonomy", "destination", "available", "amenity_ids", "unit_price", "star_rating", "lat", "lon")


@runtime_checkable
class VectorStore(Protocol):
    name: str

    def connect(self) -> None: ...
    def close(self) -> None: ...
    def server_version(self) -> str: ...
    def client_version(self) -> str: ...
    def capabilities(self) -> Capabilities: ...
    def translate(self, filt: dict | None) -> Any: ...            # thuần, không I/O — để unit test
    def create(self, index: Any) -> None: ...                      # drop + tạo bảng/collection + payload index
    def upsert(self, ids: list[str], vecs: np.ndarray, payloads: list[dict]) -> None: ...
    def finalize(self) -> float: ...                               # build/đợi index xong; trả số giây
    def search(self, q: np.ndarray, filt: dict | None, k: int, qp: dict) -> list[Hit]: ...
    def lexical_search(self, text: str, filt: dict | None, k: int) -> list[Hit]: ...
    def count(self, filt: dict | None) -> tuple[int, bool]: ...    # (số, exact?)
    def facet(self, filt: dict | None, field: str) -> tuple[dict[str, int], bool]: ...
    def set_available(self, id: str, value: bool) -> None: ...
    def delete_ids(self, ids: list[str]) -> None: ...
    def delete_all(self) -> None: ...
    def backup(self, dest: Path) -> None: ...
    def restore(self, src: Path) -> None: ...


@dataclass
class StoreOptions:
    """Tuỳ chọn runtime không thuộc engine config (truyền được qua spawn)."""
    timeout_ms: float | None = None         # statement/request timeout mỗi query
    extra: dict[str, Any] = field(default_factory=dict)


class BaseStore:
    """Mặc định cho các phần fast-track chưa cài."""
    name = "base"

    def lexical_search(self, text: str, filt: dict | None, k: int) -> list[Hit]:
        raise UnsupportedFeature("lexical", "Part 6b — chưa cài ở fast-track")

    def facet(self, filt: dict | None, field: str) -> tuple[dict[str, int], bool]:
        raise UnsupportedFeature("facet", "chưa cài ở fast-track")

    def backup(self, dest: Path) -> None:
        raise UnsupportedFeature("backup", "G7 — chưa cài ở fast-track")

    def restore(self, src: Path) -> None:
        raise UnsupportedFeature("restore", "G7 — chưa cài ở fast-track")

    def supports_query_config(self, qp: dict) -> tuple[bool, str]:
        return True, ""

    def export_state(self) -> dict:
        """Trạng thái dựng một lần ở process cha (vd. thống kê cho mode auto) để worker spawn nạp lại."""
        return {}

    def import_state(self, state: dict) -> None:
        pass

    def plan_uses_index(self, q: np.ndarray, filt: dict | None, k: int, qp: dict) -> bool | None:
        return None
