# Hiệu ứng vào cho tin nhắn gửi đi trong widget trợ lý

- Ngày: 2026-10-05
- Tác giả: Nguyễn Minh Nhật / Claude
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: frontend

## Mục tiêu

Sau khi "Xác nhận" form gợi ý gửi luôn (`2026-10-05-xac-nhan-form-goi-y-gui-luon.md`), người dùng muốn có hiệu ứng gửi đi như một tin nhắn gõ tay.

## File thay đổi

- `src/frontend/src/app/globals.css` — sửa: thêm keyframes `messageSendIn` và class `message-send-in` (tôn trọng `prefers-reduced-motion`).
- `src/frontend/src/features/itinerary/widget/WidgetChat.tsx` — sửa: bong bóng tin nhắn của người dùng dùng `message-send-in`.

## Quyết định

- Gửi từ form và gõ tay cùng đi qua `handleSendMessage` → `sendMessage(appendUser: true)`, nên một class chung phủ cả hai đường. Chỉ chỉnh giao diện, không lệch PRD.

## Kiểm tra

- `tsc --noEmit`: không lỗi. Chưa thử trên trình duyệt.

## Còn lại / rủi ro

- Mở lại hội thoại cũ cũng phát hiệu ứng cho các bong bóng người dùng (nhẹ, 0,22 giây).
- Form gợi ý vẫn biến mất ngay khi gửi (chỉ hiện ở tin mới nhất); chưa làm hiệu ứng thu gọn.
