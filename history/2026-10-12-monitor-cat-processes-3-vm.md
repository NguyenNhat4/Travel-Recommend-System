# Cắt metric tiến trình trên vota-ci-runner, pg-a, pg-b (hoàn tất phần còn lại của entry tiết kiệm)

- Ngày: 2026-10-12
- Tác giả: Khoa15 (yêu cầu "cắt cả ba") / Claude Code (agent)
- Nhánh: Khoa15/adjust-monitor-staging-ha
- Trạng thái: dang dở (đã cắt processes trên cả ba VM; chưa cập nhật cấu hình của ci-runner trong repo; chưa kiểm billing sau 24 giờ; chưa xử lý sự cố replica DB)
- Phạm vi: infra (patroni, monitoring agent), GCP staging (ci-runner ngoài Terraform, pg-a, pg-b)
- Thay thế phần chưa làm trong: `2026-10-12-monitor-tiet-kiem-processes.md`

## Thay đổi

- `infra/terraform/environments/staging-ha/patroni_ops_agent.yaml` (nguồn của `patroni-node.sh.tftpl`, dùng cho pg-a/pg-b): thêm `metrics.processors.metrics_filter` (`exclude_metrics`, `agent.googleapis.com/processes/*`) và tham chiếu trong `default_pipeline`. Đây là thay đổi trong repo; **chưa apply Terraform cho Patroni** vì còn drift `machine_type` (xem entry apply).
- `pg-a`, `pg-b` (live, IAP SSH): ghi cùng nội dung như file trên vào `/etc/google-cloud-ops-agent/config.yaml`, có sao lưu `config.yaml.bak-processes` và tự khôi phục nếu restart lỗi. Cả hai restart OK; agent `active`. Không restart VM hay DB.
- `vota-ci-runner` (live, IAP SSH, ngoài Terraform): config trước đó chỉ có comment mặc định. Ghi cấu hình metrics tối thiểu (hostmetrics, metrics_filter); logging giữ mặc định. Có sao lưu `config.yaml.bak-processes`. Restart OK. **Cấu hình này không nằm trong repo**; cần ghi nhận thủ công.
- Trước đó đã có: `ops-agent-staging.yaml` (app HA, rollout 07:21–07:30 UTC) và `ops-agent-crawler.yaml` (deploy crawler). Xem `2026-10-12-monitor-tiet-kiem-processes.md`.

## Kiểm

- `processes/cpu_time` dừng sau thời điểm restart (~07:41 UTC): pg-a 07:40:50, pg-b 07:41:46, ci-runner 07:41:38. Crawler dừng từ 07:18:29; VM app mới không có series nào.
- `memory/percent_used` vẫn gửi đều trên cả ba (điểm mới nhất 07:45–07:46 UTC).
- Log probe Patroni (`patroni_cluster`) vẫn lên đều từ pg-a và pg-b.
- Test staging-ha: `test_ha_telemetry` 12 OK; các test khác không đổi.

## Lưu ý về cách kiểm (đã sửa)

- Các lần kiểm đầu trả 0 series cho mọi VM là **sai**: shell là zsh nên `for X in "pg-a 6872…"` không tách chuỗi, `instance_id` bị rỗng. Đã kiểm lại bằng ID viết cứng; kết quả ở trên là kết quả đúng.

## Phát hiện: replica DB chưa theo kịp leader (không liên quan đến thay đổi này)

- `curl http://127.0.0.1:8008/cluster` trên pg-a (chỉ đọc): leader `vota-ha-pg-a` timeline 5; replica `vota-ha-pg-b` timeline 2, `lag` ≈ 963 MB (lsn 0/890FA6D0). Replica vẫn `running` nhưng không theo kịp leader hiện tại.
- Log probe `patroni_cluster` ghi `no_replica` đều từ ít nhất 02:00 UTC (trước khi tôi đổi gì). Alert `DB: KHÔNG CÒN REPLICA` (patroni_monitoring.tf) lẽ ra đã kêu ngoài khung mute; chưa kiểm được email.
- Cần quyết định: kiểm log Patroni/Postgres của pg-b, slot và tiến trình streaming; có thể cần `pg_rewind` hoặc basebackup lại replica. Thao tác này thuộc DB, chưa làm.

## Còn lại / rủi ro

- Patroni: chưa apply Terraform. Thay đổi `patroni_ops_agent.yaml` làm drift thêm (metadata startup-script của pg-a/pg-b). Plan Patroni vẫn có thay đổi `machine_type` buộc stop VM. Không apply cho đến khi drift này được xử lý.
- ci-runner: cấu hình đang sống không nằm trong repo; nếu runner được tạo lại, processes sẽ quay lại.
- Billing: kiểm lại sau 24 giờ. Ước tính còn ~$4/tháng (phần agent không phải processes, sau khi trừ 150 MiB free); cần lean profile để về ~$0.
- Chưa commit.
