# Monitor HA: heartbeat crawler mỗi tick, bật cảnh báo job cào, sửa freshness trong nhánh due

- Ngày: 2026-10-12
- Tác giả: Khoa15 (yêu cầu tiếp tục chỉnh) / Claude Code (agent)
- Nhánh: Khoa15/adjust-monitor-staging-ha
- Trạng thái: dang dở (đã apply cảnh báo job cào; sửa code crawler chưa build/deploy image; chưa commit)
- Phạm vi: infra (staging-ha), src (data_collection: fresh_catalog.py), GCP staging
- Thay thế: phần heartbeat và `crawler_alerts_enabled = false` trong `2026-10-12-monitor-ha-apply.md`
- Liên quan: `2026-10-12-monitor-ha-log-crawler.md` (PR 3), `docs/plan/2026-10-12-monitor-staging-ha.md`

## Mục tiêu

Cảnh báo "job cào không chạy" và "lượt cào thất bại" chưa hoạt động (đang tắt). Cảnh báo "catalog quá hạn" không bao giờ bắn. Sửa để các cảnh báo này dùng được trên log thật.

## Nguyên nhân (đã kiểm)

- `catalog.freshness` chỉ được phát trong nhánh tick rảnh của `fresh_catalog.py`. Entrypoint `run_fresh_catalog_container.sh` (dòng 11–13) chạy `due` trước và thoát ngay khi không có lượt, nên nhánh tick gần như không chạy. Kết quả: không có `catalog.freshness` nào trong nhiều giờ dù cron chạy đều.
- `catalog.due` thì khác: entrypoint luôn gọi `due` ở mỗi tick, kể cả khi đang có lượt chạy (reason `đang có lượt chạy`). Đã kiểm trên log theo `jsonPayload.ts_utc`: đều 15 phút, có khoảng trống đúng với lịch tắt VM.

## File thay đổi

- `src/data_collection/fresh_catalog.py` — sửa: nhánh `due` gọi `emit_freshness` trong `log.use_stream(sys.stderr)` (stdout của `due` là tên chế độ, không được có log). Phát `catalog.freshness` ở mỗi tick, kể cả khi đang có lượt.
- `src/data_collection/tests/test_fresh_catalog_job.py` — thêm: `test_due_mode_emits_catalog_freshness_every_tick_even_while_a_run_is_busy` (kiểm lock bận và rảnh, stdout trống, đúng một `catalog.freshness`).
- `infra/terraform/environments/staging-ha/crawler_monitoring.tf` — sửa: heartbeat lọc `catalog.due`; metric và policy "catalog quá hạn" gated bằng `local.crawler_late_alerts`; filter của ba policy có `resource.type="gce_instance"` (Cloud Monitoring từ chối filter thiếu; gặp khi apply); text cảnh báo vắng mặt đổi sang `catalog.due`.
- `infra/terraform/environments/staging-ha/variables.tf` — sửa: `crawler_alerts_enabled` mặc định `true`; thêm `crawler_late_alert_enabled` mặc định `false`.
- `infra/terraform/environments/staging-ha/tests/test_alerts.py` — thêm 3 test: heartbeat dùng `catalog.due`; cảnh báo late bị gate; policy crawler có `resource.type`.

## Apply

- Lần 1: 4 add (2 metric, 2 policy). Hai metric được tạo; hai policy lỗi "must specify a restriction on resource.type". Đã thêm `resource.type` vào filter.
- Lần 2: 2 add (2 policy). Thành công.
- Cảnh báo late không được tạo (gate = false).
- Tfvars tái dựng trong scratchpad: bỏ dòng `crawler_alerts_enabled = false`, vì mặc định giờ là true. Tfvars thật trong secret `STAGING_HA_TFVARS` không có biến này, nên cũng nhận mặc định true.

## Kiểm

- `pytest tests/test_fresh_catalog_job.py tests/test_alerts.py` (môi trường scratch, cài requirements như CI): 62 passed.
- `python3 infra/terraform/environments/staging-ha/tests/test_*.py`: alerts 15, dashboard 12, ha_telemetry 11, egress 6, health_checks 5, pgbouncer 9, resilience 23 — tất cả OK.
- `terraform fmt -check`: sạch. `terraform validate`: "The configuration is valid."
- Trên GCP (chỉ đọc): hai policy `vota-ha Crawler: JOB CÀO KHÔNG CHẠY` và `vota-ha Crawler: LƯỢT CÀO THẤT BẠI` đang bật; metric `vota-ha_crawler_freshness_heartbeat` và `vota-ha_crawler_run_failed` đã có; `catalog.due` đều 15 phút tới 07:00 UTC.
- Chưa kiểm: alert bắn thật và email tới người nhận.

## Còn lại / rủi ro

- **Bản crawler đang chạy chưa có sửa freshness.** Cảnh báo "catalog quá hạn" vẫn tắt (`crawler_late_alert_enabled = false`). Để bật: commit sửa, chạy crawler CD (`staging-ha-crawler-cd.yml`) để build và deploy image, kiểm `catalog.freshness` xuất hiện mỗi 15 phút trên log, rồi đặt `crawler_late_alert_enabled = true` và apply. Commit và CD là quyết định của người vận hành.
- Email: hai cảnh báo đang bật gửi email nếu cron ngừng giữa ngày (ngoài khung mute 23:55–08:35). Khung mute che các khoảng VM tắt theo lịch (23:59–01:45, 04:00–08:30) và lượt cào 01:45–04:00.
- Khoảng trống trong lúc cảnh báo được tạo: metric heartbeat chỉ đếm từ lúc tạo. Đã có điểm dữ liệu trước khi thấy cảnh báo.
- Chưa commit.
