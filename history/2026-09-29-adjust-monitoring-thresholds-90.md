# Điều chỉnh threshold monitoring App VM và DB VM lên 90%

- Ngày: 2026-09-29
- Trạng thái: hoàn tất trên staging
- Phạm vi: alert policies tài nguyên của App VM và DB VM; không thay đổi uptime/readiness/error-log thresholds

## Thay đổi

- App VM: CPU, memory và disk đều alert khi vượt `90%` liên tục `5 phút`.
- DB VM: CPU, memory và disk đều alert khi vượt `90%` liên tục `5 phút`.
- DB VM unavailable: vẫn alert khi metric uptime bị mất trong `5 phút`.
- Public readiness: vẫn alert sau `3 phút` lỗi.
- Error logs: vẫn alert khi error-log rate lớn hơn `0` trong `5 phút`.

## Kết quả apply

- Terraform: `0 added, 6 changed, 0 destroyed`.
- Terraform drift check sau apply: `No changes`.
- Cloud Monitoring API xác nhận sáu policy tài nguyên có threshold `0.9` hoặc `90` và duration `300s`.
