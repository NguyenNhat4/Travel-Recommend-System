# Thêm cấu hình REPLICA_DATABASE vào .env.example

- Ngày: 2026-10-01
- Tác giả: Khoa / Claude
- Nhánh: khoa/env-replica-database
- Trạng thái: hoàn thành
- Phạm vi: backend, data (cấu hình mẫu)

## Mục tiêu

Ghi lại cấu hình để backend và job crawler đọc từ DB replica (bản sao chỉ đọc của primary), để team biết đặt biến nào, cổng nào và giới hạn gì.

## File thay đổi

- `.env.example` — sửa: thêm `REPLICA_DATABASE_URL` và `REPLICA_CDP_DATABASE_URL` (dạng comment) kèm giải thích tunnel `127.0.0.1:15433 -> 10.148.0.4:5432` và các đường đọc thuần được phép.
- `src/data_collection/.env.example` — sửa: thêm `REPLICA_DATABASE_URL` (dạng comment) kèm hướng dẫn đặt vào `CLOUD_DATABASE_URL` cho job embed và cảnh báo không đặt vào `CLOUD_SEED_DATABASE_URL`.

## Quyết định

- Tên biến `REPLICA_DATABASE_*` theo yêu cầu, thay cho `READ_DATABASE_*` ở bản nháp đầu.
- Để dạng comment: mặc định không đặt thì mọi truy vấn vẫn đi qua primary.
- Replica là bản sao cả cụm nên dùng cùng user và mật khẩu với primary, chỉ khác host và cổng.
- Chỉ đường đọc thuần dùng replica. Ghi và đọc-sau-ghi (đăng nhập, token, giỏ hàng, đặt chỗ, thanh toán, ghi CDP, `load_products`, `parse_combos`, seed) ở lại primary.

## Kiểm tra

- Chỉ đổi file mẫu, toàn bộ là comment: không ảnh hưởng hành vi khi chạy. Không có test để chạy.

## Còn lại / rủi ro

- Backend chưa đọc `REPLICA_*`: `src/backend/app/core/config.py` mới có `database_url` và `cdp_database_url`. Cần thêm trường cấu hình và nối vào các adapter chỉ đọc (`PostgresProductQuery`, `PostgresProductLookup`, `PostgresSearchLogReader`, `PostgresCdpReader`), mặc định bằng primary.
- Tunnel `127.0.0.1:15433` trên VM app chưa tạo.
- Crawler đọc `CLOUD_DATABASE_URL` cho job embed; muốn dùng replica thì đặt biến đó, hoặc sửa code để đọc thẳng `REPLICA_DATABASE_URL`. Job embed chạy ngay sau bước nạp có thể thấy replica chưa kịp nhận dữ liệu mới.
