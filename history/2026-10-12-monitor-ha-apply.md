# Monitor HA: apply PR 1–3 lên staging-ha, test VM, rollout template, deploy crawler

- Ngày: 2026-10-12
- Tác giả: Khoa15 (yêu cầu apply) / Claude Code (agent)
- Nhánh: Khoa15/adjust-monitor-staging-ha
- Trạng thái: dang dở (đã apply phần của monitor; chưa commit; chưa xử lý heartbeat crawler; chưa đồng bộ các thay đổi drift ngoài phạm vi)
- Bị thay thế bởi: 2026-10-12-monitor-ha-crawler-heartbeat.md (phần heartbeat crawler và `crawler_alerts_enabled`)
- Phạm vi: infra (staging-ha, monitoring agent), scripts (deploy crawler), GCP staging (`vinpearl-508801`)
- Liên quan: `2026-10-12-monitor-ha-canh-bao-va-dashboard.md` (PR 1), `2026-10-12-monitor-ha-log-va-nhan-nhom.md` (PR 2), `2026-10-12-monitor-ha-log-crawler.md` (PR 3), `docs/plan/2026-10-12-monitor-staging-ha.md`

## Mục tiêu

Apply các thay đổi monitor đã viết; kiểm bằng VM thử trước khi đổi template app; deploy crawler để cài Ops Agent với cấu hình riêng. Không xử lý các thay đổi drift không thuộc monitor (xem "Còn lại").

## Cách apply

- State: `gs://vinpearl-508801-staging-tfstate/infra/staging-ha/default.tfstate`. Tfvars thật nằm trong GitHub secret, không có trong repo, nên dựng lại từ state (file `ha-reproduce.tfvars` ở scratchpad, ngoài repo): `db_primary_ip = 10.148.0.34` (từ DNS `db.vota.internal`), `create_patroni = true`, `create_weaviate = false`, `create_bastion = true`, `origin_tls_enabled = true`, `crawler_monitor_public = true`, `create_crawler_vm = true`, `crawler_alerts_enabled = false`, `alert_emails` = một email từ kênh hiện có, digest app và crawler lấy từ `deploy/staging-ha-last-good*.json`.
- Terraform 1.15.8 (khớp `TF_VERSION` của CD).
- Plan đầy đủ: 7 add, 10 change, 5 destroy. Chỉ 9 mục là của PR này (xem bên dưới); các mục còn lại là drift không liên quan và **không được apply**. Dùng `-target` để chỉ apply phần của monitor, rồi plan/apply lại từng nhóm.

## Đã apply

Nhóm 1 (PR 1, không đụng VM): `alert_mute_on`, `alert_mute_off` (retry), `ha_alert_mute_job_failed` (log metric), `email_always` (kênh), `mute_job_failed` (alert), `group_at_max` (AND hai điều kiện), `group_below_min` (đếm bằng `instance_group/size`). Plan: 4 add, 4 change, 0 destroy.

Nhóm 2: `google_monitoring_dashboard.ha`. Lần apply đầu lỗi: API từ chối `color` trong `thresholds` của xyChart. Đã bỏ `color` khỏi xyChart (giữ ở scorecard), thêm test `test_xychart_thresholds_have_no_color`. Apply lại thành công.

Nhóm 3 (PR 2, đổi template): `google_compute_instance_template.app` (tạo mới, xóa cũ) và `google_compute_region_instance_group_manager.app` (version). Plan: 1 add, 1 change, 1 destroy. MIG thay `vota-ha-app-3gtn` bằng `vota-ha-app-5vx9`, ổn định lúc 05:33 UTC, LB HEALTHY. Đây là gián đoạn đã chốt (max_surge 0, một VM). Chưa đo chính xác thời gian gián đoạn vì không lấy mẫu LB liên tục.

Crawler: `scripts/deploy-staging-ha-crawler.sh` với digest `vota-fresh-catalog@sha256:e687a460...` (last-good). Kết quả: `ops-agent-ok`, cron cài lại, monitor khởi động lại.

## Các thay đổi drift KHÔNG được apply (cần quyết định)

Plan đầy đủ có các thay đổi không thuộc PR này, nằm sẵn trong code nhưng chưa từng apply vào state:

- `google_compute_instance.patroni["a"|"b"|"w"]`: `machine_type` `e2-custom-1-1024` → `e2-standard-2`. Đổi loại máy buộc phải stop/start VM DB đang chạy: **DB downtime**.
- `google_compute_instance.bastion[0]`: bỏ public IP (`access_config`), bỏ schedule; `bastion_ssh` (0.0.0.0/0) bị xóa, `bastion_iap_ssh` được tạo. Đổi quyền truy cập.
- `google_compute_resource_policy.patroni_schedule` bị xóa, `patroni_replica_schedule` được tạo.
- `google_dns_record_set.db_replica[0]` (`db-replica.vota.internal` → 10.148.0.4) bị xóa.
- `google_cloud_scheduler_job.app_autoscaler_on`: 08:30 → 08:20 (theo default trong code).

Hệ quả: `scripts/deploy-staging-ha-app.sh` (allowlist) sẽ dừng với "Plan có thay đổi ngoài phạm vi" ở lần CD kế tiếp, cho đến khi các mục trên được xử lý. Không tự quyết các mục này.

## Kiểm test VM trước rollout (`vota-ops-test-ha`, đã xóa)

Tạo từ đúng `startup-script` và metadata `vota-mon-*` của template mới, nhãn như template, không có tag `vota-ha-app`, không vào LB:

