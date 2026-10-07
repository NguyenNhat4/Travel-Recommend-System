# Ô gõ điểm đến để trống khi chọn chip

- Ngày: 2026-10-06
- Tác giả: Nguyễn Minh Nhật / Claude
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: frontend

## Mục tiêu

Ở form gợi ý, bấm chip điểm đến (ví dụ "Hải Phòng") thì ô "Hoặc nhập điểm đến khác…" bị điền luôn tên chip, vì ô gõ và chip dùng chung `intent.destination`. Ô gõ phải để trống (hiện placeholder) khi điểm đến đến từ chip.

## File thay đổi

- `src/frontend/src/components/assistant/TripDetailsForm.tsx` — sửa: thêm cờ `typedDestination`; ô gõ chỉ hiện chữ người dùng tự gõ, chip chỉ sáng khi điểm đến chọn từ chip.

## Quyết định

- Giữ một nguồn giá trị `intent.destination` (câu gửi đi không đổi); chỉ tách cách hiển thị. Gõ trùng tên chip vẫn giữ chữ trong ô, không nhảy sang chip.
- Không lệch PRD: chỉ sửa hiển thị form, không đổi hành vi xác nhận/contract.

## Kiểm tra

- `npx tsc --noEmit` (src/frontend): không lỗi. Chưa thử bằng tay trên trình duyệt.

## Còn lại / rủi ro

- Không có.
