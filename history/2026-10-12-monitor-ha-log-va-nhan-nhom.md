# Monitor HA (PR 2): nhãn nhóm, Ops Agent và collector trên VM app HA, dashboard container

- Ngày: 2026-10-12
- Tác giả: Khoa15 (yêu cầu) / Claude Code (agent)
- Nhánh: Khoa15/adjust-monitor-staging-ha
- Trạng thái: dang dở (code và test local xong; chưa tạo VM thử, chưa rollout template, chưa apply)
- Phạm vi: infra (staging-ha)
- Liên quan: `2026-10-12-monitor-ha-canh-bao-va-dashboard.md` (PR 1), `docs/plan/2026-10-12-monitor-staging-ha.md`

## Mục tiêu

VM app trong MIG hiện chỉ có Ops Agent mặc định (syslog và host metrics). Log backend và container không lên Cloud Logging (kiểm 2026-10-12: không có entry `service="backend"` nào trong 1 ngày). Entry này đưa cấu hình giám sát của VM staging cũ sang VM HA, và gắn nhãn nhóm để lọc VM theo nhóm.

## File thay đổi

- `infra/terraform/environments/staging-ha/main.tf` — sửa: thêm `locals.monitoring_metadata` (9 key `vota-mon-*`, đọc từ `infra/monitoring/` bằng `file()`); template có `labels = { group = "vota-ha-app", role = "app" }`; `metadata = merge(local.monitoring_metadata, {...})`.
- `infra/terraform/environments/staging-ha/startup.sh.tftpl` — thêm: hàm `fetch_monitoring_file` và `install_monitoring`, gọi sau bước cài Ops Agent. Ghi file từ metadata vào `/opt/vota-monitoring/`; cài Ops Agent với `ops-agent-staging.yaml` (có `hostmetrics`, giữ metric memory cho autoscaler), khôi phục cấu hình trước đó nếu restart lỗi; cài watcher và collector bằng `install-vota-docker-event-watcher.sh` có sẵn.
- `infra/terraform/environments/staging-ha/dashboard.tf` — thêm: hai ô CPU và RAM theo từng container (`custom.googleapis.com/vota/container/*`), nhóm theo `container_name` và `instance_id`.
- `infra/terraform/environments/staging-ha/tests/test_ha_telemetry.py` — thêm (mới): 8 test ở commit này (sau đó PR 3 thêm 2 test cho crawler).

## Quyết định

- File giám sát đưa qua `metadata`, không nhúng vào `startup.sh.tftpl`. Lý do: template dùng `templatefile`, script Python và install script có thể chứa `${`, dễ lỗi escape. Tổng metadata khoảng 20 KB, dưới giới hạn 256 KB.
- Cấu hình Ops Agent được cài trước collector. Nếu Ops Agent không khởi động với cấu hình mới, hàm khôi phục cấu hình trước đó, để metric `agent.googleapis.com/memory/percent_used` (autoscaler) không mất.
- Hàm `install_monitoring` được gọi trong `||`, nên lỗi không chặn khởi động app. Mỗi bước tải file có `|| return 1` để dừng sớm (test kiểm điều này).
- C3 (alert RAM vắng mặt theo nhóm) chưa làm: chưa kiểm được `metadata.user_labels` trong alert filter. Cần VM thử.
- Hệ quả đã biết: các alert project-wide của `infra/monitoring` (`staging_error_logs`, `staging_container_stop`, `staging_container_oom`) sẽ đếm cả VM HA sau rollout, và gửi qua kênh `vota-staging`. Chưa quyết định giữ hay giới hạn; xem plan.

## Kiểm tra

- `python3 infra/terraform/environments/staging-ha/tests/test_ha_telemetry.py` (8 test lúc thêm; sau PR 3 là 10): OK.
- `terraform -chdir=infra/terraform/environments/staging-ha fmt -check -recursive`: sạch.
- `terraform -chdir=infra/terraform/environments/staging-ha validate`: "The configuration is valid."
- Khối giám sát trong `startup.sh.tftpl` tách ra và chạy `bash -n`: OK. Không còn `${`/`%{` trong khối này (chỉ các dòng templatefile có sẵn).
- `bash -n infra/monitoring/install-vota-docker-event-watcher.sh`: OK. `py_compile` ba collector: OK.
- Chưa kiểm: VM thử (chưa tạo), rollout template, Ops Agent có khởi động với `ops-agent-staging.yaml` trên VM thật, log backend có `instance_id`, series custom metric của container.

## Còn lại / rủi ro

- Tạo VM thử `vota-ha-app-ops-test` (không gắn tag `vota-ha-app`) để kiểm trước khi rollout. Cần người duyệt vì là ghi lên GCP.
- Rollout template làm MIG thay VM: làm lúc MIG về 0 VM (00:00–08:19, CD bị khoá 23:45–08:40) hoặc chấp nhận downtime ~230–300 s theo quyết định 2026-10-09.
- Sau rollout kiểm autoscaler `ACTIVE`, `statusDetails` trống (xem `2026-10-09-app-debian-ops-agent-va-hoan-tat-todo-ha.md`).
- Xác nhận `hostmetrics` của `ops-agent-staging.yaml` vẫn đủ metric memory `state="used"` trên VM thật.
