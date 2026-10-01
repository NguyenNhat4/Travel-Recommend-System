# Snapshot catalog `2026-09-29`: thêm vé máy bay khứ hồi, làm mặc định cho `make demo-db`

- Ngày: 2026-09-29
- Tác giả: Đăng Khôi / Claude Code
- Nhánh: test/newcrawl
- Trạng thái: hoàn thành
- Phạm vi: data, docs

## Mục tiêu

Người yêu cầu: "tạo snapshot để họ tự make demo-db". Team FE cần dữ liệu vé khứ hồi (`fareClasses`, contract 1.9.0) ngay
trên máy mình, trước khi job cào mới chạy trên VM. Phục vụ FR-CAT-01, FR-CAT-03.

## File thay đổi

- `src/data_collection/snapshots/2026-09-29/products.jsonl.gz`, `manifest.json`, `combo_items_manual.jsonl` — thêm:
  - snapshot `2026-09-23` (11.387) + vé máy bay trip.com cào ngày 29/09/2026: 11.708 sản phẩm;
  - lượt cào local `full-20260929T090423Z-312984`, chỉ bật nguồn `sources.tripFlights`, phạm vi `@deep`: 7 sân bay, 50 tuyến
    nội địa, 34 trang, 0 lỗi;
  - thay 110 dòng cùng `sourceRef` (29 tuyến, 81 vé một chiều; `productId` giống hệt vì sinh theo `sourceRef`);
  - thêm 321 vé mới (31 một chiều, 290 khứ hồi);
  - gzip tất định (`mtime=0`); mapping combo chép nguyên từ `2026-09-23`.
- `Makefile` — sửa: `CATALOG_SNAPSHOT` mặc định → `2026-09-29`.
- `src/data_collection/seed/config.py` — sửa: `DEFAULT_SNAPSHOT_DIR` → `2026-09-29`.
- `src/data_collection/snapshots/README.md` — sửa: mô tả snapshot mặc định mới, hạn báo giá vé khứ hồi, lý do giữ `2026-09-23`.
- `src/data_collection/README.md` — sửa: hai chỗ trỏ snapshot; khối seed-report do seed ghi lại theo snapshot mới.
- `docs/spec/MOCK_DATA_SPEC.md` — sửa: cây thư mục trỏ `snapshots/2026-09-29/`.
- `src/backend/tests/integration/test_local_postgres_adapters.py` — sửa: số sản phẩm `== 11_387` → `>= 11_387` (cùng ngưỡng
  `db/verify.sql`; test chỉ chạy khi `RUN_POSTGRES_INTEGRATION=1`).
- `history/2026-09-29-snapshot-catalog-ve-khu-hoi.md` — thêm: entry này.

## Quyết định

- Ghép lên snapshot cũ thay vì xuất từ `cdp.products`: bản xuất DB mang cửa sổ ngày đã cắt theo ngày nạp; snapshot phải giữ
  khoảng ngày của nguồn để seed tự cuộn theo `--as-of`.
- Bộ đánh giá search (`src/evaluation/search_bench`, `docs/spec/bench/`) vẫn ghim `2026-09-23` để tái lập; không đổi.
- Chưa có hạng vé (`code: null`, "Giá rẻ nhất"); không có giá thương gia.

## Kiểm tra

- Snapshot: ID và `sourceRef` duy nhất; mọi `parentProductId` trỏ tới dòng có trong snapshot; 13 trường đúng thứ tự.
- Seed đầy đủ vào database nháp `vota_snapcheck` + `insider_snapcheck`, dựng từ `db/*.sql` + migration, với `--as-of 2026-09-29 --seed 42 --reset`:
  - kết quả: 11.708 products, 2.000 profiles, 7.134 events, 307 combo items;
  - `db/verify.sql`: 0 FAIL; `db/verify_insider.sql`: 0 FAIL;
  - hai database nháp đã xoá.
- `data_collection` `pytest tests`: 411 passed, 3 skipped.
- Cùng dữ liệu đã nạp vào `vota` local (bằng `load_into_db`) và gọi API thật:
  - `GET /products?parentProductId=` (HAN–DAD, SGN–PQC) và `GET /products/{id}` khớp contract 1.9.0;
  - phòng khách sạn không có `fareClasses`.

## Còn lại / rủi ro

- Vé khứ hồi có `priceValidUntil = 2026-09-30`. Từ 01/10, `fareClasses` trả `EXPIRED` (vẫn thêm giỏ được). Giá mới đến
  từ job cào trên VM, không làm mới snapshot hằng ngày.
- Máy đã seed trước đây: `make demo-db` báo DB đã có dữ liệu và dừng; cần `make demo-db-reset` (xoá state demo local) để có snapshot mới.
- Nạp DB staging: chờ người yêu cầu có kết nối (SSH tunnel + tài khoản ghi `cdp.products`). Lệnh dự kiến: seed
  `--catalog-only` với snapshot này.
  - Đã mô phỏng trên database nháp: seed đầy đủ `2026-09-23`, rồi `--catalog-only` `2026-09-29`.
  - Kết quả: inserted 321, updated 110; không đổi `app.bookings`, `cdp.events`; `db/verify.sql` 0 FAIL.
  - Database nháp đã xoá.
- Chưa commit.
