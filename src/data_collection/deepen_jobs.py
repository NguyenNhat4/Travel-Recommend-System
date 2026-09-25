#!/usr/bin/env python3
"""Nâng số khách sạn Booking của các thành phố đã cào lên mức cao hơn, không cào lại trang đã có.

Job batch được đặt tên theo tham số (gồm --per-destination), nên đổi 100 → 200 tạo job mới và cào lại 100 khách sạn đầu.
Công cụ này tạo sẵn thư mục job mới với hàng đợi (SQLite) sao chép từ job cũ: URL đã xong được đánh dấu `skipped`
(kèm ghi chú job gốc) nên bị bỏ qua, chỉ phần mới còn `pending`. Bản ghi và raw của 100 khách sạn đầu vẫn nằm ở job cũ
và được `batch.py merge` gộp như mọi job khác.

  python deepen_jobs.py --cities @deep --to 200            # xem kế hoạch
  python deepen_jobs.py --cities @deep --to 200 --apply    # tạo job, rồi chạy:
  python batch.py run booking-hotels --cities @deep --per-destination 200 --dates 2026-10-15 --fast --concurrency 2
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
from pathlib import Path

import batch
from collectors.common import Paths
from monitor import pid_alive

ROOT = Path(__file__).resolve().parent


def holds_file(pid: int, target: Path) -> bool | None:
    """Tiến trình `pid` đang mở `target`? RunLock giữ file khoá mở suốt thời gian chạy, còn file cũ vẫn ghi PID của
    tiến trình đã xong nên không thể tin PID. None = không kiểm tra được."""
    fd_dir = Path(f"/proc/{pid}/fd")
    if not fd_dir.is_dir():
        return None
    want = str(target.resolve())
    try:
        for fd in fd_dir.iterdir():
            try:
                if os.readlink(fd) == want:
                    return True
            except OSError:
                continue
    except OSError:
        return None
    return False


def running_pid(path: Path) -> int | None:
    """PID tiến trình đang giữ một khoá trong state/ của job batch này, hoặc None."""
    for lock in (path / "state").glob("*.lock"):
        try:
            pid = int(lock.read_text().strip() or 0)
        except (OSError, ValueError):
            continue
        if not (pid and pid_alive(pid)):
            continue
        held = holds_file(pid, lock)
        if held:
            return pid
        if held is None:
            try:
                cmd = Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\0", b" ").decode(errors="replace")
            except OSError:
                continue
            if "python" not in cmd:
                continue
            if lock.stem == "batch_job" and "batch.py" in cmd:
                return pid
            if any(x in cmd for x in ("crawl.py", "normalise.py")) and re.search(rf"--data-dir {re.escape(str(path))}(\s|$)", cmd):
                return pid
    return None


def city_spec(city: str, dates: str, per_destination: int) -> dict:
    specs, _ = batch.plan_jobs("booking-hotels", city, dates=dates, per_destination=per_destination)
    return next(s for s in specs if s["city"] != "all")


def plan(root: Path, cities: str, dates: str, old: int, new: int) -> list[dict]:
    from collectors.plan import select_destinations

    rows = []
    for dest in select_destinations(cities):
        old_spec, new_spec = city_spec(dest.name, dates, old), city_spec(dest.name, dates, new)
        old_dir, new_dir = root / batch.job_id(old_spec), root / batch.job_id(new_spec)
        row = {"city": dest.name, "oldDir": old_dir, "newDir": new_dir, "newSpec": new_spec, "action": "clone"}
        if not (old_dir / "state" / "crawl_state.sqlite").exists():
            row["action"] = f"bỏ qua: chưa có job {old} khách sạn để tái dùng"
        elif running_pid(old_dir):
            row["action"] = "bỏ qua: job cũ đang chạy (chờ xong)"
        elif (new_dir / "state" / "crawl_state.sqlite").exists():
            row["action"] = "đã có (giữ nguyên, không ghi đè)"
        rows.append(row)
    return rows


def clone_state(row: dict, old_per: int) -> int:
    """Sao chép hàng đợi; trả số URL được đánh dấu skipped (đã cào ở job cũ)."""
    paths = Paths(row["newDir"]).ensure()
    src = sqlite3.connect(row["oldDir"] / "state" / "crawl_state.sqlite")
    dst = sqlite3.connect(paths.state / "crawl_state.sqlite")
    try:
        src.backup(dst)
        n = dst.execute(
            "UPDATE items SET status='skipped', last_error=? WHERE status='done'",
            (f"đã cào ở job {row['oldDir'].name} (per-destination {old_per})",)).rowcount
        dst.commit()
    finally:
        src.close()
        dst.close()
    (row["newDir"] / "job.json").write_text(json.dumps(row["newSpec"], ensure_ascii=False, indent=2), encoding="utf-8")
    return n


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cities", default="@deep")
    ap.add_argument("--from-per", type=int, default=100, help="--per-destination của job đã cào")
    ap.add_argument("--to", type=int, default=200, help="--per-destination mới")
    ap.add_argument("--dates", default="2026-10-15", help="ngày hỏi giá của job đã cào")
    ap.add_argument("--root", type=Path, default=ROOT / "data/batches")
    ap.add_argument("--apply", action="store_true", help="tạo job (mặc định chỉ in kế hoạch)")
    a = ap.parse_args(argv)
    if a.to <= a.from_per:
        ap.error("--to phải lớn hơn --from-per")
    root = a.root.resolve()
    for row in plan(root, a.cities, a.dates, a.from_per, a.to):
        note = row["action"]
        if a.apply and note == "clone":
            note = f"đã tạo, {clone_state(row, a.from_per)} URL cũ đánh dấu skipped"
        print(f"{row['city']:16s} {row['oldDir'].name[:8]} → {row['newDir'].name[:8]}  {note}", flush=True)
    if not a.apply:
        print("(xem trước: thêm --apply để tạo)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
