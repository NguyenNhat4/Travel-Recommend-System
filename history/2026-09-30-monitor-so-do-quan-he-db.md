# Monitor: sơ đồ quan hệ giữa các bảng (giai đoạn 1, phần sơ đồ)

- Ngày: 2026-09-30
- Tác giả: Đăng Khôi / Claude Code
- Nhánh: test/newcrawl
- Trạng thái: dang dở
- Phạm vi: data, docs

## Mục tiêu

Người yêu cầu: "Tôi chưa thấy hình vẽ mỗi quan hệ giữa các bản, bảng schema hoàn chỉnh trong đó ? khi bấm vào có thể xem
chi tiết từng bảng ?". Phần "Sơ đồ quan hệ" của đề xuất đã áp dụng
`docs/prd/update-archive/2026-09-30-monitor-trang-thai-db-realtime.md` (`docs/prd/deployment-plan.md` §5).

## File thay đổi

- `src/data_collection/db_browser.py` — sửa: `graph()` (mọi bảng / view kèm đủ cột: kiểu, PK, FK, cột bí mật; số dòng; cạnh
  khoá ngoại và cạnh quy ước: view `product_id` → `cdp.products`, sản phẩm con → cha, vé mô phỏng → vé gốc).
- `src/data_collection/monitor.py` — sửa: route `/api/dbx/graph`.
- `src/data_collection/monitor_ui/index.html` — sửa: tab DB có "Bảng dữ liệu" / "Sơ đồ quan hệ"; sơ đồ SVG không thư viện
  ngoài (cột theo schema, schema dài chia 2 cột; nét liền khoá ngoại, nét đứt quy ước; rê chuột tô quan hệ của bảng; bấm mở
  bảng); nút "Xem toàn cảnh" / "Cỡ thật"; URL `#page=db&mode=diagram`.
- `src/data_collection/tests/test_db_browser.py` — sửa: thêm test sơ đồ.
- `history/2026-09-30-monitor-so-do-quan-he-db.md` — thêm: entry này.

## Kiểm tra

- `DBX_TEST_DATABASE_URL=… pytest test_db_browser.py`: 12 passed (mọi bảng có mặt, `cdp.products` đủ 13 cột, cột bí mật đánh
  dấu, khoá ghép `combo_items`, cạnh quy ước, mọi cạnh trỏ tới bảng / cột có thật).
- Monitor local (:8765) trỏ DB `vota` local + backend local (:8000, `ITINERARY_DATA_MODE=inprocess`): sơ đồ 20 bảng / view,
  24 quan hệ; rê chuột `cdp.products` tô 10 quan hệ, làm mờ 14; bấm ô `bookings` mở bảng `app.bookings`, URL
  `#page=db&table=app.bookings`.

## Còn lại / rủi ro

- Giai đoạn 1 còn: sơ đồ luồng dữ liệu (ai đọc / ghi bảng nào) và hoạt động DB realtime (`pg_stat_user_tables`,
  `pg_stat_activity`) tô lên sơ đồ.
- Chưa commit.
