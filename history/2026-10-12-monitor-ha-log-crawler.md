# Monitor HA (PR 3): log crawler lên Cloud Logging, sửa parse JSON của cấu hình crawler

- Ngày: 2026-10-12
- Tác giả: Khoa15 (yêu cầu) / Claude Code (agent)
- Nhánh: Khoa15/adjust-monitor-staging-ha
- Trạng thái: dang dở (code và test local xong; chưa chạy deploy crawler, chưa kiểm log trên Cloud Logging)
- Phạm vi: scripts (deploy crawler), infra (monitoring agent)
- Liên quan: `2026-10-12-monitor-ha-log-va-nhan-nhom.md` (PR 2), `docs/plan/2026-10-12-monitor-staging-ha.md`

## Mục tiêu

Ba cảnh báo crawler (`crawler_monitoring.tf`: job không chạy, lượt thất bại, catalog quá hạn) đọc `jsonPayload.service="crawler"`. Kiểm 2026-10-12: không có entry `service="crawler"` nào trong 1 ngày, và VM `vota-ha-crawler` không có `syslog`. VM crawler không cài Ops Agent. Entry này cài Ops Agent với cấu hình riêng cho crawler.

## Phát hiện trong cấu hình có sẵn

- `infra/monitoring/ops-agent-staging.yaml`: receiver `fresh_catalog_logs` tail `/srv/vota/fresh-catalog-logs/*.log` nhưng pipeline `fresh_catalog_pipeline` không có processor. Dòng JSON của `log.emit` (`src/data_collection/log.py`) sẽ không thành `jsonPayload.service`. File này **không sửa** trong entry này (VM cũ đã TERMINATED; app VM HA không đọc thư mục này).
- `ops-agent-staging.yaml` có `docker_json` cho mọi container. Dùng cho crawler sẽ đưa stdout của container lên hai lần (file lượt cào và docker json-file).
- Pattern `*.log` cũng bắt `monitor-cd.log` (log của monitor).

## File thay đổi

- `infra/monitoring/ops-agent-crawler.yaml` — thêm (mới): receiver `fresh_catalog_logs` tail `/srv/vota/fresh-catalog-logs/fresh-catalog-2*.log`; processor `parse_json` trên `message`; hostmetrics giữ nguyên.
- `scripts/deploy-staging-ha-crawler.sh` — sửa: bước 1b copy `ops-agent-crawler.yaml` vào thư mục tạm; bước 2d cài Ops Agent nếu thiếu, ghi cấu hình crawler, khôi phục cấu hình trước nếu restart lỗi. Lỗi bước 2d chỉ cảnh báo, không chặn cài cron và monitor.
- `infra/terraform/environments/staging-ha/tests/test_ha_telemetry.py` — sửa: thêm 2 test (cấu hình crawler không có `docker_json` trong phần code, chỉ đọc `fresh-catalog-2*.log`, có `parse_json`; script deploy có gọi cấu hình này).

## Quyết định

- Cấu hình crawler riêng, không dùng chung `ops-agent-staging.yaml`. Lý do: tránh đếm đôi stdout container và không kéo `monitor-cd.log` vào.
- Pattern `fresh-catalog-2*.log` khớp với tên file lượt cào (`fresh-catalog-YYYYmmdd-HHMMSS.log`, xem `run_daily_docker.sh`). Không khớp `fresh-catalog-errors.log` và `monitor-cd.log`.
- Bước 2d không đổi metadata VM trong Terraform (allowlist CD chỉ cho tạo VM crawler). Cài bằng SSH như các bước cũ.
- Khôi phục cấu hình trước khi restart lỗi, giống `install_monitoring` ở PR 2.

## Kiểm tra

- `bash -n scripts/deploy-staging-ha-crawler.sh`: OK.
- Dựng lại chuỗi lệnh remote `ops_cmd` với một đường dẫn giả: đúng cú pháp, biến `$conf` giữ nguyên để shell trên VM mở rộng.
- `python3 -c "import yaml; yaml.safe_load(...)"` trên `ops-agent-crawler.yaml`: OK; receiver `fresh_catalog_logs`, pipeline `fresh_catalog_pipeline`.
- `python3 infra/terraform/environments/staging-ha/tests/test_ha_telemetry.py`: 10 test OK.
- `infra/monitoring/tests/test_staging_layout.sh`: PASS (sau khi thêm file mới).
- Chưa kiểm: `parse_json` trên dòng text (`fresh-catalog.start`, `fresh-catalog.exit`) có giữ dòng hay làm rớt dòng; Ops Agent cài được trên VM crawler (cần NAT và IAP SSH); log `catalog.freshness` xuất hiện trong Cloud Logging.

## Còn lại / rủi ro

- Chạy `scripts/deploy-staging-ha-crawler.sh` (CD crawler) để cài Ops Agent. Kiểm sau deploy: `gcloud logging read 'jsonPayload.service="crawler"' --freshness=1h` có dòng; `catalog.freshness` xuất hiện ở tick 15 phút.
- Nếu `parse_json` làm rớt dòng text, sửa processor (ví dụ đặt điều kiện chỉ parse dòng bắt đầu bằng `{`).
- Sau khi cảnh báo crawler có dữ liệu thật, cần kiểm lại lịch: VM crawler tắt 23:59–01:45 và 04:00–08:30 (`crawler.tf`, `scheduler.tf`), chạy thêm 01:45–04:00. Cả ba khoảng này nằm trong khung mute 23:55–08:35, nên cảnh báo "job cào không chạy" và "lượt thất bại" không gửi email tới 08:35. Đây là quyết định mute đã chốt.
- `infra/monitoring/ops-agent-staging.yaml` còn lỗi parse như trên, chưa sửa vì không còn VM nào đọc thư mục đó.
