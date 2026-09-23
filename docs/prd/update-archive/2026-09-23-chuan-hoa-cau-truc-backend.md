# Chuẩn hoá cấu trúc thư mục backend và dọn file cũ ở gốc `src/`

- Ngày: 2026-09-23
- Người đề xuất: mihhquan / Claude Code
- Trạng thái: đã áp dụng
- Chốt bởi / ngày: mihhquan, 2026-09-23 (áp dụng cùng ngày; kế hoạch và việc còn lại: `docs/plan/2026-09-23-chuan-hoa-cau-truc-backend.md`)
- PRD bị ảnh hưởng: `docs/prd/architecture.md` §2 (cây thư mục backend, quy tắc phụ thuộc), §6.1 (câu về thư mục cũ ở gốc `src/`)
- Mã FR/NFR: NFR-MAINT-01 (Clean Architecture), NFR-MAINT-02 (Contract-First)

## Lý do

Cách chia **theo lớp trước, domain sau** trong PRD §2 vẫn hợp lý và được giữ nguyên. Tuy vậy, khi rà `src/backend/app` ngày 23/09/2026, code đang vi phạm chính các quy tắc của §2. Nguyên nhân là cây thư mục hiện tại không có sẵn chỗ cho một số trách nhiệm, nên code bị đặt tạm vào lớp sai:

| Vi phạm hiện tại | Chỗ trong code | Nguyên nhân: thiếu chỗ cho |
|---|---|---|
| `application` gián tiếp import FastAPI | `application/booking/purchase_events.py`, `application/recommendation/history.py` → `core/request_context.py` (import `fastapi`) | Middleware HTTP (phần FastAPI của request context) |
| Route tự lắp ráp agent, không qua `main.py` | `api/v1/routes/assistant.py` tạo `ItineraryToolGateway`, `RuntimeAgentDependencies` | Lớp dependency của API (`Depends`) |
| `api` gọi thẳng `agents`, bỏ qua `application` | `api/v1/routes/assistant.py` | Use case itinerary + port cho planner |
| `application` import script build và `jsonschema` để kiểm response theo OpenAPI | `application/itinerary/contracts.py`, `tool_contracts.py` → `src.shared.contracts.scripts.bundle_openapi` | Adapter kiểm contract phía `infrastructure` |
| DTO pydantic của API nằm trong `domain` | `domain/itinerary/schemas.py` (`ItineraryRequestModel`) | Schema request/response của API |
| Fake/mock dùng cho test nằm lẫn trong `infrastructure` | `infrastructure/cdp/local_cdp_client.py` (đọc JSONL, chỉ test dùng), `vectors/in_memory_store.py`, `clients/itinerary_fixture_clients.py` | Thư mục fake cho test |
| Không có gì chặn vi phạm tái diễn | — | Test tự động kiểm quy tắc import |

Ngoài ra, `src/main.py` và `src/config.py` ở gốc `src/` là code chết: `src/main.py` import `src.api.routes`, nhưng thư mục đó không còn tồn tại. PRD §6.1 hiện chỉ cấm "mở rộng" các file này; đề xuất xoá hẳn để không ai nhầm đây là entrypoint.

## Nội dung đề xuất

### 1. `docs/prd/architecture.md` §2, cây thư mục backend

Hiện tại:

```
src/backend/app/
├── domain/<domain>/         # LỚP 1: entity, value object, business rule thuần (auth, booking, catalog, itinerary, recommendation, search)
├── application/             # LỚP 2: use case và port
│   ├── ports/               # Giao diện trừu tượng: CdpClient, InsiderClient, SearchClient, embedding, vector store...
│   └── <domain>/            # Use case theo domain (auth, booking, catalog, itinerary, recommendation, search, tracking)
├── infrastructure/          # LỚP 3: hiện thực port
│   ├── persistence/         # PostgreSQL qua DATABASE_URL (role vota_app)
│   ├── cdp/                 # LocalCdpClient (CDP_DATABASE_URL) hoặc HttpCdpClient sau này
│   ├── clients/             # HTTP client ra ngoài, gồm HttpInsiderClient
│   ├── auth/                # Hash mật khẩu, JWT
│   ├── llm/                 # Adapter LLM provider
│   ├── embeddings/          # CohereEmbedder (embed-multilingual-v3.0)
│   └── vectors/             # WeaviateVectorStore; in_memory_store.py cho test offline
├── agents/                  # LangGraph: state, graph, node và tools/
├── api/v1/routes/           # LỚP 4: FastAPI router theo domain, chỉ xử lý HTTP
├── core/                    # settings, logging, security, error envelope
└── main.py                  # composition root: nối infrastructure vào use case
```

