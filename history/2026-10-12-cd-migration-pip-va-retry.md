# Sửa CD staging-HA: bước migration không dùng venv, scheduler mute khai báo retry_config

- Ngày: 2026-10-12
- Tác giả: Khoa15 / Claude (agent), sửa theo CI check fail "Apply, verify and roll back backend on staging-ha" của PR #157 (run 38214273801, `0baf0f72`)
- Nhánh: release-mvp-v2
- Trạng thái: hoàn thành
- Phạm vi: infra

## Mục tiêu

Run `38214273801` fail ở hai chỗ:

1. Bước `Apply pending DB migrations` (mới thêm ở `0baf0f72`) lỗi `ensurepip is not available`: runner Debian không có `python3-venv`, nên `python3 -m venv` không chạy được.
2. Rollback: guard `Plan có thay đổi ngoài phạm vi cho phép` báo `google_cloud_scheduler_job.alert_mute_off|update`. Local plan cho thấy `alert_mute_on` và `alert_mute_off` đều có diff `retry_config`: state (giá trị mặc định GCP) có `retry_count = 3`, `min_backoff_duration = 30s`, `max_backoff_duration = 300s`, `max_doublings = 5`, `max_retry_duration = 0s`, còn config không khai báo nên Terraform muốn xóa.

## File thay đổi

- `.github/workflows/staging-ha-backend-cd.yml` — sửa: cài `psycopg` bằng `pip install --target "$RUNNER_TEMP/migrate-deps"` và đặt `PYTHONPATH`, thay cho venv; gọi `python3 db/migrations/run.py` trực tiếp.
- `infra/terraform/environments/staging-ha/alert_mute.tf` — sửa: thêm block `retry_config` với giá trị đang có trên job vào cả `google_cloud_scheduler_job.alert_mute_on` và `alert_mute_off`.

## Quyết định

- Không nới guard: không thêm `alert_mute_off` vào danh sách cho phép. Khai báo đúng giá trị đang có để plan khớp state.
- `pip install --target` tránh PEP 668 (pip hệ thống bị chặn) và không cần `python3-venv`.

## Kiểm tra

- Trên máy local: `python3 -m pip install --target ... 'psycopg[binary]>=3.2,<4'` rồi `PYTHONPATH=... python3 -c "import psycopg"` thành công.
- `terraform validate` đạt; plan local không còn thay đổi `google_cloud_scheduler_job.*`. Các thay đổi còn lại trong plan local là `google_compute_firewall.patroni_clients[0]|update` (đã có chủ đích), thay đổi app template/MIG (đã cho phép), và các thay đổi monitoring do tfvars local khác secret CI (không có trong guard của CI).

## Còn lại / rủi ro

- Chưa xác minh được lần CI kế tiếp. Nếu guard còn báo thay đổi khác, cần xem log plan trên CI.
- `retry_config` khai báo cứng; nếu sau này đổi mặc định trong provider thì cần cập nhật lại.
