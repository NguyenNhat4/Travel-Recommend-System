# Sửa bootstrap runtime cho HA app MIG

- Ngày: 2026-10-08
- Tác giả: người dùng / Codex
- Nhánh: `khoa/ha-runtime-bootstrap-fix`
- Trạng thái: hoàn thành
- Phạm vi: backend

## Mục tiêu

Sửa nguyên nhân hệ thống khiến toàn bộ VM mới trong `vota-ha-app` không đạt readiness: Container-Optimized OS không có `gcloud`/`docker compose`, JWT PEM được bind-mount với quyền `root:root 600` trong khi backend chạy bằng group `10001`, và rollout MIG chưa khai báo rõ phương thức thay instance.

## File thay đổi

- `infra/terraform/environments/staging-ha/compose.ha.yml` — sửa: bind-mount thư mục JWT vào container backend ở chế độ chỉ đọc.
- `infra/terraform/environments/staging-ha/main.tf` — sửa: dùng `SUBSTITUTE`, `max_surge = 3`, `max_unavailable = 0` cho rolling update MIG.
- `infra/terraform/environments/staging-ha/monitoring.tf` — sửa: biểu diễn điều kiện autoscaler đạt trần bằng `COMPARISON_GT` và ngưỡng `max_replicas - 0.5`, tương thích Cloud Monitoring.
- `infra/terraform/environments/staging-ha/pgbouncer-setup.sh` — sửa: giải mã password URL-encoded trước khi ghi `userlist.txt`, escape dấu nháy và từ chối input không an toàn.
- `infra/terraform/environments/staging-ha/startup.sh.tftpl` — sửa: lấy Secret Manager bằng metadata token/REST, chạy Compose qua `docker:27-cli`, tạo JWT PEM với group `10001`, quyền thư mục `750` và file `640`.
- `infra/terraform/environments/staging-ha/tests/test_alerts.py` — sửa: kiểm tra điều kiện cảnh báo trần mới.
- `infra/terraform/environments/staging-ha/tests/test_pgbouncer_setup.py` — sửa: thêm test password URL-encoded, dấu nháy và input không hợp lệ.
- `infra/terraform/environments/staging-ha/tests/test_resilience.py` — sửa: kiểm tra policy `SUBSTITUTE` và quyền JWT cho backend group.
- `history/2026-10-08-ha-runtime-bootstrap-fix.md` — thêm: ghi lại nguyên nhân, quyết định và kết quả kiểm chứng.

## Quyết định

- Sửa ở instance template/startup script và để MIG recreate/rollout tự động; không SSH hoặc chỉnh tay từng VM.
- Giữ key root-owned nhưng cho group runtime `10001` traverse/read, thay vì làm lộ key cho mọi user trong container.
- Dùng `SUBSTITUTE` với `max_unavailable = 0` để thay instance mới mà không chủ động làm mất capacity trong rolling update.
- Không ghi secret, JWT hoặc giá trị môi trường nhạy cảm vào source, history hay log.

## Kiểm tra

- `python3 -m unittest discover -s infra/terraform/environments/staging-ha/tests -p 'test_*.py' -v` — **48 tests, PASS**.
- Rendered startup script từ instance template hiện hành — `bash -n`, **PASS**.
- GCP `vota-ha-app` — 3/3 VM `RUNNING`, dùng cùng instance template, phân bố ở `asia-southeast1-a/b/c`, tất cả `HEALTHY`.
- GCP backend service `vota-ha-app` — 3/3 backend port `3000`, tất cả `HEALTHY`.
- GCP MIG — `isStable: true`, `versionTarget.isReached: true`, `replacementMethod: SUBSTITUTE`, `maxUnavailable: 0`.
- Terraform apply đã hoàn tất trước khi ghi entry này: **0 added, 2 changed, 1 destroyed**.

## Còn lại / rủi ro

- Chưa chạy rolling-update drill dưới tải thực tế sau lần sửa; cần thực hiện trong kế hoạch HA nếu cần bằng chứng SLO.
- Các file local `backend_override.tf`, plan Terraform, log/agent worktree và báo cáo stress-test không thuộc commit này, được giữ nguyên ngoài phạm vi.
