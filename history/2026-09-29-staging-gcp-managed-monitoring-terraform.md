# Thêm Terraform cho Google Cloud Managed Monitoring staging

- Ngày: 2026-09-29
- Tác giả: Người yêu cầu / Codex
- Nhánh: `khoa/monitoring-system`
- Trạng thái: dang dở — cấu hình và CI validation đã thêm; chưa apply staging cloud
- Phạm vi: DevOps, monitoring, CI/CD

## Mục tiêu

Triển khai cấu hình monitoring staging đầy đủ theo hướng Google Cloud Managed Monitoring + Terraform. Staging giữ đầy đủ production-grade coverage; không tạo hoặc cấu hình live-environment resources trong task này. Crawler monitor UI không thuộc phạm vi.

## File thay đổi

- `.gitignore` — sửa: bỏ qua Terraform cache, state, plan và tfvars thật.
- `.github/workflows/monitoring-terraform-staging.yml` — thêm: PR fmt/validate và apply staging có protected environment, WIF và GCS backend.
- `docs/plan/2026-09-29-staging-gcp-managed-monitoring.md` — thêm: thiết kế, preflight và acceptance scope.
- `infra/monitoring/versions.tf` — thêm: Terraform/provider constraints và GCS backend.
- `infra/monitoring/backend.tf` — thêm: ghi chú partial backend configuration.
- `infra/monitoring/backend.staging.hcl.example` — thêm: ví dụ bucket/prefix state staging.
- `infra/monitoring/provider.tf` — thêm: Google provider.
- `infra/monitoring/variables.tf` — thêm: biến staging và validation.
- `infra/monitoring/locals.tf` — thêm: labels và notification channel selection.
- `infra/monitoring/main.tf` — thêm: dashboard, alert policies, uptime check, log metric và email channel.
- `infra/monitoring/outputs.tf` — thêm: resource IDs phục vụ post-apply verification.
- `infra/monitoring/staging.tfvars.example` — thêm: template biến staging không chứa secret thật.
- `infra/monitoring/ops-agent-staging.yaml` — thêm: Ops Agent host metrics và Docker log pipeline.
- `infra/monitoring/README.md` — thêm: cách validate/init/plan/apply staging và boundary crawler monitor.
- `infra/monitoring/modules/README.md` — thêm: module boundary dành cho môi trường thứ hai về sau.
- `infra/monitoring/tests/test_staging_layout.sh` — thêm: guard staging-only và required resource checks.
- `infra/monitoring/.terraform.lock.hcl` — thêm: lock Google provider v6.50.0 sau Terraform init.
- `history/2026-09-29-staging-gcp-managed-monitoring-terraform.md` — thêm: entry lịch sử task.

## Quyết định

- Chỉ cấu hình root `infra/monitoring` cho `staging`; không tạo production resource/path.
- Terraform state staging dùng GCS backend với prefix `monitoring/staging`; bucket và IAM là preflight bên ngoài repo.
- Terraform quản lý Cloud Monitoring/Logging control-plane resources; Ops Agent YAML được version trong repo nhưng chưa tự cài vào VM trong phiên này.
- Notification email là sensitive variable; không commit email/webhook secret.
- Không đưa `src/data_collection/monitor.py` hoặc crawler-specific metric vào monitoring package.

## Kiểm tra

- `bash infra/monitoring/tests/test_staging_layout.sh` — PASS.
- `terraform -chdir=infra/monitoring fmt -check -recursive` — PASS.
- `bash -n infra/monitoring/tests/test_staging_layout.sh` — PASS.
- PyYAML parse và semantic checks cho `.github/workflows/monitoring-terraform-staging.yml` — PASS.
- `git diff --check` — PASS.
- `terraform init -backend=false` — PASS, Google provider v6.50.0 đã được tải và lock.
- `terraform validate -no-color` — INCONCLUSIVE trên máy local: Google provider Darwin plugin không handshake được với Terraform; workflow Ubuntu sẽ validate lại.
- Ops Agent first rollout — rollback an toàn: VM agent log xác nhận thiếu `roles/monitoring.metricWriter`/`roles/logging.logWriter` và cấu hình `hostmetrics.scrapers` không được schema của agent chấp nhận; config đã được sửa và sẽ retry sau khi cấp IAM.
- `terraform apply` — chưa chạy; chưa có staging state bucket/credentials/target values.

## Còn lại / rủi ro

- Tạo GCS state bucket staging, bật versioning và cấp IAM trước `terraform init` với backend thật.
- Cấu hình GitHub Environment `staging`: `GCP_WIF_PROVIDER`, `GCP_CI_SERVICE_ACCOUNT`, `GCP_PROJECT_ID`, `TF_STATE_BUCKET`, VM names, uptime host/path và notification email.
- Cài Ops Agent lên App VM và DB VM bằng cấu hình đã version; kiểm tra metric/log trước apply alert policy.
- Chạy GitHub Actions validate/plan/apply từ approved release ref; chưa có bằng chứng cloud runtime trong task này.
