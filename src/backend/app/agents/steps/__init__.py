"""Luật của từng bước trong graph itinerary; `agents/nodes.py` chỉ còn hàm node gọi vào đây.

- `prompts` — system prompt cho các lượt gọi LLM.
- `messages` — câu chữ trả về người dùng và helper `message`/`event`/`failure`/`chat_model`.
- `classification` — trích intent từ message (`extract`), luật câu dừng và chọn phương án (`precheck`).
- `tool_planning` — chuẩn hóa điểm đến, lập và chạy tool plan (`tool`).
- `evaluation` — chấm kết quả truy xuất, chọn `decision` (`evaluate`).
- `conversation` — soạn câu hỏi thiếu thông tin (`clarify`) và câu cố định khi bị chặn (`converse`).
- `orchestration`, `jobs`, `fares`, `consent`, `shown` — orchestrator: chọn việc, chạy việc, câu vé, đồng ý lập lịch, trí nhớ thẻ.
- `replies` — nút gợi ý và câu chữ dùng chung của câu trả lời.
- `composition` — dựng lịch trình bằng luật tất định (`compose`).
- `narration` — lời diễn giải lịch trình `COMPLETED`: LLM viết, backend kiểm link/giá và dự phòng bằng luật (`narrate`).
- `failures` — gom lỗi thành một Error Envelope (`dead_letter`).
- `validation` — kiểm response theo contract và grounding (`finalize`).
- `guardrails` — mẫu tất định chặn chèn lệnh (`precheck`) và lộ secret/tuyên bố đặt chỗ (`finalize`).
- `history` — ngữ cảnh hội thoại chung cho mọi lượt gọi LLM.
- `turn_notes` — câu ngắn mô tả chuyến đi và từng lượt trợ lý theo nghĩa, dùng trong ngữ cảnh đó (`finalize` lưu kèm).
"""
