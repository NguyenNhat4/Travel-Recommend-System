# Catalog snapshots

Mỗi thư mục ngày là đầu vào có version cho local demo. Snapshot được commit ở dạng `products.jsonl.gz`; file JSONL đã bung và mọi output loader/seed tiếp tục nằm dưới `src/data_collection/data/` và bị Git ignore.

`manifest.json` cố định số dòng cùng SHA-256 của file nén, catalog gốc và mapping combo. Seed kiểm tra toàn bộ trước khi sinh artifact hoặc ghi database. Không sửa file trong snapshot bằng tay; tạo phiên bản ngày mới khi catalog thay đổi.

Snapshot `2026-09-21` chứa:

- 10.320 sản phẩm theo 13 trường catalog chính thức.
- 64 dòng mapping combo đã duyệt tay.
- Không chứa profile, event, booking, secret hoặc Docker volume; các dữ liệu demo đó được seed tất định khi chạy.
