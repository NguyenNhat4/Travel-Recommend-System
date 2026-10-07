"""Readiness khi mất DB: một VM mất DB thì bị loại, mọi VM mất DB thì giữ lại.

Use case (docs/plan/2026-10-07-ha-vung-crawler-rolling.md §3, use case 5): 3 VM sau LB, lúc 14:00 một khách tìm
"Vinpearl Phú Quốc" (không cần DB) và một khách khác đăng nhập (cần DB).
- Primary Postgres chết ~3 phút trong lúc failover. Trước khi sửa, `READY_REQUIRES_DB` làm cả 3 VM trả 503 ở
  /health/ready, LB không còn backend sẵn sàng nên trang tìm kiếm cũng lỗi dù catalog đã nằm trong bộ nhớ/Weaviate.
- Chỉ pgbouncer của VM #2 chết: VM #2 vẫn phải bị loại, nếu không 1/3 lượt đăng nhập trả lỗi.
Test chạy trên Redis giả (sorted set trong bộ nhớ), không cần Redis thật. Chưa kiểm: hành vi LB thật khi mọi backend
unhealthy (tài liệu GCP nói trả 502 failed_to_pick_backend) vì chưa apply lên GCP.
"""
import asyncio
import json

import pytest

from src.backend.app import main
from src.backend.app.infrastructure.persistence.db_peer_registry import DbPeerRegistry, KEY


class FakeRedis:
    def __init__(self):
        self.sets: dict[str, dict[str, float]] = {}
        self.down = False

    def _guard(self):
        if self.down:
            raise ConnectionError("redis down")

    async def zadd(self, name, mapping):
        self._guard()
        self.sets.setdefault(name, {}).update(mapping)
        return len(mapping)

    async def zrem(self, name, *values):
        self._guard()
        return sum(self.sets.get(name, {}).pop(v, None) is not None for v in values)

    async def zscore(self, name, value):
        self._guard()
        return self.sets.get(name, {}).get(value)

    async def zremrangebyscore(self, name, min, max):
        self._guard()
        data = self.sets.get(name, {})
        for k in [k for k, v in data.items() if min <= v <= max]:
            del data[k]

    async def zcount(self, name, min, max):
        self._guard()
        hi = float("inf") if max == "+inf" else max
        return sum(1 for v in self.sets.get(name, {}).values() if min <= v <= hi)


class Probe:
    def __init__(self, up: bool):
        self.up = up

    async def ok(self):
        return self.up


class Vm:
    """Một VM: probe DB riêng + sổ chung Redis, gọi đúng hàm health_ready của app."""

    def __init__(self, redis, name, clock, up=True):
        self.probe = Probe(up)
        self.peers = DbPeerRegistry(redis, name, ttl_seconds=30, clock=clock)

    def ready(self, monkeypatch):
        monkeypatch.setattr(main.settings, "ready_requires_db", True)
        monkeypatch.setattr(main.settings, "ready_requires_recsys", False)
        monkeypatch.setattr(main.app.state, "ready", True, raising=False)
        monkeypatch.setattr(main.app.state, "db_probe", self.probe, raising=False)
        monkeypatch.setattr(main.app.state, "db_peers", self.peers, raising=False)
        monkeypatch.setattr(main.app.state, "last_readiness", None, raising=False)
        response = asyncio.run(main.health_ready())
        return response.status_code, json.loads(response.body)


@pytest.fixture
def fleet():
    redis, now = FakeRedis(), [1000.0]
    clock = lambda: now[0]  # noqa: E731
    vms = [Vm(redis, f"vm{i}", clock) for i in (1, 2, 3)]
    return redis, now, vms


def _round(vms, monkeypatch):
    return [vm.ready(monkeypatch)[0] for vm in vms]


def test_all_vms_ready_when_db_is_up(fleet, monkeypatch):
    _, _, vms = fleet
    assert _round(vms, monkeypatch) == [200, 200, 200]


