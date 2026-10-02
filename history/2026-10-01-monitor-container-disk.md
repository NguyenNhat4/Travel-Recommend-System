# Monitor dung lượng đĩa theo từng container

- Ngày: 2026-10-01
- Tác giả: người dùng / Claude
- Nhánh: khoa/monitor-container-disk
- Trạng thái: hoàn thành source và kiểm tra cục bộ; chưa apply Terraform và chưa cài collector lên VM (CD tự cài khi PR merge vào release-mvp-v2)
- Phạm vi: monitoring

## Mục tiêu

Dashboard hiện chỉ có disk % của cả VM; không biết container nào chiếm đĩa. Bổ sung đo disk theo container, có biểu đồ và cảnh báo. Thuộc lớp vận hành, phục vụ NFR-REL-01; không lệch PRD.

## File thay đổi

- `infra/monitoring/vota-container-disk-collector.py` — thêm: mỗi 5 phút ghi một dòng JSON/container (writable layer, json-log + rotation, named volume, tổng) vào `/var/log/vota/container-disk.jsonl`.
- `infra/monitoring/vota-container-disk-collector.service` — thêm: unit systemd (Nice=10, IO idle).
- `infra/monitoring/tests/test_container_disk.py` — thêm: 7 unit test cho collector.
- `infra/monitoring/ops-agent-staging.yaml` — sửa: receiver/processor/pipeline đọc file container-disk.
- `infra/monitoring/vota-monitoring-logrotate.conf` — sửa: xoay log container-disk.
- `infra/monitoring/install-vota-docker-event-watcher.sh` — sửa: cài và bật collector.
- `infra/monitoring/main.tf` — sửa: log-based metric distribution `container_disk_bytes`, alert policy `container disk usage high`, 2 widget dashboard (biểu đồ + logs panel số liệu chính xác).
- `infra/monitoring/variables.tf` — sửa: biến `container_disk_alert_gib` (mặc định 5).
- `infra/monitoring/outputs.tf` — sửa: thêm alert id.
- `infra/monitoring/tests/test_staging_layout.sh` — sửa: assertion cho các thành phần mới.
- `infra/monitoring/README.md` — sửa: mô tả và giới hạn.
- `.github/workflows/monitoring-agent-cd-staging.yml` — sửa: trigger path, validate, copy/cài collector, kiểm tra service.

## Quyết định

- Log-based metric thay vì Prometheus receiver của Ops Agent: cùng mẫu với watcher đang chạy, không phụ thuộc loại monitored resource chưa kiểm chứng được.
- Đo bằng Docker (inspect --size) và quét thư mục bằng Python (`st_blocks`), không dùng `du -b` (cờ GNU, trả 0 trên macOS — lỗi bắt được khi test shim).
- Layer image dùng chung và bind mount không tính; volume dùng chung được tính ở mọi container mount nó (ghi trong README).
- Biểu đồ dùng percentile của bucket rộng 10% (sai số khoảng ±5%, container < 1 MiB hiện 0); số chính xác nằm ở logs panel.

## Kiểm tra

- TDD: test RED (thiếu collector) → GREEN.
- `bash infra/monitoring/tests/test_staging_layout.sh` — PASS (9 unittest).
- `terraform -chdir=infra/monitoring fmt -check -recursive` — PASS; `init -backend=false` + `validate` — PASS.
- Chạy `collect()` với shim `docker` giả: ra đúng writable/log/volume/total, volume dùng chung đo 1 lần. Daemon Docker thật không chạy trên máy local nên chưa thử với Docker thật.
- Parse YAML workflow và Ops Agent config — PASS. Chưa có actionlint.

## Còn lại / rủi ro

- Sau merge: xác nhận `systemctl is-active vota-container-disk-collector` và dòng `container_disk` trong Logs Explorer; chạy plan/apply Terraform monitoring để tạo metric, alert, widget.
- Log-based metric chỉ có dữ liệu từ lúc tạo metric, không backfill.
- Cổng 5 GiB là mặc định; chỉnh theo kích thước volume Weaviate/Postgres thực tế.
