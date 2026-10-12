# Gộp monitor staging-ha lên nhánh mới nhất của release-mvp-v2 và mở PR

- Ngày: 2026-10-12
- Tác giả: Khoa15 (yêu cầu "ok, tạo PR vào release-mvp-v2") / Claude Code (agent, Haiku 5.5)
- Nhánh: Khoa15/adjust-monitor-staging-ha
- Trạng thái: dang dở (PR đã mở vào release-mvp-v2, chưa merge; chờ người duyệt)
- Phạm vi: infra (staging-ha, monitoring), scripts (deploy crawler), src/data_collection (freshness của crawler)
- Liên quan: các entry `2026-10-12-monitor-*` (đã liệt kê dưới đây)

## Mục tiêu

Đưa toàn bộ thay đổi monitor staging-ha vào một commit trên nhánh đã rebase lên `origin/release-mvp-v2` (222f90c7), rồi mở PR vào `release-mvp-v2`. Không merge: merge sẽ kích hoạt CD staging-ha, xem mục "Còn lại / rủi ro".

## File thay đổi

Đã sửa (tracked):

- `infra/monitoring/ops-agent-staging.yaml` — thêm `metrics_filter` loại `agent.googleapis.com/processes/*`.
- `infra/monitoring/vota-docker-event-watcher.py` — container helper (`docker:`) không tính là service dừng.
- `infra/terraform/environments/staging-ha/alert_mute.tf` — retry_config cho job mute; kênh email luôn bật, metric và policy "job mute lỗi". Bỏ `patroni_replica_schedule` (upstream đã bỏ).
- `infra/terraform/environments/staging-ha/crawler_monitoring.tf` — heartbeat theo `catalog.due`; cảnh báo late tách ra cổng `crawler_late_alert_enabled`.
- `infra/terraform/environments/staging-ha/main.tf` — nhãn nhóm trên template app; metadata monitor và startup script.
- `infra/terraform/environments/staging-ha/monitoring.tf` — `group_at_max` kết hợp số VM và CPU; `group_below_min` đếm theo nhóm.
- `infra/terraform/environments/staging-ha/outputs.tf` — output `ha_dashboard_url`.
- `infra/terraform/environments/staging-ha/patroni_ops_agent.yaml` — `metrics_filter` loại processes (chưa apply cho Patroni, xem rủi ro).
- `infra/terraform/environments/staging-ha/startup.sh.tftpl` — cài file monitor và Ops Agent có sao lưu/khôi phục cấu hình.
- `infra/terraform/environments/staging-ha/tests/test_alerts.py` — cập nhật theo các cảnh báo mới.
- `infra/terraform/environments/staging-ha/variables.tf` — `crawler_alerts_enabled` mặc định true (upstream đã đặt); thêm `crawler_late_alert_enabled` mặc định false. Giữ `db_client_tags` của upstream.
- `scripts/deploy-staging-ha-crawler.sh` — bước cài cấu hình Ops Agent cho VM crawler.
- `src/data_collection/fresh_catalog.py` — lượt `due` ghi `catalog.freshness` ở mỗi tick, kể cả khi đang có lượt chạy.
- `src/data_collection/tests/test_fresh_catalog_job.py` — thêm test `due` ghi freshness ở mỗi tick (giữ test của upstream).
- `src/data_collection/tests/test_log.py` — assertion `catalog.due` tìm bản ghi theo `event` thay vì dòng cuối, vì `due` nay ghi thêm `catalog.freshness` sau `catalog.due`.

Mới (untracked):

- `docs/plan/2026-10-12-monitor-staging-ha.md` — plan.
- `infra/monitoring/ops-agent-crawler.yaml` — cấu hình Ops Agent cho VM crawler.
- `infra/terraform/environments/staging-ha/dashboard.tf` — dashboard HA và metric latency.
- `infra/terraform/environments/staging-ha/tests/test_dashboard.py`, `tests/test_ha_telemetry.py` — test mới.
- `history/2026-10-12-monitor-cat-processes-3-vm.md`, `…-monitor-ha-apply.md`, `…-monitor-ha-canh-bao-va-dashboard.md`, `…-monitor-ha-crawler-heartbeat.md`, `…-monitor-ha-do-tre-va-log.md`, `…-monitor-ha-log-crawler.md`, `…-monitor-ha-log-va-nhan-nhom.md`, `…-monitor-tiet-kiem-processes.md` — lịch sử các bước trước.
- `history/2026-10-12-monitor-tao-pr-release-mvp-v2.md` — entry này.

