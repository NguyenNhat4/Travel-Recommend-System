# Agent giám sát trên VM

Thư mục này chỉ còn các file chạy **trên VM**. `infra/terraform/environments/staging-ha/main.tf` đọc chúng bằng `file()` và đưa vào metadata của template app. `startup.sh.tftpl` tải về rồi cài khi VM khởi động. `scripts/deploy-staging-ha-crawler.sh` chép riêng `ops-agent-crawler.yaml` lên VM crawler. Dashboard, alert và log-based metric của staging-ha nằm trong Terraform root `infra/terraform/environments/staging-ha`.

Terraform giám sát của staging cũ (state `monitoring/staging`) đã gỡ khỏi repo ngày 2026-10-13 (`docs/prd/update-archive/2026-10-13-ngung-ci-cd-staging-cu.md`). Tài nguyên GCP của nó vẫn còn. **Không destroy state `monitoring/staging` hay `infra/staging`.** Hai state này còn giữ những tài nguyên staging-ha đang dùng nhưng không quản lý:

- Alert và log-metric áp cho toàn project (không gắn VM cũ): `vota-staging_container_stop_by_name`, `_container_oom`, `_container_disk_bytes`, `_crawler_failure`, `_crawler_warning`, `_error_logs`, `_docker_watcher_heartbeat`, cùng các alert policy tương ứng và `log ingestion spike`. Cảnh báo crawler của staging-ha (`crawler_monitoring.tf`) chỉ bổ sung cho `crawler failure`, không thay thế nó.
- Metric descriptor `custom.googleapis.com/vota/container/{cpu_percent,memory_bytes,memory_percent}`, mà dashboard staging-ha vẽ.
- Retention của bucket log `_Default` và exclusion `vota-staging-debug-and-health-ok`.
- IP tĩnh `34.142.132.251` (`google_compute_address.app_public` trong state `infra/staging`), mà bastion staging-ha đang dùng.

Muốn đổi các tài nguyên trên thì import chúng vào root staging-ha trước (task riêng). Lấy Terraform cũ từ một commit trước 2026-10-13 nếu cần tra cứu.

## File

- `ops-agent-staging.yaml`: cấu hình Ops Agent của VM app, đọc log container (docker json-file) và các file JSONL bên dưới.
- `ops-agent-crawler.yaml`: cấu hình Ops Agent của VM crawler, đọc log các lượt cào.
- `vota-docker-event-watcher.py|.service`: ghi event vòng đời container vào `/var/log/vota/docker-events.jsonl`.
- `vota-container-disk-collector.py|.service`: lấy mẫu dung lượng đĩa theo container mỗi 5 phút, ghi vào `/var/log/vota/container-disk.jsonl`.
- `vota-container-stats-collector.py|.service`: chạy `docker stats` mỗi 60 giây và ghi metric `custom.googleapis.com/vota/container/*`.
- `vota-monitoring-logrotate.conf`: xoay log hằng ngày.
- `install-vota-docker-event-watcher.sh`: cài các systemd unit và logrotate ở trên rồi bật ba service.

Sửa một file ở đây chỉ có hiệu lực cho VM được tạo từ template mới, vì Terraform đọc file khi plan. Áp dụng qua `staging-ha-infra-cd.yml`.

## Kiểm tra cục bộ

```bash
python3 -m pytest -q infra/monitoring/tests
python3 infra/terraform/environments/staging-ha/tests/test_ha_telemetry.py
```

Trên một VM đang chạy:

```bash
sudo systemctl is-active vota-docker-event-watcher.service vota-container-disk-collector.service vota-container-stats-collector.service
sudo tail -n 20 /var/log/vota/docker-events.jsonl
```
