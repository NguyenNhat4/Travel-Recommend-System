# Agent giám sát trên VM

Thư mục này chỉ còn các file chạy **trên VM**. `infra/terraform/environments/staging-ha/main.tf` đọc chúng bằng `file()` và đưa vào metadata của template app. `startup.sh.tftpl` tải về rồi cài khi VM khởi động. `scripts/deploy-staging-ha-crawler.sh` chép riêng `ops-agent-crawler.yaml` lên VM crawler. Dashboard, alert và log-based metric của staging-ha nằm trong Terraform root `infra/terraform/environments/staging-ha`.

Terraform giám sát của staging cũ (state `monitoring/staging`) đã gỡ khỏi repo ngày 2026-10-13. Cùng ngày, các alert, log-metric, dashboard và uptime check gắn VM cũ đã xoá khỏi GCP (`docs/prd/update-archive/2026-10-13-xoa-monitoring-staging-cu.md`). **Không chạy plan hay apply** trên state `monitoring/staging` hay `infra/staging`: state đã lệch so với GCP.

Còn trên GCP, không có code quản lý, và staging-ha đang dựa vào một phần:

- Bảy alert policy toàn project (container OOM, service container stopped, container disk, Docker watcher absent, error logs, crawler failed, log ingestion spike) và log-metric `vota-staging_*` của chúng. Policy "crawler partial run" đã xoá (2026-10-14): lọc `exit_code=3`, mà bản crawler hiện tại không còn phát. Cảnh báo crawler của staging-ha (`crawler_monitoring.tf`) chỉ bổ sung cho `crawler failed`, không thay thế nó.
- Kênh email `vota-staging email alerts`, mà tám policy trên dùng.
- Metric descriptor `custom.googleapis.com/vota/container/{cpu_percent,memory_bytes,memory_percent}`, mà dashboard staging-ha vẽ. Không xoá: GCP chặn tạo lại cùng tên trong 24 giờ.
- IP tĩnh `34.142.132.251`, mà bastion staging-ha đang dùng.

Muốn đưa các tài nguyên trên về Terraform thì import vào root staging-ha (task riêng). Lấy Terraform cũ từ một commit trước 2026-10-13 nếu cần tra cứu.

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
