# Monitor tiết kiệm: loại metric theo tiến trình (agent processes/*) khỏi Ops Agent của HA

- Ngày: 2026-10-12
- Tác giả: Khoa15 (yêu cầu "loại ngay", sau đó "tìm giải pháp tiết kiệm hơn") / Claude Code (agent)
- Nhánh: Khoa15/adjust-monitor-staging-ha
- Trạng thái: dang dở (đã áp dụng cho app HA và crawler; chưa áp dụng cho `vota-ci-runner`, `pg-a`, `pg-b`; chưa commit)
- Bị thay thế bởi: 2026-10-12-monitor-cat-processes-3-vm.md (phần ci-runner, pg-a, pg-b)
- Phạm vi: infra (monitoring agent, staging-ha), scripts (deploy crawler), GCP staging
- Liên quan: `2026-10-12-monitor-ha-apply.md`, `2026-10-12-monitor-ha-crawler-heartbeat.md`

## Mục tiêu

Chi phí Cloud Monitoring đang ~$213/tháng (ước tính). Phần lớn là metric `agent.googleapis.com/processes/*` (~83% dung lượng agent được tính phí). Autoscaler và dashboard không dùng metric này.

## Thay đổi

- `infra/monitoring/ops-agent-staging.yaml` (app HA): thêm `metrics.processors.metrics_filter` (`type: exclude_metrics`, `agent.googleapis.com/processes/*`), `default_pipeline` tham chiếu processor. `hostmetrics` và `memory/percent_used` giữ nguyên.
- `infra/monitoring/ops-agent-crawler.yaml` (crawler): cùng thay đổi.
- Cú pháp đối chiếu với tài liệu Ops Agent: [Disable collection of process metrics](https://docs.cloud.google.com/monitoring/settings/disable) (Ops Agent >= 2.0.0; processor áp dụng cho `default_pipeline`).
- `infra/terraform/environments/staging-ha/tests/test_ha_telemetry.py`: thêm `test_process_metrics_are_excluded_but_host_metrics_stay`.

## Apply

- Crawler: `scripts/deploy-staging-ha-crawler.sh` với digest last-good. Kết quả `ops-agent-ok`; agent báo PASS. `processes/cpu_time` dừng ở 07:18:29 UTC, `memory`/`cpu` vẫn đều.
- App HA: `terraform plan -target=google_compute_instance_template.app -target=google_compute_region_instance_group_manager.app` → 1 add, 1 change, 1 destroy (template thay thế, MIG đổi version). Apply 07:21 UTC. MIG thay `vota-ha-app-5vx9` bằng `vota-ha-app-q7tm`; ổn định 07:30 UTC; LB HEALTHY.
- Gián đoạn: MIG không có VM nào trong khoảng 07:25:01–07:25:27 UTC; VM mới khởi động đến khoảng 07:29 UTC. Thời gian LB không phục vụ chưa đo liên tục.

## Kiểm

- VM app mới: `processes/cpu_time` 0 series; `memory/percent_used` 5 series và `disk/percent_used` 6 series, điểm mới nhất 07:29:47 UTC; log backend (`search.prewarm.done`, `readiness.recovered`) lên đều.
- Test staging-ha: alerts 15, dashboard 12, ha_telemetry 12, egress 6, health_checks 5, pgbouncer 9, resilience 23 — tất cả OK.
- YAML của cả hai file parse được; `metrics_filter` nằm đúng trong `default_pipeline`.

## Số liệu billing (MTD 1–12/10/2026, từ `monitoring.googleapis.com/billing/bytes_ingested`)

- Tổng agent: 386.7 MiB. Riêng `processes/*`: ~322 MiB (cpu_time 107.6; disk read/write 53.8 mỗi cái; vm_usage 53.8; rss_usage 53.8).
- Phân bố số series `processes/cpu_time` (1h): `vota-ci-runner` 1152; `vota-ha-pg-a` 426; `vota-ha-app-5vx9` 402; `vota-ha-pg-b` 318; `vota-ha-crawler` 296. VM HA đã tắt: app và crawler. **Còn lại: ci-runner, pg-a, pg-b (~73% số series processes).**
- Metric agent được dashboard/alert dùng: `memory/percent_used`, `disk/percent_used`. Metric khác (`cpu/usage_time`, `network/tcp_connections`, `disk/operation_*`, `interface/*`, `swap/io`, `cpu/load_*`) không được repo dùng.
- Ước tính sau khi loại processes trên HA: chi phí vẫn ~$130–160/tháng vì ci-runner và pg-a, pg-b còn gửi processes. Ước tính theo tỷ lệ số series, chưa đo theo byte từng VM.

## Phương án đã so sánh

- Cloud Monitoring (giữ hiện tại): free 150 MiB; $0.258/MiB sau đó ([Cloud Monitoring pricing](https://cloud.google.com/monitoring/pricing)). Đủ rẻ nếu chỉ giữ metric cần thiết.
- Managed Service for Prometheus: $0.06/triệu sample ([Managed Prometheus](https://cloud.google.com/managed-prometheus)). Vẫn cần Ops Agent cho memory (autoscaler) nên không tiết kiệm thêm; thêm vận hành.
- Prometheus + Grafana tự host trên e2-small: ~$12–36/tháng VM tùy bảng giá ([gcloud-compute e2-small](https://gcloud-compute.com/e2-small.html)), cộng đĩa và vận hành; vẫn cần Ops Agent cho autoscaler. Đắt hơn phương án hiện tại sau khi cắt metric.
- Logs: 1.39 GiB MTD, dưới 50 GiB free ([Cloud Logging pricing](https://cloud.google.com/products/observability/pricing)) → $0.

## Còn lại / rủi ro

- Chưa làm: `vota-ci-runner`, `pg-a`, `pg-b`. Ops Agent của các máy này không nằm trong config của repo (runner ngoài Terraform; Patroni ghi config từ `patroni-node.sh.tftpl` lúc boot). Cần quyết định vì phải SSH vào máy; `gcloud compute ssh` có thể ghi SSH key vào metadata. Chỉ cần restart Ops Agent, không restart DB.
- Đề xuất bước tiếp: bỏ thêm metric không dùng (lean profile) để xuống dưới 150 MiB free. Cần rollout template app thêm một lần.
- Kiểm lại billing sau 24 giờ: `processes/*` phải về 0 trên các VM đã áp dụng, và MTD bytes ngày mới thấp hơn rõ.
- Chưa commit.
