# Render câu trả lời thật từ Agent API

- Ngày: 2026-09-19
- Tác giả: người dùng / Codex
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: evaluation

## Mục tiêu

Hiển thị câu trả lời thực tế trong response API ở chat thay vì câu fallback chung của UI; JSON chỉ mở khi người dùng cần kiểm tra.

## File thay đổi

- `src/evaluation/agent/streamlit_app.py` — sửa: render `error.message`, `question` hoặc `message` theo đúng response union; để JSON trong expander đóng mặc định.

## Quyết định

- UI không tự viết lại nội dung Agent. ErrorResponse đọc từ `error.message`; clarification đọc `question`; no-results/fallback đọc `message`; completed tiếp tục render itinerary có cấu trúc.
- Hiện `requestId` của lỗi ở caption để đối chiếu diagnostic log.

## Kiểm tra

- Unit render với ErrorResponse: hiện đúng message API và requestId.
- Streamlit `AppTest`: pass, không có exception.
- `git diff --check`: pass.

## Còn lại / rủi ro

- `ItineraryCompleted` hiện không có trường narration/message trong contract; UI render trực tiếp itinerary thay vì tự tạo lời văn ngoài API.
