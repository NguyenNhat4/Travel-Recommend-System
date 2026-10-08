# Nối log JSON vào Ops Agent, metric và dashboard

- Ngày: 2026-10-06
- Tác giả: Khoa / Claude
- Nhánh: khoa/logging-monitoring
- Trạng thái: dang dở
- Phạm vi: docs

## Mục tiêu

Sau khi backend, frontend, crawler phát log JSON theo `docs/spec/logging-schema.md`, sửa phần monitoring để `severity`, request và lỗi được đếm đúng (điều tra ngày 2026-10-06: severity rỗng, metric đếm health check, metric lỗi chỉ thấy lỗi của Ops Agent).

## File thay đổi

- `infra/monitoring/ops-agent-staging.yaml` — sửa: parse hai tầng cho `docker_json` (vỏ docker rồi dòng app), thời gian từ `ts_utc`, `severity` từ `jsonPayload.severity`
- `infra/monitoring/main.tf` — sửa: `staging_error_logs` loại `logName:"ops-agent"`; metric requests/5xx dùng `event=http.request`, `service=backend`, loại `/health/`; metric crawler exit 3 dùng `event=run.end` + `exit_code=3`
- `infra/monitoring/dashboard.tf` — sửa: panel log backend/frontend/crawler lọc theo `jsonPayload.service`
- `infra/monitoring/tests/test_staging_layout.sh` — sửa: kiểm filter mới, cấm regex text của uvicorn
- `history/2026-10-06-logging-monitoring.md` — thêm

## Quyết định

- Metric exit 3 chuyển sang `run.end` để không đếm đôi giữa stdout container và file job log.
- Không thêm label `service` vào metric lỗi (đổi descriptor buộc tạo lại metric); dashboard tách theo service bằng panel log.
- Deploy cùng lúc với backend JSON: metric cũ (regex text uvicorn) sẽ về 0 sau khi backend đổi.

## Kiểm tra

- `bash infra/monitoring/tests/test_staging_layout.sh`: PASS. `terraform validate`: valid. `terraform fmt`: đã chạy.
- Chưa kiểm trên VM thật: cú pháp `parse_json` (`time_key`, `time_format`) và `modify_fields` của Ops Agent, chưa `terraform plan/apply`.

## Còn lại / rủi ro

- Thử trên một VM staging: log container phải có `severity` và `jsonPayload.service`; nếu `time_format` không khớp thì bỏ `time_key`.
- Nhóm VM HA (COS, không có Ops Agent) để sau.
- Metric/alert nhóm HA không dùng các filter này.
