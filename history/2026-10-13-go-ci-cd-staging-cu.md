# Gỡ CI/CD và Terraform của staging cũ, chỉ giữ staging-ha

- Ngày: 2026-10-13
- Tác giả: hp09.com@gmail.com (yêu cầu) / Claude Code (agent)
- Nhánh: claude/cicd-review-53f208
- Trạng thái: hoàn thành
- Phạm vi: infra (CI/CD), docs

## Mục tiêu

Người dùng yêu cầu xoá CI/CD của staging cũ để tránh nhiễu, chỉ giữ CI/CD của staging-ha. Đây là thay đổi lệch PRD (`deployment-plan.md` §1.1 nhắc `infra-terraform-staging.yml`), nên đã tạo đề xuất `docs/prd/update-archive/2026-10-13-ngung-ci-cd-staging-cu.md`. Người dùng chốt ngày 2026-10-13, chọn mở rộng phạm vi sang xoá cả Terraform cũ.

## File thay đổi

- `docs/prd/update-archive/2026-10-13-ngung-ci-cd-staging-cu.md` — thêm: đề xuất, trạng thái `đã áp dụng`.
- `docs/prd/update/2026-10-09-cd-staging-ha.md` → `docs/prd/update-archive/` — đổi tên: trạng thái `từ chối`, bị thay thế bởi đề xuất trên.
- `docs/prd/deployment-plan.md` — sửa §1.1 (staging-ha là staging duy nhất, cấm destroy state cũ, liệt kê tài nguyên đang phục vụ staging-ha) và §6.3 (bỏ đường dẫn root cũ).
- `.github/workflows/infra-terraform-staging.yml`, `monitoring-terraform-staging.yml`, `monitoring-agent-cd-staging.yml` — xoá.
- `.github/actions/sync-env-from-secret-manager/action.yml` — xoá (không workflow nào dùng).
- `.github/workflows/backend-ci-cd.yml` — sửa: bỏ path action/compose VM cũ và `scripts/**` trùng; bước kiểm script VM cũ được thay bằng `bash -n` cho bốn script deploy staging-ha.
- `.github/workflows/frontend-ci-cd.yml` — sửa: bỏ path action, compose và `deploy-frontend-vm.sh`.
- `.github/workflows/crawler-ci-cd.yml` — sửa: bỏ path action; xoá job `publish`; job `build` chỉ chạy trên PR, chỉ đọc cache GHA, không đăng nhập GAR.
- `.github/workflows/ha-checks.yml` — sửa: thêm path `infra/monitoring/**`, bước `bash -n` và `unittest` cho agent giám sát (trước đây do `monitoring-agent-cd-staging.yml` kiểm).
- `infra/terraform/environments/staging/` (15 file) — xoá.
- `infra/monitoring/` — xoá các file `*.tf`, `.terraform.lock.hcl`, `backend.staging.hcl.example`, `staging.tfvars.example`, `modules/README.md`, `tests/test_staging_layout.sh`, `install-backend-monitoring.sh`, `install-db-replica-monitoring.sh`, `ops-agent-db-replica.yaml`. Giữ các agent/collector mà staging-ha nạp qua `main.tf` và các test của chúng.
- `infra/monitoring/README.md` — viết lại: chỉ mô tả agent trên VM, kèm danh sách tài nguyên không được destroy.
- `infra/terraform/environments/staging-ha/tests/test_ha_telemetry.py` — sửa: bỏ phần đọc `infra/monitoring/main.tf`, thay bằng kiểm filter `helper` của dashboard staging-ha.
- `ops/ci-db-replication.sh`, `ops/bootstrap-db-primary-replication.sh`, `ops/bootstrap-db-replica.sh`, `ops/db-replica-lag-probe.sh`, `ops/tests/test_infra_layout.sh` — xoá.
- `ops/docker-compose.backend-vm.yml`, `scripts/deploy-backend-vm.sh`, `scripts/deploy-frontend-vm.sh`, `scripts/tests/test-backend-vm-cd-sync.sh` — xoá.
- `ops/promote-db-replica.sh` — sửa: hướng dẫn in ra không còn trỏ tới workflow/script đã gỡ.
- `docs/guide/env-secret-manager.md` — xoá (hướng dẫn riêng cho action đã gỡ).
- `docs/guide/trien-khai-job-cao-du-lieu.md` — sửa: mục deploy mô tả `staging-ha-crawler-cd.yml`.
- `docs/guide/van-hanh-db-replica.md` — sửa: thêm ghi chú staging cũ đã ngừng ở đầu file.
- `src/data_collection/README.md` — sửa: câu về monitor công khai trỏ tới CD staging-ha.

