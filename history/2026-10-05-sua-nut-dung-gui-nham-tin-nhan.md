# Sửa nút Dừng làm gửi nhầm tin đang gõ trong widget trợ lý

- Ngày: 2026-10-05
- Tác giả: Nguyễn Minh Nhật / Claude
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: frontend

## Mục tiêu

Khi agent đang xử lý, người dùng gõ chữ rồi bấm nút vuông (Dừng) thì tin đang gõ bị gửi đi.

## File thay đổi

- `src/frontend/src/features/itinerary/widget/WidgetComposer.tsx` — sửa: thêm `key="stop"` và `key="send"` cho hai nút để React không tái dùng một phần tử DOM.

## Quyết định

- Nguyên nhân suy ra từ code, chưa tái hiện trên trình duyệt: hai nút nằm ở cùng vị trí trong một ternary; bấm Dừng làm `busy=false`, React đổi nút đó từ `type="button"` sang `type="submit"` trước khi trình duyệt xử lý hành động mặc định của click, nên form submit. `key` riêng khiến React gỡ nút cũ và tạo nút mới.

## Kiểm tra

- `tsc --noEmit`: không lỗi. Chưa thử trên trình duyệt.

## Còn lại / rủi ro

- Cần thử tay: gõ chữ trong lúc agent chạy, bấm nút vuông, chữ phải còn nguyên trong ô nhập và không có tin mới nào được gửi.
