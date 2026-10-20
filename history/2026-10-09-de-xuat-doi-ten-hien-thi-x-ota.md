# Đề xuất đổi tên hiển thị V-OTA sang X-OTA

- Ngày: 2026-10-09
- Tác giả: mihhquan / Claude Code
- Nhánh: feat/fix-bug
- Trạng thái: dang dở
- Phạm vi: docs, frontend

## Mục tiêu

Người dùng yêu cầu refactor các chỗ giao diện hiển thị tên V-OTA thành X-OTA. PRD (`docs/prd/user-flow.md`) và
`docs/spec/product.md` ghi tên V-OTA, nên thay đổi lệch PRD và cần đề xuất được chốt trước khi sửa source (AGENTS.md mục 8).

## File thay đổi

- `docs/prd/update/2026-10-09-doi-ten-hien-thi-x-ota.md` — thêm: đề xuất, trạng thái `chờ chốt`.
- `history/2026-10-09-de-xuat-doi-ten-hien-thi-x-ota.md` — thêm: entry này.

## Quyết định

- Chưa sửa source. Đã khảo sát bằng `grep`: khoảng 88 dòng chứa "V-OTA" trong `src/frontend` (kể cả test), 3 mock và `errors.py`
  trong phần backend/shared có câu chữ hiển thị trên UI.
- Đề xuất chỉ đổi chữ hiển thị, giữ tên kỹ thuật (`vota` DB/role, khoá lưu trữ, package).

## Kiểm tra

- Không chạy lệnh kiểm tra (chỉ thêm tài liệu).

## Còn lại / rủi ro

- Chờ người dùng chốt đề xuất và trả lời 3 câu hỏi trong đó (phương án tài liệu A/B, tên khách sạn mẫu, tên pháp nhân ở chân trang).
- Sau khi chốt: cập nhật PRD trước, rồi sửa source, chạy test frontend và `validate_contract.py`, chuyển đề xuất sang `docs/prd/update-archive/`.
