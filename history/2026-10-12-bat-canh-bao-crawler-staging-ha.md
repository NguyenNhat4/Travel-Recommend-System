# Bật cảnh báo crawler staging-HA (crawler_alerts_enabled = true)

- Ngày: 2026-10-12
- Tác giả: Khoa15 / Claude (agent), theo lựa chọn của người vận hành (giữ cảnh báo crawler), sửa theo CI check fail "Apply, verify and roll back backend on staging-ha" (run 38216076601, `7e60273c`)
- Nhánh: release-mvp-v2
- Trạng thái: hoàn thành (còn theo dõi, xem "Còn lại")
- Phạm vi: infra

## Mục tiêu

Run `38216076601` fail vì guard báo `google_logging_metric.crawler_freshness_heartbeat[0]|delete`: metric và policy cảnh báo crawler đã có trong state, nhưng config mặc định `crawler_alerts_enabled = false` nên plan đề xuất xóa. Người vận hành chọn giữ cảnh báo.

## File thay đổi

- `infra/terraform/environments/staging-ha/variables.tf` — sửa: `crawler_alerts_enabled` mặc định `true` (secret `STAGING_HA_TFVARS` của CI có thể ghi đè; không đọc được để kiểm tra).
- `scripts/deploy-staging-ha-app.sh` — sửa: thêm vào danh sách thay đổi được phép các thay đổi do bật cảnh báo: `google_logging_metric.crawler_freshness_heartbeat[0]|update`, `google_logging_metric.crawler_catalog_late[0]|create`, `google_monitoring_alert_policy.crawler_catalog_late[0]|create`, `google_monitoring_alert_policy.crawler_run_failed[0]|update`, `google_monitoring_alert_policy.crawler_silent[0]|update`.

## Kiểm tra

- Log Cloud Logging không có event `catalog.freshness` trong 2 ngày gần đây. Đã cảnh báo người vận hành trước khi chọn hướng này: nếu crawler chưa phát event, các cảnh báo "catalog không đổi" và "job không chạy" sẽ báo nhiễu.
- Plan local với mặc định mới: metric `crawler_freshness_heartbeat` chuyển sang `update` (không còn `delete`); `crawler_catalog_late` và các policy `crawler_*` được tạo/cập nhật đúng như danh sách cho phép.

## Còn lại / rủi ro

- Nếu `STAGING_HA_TFVARS` đặt `crawler_alerts_enabled = false` tường minh thì giá trị mặc định mới không có tác dụng và CI vẫn sẽ chặn. Cần kiểm tra secret.
- Cảnh báo có thể báo nhiễu cho đến khi crawler phát `catalog.freshness`.
- Plan local còn các thay đổi monitoring khác (dashboard `ha`, channel `email_always`, metric `ha_api_latency`…) do tfvars local khác secret CI; CI trước đó không báo các thay đổi này nên không đưa vào danh sách cho phép.
