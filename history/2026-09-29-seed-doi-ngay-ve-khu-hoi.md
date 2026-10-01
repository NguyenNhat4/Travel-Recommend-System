# Seed demo dời ngày vé khứ hồi vào cửa sổ 30 ngày

- Ngày: 2026-09-29
- Tác giả: Đăng Khôi / Claude Code
- Nhánh: test/newcrawl
- Trạng thái: hoàn thành
- Phạm vi: data, docs
- Thay thế: `2026-09-29-de-xuat-seed-doi-ngay-ve-khu-hoi.md` (đề xuất đã chốt và áp dụng)

## Mục tiêu

Người yêu cầu: vé khứ hồi cũng "không cố định ngày: seed dời ngày bay vào cửa sổ" như vé một chiều. Lý do: FE có vé khứ hồi đặt
được ở mọi ngày chạy `make demo-db-reset`. Chốt đề xuất
`docs/prd/update-archive/2026-09-29-seed-demo-doi-ngay-ve-khu-hoi.md` ngày 2026-09-29, kèm yêu cầu "không gắn thêm gì không
liên quan". Phục vụ FR-CAT-01, FR-CAT-03.

## File thay đổi

- `docs/prd/data-model.md` — sửa §3, đoạn vé báo giá ngày cố định:
  - job cào giữ ngày thật;
  - seed demo dời vé ngoài cửa sổ, hai chặng dời cùng số ngày, giá và `priceValidUntil` giữ nguyên.
- `src/data_collection/seed/load_products.py` — sửa `convert` và thêm các hàm `seed_fixed_flight_date`, `shift_fixed_flight`,
  `itinerary`, `_departure_day`:
  - ngày đi trong cửa sổ: giữ ngày thật, không xét hạn báo giá;
  - ngoài cửa sổ: dời theo `as_of + crc32(productId nhỏ nhất của hành trình) % 30`;
  - ô trùng hành trình khác cùng chuyến thì lùi sang ngày kế tiếp;
  - dời `returnFlight`, `returnDate` và ngày trong `name` / `description`; không thêm khoá.
- `src/data_collection/tests/test_flight_variants.py` — sửa: thay `test_loader_keeps_both_legs_and_expires_old_quotes` (luật cũ)
  bằng các test:
  - seed giữ ngày thật / dời hai chặng / không thêm khoá;
  - trường hợp ngày về mới trùng ngày đi cũ;
  - không dời hai hành trình vào cùng ngày, hạng vé dời cùng ngày;
  - job `apply_window` vẫn giữ ngày thật và khoá vé hết hạn.
- `docs/spec/MOCK_DATA_SPEC.md` — sửa §2 bước 1 và bảng "Ngày bay".
- `docs/spec/data-collection/schema.md` — sửa dòng `fixedDepartureDate`.
- `src/data_collection/snapshots/README.md` — sửa đoạn vé khứ hồi của snapshot `2026-09-29`.
- `docs/prd/update/2026-09-29-seed-demo-doi-ngay-ve-khu-hoi.md` → `docs/prd/update-archive/` — đổi tên (`git mv`): trạng thái
  `đã áp dụng`, bỏ `dateShifted`, ghi điều chỉnh khi chốt.
- `history/2026-09-29-seed-doi-ngay-ve-khu-hoi.md` — thêm: entry này.

## Quyết định

- Bỏ `attributes.dateShifted` theo người chốt; vé khứ hồi dời giống vé một chiều.
- Seed không khoá vé hết hạn báo giá. Code cũ (`fixed_flight_window`) khoá, nên seed từ 01/10 có 0 vé khứ hồi đặt được. Bảng số
  vé theo ngày seed đưa trong đề xuất trước đó đã bỏ sót điểm này.
- Job cào không đổi: `fresh_catalog_db.apply_window` vẫn dùng `fixed_flight_window`.
- Giữ một hành trình một thẻ `fareClasses`: hạng vé dời theo ID nhỏ nhất của nhóm; lùi ngày khi trùng ô.
  - Trước khi thêm, snapshot có 2–3 cặp hành trình trùng khoá khi seed ngày 15/10 và 05/11.

## Kiểm tra

- `pytest tests/test_flight_variants.py tests/test_seed_load_products.py`: pass.
- Kiểm test bắt được lỗi (tắt từng hành vi rồi khôi phục, `cmp` sạch): mỗi lần đều ≥ 1 test fail. Các hành vi đã tắt:
  - không dời chặng về;
  - không đổi `returnDate`;
  - không đổi tên;
  - luôn dời;
  - không dời;
  - bỏ kiểm trùng ô;
  - hạng vé dời riêng.
- `data_collection` `pytest tests`: 414 passed, 3 skipped.
- Snapshot `2026-09-29`, `convert` với as_of 29/09, 01/10, 15/10, 05/11, 25/11, 10/01/2027:
  - 290/290 vé khứ hồi đặt được;
  - 0 hành trình trùng khoá;
  - ngày trong tên, `returnDate`, chặng về khớp nhau.
- Seed đầy đủ vào database nháp (đã xoá sau khi kiểm):
  - as_of 2026-09-29: 290 vé khứ hồi đặt được; `db/verify.sql` 0 FAIL, `db/verify_insider.sql` 0 FAIL.
  - as_of 2026-11-25: FAIL `is_recommendable properties >= 300` và `future purchases inside window`. Code gốc (HEAD) cùng
    ngày cũng FAIL đúng hai dòng này: dữ liệu khách sạn của catalog không phủ ngày đó, không do thay đổi này.
- Khối seed-report trong `src/data_collection/README.md` được khôi phục sau các lần seed nháp (không đổi).

## Còn lại / rủi ro

- Giá vé bị dời là giá của ngày gốc (giá tham khảo). `fareClasses` báo `EXPIRED` từ 01/10.
- `vota` local đã nạp trước đó bằng `load_into_db` (luật job): chạy `make demo-db-reset` để có vé dời ngày.
- Chưa commit.
