# Thẻ lịch trình hiện buổi thay cho khung giờ

- Ngày: 2026-10-01
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/itinerary-agent-guardrails
- Trạng thái: hoàn thành
- Phạm vi: frontend

## Mục tiêu

Thẻ hoạt động trong khung lịch trình (widget bên phải) đang hiện khung giờ bịa sẵn như `08:00 - 11:30`. Người dùng yêu cầu bỏ giờ, hiện "Buổi sáng"/"Buổi chiều" cho khớp với lời kể của agent.

## File thay đổi

- `src/frontend/src/features/itinerary/widget/WidgetDays.tsx` — sửa: nhãn thẻ là `Buổi sáng/trưa/chiều/tối` theo `slot.time`, bỏ khung giờ cứng.
- `src/frontend/src/features/itinerary/widget/widgetPlan.ts` — sửa: map `SlotTime` của API (`MORNING`...) sang `morning`... qua `SLOT_TIME_FROM_API`; bỏ bảng khung giờ mặc định và `timeRange`.
- `src/frontend/src/services/assistant.ts` — sửa: export `SLOT_TIME_FROM_API` để dùng lại.
- `src/frontend/tests/unit/widgetPlan.test.ts` — sửa: pointId dùng `time` chữ thường; thêm test map buổi.

## Quyết định

- Contract chỉ có `SlotTime` (buổi), không có giờ cụ thể; khung giờ hiển thị trước đây là số bịa ở frontend nên bỏ.
- Lỗi kèm theo: `widgetPlan.ts` gán thẳng `s.time` viết hoa nên mọi slot rơi về fallback `08:00 - 11:30` (cả slot chiều) và icon buổi trên bản đồ luôn là 🌙. Map sang chữ thường đúng với kiểu `ItinerarySlot['time']` sửa cả hai.

## Kiểm tra

- `npx vitest run` (src/frontend): 406/406 pass.
- `npx tsc --noEmit`: chỉ còn 3 lỗi cũ trong `.next/types` (route assistant đã xoá), không liên quan.

## Còn lại / rủi ro

- Chưa kiểm tra trực quan trên trình duyệt.
