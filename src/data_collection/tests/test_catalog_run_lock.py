"""Khoá một-lượt-chạy ở mức DB cho job cào.

Use case (docs/plan/2026-10-07-ha-vung-crawler-rolling.md §4, use case 4): cron tick mỗi 15 phút; lượt
full lúc 02:00 chạy 3 giờ. Lúc 02:15 một người chạy tay `fresh-run` trên máy khác. Khoá tệp của cron
không thấy lượt này, nên nếu chỉ có khoá tệp cả hai cùng cào Trip/Booking với IP đó: gấp đôi
lượt gọi, nguy cơ bị chặn, và cùng nạp DB. Khoá DB làm lượt chạy tay 02:15 thoát ngay với `catalog.lock.busy scope=database`.
Test chạy trên Postgres THẬT khi có CATALOG_TEST_DATABASE_URL; còn lại dùng kết nối giả.
"""
from __future__ import annotations

import contextlib
import os
import unittest
from unittest.mock import Mock

import catalog_run_lock
from catalog_run_lock import CatalogRunLock


def fake_connect(result):
    conn = Mock()
    conn.execute.return_value.fetchone.return_value = (result,)
    return Mock(return_value=conn), conn


class RunLockUnit(unittest.TestCase):
    def test_acquired_lock_is_held_until_release(self):
        connect, conn = fake_connect(True)
        lock = CatalogRunLock("postgresql://x", connect=connect)
        self.assertTrue(lock.acquire())
        conn.close.assert_not_called()
        lock.release()
        executed = [call.args[0] for call in conn.execute.call_args_list]
        self.assertEqual(executed, ["SELECT pg_try_advisory_lock(%s)", "SELECT pg_advisory_unlock(%s)"])
        conn.close.assert_called_once()

    def test_busy_lock_returns_false_and_closes_the_connection(self):
        connect, conn = fake_connect(False)
        self.assertFalse(CatalogRunLock("postgresql://x", connect=connect).acquire())
        conn.close.assert_called_once()

    def test_connection_error_propagates_instead_of_running_without_a_lock(self):
        connect = Mock(side_effect=OSError("db down"))
        with self.assertRaises(OSError):
            CatalogRunLock("postgresql://x", connect=connect).acquire()

    def test_release_is_idempotent_and_safe_without_acquire(self):
        lock = CatalogRunLock("postgresql://x", connect=fake_connect(True)[0])
        lock.release()
        lock.acquire()
        lock.release()
        lock.release()

    def test_key_differs_from_the_loader_transaction_lock(self):
        self.assertNotEqual(catalog_run_lock.KEY, 7791024)

    def test_stack_releases_on_exit(self):
        connect, conn = fake_connect(True)
        original = catalog_run_lock.CatalogRunLock
        catalog_run_lock.CatalogRunLock = lambda url: original(url, connect=connect)
        try:
            with contextlib.ExitStack() as stack:
                self.assertTrue(catalog_run_lock.acquire(stack, "postgresql://x"))
                conn.close.assert_not_called()
            conn.close.assert_called_once()
        finally:
            catalog_run_lock.CatalogRunLock = original


@unittest.skipUnless(os.environ.get("CATALOG_TEST_DATABASE_URL"), "cần CATALOG_TEST_DATABASE_URL (Postgres thật)")
class RunLockPostgres(unittest.TestCase):
    def test_second_holder_is_refused_until_the_first_releases_or_dies(self):
        url = os.environ["CATALOG_TEST_DATABASE_URL"]
        first, second = CatalogRunLock(url), CatalogRunLock(url)
        self.assertTrue(first.acquire())
        self.assertFalse(second.acquire())
        first._conn.close()  # container bị giết: kết nối đứt, Postgres tự nhả khoá
        first._conn = None
        self.assertTrue(second.acquire())
        second.release()


if __name__ == "__main__":
    unittest.main()
