# Kiểm lại phần rà soát production mục 1, loại "TMS Quy Nhơn - Lee Xinh"

- Ngày: 2026-10-13
- Tác giả: Phạm Nguyễn Đăng Khôi / Claude (agent)
- Nhánh: test/newcrawl (worktree `~/code/Travel-Recommendation-Product-newcrawl`)
- Trạng thái: dang dở — job xong; production chưa sửa (chờ merge + deploy theo chốt của người dùng); mục 2, 4 chưa làm
- Phạm vi: data

## Mục tiêu

Người dùng (13/10 chiều): "xem thử đã tới đâu, kiểm tra lại", "nhớ test đầy đủ", "hỏi lại tôi nếu cần" — tiếp phần bàn giao
`docs/plan/2026-10-13-ban-giao-ra-soat-du-lieu-production.md` sau `history/2026-10-13-ten-soat-tay-va-loai-khach-san-kem-phong.md`.
FR-CAT-02, NFR-REL-01. Không lệch PRD (chỉ thêm dữ liệu soát tay theo cơ chế đã có).

## File thay đổi

- `src/data_collection/collectors/excluded_products.csv` — sửa: +1 dòng `trip:attraction:141833025` (tổng 45).
- `src/data_collection/tests/test_quality.py` — sửa: danh sách 13/10 có ref mới; căn hộ TMS thật (`booking:hotel:8466578`) không bị loại.
- `docs/plan/2026-10-13-ban-giao-ra-soat-du-lieu-production.md` — sửa: quyết định mới, bản xem trước production, cách chạy đủ test.
- `history/2026-10-13-kiem-lai-ra-soat-va-loai-tms-lee-xinh.md` — thêm.

## Quyết định

- Người dùng chốt: L'azur Cửa Lò (29 tin Booking) và căn hộ TMS Quy Nhơn giữ hết — các tin có ID riêng, giá khác nhau
  (600k–2,5 triệu), là căn hộ khác chủ trong cùng toà.
- Người dùng chốt loại `trip:attraction:141833025` "TMS Quy Nhơn - Lee Xinh". Bằng chứng (đọc production): `nameEn` "Dieu Tri
  Market", URL `dieu-tri-market-141833025`, giờ mở 04:00–12:00, nhưng địa chỉ 28 Nguyễn Huệ và toạ độ là toà căn hộ TMS; không giá.
  Bản ghi Trip bị trộn: đổi tên thành chợ thì toạ độ sai, giữ tên căn hộ thì sai loại → loại, không đổi tên.
- Người dùng chốt: chỉ sửa production sau khi `test/newcrawl` được merge vào `release-mvp-v2` và CD crawler deploy. Lý do: VM chạy
  code cũ (daily 13/10 08:45, #188); CD crawler chỉ deploy khi push `main`/`release-mvp-*`; code cũ không có 7 ref trong danh sách
  loại nên lượt daily có thể bật lại dòng đã ẩn tay. Tên đổi tay không bị ghi đè (upsert giữ `name`/`description` của dòng không phải
  vé máy bay), nhưng làm cùng đợt cho gọn.
- Đã đọc `fresh_catalog_db.apply_window` / `_hide_hotels_without_rooms`: với code mới, dòng đã ẩn không bị bật lại — không dòng nào
  mang `windowClosed`, ẩn kèm phòng con nên FR-CAT-02 không bật lại khách sạn, tuyến `trip:route:cah-han` 0 chuyến (quy tắc "vé có giá
  luôn đặt được" không áp).

## Kiểm tra

- `git rev-parse HEAD origin/test/newcrawl` (sau fetch): cùng `68c3b90a` trước thay đổi này.
- Production (tunnel, `default_transaction_read_only=on`): 6 ref của 13/10 sáng + Lee Xinh đang bán, 10 phòng con đang bán, 2 tên
  chưa đổi → bản xem trước: ẩn 17 dòng, đổi tên 2 dòng. `VW00613`, `booking:hotel:16986224` đang bán. Chưa ghi gì.
- `python -m pytest -q -p no:cacheprovider data_collection/tests` (từ `src/`, env vsf2) trước thay đổi, chỉ `DBX_TEST_DATABASE_URL`:
  687 passed, 18 skipped.
- Cùng lệnh, bật đủ mọi test DB thật trên DB nháp trong container local (đã xoá sau khi chạy; cách dựng ở plan §6), sau thay đổi:
  **704 passed, 1 failed, 0 skipped**. Lỗi duy nhất `test_stream_feed_db.py::StreamLoadRealDbTests::test_rows_loaded_separately_then_merged_leave_one_visible`
  có từ trước: cùng lỗi trên `70e142e2` và `origin/release-mvp-v2` (chạy từ `git archive`); test 29/09 dùng khách sạn không có hạng
  phòng, bị quy tắc FR-CAT-02 (06/10) tắt khi nạp.
- `test_simulated_business.py` cần bản sao DB có vé `demo:business:*` (trên schema rỗng lỗi `0 not greater than 0`): 10 passed.
  `test_release_flights.py` cần DB trống mới mỗi lần (DB đã có bảng → `DuplicateTable`): 6 passed.

## Còn lại / rủi ro

- Người dùng mở PR `test/newcrawl` → `release-mvp-v2` (merge không xung đột lúc kiểm), CD deploy; rồi viết script sửa production
  (xem trước → người dùng đồng ý trong chat → ghi 19 dòng) → "Bảo trì và index" → rà lại.
- Hỏi người dùng có sửa test cũ `test_rows_loaded_separately_then_merged_leave_one_visible` không (thêm một phòng vào dữ liệu test).
- Còn chờ: 2 cặp tour Booking cùng tên, nhóm A/B (điểm thu phí, sân golf không giá), mục 2 (121 tên tiếng Anh), mục 4 (toạ độ,
  Tuyên Quang).