def test_one_vm_losing_db_is_evicted(fleet, monkeypatch):
    _, _, vms = fleet
    _round(vms, monkeypatch)
    vms[1].probe.up = False
    status, body = vms[1].ready(monkeypatch)
    assert (status, body["db"], body["mode"]) == (503, False, "normal")
    assert _round([vms[0], vms[2]], monkeypatch) == [200, 200]


def test_every_vm_losing_db_stays_ready_in_outage_mode(fleet, monkeypatch):
    _, _, vms = fleet
    _round(vms, monkeypatch)
    for vm in vms:
        vm.probe.up = False
    results = [vm.ready(monkeypatch) for vm in vms]
    # VM đầu có thể còn thấy VM sau chưa kịp xoá dấu và bị loại một vòng; vòng thứ hai mọi VM đều được giữ lại.
    assert sum(r[0] == 200 for r in results) >= 1
    again = [vm.ready(monkeypatch) for vm in vms]
    assert [r[0] for r in again] == [200, 200, 200]
    assert all(r[1]["mode"] == "db_outage" and r[1]["db"] is False for r in again)


def test_never_all_unready_while_failures_arrive_one_by_one(fleet, monkeypatch):
    _, _, vms = fleet
    _round(vms, monkeypatch)
    for vm in vms:
        vm.probe.up = False
        statuses = [v.ready(monkeypatch)[0] for v in vms]
        assert 200 in statuses


def test_vm_recovers_and_leaves_outage_mode(fleet, monkeypatch):
    _, _, vms = fleet
    _round(vms, monkeypatch)
    for vm in vms:
        vm.probe.up = False
    _round(vms, monkeypatch)
    _round(vms, monkeypatch)
    for vm in vms:
        vm.probe.up = True
    statuses = [vm.ready(monkeypatch) for vm in vms]
    assert [s[0] for s in statuses] == [200, 200, 200] and all(s[1]["mode"] == "normal" for s in statuses)


def test_stale_marks_expire_so_a_dead_vm_is_not_counted_as_a_healthy_peer(fleet, monkeypatch):
    _, now, vms = fleet
    _round(vms, monkeypatch)                      # cả 3 có dấu lúc t=1000
    now[0] += 31                                  # sau ttl 30s, vm2 và vm3 chết (không còn gọi ready)
    vms[0].probe.up = False
    status, body = vms[0].ready(monkeypatch)
    assert (status, body["mode"]) == (200, "db_outage")


def test_unknown_peer_state_keeps_ready_rather_than_evicting_everyone(fleet, monkeypatch):
    redis, _, vms = fleet
    _round(vms, monkeypatch)
    redis.down = True
    vms[0].probe.up = False
    status, body = vms[0].ready(monkeypatch)
    assert (status, body["mode"]) == (200, "db_outage")


def test_without_registry_behaviour_is_unchanged_503(monkeypatch):
    vm = Vm(FakeRedis(), "solo", lambda: 0.0, up=False)
    monkeypatch.setattr(main.settings, "ready_requires_db", True)
    monkeypatch.setattr(main.settings, "ready_requires_recsys", False)
    monkeypatch.setattr(main.app.state, "ready", True, raising=False)
    monkeypatch.setattr(main.app.state, "db_probe", vm.probe, raising=False)
    monkeypatch.setattr(main.app.state, "db_peers", None, raising=False)
    assert asyncio.run(main.health_ready()).status_code == 503


def test_registry_peers_ok_excludes_self():
    redis = FakeRedis()
    a = DbPeerRegistry(redis, "a", clock=lambda: 10.0)
    b = DbPeerRegistry(redis, "b", clock=lambda: 10.0)

    async def go():
        await a.mark_ok(); await b.mark_ok()
        return await a.peers_ok(), KEY in redis.sets

    assert asyncio.run(go()) == (1, True)
