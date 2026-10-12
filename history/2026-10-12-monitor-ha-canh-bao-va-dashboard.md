# Monitor HA (PR 1): sửa cảnh báo nhóm, mute có kênh luôn bật, dashboard nhóm

- Ngày: 2026-10-12
- Tác giả: Khoa15 (yêu cầu) / Claude Code (agent)
- Nhánh: Khoa15/adjust-monitor-staging-ha
- Trạng thái: dang dở (code và test local xong; chưa apply, chưa commit, chưa kiểm alert thật trên GCP)
- Phạm vi: infra (staging-ha), docs
- Liên quan: `docs/plan/2026-10-12-monitor-staging-ha.md` (plan đã duyệt), `2026-10-05-ha-canh-bao-nhom-vm.md` (alert nhóm gốc)

## Mục tiêu

Monitor nhóm HA không trả lời được "CPU của VM này thuộc nhóm nào" và `group_at_max` báo nhiễu. Entry này sửa cảnh báo nhóm, thêm kênh báo lỗi cho job mute, và thêm dashboard nhóm. Không đụng VM, template hay MIG.

## File thay đổi

- `docs/plan/2026-10-12-monitor-staging-ha.md` — thêm: plan đã duyệt, kèm kết quả kiểm GCP (chỉ đọc) và trạng thái.
- `infra/terraform/environments/staging-ha/monitoring.tf` — sửa: `locals.group_size_filter` (metric `instance_group/size`); `group_below_min` đếm VM bằng metric của MIG; `group_at_max` đổi thành AND của số VM >= max và CPU nhóm > `cpu_target`, mô tả cập nhật.
- `infra/terraform/environments/staging-ha/alert_mute.tf` — thêm: `retry_config` cho hai job mute; `google_monitoring_notification_channel.email_always` (không có `ignore_changes`); `google_logging_metric.ha_alert_mute_job_failed`; `google_monitoring_alert_policy.mute_job_failed`.
- `infra/terraform/environments/staging-ha/dashboard.tf` — thêm (mới): `google_monitoring_dashboard.ha`.
- `infra/terraform/environments/staging-ha/outputs.tf` — thêm: output `ha_dashboard_url`.
- `infra/terraform/environments/staging-ha/tests/test_alerts.py` — sửa: test `at_max` cũ khóa hành vi sai, viết lại; thêm test cho kênh luôn bật, retry, `group_size_filter`.
- `infra/terraform/environments/staging-ha/tests/test_dashboard.py` — thêm (mới).

## Quyết định

- Đếm VM bằng `compute.googleapis.com/instance_group/size` (tài nguyên `instance_group`, nhãn `instance_group_name`), không đếm theo tiền tố tên. Đã xác nhận metric tồn tại qua Monitoring API (chỉ đọc).
- `group_at_max` cần cả hai điều kiện trong 15 phút: số VM bằng `max_replicas` và CPU trung bình nhóm vượt `cpu_target`. Chỉ đếm VM thì báo cả khi 2 VM nhàn rỗi, vì scale-in chậm (600 s).
- Mute 23:55–08:35 giữ nguyên theo quyết định người dùng. Kênh luôn bật chỉ dùng cho alert "job mute lỗi", không đưa vào lịch mute.
- Không đổi `infra/monitoring` (stack cũ).

## Kiểm tra

- `python3 infra/terraform/environments/staging-ha/tests/test_*.py` (từng file): alerts 12 OK, dashboard 8 OK, egress 6 OK, health_checks 5 OK, pgbouncer 9 OK, resilience 23 OK (test_ha_telemetry: xem entry PR 2).
- `terraform -chdir=infra/terraform/environments/staging-ha fmt -check -recursive`: sạch.
- `terraform -chdir=infra/terraform/environments/staging-ha init -backend=false` rồi `validate`: "Success! The configuration is valid."
- Kiểm trên GCP (chỉ đọc): `instance_group/size` có series với `instance_group_name="vota-ha-app"` (giá trị 1); job `vota-ha-alert-mute-off` chạy thành công 2026-10-12 lúc 01:35 UTC (08:35 giờ VN), log `AttemptFinished` với `jobName` và `url` đúng.
- Chưa kiểm: `group_at_max` bắn thật; filter `mute_job_failed` khớp log lỗi thật (chưa có lượt lỗi để so); dashboard hiển thị đúng trên GCP.

## Còn lại / rủi ro

- Apply cần `staging-ha.tfvars` thật (secret `STAGING_HA_TFVARS`) và người duyệt plan. Apply tay từ nhánh PR trước khi merge: allowlist của `scripts/deploy-staging-ha-app.sh:50-56` không cho phép tạo alert, dashboard hay log metric; CD sẽ dừng nếu gặp.
- `values(google_monitoring_notification_channel.email)[0]` trong `alert_mute.tf` lỗi khi `alert_emails` rỗng (lỗi có sẵn, chưa sửa).
- Mute vẫn che cảnh báo crawler (01:45–04:00) và Patroni mất leader. Người dùng đã chọn giữ.
- Ngưỡng p95 800 ms chưa khớp NFR-PERF-01 (250 ms). Chưa đổi.
