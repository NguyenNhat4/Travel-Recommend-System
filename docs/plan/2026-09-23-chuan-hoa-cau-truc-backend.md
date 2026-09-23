# Kế hoạch: chuẩn hoá cấu trúc thư mục backend

- Ngày: 2026-09-23
- Phục vụ: NFR-MAINT-01 (Clean Architecture), NFR-MAINT-02 (Contract-First) — `docs/prd/requirements.md` §2.4
- Căn cứ: đề xuất đã chốt `docs/prd/update-archive/2026-09-23-chuan-hoa-cau-truc-backend.md`; `docs/prd/architecture.md` §2 (cây thư mục, quy tắc 1–11), §6.1
- Người làm: mihhquan / Claude Code, nhánh `feat/auth`

Thay đổi chỉ về cấu trúc: không đổi contract OpenAPI, DDL, route hay hành vi API. Danh sách route trước và sau refactor giống hệt nhau.

## Đã làm

| # | Bước | Kết quả |
|---|---|---|
| 1 | Xoá `src/main.py`, `src/config.py` | Xong. `src/__init__.py` giữ nguyên |
| 2 | `core` không import FastAPI | `core/request_context.py` chỉ còn `ContextVar`; middleware sang `api/middleware.py`, exception handler sang `api/errors.py`; `core/settings.py` gộp vào `core/config.py` |
| 3 | Router | `api/deps.py`; một router `api/v1/router.py`; route search/recommendations bỏ prefix tự khai; `assistant.py` gọi use case `PlanItinerary` |
| 4 | DTO | `domain/itinerary/schemas.py` → `api/v1/schemas/itinerary.py` |
| 5 | Port | `recsys.py` tách thành `embedder.py`, `vector_store.py`, `unit_index.py`; `CdpClientPort` → `CdpHistoryReader` trong `cdp_client.py`; thêm `llm.py`, `itinerary_planner.py` |
| 6 | Infrastructure | Adapter CDP về `infrastructure/cdp/`; conversation store và LangGraph checkpointer về `persistence/`; `agents/llm.py` gộp vào `infrastructure/llm/client.py` (thêm `LazyChatModel`) |
| 7 | Test | Fake sang `tests/fakes/`; `tests/unit/` chia theo lớp; thêm `tests/architecture/test_import_rules.py` (stdlib `ast`, không thêm dependency) |
| 8 | Agent | `scenarios.py`, `metrics.py`, `report.py`, `cli.py` → `src/evaluation/agent/`; xoá `tools/example_tool.py` |
| 9 | Tài liệu | `src/backend/README.md`, `docs/spec/architecture-repo.md` §4–5 |

Fixture 50 sản phẩm của itinerary vẫn ở `infrastructure/clients/itinerary_fixture_clients.py`, vì `ITINERARY_DATA_MODE=fixture` chạy trong môi trường dev thật và `main.py` không được import từ `tests/`.

## Còn lại

1. **Kiểm contract trong itinerary (`application/itinerary/contracts.py`, `tool_contracts.py`) chưa chuyển sang `infrastructure/contracts/` và chưa có port `contract_validator`.** Lý do: `agents/models.py` đọc `bounds`/`enum_values` ngay lúc import để dựng schema pydantic cho LLM, và `agents/nodes.py` cùng tool gateway gọi `valid`/`normalize_arguments`/`validate` ở hơn 15 chỗ. Chuyển sang `infrastructure` thì agent phải import `infrastructure` (vi phạm quy tắc 7). Truyền qua port thì phải viết lại cách dựng model và phần lớn `nodes.py`, tức là đổi hành vi agent. Cần người dùng chọn hướng xử lý, xem history entry cùng ngày.
2. Chưa có `ports/insider_client.py` và `HttpInsiderClient`: thuộc FR-ENG, không nằm trong phạm vi refactor này.
3. Route auth, catalog, cart, booking, events chưa có trong `api/v1/routes/`: việc của từng feature, đặt đúng thư mục khi làm.
4. Integration test Postgres chưa chạy lại vì Postgres local đang tắt. Khi có DB: `RUN_POSTGRES_INTEGRATION=1 python -m pytest -q src/backend/tests`.
