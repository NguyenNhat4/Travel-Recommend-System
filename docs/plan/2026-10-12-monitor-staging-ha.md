# Monitor cho nhóm autoscale staging-ha (MIG `vota-ha-app`)

- Ngày: 2026-10-12
- Phục vụ: NFR-PERF-01, NFR-PERF-02 (đo p95 và độ trễ trên cụm HA), `docs/prd/deployment-plan.md` §5 (giám sát). PRD không có mã NFR riêng cho quan sát; làm theo tiền lệ `docs/plan/2026-09-30-monitoring-slos.md`.
- Phạm vi: infra (`infra/terraform/environments/staging-ha`, `infra/monitoring`), scripts (deploy crawler)
- Trạng thái: PR 1 và PR 2, PR 3 đã viết và kiểm local; chưa apply, chưa commit. Xem "Trạng thái" cuối file.

## Bối cảnh

Hai câu hỏi vận hành chưa trả lời được trên monitor Google: log backend thuộc VM nào, và CPU của một VM thuộc nhóm autoscale nào. Khảo sát (chỉ đọc) và kiểm tra GCP (chỉ đọc) cho thấy:

- `infra/monitoring` (dashboard, SLO, CPU/RAM/disk, log metric) gắn vào `GCE_APP_INSTANCE`, theo state là `vota-backend-crawler-recsys`. Ngày 2026-10-12 VM này TERMINATED, và `v-ota-db-dev`, `vota-staging-db-replica` cũng TERMINATED. Nhóm HA chỉ có 6 alert trong `staging-ha/monitoring.tf`, không có dashboard.
- Log VM HA: chỉ có `syslog` và `google_metadata_script_runner` trong 1 ngày. Không có log `service="backend"` nào, nên log container backend không lên Cloud Logging. Cấu hình Ops Agent không có receiver `docker_json`.
- Log VM crawler `vota-ha-crawler`: không có `syslog`, không có `service="crawler"` nào trong 1 ngày. Ba cảnh báo crawler (`crawler_monitoring.tf`) không có dữ liệu.
- Log LB của backend `vota-ha-app` có `httpRequest.serverIp` trùng IP nội bộ của VM (`vota-ha-app-3gtn` = 10.148.15.215). Đây là cách biết request đi tới VM nào, không cần agent. Log LB lấy mẫu 50%.
- `compute.googleapis.com/instance_group/size` tồn tại, resource `instance_group`, nhãn `instance_group_name="vota-ha-app"`. Dùng để đếm VM của MIG, không đếm theo tiền tố tên.
- Time series memory của Ops Agent không trả metadata qua API, nên không nhóm theo tên VM được. Chỉ có `resource.labels.instance_id`.
- Lỗi logic: `group_at_max` báo khi có 2 VM trong 15 phút, không kiểm tra tải. Không có alert nào cho job bật/tắt mute khi job lỗi. Mute 23:55–08:35 cũng che cả cảnh báo crawler và Patroni.

## Quyết định đã chốt (hỏi người dùng 2026-10-12)

1. Monitor mới đặt ở Terraform root `staging-ha` (cùng state, tiền tố `vota-ha`). `infra/monitoring` giữ nguyên cho stack cũ.
2. Giữ nguyên mute 23:55–08:35 cho mọi alert. Chỉ thêm: retry cho hai job mute, và một alert "job mute lỗi" đi qua kênh email luôn bật.
3. Lệnh `gcloud` chỉ đọc chạy trong lúc thực thi; không ghi gì lên GCP.

## Thay đổi đã làm

### PR 1: alert và dashboard (Terraform, không đụng VM)

- `staging-ha/monitoring.tf`:
  - `group_at_max`: đổi thành AND của hai điều kiện trong 15 phút. Số VM của MIG (`instance_group/size`) >= `max_replicas` và CPU trung bình nhóm > `cpu_target`.
  - `group_below_min`: đếm VM bằng `instance_group/size`. Điều kiện vắng mặt cũng dùng metric này.
