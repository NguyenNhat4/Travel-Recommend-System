# data_collection.seed

Pipeline deterministic theo `docs/MOCK_DATA_SPEC.md`, nạp đúng DDL trong `db/vota_schema.sql` và `db/insider_schema.sql`:

1. tìm catalog runtime `src/data_collection/data/products.jsonl`, rồi snapshot có version `src/data_collection/snapshots/2026-09-21/products.jsonl.gz` (hoặc `--products PATH`); snapshot được kiểm checksum và bung dưới thư mục runtime ignored;
2. parse combo và chuẩn hoá catalog theo cửa sổ 30 ngày;
3. sinh CDP history, 4 persona + 50 tài khoản app, booking mẫu và dữ liệu Insider;
4. nạp hai database bằng transaction; `--reset` xoá state local liên quan trước khi nạp;
5. cập nhật riêng khối `seed-report` trong README của data collection.

Chạy từ `src/`:

```bash
python -m data_collection.seed --as-of YYYY-MM-DD --seed 42 --reset
```

Từ repository root, cách ngắn nhất cho người mới là `make demo-db`; nếu database local đã có dữ liệu thì dùng `make demo-db-reset`. Snapshot còn mang theo `combo_items_manual.jsonl` đã duyệt để mọi máy tạo cùng `catalog.combo_items`.

Biến môi trường: `SEED_DATABASE_URL`, `INSIDER_DATABASE_URL`, `INSIDER_TOKEN`. Dùng `--generate-only` để chỉ sinh và kiểm tra artifact mà không ghi PostgreSQL. Pipeline không sinh vector.
