# Xoá 7 alert policy `vota-staging` của staging cũ

- Ngày: 2026-10-14
- Tác giả: Khoa15 (yêu cầu) / Claude Code (agent)
- Nhánh: khoa/canh-bao-tai-nguyen-db-crawler (PR #211)
- Trạng thái: hoàn thành (đã xoá trên GCP `vinpearl-508801`)
- Phạm vi: infra (monitoring, GCP thủ công), docs
- Liên quan: `2026-10-14-xoa-alert-crawler-partial-cu.md` (xoá policy đầu tiên cùng ngày), `2026-10-13-xoa-monitoring-staging-cu.md`

## Mục tiêu

Người dùng yêu cầu xoá 7 alert policy `vota-staging` còn lại. Đã cảnh báo trước: xoá sẽ mất cảnh báo cấp container cho staging-ha, vì chưa có policy `vota-ha` thay thế.

## Đã xoá trên GCP

| Policy | Log-metric đang dùng |
|---|---|
| vota-staging: container bị hết bộ nhớ (OOM) | `vota-staging_container_oom` |
| vota-staging: container dịch vụ bị dừng | `vota-staging_container_stop_by_name` |
| vota-staging: log lỗi trên VM | `vota-staging_error_logs` |
| vota-staging: mất tín hiệu watcher sự kiện Docker | `vota-staging_docker_watcher_heartbeat` |
| vota-staging: đĩa container gần đầy | `vota-staging_container_disk_bytes` |
| vota-staging: job cào thất bại | `vota-staging_crawler_failure` |
| vota-staging: lượng log tăng đột biến | `logging/billing/bytes_ingested` (toàn project) |

Bản sao JSON của 7 policy nằm trong scratchpad của phiên, không nằm trong repo.

Kết quả: HTTP 200 cho cả 7. Sau xoá còn 21 policy, toàn bộ là `vota-ha`.

## Giữ lại, có chủ ý

- 6 log-metric `vota-staging_*` và kênh `vota-staging: email cảnh báo`: không còn policy nào dùng. Có thể xoá tiếp nếu được yêu cầu.
- State Terraform `monitoring/staging` và `infra/staging` trên GCS: chưa xoá.

## Hệ quả

- staging-ha không còn cảnh báo: container OOM, container dừng, log lỗi, mất tín hiệu watcher, đĩa container, job cào thất bại, log tăng đột biến.
- Việc còn lại: thay bằng policy `vota-ha`, ví dụ log-based metric trên `docker_events`/`docker_json` đặt trong Terraform `staging-ha`.

## Kiểm tra

- Sao lưu JSON trước khi xoá (7 file), kiểm tra danh sách policy sau khi xoá.
- `infra/monitoring/README.md`: cập nhật mô tả tài nguyên còn lại (không còn policy nào dùng log-metric và kênh cũ).
