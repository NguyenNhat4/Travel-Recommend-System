# Xoá nút lưu hành trình (bookmark) khỏi widget lịch trình

- Ngày: 2026-09-29
- Tác giả: Nguyễn Minh Nhật / Claude Sonnet 5
- Nhánh: feat/itinerary-agent-guardrails
- Trạng thái: hoàn thành
- Phạm vi: frontend

## Mục tiêu

Người dùng yêu cầu xoá nút bookmark (lưu hành trình) cạnh nút "Thanh toán" trong footer
`WidgetPlanPanel`. Nút này chỉ toggle state cục bộ `isSavedPlan` trong React (không gọi API, không
có bảng lưu trữ nào ở backend), và log console người dùng gửi kèm cho thấy nó là nguồn của warning
React thật: `Cannot update a component (TravelProvider) while rendering a different component
(FloatingWidget)` — do `handleToggleSavePlan` gọi `showToast` (setState của `TravelContext`) ngay
trong lúc render thay vì trong một event handler đã commit.

## File thay đổi

- `src/frontend/src/features/itinerary/widget/WidgetPlanPanel.tsx` — sửa: xoá nút bookmark trong
  footer, bỏ import `Bookmark` (lucide-react) và hai biến `isSavedPlan`/`handleToggleSavePlan`
  không còn dùng.
- `src/frontend/src/features/itinerary/widget/useFloatingWidget.ts` — sửa: xoá toàn bộ
  `isSavedPlan`/`setIsSavedPlan`/`handleToggleSavePlan` — không còn UI nào gọi tới sau khi xoá nút
  ở trên (xác nhận bằng grep, không còn tham chiếu nào trong `src/frontend/src`). Loại bỏ luôn 3 lần
  reset `setIsSavedPlan(false)` (đổi lịch trình, hội thoại mới, mở lại hội thoại cũ) và field tương
  ứng khỏi object trả về của hook.

## Quyết định

- Xoá hẳn thay vì chỉ ẩn nút: tính năng không có backing thật (không gọi API `/bookings` hay bảng
  nào), chỉ là toggle UI cục bộ mất khi refresh — không có gì để giữ lại dưới dạng dữ liệu.
- Dọn theo chuỗi phụ thuộc đến hết (import → destructure → state → 3 nơi reset → object trả về của
  hook), không để lại biến chết, vì không còn UI nào tiêu thụ.

## Kiểm tra

- `cd src/frontend && npx tsc --noEmit` → sạch.
- `cd src/frontend && npm test` → **141 passed** (24 file) — không có test nào phủ tính năng bookmark
  này nên không mất coverage.

## Còn lại / rủi ro

- Không có.
