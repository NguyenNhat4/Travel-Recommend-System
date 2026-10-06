# Một biến model duy nhất cho agent: bỏ `MODEL_NAME`

- Ngày: 2026-10-05
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: mentor
- Trạng thái: hoàn thành
- Phạm vi: agent

## Mục tiêu

Hai biến cùng chọn model của agent: `ITINERARY_LLM_MODEL` thắng, bỏ trống thì OpenAI rơi về `MODEL_NAME`. Người dùng đặt `MODEL_NAME` trong `.env` mà agent không dùng vì `ITINERARY_LLM_MODEL` vẫn đang có giá trị. Gom lại còn một biến cho khỏi nhầm.

## File thay đổi

- `src/backend/app/core/config.py` — sửa: bỏ trường `model_name`.
- `src/backend/app/infrastructure/llm/client.py` — sửa: thêm `OPENAI_DEFAULT_MODEL = "gpt-4o-mini"` thay cho fallback `MODEL_NAME`; thêm `chat_model_name(settings)` trả model thực dùng theo provider.
- `src/backend/app/infrastructure/llm/__init__.py` — sửa: export `chat_model_name`.
- `src/backend/tests/unit/infrastructure/test_llm_factory.py` — sửa: bỏ `model_name`, test mặc định OpenAI và `chat_model_name`.
- `src/evaluation/agent/golden.py` — sửa: report ghi `model` bằng `chat_model_name` (trước đó `itinerary_llm_model or model_name`).
- `docker-compose.yml` — sửa: truyền `ITINERARY_LLM_MODEL` thay cho `MODEL_NAME`.
- `.env.example` — sửa: bỏ `MODEL_NAME`, ghi mặc định của từng provider ở chú thích `ITINERARY_LLM_MODEL`.
- `src/backend/README.md` — sửa: chú thích dòng `ITINERARY_LLM_MODEL`.
- `docs/spec/agent/README.md` — sửa: câu mô tả fallback `MODEL_NAME`.
- `history/2026-10-05-mot-bien-model-cho-agent.md` — thêm: entry này.

## Quyết định

- Giữ `ITINERARY_LLM_MODEL`, bỏ `MODEL_NAME`: biến giữ lại áp cho cả ba provider và cùng họ với `ITINERARY_USE_LLM`/`ITINERARY_LLM_TEMPERATURE`; `MODEL_NAME` chỉ là fallback riêng của OpenAI và không còn chỗ dùng nào khác.
- PRD (`docs/prd/`) không nhắc tới hai biến này nên không lệch PRD, không cần đề xuất.
- Mặc định khi bỏ trống không đổi: OpenAI `gpt-4o-mini`, Gemini `gemini-2.5-flash`, Anthropic `claude-sonnet-4-20250514`.

## Kiểm tra

- `.venv/bin/python -m pytest -q src/backend/tests/unit/infrastructure/test_llm_factory.py src/backend/tests/architecture`: 16 passed.
- `.venv/bin/python -m pytest -q src/backend/tests`: 1144 passed, 25 skipped.
- `docker compose config --quiet`: hợp lệ.
- Với `.env` đặt `ITINERARY_LLM_MODEL=gpt-6-luna`: `chat_model_name` và `build_chat_model(...).model_name` đều ra `gpt-6-luna`.

## Còn lại / rủi ro

- Máy nào còn `MODEL_NAME` trong `.env` mà để trống `ITINERARY_LLM_MODEL` sẽ âm thầm về mặc định provider (`extra="ignore"`); chuyển giá trị sang `ITINERARY_LLM_MODEL`.
- `gpt-6-luna` chỉ nhận temperature 1, cần `ITINERARY_LLM_TEMPERATURE=1` (mặc định 0).
