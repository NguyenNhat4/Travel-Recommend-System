# Apply Google Cloud Managed Monitoring cho staging

- Ngày: 2026-09-29
- Trạng thái: hoàn tất phần triển khai staging; còn chờ xác nhận email và sửa endpoint public
- Phạm vi: chỉ staging; không tạo hoặc thay đổi resource production; không bao gồm crawler monitor

## Kết quả triển khai

- Project: `vinpearl-508801`.
- Remote Terraform state: `gs://vinpearl-508801-staging-tfstate`, prefix `monitoring/staging`.
- Bucket đã bật versioning, uniform bucket-level access và public access prevention.
- Terraform apply: `9 added, 0 changed, 0 destroyed`.
- Tài nguyên gồm dashboard, uptime check, 5 alert policies, log-based metric và email notification channel.
- Terraform plan sau apply: `No changes`; state đã hội tụ.
- Ops Agent trên App VM `vota-backend-crawler-recsys` và DB VM `v-ota-db-dev` active; startup checks về ports, network và API đều PASS.
- Đã cấp `roles/monitoring.metricWriter` và `roles/logging.logWriter` cho service account của hai VM.

## Kiểm tra thực tế

- Uptime check kiểm tra HTTPS `v-ota.duckdns.org/health/ready` mỗi 60 giây từ USA, Europe và Asia Pacific.
- Endpoint public tại thời điểm kiểm tra trả HTTP `404`; vì vậy uptime alert đang phản ánh đúng readiness chưa đạt, không được đánh dấu healthy giả.
- Email notification channel đã tạo và enabled; trạng thái verification không được API trả về trong lần kiểm tra. Người vận hành cần xác nhận email theo thư của Google Cloud nếu console yêu cầu.

## Lệnh kiểm tra

- `bash infra/monitoring/tests/test_staging_layout.sh` — PASS.
- `terraform -chdir=infra/monitoring fmt -check -recursive` — PASS.
- `terraform -chdir=infra/monitoring validate` — PASS.
- Terraform plan staging sau apply — PASS, không có drift.
- Cloud Monitoring API — dashboard, uptime config, alert policies và log metric tồn tại.

## Việc còn lại

- Xác định URL readiness public đúng của staging hoặc expose backend readiness qua routing hiện tại; không tự đổi path khi chưa có xác nhận.
- Xác nhận email notification channel trong Google Cloud Console.
- Thiết lập GitHub Environment `staging` theo workflow, đặc biệt `TF_STATE_BUCKET` và các WIF secrets/variables, trước khi dùng CI/CD tự động.