## Quyết định

- **Gộp với upstream.** Upstream (222f90c7 và các commit trước) đã đổi cùng `alert_mute.tf`, `variables.tf` và `test_fresh_catalog_job.py`. Cách gộp:
  - `alert_mute.tf`: giữ khối `retry_config` đúng giá trị mặc định của provider (bản upstream) và comment giải thích của nhánh này; mỗi job chỉ còn một khối. Bỏ `patroni_replica_schedule` theo upstream; giữ metric/kênh/policy job mute lỗi.
  - `variables.tf`: git gộp nhầm `crawler_late_alert_enabled` thành `default = true`. Đã sửa về `false`, vì bản crawler đang chạy chưa phát `catalog.freshness` đều mỗi tick. `crawler_alerts_enabled` giữ `true`.
  - `test_fresh_catalog_job.py`: gộp tự động, giữ cả hai bên.
- **Không đổi `scripts/deploy-staging-ha-app.sh`.** Allowlist upstream vẫn đúng: mục `crawler_catalog_late[0]` không được tạo khi cổng tắt.
- **Không merge.** Merge kích hoạt các CD trên nhánh đích; người duyệt quyết định thời điểm.

## Kiểm tra

- Test staging-ha (`infra/terraform/environments/staging-ha/tests/test_*.py`): 7 file, đều OK.
- `terraform fmt -check -recursive`: không có file lệch.
- `terraform init -backend=false -lockfile=readonly` rồi `validate`: "The configuration is valid."
- `src/data_collection` (`pytest tests`, venv thử nghiệm, `PYTHONPATH=..:.`): 644 passed, 27 skipped, 5 failed trước khi sửa test:
  - `test_log.py::test_due_stdout_is_only_the_mode_name_and_log_goes_to_stderr`: do thay đổi này; đã sửa test. Sau sửa, `test_log.py` và `test_fresh_catalog_job.py`: 67 passed.
  - 4 test còn lại (`test_fresh_monitor.py::…mounts_same_volume…`, `test_runner_fresh_monitor.py` ×2, `test_timeouts_recrawl.py::…deadline_stops…`) lỗi do môi trường macOS (`stat -c` của GNU; timeout 60 s). Đã chạy đúng 4 test này trên `origin/release-mvp-v2` trong worktree tạm: cũng lỗi, nên không phải do thay đổi.
- Quét dòng thêm (1402 dòng) trước commit: không có email, khóa riêng tư, token.
- Chưa chạy: `terraform plan` trên cây đã gộp (cần tfvars thật và state GCS). Thay đổi upstream về bastion, Patroni, scheduler vẫn gây drift đã ghi ở entry apply.

## Còn lại / rủi ro

- **Khi merge sẽ chạy CD:**
  - `staging-ha-backend-cd` (đổi `infra/terraform/environments/staging-ha/**`): guard có thể dừng vì drift upstream (bastion, Patroni, scheduler, DNS).
  - `staging-ha-crawler-cd` (đổi `src/data_collection/**`): build image crawler và deploy VM crawler; sửa freshness chỉ có tác dụng sau bước này.
  - `monitoring-agent-cd-staging` (đổi `infra/monitoring/**` và watcher): deploy watcher và Ops Agent.
- **Patroni chưa apply:** `patroni_ops_agent.yaml` đổi nhưng chưa apply; Terraform Patroni còn drift `machine_type`.
- **ci-runner:** cấu hình Ops Agent đang chạy không nằm trong repo (xem entry cat-processes-3-vm).
- **Replica pg-b:** lag ~963 MB, `no_replica` từ 02:00 UTC; chờ quyết định xử lý DB.
- **Cảnh báo late crawler:** tắt cho tới khi bản crawler có sửa freshness được deploy.
- **Billing:** chưa đo lại sau 24 giờ (≈ 2026-10-13).
- Commit tạm `wip: monitor staging-ha` đã được gộp vào commit cuối và không đẩy lên remote.
