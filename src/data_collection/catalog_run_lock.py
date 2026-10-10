"""Khoá "chỉ một lượt cào chạy" dùng chung cho mọi nơi chạy job (VM cron, chạy tay).

Khoá tệp (`fresh_catalog.lock` trong thư mục state) chỉ có hiệu lực trong MỘT máy/container. Job chạy theo lịch trên
Lượt chạy tay ở máy khác trong lúc cron chạy không thấy khoá tệp của cron, nên
cần thêm khoá ở nơi chung: advisory lock của Postgres, giữ bằng một kết nối riêng suốt lượt chạy.

- `pg_try_advisory_lock` không chờ: lượt đến sau bỏ qua thay vì xếp hàng và cào lặp lại.
- Khoá gắn với kết nối: lượt chết (container bị giết, mạng đứt) thì Postgres tự nhả, không cần dọn.
- Failover DB làm mất kết nối nên mất khoá. Khi đó hai lượt có thể chồng nhau, nhưng ghi vào DB vẫn tuần tự nhờ
  `pg_advisory_xact_lock(7791024)` trong từng giao dịch nạp (fresh_catalog_db.py), nên không hỏng dữ liệu.
- Kết nối thẳng tới Postgres (db.vota.internal:5432), KHÔNG qua pgbouncer chế độ transaction: khoá mức session
  gắn với kết nối máy chủ.
"""
from __future__ import annotations

import contextlib
import os
from pathlib import Path

KEY = 7791025  # khác 7791024 (khoá giao dịch của loader), để hai khoá không chặn nhau


def lock_file(state_dir: Path) -> Path:
    """Khoá tệp của lượt chạy (monitor, job và pipeline_runtime dùng chung đúng một đường dẫn). CATALOG_LOCK_DIR đặt nó ra
    ổ cục bộ của container (vd. /tmp) khi state_dir nằm trên GCS/NFS, nơi `flock` không đáng tin."""
    return Path(os.environ.get("CATALOG_LOCK_DIR") or state_dir) / "fresh_catalog.lock"


class CatalogRunLock:
    def __init__(self, url: str, *, connect=None):
        self._url = url
        self._connect = connect
        self._conn = None

    def acquire(self) -> bool:
        connect = self._connect
        if connect is None:
            import psycopg

            connect = psycopg.connect
        conn = connect(self._url, autocommit=True, connect_timeout=10,
                       keepalives=1, keepalives_idle=30, keepalives_interval=10, keepalives_count=3)
        try:
            got = conn.execute("SELECT pg_try_advisory_lock(%s)", (KEY,)).fetchone()[0]
        except BaseException:
            conn.close()
            raise
        if not got:
            conn.close()
            return False
        self._conn = conn
        return True

    def release(self) -> None:
        conn, self._conn = self._conn, None
        if conn is not None:
            with contextlib.suppress(Exception):
                conn.execute("SELECT pg_advisory_unlock(%s)", (KEY,))
            with contextlib.suppress(Exception):
                conn.close()


def acquire(stack: contextlib.ExitStack, url: str) -> bool:
    """Giữ khoá cho tới khi `stack` đóng. False = đang có lượt khác chạy ở máy khác."""
    lock = CatalogRunLock(url)
    if not lock.acquire():
        return False
    stack.callback(lock.release)
    return True
