#!/usr/bin/env python3
"""Áp migration SQL lên database `vota` đang có dữ liệu.

`db/init/*.sql` chỉ chạy lúc initdb trên volume rỗng, nên nó không giúp gì cho máy dev đã seed hay
cho Postgres cloud dùng làm staging. Script này là đường thứ hai; chi tiết ở db/migrations/README.md.

Cần quyền tạo bảng trong schema `app` → chạy bằng SEED_DATABASE_URL (superuser), không phải
DATABASE_URL của backend. Đây là job hạ tầng, không phải code app (AGENTS.md §6.1).

    python db/migrations/run.py --status
    python db/migrations/run.py
    python db/migrations/run.py --database-url postgresql://... --dry-run
"""
from __future__ import annotations

import argparse
import getpass
import hashlib
import os
import re
import sys
from pathlib import Path

try:
    import psycopg
except ModuleNotFoundError:
    sys.exit(
        "Thiếu psycopg. Dùng venv của backend:\n"
        "    src/backend/.venv/bin/python db/migrations/run.py ...\n"
        "hoặc: pip install 'psycopg[binary]>=3.2,<4'"
    )

MIGRATIONS_DIR = Path(__file__).resolve().parent
NAME_RE = re.compile(r"^(\d{4})_[a-z0-9_]+\.sql$")

TRACKING_TABLE = """
CREATE SCHEMA IF NOT EXISTS app;
CREATE TABLE IF NOT EXISTS app.schema_migrations (
    version    text PRIMARY KEY,
    checksum   text NOT NULL,
    applied_at timestamptz NOT NULL DEFAULT now(),
    applied_by text NOT NULL
);
"""


class MigrationError(RuntimeError):
    pass


def discover() -> list[tuple[str, Path]]:
    """Trả [(version, path)] đã sắp xếp. Tên sai quy ước là lỗi, không phải cảnh báo im lặng."""
    found: dict[str, Path] = {}
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        match = NAME_RE.match(path.name)
        if not match:
            raise MigrationError(
                f"{path.name}: tên phải theo dạng NNNN_slug.sql (4 chữ số, chữ thường, gạch dưới)"
            )
        version = match.group(1)
        if version in found:
            raise MigrationError(f"trùng số thứ tự {version}: {found[version].name} và {path.name}")
        # Runner bọc mỗi file trong một transaction. File tự BEGIN/COMMIT sẽ đóng transaction đó
        # giữa chừng và psycopg báo "savepoint _pg3_1 does not exist" — lỗi khó đoán ra nguyên nhân.
        body = re.sub(r"--[^\n]*", "", path.read_text(encoding="utf-8")).upper()
        for keyword in ("BEGIN;", "COMMIT;", "ROLLBACK;"):
            if keyword in body:
                raise MigrationError(
                    f"{path.name}: bỏ {keyword[:-1]} — run.py đã tự bọc transaction cho từng migration"
                )
        found[version] = path
    return sorted(found.items())


def checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def applied_map(conn) -> dict[str, str]:
    with conn.cursor() as cur:
        cur.execute("SELECT version, checksum FROM app.schema_migrations")
        return dict(cur.fetchall())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--database-url",
        default=os.environ.get("SEED_DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/vota"),
        help="mặc định: $SEED_DATABASE_URL, rồi tới Postgres Docker local",
    )
    parser.add_argument("--status", action="store_true", help="chỉ in trạng thái, không áp gì")
    parser.add_argument("--dry-run", action="store_true", help="in migration sẽ chạy rồi thoát")
    args = parser.parse_args()

    try:
        migrations = discover()
    except MigrationError as exc:
        print(f"LỖI: {exc}", file=sys.stderr)
        return 2
    if not migrations:
        print("Không có migration nào trong db/migrations/.")
        return 0

    try:
        conn = psycopg.connect(args.database_url)
    except psycopg.OperationalError as exc:
        print(f"LỖI: không kết nối được database.\n{exc}", file=sys.stderr)
        print("Postgres đã chạy chưa? `docker compose up -d --wait postgres`", file=sys.stderr)
        return 2

    with conn:
        with conn.cursor() as cur:
            cur.execute(TRACKING_TABLE)
        conn.commit()

        applied = applied_map(conn)

        # File đã áp mà nội dung đổi = lịch sử không còn tin được. Dừng, bắt thêm migration mới.
        drifted = [
            (version, path)
            for version, path in migrations
            if version in applied and applied[version] != checksum(path)
        ]
        if drifted:
            for version, path in drifted:
                print(f"LỖI: {path.name} đã áp nhưng nội dung đã đổi.", file=sys.stderr)
            print("Không sửa file đã áp — thêm migration mới thay thế.", file=sys.stderr)
            return 3

        pending = [(version, path) for version, path in migrations if version not in applied]

        if args.status or args.dry_run:
            for version, path in migrations:
                mark = "đã áp " if version in applied else "CHỜ   "
                print(f"  {mark} {path.name}")
            print(f"\n{len(applied)} đã áp, {len(pending)} chờ.")
            return 0

        if not pending:
            print(f"Database đã cập nhật ({len(applied)} migration).")
            return 0

        who = f"{getpass.getuser()}@{os.uname().nodename}"
        for version, path in pending:
            print(f"→ áp {path.name} ...", end=" ", flush=True)
            try:
                # Mỗi migration là một transaction: hỏng thì không để lại schema dở dang.
                with conn.transaction():
                    with conn.cursor() as cur:
                        cur.execute(path.read_text(encoding="utf-8"))
                        cur.execute(
                            "INSERT INTO app.schema_migrations (version, checksum, applied_by) VALUES (%s, %s, %s)",
                            (version, checksum(path), who),
                        )
            except psycopg.Error as exc:
                print("HỎNG")
                print(f"\nLỖI trong {path.name}:\n{exc}", file=sys.stderr)
                print("Đã rollback; không migration nào sau đó được chạy.", file=sys.stderr)
                return 1
            print("xong")

        print(f"\nÁp {len(pending)} migration.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
