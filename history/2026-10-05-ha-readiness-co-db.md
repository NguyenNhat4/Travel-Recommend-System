# Readiness có kiểm DB cho nhóm HA (6.5)

- Ngày: 2026-10-05
- Tác giả: Khoa / Claude
- Nhánh: khoa/ha-load-balancing
- Trạng thái: hoàn thành
- Phạm vi: backend | infra | docs

## Mục tiêu

VM mất đường tới DB phải bị loại khỏi rotation của load balancer mà không bị autohealing thay vô ích.

## File thay đổi

- `src/backend/app/infrastructure/persistence/db_probe.py` — thêm: `DatabaseProbe` (`SELECT 1`, timeout, cache, khóa một lượt)
- `src/backend/app/core/config.py` — sửa: `ready_requires_db`, `ready_db_timeout_seconds`, `ready_db_cache_seconds`
- `src/backend/app/main.py` — sửa: dựng probe trong lifespan; `/health/ready` thêm điều kiện DB và trường `db`
- `src/backend/tests/unit/api/test_db_readiness.py` — thêm: 9 test
- `infra/terraform/environments/staging-ha/compose.ha.yml` — sửa: `READY_REQUIRES_DB=true`
- `docs/plan/2026-10-05-ha-load-balancing.md` — sửa: use case và dòng 6.5

## Quyết định

- Chỉ readiness kiểm DB; liveness (`/health/live`) giữ nguyên không phụ thuộc DB (6.0).
- Probe dùng `database_url` mà request dùng, nên hỏng sidecar pgbouncer (6.4) cũng bị phát hiện.
- Mặc định tắt: staging một VM giữ nguyên hành vi.
- Use case: VM #2 mất đường DB trong khi 2 VM kia bình thường (plan §3b).

## Kiểm tra

- `pytest` các file `test_db_readiness.py`, `test_ha_readiness.py`, `tests/architecture`: 27 passed.
- Chạy thật trên Postgres 16 Docker: DB chạy True (0,05 giây); dừng DB False ngay; khởi động lại tự True.
- Chưa chạy: LB thật; thời gian phát hiện trên cloud.

## Còn lại / rủi ro

- Mỗi worker có một probe riêng; với cache 5 giây tối đa khoảng 1 kết nối mỗi 5 giây mỗi worker, không đáng kể.