- Ops Agent nạp cấu hình mới (`Merged config` có `docker_json`, `container_disk`, `docker_events`, `fresh_catalog_logs`); `hostmetrics` còn.
- Log backend lên Cloud Logging, `jsonPayload.service="backend"`, log `docker_json`, có `readiness.recovered` và `search.prewarm.done`.
- Metric `agent.googleapis.com/memory/percent_used` (5 state) và `compute.googleapis.com/instance/cpu/utilization` có series.
- Metric container `custom.googleapis.com/vota/container/cpu_percent` có `vota-backend`, `vota-frontend`, `vota-pgbouncer`.
- Watcher, disk collector, stats collector đều `active (running)`.
- Phát hiện: container helper `docker:27-cli` (`docker compose up -d`, thoát ngay) bị phân loại là `service` và `staging_container_stop` sẽ báo mỗi lần boot. Đã sửa `container_class` trong `infra/monitoring/vota-docker-event-watcher.py` (image `docker:` → `helper`); xác nhận trên VM app mới: `die ... helper`.
- Nhãn `group` của VM **không** hiện trong `metadata` của series qua Monitoring API (`userLabels` rỗng). Không dựa vào nhãn này cho filter. Alert và dashboard dùng `instance_group/size` và tên VM.

## Kiểm sau rollout

- MIG: một VM `vota-ha-app-5vx9`, `isStable=True`, `versionTarget.isReached=True`.
- Autoscaler: `ACTIVE`, mode `ON`, `statusDetails` rỗng.
- LB: HEALTHY.
- Log backend từ VM mới: có (`docker_json`).
- Metric container và memory từ VM mới: có.

## Crawler (PR 3)

- Sau deploy, `jsonPayload.service="crawler"` có trong `fresh_catalog_logs`: `catalog.due`, `run.end`, `alert.*`, `step.end`, `catalog.substep`, v.v.
- `parse_json` không làm rớt dòng text: `fresh-catalog.start` và `fresh-catalog.exit` vẫn có trong `textPayload`.
- **Tác động phụ đã xác nhận:** Ops Agent đọc lại toàn bộ file `fresh-catalog-*.log` cũ khi khởi động lần đầu. Các event lịch sử (ví dụ `run.end` của lượt 09/10, 11/10) được nạp với timestamp Cloud Logging là 05:27:29 UTC. Không phải lượt đang chạy bị dừng. Chi phí ingest một lần chưa được đo.

## Phát hiện: heartbeat `catalog.freshness` gần như không bao giờ được ghi

- `run_fresh_catalog_container.sh` (entrypoint, dòng 11–13): với `tick`, chạy `due` trước; nếu không có lượt đến hạn thì `exit 0` **ngay**, không chạy `fresh_catalog.py tick`.
- `emit_freshness` chỉ được gọi từ `check_sla` trong nhánh `tick` của Python (`fresh_catalog.py:1049–1050`). Nhánh này gần như không chạy khi máy rảnh.
- Kết quả đo: tick 05:30 có `catalog.due -: hôm nay đã chạy lượt theo lịch`, rồi thoát, không có `catalog.freshness`. Trong 3 giờ qua không có `catalog.freshness` nào.
- Hệ quả: nếu bật `crawler_alerts_enabled`, cảnh báo "JOB CÀO KHÔNG CHẠY" (vắng 60 phút) sẽ báo liên tục. **Vì vậy đã giữ `crawler_alerts_enabled = false`.**
- Hướng sửa (chưa làm, cần đổi code crawler và build image qua CI): khi `due` rỗng, gọi `fresh_catalog.py tick` (nhánh rảnh có `check_sla` và không cần DB) thay vì `exit 0`; hoặc phát `catalog.freshness` ngay trong entrypoint. Sau đó chạy crawler CD và kiểm `catalog.freshness` xuất hiện mỗi 15 phút.
- Thêm: trong lúc một lượt chạy (nhiều giờ), không có heartbeat nào; cảnh báo vắng 60 phút cũng sẽ báo sai trong lúc cào. Cần heartbeat trong lúc chạy.

## Quyết định mục 3 (phạm vi alert project-wide của stack cũ)

- Giữ nguyên định nghĩa `infra/monitoring` (không sửa stack cũ).
- Hệ quả đã chấp nhận: `staging_container_stop`, `staging_container_oom`, `staging_error_logs` giờ đếm cả VM HA và gửi qua kênh `vota-staging`. Lý do: đây là độ phủ mong muốn cho HA; kênh này cùng người vận hành.
- Cần xem lại: `infra/monitoring` còn nhắm `vota-backend-crawler-recsys` và `v-ota-db-dev`, cả hai đang TERMINATED. Các alert vắng mặt (ví dụ `staging_db_uptime`) có thể đang gửi email; chưa kiểm được lịch sử incident.

## Kiểm local

- `python3 infra/terraform/environments/staging-ha/tests/test_*.py`: alerts 12, dashboard 9, ha_telemetry 11, egress 6, health_checks 5, pgbouncer 9, resilience 23 — tất cả OK.
- `bash infra/monitoring/tests/test_staging_layout.sh`: PASS.
- `terraform fmt -check`: sạch. `terraform validate`: "The configuration is valid."

## Còn lại

- Quyết định về bốn mục drift (Patroni machine type, bastion, DNS db-replica, lịch autoscaler). Cho đến khi xử lý, CD staging-ha bị chặn.
- Sửa heartbeat crawler (entrypoint + CI build), rồi mới bật `crawler_alerts_enabled`.
- C3 (alert RAM vắng mặt theo nhóm) chưa làm.
- Commit: chưa commit. Các file mới và đã sửa nằm trong working tree.
