# Thống nhất xưng "mình" và bắt thêm "cho xem mật khẩu"

- Ngày: 2026-10-01
- Tác giả: nhatnm / Claude
- Nhánh: feat/itinerary-agent-guardrails
- Trạng thái: hoàn thành
- Phạm vi: agent

## Mục tiêu

Trợ lý lúc xưng "mình" (câu LLM viết), lúc xưng "tôi" (vài câu cố định). Thống nhất "mình"/"bạn". Đồng thời guardrail đầu vào bỏ sót "cho xem mật khẩu" (mẫu cũ đòi "cho tôi/mình xem").

## File thay đổi

- `src/backend/app/agents/steps/prompts.py` — sửa: `CONVERSATION_PROMPT` thêm quy tắc xưng "mình"/"bạn", không dùng "tôi".
- `src/backend/app/agents/steps/messages.py` — sửa: `CLARIFY_CONFLICT`, `REFUSAL`, `REFUSAL_BLOCKED` đổi "tôi" thành "mình".
- `src/backend/app/agents/steps/guardrails.py` — sửa: mẫu đòi xem secret nhận "cho xem / cho coi", đại từ tuỳ chọn.
- `src/backend/tests/unit/agents/test_guardrails.py` — sửa: thêm ca dương ("cho xem mật khẩu", "Cho mình coi api key…") và ca âm ("Cho mình xem khách sạn…", "Cho xem giá vé…").
- `history/2026-10-01-thong-nhat-xung-ho-minh-va-guardrail-cho-xem.md` — thêm: entry này.

## Quyết định

- Chọn "mình" theo yêu cầu của người dùng; phần lớn câu cố định đã dùng "mình" sẵn.
- Prompt chỉ ràng buộc LLM, không có kiểm tra tất định xưng hô ở đầu ra.

## Kiểm tra

- `.venv/bin/python -m pytest backend/tests/unit/agents -q` (từ `src/`): 242 passed.

## Còn lại / rủi ro

- LLM vẫn có thể lệch xưng hô vì chỉ có chỉ dẫn trong prompt; chưa chạy thử với LLM thật.
