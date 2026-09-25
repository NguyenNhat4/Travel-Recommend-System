# Cấu hình timeout LLM cho Agent demo

- Ngày: 2026-09-19
- Tác giả: người dùng / Codex
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: backend, agent, evaluation

## Mục tiêu

Sửa lỗi node `classify` trả `LLM_UNAVAILABLE` vì graph hủy request OpenAI sau giới hạn cố định 2 giây trong demo local.

## File thay đổi

- `.env.example` — sửa: thêm timeout LLM 30 giây và tăng toàn request lên 90 giây cho profile demo.
- `Makefile` — sửa: `make chat` export timeout demo, ghi đè giá trị `.env` cũ nếu shell chưa cấu hình.
- `src/backend/app/core/config.py` — sửa: thêm `itinerary_llm_timeout_seconds`.
- `src/backend/app/agents/runtime_dependencies.py` — sửa: truyền timeout tool/LLM vào graph thay vì dùng hằng mặc định.
- `src/backend/app/api/v1/routes/assistant.py` — sửa: lấy timeout từ Settings khi dựng runtime theo request.

## Quyết định

- Profile demo dùng 30 giây cho mỗi LLM call và 90 giây cho toàn request vì một lượt hoàn chỉnh có thể gọi classify, tool planning và composition tuần tự.
- Timeout vẫn cấu hình được qua environment; code default giữ 2/5 giây để không âm thầm thay đổi profile ngoài `make chat`.

## Kiểm tra

- Python compile cho config, runtime dependencies và API route: pass.
- Unit test wiring xác nhận runtime truyền đúng timeout vào `build_graph`: pass.
- `make -n chat` thể hiện hai biến timeout và recipe qua Bash syntax: pass.
- `git diff --check`: pass.

## Còn lại / rủi ro

- Cần chạy lại với provider thật để đo latency thực; thay đổi này sửa giới hạn local đã chứng minh trong log, không chứng minh provider luôn trả lời trong 30 giây.
