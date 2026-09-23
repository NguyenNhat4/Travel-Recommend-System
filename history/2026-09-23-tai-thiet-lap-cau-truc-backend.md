# Tái thiết lập cấu trúc backend theo đề xuất đã chốt

- Ngày: 2026-09-23
- Tác giả: mihhquan / Claude Code
- Nhánh: feat/auth
- Trạng thái: dang dở
- Phạm vi: backend, agent, evaluation, docs
- Thay thế: 2026-09-23-de-xuat-chuan-hoa-cau-truc-backend.md

## Mục tiêu

Người dùng chốt đề xuất `docs/prd/update-archive/2026-09-23-chuan-hoa-cau-truc-backend.md` ("chốt tái thiết lập backend"). Theo `AGENTS.md` §8 bước 3: cập nhật PRD trước, sau đó đưa code backend về đúng `docs/prd/architecture.md` §2 (NFR-MAINT-01). Chỉ đổi cấu trúc: không đổi contract, DDL, route hay hành vi API.

## File thay đổi

PRD, quy tắc, tài liệu:
- `docs/prd/architecture.md` — sửa: §2 cây thư mục mới và quy tắc 8–11; §5 đường dẫn fake vector store; §6.1 ghi đã xoá file cũ ở gốc `src/`.
- `AGENTS.md` — sửa: §3 câu về thư mục cũ, trỏ tới quy tắc 1–11 và test kiến trúc.
- `docs/prd/update/2026-09-23-chuan-hoa-cau-truc-backend.md` → `docs/prd/update-archive/` — đổi tên: trạng thái `đã áp dụng`, thêm ghi chú khi áp dụng.
- `docs/plan/2026-09-23-chuan-hoa-cau-truc-backend.md` — thêm: kế hoạch, bảng việc đã làm, việc còn lại.
- `docs/spec/architecture-repo.md` — sửa: §4 cây backend, §5 thêm quy tắc api/core/fakes.
- `src/backend/README.md` — sửa: viết lại lệnh chạy (từ repo root) và bảng "Chỗ nào làm gì".
- `history/2026-09-23-de-xuat-chuan-hoa-cau-truc-backend.md` — sửa: thêm dòng `Bị thay thế bởi`.

Xoá file cũ:
- `src/main.py`, `src/config.py` — xóa: code chết (import `src.api.routes` không tồn tại).

`core` và `api`:
- `src/backend/app/core/request_context.py` — sửa: chỉ còn `ContextVar` + `bind_request_id`/`reset_request_id`, không import FastAPI.
- `src/backend/app/api/middleware.py` — thêm: `install_request_id`, `install_cors`.
- `src/backend/app/api/errors.py` — thêm: handler `RequestValidationError` → Error Envelope (chuyển từ `main.py`).
- `src/backend/app/core/config.py` — sửa: thêm 5 trường RecSys (`embed_model`, `embed_cache_dir`, `search_cutoff`, `search_max_limit`, `recommend_candidate_k`).
- `src/backend/app/core/settings.py` — xóa: gộp vào `config.py`; bỏ `products_path`/`events_path` vì không nơi nào đọc.
- `src/backend/app/api/deps.py` — thêm: Depends lấy use case từ `app.state`.
- `src/backend/app/api/router.py` → `src/backend/app/api/v1/router.py` — đổi tên: một router v1 gồm assistant, search, recommendations.
- `src/backend/app/api/v1/routes/search.py`, `recommendations.py` — sửa: bỏ prefix `/api/v1` tự khai, nhận use case qua `Depends`.
- `src/backend/app/api/v1/routes/assistant.py` — sửa: bỏ `_runtime`/`_input`/`_topology`; gọi `PlanItinerary` qua `Depends`, không import `agents`.
- `src/backend/app/domain/itinerary/schemas.py` → `src/backend/app/api/v1/schemas/itinerary.py` — đổi tên: DTO pydantic ra khỏi domain; thêm `api/v1/schemas/__init__.py`.

