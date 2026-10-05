"""Điều kiện HA nhiều bản sao: readiness phụ thuộc RecSys và dịch vụ dùng chung không được trỏ loopback.

Use case (docs/plan/2026-10-05-ha-load-balancing.md §3b): 2 VM, VM B có Weaviate rỗng. Khi RecSys tắt, /search trả
trang rỗng với HTTP 200, nên nếu /health/ready vẫn 200 thì LB đẩy ~50% lượt tìm "Vinpearl Phú Quốc" vào VM B.
"""
import asyncio
import json
from types import SimpleNamespace

import pytest

from src.backend.app import main
from src.backend.app.core.config import Settings, shared_backend_violations


def _ready_payload(monkeypatch, *, required: bool, index) -> tuple[int, dict]:
    monkeypatch.setattr(main.settings, "ready_requires_recsys", required)
    monkeypatch.setattr(main.app.state, "ready", True, raising=False)
    monkeypatch.setattr(main.app.state, "index", index, raising=False)
    response = asyncio.run(main.health_ready())
    return response.status_code, json.loads(response.body)


def test_ready_is_503_when_recsys_missing_and_required(monkeypatch):
    status, body = _ready_payload(monkeypatch, required=True, index=None)
    assert (status, body["ready"], body["recsys"]) == (503, False, False)


def test_ready_is_200_when_recsys_loaded_and_required(monkeypatch):
    status, body = _ready_payload(monkeypatch, required=True, index=SimpleNamespace(units=[1]))
    assert (status, body["ready"]) == (200, True)


def test_single_vm_default_keeps_ready_without_recsys(monkeypatch):
    status, _ = _ready_payload(monkeypatch, required=False, index=None)
    assert status == 200


def _settings(**kw) -> Settings:
    base = dict(require_shared_backends=True, weaviate_url="http://10.148.0.9:8080",
                auth_redis_url="redis://:p@10.0.0.5:6379/1", itinerary_redis_url="redis://:p@10.0.0.5:6379/2",
                database_url="postgresql://u:p@db.vota.internal:5432/vota",
                cdp_database_url="postgresql://c:p@db.vota.internal:5432/vota")
    return Settings(_env_file=None, **{**base, **kw})


def test_shared_backends_pass_with_private_ips():
    assert shared_backend_violations(_settings()) == []


@pytest.mark.parametrize("field,value,name", [
    ("weaviate_url", "http://localhost:8080", "WEAVIATE_URL"),
    ("auth_redis_url", "redis://:p@127.0.0.1:6379/1", "AUTH_REDIS_URL"),
    ("itinerary_redis_url", "", "ITINERARY_REDIS_URL"),
    ("database_url", "postgresql://u:p@127.0.0.1:15432/vota", "DATABASE_URL"),      # tunnel SSH không có trên VM của MIG
    ("cdp_database_url", "postgresql://c:p@localhost:5432/vota", "CDP_DATABASE_URL"),
])
def test_loopback_or_blank_shared_backend_is_rejected(field, value, name):
    assert shared_backend_violations(_settings(**{field: value})) == [name]


def test_guard_is_off_by_default():
    assert shared_backend_violations(Settings(_env_file=None, weaviate_url="http://localhost:8080")) == []


def test_lifespan_refuses_to_start_on_loopback_weaviate(monkeypatch):
    monkeypatch.setattr(main, "get_settings", lambda: _settings(weaviate_url="http://localhost:8080"))

    async def go():
        async with main.lifespan(main.app):
            pass

    with pytest.raises(RuntimeError, match="WEAVIATE_URL"):
        asyncio.run(go())
