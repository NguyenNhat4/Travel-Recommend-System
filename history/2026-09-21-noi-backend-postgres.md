# Nối Backend với PostgreSQL local đã seed

- Ngày: 2026-09-21
- Tác giả: Đặng Khôi / Codex
- Nhánh: mockdata-work
- Trạng thái: hoàn thành
- Phạm vi: backend, cdp, docs

## Mục tiêu

Cho Backend dùng trực tiếp catalog, profile và event đã được seed trong PostgreSQL Docker local theo DDL chính thức. Việc nối phải dùng đúng boundary/role, không tạo database hay bảng mới, không chạy lại seed, không thay đổi dữ liệu hiện có và không thay đổi OpenAPI.

## File thay đổi

- `.env.example` — sửa: thêm lựa chọn adapter CDP local mặc định.
- `src/backend/README.md` — sửa: hướng dẫn chạy Backend với PostgreSQL Docker và giải thích vai trò của hai DSN.
- `src/backend/requirements.txt` — thêm: dependency runtime/test của Backend, gồm FastAPI, psycopg, LangGraph và pytest.
- `src/backend/app/core/config.py` — sửa: thay mặc định SQLite/Chroma bằng hai DSN PostgreSQL local và cấu hình chọn adapter local/HTTP.
- `src/backend/app/application/ports/cdp_client.py` — sửa: cập nhật mô tả implementation hiện hành của port CDP.
- `src/backend/app/infrastructure/clients/local_cdp_client.py` — thêm: adapter PostgreSQL cho profile/event CDP theo DDL và quyền chính thức.
- `src/backend/app/infrastructure/persistence/postgres_catalog.py` — thêm: lookup sản phẩm từ `cdp.products` bằng role ứng dụng.
- `src/backend/app/infrastructure/clients/cdp_event_dispatcher.py` — sửa: bắt đúng timeout shutdown trên cả Python 3.10 và 3.11+.
- `src/backend/app/main.py` — sửa: composition root nối adapter PostgreSQL local, giữ lựa chọn HTTP cho môi trường sau này.
- `src/backend/app/agents/graph.py` — sửa: đường import package Agent theo cấu trúc `src/backend` hiện hành để app khởi động được.
- `src/backend/app/agents/nodes/example_node.py` — sửa: đường import `AgentState` theo cấu trúc hiện hành.
- `src/backend/tests/integration/test_local_postgres_adapters.py` — thêm: test chỉ-đọc catalog/CDP thật và ranh giới quyền của hai role.
- `src/backend/tests/unit/test_backend_wiring.py` — thêm: test lifespan, health route và adapter mặc định của composition root.
- `history/2026-09-21-noi-backend-postgres.md` — thêm: entry này.

## Quyết định

- `DATABASE_URL` dùng `vota_app_login` cho dữ liệu ứng dụng/catalog; `CDP_DATABASE_URL` dùng `cdp_client_login` cho `LocalCdpClient`. Backend không dùng tài khoản seed/superuser.
- Mặc định local là `CDP_ADAPTER=local`; `CDP_ADAPTER=http` vẫn giữ `CdpHttpClient` để đổi implementation mà không sửa use case.
- Chỉ composition root biết implementation. Business/use case tiếp tục phụ thuộc port `CdpClient` và `ProductLookup`.
- DDL local chưa có cột external event ID, search query hay cancelled-at. Adapter khử trùng purchase bằng booking group/product/date, không ghi search query vào CDP, và huỷ purchase bằng `DELETE` theo quyền/DDL hiện hành; không tự thêm bảng hoặc cột.
- Integration test chỉ đọc database đã seed. Không test đường ghi lên dữ liệu snapshot để tránh tạo hoặc xoá dữ liệu của người dùng.
- Sửa hai import Agent tồn tại sẵn vì chúng trỏ tới package cũ `src.agents` và chặn việc import/khởi động Backend; không thay đổi hành vi Agent.

## Kiểm tra

- Import dependency Agent trong conda `vsf` → **PASS** (`langgraph`, `langchain_openai`).
- `RUN_POSTGRES_INTEGRATION=1 ... python -m pytest -q -p no:cacheprovider src/backend/tests` với hai DSN local → **30/30 PASS**; còn một warning deprecation từ Starlette/AnyIO, không ảnh hưởng kết quả.
- Integration kiểm tra quyền → **PASS**: app role đọc được `cdp.products` nhưng không đọc `cdp.events`; CDP role đọc được profile nhưng không đọc `catalog.combo_items`.
- Đếm lại sau test → giữ nguyên **10.320 products, 2.000 profiles, 7.511 events, 3.373 purchases, 218 combo items, 1 booking, 0 product vectors**.
- `git diff --check` → sẽ chạy lại ở vòng kiểm tra cuối.
- Contract validator không chạy lại vì task này không thay đổi OpenAPI, schema response hoặc mock fixture.

## Còn lại / rủi ro

- Backend hiện đã có kết nối/adapter nhưng repository vẫn chưa triển khai endpoint Catalog/Search/Recommendation và thuật toán recommendation hoàn chỉnh; mới có route Assistant cùng các use case nền hiện hữu.
- `catalog.product_vectors` vẫn bằng 0. Sinh embedding và pipeline retrieval/model là phần tuần 2, không thuộc việc nối DB này.
- Mật khẩu trong `.env.example` chỉ dành cho PostgreSQL Docker local/dev, không dùng cho production.
- Chưa commit, chưa push theo yêu cầu.
