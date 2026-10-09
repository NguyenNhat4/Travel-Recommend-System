# Đề xuất: Xác nhận form gợi ý thì gửi luôn

- Ngày: 2026-10-05
- Tác giả: Nguyễn Minh Nhật / Claude
- Nhánh: feat/agent
- Trạng thái: dang dở
- Phạm vi: frontend, docs

## Mục tiêu

Người dùng muốn bấm "Xác nhận" ở form gợi ý thông tin chuyến đi thì gửi luôn, thay vì chỉ đặt câu vào ô nhập. PRD hiện quy định "không tự gửi" nên đây là thay đổi lệch PRD, cần đề xuất được chốt trước (AGENTS.md mục 8).

## File thay đổi

- `docs/prd/update/2026-10-05-xac-nhan-form-goi-y-gui-luon.md` — thêm: đề xuất, trạng thái chờ chốt.

## Quyết định

- Chưa sửa code và chưa sửa PRD. Dừng chờ người dùng chốt.

## Kiểm tra

- Không có (chỉ thêm tài liệu).

## Còn lại / rủi ro

- Sau khi chốt: cập nhật PRD, sửa `handleConfirmTripDetails` trong `useFloatingWidget.ts`, chuyển đề xuất sang `docs/prd/update-archive/`, ghi entry mới.
