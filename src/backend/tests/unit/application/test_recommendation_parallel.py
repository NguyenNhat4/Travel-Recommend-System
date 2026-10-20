"""Các lượt kho vector độc lập của gợi ý chạy song song trên pool (2026-10-12): output phải y hệt chạy tuần tự.

ANN ngắn hạn, ANN dài hạn và vector của món phổ biến gửi cùng lúc; kết quả ghép đúng thứ tự cũ (lịch sử → ngắn hạn → dài hạn
→ phổ biến), nên `_LocalSpace`, thứ tự ứng viên và cách phá hoà giữ nguyên. Không có pool thì gọi tuần tự đúng thứ tự cũ.
"""
from __future__ import annotations

import copy
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest

from src.backend.app.application.recommendation import BuildPopularity, RecommendForUser
from src.backend.app.application.recommendation.responses import ENGINE_ONLY_DIAGNOSTICS
from src.backend.tests.conftest import EVENTS, ROWS, FakeEmbedder
from src.backend.tests.unit.application.test_recommendation_explore_fill import COMBO_ITEMS, EXTRA


class CountingVectors:
    """Bọc kho vector, đếm từng loại lời gọi (an toàn khi gọi từ nhiều thread)."""

    def __init__(self, inner, fail_on_call: int | None = None):
        self.inner, self.dimension = inner, inner.dimension
        self.calls = {"near_vector": 0, "vectors": 0}
        self._lock = threading.Lock()
        self._fail_on_call = fail_on_call

    def vectors(self, ids):
        with self._lock:
            self.calls["vectors"] += 1
        return self.inner.vectors(ids)

    def near_vector(self, *a, **kw):
        with self._lock:
            self.calls["near_vector"] += 1
            n = self.calls["near_vector"]
        if self._fail_on_call is not None and n == self._fail_on_call:
            raise RuntimeError("weaviate down")
        return self.inner.near_vector(*a, **kw)


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    from datetime import datetime, timezone

    from src.backend.tests.fakes.in_memory_vector_store import InMemoryVectorStore
    from src.backend.tests.fakes.jsonl_cdp_reader import JsonlCdpReader

    d = tmp_path_factory.mktemp("parallel")
    (d / "products.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in ROWS + EXTRA), encoding="utf-8")
    (d / "combo_items.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in COMBO_ITEMS), encoding="utf-8")
    (d / "events.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in EVENTS), encoding="utf-8")
    index, vectors = InMemoryVectorStore(str(d / "products.jsonl"), FakeEmbedder(), str(d / ".embcache")).load()
    cdp = JsonlCdpReader(str(d / "events.jsonl"))
    now = datetime(2026, 9, 21, tzinfo=timezone.utc)
    pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="test-recsys-io")
    yield {"index": index, "vectors": vectors, "cdp": cdp, "now": now, "pop": BuildPopularity(index, cdp)(now=now),
           "pool": pool}
    pool.shutdown(wait=True)


def _strip(result: dict) -> dict:
    out = copy.deepcopy(result)
    for key in ENGINE_ONLY_DIAGNOSTICS:
        out.get("diagnostics", {}).pop(key, None)
    return out


def _open_trip(now):
    t = (now - timedelta(days=2)).isoformat()
    old = (now - timedelta(days=120)).isoformat()
    return [{"cdpUserId": "U", "eventName": "product_view", "productId": "A6", "timestamp": old, "eventGroupId": "OLD"},
            {"cdpUserId": "U", "eventName": "purchase", "productId": "R1", "timestamp": t, "usingDate": "2026-10-05",
             "eventGroupId": "OPEN"}]


def _ended_trip(now):
    t = (now - timedelta(days=40)).isoformat()
    return [{"cdpUserId": "U", "eventName": "purchase", "productId": "R7", "timestamp": t, "usingDate": "2026-08-20",
             "eventGroupId": "DONE"},
            {"cdpUserId": "U", "eventName": "purchase", "productId": "A6", "timestamp": t, "usingDate": "2026-08-21",
             "eventGroupId": "DONE"}]


SCENARIOS = {
    # tên: (cdp_user_id, events (None = đọc CDP), k, destination)
    "open_trip_with_explore": ("U", "open", 6, None),
    "open_trip_locked_destination": ("U", "open", 3, "Phú Quốc"),
    "ended_trip_next_trip_scoring": ("U", "ended", 4, None),
    "member_from_cdp": ("P1", None, 3, None),
    "dormant": ("P3", None, 2, None),
    "cold_start_member": ("NOBODY", None, 4, None),
    "guest": (None, None, 4, None),
}


def _run(world, executor, user, events, k, destination, vectors=None):
    now = world["now"]
    vec = vectors or CountingVectors(world["vectors"])
    rec = RecommendForUser(world["index"], vec, world["cdp"], world["pop"], executor=executor)
    batch = {"open": _open_trip(now), "ended": _ended_trip(now)}.get(events) if events else None
    return rec(user, k=k, now=now, events=batch, destination=destination), vec


@pytest.mark.parametrize("name", sorted(SCENARIOS))
def test_parallel_output_is_identical_to_sequential(world, name):
    user, events, k, destination = SCENARIOS[name]
    sequential, seq_vec = _run(world, None, user, events, k, destination)
    parallel, par_vec = _run(world, world["pool"], user, events, k, destination)
    assert _strip(parallel) == _strip(sequential)
    assert par_vec.calls == seq_vec.calls   # cùng số lượt ANN và cùng số lượt lấy vector


def test_parallel_records_per_call_timings(world):
    result, _ = _run(world, world["pool"], "U", "open", 6, None)
    stages = result["diagnostics"]["stageMs"]
    assert {"annShort", "annLong", "popularVectors", "candidates"} <= set(stages)


@pytest.mark.parametrize("parallel", [False, True])
def test_vector_store_error_in_the_second_ann_propagates(world, parallel):
    failing = CountingVectors(world["vectors"], fail_on_call=2)   # lượt ANN thứ hai (dài hạn) của khách có chuyến mở
    with pytest.raises(RuntimeError, match="weaviate down"):
        _run(world, world["pool"] if parallel else None, "U", "open", 6, None, vectors=failing)
