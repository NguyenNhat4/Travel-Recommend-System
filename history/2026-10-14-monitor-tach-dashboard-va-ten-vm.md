# Tách dashboard HA thành sáu trang, đổi sang tên VM, thêm dashboard cảnh báo

- Ngày: 2026-10-14
- Tác giả: Khoa15 (yêu cầu) / Claude Code (agent)
- Nhánh: khoa/monitor-tach-dashboard-ten-vm (PR riêng vào release-mvp-v2)
- Trạng thái: dang dở (code và test xong, plan đã kiểm; chưa apply; xem mục "Còn lại")
- Phạm vi: infra (staging-ha), scripts (allowlist CD), docs (guide vận hành)
- Liên quan: `2026-10-14-canh-bao-tai-nguyen-db-va-crawler.md` (PR #211, đã merge), `2026-10-14-p95-lb-them-tong-request.md` (commit `261bbe36`, `c073262b` trên nhánh này)

## Mục tiêu

Ba yêu cầu cùng lúc:

1. Dashboard HA có 21 ô, bốn khung log và bốn biểu đồ phân vị, tải cùng lúc, nên chậm. Tách thành nhiều trang theo chủ đề.
2. Dashboard hiển thị mã instance (ô RAM, đĩa, container) thay vì tên VM. Mã đổi mỗi lần MIG thay VM (`2ztd`, `v00s` → `1ztg`). Đổi sang tên VM.
3. Chưa có dashboard tổng hợp cảnh báo. Thêm một trang cho các alert policy.

## Đã kiểm trước khi đổi

- `metadata.system_labels.name` là tên VM và nhóm được cho metric Ops Agent (RAM, đĩa), metric container (CPU, RAM theo container) và metric độ trễ log-based. Đã kiểm qua `timeSeries.list` với `groupByFields`. Không cần sửa VM hay template.
- Metric CPU của Compute Engine vẫn dùng nhãn `instance_name`.

## File thay đổi

- `infra/terraform/environments/staging-ha/dashboard.tf`: viết lại thành năm dashboard:
  - `ha` (giữ địa chỉ cũ, tên đổi thành `tổng quan nhóm app`): sẵn sàng LB, số VM, request theo mã, CPU từng VM app.
  - `ha_latency` (`độ trễ API`): p95/p99 theo VM, p95 theo route, LB p95/p99. Biểu đồ phân vị chỉ nằm ở đây.
  - `ha_vm_app` (`tài nguyên VM app`): RAM, đĩa, CPU và RAM container theo tên VM; RAM theo trạng thái ở cuối (nhiều đường nhất).
  - `ha_db_crawler` (`DB và máy cào`): CPU, RAM, đĩa của pg-a, pg-b, pg-w và máy cào. pg-w chỉ có CPU.
  - `ha_logs` (`nhật ký`): bốn khung log. Chỉ trang này có khung log.
- `infra/terraform/environments/staging-ha/alerts_dashboard.tf` (mới): `ha_alerts` (`cảnh báo`). Mỗi ô là một widget `alertChart` trỏ tới một policy; policy có `count` dùng `try()` nên ô tự bỏ khi policy không tồn tại. Ghi khung mute 23:55–08:35 và việc `vota-staging:` chưa có trong Terraform.
- `infra/terraform/environments/staging-ha/monitoring.tf`: `group_memory_high` và `group_disk_high` nhóm theo `metadata.system_labels.name` (và thiết bị), để incident nêu đúng VM. Đổi chữ tài liệu trỏ tới dashboard mới.
- `infra/terraform/environments/staging-ha/patroni_monitoring.tf`: `db_memory_high`, `db_disk_high` nhóm theo tên VM; `db_cpu_high` nhóm theo `metric.label.instance_name`.
- `infra/terraform/environments/staging-ha/crawler_monitoring.tf`: `crawler_memory_high`, `crawler_disk_high`, `crawler_cpu_sustained` nhóm theo tên VM.
- `infra/terraform/environments/staging-ha/tests/test_dashboard.py`: viết lại theo sáu trang (20 test).
- `infra/terraform/environments/staging-ha/tests/test_alerts.py`: đổi assert nhóm DB sang tên VM; thêm test cho app và máy cào.
- `scripts/deploy-staging-ha-app.sh`: allowlist: năm dashboard `|create`, tám policy `|update`.
- `docs/guide/van-hanh-db-patroni.md`: §8 đổi "mã instance" thành tên VM, trỏ tới dashboard mới.

## Quyết định

- **Không đổi VM hay template.** Tên VM đến từ metadata của Ops Agent, không cần nhãn mới. Đổi template sẽ làm MIG thay VM.
- **Giữ địa chỉ `google_monitoring_dashboard.ha`** cho trang tổng quan để tránh xoá và tạo lại. URL output `ha_dashboard_url` vẫn trỏ tới đó.
- **Alert per-VM theo tên**: thêm `group_by` vào policy đã có, không tạo policy mới. Thresholds và điều kiện giữ nguyên.
- **Alignment 300 giây cho ô theo VM** để giảm số điểm; ô LB và scorecard giữ 60 giây.

## Plan (chỉ đọc, `-target` gồm 6 dashboard và 8 policy)

- `Plan: 5 to add, 11 to change, 0 to destroy`.
- 5 dashboard tạo mới; `ha` đổi tên và nội dung; 8 policy đổi `group_by` (và chữ tài liệu).
- Hai thay đổi ngoài dự kiến, đều do phụ thuộc của `ha_alerts`:
  - `group_at_max`: chỉ đổi chữ mô tả (có chủ đích, trỏ tới dashboard mới).
  - `lb_latency`: **GCP đã có điều kiện "tổng request LB > 100 trong 10 phút" (AND)**, nhưng `release-mvp-v2` chưa có. Điều kiện này nằm ở `261bbe36` và `c073262b` trên nhánh này, đã apply lên GCP lúc 11:47 (giờ Việt Nam). Nhánh này phải mang theo hai commit đó; nếu không, apply sẽ gỡ điều kiện đó.

## Kiểm tra

- Test staging-ha: `test_dashboard.py` 20 OK; `test_alerts.py` OK; `test_slot_deploy.py` 2 lỗi `mapfile` có sẵn trên nhánh gốc (bash 3.2 của macOS), không liên quan.
- `terraform fmt -check -recursive`: sạch (sau `fmt -recursive` định dạng lại `dashboard.tf`).
- `terraform validate`: "The configuration is valid."
- `bash -n scripts/deploy-staging-ha-app.sh`: OK.

## Còn lại

- Chưa apply tại thời điểm viết; sẽ cập nhật mục này sau khi apply và kiểm lại trên API.
- Dashboard cảnh báo chưa có 8 cảnh báo `vota-staging:` (staging cũ, chưa đưa vào Terraform). Xem `infra/monitoring/README.md`.
- Cảnh báo `vota-staging: lượt cào hoàn thành một phần` lọc `exit_code=3`, nhưng lượt partial hiện ghi `exit_code=0`. Rule chết; chưa sửa.
- Hai state Terraform cũ (`monitoring/staging`, `infra/staging`) vẫn còn trên GCS; chưa xử lý.
- Chưa kiểm được thời gian tải của từng dashboard trên trình duyệt (không có phiên đăng nhập Google trong công cụ).