Thay bằng:

```
src/backend/app/
├── domain/<domain>/         # LỚP 1: entity, value object, business rule thuần (auth, booking, catalog, itinerary, recommendation, search)
├── application/             # LỚP 2: use case và port
│   ├── ports/               # Giao diện trừu tượng, MỖI PORT MỘT FILE: cdp_client, insider_client, embedder,
│   │                        #   vector_store, llm, contract_validator, itinerary_tools, auth...
│   └── <domain>/            # Use case theo domain (auth, booking, catalog, itinerary, recommendation, search, tracking)
├── infrastructure/          # LỚP 3: hiện thực port
│   ├── persistence/         # PostgreSQL qua DATABASE_URL (role vota_app); conversation store
│   ├── cdp/                 # Mọi adapter CDP: LocalCdpClient, đọc lịch sử, HttpCdpClient, hàng đợi ghi event nền
│   ├── clients/             # CHỈ HTTP client ra service ngoài, gồm HttpInsiderClient
│   ├── auth/                # Hash mật khẩu, JWT
│   ├── llm/                 # Adapter LLM provider (agent lấy LLM qua port llm, không tự import SDK)
│   ├── embeddings/          # CohereEmbedder (embed-multilingual-v3.0)
│   ├── vectors/             # WeaviateVectorStore
│   └── contracts/           # Kiểm dữ liệu theo OpenAPI bundle (jsonschema)
├── agents/                  # LangGraph: state, graph, node và tools/; hiện thực port planner itinerary
├── api/                     # LỚP 4: chỉ xử lý HTTP
│   ├── deps.py              # FastAPI Depends: lấy use case đã nối sẵn, route không tự lắp ráp
│   ├── middleware.py        # Request ID, CORS...
│   ├── errors.py            # Error Envelope + exception handler
│   └── v1/
│       ├── router.py        # Router v1 duy nhất; route không tự khai prefix /api/v1
│       ├── schemas/         # DTO request/response (pydantic) theo domain
│       └── routes/          # Router theo domain
├── core/                    # settings (một lớp Settings duy nhất), logging, request context (không import FastAPI)
└── main.py                  # composition root: nối infrastructure vào use case

src/backend/tests/
├── fakes/                   # Bản giả của port cho test offline: CDP đọc JSONL, in-memory vector store, fixture itinerary
├── unit/                    # domain/, application/, agents/
├── integration/
├── contract/
└── architecture/            # Test tự động kiểm quy tắc phụ thuộc bên dưới
```

### 2. `docs/prd/architecture.md` §2, quy tắc phụ thuộc: bổ sung sau quy tắc 7

Hiện tại: danh sách dừng ở quy tắc 7 ("**`agents`** không tự truy cập DB…").

Thêm:

> 8. **`api`** chỉ gọi use case trong `application`, không import `agents` hay `infrastructure`. Use case itinerary gọi agent qua port; `main.py` nối LangGraph vào port đó.
> 9. **`core`** không import FastAPI. Phần dính framework (middleware, exception handler) nằm trong `api/`.
> 10. Bản giả dùng cho test đặt ở `tests/fakes/`, không đặt trong `infrastructure/`.
> 11. Quy tắc 1–9 được kiểm tự động bằng test trong `tests/architecture/`; test này chạy trong CI như unit test.

### 3. `docs/prd/architecture.md` §6.1, câu cuối

Hiện tại:

> Thư mục cũ ở gốc `src/` (`src/agents`, `src/api`, `src/models`, `src/services`, `src/main.py`, `src/config.py`) không được mở rộng.

Thay bằng:

> Các thư mục cũ ở gốc `src/` (`src/agents`, `src/api`, `src/models`, `src/services`, `src/main.py`, `src/config.py`) đã bị xoá; không tạo lại. `src/__init__.py` được giữ để import dạng `src.backend.app…` chạy được.

## Thay đổi source sau khi chốt

Sau khi PRD được cập nhật như trên:

1. **Xoá file cũ:** `src/main.py`, `src/config.py`. Sửa câu tương ứng trong `AGENTS.md` §3.
2. **`core` và `api`:**
   - Tách `core/request_context.py` thành `core/request_context.py` (chỉ `ContextVar`) và `api/middleware.py`.
   - Chuyển exception handler ra khỏi `main.py` sang `api/errors.py`.
   - Gộp `core/settings.py` vào `core/config.py`.
3. **Router:**
   - Thêm `api/deps.py`.
   - Bỏ prefix `/api/v1` trong `routes/search.py` và `routes/recommendations.py`, đưa hai route này vào `api/v1/router.py`.
   - `routes/assistant.py` chỉ gọi use case `application/itinerary/use_cases.py`.
