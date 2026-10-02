# Dashboard monitoring theo từng VM và từng container

- Ngày: 2026-10-02
- Tác giả: người dùng / Claude
- Nhánh: feat/monitoring-dashboard-per-vm
- Trạng thái: hoàn thành
- Phạm vi: docs (infra/monitoring)

## Mục tiêu

Dashboard cũ (`gridLayout` 2 cột) gộp số liệu, không thấy từng VM/service, không có CPU/RAM theo container, chart line cho cả dữ liệu đếm, không có ngưỡng, thiếu DB replica. Làm lại để đọc nhanh tình trạng từng VM và từng container.

## File thay đổi

- `infra/monitoring/dashboard.tf` — thêm: dashboard `mosaicLayout` 12 cột, chia khối Overview/API/VM/Containers/Events/Logs (resource `staging_overview`).
- `infra/monitoring/container_metrics.tf` — thêm: metric descriptor custom cho CPU/RAM container và alert collector im lặng.
- `infra/monitoring/vota-container-stats-collector.py`, `.service` — thêm: collector `docker stats` ghi custom metric qua Monitoring API.
- `infra/monitoring/main.tf` — sửa: xoá dashboard `staging` cũ; alert App VM CPU từ 90% lên 95% (190% của 1 vCPU, VM 2 vCPU).
- `infra/monitoring/variables.tf`, `container_metrics.tf`, `dashboard.tf` — sửa: biến `container_cpu_alert_percent` (190), alert `container CPU high`, vạch ngưỡng trên chart CPU container.
- `infra/monitoring/tests/test_container_stats.py` — thêm: test parse và payload.
- `infra/monitoring/tests/test_staging_layout.sh`, `outputs.tf`, `install-vota-docker-event-watcher.sh`, `README.md`, `.github/workflows/monitoring-agent-cd-staging.yml` — sửa: trỏ sang dashboard mới, cài và deploy collector mới.

## Quyết định

- CPU/RAM theo container dùng custom metric GAUGE (số chính xác), không dùng distribution log-based (sai số ±5%).
- Metric descriptor khai báo trong Terraform để dashboard/alert không bị 404 trước khi collector ghi lần đầu.
- Collector mới chỉ cài trên App VM; container trên DB VM chưa có.

## Kiểm tra

- `bash infra/monitoring/tests/test_staging_layout.sh`: PASS (15 unit test OK).
- `terraform init -backend=false && validate && fmt -check` trên bản sao: PASS. Chưa plan/apply (không có quyền đọc state).

## Còn lại / rủi ro

- Apply sẽ huỷ dashboard cũ và tạo dashboard mới (URL dashboard đổi).
- Ngưỡng CPU theo VM 2 vCPU: 190% mỗi container = 95% VM; DB VM vẫn 90%.
- Chưa xem trên GCP thật: các trường `timeSeriesTable`, `thresholds`, filter `starts_with("/dev/")` cần kiểm khi apply.
