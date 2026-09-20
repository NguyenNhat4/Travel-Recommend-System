# Thêm diagnostic log cho Agent demo

- Ngày: 2026-09-19
- Tác giả: người dùng / Codex
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: backend, evaluation

## Mục tiêu

Giữ đủ context kỹ thuật để chẩn đoán lỗi phát sinh khi người dùng test FastAPI, LangGraph và Streamlit, đồng thời tránh ghi prompt, JWT hoặc raw graph state.

## File thay đổi

- `Makefile` — sửa: `make chat` tee log của hai process vào `.logs/agent-demo.log`; thêm `make chat-logs`.
- `src/backend/app/api/v1/routes/assistant.py` — sửa: log lifecycle request/SSE, từng node và stack trace lỗi với request/run/conversation correlation IDs.
- `src/backend/app/agents/nodes.py` — sửa: giữ exception gốc của classify/composition LLM thay vì chỉ trả mã tổng quát `LLM_UNAVAILABLE`.
- `src/evaluation/agent/streamlit_app.py` — sửa: log stack trace khi API request từ UI thất bại.

## Quyết định

- Log chỉ chứa metadata chẩn đoán: requestId, runId, conversationId, transport, node, outcome, duration, status và retry count.
- Không log message người dùng, prompt/model output nội bộ, Authorization/JWT, tool payload hoặc raw graph state.
- File log local dùng đuôi `.log` nên đã được `.gitignore` hiện hành loại khỏi Git.

## Kiểm tra

- Python compile cho API route và Streamlit: pass.
- Streamlit `AppTest`: pass, không có exception.
- `make -n chat` và Bash syntax của recipe: pass.
- `make -n chat-logs` và Bash syntax của recipe: pass.
- `git diff --check`: pass.

## Còn lại / rủi ro

- Log local không có rotation; xóa thủ công `.logs/agent-demo.log` khi không còn cần. Không gửi log ra dịch vụ ngoài.