4. **DTO:** chuyển `domain/itinerary/schemas.py` sang `api/v1/schemas/itinerary.py`.
5. **Port:**
   - Tách `application/ports/recsys.py` thành `embedder.py`, `vector_store.py` và `unit_index.py`.
   - Gộp `CdpClientPort` vào `ports/cdp_client.py` dưới tên `CdpHistoryReader`.
   - Thêm port `llm.py`, `contract_validator.py` và port planner itinerary.
6. **Infrastructure:**
   - Đưa mọi adapter CDP vào `infrastructure/cdp/`: `clients/local_cdp_client.py` (bản Postgres), `clients/cdp_http_client.py` → `cdp/http_cdp_client.py`, `clients/cdp_event_dispatcher.py` → `cdp/event_dispatcher.py`.
   - Chuyển `clients/itinerary_conversation_store.py` sang `persistence/`.
   - Chuyển `application/itinerary/contracts.py` và `tool_contracts.py`, phần dùng `jsonschema`/`bundle_openapi`, sang `infrastructure/contracts/`.
   - Gộp `agents/llm.py` vào `infrastructure/llm/`.
7. **Test:**
   - Chuyển `infrastructure/cdp/local_cdp_client.py` (bản JSONL), `vectors/in_memory_store.py` và `clients/itinerary_fixture_clients.py` sang `tests/fakes/`.
   - Chế độ `ITINERARY_DATA_MODE=fixture` khi chạy dev vẫn cần fixture clients, nên phải xác nhận lại lúc làm: hoặc giữ một bản trong `infrastructure/clients/`, hoặc `main.py` import từ `tests/fakes/`. Cách thứ hai không nên dùng.
   - Chia lại `tests/unit/` theo lớp.
   - Thêm `tests/architecture/test_import_rules.py`, dùng `import-linter` hoặc quét AST bằng stdlib nếu không muốn thêm dependency. Thêm dependency vào `src/backend/requirements.txt` nếu chọn `import-linter`.
8. **Agent:**
   - Chuyển `agents/scenarios.py`, `metrics.py`, `report.py` và `cli.py` sang `src/evaluation/agent/`. Hiện không module nào trong backend import các file này.
   - Xoá `agents/tools/example_tool.py`.
9. **Tài liệu:**
   - Viết lại bảng "Chỗ nào làm gì" và lệnh chạy trong `src/backend/README.md`.
   - Đồng bộ `docs/spec/architecture-repo.md` §4–5 với PRD mới.
   - Tạo plan triển khai ở `docs/plan/2026-09-23-chuan-hoa-cau-truc-backend.md`, chia các bước trên thành từng PR nhỏ, mỗi PR giữ test xanh.

Không đổi contract OpenAPI, DDL hay hành vi API. Đây là thay đổi cấu trúc, không thay đổi tính năng.

## Ngoài phạm vi đề xuất này

- Frontend lệch PRD §6.1–6.2: không có `features/`; có server Express trong `src/frontend/server/` gọi thẳng `@google/genai`; `src/frontend/src/data/catalog.ts` chứa sẵn sản phẩm viết tay, có rủi ro với NFR-REL-01. Cần một đề xuất riêng, có người phụ trách Web review.
- Thay `PostgresVectorStore` và `SentenceTransformersEmbedder` bằng Weaviate + Cohere: đã chốt ngày 22/09, là việc hiện thực chứ không phải thay đổi cấu trúc thư mục.

## Ghi chú khi áp dụng (2026-09-23)

- Áp dụng đủ mục 1–3 vào `docs/prd/architecture.md`. Có hai chỉnh nhỏ để PRD khớp chính đề xuất: chú thích `tests/fakes/` bỏ "fixture itinerary", chú thích `clients/` thêm fixture cho `ITINERARY_DATA_MODE=fixture` (theo lựa chọn ở bước 7 phần "Thay đổi source"); §5 đổi đường dẫn `in_memory_store.py` thành `tests/fakes/in_memory_vector_store.py`.
- Chưa làm phần `infrastructure/contracts/` và port `contract_validator` (bước 5–6): chuyển các hàm này đi sẽ buộc agent import `infrastructure` hoặc phải viết lại `agents/nodes.py`. Chờ người dùng chọn hướng; chi tiết ở kế hoạch.
- Agent LangGraph checkpointer (`agents/persistence.py`) cũng chuyển sang `infrastructure/persistence/langgraph_checkpointer.py`, vì nó dùng `sqlite3` (quy tắc 7).
