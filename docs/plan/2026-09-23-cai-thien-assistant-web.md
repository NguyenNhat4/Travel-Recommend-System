# Kế hoạch: cải thiện Itinerary Assistant trên web (`/assistant`)

- Ngày: 2026-09-23
- Phục vụ: FR-AGT-04, FR-AGT-05, AC-AGT-01 — `docs/prd/requirements.md` §1.4, §3
- Căn cứ: `docs/prd/user-flow.md` §1.2 bước 3–4, §3.2, §4.2; `docs/spec/hop-dong-tich-hop-frontend.md` §4.8, §5, §6
- Người làm: Nguyễn Minh Nhật / Claude Code, nhánh `feat/agent`

Chỉ sửa frontend, không đổi contract OpenAPI, không lệch PRD.

## Đã làm

| # | Bước | Kết quả |
|---|---|---|
| 1 | Nhãn hiển thị do client sở hữu | `components/assistant/assistantLabels.ts`: buổi, trạng thái ngân sách, loại nhóm khách, loại hoạt động, taxonomy, hậu tố giá, tên bước của graph |
| 2 | Thẻ sản phẩm có hành động | Link `/product/{productId}` (mở tab mới để giữ lịch trình), nút "Thêm vào giỏ" cho mục đủ điều kiện |
| 3 | Đặt trọn lịch trình + ngân sách | Nút "Thêm cả lịch trình vào giỏ", một toast tổng kết; thanh ngân sách khi có `budget` và `estimatedTotal` |
| 4 | Chỉnh nhanh (FR-AGT-05) | Bớt/Thêm 1 ngày qua `intentOverride.days`; "Đổi khách sạn", "Đổi lựa chọn khác" theo slot, "Giảm chi phí" qua tin nhắn soạn sẵn |
| 5 | Chữ hướng người dùng | Bỏ chữ "backend"/enum thô; banner cảnh báo giá cũ khi xem lịch trình đã lưu/chia sẻ |
| 6 | Bản đồ | Sửa map `SlotTime` (trước đây mọi slot thành `morning`); bỏ tọa độ giả ở tâm thành phố |
| 7 | Dọn code | Xoá bộ dựng lịch trình phía client (`extractIntent`, `buildGroundedItinerary`) không còn nơi gọi |

## Còn lại

- Thêm `coordinates` vào `ProductSummary` để bản đồ có dữ liệu thật — đổi contract, cần đề xuất `docs/prd/update/`.
- Giỏ hàng vẫn là state local trong `TravelContext`, chưa gọi `POST /cart/items`.
- `AiFloatingWidget.tsx` còn UI và hàm map riêng (vẫn đặt tọa độ mặc định); nên hợp nhất với `AssistantResultPanel`.
