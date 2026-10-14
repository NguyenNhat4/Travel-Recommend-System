# Dựng lại cảnh báo container, log và job cào cho staging-ha (tiếng Việt, có mô tả lỗi)

- Ngày: 2026-10-14
- Tác giả: Khoa15 (yêu cầu) / Claude Code (agent)
- Nhánh: khoa/canh-bao-tai-nguyen-db-crawler (PR #211)
- Trạng thái: hoàn thành (đã apply lên GCP `vinpearl-508801`)
- Phạm vi: infra (staging-ha, monitoring), scripts (allowlist CD), docs
- Liên quan: `2026-10-14-xoa-7-alert-vota-staging.md` (xoá 7 policy cũ, lý do và hệ quả), `2026-10-14-xoa-alert-crawler-partial-cu.md`

## Mục tiêu

Sau khi xoá 7 policy `vota-staging`, staging-ha không còn cảnh báo container, log và job cào. Dựng lại bằng Terraform, tên và mô tả tiếng Việt, mỗi mô tả nêu rõ lỗi, nguyên nhân cần kiểm tra và cách xử lý. Email nêu đúng tên VM.

## Cái gì được dựng lại

| Cảnh báo (tên hiển thị) | Log-metric | Điều kiện |
|---|---|---|
| vota-ha Container: hết bộ nhớ (OOM) | `vota-ha_container_oom` | Có OOM-kill trong 1 phút |
| vota-ha Container: dịch vụ bị dừng bất thường | `vota-ha_container_dung` | Có container dịch vụ dừng trong 1 phút |
| vota-ha Container: đĩa gần đầy (trên 5 GiB) | `vota-ha_container_disk` | p99 dung lượng một container > 5 GiB trong 10 phút |
| vota-ha Docker: mất tín hiệu trình theo dõi sự kiện | `vota-ha_docker_watcher` | Không có nhịp trong 5 phút (vắng mặt) |
| vota-ha Log: lỗi mức ERROR trên VM | `vota-ha_error_logs` | Có log ERROR trong 5 phút |
| vota-ha Job cào: container cào thất bại | `vota-ha_crawler_container_fail` | Container cào thoát mã khác 0 hoặc OOM trong 1 phút |
| vota-ha Log: lượng log tăng đột biến (toàn project) | billing `bytes_ingested` | > 0,25 GiB trong 1 giờ |

Ngưỡng nằm trong `variables.tf`: `alert_container_disk_bytes` (5 GiB), `alert_log_spike_bytes_per_hour` (0,25 GiB).

## Khác với cảnh báo cũ

- **Nhãn VM**: log-metric lấy nhãn `vm` từ `compute.googleapis.com/resource_name`. Mỗi incident nêu tên VM thay vì mã instance.
- **Mô tả**: mỗi policy có ba mục: Lỗi, Kiểm tra, Xử lý. Cảnh báo "mất tín hiệu watcher" ghi rõ các cảnh báo OOM, container dừng sẽ không hoạt động khi watcher dừng.
- **Kênh**: dùng kênh HA chung (`local.alert_channels`), **nên chịu lịch mute 23:55–08:35**. Cũ là kênh `vota-staging` không bị mute. Đây là thay đổi hành vi, theo quyết định ngày 2026-10-12 (mute cho mọi alert HA). Cần xác nhận lại nếu muốn cảnh báo OOM và container dừng hoạt động ban đêm.
- **Ngưỡng lỗi**: giữ nguyên ngưỡng "lớn hơn 0 trong 5 phút" cho log lỗi, nên một dòng lỗi cũng kêu. Đã thấy điều này ngày 14/10 lúc 03:29 UTC (16 lỗi 503 trong 2 giây). Chưa đổi.

## Đã apply

- `terraform plan -target` (13 địa chỉ): **13 to add, 0 to change, 0 to destroy**.
- `terraform apply`: 12 tạo xong ở lần chạy đầu. Policy `container_dung` lỗi 404 vì metric mới chưa sẵn sàng (GCP cần đến 10 phút). Chạy lại sau khoảng 4 phút: **1 added**.
- Đọc lại từ API: 28 policy (21 `vota-ha` cũ + 7 mới); 6 log-metric mới có nhãn `vm` đúng.

## Giữ lại, có chủ ý

- 6 log-metric `vota-staging_*` và kênh `vota-staging: email cảnh báo`: không còn policy nào dùng. Chưa xoá; đợi xác nhận.
- State Terraform `monitoring/staging` và `infra/staging`: chưa xoá.

## Kiểm tra

- `python3 tests/test_alerts.py`: 36 test OK (gồm 8 test mới: tên tiếng Việt, mục Lỗi/Kiểm tra/Xử lý, kênh chung, nhãn VM, mô tả watcher, ngưỡng log tăng, allowlist).
- `python3 tests/test_dashboard.py`: OK; các test khác OK, trừ `test_slot_deploy.py` (lỗi `mapfile` có sẵn).
- `terraform fmt -check -recursive`: sạch. `terraform validate`: "The configuration is valid."
- `scripts/deploy-staging-ha-app.sh`: thêm 13 địa chỉ `|create` vào allowlist.

## Còn lại

- Log-metric mới chưa có dữ liệu lịch sử. Cảnh báo sẽ chỉ có số liệu từ lúc dựng, nên cần chờ một sự kiện thật để kiểm chứng.
- Quyết định ngưỡng log lỗi (hiện là lớn hơn 0 trong 5 phút).
- Quyết định mute ban đêm cho cảnh báo container.
- Xoá 6 log-metric `vota-staging_*`, kênh cũ và hai state Terraform cũ khi được xác nhận.
