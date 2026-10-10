"""Chặn test chạy nhầm vào dịch vụ thật (staging, cloud). Dùng bởi conftest.py.

Lý do: `.env` của dev thường trỏ DB staging qua tunnel (127.0.0.1:15432), Weaviate Cloud và khóa Cohere/OpenAI thật.
Test dựng app đọc `.env` đó sẽ ghi/đọc/gọi dịch vụ thật mà không báo gì.
"""
from __future__ import annotations

import os
from urllib.parse import urlparse

#: Biến kết nối mà test có thể đọc. Chỉ xét biến có trong môi trường shell (conftest đã tắt đọc `.env`).
CONNECTION_VARS = (
    "DATABASE_URL", "CDP_DATABASE_URL", "SEED_DATABASE_URL", "INSIDER_DATABASE_URL",
    "AUTH_REDIS_URL", "ITINERARY_REDIS_URL", "WEAVIATE_URL", "CDP_BASE_URL", "INSIDER_BASE_URL",
    "ITINERARY_SERVICE_BASE_URL",
)
LOOPBACK = {"localhost", "127.0.0.1", "::1"}
#: Cổng tunnel SSH tới Postgres staging (primary, replica): loopback nhưng là máy từ xa.
STAGING_TUNNEL_PORTS = {15432, 15433}
OVERRIDE = "ALLOW_REMOTE_TEST_DEPS"


def remote_dependency_violations(environ: dict[str, str] | None = None) -> list[str]:
    env = os.environ if environ is None else environ
    if env.get(OVERRIDE) == "1":
        return []
    bad = []
    for name in CONNECTION_VARS:
        value = env.get(name, "").strip()
        if not value:
            continue
        parsed = urlparse(value if "://" in value else f"http://{value}")
        host = (parsed.hostname or "").lower()
        if host not in LOOPBACK or parsed.port in STAGING_TUNNEL_PORTS:
            bad.append(f"{name} → {host or value}{':' + str(parsed.port) if parsed.port else ''}")
    return bad
