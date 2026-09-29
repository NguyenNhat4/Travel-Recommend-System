# Đề xuất: seed demo dời ngày vé khứ hồi vào cửa sổ 30 ngày

- Ngày: 2026-09-29
- Tác giả: Đăng Khôi / Claude Code
- Nhánh: test/newcrawl
- Trạng thái: dang dở
- Phạm vi: docs

## Mục tiêu

Người yêu cầu: vé khứ hồi trong snapshot cũng "không cố định ngày: seed dời ngày bay vào cửa sổ". Hiện
`docs/prd/data-model.md` (dòng 264) ghi loader không dời ngày vé `fixedDepartureDate` → lệch PRD, cần đề xuất và chốt trước
(AGENTS.md mục 8).

## File thay đổi

- `docs/prd/update/2026-09-29-seed-demo-doi-ngay-ve-khu-hoi.md` — thêm: đề xuất, trạng thái `chờ chốt`.
- `history/2026-09-29-de-xuat-seed-doi-ngay-ve-khu-hoi.md` — thêm: entry này.

## Quyết định

- Đề xuất chỉ áp cho seed demo (snapshot / `make demo-db`), job cào trên VM vẫn giữ ngày thật.
- Dời cả hai chặng cùng số ngày, giữ `priceValidUntil`, gắn `dateShifted: true`.

## Kiểm tra

- Số vé khứ hồi đặt được theo ngày seed tính từ snapshot `2026-09-29` (bảng trong đề xuất).
- Chưa sửa code.

## Còn lại / rủi ro

- Chờ người yêu cầu chốt đề xuất; chưa sửa PRD, code hay spec.
