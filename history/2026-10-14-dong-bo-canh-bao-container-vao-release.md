# Đưa cảnh báo container, log và job cào đang chạy trên GCP vào release-mvp-v2

- Ngày: 2026-10-14
- Tác giả: Khoa15 (yêu cầu) / Claude Code (agent)
- Nhánh: khoa/dong-bo-canh-bao-container
- Trạng thái: hoàn thành (plan chỉ đọc khớp; chưa merge)
- Phạm vi: infra (staging-ha), docs (infra/monitoring/README.md)
- Liên quan: `2026-10-14-canh-bao-container-va-log-ha.md`, `2026-10-14-xoa-7-alert-vota-staging.md`, `2026-10-14-xoa-alert-crawler-partial-cu.md` (các commit này đã apply lên GCP từ nhánh PR cũ, chưa vào release)

## Sự cố

Run CD `staging-ha-infra-cd` sau merge #217 chặn ở cổng plan: `google_logging_metric.container_disk|delete`. Resource này nằm trong state GCP (đã apply từ nhánh PR cũ) nhưng không có trong code `release-mvp-v2`. Cổng chặn đúng: không được xoá một metric đang có alert `vota-ha Container: đĩa gần đầy` dùng. Cùng loại lệch với `lb_latency` (#216).

## Thay đổi

Cherry-pick ba commit từ nhánh PR cũ, theo thứ tự:

- `10e17fc4` dựng lại cảnh báo container, log và job cào bằng tiếng Việt (`container_monitoring.tf`, sáu log-metric và bảy policy).
- `650dbb64` xoá bảy policy `vota-staging` của staging cũ.
- `6a7098d0` xoá cảnh báo "lượt cào hoàn thành một phần" cũ (lọc `exit_code=3`, không còn khớp).

Xung đột ở `infra/monitoring/README.md` (cả hai lần) được giải quyết bằng phiên bản của commit, vì nó mô tả đúng trạng thái GCP.

## Kiểm tra

- Plan chỉ đọc `-target` cho 14 resource của `container_monitoring.tf` (6 log-metric, 8 policy): **No changes. Your infrastructure matches the configuration.**
- `test_alerts.py`, `test_dashboard.py` và các test khác trong `staging-ha/tests` đều OK; `test_slot_deploy.py` có hai lỗi `mapfile` cũ trên nhánh gốc.
- `terraform fmt -check -recursive`: sạch; `terraform validate`: "The configuration is valid."

## Còn lại

- Sau khi merge, run CD đầu tiên cần xanh (không còn `container_disk|delete`). Cần kiểm tra run đó.
- Có thể xoá log-metric `vota-staging_*` cũ (6 cái, không còn policy nào dùng) sau khi kiểm chứng cảnh báo `vota-ha` mới. Chưa làm.
