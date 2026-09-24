# Hiển thị form nhu cầu cùng lời chào đầu tiên của trợ lý

- Ngày: 2026-09-24
- Tác giả: Nguyễn Minh Nhật / Codex
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: frontend

## Mục tiêu

Hiển thị form chọn nhanh nhu cầu ngay cùng lời chào đầu tiên khi người dùng mở giao diện trợ lý du lịch. Điểm đến phải lấy từ `GET /api/v1/destinations`; form chỉ xuất hiện trước request đầu tiên của mỗi cuộc trò chuyện. Lời chào cần giải thích rằng thông tin càng đầy đủ thì đề xuất càng chính xác và sát nhu cầu.

## File thay đổi

- `src/frontend/src/components/assistant/AssistantTripStarter.tsx` — thêm: form khởi tạo chuyến đi, trạng thái tải/lỗi/rỗng và các lựa chọn điểm đến, thời lượng, nhóm đồng hành, phong cách.
- `src/frontend/src/services/destinations.ts` — thêm: service đọc danh sách điểm đến từ BFF route `/api/v1/destinations`, dùng type sinh từ OpenAPI và kiểm tra payload runtime.
- `src/frontend/src/components/assistant/AssistantConversation.tsx` — sửa: đặt form trong bong bóng chào đầu tiên, cập nhật lời chào và ẩn form ngay khi transcript có request đầu tiên.
- `src/frontend/src/components/assistant/AiFloatingWidget.tsx` — sửa: áp dụng cùng lời chào/form cho widget nổi; bỏ form làm rõ đầy đủ và fallback điểm đến hardcode ở các lượt sau; response cần thêm thông tin/không có kết quả hiển thị như message AI bình thường.
- `src/frontend/src/components/assistant/AssistantView.tsx` — sửa: không render card kết quả riêng cho response cần thêm thông tin hoặc không có kết quả; nội dung chỉ xuất hiện trong bong bóng chat.
- `src/frontend/tests/unit/destinationsService.test.ts` — thêm: kiểm tra route, method, cache và payload điểm đến không hợp lệ.
- `src/frontend/tests/unit/assistantTripStarter.test.tsx` — thêm: kiểm tra hiển thị ngay, dữ liệu điểm đến động, submit lựa chọn và retry khi tải lỗi.
- `src/frontend/tests/unit/assistantConversationStarter.test.tsx` — thêm: kiểm tra nội dung lời chào, gửi request từ form và form chỉ xuất hiện trước request đầu tiên.
- `history/2026-09-24-form-mo-dau-tro-ly.md` — thêm: ghi lịch sử thay đổi này.

## Quyết định

- Không lệch PRD: thay đổi hiện thực FR-AGT-01, hỗ trợ FR-AGT-03 và AC-AGT-01; không đổi OpenAPI hay backend.
- Form đầy đủ chỉ gắn với trạng thái transcript rỗng. Khi bắt đầu request đầu tiên, transcript không còn rỗng nên form biến mất; reset cuộc trò chuyện tạo một phiên mới và hiển thị lại lời chào/form.
- Không có danh sách điểm đến dự phòng hardcode. UI hiển thị rõ loading, error/retry hoặc empty nếu route không trả dữ liệu.
- Các lượt `NEEDS_CLARIFICATION` không dựng lại form khởi tạo; câu hỏi của backend hiển thị như một bong bóng chat bình thường để người dùng trả lời trong ô nhập.
- `NEEDS_CLARIFICATION` và `NO_RESULTS` chỉ hiển thị một bong bóng trả lời AI bình thường. Không render thêm card trong widget, transcript hoặc khu vực kết quả của trang `/assistant` để tránh lặp nội dung.
- Dùng service frontend qua BFF và type `DestinationListResponse` sinh từ OpenAPI theo hợp đồng tích hợp frontend.

## Kiểm tra

- `npx vitest run tests/unit/destinationsService.test.ts tests/unit/assistantTripStarter.test.tsx tests/unit/assistantConversationStarter.test.tsx`: PASS 8/8, 3 file.
- `npx eslint src/components/assistant/AiFloatingWidget.tsx src/components/assistant/AssistantConversation.tsx src/components/assistant/AssistantView.tsx src/components/assistant/AssistantTripStarter.tsx src/services/destinations.ts tests/unit/destinationsService.test.ts tests/unit/assistantTripStarter.test.tsx tests/unit/assistantConversationStarter.test.tsx`: PASS.
- `npm test -- --reporter=dot`: PASS 84/84, 15 file.
- `npx tsc --noEmit`: PASS.
- `npm run build:web`: PASS; Next.js 16.3.5 production build hoàn tất 9/9 static pages.
- `git diff --check`: PASS.

## Còn lại / rủi ro

- Chưa kiểm tra thủ công với backend thật trong trình duyệt; unit test đã mô phỏng đúng response contract của route điểm đến.
- Danh sách điểm đến phụ thuộc catalog backend. Nếu route trả mảng rỗng hoặc lỗi, form không cho submit và hiển thị trạng thái tương ứng.
