# Dựng lại database local; sửa seed và Makefile còn trỏ tới catalog.product_vectors

- Ngày: 2026-09-23
- Tác giả: mihhquan / Claude Code
- Nhánh: feat/auth
- Trạng thái: hoàn thành
- Phạm vi: data, db

## Mục tiêu

Migration `0002_drop_product_vectors.sql` không chạy được trên volume Postgres tạo từ image `pgvector` cũ (`could not access file "$libdir/vector"`), xem `2026-09-23-job-embed-products-weaviate-cohere.md`. Người dùng chọn tạo lại volume: `docker compose down -v` rồi `make demo-db`. Khi dựng lại thì lộ ra ba lỗi làm `make demo-db`/`demo-db-reset` không chạy hết, nên sửa luôn.

## File thay đổi

- `src/data_collection/seed/report.py` — sửa: bỏ đếm `catalog.product_vectors` (bảng đã bị migration 0002 gỡ; seed nạp xong rồi mới hỏng ở bước báo cáo). Dòng báo cáo đổi thành "vector nạp lên Weaviate bằng `make embed-products`".
- `src/data_collection/seed/database.py` — sửa: bỏ `catalog.product_vectors` khỏi `TRUNCATE` của `--reset`, vì bảng đã bỏ làm `make demo-db-reset` lỗi.
- `src/data_collection/README.md` — sửa: câu mô tả pipeline không còn nhắc `product_vectors`. Khối `seed-report` được seed tự ghi lại.
- `Makefile` — sửa: lệnh seed trong `demo-db`/`demo-db-reset` đặt trong subshell `(cd src && …)`. Do `.ONESHELL`, `cd src` cũ làm `$(MAKE) verify-db` chạy trong `src/` và báo `No rule to make target 'verify-db'`. Thêm ngoặc kép quanh `$(PYTHON)`/`$(MIGRATE_PYTHON)` để chạy được khi đường dẫn repo có dấu cách.
- `README.md` — sửa: hướng dẫn `PYTHON=` phải là đường dẫn tuyệt đối, vì seed chạy từ `src/`.

## Quyết định

- Sửa seed theo DDL hiện hành, không tạo lại bảng. Vector đã chốt chuyển sang Weaviate (`2026-09-22-chuyen-vector-sang-weaviate-cohere.md`). Không lệch PRD.
- `docker compose down -v` xoá mọi volume của project: `pgdata`, `weaviate_data` (gồm 5 object thử nghiệm) và 2 volume cache của backend. Người dùng đã đồng ý mất dữ liệu local.

## Kiểm tra

- `docker compose down -v`: xoá `pgdata`, `weaviate_data`.
- `make demo-db` trên volume mới: migration 0001 và 0002 áp thành công; seed nạp đủ, hỏng ở `report.py` (đã sửa).
- `make demo-db-reset PYTHON="$PWD/src/backend/.venv/bin/python"` sau khi sửa: exit 0. Loaded `cdp.products=10320`, `cdp.profiles=2000`, `cdp.events=7131`, `app.users=54`, `insider.*` đủ. `db/verify.sql` và `db/verify_insider.sql`: 22/22 PASS, 0 FAIL.
- `pytest -q data_collection/tests -k "seed or report"` (từ `src/`): 55 passed.

## Còn lại / rủi ro

- Weaviate local đã trống. Muốn có vector local thì chạy `docker compose up -d --wait weaviate` rồi `make embed-products` với `WEAVIATE_URL=http://localhost:8080`. Đẩy lên cloud vẫn chờ đề xuất `docs/prd/update/2026-09-23-weaviate-cloud-index-hfresh.md`.
- Máy khác còn volume tạo từ image pgvector sẽ gặp cùng lỗi migration 0002. Cách xử lý đã dùng ở đây: `docker compose down -v` rồi `make demo-db`, sẽ mất dữ liệu local.
- Chưa commit.
