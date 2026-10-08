# Giới hạn log container và gộp log lỗi Redis của frontend

- Ngày: 2026-10-06
- Tác giả: Khoa / Claude
- Nhánh: khoa/logging-integration-fixes
- Trạng thái: hoàn thành
- Phạm vi: frontend, docs

## Mục tiêu

Log JSON làm log container lớn hơn; docker json-file mặc định không giới hạn nên có nguy cơ đầy đĩa VM. Khi Redis sập, `bff.session.store` ghi ERROR mỗi lần client retry.

## File thay đổi

- `docker-compose.yml` — sửa: `x-logging` (json-file, 50 MB x 5) cho mọi service
- `ops/docker-compose.backend-vm.yml` — sửa: như trên cho backend, frontend
- `src/data_collection/run_daily_docker.sh` — sửa: `--log-opt max-size=50m --log-opt max-file=5` cho ba lệnh `docker run`
- `src/frontend/src/services/server/sessionStore.ts` — sửa: ghi lỗi Redis lần đầu rồi gộp mỗi 60 giây kèm `count`; `bff.session.store.recovered` khi kết nối lại
- `history/2026-10-06-logging-gioi-han-log-container.md` — thêm

## Quyết định

- Mỗi container tối đa 250 MB trên đĩa; Cloud Logging giữ lâu dài.
- Chưa áp cho nhóm VM HA (`compose.ha.yml`, `weaviate.tf`) và container Postgres ở `ops/bootstrap-db-vm.sh`.
- Theo yêu cầu người dùng: không chạy test thêm, quan sát trực tiếp trên VM.

## Kiểm tra

- `docker compose -f docker-compose.yml config -q`: hợp lệ. `bash -n run_daily_docker.sh`: ok. `tsc`: chỉ còn lỗi casing `WidgetProgress` có sẵn.
- Chưa chạy test hay thử trên VM.

## Còn lại / rủi ro

- Container đang chạy chỉ nhận log-opts mới khi được tạo lại (lần deploy kế).
- Cách Ops Agent xử lý đúng lúc file xoay vòng cần quan sát trên VM.
