# Không hỏi lại khi người dùng rút lại yêu cầu đổi

- Ngày: 2026-10-01
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/itinerary-agent-guardrails
- Trạng thái: hoàn thành
- Phạm vi: agent, docs

## Mục tiêu

Trace LangSmith `nhat-10-1`, thread `be497826-83c6-43dc-b513-01ae75590bdb`: sau "đi hà nội 3 ngày" → "đổi điểm đi",
người dùng trả lời "không đổi nữa", "không đổi", "tôi không có đổi" nhưng lượt nào cũng bị hỏi lại điểm đến. LLM ở
`extract` trả `change_without_value: ["destination"]` cho câu rút lại yêu cầu đổi, nên `extract_result` đi nhánh
`change_without_value` thay vì giữ Hà Nội và hỏi tiếp ngày đi/số người/ngân sách (hoặc lập lịch nếu đã hỏi).
Phục vụ FR-AGT-01, FR-AGT-05 (cùng phạm vi `history/2026-09-30-hoi-lai-khi-doi-ma-chua-noi-cu-the.md`).

## File thay đổi

- `src/backend/app/agents/steps/prompts.py` — sửa: `EXTRACT_PROMPT` thêm luật câu từ chối/rút lại yêu cầu đổi không phải là đổi, để `change_without_value` rỗng kể cả khi lượt trước vừa hỏi đổi thành gì.
- `docs/spec/agent/langgraph-nodes.md` — sửa: mô tả `change_without_value` ở node `extract` ghi rõ câu rút lại không tính.

## Quyết định

- Sửa ở prompt, không thêm luật regex ở backend: giữ quyết định của entry 2026-09-30 là LLM nhận ra "đổi mà chưa nói cụ thể", backend chỉ chặn khi LLM tự mâu thuẫn.
- Không lệch PRD: hành vi đúng theo spec hiện có (chỉ hỏi lại khi người dùng muốn đổi mà chưa nói giá trị).

## Kiểm tra

- Chạy `extract_node_async` với LLM thật cấu hình trong `.env` (lịch sử như trace trên, intent Hà Nội 3 ngày, mỗi câu 10 lần):
  - Prompt cũ: "không đổi nữa", "không đổi", "thôi giữ nguyên" → hỏi lại điểm đến 10/10; "tôi không có đổi" → hỏi lại 10/10 (6 `conflict`, 4 `change_without_value`).
  - Prompt mới, `start_date_asked = True`: bốn câu trên → `tool`, giữ Hà Nội 10/10; "đổi điểm đến" → hỏi lại điểm đến 9/10 (1 lần `conflict`); "đổi sang Đà Nẵng" → `tool` Đà Nẵng 10/10.
  - Prompt mới, `start_date_asked = False` (5 lần/câu): bốn câu rút lại → `missing_info`, `missing_fields = [startDate, party, budget]`, giữ Hà Nội 5/5.
- `.venv/bin/python -m pytest -q src/backend/tests/unit/agents src/backend/tests/architecture`: 297 passed.

## Còn lại / rủi ro

- Chưa thêm ca "không đổi nữa" vào golden eval (`src/evaluation/datasets/itinerary_agent_golden.yaml`, G-079).
- "đổi điểm đi" ở cùng thread bị LLM gắn `conflict` thay vì `change_without_value` (vẫn hỏi lại, chỉ khác câu chữ); chưa sửa.
- LLM không tất định; kết quả trên đo trên một model và một môi trường.
