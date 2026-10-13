# Chuyển tên và mô tả của monitor và cảnh báo sang tiếng Việt

- Ngày: 2026-10-13
- Tác giả: Khoa15 (yêu cầu) / Claude Code (agent)
- Nhánh: Khoa15/xoa-monitoring-staging-cu
- Trạng thái: hoàn thành (code và kiểm tra local xong; apply qua `staging-ha-infra-cd.yml` sau merge)
- Phạm vi: infra (staging-ha monitoring), src (monitor job cào), docs

## Mục tiêu

Yêu cầu của người dùng: ngôn ngữ trong monitor và alert đều là tiếng Việt. Chỉ đổi chữ hiển thị (tên alert, tiêu đề dashboard, mô tả, nội dung hướng dẫn, nhãn UI). Không đổi filter, ngưỡng, metric, tên resource, tên trường JSON hay identifier kỹ thuật (`min_replicas`, `cpu_target`, `status=failed`, `catalog.due`, `leader`/`replica` khi cần giữ nghĩa).

## File thay đổi

- `infra/terraform/environments/staging-ha/monitoring.tf` — sửa: display_name của các alert nhóm HA, uptime check, alert CI runner.
- `infra/terraform/environments/staging-ha/crawler_monitoring.tf` — sửa: alert job cào (tiền tố `Crawler:` → `Job cào:`), điều kiện `catalog late` → `catalog quá hạn`.
- `infra/terraform/environments/staging-ha/patroni_monitoring.tf` — sửa: alert và mô tả log-metric Patroni (leader → node chính (leader), replica streaming → replica đang đồng bộ).
- `infra/terraform/environments/staging-ha/alert_mute.tf` — sửa: alert và điều kiện job bật/tắt kênh cảnh báo.
- `infra/terraform/environments/staging-ha/dashboard.tf` — sửa: tiêu đề các ô (readiness, ERROR, die/OOM, lượt cào, p95/p99, RAM instance).
- `scripts/deploy-staging-ha-app.sh` — sửa: thêm 11 địa chỉ `|update` vào `allowed_changes` (xem Quyết định).
- `src/data_collection/monitor_ui/index.html` — sửa: nhãn `Log runner` → `Log chạy`, `Model · text builder` → `Model · bộ tạo text`, `Search unit` → `Đơn vị tìm kiếm`.
- `history/2026-10-13-monitor-canh-bao-tieng-viet.md` — thêm: entry này.

Không đổi, có chủ ý:

- Tên IAM custom role (`VOTA HA ops scheduler`) là chữ của IAM, không phải monitor hay alert.
- Các thuật ngữ kỹ thuật được giữ: VM, MIG, LB, SSE, HA, p95, p99, 5xx, RAM, CPU, Redis, Patroni, Postgres, Ops Agent.

Ngoài repo (GCP, không do Terraform quản lý), đổi displayName bằng `PATCH` có `updateMask=displayName`, kiểm tên cũ trước khi đổi:

- 8 alert policy `vota-staging ...` đang giữ sau đợt xoá: container OOM, container dịch vụ bị dừng, đĩa container gần đầy, mất tín hiệu watcher Docker, log lỗi trên VM, job cào thất bại, lượt cào hoàn thành một phần, lượng log tăng đột biến.
- Kênh email `vota-staging email alerts` → `vota-staging: email cảnh báo`.

## Quyết định

- **Đổi display_name là `update` tại chỗ trên resource đã có trong state.** Cổng `allowed_changes` chặn update không có trong danh sách, nên thêm 11 địa chỉ `|update` (alert, uptime check, log-metric Patroni) vào allowlist với chú thích. Không nới cổng: các địa chỉ này chỉ đổi text, filter và ngưỡng giữ nguyên.
- **`crawler_catalog_late`, `group_memory_high`, `group_disk_high`, `ci_runner_down` là `create`** (chưa có trên GCP), đã có trong allowlist; text mới được áp khi tạo.
- **Mô phỏng cổng**: đối chiếu danh sách 18 block đã đổi (so với `HEAD`) với allowlist, tất cả đều được cho qua.
- **Monitor UI nằm trong `src/data_collection/**`**: merge sẽ kích hoạt Crawler CD và redeploy monitor cào trên VM crawler (container monitor được thay; lượt cào đang chạy giữ nguyên, theo `deploy-staging-ha-crawler.sh`).

## Kiểm tra

- `terraform fmt -check -recursive` và `terraform validate` (staging-ha): pass.
- Test staging-ha: `test_alerts`, `test_dashboard`, `test_ha_telemetry`, `test_health_checks`, `test_resilience`, `test_egress_and_secrets`, `test_pgbouncer_setup`: pass.
- `test_slot_deploy.py`: fail trên máy local vì `mapfile` không có trong bash 3.2 của macOS (đã biết, CI chạy bash 5 trên Linux).
- `infra/monitoring/tests`: pass (18 test).
- `src/data_collection/tests/test_monitor_public.py` và `test_fresh_monitor.py`: 28 pass. 1 test fail do `run_daily_docker.sh` dùng `date -I` (BSD date của macOS không hỗ trợ), không liên quan thay đổi; CI chạy Linux.
- Chưa chạy `terraform plan` với state thật (cần `STAGING_HA_TFVARS`).

## Còn lại / rủi ro

- Sau merge, `Staging-HA Infra CD` đổi tên 11 resource trên GCP. Đổi tên không làm thay đổi filter hay ngưỡng, nhưng cần kiểm lại sau apply rằng các alert vẫn gửi đúng kênh.
- Monitor job cào được redeploy vì `src/data_collection` đổi.
- Chưa dịch hết các chuỗi trong code backend, log và tài liệu `docs/` (ngoài phạm vi monitor và alert).
