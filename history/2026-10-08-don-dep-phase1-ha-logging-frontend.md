# Dọn dẹp Phase 1: trùng tên WidgetProgress, bỏ db.pool.exhausted, log-opts nhóm HA

- Ngày: 2026-10-08
- Tác giả: Khoa15 / Claude (agent)
- Nhánh: khoa/ha-runtime-bootstrap-fix
- Trạng thái: hoàn thành
- Phạm vi: frontend | backend | infra | ops | docs

## Mục tiêu

Xử lý ba todo còn mở của logging và HA: (1) hai file `WidgetProgress.tsx` và `widgetProgress.ts` chỉ khác chữ hoa/thường, gây lỗi trên macOS; (2) sự kiện `db.pool.exhausted` có trong allowlist nhưng không có code nào phát ra; (3) nhóm HA chưa có giới hạn log json-file.

## File thay đổi

- `src/frontend/src/features/itinerary/widget/widgetProgress.ts` → `widgetProgressView.ts` — đổi tên (git mv) để tránh trùng tên.
- `src/frontend/src/features/itinerary/widget/WidgetProgress.tsx` — sửa: import `./widgetProgressView`.
- `src/frontend/tests/unit/widgetProgress.test.ts` — sửa: import `widgetProgressView`.
- `src/backend/app/core/logging_config.py` — sửa: bỏ `db.pool.exhausted` khỏi allowlist.
- `docs/spec/logging-schema.md` — sửa: bỏ `db.pool.exhausted` khỏi bảng sự kiện hạ tầng.
- `infra/terraform/environments/staging-ha/compose.ha.yml` — sửa: thêm anchor `x-logging` (json-file, 50 MB × 5) và gắn cho pgbouncer, backend, frontend.
- `ops/bootstrap-db-vm.sh` — sửa: thêm `--log-opt max-size=50m --log-opt max-file=5` cho container Postgres.
- `history/2026-10-08-don-dep-phase1-ha-logging-frontend.md` — thêm: entry này.

## Quyết định

- Đổi tên util thay vì đổi tên component: component `WidgetProgress` đã được import ở `WidgetChat.tsx`.
- Bỏ `db.pool.exhausted` thay vì thêm pool, vì adapter Postgres hiện không có pool để đo (người dùng chốt D3 = xoá).
- Log-opts của container Postgres chỉ áp khi container được tạo; container đang chạy phải được tạo lại mới có hiệu lực.

## Kiểm tra

- `npx vitest run` (src/frontend): 71 file, 717 test PASS. Trước đó 7 file fail vì `pino` chưa được cài; đã chạy `npm install` đồng bộ với lock file.
- `npx tsc --noEmit`: không còn lỗi trong `src/`; lỗi `.next/types` (file sinh tự động cũ) không thuộc repo.
- `pytest src/backend/tests/unit/core src/backend/tests/architecture`: 23 passed (môi trường venv nháp, cài dependency không gồm torch/transformers).
- `docker compose -f compose.ha.yml config` (bản sao không có `env_file` của `/etc/vota`): hợp lệ, cả ba service có `max-size: 50m`.
- `bash -n ops/bootstrap-db-vm.sh`: pass.

## Còn lại / rủi ro

- Chưa chạy `terraform plan` (chưa có biến và secret của nhóm HA trong bước này).
- Log-opts Postgres cần tạo lại container để có hiệu lực.
