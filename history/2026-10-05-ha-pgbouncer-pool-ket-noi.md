# pgbouncer sidecar và DSN riêng cho khoá leader (6.3 + 6.4)

- Ngày: 2026-10-05
- Tác giả: Khoa / Claude
- Nhánh: khoa/ha-load-balancing
- Trạng thái: hoàn thành
- Phạm vi: backend | infra | ops | docs

## Mục tiêu

Backend mở một connection Postgres cho mỗi thao tác; nhiều VM × worker làm hết `max_connections`. Thêm connection pooling mà không làm hỏng khoá leader của job đối soát.

## File thay đổi

- `src/backend/app/core/config.py` — sửa: `leader_lock_database_url`; `shared_backend_violations` cho phép pgbouncer sidecar `127.0.0.1:6432` và bắt buộc DSN leader trực tiếp
- `src/backend/app/infrastructure/persistence/postgres_booking.py` — sửa: `PostgresBookingStore(database_url, leader_lock_database_url)`
- `src/backend/app/main.py` — sửa: truyền DSN leader
- `src/backend/tests/unit/api/test_ha_readiness.py` — sửa: 3 ca pooler/leader/tunnel (tổng 14)
- `src/backend/tests/integration/test_booking_postgres.py` — sửa: test leader dùng `LEADER_LOCK_DATABASE_URL`
- `src/backend/tests/integration/test_pgbouncer_pool.py` — thêm: đo burst 250 client trực tiếp vs pooler, khoá leader qua pooler (cần `RUN_PGBOUNCER_INTEGRATION=1`)
- `infra/terraform/environments/staging-ha/pgbouncer.ini`, `pgbouncer-setup.sh` — thêm: cấu hình và script sinh userlist từ env secret
- `infra/terraform/environments/staging-ha/compose.ha.yml`, `startup.sh.tftpl`, `main.tf` — sửa: sidecar `vota-pgbouncer` ghim digest, backend phụ thuộc pgbouncer healthy, startup chạy script
- `infra/terraform/environments/staging-ha/tests/test_pgbouncer_setup.py` — thêm: 7 test
- `ops/check-db-direct.sh`, `ops/tests/test_check_db_direct.sh` — sửa: chế độ `POOLED=1`
- `docs/plan/2026-10-05-ha-load-balancing.md` — sửa: use case và dòng 6.3 + 6.4

## Quyết định

- Sidecar trên mỗi VM, không dùng pgbouncer trung tâm (tránh thêm một điểm lỗi duy nhất).
- `pool_mode = transaction` với `max_prepared_statements = 100`; đo cho thấy 20 test tích hợp pass.
- Pool 10 + 2 dự phòng mỗi (database, role) sau khi đo: đỉnh thực 12 connection.
- Khoá leader luôn đi DSN trực tiếp; guard bắt buộc đặt `LEADER_LOCK_DATABASE_URL` khi dùng pooler.
- Image ghim digest `edoburu/pgbouncer@sha256:9c7894...` (đã chạy thử, PgBouncer 1.26.0).

## Kiểm tra

- Postgres 16 Docker `max_connections=100` + pgbouncer 1.26: 250 client đồng thời, 3 lần: trực tiếp lỗi 42/83/81, đỉnh ~91 connection; qua pooler lỗi 0, đỉnh 12 connection thật.
- 20 test tích hợp cũ (booking, auth, catalog, CDP) pass qua pooler khi có `LEADER_LOCK_DATABASE_URL`; không có nó, test leader fail đúng như dự đoán.
- `test_pgbouncer_pool.py`: 4 passed (lặp 3 lần, ổn định); `test_pgbouncer_setup.py`: 7 passed; `test_check_db_direct.sh`: PASS; `terraform validate`: pass.
- Chưa chạy: trên VM thật (kéo image qua NAT, quyền `/etc/vota/pgbouncer`, healthcheck `nc`).

## Còn lại / rủi ro

- Mật khẩu role phải là ký tự an toàn trong URL (không `% @ : / "`); script từ chối nếu không.
- Env secret cần thêm `PGBOUNCER_UPSTREAM_HOST`, `LEADER_LOCK_DATABASE_URL`, và DATABASE_URL/CDP_DATABASE_URL trỏ `127.0.0.1:6432`.