- `staging-ha/alert_mute.tf`:
  - `retry_config` (3 lần, backoff 30–300 s) cho hai `google_cloud_scheduler_job`.
  - `google_monitoring_notification_channel.email_always`: không có `ignore_changes = [enabled]`, không bị lịch mute tắt.
  - `google_logging_metric.ha_alert_mute_job_failed`: đếm lỗi mức ERROR của hai job.
  - `google_monitoring_alert_policy.mute_job_failed`: dùng kênh luôn bật.
- `staging-ha/dashboard.tf` (mới): `google_monitoring_dashboard.ha`, gồm readiness, số VM, request theo mã, p95 có đường 250 ms và ngưỡng alert, CPU từng VM (`instance_name`), RAM từng VM (`instance_id`), và ghi chú cách đối chiếu VM với MIG.
- `staging-ha/outputs.tf`: thêm `ha_dashboard_url`.
- Test: `tests/test_alerts.py` (sửa test `at_max` cũ đang khóa hành vi sai; thêm test cho kênh luôn bật và retry), `tests/test_dashboard.py` (mới).

### PR 2: log và container cho VM HA, nhãn nhóm (Terraform, chưa tạo VM thử)

- `staging-ha/main.tf`: nhãn `group = "vota-ha-app"`, `role = "app"` trên template. Thêm `monitoring_metadata`: 9 key `vota-mon-*` đọc file từ `infra/monitoring/` bằng `file()`.
- `staging-ha/startup.sh.tftpl`: hàm `install_monitoring`, gọi sau bước cài Ops Agent. Ghi file từ metadata; cài Ops Agent với `ops-agent-staging.yaml` (giữ `hostmetrics` cho autoscaler); nếu cấu hình mới không khởi động thì khôi phục cấu hình trước đó; cài watcher và collector bằng `install-vota-docker-event-watcher.sh` có sẵn. Lỗi giám sát không chặn khởi động app.
- `staging-ha/dashboard.tf`: thêm CPU và RAM theo từng container (`custom.googleapis.com/vota/container/*`), nhóm theo `container_name` và `instance_id`.
- Test: `tests/test_ha_telemetry.py` (mới).

### PR 3: log crawler (script deploy, không đổi Terraform)

- Phát hiện: `infra/monitoring/ops-agent-staging.yaml` có receiver `fresh_catalog_logs` nhưng pipeline không có `parse_json`. Dòng JSON của `log.emit` sẽ không thành `jsonPayload.service`, nên cảnh báo crawler không khớp. File này không được sửa trong PR này.
- `infra/monitoring/ops-agent-crawler.yaml` (mới): chỉ đọc `fresh-catalog-2*.log`, có `parse_json` trên `message`, không có `docker_json` (tránh đếm đôi stdout container và không đọc `monitor-cd.log`).
- `scripts/deploy-staging-ha-crawler.sh`: bước 1b copy file cấu hình; bước 2d cài Ops Agent nếu thiếu, cài cấu hình crawler, khôi phục nếu restart lỗi. Lỗi bước 2d chỉ cảnh báo, không chặn cài cron và monitor.

## Khác với plan đã duyệt

- C2: file giám sát đưa qua `metadata` và `file()`, không nhúng vào `startup.sh.tftpl`. Lý do: template dùng `templatefile`, các script có thể chứa `${`.
- B1/B1b: `group_below_min` cũng đổi sang `instance_group/size` (theo A6 của plan).
- C3 (alert RAM vắng mặt theo nhóm): chưa làm. Chưa kiểm được `metadata.user_labels` trên alert filter; cần VM thử trước.
- Thêm `parse_json` vào cấu hình crawler mới (PR 3). Chưa có trong plan gốc; là lỗi thật của cấu hình hiện có.

## Chưa làm (cần người duyệt hoặc cần GCP thật)

