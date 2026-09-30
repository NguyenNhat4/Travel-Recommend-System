# Triển khai artifact giám sát crawler và container

- Ngày: 2026-09-30
- Trạng thái: dang dở — đã sửa workspace và validation cục bộ; chưa cài VM/chạy Terraform apply

## Quyết định

- Người dùng đã chốt phạm vi trong hội thoại và yêu cầu không cập nhật nội dung PRD.
- Giữ crawler `--rm`; dùng Docker event watcher để lưu lifecycle event trước khi container bị xóa.
- Chỉ chuẩn bị artifact staging; chưa có quyền/bằng chứng để mutate VM hoặc GCP.

## File thay đổi

- `docs/prd/update/2026-09-30-crawler-container-monitoring-alerts.md`
- `docs/plan/2026-09-30-crawler-container-monitoring-alerts.md`
- `infra/monitoring/main.tf`
- `infra/monitoring/ops-agent-staging.yaml`
- `infra/monitoring/outputs.tf`
- `infra/monitoring/README.md`
- `infra/monitoring/tests/test_staging_layout.sh`
- `infra/monitoring/vota-docker-event-watcher.py`
- `infra/monitoring/vota-docker-event-watcher.service`
- `infra/monitoring/install-vota-docker-event-watcher.sh`
- `.github/workflows/monitoring-agent-cd-staging.yml`
- file này

## Kiểm tra

- Test layout đã được viết trước implementation và đã chuyển từ fail do thiếu artifact sang PASS.
- Đã chạy kiểm tra cú pháp Python và Bash qua test layout/validation cục bộ.
- Chưa chạy Terraform apply, chưa SSH/cài trên VM, chưa có Cloud Monitoring runtime evidence.
- Đã tách đường triển khai watcher/Ops Agent thành workflow CD riêng; workflow crawler không sở hữu việc restart Ops Agent.

## Việc còn lại

Chạy workflow monitoring-agent CD để cài watcher/restart Ops Agent trên VM staging, kiểm tra Ops Agent/Cloud Logging, sau đó tạo và review staging plan trước apply.
