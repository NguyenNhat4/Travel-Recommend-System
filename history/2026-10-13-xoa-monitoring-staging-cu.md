# Xoá monitoring cũ của staging cũ: GCP, PRD và README

- Ngày: 2026-10-13
- Tác giả: Khoa15 (yêu cầu) / Claude Code (agent)
- Nhánh: Khoa15/xoa-monitoring-staging-cu
- Trạng thái: hoàn thành
- Phạm vi: infra (monitoring), docs

## Mục tiêu

Xoá monitoring cũ của staging cũ (alert, log-metric, dashboard, uptime check, exclusion log gắn VM đã nghỉ) và làm mô tả trong PRD và README khớp với GCP sau khi xoá.

Phần gỡ CI/CD và Terraform cũ đã có trên `release-mvp-v2` qua PR #192 (`history/2026-10-13-go-ci-cd-staging-cu.md`, `history/2026-10-13-cd-staging-ha-mot-luong-hai-pha.md`). Entry này không lặp lại phần đó.

## Đã xoá trên GCP (project `vinpearl-508801`)

- 18 alert policy: 15 `vota-staging*` (12 gắn instance ID của VM đã `TERMINATED`: `v-ota-db-dev`, `vota-backend-crawler-recsys`, `vota-staging-db-replica`; 2 replica; 1 `public readiness` trỏ `v-ota.duckdns.org`, mà duckdns giờ là IP bastion và fail 100%), và 3 policy `VM … utilization / networking latency` do Compute Engine tự tạo (không có trong repo; áp cho mọi VM kể cả staging-ha; người dùng chọn xoá).
- 4 log-metric: `vota-staging_db_replica_probe_heartbeat`, `_db_replica_unhealthy`, `_http_requests_5xx`, `_http_requests_total`.
- Dashboard `vota-staging infrastructure` (dùng metric đã chết).
- Uptime check `vota-staging-readiness`.
- Exclusion log `vota-staging-debug-and-health-ok` (áp cho mọi `gce_instance`; người dùng chọn xoá).

Số policy: 38 → 20. Policy `vota-ha` không đổi (12).

## Giữ lại, có chủ ý

- 8 alert policy toàn project đang bảo vệ VM staging-ha: container OOM, service container stopped, container disk usage, Docker watcher absent, error logs, crawler failed, crawler partial run, log ingestion spike. Staging-ha chưa có thay thế.
- Kênh email `vota-staging email alerts` (8 policy trên dùng).
- Log-metric `vota-staging_container_*`, `_crawler_*`, `_docker_watcher_heartbeat`, `_error_logs` (dùng bởi 8 policy trên).
- Metric descriptor `custom.googleapis.com/vota/container/*`: dashboard `vota-ha HA: nhóm app` đang vẽ. GCP chặn tạo lại cùng tên trong 24 giờ sau khi xoá.
- IP tĩnh `34.142.132.251`: bastion staging-ha đang dùng.

## Sửa trong repo

- `docs/prd/deployment-plan.md` §1.1: mô tả đúng tài nguyên còn lại (đề xuất `docs/prd/update-archive/2026-10-13-xoa-monitoring-staging-cu.md`). Bản của release vẫn ghi exclusion và alert đã xoá.
- `infra/monitoring/README.md`: bỏ exclusion và retention khỏi danh sách còn lại; ghi rõ không chạy plan hay apply trên state `monitoring/staging` và `infra/staging` (state đã lệch so với GCP).

## Kiểm tra

- Trước xoá: liệt kê policy, log-metric, dashboard, uptime check, kênh, exclusion và descriptor (chỉ đọc, REST API). Kiểm tra tham chiếu chéo: không policy `vota-ha` nào dùng kênh cũ hay log-metric cũ; dashboard `vota-ha` chỉ dùng descriptor `custom.googleapis.com/vota/container/*` và log-metric `vota-ha_api_latency_ms`.
- Sau xoá: `policies` 38 → 20, 18 xoá, 0 thêm; 12 policy `vota-ha` còn nguyên; dashboard, uptime check, exclusion đã xoá, descriptor còn nguyên. Mọi lệnh xoá trả HTTP 200.
- Bản sao JSON của tài nguyên đã xoá nằm trong thư mục scratchpad của phiên (không nằm trong repo).

## Còn lại / rủi ro

- Không còn lớp cảnh báo memory/disk cho VM app staging-ha trước khi entry `2026-10-13-canh-bao-bo-nho-va-dia-app-ha.md` được apply.
- Chưa import 8 policy, log-metric, kênh email, descriptor và IP còn lại vào Terraform staging-ha (task riêng).
- Hai state `infra/staging` và `monitoring/staging` đã lệch so với GCP: không chạy plan hay apply trên chúng.
- Ba VM cũ (`v-ota-db-dev`, `vota-backend-crawler-recsys`, `vota-staging-db-replica`) vẫn `TERMINATED`, chưa xoá.