1. Apply Terraform (`staging-ha`): cần `staging-ha.tfvars` thật (secret `STAGING_HA_TFVARS`) và người duyệt plan. Phải apply tay từ nhánh PR trước khi merge, vì allowlist của `scripts/deploy-staging-ha-app.sh:50-56` không cho phép tạo alert, dashboard hay log metric.
2. Tạo VM thử `vota-ha-app-ops-test` (không gắn tag `vota-ha-app`) để kiểm Ops Agent, log có `instance_id`, series custom metric và memory metric. Chưa làm vì tạo VM là ghi lên GCP.
3. Rollout template app: đổi template làm MIG thay VM. Làm lúc MIG về 0 VM hoặc chấp nhận downtime ~230–300 s.
4. Chạy deploy crawler để cài Ops Agent. Kiểm `catalog.freshness` xuất hiện trong Cloud Logging.
5. Kiểm `parse_json` trên dòng text (`fresh-catalog.start`) có giữ dòng hay làm rớt dòng. Chưa kiểm được trên VM.
6. Kiểm trên GCP: `group_at_max` có bắn thật không, filter của `mute_job_failed` có khớp log lỗi thật của Cloud Scheduler không (chưa có lượt lỗi để so).

## Rủi ro và việc phải quyết định

- Sau khi HA có log container, các alert project-wide của `infra/monitoring` (`staging_error_logs`, `staging_container_stop`, `staging_container_oom`) sẽ đếm cả VM HA, và gửi qua kênh `vota-staging` của stack cũ. Cần quyết định: giữ, hay giới hạn theo nhãn nhóm.
- Mute 23:55–08:35 vẫn che cảnh báo crawler lỗi trong khung 01:45–04:00 và Patroni mất leader. Người dùng đã chọn giữ.
- `alert_emails` mặc định rỗng và `values(google_monitoring_notification_channel.email)[0]` trong `alert_mute.tf` sẽ lỗi khi plan nếu `alert_emails` rỗng. Đây là lỗi có sẵn, không sửa trong plan này.
- Ngưỡng p95 800 ms (`alert_p95_latency_ms`) cao hơn NFR-PERF-01 (250 ms). Chưa đổi.
- Chưa kiểm được Ops Agent đang chạy cấu hình gì trên VM HA: `gcloud compute ssh` ghi SSH key vào metadata, nằm ngoài phạm vi chỉ đọc.

## Kiểm tra

- Terraform: `fmt -check -recursive` sạch; `init -backend=false` rồi `validate`: "The configuration is valid."
- Test cấu trúc `staging-ha/tests/*.py`: alerts 12, dashboard 8, ha_telemetry 10, egress 6, health_checks 5, pgbouncer 9, resilience 23 — tất cả OK.
- `infra/monitoring/tests/test_staging_layout.sh`: PASS.
- `bash -n`: `scripts/deploy-staging-ha-crawler.sh`, `install-vota-docker-event-watcher.sh` và khối giám sát trong `startup.sh.tftpl` (đã tách ra): OK.
- `py_compile`: ba collector Python: OK.
- YAML `ops-agent-crawler.yaml`: parse được; receiver `fresh_catalog_logs`, pipeline `fresh_catalog_pipeline`.
- GCP (chỉ đọc): các kết quả nêu trong "Bối cảnh".

## Trạng thái

- Đã apply (chi tiết và các phát hiện: `history/2026-10-12-monitor-ha-apply.md`): alert và mute của PR 1, dashboard HA, template và MIG của PR 2 (VM app đã thay bằng `vota-ha-app-5vx9`, ổn định, LB HEALTHY), deploy crawler với Ops Agent riêng (PR 3). VM thử đã kiểm và xóa.
- Crawler (cập nhật, `history/2026-10-12-monitor-ha-crawler-heartbeat.md`): heartbeat chuyển sang `catalog.due` (mỗi tick kể cả khi đang chạy). Đã bật cảnh báo "job cào không chạy" và "lượt cào thất bại". Cảnh báo "catalog quá hạn" vẫn tắt, chờ bản crawler có sửa freshness trong nhánh due được build và deploy.
- Độ trễ p95/p99 và khung log trên dashboard: `history/2026-10-12-monitor-ha-do-tre-va-log.md`.
- Chưa làm: C3; alert cho độ trễ và search (cần chốt ngưỡng); các mục drift ngoài phạm vi (Patroni machine type, bastion, DNS db-replica, lịch autoscaler), cần quyết định trước khi CD staging-ha chạy lại.
- Chưa commit.
