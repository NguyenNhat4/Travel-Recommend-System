# Ép planner của node `tool` luôn gọi tool

- Ngày: 2026-10-01
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/itinerary-agent-guardrails
- Trạng thái: hoàn thành
- Phạm vi: agent, docs

## Mục tiêu

Sau bản sửa `history/2026-10-01-khong-hoi-lai-khi-rut-lai-yeu-cau-doi.md`, "không đổi nữa" đi đúng `extract → tool`
nhưng người dùng nhận lỗi "Chưa thể lập kế hoạch truy vấn hợp lệ". Trace LangSmith `nhat-10-1`, thread
`5d2595e5-9a2c-440f-bd16-c9ce82130b3c`: LLM lập plan (gpt-4o-mini, `bind_tools` không ép) trả câu chat "Bạn có muốn đổi
điểm đến không?..." thay vì tool call → plan rỗng → `INVALID_TOOL_PLAN` (không retryable) → `evaluate` `failed` →
`dead_letter`. Phục vụ FR-AGT-01, NFR-REL-01 (truy xuất vẫn chỉ qua Search/Recommendation).

## File thay đổi

- `src/backend/app/agents/steps/tool_planning.py` — sửa: `build_plan` gọi `bind_tools(definitions, tool_choice="any")`.
- `src/backend/app/application/ports/llm.py` — sửa: `ChatModelPort.bind_tools` nhận `tool_choice` (keyword, mặc định `None`).
- `src/backend/tests/unit/agents/test_itinerary_runtime.py` — sửa: LLM giả ghi `tool_choice`; kiểm planner nhận `"any"`.
- `src/backend/tests/unit/agents/test_itinerary_tools.py`, `src/backend/tests/unit/agents/test_conversation_history.py`, `src/backend/tests/contract/test_assistant_contract.py` — sửa: LLM giả nhận tham số `tool_choice`.
- `docs/spec/agent/langgraph-nodes.md` — sửa: dòng node `tool` ghi planner bắt buộc gọi ít nhất một tool.

## Quyết định

- Sửa gốc ở lời gọi LLM (`tool_choice="any"`) thay vì coi plan rỗng là "search theo điểm đến": test hiện có cố ý giữ plan rỗng là `INVALID_TOOL_PLAN`, và node `tool` không có trường hợp hợp lệ nào không gọi tool. `"any"` là giá trị LangChain hiểu cho cả OpenAI (đổi thành `required`), Anthropic và Gemini.
- `validated_plan` vẫn tự thêm search cho các loại hotel/attraction/golf còn thiếu, nên plan một lời gọi vẫn phủ đủ.

## Kiểm tra

- Chạy planner với LLM thật trong `.env` (gpt-4o-mini), lịch sử như trace (Phú Quốc 1 ngày, 2 người lớn, lượt trước hỏi đổi điểm đến), mỗi câu 10 lần:
  - Không ép: "không đổi nữa" → 0 tool call 10/10; "thôi giữ nguyên" → 0 tool call 9/10.
  - `tool_choice="any"`: hai câu trên → 1 tool call 10/10; "Lên lịch trình 1 ngày tại Phú Quốc" → 3 tool call 10/10 (như khi không ép).
- `.venv/bin/python -m pytest -q src/backend/tests/unit/agents src/backend/tests/architecture src/backend/tests/contract`: 367 passed.

## Còn lại / rủi ro

- Chưa chạy lại cả lượt qua UI; chưa thêm ca "đổi điểm đi" → "không đổi nữa" vào golden eval G-079.
- Chưa thử với provider Gemini/Anthropic thật.
