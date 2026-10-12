# Plan monitoring staging (infra/monitoring) với state có sẵn trên GCS

- Ngày: 2026-10-08
- Tác giả: Khoa15 / Claude (agent)
- Nhánh: khoa/ha-runtime-bootstrap-fix
- Trạng thái: đã hoàn thành (mục 2.6 của `docs/plan/2026-10-08-hoan-thanh-todo-ha.md`); chưa apply
- Phạm vi: infra/monitoring (không đổi mã Terraform)

## Mục tiêu

Hoàn thành mục 2.6: chạy `terraform plan` cho `infra/monitoring` với backend đã có state trên GCS, để kiểm tra state và cấu hình khớp nhau.

## Nguồn giá trị

- Bucket state là `vinpearl-508801-staging-tfstate` (bucket duy nhất có state Terraform trong project, ngoài bucket `_cloudbuild`). State monitoring nằm ở `monitoring/staging/default.tfstate`.
- Các giá trị trong `staging.tfvars` lấy từ state đó: app VM `vota-backend-crawler-recsys`, DB VM `v-ota-db-dev`, replica `vota-staging-db-replica` (zone `asia-southeast1-b`), uptime `v-ota.duckdns.org` với path `/health/ready`, email alert `nguyentrongdangkhoa15@gmail.com`.
- `log_retention_days = 30`, `name_prefix = vota-staging`.

## File đã tạo (không commit)

- `infra/monitoring/backend.staging.hcl`: `bucket = "vinpearl-508801-staging-tfstate"`, `prefix = "monitoring/staging"`. Đã thêm vào `.gitignore` theo README (`Never commit backend.staging.hcl`).
- `infra/monitoring/staging.tfvars`: đã có sẵn trong `.gitignore` (`*.tfvars`).

## Kết quả plan

- `terraform init -backend-config=backend.staging.hcl`: OK.
- Lần plan đầu: 7 resource bị đánh dấu xoá và 19 thay đổi, do thiếu `db_replica_vm_name`/`db_replica_zone`. Đã khai báo đúng replica theo state.
- Plan sau cùng: `Plan: 0 to add, 24 to change, 0 to destroy.`
- Các thay đổi là in-place và không ảnh hưởng dữ liệu:
  - `notification_channels` (23 policy): provider báo "value is unchanged" (giá trị nhạy cảm, chỉ hiển thị).
  - Dashboard `staging_overview`: provider điền thêm giá trị mặc định (`xPos = 0`, `lowerBound = 0`, `style = {}`).
- `google_logging_project_bucket_config` (`_Default`) đã nằm trong state, không cần import lại.

## Không làm

- Không `terraform apply`. Thay đổi trong plan là thuần cấu hình provider, không có thay đổi thực tế. Nếu muốn đưa state về khớp hoàn toàn, chạy apply có chủ đích sau khi người vận hành xem lại plan.

## Kiểm tra

```bash
cd infra/monitoring
terraform init -input=false -reconfigure -backend-config=backend.staging.hcl
terraform plan -input=false -no-color -var-file=staging.tfvars | grep -E "^Plan:"
```

## Còn lại / rủi ro

- Quyết định có apply để xoá drift cosmetic không (người vận hành).
- Email và uptime host đang lấy từ state, không xác nhận lại với người vận hành.
