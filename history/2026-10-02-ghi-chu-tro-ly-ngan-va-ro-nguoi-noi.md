# Ghi chú trợ lý ngắn và rõ người nói trong ngữ cảnh LLM

- Ngày: 2026-10-02
- Tác giả: nhatutc2 / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: agent, docs

## Mục tiêu

Payload `classify` trong trace LangSmith `nhat-10-1` (02/10, tin "đi đâu cũng được", chuyến Nha Trang) có ba vấn đề:
- Ghi chú lịch trình "gửi lịch trình Nha Trang 3 ngày: Vinpearl…, Hòn Tre, VinWonders…" lặp ở mỗi lượt lịch trình, lặp tiếp ở `last_assistant_message` và trùng với `previous_selection`.
- `conversation_history` là cặp `role:`/`content:` phẳng, nên LLM dễ đọc nhầm ghi chú của trợ lý thành lời người dùng.
- Người dùng yêu cầu rút ngắn và làm rõ người nói.

Phục vụ FR-AGT-01 (hội thoại đa lượt). Không lệch PRD: chỉ đổi cách trình bày ngữ cảnh nội bộ gửi LLM, không đổi contract hay hành vi sản phẩm.

## File thay đổi

- `src/backend/app/agents/steps/history.py` — sửa: `llm_context.conversation_history` mỗi mục một khoá theo người nói (`user` nguyên văn, `assistant_did` ghi chú).
- `src/backend/app/agents/steps/turn_notes.py` — sửa: ghi chú lịch trình bỏ tên sản phẩm; xoá `_itinerary_names`, `MAX_NOTE_PRODUCTS`.
- `src/backend/app/agents/steps/messages.py` — sửa: `note_itinerary` (vi/en) không còn `{products}`.
- `src/backend/app/agents/steps/prompts.py` — sửa: `CLASSIFY_PROMPT`, `EXTRACT_PROMPT`, `CONVERSATION_PROMPT` giải thích khoá `user`/`assistant_did`; `assistant_did` không bao giờ là lời người dùng.
- `src/backend/tests/unit/agents/test_turn_context.py` — sửa: kỳ vọng ghi chú ngắn và định dạng mới; thêm test không còn `role:`/`content:` trong payload.
- `src/backend/tests/unit/agents/test_conversation_history.py`, `test_reply_titles.py`, `test_classify.py` — sửa: kỳ vọng định dạng mới.
- `docs/spec/agent/langgraph-nodes.md`, `docs/spec/agent/state-fields.md` — sửa: mô tả định dạng `conversation_history` trong ngữ cảnh LLM.

## Quyết định

- Khoá theo người nói thay cho `role`/`content`: một dòng YAML `- user: …` / `- assistant_did: …` vừa ngắn vừa không thể lẫn người nói. Bản lưu trong store vẫn giữ `role`/`content`/`note`, chỉ bản gửi LLM đổi.
- Tên sản phẩm chỉ còn ở `previous_selection` (lịch gần nhất, kèm id). Đây cũng là nguồn duy nhất LLM được dùng để loại/đổi món. Sản phẩm của các lịch cũ hơn không còn trong ngữ cảnh.
- Giữ `last_assistant_message`: với lịch trình nó giờ chỉ là ghi chú ngắn, còn với câu hỏi lại vẫn nguyên văn để hiểu câu trả lời ngắn.
- Ghi chú đã lưu trước thay đổi này vẫn còn danh sách sản phẩm cho tới khi hội thoại hết hạn; không viết code chuyển đổi.

## Kiểm tra

- Test mới và test sửa fail trên code cũ (7 fail), pass sau khi sửa.
- `.venv/bin/python -m pytest -q src/backend/tests/unit/agents src/backend/tests/unit/domain`: 615 passed.
- `.venv/bin/python -m pytest -q src/backend/tests`: 1102 passed, 21 skipped.
- Chưa chạy golden với LLM thật; chưa thử trên UI.

## Còn lại / rủi ro

- Cần chạy golden (`src.evaluation.agent.golden`) để đo ảnh hưởng thật lên phân luồng và trích intent.
- `TOOL_PLAN_PROMPT`, `NARRATE_PROMPT`, `DESTINATION_PROMPT` cũng nhận ngữ cảnh này nhưng chưa thêm câu giải thích khoá; chúng chỉ dùng lịch sử để hiểu tham chiếu.
