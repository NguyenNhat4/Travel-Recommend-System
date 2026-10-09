# Vé Vinpearl trùng tên do biến thể giá thành viên: sửa gộp và ẩn 12 dòng trên production

- Ngày: 2026-10-08
- Tác giả: Pham Nguyen Dang Khoi / Claude Code
- Nhánh: fix/full-refresh-stable (worktree `Travel-Recommendation-Product-fullrefresh`)
- Trạng thái: hoàn thành (code chưa commit/deploy; DB production đã sửa bằng script, người dùng chạy)
- Phạm vi: data

## Mục tiêu

Người dùng thấy "[Grand World Phú Quốc] - Vé đi thuyền Venice (Water Taxi)" có 2 dòng trên production. Phục vụ FR-CAT-01
(mỗi sản phẩm một dòng), FR-CAT-03 (giá đúng). Không lệch PRD.

## Chẩn đoán (chỉ đọc qua API monitor)

- Hai dòng VW02818 (188.000 đ, thấy 08/10) và VW02833 (182.000 đ, thấy 02/10). Lượt VM mới nhất: VW02818 = "[VIN33 - Gold]",
  VW02833 = "[VIN33 - Platinum]" — cùng một vé, biến thể giá thành viên. `normalise.merge_member_variants` gộp về một vé (giá
  cao nhất khi không có vé thường); dòng biến thể đã nạp riêng ở lượt 01–02/10 không bao giờ được xuất lại nên nằm nguyên trong
  DB, `available = true`.
- Production 08/10: 10 vé, 12 dòng thừa (VinWonders Phú Quốc 3 dòng 1.050.000 / 987.000 / 955.500 đ, Safari Phú Quốc 3 dòng,
  Nam Hội An, Cửa Hội, Vũ Yên, Grand World…).

## File thay đổi

- `src/data_collection/normalise.py` — sửa: `merge_member_variants` ghi ref của biến thể bị gộp vào `sameAs` của vé đại diện
  (không lặp ref đã có) → bước nạp DB đánh dấu dòng biến thể cũ `mergedInto` và tắt bán theo cơ chế ghép sẵn có.
- `src/data_collection/tests/test_member_variants.py` — thêm: 3 test (sameAs khi gộp, vé thường giữ ref không lặp, dòng biến
  thể cũ trong DB bị gộp đi và ẩn qua `prepare_rows`).
- `src/data_collection/tests/fixtures/normalise_sample/expected_products.jsonl` — sửa: vé VW02873 có thêm
  `sameAs: ["vinpearl:tour:VW02874"]` (so lại: không khác gì ngoài `sameAs`).
- Ngoài git (thư mục `data/` bị ignore, repo chính): `src/data_collection/data/vm-repair-20261008/hide_member_dups.py` — nhóm vé
  Vinpearl đang bán cùng tên + điểm đến; dòng thấy gần nhất (duy nhất) giữ và nhận ref dòng kia vào `sameAs`; dòng kia
  `mergedInto`, bỏ `availability`, `available = false`; không xoá; sao lưu trước; mặc định chạy thử + rollback, `--apply
  --expect N`; khoá `pg_advisory_xact_lock(7791024)`.

## Quyết định

- Người dùng chọn sửa code + ẩn ngay trên DB (không chờ deploy).
- Giữ cách chọn vé đại diện hiện có (vé thường, không có thì giá cao nhất); giá hạng được chọn là `unitPrice`, các hạng khác ở
  `memberPrices` (như production).

## Kiểm tra

- `pytest tests/test_member_variants.py tests/test_normalise_steps.py tests/test_normalise_stream.py`: 39 passed; cả bộ 578 passed.
- Script trên máy local: chạy thử trên `vota_prodcopy` (bản sao 07/10): 4 nhóm sửa, 6 bỏ qua (cả hai dòng cùng thấy 02/10 ở bản
  sao cũ); `--apply --expect 4` trên bản sao tạm `vota_dupfix_test`: đúng 4 dòng ẩn, keeper nhận `sameAs`; chạy
  `maintain_catalog` của code đang chạy trên VM (decccec) lên bản sao đó: dòng ẩn vẫn ẩn; bản sao tạm đã xoá.
- Production (người dùng chạy qua tunnel 15432, role `vota_db_dev`): chạy thử 10 nhóm · 12 dòng ẩn · 0 bỏ qua · 0 giỏ/đơn trỏ
  tới · còn 0 nhóm trùng; rồi `--apply --expect 12` (COMMITTED). Kiểm lại qua API monitor (17.679 dòng): 0 nhóm vé Vinpearl
  trùng tên đang bán; 12 dòng ẩn `available = false`, `mergedInto` đúng vé giữ, không còn `availability`; 10 vé giữ đang bán,
  `sameAs` đủ ref.

## Còn lại / rủi ro

- Vector Weaviate của 12 dòng ẩn bị dọn ở bước index của lượt cào kế tiếp; backend nạp lại catalog trong 15 phút.
- Rà toàn catalog còn 29 nhóm trùng tên đang bán khác (26 khách sạn chủ yếu Booking + Agoda chưa ghép được, 3 điểm tham quan);
  chưa xử lý, cần xem từng nhóm (có thể là cơ sở khác nhau thật).
