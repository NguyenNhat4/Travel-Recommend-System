# Kế hoạch triển khai cảnh báo crawler và container

- Ngày: 2026-09-30
- Proposal: `docs/prd/update/2026-09-30-crawler-container-monitoring-alerts.md`
- Mã NFR: NFR-SEC-01, NFR-MAINT-01
- Môi trường: staging trước; chưa triển khai production

## Phạm vi

- Ghi Docker lifecycle events vào JSONL để giữ bằng chứng trước khi container `--rm` bị xóa.
- Cho Ops Agent đọc crawler logs và Docker events.
- Tạo log-based metrics và alert policies cho crawler partial/failure, service container stop, OOM và watcher heartbeat absence.
- Không đổi semantics crawler one-shot và không bật `restart=always`.
- Không cập nhật nội dung PRD theo yêu cầu người dùng; proposal đã chốt là căn cứ thay đổi lần này.

## Thứ tự

1. Chạy test layout trước khi thêm implementation (RED).
2. Thêm watcher, systemd unit, installer, Ops Agent receivers và Terraform metrics/alerts.
3. Chạy shell/Python/Terraform validation và kiểm tra diff không chứa secret.
4. Trên VM staging: cài watcher, kiểm tra heartbeat/event file, reload Ops Agent và xác nhận log vào Cloud Logging.
5. Chạy Terraform plan staging; review danh sách resource trước khi apply.
6. Tạo test container lỗi/OOM có kiểm soát, xác nhận alert; sau đó rollback test artifact nếu cần.

## Rollback

- Disable watcher bằng `sudo systemctl disable --now vota-docker-event-watcher.service`.
- Revert Terraform resources bằng plan đã review; không xóa state bucket.
- Giữ crawler runner one-shot và log host hiện có.

## Acceptance evidence

- `test_staging_layout.sh`, `terraform fmt`, `terraform validate` pass.
- VM có service watcher active, heartbeat tăng đều và event `die` được ghi.
- Ops Agent active với hai receiver mới.
- Cloud Logging có structured Docker events và crawler exit markers.
- Alert policies tồn tại trong Terraform state; test event tạo incident đúng severity.
