# Merge khoa/backend-db-unavailable-degraded vào nhánh HA

- Ngày: 2026-10-08
- Tác giả: Khoa15 / Claude (agent)
- Nhánh: khoa/ha-runtime-bootstrap-fix (merge `khoa/backend-db-unavailable-degraded` @ d5452fc)
- Trạng thái: hoàn thành
- Phạm vi: backend | contract | frontend (kiểu sinh tự động) | docs

## Mục tiêu

Đưa commit `d5452fc` (DB không với tới được thì trả 503 `DATABASE_UNAVAILABLE`, không treo; `connect_async` có timeout) vào nhánh HA. Người dùng chốt D1 = merge.

## File xung đột và cách giải quyết

- `src/shared/contracts/openapi.yaml` — giữ version `1.18.0` của HEAD (nhánh kia đặt `1.14.0`, cũ hơn).
- `src/shared/contracts/schemas/common.yaml` — giữ cả hai: mã booking của HEAD và `DATABASE_UNAVAILABLE`.
- `src/frontend/src/types/api.gen.ts` — giữ dòng `ErrorCode` của HEAD, thêm `"DATABASE_UNAVAILABLE"` (sinh từ contract, không sửa tay ngoài thay đổi này).
- `src/backend/app/api/errors.py` — giữ cả hai handler: `embedding_unavailable` (HEAD) và `database_unavailable` (nhánh kia). `install_error_handlers` nhận thêm `database_driver_errors` có mặc định rỗng.
- `src/backend/app/infrastructure/persistence/db_probe.py` — giữ API của HEAD (`ok()`, `cache_seconds`, `select_one` được inject). `main.py` và các test HA đều dùng API này.
- `src/backend/app/main.py` — giữ logic readiness của HEAD; thêm `db_connection.configure(...)` từ nhánh kia để áp timeout kết nối. Không đưa lại `print` vì nhánh logging đã thay bằng log.
- `src/backend/tests/unit/infrastructure/test_db_probe.py` — viết lại theo API của HEAD, giữ đủ ba kịch bản của nhánh kia (cache TTL và phục hồi; gọi đồng thời chỉ ping một lần; lỗi bất kỳ là "không sẵn sàng").

## Quyết định

- **Readiness khi DB không với tới được: giữ hành vi HA (HEAD), không theo nhánh kia.** Nhánh kia ghi `/health/ready` luôn 200 và DB không quyết định HTTP status. HEAD trả 503 cho VM mất DB để load balancer loại VM đó (plan HA mục 6.5, và logic "mất DB một VM / mọi VM" trong `main.py`). Nếu bỏ hành vi này, VM mất DB vẫn nhận traffic. Đây là hai thiết kế mâu thuẫn; quyết định này được ghi để người chốt có thể đảo lại.
- Probe của HEAD dùng `psycopg.connect(connect_timeout=...)`, chưa dùng `connect_async` (không có `tcp_user_timeout`/keepalive của nhánh kia). Có thể nối sau nếu cần.

## Kiểm tra

- Contract: `validate_contract.py` — PASS (117 schemas, 93 fixtures; CDP clone 12 schemas).
- Backend unit (`pytest src/backend/tests --ignore=src/backend/tests/integration`, venv nháp): 1831 passed, 2 skipped trước khi sửa `test_db_probe.py`; sau khi viết lại, các test liên quan DB và readiness (5 file, 33 test) PASS.
- Không còn marker xung đột trong `src/`, `docs/`, `ops/`, `infra/`.

## Còn lại / rủi ro

- Chưa chạy lại toàn bộ backend unit sau khi viết lại `test_db_probe.py` (chỉ chạy nhóm liên quan).
- Chưa chạy frontend test sau merge (chỉ kiểu sinh tự động thay đổi).
- Chưa có quyết định đề xuất PRD cho thay đổi readiness; hành vi giữ theo HEAD.
