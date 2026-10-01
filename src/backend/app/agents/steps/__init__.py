"""Luật của từng bước trong graph itinerary; `agents/nodes.py` chỉ còn hàm node gọi vào đây.

- `prompts` — system prompt cho các lượt gọi LLM.
- `messages` — câu chữ trả về người dùng và helper `message`/`event`/`failure`/`chat_model`.
- `classification` — trích intent từ message (`classify`).
- `tool_planning` — chuẩn hóa điểm đến, lập và chạy tool plan (`tool`).
- `evaluation` — chấm kết quả truy xuất, chọn `decision` (`evaluate`).
- `conversation` — soạn câu hỏi và câu trả lời hội thoại (`clarify`, `converse`).
- `composition` — dựng lịch trình bằng luật tất định (`compose`).
- `narration` — lời diễn giải lịch trình `COMPLETED`: LLM viết, backend kiểm link/giá và dự phòng bằng luật (`narrate`).
- `failures` — gom lỗi thành một Error Envelope (`dead_letter`).
- `validation` — kiểm response theo contract và grounding (`finalize`).
- `guardrails` — mẫu tất định chặn chèn lệnh (`classify`) và lộ secret/tuyên bố đặt chỗ (`finalize`).
- `history` — ngữ cảnh hội thoại chung cho mọi lượt gọi LLM.
- `turn_notes` — câu ngắn mô tả chuyến đi và từng lượt trợ lý theo nghĩa, dùng trong ngữ cảnh đó (`finalize` lưu kèm).
"""