`application`:
- `src/backend/app/application/itinerary/use_cases.py` — thêm: `PlanItinerary` (dựng input graph, chạy có timeout).
- `src/backend/app/application/ports/recsys.py` → `unit_index.py` — đổi tên: chỉ còn `UnitIndex`; thêm `embedder.py`, `vector_store.py`.
- `src/backend/app/application/ports/cdp_client.py` — sửa: thêm `CdpHistoryReader` (thay `CdpClientPort`).
- `src/backend/app/application/ports/llm.py`, `itinerary_planner.py` — thêm: port `ChatModelPort`, `ItineraryPlanner`, `ItineraryPlannerFactory`.
- `src/backend/app/application/ports/__init__.py` — sửa: re-export theo file mới.
- `src/backend/app/application/recommendation/use_cases.py` — sửa: `CdpClientPort` → `CdpHistoryReader`.

`agents`:
- `src/backend/app/agents/nodes.py` — sửa: bỏ `from .llm import get_llm`; `(llm or get_llm())` → `_chat_model(llm)` (ném `RuntimeError` trong cùng khối try, nên vẫn ra `LLM_UNAVAILABLE`).
- `src/backend/app/agents/runtime_dependencies.py` — sửa: thêm `LangGraphItineraryPlanner` (hiện thực port, gồm `topology()` chuyển từ route) và `RuntimeAgentDependencies.planner()`.
- `src/backend/app/agents/llm.py` → `src/backend/app/infrastructure/llm/client.py` — đổi tên: thay file OpenAI-only không ai dùng; sửa `parents[5]` để vẫn đọc `.env` ở repo root; thêm `LazyChatModel`.
- `src/backend/app/agents/persistence.py` → `src/backend/app/infrastructure/persistence/langgraph_checkpointer.py` — đổi tên: dùng `sqlite3` nên thuộc infrastructure.
- `src/backend/app/agents/tools/example_tool.py` — xóa: tool mẫu của lab, không ai dùng.
- `src/backend/app/agents/{cli,metrics,report,scenarios}.py` → `src/evaluation/agent/` — đổi tên: đổi import tương đối sang tuyệt đối.

`infrastructure`:
- `src/backend/app/infrastructure/clients/local_cdp_client.py` → `infrastructure/cdp/local_cdp_client.py` — đổi tên (bản Postgres; git hiện là D + M vì chỗ cũ trong `cdp/` là bản JSONL).
- `src/backend/app/infrastructure/clients/cdp_http_client.py` → `infrastructure/cdp/http_cdp_client.py` — đổi tên.
- `src/backend/app/infrastructure/clients/cdp_event_dispatcher.py` → `infrastructure/cdp/event_dispatcher.py` — đổi tên.
- `src/backend/app/infrastructure/clients/itinerary_conversation_store.py` → `infrastructure/persistence/conversation_store.py` — đổi tên.
- `src/backend/app/infrastructure/cdp/postgres_cdp_reader.py`, `vectors/postgres_store.py` — sửa: docstring theo đường dẫn mới.
- `src/backend/app/main.py` — sửa: import mới; `_itinerary_planner()` dựng agent cho từng request; lifespan gắn `itinerary_llm = LazyChatModel()` và `plan_itinerary`; dùng `install_cors`/`install_error_handlers`; một `include_router`; đọc RecSys từ `Settings`.

Test và requirements:
- `src/backend/tests/fakes/__init__.py` — thêm.
- `src/backend/app/infrastructure/cdp/local_cdp_client.py` (bản JSONL) → `src/backend/tests/fakes/jsonl_cdp_reader.py` — đổi tên: class `LocalCdpClient` → `JsonlCdpReader`.
- `src/backend/app/infrastructure/vectors/in_memory_store.py` → `src/backend/tests/fakes/in_memory_vector_store.py` — đổi tên.
- `src/backend/tests/architecture/test_import_rules.py` — thêm: 8 test (6 lớp, file lạc lớp, test âm).
- `src/backend/tests/unit/*.py` → `unit/{domain,application,infrastructure,api}/` — đổi tên: 10 file.
- `src/backend/tests/conftest.py`, `integration/test_local_postgres_adapters.py`, `unit/agents/test_itinerary_runtime.py` — sửa: import đường dẫn mới.
- `src/backend/tests/unit/infrastructure/test_cdp_http_client.py` — sửa: `parents[3]` → `parents[4]` sau khi chuyển thư mục.
- `src/backend/tests/unit/agents/test_itinerary_tools.py` — sửa: truyền `llm=` thay vì `patch.object(nodes, 'get_llm')`; bỏ import `patch`.
- `src/backend/tests/unit/api/test_request_context.py` — sửa: `install_request_id` import từ `api.middleware`.
- `src/backend/requirements.txt` — sửa: bỏ `typer` (chỉ CLI dùng).
- `src/evaluation/requirements.txt` — sửa: thêm `typer`, `pyyaml` cho CLI đánh giá.

