# Sửa lỗi lint react-hooks/refs ở WidgetStayOptions

- Ngày: 2026-10-09
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: frontend

## Mục tiêu

Check "Frontend quality checks" của PR #124 fail ở bước Lint: 5 lỗi `react-hooks/refs` (đọc/ghi `ref.current` trong lúc render) ở `WidgetStayOptions.tsx`.

## File thay đổi

- `src/frontend/src/features/itinerary/widget/WidgetStayOptions.tsx` — sửa: thứ tự thẻ "lần hiện đầu tiên" giữ bằng `useState` (cập nhật trong lúc render) thay cho `useRef`.

## Quyết định

- Giữ nguyên hành vi (thứ tự thẻ không đảo chỗ khi backend đưa lịch đang chọn lên đầu); chỉ đổi cách lưu.

## Kiểm tra

- `eslint .`: 0 lỗi (còn 3 warning sẵn có). `tsc --noEmit`: sạch. `vitest run tests/unit`: 749/749 pass.

## Còn lại / rủi ro

- Chưa chạy e2e Playwright cho hàng thẻ "Phương án khác".
