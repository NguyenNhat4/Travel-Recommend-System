# Tiếp tục chuyến đi sau khi điểm đến không được hỗ trợ

- Ngày: 2026-09-20
- Tác giả: người dùng / Claude
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: agent, contract, docs, evaluation

## Mục tiêu

Người dùng nói `tokyo 4 ngày từ ngày mai`, nhận `UNSUPPORTED_DESTINATION`, rồi trả lời `ha noi` thì agent hỏi lại số ngày. Nguyên nhân: `finalize` chỉ lưu intent khi HTTP 200, và `ErrorResponse` không có `conversationId` nên client mở hội thoại mới ở lượt sau.

## File thay đổi

- `src/backend/app/agents/nodes.py` — sửa: `details.conversationId` trong lỗi `UNSUPPORTED_DESTINATION`; `finalize_node_async` lưu intent (đặt `destination=null`) cho riêng lỗi này.
- `src/backend/tests/unit/agents/test_itinerary_runtime.py` — sửa: test `tokyo 4 ngày` rồi `Nha Trang` ra COMPLETED giữ `days`/`startDate`; test chỉ nói số ngày thì hỏi lại `destination`.
- `src/evaluation/agent/streamlit_app.py` — sửa: `conversation_id_of` lấy `conversationId` từ body hoặc `error.details`.
- `src/shared/contracts/schemas/common.yaml` — sửa: mô tả `details` của `UNSUPPORTED_DESTINATION` thêm `conversationId`.
- `src/shared/mocks/assistant/createItinerary.422-unsupported-destination.json` — sửa: thêm `details.conversationId`.
- `docs/spec/hop-dong-tich-hop-itinerary-assistant.md` — sửa: bảng lỗi §4.
- `docs/spec/hop-dong-tich-hop-frontend.md` — sửa: xử lý lỗi và §9.4.
- `src/evaluation/agent/README.md` — sửa: mô tả node `tool`.
- `history/2026-09-20-resume-after-unsupported-destination.md` — thêm: entry này.

## Quyết định

- Giữ HTTP 422 và mã lỗi; chỉ thêm khóa vào `details` (`additionalProperties: true`), tương thích ngược trong v1. Không chọn đổi sang 200 `NEEDS_CLARIFICATION` vì đổi semantics contract v1.
- Xóa `destination` trước khi lưu để lượt sau chỉ có số ngày vẫn bị hỏi lại điểm đến.
- Chỉ áp dụng cho `UNSUPPORTED_DESTINATION`; `INVALID_TRIP_DURATION` và `LLM_UNAVAILABLE` giữ hành vi cũ.
- Ý tưởng cho v2: đưa các lỗi người dùng tự sửa được (điểm đến, số ngày) vào `NEEDS_CLARIFICATION` có `reason`, để mọi lượt hội thoại đều có `conversationId`.

## Kiểm tra

- `LANGSMITH_TRACING=false pytest src/backend/tests`: 95 passed.
- `validate_contract.py`: PASS (63 schemas, 50 grounded products, 4 itinerary statuses…).
- `conversation_id_of` chạy thử: body có ID, ID trong `error.details`, không có ID.
- `git diff --check`: pass.

## Còn lại / rủi ro

- Chưa chạy thật với model và Streamlit trên trình duyệt; chưa có AppTest cho `conversation_id_of`.
- `startDate` đã đổi sang ngày tuyệt đối ở lượt đầu; quay lại sau khi qua ngày (trong TTL 24 giờ) có thể lệch.
- `INVALID_TRIP_DURATION` (ví dụ `Nha Trang 10 ngày`) và `LLM_UNAVAILABLE` ở bước chọn điểm đến vẫn mất ngữ cảnh.
