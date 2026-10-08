# Đóng widget trợ lý khi bấm "Xem giỏ"

- Ngày: 2026-10-05
- Tác giả: nhatnm / Claude
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: frontend

## Mục tiêu

Bấm "Xem giỏ" trên toast sau khi thêm sản phẩm từ widget trợ lý thì không có gì xảy ra với người dùng.

## File thay đổi

- `src/frontend/src/features/itinerary/widget/useFloatingWidget.ts` — sửa: đóng widget khi route chuyển sang `/cart` (trước chỉ đóng với `/checkout`).

## Quyết định

- Nguyên nhân: `router.push('/cart')` vẫn chạy, nhưng `AiFloatingWidget` nằm trong `AppShell` và phủ toàn màn hình khi mở rộng nên che trang giỏ. Lịch sử chat nằm trong state của hook, widget vẫn mounted nên mở lại không mất nội dung.
- Chỉ thêm `/cart`, không đóng ở mọi route để không đổi hành vi các luồng khác.
- Không lệch PRD (sửa hành vi UI cho đúng ý đồ của toast).

## Kiểm tra

- Chưa chạy trên trình duyệt; xem phần dưới.

## Còn lại / rủi ro

- Cần bấm thử trên UI.