## Quyết định

- **Fixture itinerary giữ ở `infrastructure/clients/`**, không chuyển sang `tests/fakes/`: `ITINERARY_DATA_MODE=fixture` là chế độ chạy dev thật và `main.py` không được import từ `tests/`. Đề xuất đã nêu điểm này ở bước 7; hai chú thích trong cây thư mục PRD được sửa cho khớp.
- **Route không tự dựng agent.** `main.py` giữ `_itinerary_planner()` đọc `app.state` lúc gọi, nên contract test vẫn thay được client/LLM sau khi app khởi động, giống trước.
- **LLM đi qua `LazyChatModel`**, gọi `get_llm()` mỗi lần như hành vi cũ `llm or get_llm()`: thiếu API key vẫn ra `LLM_UNAVAILABLE` lúc gọi, không chặn khởi động.
- **Test kiến trúc dùng stdlib `ast`**, không dùng `import-linter`. Quét cả import trong thân hàm, quy import tương đối về tuyệt đối. Có test âm để tránh trường hợp bộ quét hỏng mà vẫn xanh.
- **Chưa làm `infrastructure/contracts/` và port `contract_validator`** (xem "Còn lại"). Test kiến trúc không cấm `jsonschema` trong `application`, nên hiện chưa bắt vi phạm này.
- Giữ tên class `CdpHttpClient`, chỉ đổi tên file, để thay đổi ít nhất.

## Kiểm tra

- Mốc trước refactor: `.venv/bin/python -m pytest -q src/backend/tests` → **125 passed, 2 skipped**.
- Sau refactor: `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider src/backend/tests` → **133 passed, 2 skipped** (+8 test kiến trúc). Lần chạy đầu có 5 fail (đường dẫn mock `parents[3]`, test còn patch `nodes.get_llm`); đã sửa như trên.
- Chạy bộ quét kiến trúc trên bản HEAD trước refactor (`git archive HEAD`): báo **11 vi phạm**, gồm `core` import `fastapi`, `api` import `agents`, `domain` import `pydantic`, `agents` import SDK LLM/`sqlite3`/`infrastructure`. Bản mới: 0.
- So `app.openapi()["paths"]` của HEAD và bản mới: **giống hệt** (8 path, cùng method).
- `python -m src.evaluation.agent.cli --help` → chạy được.
- `git diff --cached --check` → sạch.
- 2 test skip là integration Postgres (`RUN_POSTGRES_INTEGRATION`); Postgres local đang tắt nên **chưa chạy lại**.
- Không chạy `validate_contract.py`: không đổi contract/mock.

## Còn lại / rủi ro

- **Cần người dùng chọn hướng cho phần kiểm contract của itinerary** (`application/itinerary/contracts.py`, `tool_contracts.py` dùng `jsonschema` + `src.shared.contracts.scripts.bundle_openapi`). PRD mới ghi `infrastructure/contracts/` + port `contract_validator`, nhưng `agents/models.py` đọc `bounds`/`enum_values` ngay lúc import và `nodes.py` gọi các hàm này ở hơn 15 chỗ. Hướng (a): coi OpenAPI là "schema nghiệp vụ", chuyển loader sang `application/contracts/` và sửa PRD bằng một đề xuất mới. Hướng (b): làm đúng PRD, truyền validator qua port và dựng model agent lúc chạy; phải viết lại phần lớn `nodes.py`/`models.py`, rủi ro đổi hành vi.
- Chạy lại integration test khi có Postgres: `RUN_POSTGRES_INTEGRATION=1 python -m pytest -q src/backend/tests`.
- Nhánh khác đang sửa các file đã chuyển (`infrastructure/clients/*`, `agents/{llm,cli,persistence}.py`, `core/settings.py`, `domain/itinerary/schemas.py`, `api/router.py`) sẽ bị conflict khi merge; cần chuyển thay đổi sang đường dẫn mới.
- `docs/spec/agent/README.md` và `evaluation-plan.md` vẫn nhắc `get_llm`: tên hàm vẫn đúng, nhưng giờ nằm ở `infrastructure/llm/client.py`.
- Chưa commit.
