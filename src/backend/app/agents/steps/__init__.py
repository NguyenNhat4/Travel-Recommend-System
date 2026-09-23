"""Luật của từng bước trong graph itinerary; `agents/nodes.py` chỉ còn hàm node gọi vào đây.

- `prompts` — system prompt cho ba lượt gọi LLM.
- `messages` — câu chữ trả về người dùng và helper `message`/`event`/`failure`/`chat_model`.
- `classification` — trích intent từ message (`classify`).
- `tool_planning` — chuẩn hóa điểm đến, lập và chạy tool plan (`tool`).
- `evaluation` — chấm kết quả truy xuất, chọn `decision` (`evaluate`).
- `conversation` — soạn câu hỏi và câu trả lời hội thoại (`clarify`, `converse`).
- `composition` — dựng lịch trình bằng luật tất định (`compose`).
- `failures` — gom lỗi thành một Error Envelope (`dead_letter`).
- `validation` — kiểm response theo contract và grounding (`finalize`).
"""
