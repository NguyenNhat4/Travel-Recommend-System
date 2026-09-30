# Sửa lỗi "database is locked" khi 4 site cào cùng lúc

- Ngày: 2026-09-28
- Tác giả: Đăng Khôi / Claude Code
- Nhánh: test/newcrawl
- Trạng thái: hoàn thành
- Phạm vi: data

## Mục tiêu

Lượt `full-20260928T024657Z-14811` (bộ `local_crawl`, 4 site song song) có nhóm trip chết ngay giây đầu với
`sqlite3.OperationalError: database is locked` tại `StateDB.__init__`. 4 tiến trình `crawl.py` cùng mở file mới
`state/crawl_state.sqlite` của lượt. Hệ quả: booking/agoda vẫn chạy nhưng lượt sẽ không nạp DB. Phục vụ FR-CAT-01. Không đổi PRD, contract, DDL.

## File thay đổi

- `src/data_collection/collectors/common.py` — sửa: `StateDB`:
  - `sqlite3.connect(..., timeout=60)`;
  - thử lại `PRAGMA journal_mode=WAL` khi gặp "locked" (lệnh này có thể trả lỗi ngay, không qua busy timeout);
  - tạo/nâng cấp schema trong `BEGIN IMMEDIATE`. Trước đây hai tiến trình cùng `ALTER TABLE items ADD COLUMN plan` → "duplicate column name".
- `src/data_collection/tests/test_state_db_parallel.py` — thêm: 8 tiến trình mở cùng file mới cùng lúc, lặp 5 vòng.
- `history/2026-09-28-sqlite-state-khi-cao-song-song.md` — thêm: entry này.

## Quyết định

- Sửa ở `StateDB` (dùng chung cho mọi collector), không tách file trạng thái theo site: giữ cấu trúc thư mục lượt và monitor như cũ.

## Kiểm tra

- Test mới với code cũ: fail (`database is locked`); chỉ thêm thử lại WAL: còn fail (`duplicate column name: plan`); sau khi sửa đủ: pass 5/5 lần chạy.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=<repo>/src python -m pytest -q -p no:cacheprovider tests` (env `vsf`): **359 passed, 3 skipped**.
- `git diff --check`: sạch.

## Còn lại / rủi ro

- Lượt `full-20260928T024657Z-14811` đang chạy bằng code cũ ở nhóm trip nên vẫn sẽ lỗi. Lượt mới dùng code mới (mỗi `crawl.py` là tiến trình mới).
- Lượt đó chạy ở bộ `local_crawl`, không phải bộ demo (monitor mở thiếu `LOCAL_CRAWL_NAME=demo`).
- Chưa commit.
