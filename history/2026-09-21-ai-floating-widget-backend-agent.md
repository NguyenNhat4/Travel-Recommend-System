# Kết nối AiFloatingWidget với Backend Itinerary Agent

- Ngày: 2026-09-21
- Tác giả: người yêu cầu / Antigravity
- Nhánh: release-mvp-v1
- Trạng thái: hoàn thành
- Phạm vi: frontend

## Mục tiêu

Chuyển đổi `AiFloatingWidget.tsx` từ cơ chế giả lập mock offline (`extractIntent`, `buildGroundedItinerary`, `setTimeout`) sang gọi trực tiếp backend itinerary agent qua `useAssistant()` và SSE stream (`/api/v1/assistant/itineraries/stream`), đúng theo yêu cầu chỉ sửa đổi trong phạm vi `AiFloatingWidget.tsx`.

## File thay đổi

- `src/frontend/src/components/assistant/AiFloatingWidget.tsx` — sửa: kết nối `useAssistant()`, chuyển đổi `ItineraryResponse` (`ItineraryCompleted`, `NEEDS_CLARIFICATION`) sang `GroundedPlan` để hiển thị trên timeline và `ItineraryMap`, hiển thị tiến trình LangGraph node stream thời gian thực, xử lý lỗi kèm nút thử lại (`retry()`).

## Quyết định

- Sử dụng `useAssistant()` từ `AssistantProvider` (đã được bọc ở `src/frontend/src/app/providers.tsx`) thay vì import dịch vụ mock cũ.
- Tự động chuyển đổi `ItineraryCompleted` sang cấu trúc `GroundedPlan` chuẩn để giữ nguyên toàn bộ giao diện giàu tính năng sẵn có (tabs ngày, thẻ visual khách sạn, ảnh visual hoạt động theo chặng, bản đồ Leaflet `ItineraryMap` với tọa độ GPS từ catalog).
- Khi backend trả `NEEDS_CLARIFICATION`: hiển thị `ClarificationCard` (HITL) để người dùng tinh chỉnh và gửi câu trả lời làm rõ trực tiếp tới backend agent.
- Khi đang streaming: hiển thị thông báo trạng thái kèm danh sách các bước LangGraph đang thực hiện theo thời gian thực (`classify_intent`, `retrieve_search`, `create_draft`...).

## Kiểm tra

- `npm run typecheck --prefix src/frontend` — PASS (0 lỗi TypeScript).
- `npm test --prefix src/frontend -- --run` — PASS (46/46 unit tests trong 9 files).
- `npm run lint --prefix src/frontend` — PASS (0 errors, không có warning mới trên `AiFloatingWidget.tsx`).
- `PYTHONDONTWRITEBYTECODE=1 python3 src/shared/contracts/tests/validate_contract.py` — PASS (70 schemas, 50 grounded products, 4 itinerary statuses).
- `npm run build:web --prefix src/frontend` — PASS (Next.js production build thành công).

## Còn lại / rủi ro

- Cần đảm bảo backend FastAPI agent được khởi động (ví dụ qua Docker hoặc `uvicorn`) khi test tương tác trực tiếp ngoài trình duyệt.
