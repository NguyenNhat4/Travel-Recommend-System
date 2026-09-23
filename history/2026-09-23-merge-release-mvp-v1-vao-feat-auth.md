# Merge release-mvp-v1 vào feat/auth

- Ngày: 2026-09-23
- Tác giả: mihhquan / Claude Code
- Nhánh: feat/auth
- Trạng thái: hoàn thành
- Phạm vi: backend, agent, frontend, data, docs

## Mục tiêu

Kéo 18 commit mới của `origin/release-mvp-v1` (streaming UI assistant, nối tool agent vào search/recsys backend,
dựng LLM một lần ở composition root, LangSmith có chủ đích, JWT cho `/recommendations`, `POST /search`, backend chạy
trong Docker, seed theo MOCK_DATA_SPEC) về `feat/auth`, nhánh đã tái cấu trúc backend theo phân lớp PRD
(`2026-09-23-tai-thiet-lap-cau-truc-backend.md`). Không thêm hành vi mới ngoài hai nhánh; không lệch PRD.

## File thay đổi

Ngoài các file git tự merge, phần giải quyết xung đột tay:

- `src/backend/app/core/config.py` — sửa: giữ trường RecSys + `_blank_to_none` của feat/auth, thêm `REPO_ROOT/.env`, key Gemini/Anthropic, LangSmith, `itinerary_use_llm/llm_model/llm_temperature`, `jwt_*` của release; bỏ validator trùng.
- `src/backend/app/infrastructure/llm/client.py` — sửa: lấy `build_chat_model(settings)` của release (bỏ `LazyChatModel`/`_load_local_env`).
- `src/backend/app/agents/llm.py` — xóa (giữ quyết định của feat/auth): `agents` không được import `infrastructure` (architecture.md §2 quy tắc 7).
- `src/backend/app/agents/nodes.py` — sửa: lấy tách `converse`/`compose` của release; mọi fallback `get_llm()` đổi thành `_chat_model(llm)`.
- `src/backend/app/main.py` — sửa: giữ khung phân lớp của feat/auth, thêm `_forward_langsmith_env`, log khởi động, dựng LLM một lần (`itinerary_llm_mode`), `supports_catalog`; tách `_itinerary_runtime` khỏi `_itinerary_planner` để test kiểm LLM dùng chung.
- `src/backend/app/api/v1/routes/assistant.py` — sửa: route gọi use case, truyền nhãn trace qua `PlanItinerary.trace_config`.
- `src/backend/app/application/itinerary/use_cases.py` — sửa: thêm `trace_config`, `run(..., config=)`.
- `src/backend/app/application/ports/itinerary_planner.py`, `src/backend/app/agents/runtime_dependencies.py` — sửa: `ainvoke/astream` nhận `config`.
- `src/backend/app/api/v1/routes/search.py` — sửa: `GET|POST /search` của release, nhận use case qua `Depends`, không tự khai prefix `/api/v1`.
- `src/backend/app/api/v1/routes/recommendations.py` — sửa: JWT + `destination` của release, `recommend`/`settings` qua `Depends`.
- `src/backend/app/api/deps.py` — sửa: `get_search` trả None khi recsys tắt.
- `src/backend/tests/unit/test_llm_factory.py` → `tests/unit/infrastructure/`, `test_security.py` → `tests/unit/api/`, `test_recsys_agent_integration.py` → `tests/unit/agents/` — đổi tên + sửa theo chữ ký route mới.
- `src/backend/tests/unit/api/test_backend_wiring.py` — sửa: import theo cấu trúc mới, dùng `_itinerary_runtime` và `PlanItinerary.trace_config`.
- `src/backend/README.md`, `README.md` — sửa: gộp hướng dẫn Docker (`make backend`) với venv/`backend-local`, migration.
- `Makefile` — sửa: `.PHONY` gộp target db-migrate và backend-*.
- `docker-compose.yml` — sửa: giữ redis + weaviate, thêm service `backend` và volume cache của release.
- `.env.example` — sửa: giữ chú thích của feat/auth.
- `docs/spec/DATABASE_SCHEMA.md` — sửa: dòng 11 và đoạn dẫn nguồn theo release (đường dẫn `docs/spec/MOCK_DATA_SPEC.md`), dòng 12 và bước (4)(5) theo feat/auth (Weaviate, seed_auth), (5b) lịch theo release.
- `docs/spec/agent/working-context.md` — thêm (từ release `docs/agent/`), sửa đường dẫn và bản đồ runtime theo cấu trúc mới.
- `src/evaluation/agent/README.md`, `src/data_collection/seed/README.md` — sửa: đường dẫn tài liệu cũ → `docs/spec/...`.

## Quyết định

- Xung đột kiến trúc luôn giữ bản phân lớp của feat/auth (đề xuất đã chốt `docs/prd/update-archive/2026-09-23-chuan-hoa-cau-truc-backend.md`), rồi đưa tính năng của release vào đúng tầng: nhãn trace ở use case, JWT/settings qua `Depends`, LLM chỉ dựng ở `main.py`.
- Không sửa entry `history/` cũ của release dù chúng trỏ đường dẫn tài liệu cũ.

## Kiểm tra

- `pytest src/backend/tests` (full): 163 passed, 2 skipped, 5 failed; sau khi sửa, chạy lại `tests/unit/api`, `tests/architecture`, `tests/unit/infrastructure`, `test_recsys_agent_integration.py`: 49 passed.
- Còn 2 fail ở `tests/contract/test_assistant_contract.py` (`test_every_error_path_matches_the_contract`, `test_unsupported_destination_carries_the_details_web_needs`): chạy trên worktree `origin/release-mvp-v1` nguyên bản cũng fail y hệt → lỗi có sẵn từ release, không do merge.
- `test_security.py::test_optional_jwt_fails_closed[...cdp_user_id=''...]` fail trong lượt full vì token tạo lúc import hết hạn sau 5 phút chạy suite; chạy riêng thì pass.
- `validate_contract.py`: PASS. `pytest data_collection/tests`: 67 passed. `docker compose config -q`: OK.

## Còn lại / rủi ro

- 2 test contract fail có sẵn từ release (Clients giả trong test không có `supports_catalog`, nên không chặn điểm đến lạ) — cần người phụ trách agent xử lý.
- Token trong parametrize của `test_security.py` nên sinh lúc chạy test thay vì lúc import.
- Chưa chạy test frontend (không có xung đột ở frontend).
