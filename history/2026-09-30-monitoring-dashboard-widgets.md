# Bổ sung widget dashboard cho watcher và crawler

- Ngày: 2026-09-30
- Trạng thái: hoàn tất ở cấp source; chờ Terraform apply để có runtime evidence

## Phạm vi

Thêm widget vào dashboard staging cho Docker watcher heartbeat, crawler warning/failure và container stop/OOM.

## File thay đổi

- `infra/monitoring/main.tf`
- `infra/monitoring/README.md`
- `infra/monitoring/tests/test_staging_layout.sh`
- file này

## Kiểm tra

- `terraform -chdir=infra/monitoring fmt -check -recursive`: PASS
- `bash infra/monitoring/tests/test_staging_layout.sh`: PASS
- `git diff --check`: PASS

## Việc còn lại

Commit/push branch, tạo PR vào `release-mvp-v2`, sau đó chạy Terraform workflow để cập nhật dashboard trên GCP.
