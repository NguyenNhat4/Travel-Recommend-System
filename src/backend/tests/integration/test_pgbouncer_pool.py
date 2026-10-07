"""Đo connection pooling với pgbouncer thật (transaction mode, cấu hình ở infra/terraform/environments/staging-ha).

Use case (docs/plan/2026-10-05-ha-load-balancing.md §3b): 20:00 khuyến mãi, 250 request đồng thời mỗi request mở một
connection tới Postgres có max_connections=100 thì quá nửa bị `too many clients`. Qua pgbouncer sidecar thì không lỗi và
số connection thật bị chặn ở kích thước pool.

Chạy (cần Postgres + pgbouncer, xem docs/plan/...):
  RUN_PGBOUNCER_INTEGRATION=1 DIRECT_DATABASE_URL=postgresql://vota_app_login:vota@localhost:55432/vota \
  POOLED_DATABASE_URL=postgresql://vota_app_login:vota@localhost:56432/vota \
  SEED_DATABASE_URL=postgresql://postgres:postgres@localhost:55432/vota pytest src/backend/tests/integration/test_pgbouncer_pool.py
"""
import asyncio
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import psycopg
import pytest

from src.backend.app.infrastructure.persistence.postgres_booking import PostgresBookingStore

DIRECT = os.getenv("DIRECT_DATABASE_URL", "postgresql://vota_app_login:vota@localhost:55432/vota")
POOLED = os.getenv("POOLED_DATABASE_URL", "postgresql://vota_app_login:vota@localhost:56432/vota")
SEED = os.getenv("SEED_DATABASE_URL", "postgresql://postgres:postgres@localhost:55432/vota")
CLIENTS = 250
POOL_SIZE_WITH_RESERVE = 12   # default_pool_size 10 + reserve_pool_size 2 trong pgbouncer.ini

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_PGBOUNCER_INTEGRATION") != "1",
    reason="set RUN_PGBOUNCER_INTEGRATION=1 with Postgres and pgbouncer running",
)


def _burst(url: str) -> tuple[int, int, int]:
    """CLIENTS request đồng thời, mỗi request một connection giữ 0,2 giây. Trả (lỗi, thành công, đỉnh connection thật)."""
    peak, stop = 0, threading.Event()

    def watch():
        nonlocal peak
        with psycopg.connect(SEED, autocommit=True) as mon:
            while not stop.is_set():
                n = mon.execute("SELECT count(*) FROM pg_stat_activity WHERE usename = 'vota_app_login'").fetchone()[0]
                peak = max(peak, n)
                time.sleep(0.03)

    def one(_):
        try:
            with psycopg.connect(url, connect_timeout=20) as conn:
                conn.execute("SELECT pg_sleep(0.2)")
            return True
        except psycopg.Error:
            return False

    watcher = threading.Thread(target=watch)
    watcher.start()
    with ThreadPoolExecutor(CLIENTS) as pool:
        results = list(pool.map(one, range(CLIENTS)))
    stop.set()
    watcher.join()
    return results.count(False), results.count(True), peak


def test_direct_burst_exhausts_max_connections():
    with psycopg.connect(SEED) as conn:
        max_conn = int(conn.execute("SHOW max_connections").fetchone()[0])
    if max_conn >= CLIENTS:
        pytest.skip(f"max_connections={max_conn} đủ cho {CLIENTS} client; hạ xuống để thấy lỗi")
    failed, ok, peak = _burst(DIRECT)
    print(f"\nTRỰC TIẾP: max_connections={max_conn} lỗi={failed}/{CLIENTS} thành công={ok} đỉnh connection={peak}")
    assert failed > 0


def test_pooled_burst_has_no_failures_and_bounded_server_connections():
    failed, ok, peak = _burst(POOLED)
    print(f"\nQUA POOLER: lỗi={failed}/{CLIENTS} thành công={ok} đỉnh connection thật={peak}")
    assert failed == 0 and ok == CLIENTS
    assert peak <= POOL_SIZE_WITH_RESERVE


def test_session_advisory_lock_is_not_exclusive_through_the_pooler():
    """Lý do tồn tại của LEADER_LOCK_DATABASE_URL: qua transaction pooling cả hai bản sao đều tưởng mình là leader."""
    async def go(url):
        a, b = PostgresBookingStore(url), PostgresBookingStore(url)
        async with a.reconcile_leader() as first:
            async with b.reconcile_leader() as second:
                return first, second

    assert asyncio.run(go(DIRECT)) == (True, False)       # trực tiếp: loại trừ đúng
    assert asyncio.run(go(POOLED)) == (True, True)        # qua pooler: hỏng thầm lặng


def test_leader_lock_uses_the_direct_dsn_even_when_the_app_uses_the_pooler():
    async def go():
        a = PostgresBookingStore(POOLED, leader_lock_database_url=DIRECT)
        b = PostgresBookingStore(POOLED, leader_lock_database_url=DIRECT)
        async with a.reconcile_leader() as first:
            async with b.reconcile_leader() as second:
                return first, second

    assert asyncio.run(go()) == (True, False)
