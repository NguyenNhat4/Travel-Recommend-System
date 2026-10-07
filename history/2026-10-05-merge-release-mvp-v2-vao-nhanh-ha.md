# Merge origin/release-mvp-v2 vào nhánh HA

- Ngày: 2026-10-05
- Tác giả: Khoa / Claude
- Nhánh: khoa/ha-load-balancing-merge (merge `origin/release-mvp-v2` 255c1c0 vào `khoa/ha-load-balancing` 5db8478)
- Trạng thái: hoàn thành
- Phạm vi: backend | ops | docs

## Mục tiêu

Đưa các thay đổi mới của `release-mvp-v2` (booking đơn nháp, gợi ý tìm kiếm, contract, mock, frontend) vào nhánh HA mà không làm mất công việc HA. `git pull` trực tiếp bị hủy vì cây làm việc có file chưa commit của việc khác, nên merge làm trong một worktree sạch.

## File thay đổi

Xung đột (3 file, đều giữ cả hai bên):

- `ops/docker-compose.backend-vm.yml` — upstream thêm `ALLOWED_ORIGINS` vào `environment` của frontend, nhánh HA thêm `mem_limit`/`cpus`/`stop_grace_period`; giữ cả hai, `ALLOWED_ORIGINS` trong khối `environment`, giới hạn ở cấp service.
- `src/backend/tests/fakes/booking.py` — `InMemoryBookingStore.__init__` giữ cả `self.leader_held` (HA) và `self.drafts` (upstream).
- `src/backend/tests/integration/test_booking_postgres.py` — giữ test khoá leader (HA) và các test đơn nháp (upstream, migration 0007).

Tự merge đúng (đã kiểm diff so với upstream chỉ còn thay đổi HA): `src/backend/app/core/config.py`, `src/backend/app/main.py`, `src/backend/app/infrastructure/persistence/postgres_booking.py`.

## Quyết định

- Không merge trong cây làm việc chính vì có file chưa commit (workflow CI, `scripts/`, `Dockerfile.backend`, `.dockerignore`) cũng bị upstream sửa.
- Mọi xung đột giải quyết bằng giữ cả hai, không bỏ thay đổi nào của hai phía.

## Kiểm tra

- `pytest src/backend/tests --ignore=integration`: 1190 passed.
- Test tích hợp trên Postgres 16 Docker dựng từ schema đã merge (gồm migration 0007) và Redis tạm: 26 passed, kể cả test khoá leader và test đơn nháp của upstream; chạy lại qua pgbouncer sidecar: 26 passed, `test_pgbouncer_pool.py` 4 passed (250 client: trực tiếp lỗi 15, qua pooler lỗi 0, đỉnh 12 kết nối thật).
- `validate_contract.py`: PASS (109 schemas, 87 fixtures).
- Frontend `vitest run`: 602 passed, 1 failed (`floatingWidgetOpening.test.tsx`: "prefills a suggestion..."). Test này **fail y hệt trên `origin/release-mvp-v2` thuần**, không do merge.

## Còn lại / rủi ro

- Nhánh này chưa thay `khoa/ha-load-balancing`; cây làm việc chính còn file chưa commit của việc khác nên chưa fast-forward được.
- Test frontend `floatingWidgetOpening` lỗi sẵn ở upstream; cần chủ của phần widget xử lý.
