# Thêm memory lịch sử chat cho Itinerary Agent

- Ngày: 2026-09-24
- Tác giả: nhatnm / Codex
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: agent, backend, docs

## Mục tiêu

Cho các node trong Itinerary Agent nhận được lịch sử chat của đúng conversation để hiểu các câu nối
tiếp của người dùng. Lịch sử phải được nạp ở `intake`, có mặt trong `AgentState`, dùng bởi các bước LLM
cần ngữ cảnh và được nối/lưu lại ở `finalize`, nhưng không được thay Search/Recommendation làm nguồn
giá, availability hoặc sản phẩm.

## File thay đổi

- `src/backend/app/agents/state.py` — sửa: thêm field nội bộ `conversation_history` riêng với field
  `messages` cũ của harness.
- `src/backend/app/agents/nodes.py` — sửa: nạp/làm sạch lịch sử ở `intake`, nối cặp user/assistant và
  lưu theo conversation ở `finalize`.
- `src/backend/app/agents/steps/history.py` — thêm: lọc role, chuẩn hóa và giới hạn lịch sử gần nhất.
- `src/backend/app/agents/steps/classification.py` — sửa: đưa lịch sử vào payload trích intent.
- `src/backend/app/agents/steps/conversation.py` — sửa: đưa lịch sử vào payload viết câu hỏi/trò chuyện.
- `src/backend/app/agents/steps/tool_planning.py` — sửa: đưa lịch sử vào payload lập tool plan.
- `src/backend/app/agents/steps/prompts.py` — sửa: coi lịch sử là dữ liệu không tin cậy và chỉ dùng để
  hiểu tham chiếu; message mới/intent chuẩn hóa vẫn có quyền cao hơn.
- `src/backend/tests/unit/agents/test_conversation_history.py` — thêm: test giới hạn/làm sạch, prompt,
  vòng đời lưu-nạp theo owner và tool planner.
- `docs/spec/agent/state-fields.md` — sửa: tài liệu hóa field `conversation_history` và phân biệt với
  `messages` của harness.
- `docs/spec/agent/langgraph-nodes.md` — sửa: tài liệu hóa lịch sử ở `intake`, các node LLM và
  `finalize`.
- `docs/spec/hop-dong-tich-hop-itinerary-assistant.md` — sửa: bổ sung quy tắc lưu, giới hạn, độ tin cậy
  và giới hạn process-local của adapter hiện tại.
- `docs/spec/agent/README.md` — sửa: cập nhật hành vi multi-turn và giới hạn store hiện tại.
- `docs/spec/agent/field-review.md` — sửa: thêm field mới vào snapshot review của `AgentState`.
- `docs/spec/agent/presentation-script.md` — sửa: cập nhật mô tả memory hội thoại.
- `docs/spec/agent/presentation-slides.html` — sửa: cập nhật slide kiến trúc về memory hội thoại.
- `history/2026-09-24-memory-lich-su-hoi-thoai-agent.md` — thêm: entry này.

## Quyết định

- Hiện thực FR-AGT-01 (hội thoại đa lượt), hỗ trợ FR-AGT-05; không đổi API contract hoặc DDL và không
  lệch PRD vì `docs/prd/data-model.md` đã mô hình hóa message theo conversation.
- Không tái sử dụng `messages`: field đó là append-only của harness. `conversation_history` là danh sách
  `{role, content}` bị ghi đè theo mỗi lượt để tránh reducer nhân đôi dữ liệu.
- Chỉ nhận role `user`/`assistant`; tối đa 20 message, 1.000 ký tự/message và 8.000 ký tự tổng. Khi vượt
  giới hạn, giữ một đoạn liên tục mới nhất và bỏ message cũ trước.
- Chỉ lưu lượt có user message thật; `intentOverride` không có message không tạo cặp chat giả.
- Lịch sử chỉ giúp hiểu tham chiếu trong `classify`, tool planner, `converse`, `clarify`. Giá,
  availability và sản phẩm vẫn phải tải lại qua tool ở lượt mới.
- Giữ nguyên TTL/owner isolation của `ConversationStorePort`. Adapter đang dùng là process-local nên
  restart backend sẽ mất lịch sử; chưa thêm adapter PostgreSQL trong task này.

## Kiểm tra

- Test đỏ trước khi code: collection lỗi `ModuleNotFoundError` cho module history mới — đúng kỳ vọng.
- `PYTHONDONTWRITEBYTECODE=1 LANGSMITH_TRACING=false .venv/bin/python -m pytest -q -p no:cacheprovider src/backend/tests/unit/agents/test_conversation_history.py`: 5 passed.
- Các file unit không đi qua graph: `test_classify.py` 7 passed; `test_contract_derived_models.py` 3
  passed; `test_lab_copy.py` 4 passed; `test_normalization.py` 7 passed;
  `test_recsys_agent_integration.py` 1 passed; `test_routing.py` 3 passed.
- `test_itinerary_tools.py`: chạy được 16 test rồi tiến trình không kết thúc trong 20 giây, exit 124 ở
  test graph cuối. Một test baseline trong `test_itinerary_runtime.py` cũng timeout 20 giây tại graph.
- `git diff --check`: pass.
- Ruff không có trong `.venv`, nên chưa chạy lint bằng Ruff.

## Còn lại / rủi ro

- `InMemoryConversationStore` chỉ bền trong một process. Muốn giữ lịch sử qua restart hoặc nhiều replica
  cần adapter riêng ghi `app.conversations`/`app.conversation_messages`; DDL đã có nhưng task này chưa
  triển khai.
- Suite có test LangGraph không thoát trong môi trường hiện tại; cần xử lý riêng vòng đời async/plugin
  trước khi lấy kết quả clean của toàn bộ suite.
