# Giải thích bảng execution và các luồng Agent

- Ngày: 2026-09-20
- Tác giả: người dùng / Codex
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: evaluation, docs

## Mục tiêu

Giải thích cách đọc bảng LangGraph execution trong UI demo, trách nhiệm của từng node và các luồng rẽ nhánh hiện hành để team không hiểu `completed`, `message` hoặc `durationMs` sai nghĩa.

## File thay đổi

- `src/evaluation/agent/README.md` — sửa: thêm hướng dẫn đọc năm cột của trace, mô tả chín node, ví dụ trace đầy đủ và sơ đồ các luồng success/clarification/retry/failure.
- `history/2026-09-20-document-agent-node-flows.md` — thêm: ghi lại thay đổi tài liệu này.

## Quyết định

- Tài liệu bám trực tiếp topology và routing trong `src/backend/app/agents/graph.py`, `routing.py` và hành vi trong `nodes.py`.
- Nêu rõ `completed` là trạng thái thực thi node, không phải evaluation PASS; trạng thái cuối phải đọc từ response sau `finalize`.
- Nêu rõ `durationMs` là latency quan sát tại biên SSE, không phải CPU profile; fixture không phải bằng chứng cho service hoặc SLA production.
- Giữ node `clarify` trong bảng vì node còn tồn tại trong topology, đồng thời ghi rõ routing hiện hành đưa trường hợp thiếu thông tin qua LLM `answer`.

## Kiểm tra

- `git diff --check` cho hai file của task: pass, không có lỗi whitespace.
- Kiểm tra source bằng `rg`: pass, có đủ ba mục hướng dẫn và đúng chín dòng mô tả node.
- Đối chiếu thủ công với `graph.py`, `routing.py`, `nodes.py` và SSE route: pass; không thay đổi API/contract nên không chạy contract validator.

## Còn lại / rủi ro

- Không thay đổi code, API hay contract. Tài liệu cần được cập nhật nếu topology/routing của graph thay đổi.
