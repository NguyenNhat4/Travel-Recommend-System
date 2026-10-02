# Backend: DB không với tới được thì trả 503 DATABASE_UNAVAILABLE thay vì lỗi 500/treo (A1)

- Ngày: 2026-10-02
- Tác giả: chủ dự án (review kiến trúc DB) / Claude
- Nhánh: khoa/backend-db-unavailable-degraded
- Trạng thái: hoàn thành
- Phạm vi: backend, contract, docs

## Mục tiêu

Mục A1 của kế hoạch `docs/plan/2026-10-02-db-ha-va-do-ben-ket-noi.md` (nằm ở nhánh `khoa/db-private-link-failover-ssh`). Rà soát code cho thấy backend không crash lúc khởi động khi primary sập (lifespan không mở DB) nhưng mỗi request lỗi: các đường `app.*` trả `500 INTERNAL_ERROR`, và chỉ `postgres_cdp_reader.py` có `connect_timeout` nên VM DB treo thì request treo theo timeout TCP của hệ điều hành. Mục tiêu: lỗi DB thành 503 chuẩn, có thể thử lại, không treo, tự hồi phục.

## File thay đổi

- `src/backend/app/application/errors.py` — thêm: `DatabaseUnavailableError`.
- `src/backend/app/infrastructure/persistence/db_connection.py` — thêm: `connect_async` (connect_timeout, keepalive, tcp_user_timeout, lưới `asyncio.wait_for`), dịch lỗi kết nối; `configure()`.
- `src/backend/app/infrastructure/persistence/db_probe.py` — thêm: `DatabaseProbe` (`SELECT 1`, cache 5 giây, một ping cho mọi request đồng thời).
- `src/backend/app/infrastructure/cdp/local_cdp_client.py`, `infrastructure/auth/postgres_{refresh_tokens,user_repository,login_attempts}.py`, `infrastructure/persistence/postgres_{catalog,conversation_archive,booking}.py` — sửa: 22 chỗ `psycopg.AsyncConnection.connect` đổi sang `connect_async`; `LocalCdpClient` bắt thêm `DatabaseUnavailableError` để vẫn trả `CdpUnavailableError`; bỏ `import psycopg` thừa ở 3 file.
- `src/backend/app/api/errors.py` — sửa: handler `database_unavailable`; `install_error_handlers(app, database_driver_errors=())`.
- `src/backend/app/main.py` — sửa: `db_connection.configure` và `DatabaseProbe` trong lifespan; đăng ký `psycopg.OperationalError` vào handler; `/health/ready` thêm trường `database`.
- `src/backend/app/core/config.py` — sửa: `db_connect_timeout_seconds` (3), `db_tcp_user_timeout_ms` (15000).
- `src/shared/contracts/openapi.yaml` — sửa: version 1.13.0 → 1.14.0.
- `src/shared/contracts/schemas/common.yaml` — sửa: mã lỗi `DATABASE_UNAVAILABLE`, cập nhật mô tả `retryable`.
- `src/frontend/src/types/api.gen.ts` — sửa: thêm `DATABASE_UNAVAILABLE` vào `ErrorCode` và mô tả (sinh tự động bằng `openapi-typescript`; sửa tay đúng như đầu ra sinh, chưa chạy lại bộ sinh vì worktree không có `node_modules`).
- `src/backend/tests/unit/infrastructure/test_db_connection.py`, `test_db_probe.py`, `src/backend/tests/unit/api/test_database_unavailable.py` — thêm: 16 test.
- `src/backend/README.md`, `docs/spec/hop-dong-tich-hop-backend.md`, `.env.example` — sửa: mô tả hành vi, biến cấu hình.
- `history/2026-10-02-backend-db-unavailable-degraded.md` — thêm: entry này.

## Quyết định

- Chủ dự án chỉ đạo bỏ qua chốt PRD; đề xuất `docs/prd/update/2026-10-02-db-ha-do-ben-ket-noi.md` (NFR-REL-03, mã lỗi mới) nằm ở PR của nhánh `khoa/db-private-link-failover-ssh`, trạng thái `chờ chốt`.
- **Lệch so với plan:** dùng keepalive và `tcp_user_timeout` thay `statement_timeout`. `statement_timeout` sẽ cắt nhầm truy vấn dài hợp lệ (nạp lại toàn catalog), còn keepalive vẫn phát hiện DB chết giữa chừng.
- `/health/ready` chỉ báo `database`, không đổi HTTP status theo DB: orchestrator không restart app và deploy không bị hoàn tác vì DB gián đoạn; liveness `/health` không đụng DB.
- Lỗi rớt giữa chừng (`psycopg.OperationalError`) do composition root đăng ký vào handler, giữ quy tắc `api` không import driver (`architecture.md` §2 quy tắc 6). `application` chỉ biết `DatabaseUnavailableError`.
- Không thêm pool (A7 "chưa cần"); không đổi `postgres_cdp_reader`, `postgres_search_logs`, `vectors/postgres_store` vì đã có `connect_timeout` riêng.
- Contract thêm mã lỗi nên tăng minor 1.14.0 (cộng thêm, không phá v1).

## Kiểm tra

- `python3 -m pytest -q src/backend/tests/architecture src/backend/tests/contract src/backend/tests/unit` — PASS toàn bộ (kể cả 16 test mới).
- `PYTHONDONTWRITEBYTECODE=1 python3 src/shared/contracts/tests/validate_contract.py` — PASS (102 schemas, 70 fixture).
- Chạy thật `uvicorn` với `DATABASE_URL` trỏ cổng chết: `/health` 200; `/health/ready` 200 kèm `"database":"down"`; `POST /api/v1/auth/login` trả 503 `DATABASE_UNAVAILABLE`, `retryable: true`, `Retry-After: 5` trong khoảng 5 ms.
- Chưa chạy: test integration có Postgres thật (`RUN_POSTGRES_INTEGRATION=1`), kịch bản dừng container Postgres rồi bật lại để kiểm tự hồi phục, frontend `generate:api-types`.

## Còn lại / rủi ro

- Chưa kiểm tự hồi phục trên Postgres thật (dừng rồi bật lại container).
- Luồng stream `/assistant/itineraries/stream` ném lỗi trong generator nên không đi qua handler; chưa xử lý.
- Cần chạy lại `npm run generate:api-types` ở frontend khi có môi trường để chắc `api.gen.ts` khớp đầu ra bộ sinh.
- NFR-REL-03 và mã `DATABASE_UNAVAILABLE` chờ chốt PRD.
