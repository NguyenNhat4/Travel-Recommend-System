# Monitor: tab "DB" xem toàn bộ database `vota`, có liên kết

- Ngày: 2026-09-30
- Tác giả: Đăng Khôi / Claude Code
- Nhánh: test/newcrawl
- Trạng thái: hoàn thành
- Phạm vi: data, docs

## Mục tiêu

Người yêu cầu chốt đề xuất `docs/prd/update-archive/2026-09-30-monitor-xem-toan-bo-db.md` ("CHốt"); "đây là của admin".

## File thay đổi

- `docs/prd/requirements.md` — sửa: NFR-SEC-01 (che cột bí mật), NFR-SEC-02 (ngoại lệ công cụ xem DB chỉ đọc).
- `docs/prd/deployment-plan.md` — sửa: §5 thêm mục xem DB trên monitor.
- `docs/prd/update/2026-09-30-monitor-xem-toan-bo-db.md` → `docs/prd/update-archive/` — sửa: `đã áp dụng`.
- `src/data_collection/db_browser.py` — thêm: metadata từ `information_schema` / `pg_constraint`, bảng + số dòng, dòng (lọc,
  tìm, sắp xếp, phân trang ≤ 200), dòng chi tiết với liên kết hai chiều (khoá ngoại + quy ước `parentProductId`,
  `demo:business:`, view `product_id`), con theo `parentProductId`; kết nối chỉ đọc, `statement_timeout` 5 s; che cột bí mật.
- `src/data_collection/monitor.py` — sửa: `FreshMonitor.dbx()`, route `/api/dbx/tables|rows|row|children`, `prefixed()`.
- `src/data_collection/monitor_ui/index.html` — sửa: tab "DB" (danh sách bảng, bảng dữ liệu, ô khoá bấm được, cửa sổ dòng).
- `src/data_collection/tests/test_db_browser.py` — thêm: 3 test thuần + 8 test PostgreSQL (`DBX_TEST_DATABASE_URL`).
- `docs/guide/trien-khai-job-cao-du-lieu.md` (mục Monitor), `src/data_collection/README.md` — sửa: mô tả tab DB.
- `history/2026-09-30-monitor-tab-db.md` — thêm: entry này.

## Kiểm tra

- Database nháp `vota_dbx_test_20260930` (+ `insider_dbx_test_20260930`) seed đầy đủ snapshot 2026-09-30:
  `test_db_browser.py` 11 passed. Phá thử (bỏ che cột / tìm trong cột bí mật / cho ghi / bỏ kiểm tên bảng): mỗi lần ≥ 1 fail.
- Monitor local cổng 8799 trỏ DB nháp, kiểm bằng trình duyệt: tab DB, link `#page=db&table=…`, dòng đơn → liên kết
  profiles / booking_items / payments, booking_items → sản phẩm, sản phẩm → cha (quy ước) → 13 phòng con, `app.users`
  hiện `password_hash` "(ẩn)".
- Bố cục khung hẹp (859 px) sau khi đổi sang class `.dbgrid` có media query: trang không cuộn ngang (scrollWidth 844), chỉ bảng
  dữ liệu cuộn trong `.scroll`.
- `DBX_TEST_DATABASE_URL=… pytest src/data_collection/tests`: 467 passed, 9 skipped; `compileall src/data_collection`: ok.

## Còn lại / rủi ro

- Database nháp `vota_dbx_test_20260930`, `insider_dbx_test_20260930` giữ lại trên Postgres local cho việc tiếp theo (monitor
  trạng thái DB / sơ đồ quan hệ); xoá khi xong.
- Chưa commit. Monitor public chưa đăng nhập: nên giới hạn IP cổng 8765.
