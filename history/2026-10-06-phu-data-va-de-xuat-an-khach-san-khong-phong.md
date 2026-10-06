# Phủ thêm data lên DB VM (điểm tham quan, combo, khách sạn Agoda) và ẩn khách sạn không có phòng (FR-CAT-02)

- Ngày: 2026-10-06
- Tác giả: Đăng Khôi / Claude Code
- Nhánh: test/newcrawl
- Trạng thái: dang dở (lệnh ẩn 303 KS trên DB VM chờ người dùng chạy; code chưa commit)
- Phạm vi: data, docs

## Mục tiêu

Người dùng muốn phủ thêm combo, golf, điểm tham quan có giá và các thành phố chưa có data, đưa vào DB chung; chỉ giữ sản phẩm đặt được. Phục vụ FR-CAT-01, FR-CAT-02, FR-CAT-04.

## Đã làm (không đổi code trong repo)

- Cào local vào `src/data_collection/data/coverage-20261006/` (ignored), chỉ nguồn HTTP/trang được robots cho phép:
  - Vinpearl voucher API: so với DB, Vinpearl đã đủ (6 mục còn bán chưa thấy đều là trang nhóm type 7, vé con đã có).
  - `vinpearl-bundles` (combo bay + ở): kẹt 404 ở tuyến HAN → VDO hơn 1 giờ, dừng; xuất offline từ cache 11 combo (3 tuyến).
  - `trip-attractions` @all, budget 60: 431 trang, gần như không thêm điểm có giá (Trip không hiện giá vé).
  - `booking-attractions` lọc slug địa danh, 300 trang (Chromium trong Xvfb; một lần trình duyệt đóng ở trang 150, chạy tiếp): giá USD/EUR đổi VND theo tỷ giá normalise.
  - `agoda-api` 31 thành phố, 30 KS/thành phố, 1 ngày giá: 915 KS, chỉ 297 có hạng phòng (nguồn báo không có nhà cung cấp cho phần còn lại).
- Không dùng `trip-combos`/`trip-hotels` (robots cấm).
- Chuẩn hoá bằng `normalise.py` cùng tham số job; điểm tham quan dùng `--no-plan` vì `booking_attraction` bị cắt cứng 10/điểm đến.
- Loại khi nạp: 4 điểm Trip trùng vé Vinpearl (tránh ghi đè giá Vinpearl), 53 mục booking là dịch vụ đưa đón, 2 tour giá hỏng (€ 1,69), 2 KS Agoda trùng tên KS booking đã có, 618 KS Agoda không có phòng.
- Nạp bằng `load_into_db` qua script `src/data_collection/data/vm-repair-20261006/load_coverage.py` (chạy thử = transaction + rollback; `--apply` sao lưu rồi ghi). Người dùng chạy:
  - Đợt điểm tham quan + combo: COMMITTED — 303 mới, 367 làm mới, 0 trùng ref; sao lưu `backup-before-coverage-2026-10-06.jsonl`.
  - Đợt KS Agoda đặt được (`load_agoda_bookable`: 295 KS, 1.024 hạng phòng có giá): COMMITTED — 1.319 mới, 0 trùng ref.
  - Lỗi script: lần chạy thứ hai ghi đè file sao lưu của đợt 1 (cùng tên) bằng file 0 dòng. Trạng thái cũ của cả 367 dòng vẫn có trong `backup-before-maintain-2026-10-06.jsonl` (chụp sáng 06/10). Đã sửa script: tên sao lưu kèm tên đợt.

## Kiểm tra DB VM sau đợt 1 (chỉ đọc)

- 0 ref trùng; vé máy bay 2.599/2.599 đang bán, 0 đã bay / lệch ngày; 8.693 phòng lịch từ 06/10.
- Điểm tham quan đặt được 565 (Huế 68, Phan Thiết 50, Vũng Tàu 48 mới…), combo 146; sản phẩm mới đều có ảnh và cửa sổ.
- `db/verify.sql` (bỏ meta-command psql): 23/26 PASS; FAIL `profiles = 2000` (7003), `events 6000-8000` (40058), `max events per user <= 15` (37) — do làm giàu CDP 05/10 (`2026-10-05-cdp-append-v1.md`), không do đợt này.
- 11 combo mới: 22 thành phần chưa map sang sản phẩm (parser chỉ thấy sản phẩm của đợt nạp); lượt cào đầy đủ sẽ map lại.

## File thay đổi

- `docs/prd/update-archive/2026-10-06-an-khach-san-khong-co-phong-dat-duoc.md` — thêm: đề xuất ẩn KS không có phòng đặt được; người dùng chốt 06/10 ("ok tôi đồng ý"), đã áp dụng.
- `docs/prd/requirements.md` FR-CAT-02, `docs/prd/data-model.md` §4.2 — sửa: KS tổng quan không có phòng con đặt được thì `available = false`, tự bật lại khi có phòng.
- `src/data_collection/fresh_catalog_db.py` — sửa: `_hide_hotels_without_rooms` chạy cuối `apply_window` (mọi `maintain_catalog` và lần nạp), dấu `noBookableRoom`, chỉ bật lại dòng có dấu (không gộp, không giá quá hạn, không ngoài cửa sổ).
- `src/data_collection/seed/load_products.py` — sửa: seed demo áp cùng quy tắc.
- `src/data_collection/tests/test_fresh_catalog_job.py` — sửa 2 test dùng KS không phòng làm mẫu (đổi sang combo), thêm 2 test cho quy tắc.
- `docs/spec/data-collection/schema.md` (khoá `noBookableRoom`), `src/data_collection/README.md` — sửa.
- Script ngoài git (thư mục ignored): `load_coverage.py`, `hide_unbookable_hotels.py` (gắn cùng dấu `noBookableRoom`) trong `src/data_collection/data/vm-repair-20261006/`.

## Kiểm tra quy tắc ẩn KS

- `pytest src/data_collection/tests`: 489 passed, 21 skipped.
- Chạy thử `apply_window` mới trên dữ liệu VM (sau khi nạp Agoda), trong bộ nhớ: đổi đúng 303 dòng, tất cả `hotel/property` bị tắt; không dòng nào khác đổi.

## Còn lại / rủi ro

- Người dùng chạy `hide_unbookable_hotels.py --apply` (ẩn 303 KS Agoda không phòng, có sao lưu).
- Code quy tắc mới phải lên VM (merge `test/newcrawl` → `release-mvp-v2`, deploy); trước đó job image cũ sẽ bật lại các KS đã ẩn tay.
- Sản phẩm mới chỉ tìm được qua vector sau bước index bằng image mới (e5, `ProductE5Small`).
- Tour booking nhiều chặng gắn một điểm đến theo trang nguồn; Đà Nẵng, Quy Nhơn, Hạ Long, Sa Pa vẫn ít tour có giá.
