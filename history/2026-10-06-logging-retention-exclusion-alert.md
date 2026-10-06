# Retention, exclusion và cảnh báo lượng nạp của Cloud Logging

- Ngày: 2026-10-06
- Tác giả: Khoa / Claude
- Nhánh: khoa/logging-integration-fixes
- Trạng thái: hoàn thành
- Phạm vi: docs

## Mục tiêu

Kiểm `vinpearl-508801` cho thấy `_Default` giữ log 30 ngày theo mặc định GCP, không khai báo trong Terraform, không có exclusion hay cảnh báo lượng nạp. Đưa vòng đời log vào code.

## File thay đổi

- `infra/monitoring/logging_retention.tf` — thêm: `google_logging_project_bucket_config` cho `_Default` (import block), exclusion DEBUG + health check 200, alert `bytes_ingested`
- `infra/monitoring/variables.tf` — sửa: `log_retention_days` (30), `log_ingest_alert_gib_per_hour` (0,25 ≈ 6 GiB/ngày)
- `infra/monitoring/staging.tfvars.example` — sửa: thêm `log_retention_days`
- `infra/monitoring/tests/test_staging_layout.sh` — sửa: kiểm file và ba tài nguyên mới
- `history/2026-10-06-logging-retention-exclusion-alert.md` — thêm

## Quyết định

- Giữ 30 ngày (như đang chạy) để apply không đổi hành vi; chỉ ghi vào code.
- Exclusion không ảnh hưởng log-based metric (metric đếm trước khi loại).
- Import `_Default` bằng import block (Terraform >= 1.6 theo versions.tf).

## Kiểm tra

- `terraform validate`: hợp lệ; `test_staging_layout.sh`: PASS. Chưa `terraform plan/apply`.

## Còn lại / rủi ro

- Chạy `terraform plan` trước khi apply để chắc import `_Default` không đổi gì ngoài retention.
- Tên metric `logging.googleapis.com/billing/bytes_ingested` và `resource.type="global"` chưa thử trên project thật.
- Regex exclusion chỉ khớp dòng health dạng text cũ của uvicorn; log JSON mới đã ghi health ở DEBUG nên không phát sinh.
