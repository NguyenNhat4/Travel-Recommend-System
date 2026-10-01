# Đo lần gọi web / agent (giai đoạn 2) và tab Realtime trên monitor

- Ngày: 2026-09-30
- Tác giả: Đăng Khôi / Claude Code
- Nhánh: test/newcrawl
- Trạng thái: hoàn thành
- Phạm vi: backend, data, docs

## Mục tiêu

Theo đề xuất đã áp dụng `docs/prd/update-archive/2026-09-30-monitor-trang-thai-db-realtime.md` (người yêu cầu: "Tôi muốn
dùng cách đo của stageMs, 3, đã ok, TÔi muốn làm tiếp trên nhánh test/crawl này luôn"; "làm giai đoạn 2"): mỗi lần web /
agent lấy dữ liệu hiện realtime trên monitor. `docs/prd/deployment-plan.md` §5, `docs/prd/architecture.md` §2.

## File thay đổi

- Lấy commit `f03ffea` của nhánh `feat/search-stage-timing` (tqanh123, chưa merge) bằng `git diff | git apply` — nội dung giữ
  nguyên để khi PR đó merge không conflict; bỏ hai dòng đổi phiên bản 1.8.0 → 1.9.0 vì nhánh này đã ở 1.9.0:
  `docs/spec/hop-dong-tich-hop-search-recommendation.md`, `history/2026-09-29-search-stage-timing.md`,
  `src/backend/app/application/search/use_cases.py` (`StageTimer`, `diagnostics.stageMs`),
  `src/backend/tests/unit/application/test_search_stage_timing.py`, `src/frontend/src/types/api.gen.ts`,
  `src/shared/contracts/schemas/search.yaml`.
- `src/backend/app/core/call_context.py` — thêm: nguồn (`web` | `agent`) và dict chi tiết của lần gọi (ContextVar).
- `src/backend/app/application/ports/call_telemetry.py` — thêm: port `CallTelemetry`.
- `src/backend/app/application/telemetry.py` — thêm: `Traced` bọc use case (sync / async, `lookup`), `summarize` đọc
  `productId`, số kết quả, `stageMs` từ kết quả; không đọc tham số.
- `src/backend/app/infrastructure/telemetry/__init__.py`, `memory.py` — thêm: `InMemoryCallTelemetry` (vòng đệm 2.000, tổng hợp
  p50 / p95, text Prometheus).
- `src/backend/app/api/middleware.py` — sửa: `install_call_telemetry` (request `/api/v1`, tên route dạng `{tham số}` dựng từ
  đường dẫn thật + `path_params`), `route_template`.
- `src/backend/app/api/ops.py` — thêm: `GET /metrics`, `GET /internal/calls`.
- `src/backend/app/application/itinerary/engine_tools.py` — sửa: `_guard` ghi lần gọi nguồn `agent`, logic map lỗi cũ chuyển
  sang `_mapped` (không đổi).
- `src/backend/app/main.py` — sửa: tạo telemetry, middleware, ops router, bọc `TRACED_SERVICES` sau mỗi lần publish catalog,
  ghi số sản phẩm trong bộ nhớ, truyền telemetry cho công cụ agent.
- `src/backend/tests/unit/application/test_call_telemetry.py` — thêm: 8 test.
- `src/data_collection/monitor.py` — sửa: `backend_calls` + route `/api/calls` (đọc `BACKEND_URL`).
- `src/data_collection/monitor_ui/index.html` — sửa: trang "Realtime" (tổng hợp theo nguồn, lần gọi gần nhất, lọc nguồn,
  `productId` mở tab DB), cập nhật tại chỗ 2 giây, không vẽ lại khi không có lần gọi mới.
- `src/data_collection/run_daily_docker.sh` — sửa: truyền `BACKEND_URL` vào container `fresh-monitor`.
- `src/data_collection/tests/test_monitor_backend_calls.py` — thêm: 2 test.
- `docs/spec/hop-dong-tich-hop-backend.md` (§8.6a mới), `src/backend/README.md`, `docs/guide/trien-khai-job-cao-du-lieu.md`,
  `src/data_collection/README.md` — sửa: mô tả endpoint và tab Realtime.
- `history/2026-09-30-do-lan-goi-web-agent-realtime.md` — thêm: entry này.

## Quyết định

- Đã đọc: `docs/prd/architecture.md` §2, `docs/prd/deployment-plan.md` §5, `docs/spec/contracts-guide.md`,
  `src/backend/README.md`, `docs/spec/hop-dong-tich-hop-backend.md` §8, code `main.py`, `api/`, `engine_tools.py`, use case
  search / catalog / recommendation.
- Agent gọi engine **trong tiến trình** (`ITINERARY_DATA_MODE=inprocess`), không qua HTTP → đo ở `_guard` của công cụ, không chỉ
  middleware. Use case được bọc ở composition root nên không sửa ruột use case.
- Endpoint vận hành ngoài `/api/v1`, `include_in_schema=False`, theo tiền lệ `/health` (không có trong `openapi.yaml`); ghi
  trong hợp đồng backend §8.6a. Không có dữ liệu cá nhân, không query string / câu tìm kiếm.
- Đính chính so với đề xuất: `/products`, `/products/{id}` đọc thẳng Postgres mỗi request (`PostgresProductQuery`); chỉ search /
  similar / recommend dùng bản trong bộ nhớ.

## Kiểm tra

- `test_search_stage_timing.py`: 12 passed; `validate_contract.py`: PASS (89 schema, fixture, CDP clone).
- `test_call_telemetry.py`: 8 passed. Test bắt 2 lỗi thật trong lúc viết: tên route lặp `/api/v1/api/v1`, rồi route qua
  `include_router(prefix=…)` chỉ giữ phần sau prefix (FastAPI 0.141.1) → đổi sang dựng tên từ đường dẫn + `path_params`.
- Backend `tests/architecture` + `tests/unit/api` + `tests/unit/application`: 213 passed (trước khi thêm test mới).
- `test_monitor_backend_calls.py`: 2 passed.
- Toàn bộ `src/backend/tests`: 719 passed, 19 skipped (trước: 699 + 12 stageMs + 8 telemetry).
- Toàn bộ `src/data_collection/tests`: 461 passed, 17 skipped; `bash -n run_daily_docker.sh`: ok; `git diff --check`: sạch.
- Chạy thử đầu cuối: backend giả dùng middleware / ops router / telemetry / công cụ agent thật (cổng 8798) + monitor local
  (8799): tab Realtime hiện web và agent tách riêng, `stageMs` 6 bước, lỗi công cụ `error:SEARCH_UNAVAILABLE`, `/metrics`
  đúng định dạng; vị trí cuộn giữ nguyên khi cập nhật.

## Còn lại / rủi ro

- Giai đoạn 1 (sơ đồ quan hệ, luồng dữ liệu, hoạt động DB realtime trong tab DB) chưa làm.
- Chưa chạy backend thật (cần Weaviate / Cohere / khoá JWT); kiểm bằng test và backend giả.
- Chưa commit.
