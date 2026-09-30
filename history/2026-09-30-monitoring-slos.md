# Bổ sung SLO cho staging

- Ngày: 2026-09-30
- Tác giả: người dùng / agent
- Nhánh: khoa/agent-watcher-containers
- Trạng thái: hoàn thành
- Phạm vi: monitoring

## Mục tiêu

Thêm SLO availability, error rate và latency cho staging, đồng thời hiển thị compliance/error budget trên dashboard Cloud Monitoring.

## File thay đổi

- `docs/plan/2026-09-30-monitoring-slos.md` — thêm: plan triển khai và evidence.
- `infra/monitoring/main.tf` — thêm: HTTP access metrics, custom service, ba SLO và dashboard scorecards.
- `infra/monitoring/outputs.tf` — thêm: output `slo_ids`.
- `infra/monitoring/tests/test_staging_layout.sh` — thêm: assertions cho metrics, service, SLO và widgets.
- file này — cập nhật: trạng thái và evidence triển khai.

## Quyết định

- Service SLO dùng custom service `vota-staging-api`.
- Availability đo từ uptime check readiness hiện có.
- Error rate đo từ access log Uvicorn của Backend.
- Latency đo từ uptime check request latency.
- Mục tiêu staging: availability `99.5%`, error rate `99.5% good requests`, latency `95%` cửa sổ dưới `1s`.
- Không sửa PRD; thay đổi hiện thực NFR-PERF-01/NFR-REL-01 trong lớp vận hành staging.

## Kiểm tra

- Đã kiểm tra live Cloud Monitoring: uptime `check_passed` và `request_latency` có dữ liệu; app access log có HTTP status.
- `bash infra/monitoring/tests/test_staging_layout.sh`: PASS.
- `terraform -chdir=infra/monitoring fmt -check -recursive`: PASS.
- `git diff --check`: PASS.
- Remote Terraform plan parse: PASS; targeted plans không có destroy.
- Staging apply: 3 telemetry/service resources created, 3 SLOs created, dashboard updated.
- Live verification: custom service và ba SLO tồn tại; dashboard có 6 SLO widgets; log metrics có đúng filters.

## Còn lại / rủi ro

- Full refresh plan còn hiển thị 15 thay đổi nhạy cảm `notification_channels` nhưng không có destroy; không apply phần drift này trong targeted rollout.
- SLO error rate phụ thuộc access-log format của Uvicorn; nếu format đổi, metric filter phải cập nhật.
- Local `terraform validate` bị provider binary `darwin_amd64` handshake; remote plan đã parse/apply thành công.
