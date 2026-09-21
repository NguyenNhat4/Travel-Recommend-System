# Route hội thoại chung qua LLM answer

- Ngày: 2026-09-19
- Tác giả: người dùng / Codex
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: backend, agent

## Mục tiêu

Đảm bảo lời chào, lời cảm ơn và yêu cầu gợi ý du lịch còn thiếu thông tin được node `answer` trả lời bằng LLM, không gọi tool sản phẩm trước khi có `destination` và `days`.

## File thay đổi

- `src/backend/app/agents/models.py` — sửa: thêm loại phân loại nội bộ `conversation` và structured output cho câu trả lời hội thoại.
- `src/backend/app/agents/state.py` — sửa: lưu `interaction_type` thô trong graph state.
- `src/backend/app/agents/nodes.py` — sửa: phân loại hội thoại chung, dựng prompt an toàn và gọi LLM tại `answer`; giữ fallback xác định khi provider lỗi.
- `src/backend/app/agents/routing.py` — sửa: route trường hợp thiếu thông tin qua `answer` để LLM tạo câu hỏi làm rõ.
- `src/backend/tests/unit/agents/test_itinerary_runtime.py` — sửa: thêm regression test cho lời chào, gợi ý chung và xác nhận không gọi product tools.
- `src/backend/tests/unit/agents/test_routing.py` — sửa: đồng bộ kỳ vọng conditional route mới.

## Quyết định

- Dùng nhánh LangGraph tường minh `classify -> answer -> finalize` cho `conversation`; không nhét việc sinh câu trả lời vào node classify.
- `answer` dùng structured output giới hạn 500 ký tự và nhận state thô gồm message, intent đã biết, trường còn thiếu và loại tương tác.
- LLM không được tuyên bố đã search, recommendation, kiểm tra availability hoặc booking khi tool chưa chạy; không được nêu sản phẩm cụ thể.
- Nếu LLM lỗi, backend vẫn trả câu hỏi làm rõ cố định theo contract; không gọi tool và không tạo dữ liệu sản phẩm.

## Kiểm tra

- Unit test routing và classify: 8/8 pass.
- Regression test lời chào: pass; đúng chuỗi gọi `Extraction`, `ConversationalAnswer`, không gọi tool.
- Regression test gợi ý chung: pass; trả `NEEDS_CLARIFICATION`, không gọi tool.
- Graph topology assertion cho `classify -> answer -> finalize`: pass.
- Python compile các file thay đổi: pass.
- `git diff --check`: pass.
- Toàn file `test_itinerary_runtime.py` chưa kết thúc sạch vì runner giữ task/thread sau khi test đã in `ok`; đây là rủi ro teardown đã được ghi nhận từ trước, không phải assertion fail của thay đổi này.

## Còn lại / rủi ro

- Chất lượng câu chữ thực tế vẫn phụ thuộc model/provider; cần smoke test qua `make chat` với key hợp lệ.
- Fallback xác định vẫn cần thiết để API có phản hồi hợp lệ khi LLM timeout hoặc structured output sai.