## Quyết định

- Xoá code không xoá tài nguyên GCP. Hai state `infra/staging` và `monitoring/staging` còn giữ một số tài nguyên staging-ha đang dùng: alert và log-metric toàn project (container stop/OOM/disk, crawler failure/warning, error logs, watcher heartbeat, log ingestion spike), metric descriptor `vota/container/*`, retention/exclusion log, IP tĩnh `34.142.132.251` của bastion. Người dùng chọn vẫn xoá code, ghi cảnh báo cấm destroy ở PRD §1.1 và `infra/monitoring/README.md`, và để việc import vào staging-ha cho task sau.
- Giữ `ops/promote-db-replica.sh` vì `staging-ha/dns.tf` và `ha-checks` vẫn dùng. Giữ `ops/bootstrap-db-vm.sh` và `bootstrap-db-schema.sh` vì `ops/tests/test_db_image.sh` dùng chúng.
- Không sửa ghi chú cũ trong `Dockerfile.backend:53` và `scripts/deploy-staging-ha-crawler.sh` (trỏ tới script/workflow đã gỡ), vì sửa hai file này sẽ kích hoạt build và deploy staging-ha chỉ vì một dòng comment.
- Không sửa `docs/plan/*`, `docs/spec/2026-09-24-*`: đây là tài liệu lịch sử của từng giai đoạn.

## Kiểm tra

- Parse YAML 10 workflow còn lại: pass.
- `infra/terraform/environments/staging-ha/tests/test_*.py` (8 file): pass. `test_ha_telemetry.py` fail sau khi xoá `infra/monitoring/main.tf`, pass sau khi sửa.
- `python3 -m unittest discover -s infra/monitoring/tests -p 'test_*.py'`: OK (18 test). `bash -n` agent installer: pass.
- `bash scripts/tests/test-install-vota-cron.sh`: pass. `bash ops/tests/test_promote_db_replica.sh`: pass.
- `bash -n` bốn script deploy staging-ha và `ops/promote-db-replica.sh`: pass. `terraform fmt -check` root staging-ha: pass.
- Chưa chạy workflow thật trên GitHub. Chưa có `actionlint` trên máy.

## Còn lại / rủi ro

- Import các tài nguyên toàn project nêu trên vào root staging-ha, rồi mới dọn tài nguyên staging cũ (VM, DB, firewall, địa chỉ).
- Khi merge, thay đổi này kích hoạt `Staging-HA Infra CD` (vì sửa test trong `staging-ha/`) và `Staging-HA Crawler CD` (vì sửa `src/data_collection/README.md`). Cả hai chạy lại với code ứng dụng không đổi.
- Các secret và biến GitHub của staging cũ (`GCE_INSTANCE`, `GCE_ZONE`, `GCE_DB_INSTANCE`, `GCE_APP_INSTANCE`, `GCE_DB_REPLICA_INSTANCE`, `STAGING_UPTIME_HOST`, `GCE_BACKEND_ENV_SECRET`, `GCE_CRAWLER_ENV_SECRET`, `INFRA_ALLOW_*`) không còn workflow nào đọc; người dùng tự gỡ ở Settings nếu muốn.
- Tag `:buildcache` của `GAR_FRESH_IMAGE` không còn ai ghi (staging-ha dùng `:buildcache-ha`).
