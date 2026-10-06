"""Readiness có kiểm DB (chỉ cho load balancer).

Use case (docs/plan/2026-10-05-ha-load-balancing.md §3b): 3 VM, VM #2 mất đường tới DB (sidecar kết nối hỏng). Nếu
/health/ready không kiểm DB, 1/3 lượt đăng nhập và đặt chỗ trả 5xx cho tới khi có người can thiệp.
"""
import asyncio
import json
from types import SimpleNamespace

import pytest

from src.backend.app import main
from src.backend.app.infrastructure.persistence.db_probe import DatabaseProbe


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def _probe(outcomes, clock=None, cache=5.0):
    calls = []

    def select_one(url, timeout):
        calls.append(url)
        outcome = outcomes.pop(0) if len(outcomes) > 1 else outcomes[0]
        if isinstance(outcome, Exception):
            raise outcome

    return DatabaseProbe("postgresql://x", timeout_seconds=1, cache_seconds=cache, clock=clock or Clock(),
                         select_one=select_one), calls


def test_probe_is_ok_when_select_succeeds():
    probe, calls = _probe([None])
    assert asyncio.run(probe.ok()) is True and calls == ["postgresql://x"]


def test_probe_is_not_ok_on_any_error():
    probe, _ = _probe([ConnectionRefusedError("down")])
    assert asyncio.run(probe.ok()) is False


def test_probe_caches_so_lb_probes_do_not_open_a_connection_each_time():
    clock = Clock()
    probe, calls = _probe([None], clock)

    async def go():
        await probe.ok()
        clock.t = 4.9
        await probe.ok()
        clock.t = 5.1
        await probe.ok()

    asyncio.run(go())
    assert len(calls) == 2           # lượt 2 dùng cache, lượt 3 hết hạn cache


def test_probe_recovers_after_failure():
    clock = Clock()
    probe, _ = _probe([OSError("down"), None], clock)

    async def go():
        first = await probe.ok()
        clock.t = 6
        return first, await probe.ok()

    assert asyncio.run(go()) == (False, True)


def test_concurrent_probes_share_one_check():
    probe, calls = _probe([None])

    async def go():
        return await asyncio.gather(*(probe.ok() for _ in range(20)))

    assert all(asyncio.run(go())) and len(calls) == 1


def _ready(monkeypatch, *, required: bool, probe):
    monkeypatch.setattr(main.settings, "ready_requires_db", required)
    monkeypatch.setattr(main.settings, "ready_requires_recsys", False)
    monkeypatch.setattr(main.app.state, "ready", True, raising=False)
    monkeypatch.setattr(main.app.state, "db_probe", probe, raising=False)
    response = asyncio.run(main.health_ready())
    return response.status_code, json.loads(response.body)


def test_ready_is_503_when_db_unreachable_and_required(monkeypatch):
    probe, _ = _probe([ConnectionRefusedError()])
    status, body = _ready(monkeypatch, required=True, probe=probe)
    assert (status, body["db"], body["ready"]) == (503, False, False)


def test_ready_is_200_when_db_reachable_and_required(monkeypatch):
    probe, _ = _probe([None])
    assert _ready(monkeypatch, required=True, probe=probe)[0] == 200


def test_db_is_not_probed_when_not_required(monkeypatch):
    probe, calls = _probe([ConnectionRefusedError()])
    status, body = _ready(monkeypatch, required=False, probe=probe)
    assert status == 200 and body["db"] is True and calls == []
