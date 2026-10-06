# Thêm ITINERARY_LLM_REASONING_EFFORT cho OpenAI

- Ngày: 2026-10-05
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: agent

## Mục tiêu

Với `ITINERARY_LLM_MODEL=gpt-6-luna`, node `tool` (bước `plan`, `bind_tools(..., tool_choice="any")`) nhận 400 từ OpenAI: "Function tools with reasoning_effort are not supported for gpt-6-luna in /v1/chat/completions". Cả lượt chat rơi vào `dead_letter` và trả 503 `LLM_UNAVAILABLE`. `classify`/`extract` không lỗi vì dùng structured output. Code không gửi `reasoning_effort`, nên reasoning mặc định phía server là nguyên nhân; cần một cách đặt `none`.

## File thay đổi

- `src/backend/app/core/config.py` — sửa: thêm `itinerary_llm_reasoning_effort` (`none|minimal|low|medium|high`, mặc định None); thêm vào `_OPTIONAL_BLANK_IS_NONE` để biến để trống trong `.env` không làm `Settings()` lỗi.
- `src/backend/app/infrastructure/llm/client.py` — sửa: nhánh OpenAI truyền `reasoning_effort` vào `ChatOpenAI` (None = không gửi).
- `src/backend/tests/unit/infrastructure/test_llm_factory.py` — sửa: test tham số chỉ được chuyển tiếp khi có đặt.
- `.env.example` — sửa: thêm `ITINERARY_LLM_REASONING_EFFORT=` kèm chú thích.
- `docker-compose.yml` — sửa: truyền `ITINERARY_LLM_REASONING_EFFORT` vào container backend.
- `src/backend/README.md` — sửa: thêm dòng biến mới.
- `history/2026-10-05-reasoning-effort-cho-openai.md` — thêm: entry này.

## Quyết định

- Chỉ áp cho OpenAI; Gemini/Anthropic không đổi. Mặc định không gửi tham số nên hành vi cũ giữ nguyên với các model khác.
- Chọn biến cấu hình thay vì hard-code `none` hay chuyển sang Responses API: ít đụng nhất, không đổi API đang dùng.
- PRD không nhắc biến này (cùng lý do với `2026-10-05-mot-bien-model-cho-agent.md`), nên không lệch PRD.
- `.env` local (ignored) đặt `ITINERARY_LLM_REASONING_EFFORT=none`.

## Kiểm tra

- `.venv/bin/python -m pytest -q src/backend/tests`: 1146 passed, 25 skipped.
- `Settings(itinerary_llm_reasoning_effort='')` cho `None`.
- `docker compose config --quiet`: hợp lệ.
- Chưa chạy lại lượt chat thật với `gpt-6-luna` sau khi sửa; cần restart backend rồi thử lại.

## Còn lại / rủi ro

- Chưa xác nhận `gpt-6-luna` chấp nhận `reasoning_effort=none` cùng `temperature=1` trên chat completions; nếu vẫn 400 thì cân nhắc `use_responses_api=True`.
- Thay đổi code đã nằm trong commit `880dd96` nhưng commit đó chưa kèm entry này; entry cần vào commit kế tiếp.
- `src/frontend/.../ItineraryMap.tsx` đang sửa dở trong working tree, không thuộc thay đổi này.
