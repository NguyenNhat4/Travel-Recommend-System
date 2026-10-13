# Bổ sung vé Booking có giá cho nơi thiếu điểm tham quan, sửa gán điểm đến của tour

- Ngày: 2026-10-12
- Tác giả: Phạm Nguyễn Đăng Khôi / Claude (agent)
- Nhánh: test/newcrawl
- Trạng thái: dang dở
- Phạm vi: data

## Mục tiêu

Issue #159: lên lịch trình ở tỉnh/thành chỉ có khách sạn thì agent không gợi ý được nơi đi chơi, vì catalog không có
điểm tham quan. Grounding 100% (NFR-REL-01) nên agent chỉ dùng được sản phẩm có trong catalog. Người dùng yêu cầu bổ sung
bằng **dữ liệu thật** (không tạo vé/hoạt động giả), ưu tiên vé có giá để bỏ vào giỏ được. Phục vụ FR-CAT-01, FR-AGT.

Hiện trạng production trước khi bổ sung (đọc 12/10): 58 điểm đến có khách sạn, 19 nơi không có điểm tham quan nào
(Thanh Hóa, Tây Ninh, Cà Mau, Tam Đảo, Lý Sơn, Sóc Trăng, Sơn La, Mù Cang Chải, Mộc Châu, Bắc Ninh, Lạng Sơn, Hà Giang,
Bạc Liêu, Bảo Lộc, Hà Tiên, Vân Đồn, Sầm Sơn, Tuyên Quang…). Điểm tham quan Trip chỉ có ở nơi có `trip_city` trong
`collectors/plan.py`, và 349 điểm Trip không có giá. View `catalog.product_meta` đặt `is_bookable = false` khi
`unit_price` rỗng, nên các điểm này không vào giỏ được.

## File thay đổi

- `src/data_collection/collectors/geo.py` — sửa: thêm tên địa danh hay gặp trong tên tour: Pù Luông → Thanh Hóa, Lan Hạ →
  Cát Bà, DMZ / Vịnh Mốc / Khe Sanh / Hiền Lương → Quảng Trị, Paradise Cave / Sơn Đoòng / Kẻ Bàng → Phong Nha,
  Bà Đen / Black Virgin → Tây Ninh, Cái Răng → Cần Thơ, Mã Pí Lèng / Lũng Cú → Hà Giang, Fansipan / Cát Cát → Sa Pa,
  Cù Lao Chàm / Mỹ Sơn → Hội An, Trà Sư → Châu Đốc, Tà Xùa → Sơn La.
- `src/data_collection/normalise.py` — sửa: thêm `tour_destination()`. Hàm này che phần nơi khởi hành trong tên tour
  ("From Hanoi…", "…from Hanoi", "Hue to …", "Hanoi: …"), đọc "Dien Bien Phu" trong tên tour là thành phố. Dùng trong
  `booking_attraction_product()`; tên không nêu nơi đến thì giữ cách cũ (`normalise_destination(name, subtitle, city)`).
- `src/data_collection/tests/test_quality.py` — sửa: thêm `test_booking_tour_destination_ignores_departure_city`.
- `history/2026-10-12-bo-sung-ve-booking-noi-thieu-diem-tham-quan.md` — thêm: entry này.

Ngoài repo (thư mục bị git ignore `src/data_collection/data/attractions-fill-20261012/` của worktree chính): `picked.json`
(URL đã chọn), `interim/` và `products.jsonl` (kết quả cào + chuẩn hoá), `load_attractions.py` (script nạp, mặc định chỉ
xem trước), `load/db_report.jsonl`.

## Quyết định

- Nguồn: sitemap vé tham quan Booking (13.623 URL ở Việt Nam, có giá, đặt được). Job cào hằng ngày không lấy nguồn này;
  production mới có 283 vé từ đợt nạp đầu. Chọn tối đa 25 URL cho mỗi điểm đến còn thiếu hoặc mỏng, theo từ khoá trong
  slug, ưu tiên hoạt động (trek, kayak, lặn, biển, hang động…), seed 42. Cào bằng `crawl.py booking-attractions --match`
  (trình duyệt trong Xvfb, không dùng `--fast` vì `--fast` không lấy được giá).
- Chỉ dữ liệu thật; không sinh vé mô phỏng (người dùng chốt trong phiên).
- Bỏ 42 sản phẩm "xe đưa đón" (transfer) khỏi đợt nạp, vì không phải điểm vui chơi.
- Nạp bằng đúng `fresh_catalog_db.load_into_db`: chỉ upsert, không xoá. Cùng transaction đó chạy `simulated_business` và
  `demo_data` (mock 09/10, FR-CAT-03 ngoại lệ 2–5); người dùng chọn giữ mock bật.

## Kiểm tra

- Cào: 410/410 trang, 0 lỗi, 399 có giá. `normalise.py --no-plan`: 398 sản phẩm, đều có giá.
- `pytest data_collection/tests` (env vsf2): 649 passed, 27 skipped.
- Chạy thử trên production (đọc + demo_data trong transaction ROLLBACK): `new 304`.
- Người dùng đồng ý, nạp lên production ~12:56 ngày 12/10 (`load_attractions.py --apply`): `new 304, dbRowsWritten 304`.
  Cùng transaction: `fillWritten 7390` (3.704 một chiều + 3.662 khứ hồi), `reverseRoutes 24`, `mockProducts 100`,
  `comboItemsChanged 237`, `simulatedRooms 1`.
- Đọc lại production: `cdp.products` 29.093; 587 vé Booking đặt được; demo `fill` 7.366, `reverse` 24, `combo` 104
  (100 đang bán), `room` 1; `combo_items` 101/445 dòng có `price_share`.
- Bấm `index` trên monitor production lúc 12:57 (`full`/`daily` không chạy kèm) để embed + index các dòng mới.

## Còn lại / rủi ro

- Chờ lượt `index` trên monitor xong, rồi kiểm tra search/agent thấy vé mới.
- Vẫn 0 vé có giá (dù có khách sạn): Quy Nhơn, Buôn Ma Thuột, Pleiku, Tuy Hòa, Rạch Giá, Kon Tum, Cà Mau, Đồng Tháp,
  Tam Đảo, Sóc Trăng, Sơn La, Bạc Liêu, Lạng Sơn, Bảo Lộc, Hà Tiên, Vân Đồn, Sầm Sơn, Tuyên Quang. Booking gần như không có
  tour ở đây; cần nguồn khác (vd. `crawl.py trip-experiences`), làm ở đợt sau.
- Khoảng 85% vé mới có mô tả tiếng Anh (lần đếm trước khi bỏ xe đưa đón: 293/346), do nhà cung cấp tour viết, giống 283
  vé Booking đã có.
- Job cào hằng ngày chưa lấy vé Booking: việc "chỉnh job cào" người dùng để sau. Lượt cào lớn không xoá các dòng này
  (nạp chỉ upsert), nhưng giá của chúng sẽ không được làm mới cho tới khi job có nguồn này.
- Điểm đến "Vinpearl Onsen Resort Tuyên Quang" (một khách sạn) là lỗi dữ liệu có sẵn, chưa xử lý.
