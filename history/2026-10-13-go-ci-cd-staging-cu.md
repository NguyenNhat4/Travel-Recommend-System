# Gỡ CI/CD, Terraform và monitoring của staging cũ, chỉ giữ staging-ha

- Ngày: 2026-10-13
- Tác giả: Khoa15 (yêu cầu) / Claude Code (agent)
- Nhánh: Khoa15/xoa-monitoring-staging-cu
- Trạng thái: dang dở (code xong, kiểm tra local xong; PR và CD chưa xác nhận)
- Phạm vi: infra (CI/CD, monitoring), docs

## Mục tiêu

Xoá CI/CD của staging cũ để tránh nhiễu, chỉ giữ CI/CD của staging-ha, và xoá monitoring cũ của staging cũ. Thay đổi này lệch PRD `deployment-plan.md` §1.1 và §6.3, nên có hai đề xuất đã áp dụng trong `docs/prd/update-archive/`: `2026-10-13-ngung-ci-cd-staging-cu.md` (gỡ CI/CD và Terraform) và `2026-10-13-xoa-monitoring-staging-cu.md` (xoá trên GCP, cập nhật mô tả tài nguyên còn lại).

## File thay đổi

- `docs/prd/update-archive/2026-10-13-ngung-ci-cd-staging-cu.md` — thêm: đề xuất, trạng thái `đã áp dụng`.
- `docs/prd/update-archive/2026-10-13-xoa-monitoring-staging-cu.md` — thêm: đề xuất, trạng thái `đã áp dụng`.
- `docs/prd/update/2026-10-09-cd-staging-ha.md` → `docs/prd/update-archive/2026-10-09-cd-staging-ha.md` — đổi tên: trạng thái `từ chối`, bị thay thế.
- `docs/prd/deployment-plan.md` — sửa §1.1 (staging-ha là staging duy nhất; mô tả đúng tài nguyên staging cũ còn trên GCP) và §6.3 (bỏ đường dẫn root cũ).
- `.github/workflows/infra-terraform-staging.yml`, `monitoring-terraform-staging.yml`, `monitoring-agent-cd-staging.yml` — xoá.
- `.github/actions/sync-env-from-secret-manager/action.yml` — xoá (không workflow nào dùng).
- `.github/workflows/backend-ci-cd.yml` — sửa: bỏ path action và compose VM cũ, bỏ `scripts/**` trùng; bước kiểm script VM cũ thay bằng `bash -n` cho bốn script deploy staging-ha.
- `.github/workflows/frontend-ci-cd.yml` — sửa: bỏ path action, compose và `deploy-frontend-vm.sh`.
- `.github/workflows/crawler-ci-cd.yml` — sửa: bỏ path action; xoá job `publish`; job `build` chỉ chạy trên PR, chỉ đọc cache GHA.
- `.github/workflows/ha-checks.yml` — sửa: thêm path `infra/monitoring/**`, bước `bash -n` và `unittest` cho agent giám sát (trước đây do `monitoring-agent-cd-staging.yml` kiểm).
- `infra/terraform/environments/staging/` (15 file) — xoá.
- `infra/monitoring/` — xoá các file Terraform (`*.tf`, lock, ví dụ tfvars và backend, `modules/`), `tests/test_staging_layout.sh`, `install-backend-monitoring.sh`, `install-db-replica-monitoring.sh`, `ops-agent-db-replica.yaml`. Giữ agent và collector mà startup script của staging-ha cài lên VM, cùng test của chúng.
- `infra/monitoring/README.md` — viết lại: chỉ mô tả agent trên VM, còn gì trên GCP và không được destroy.
- `infra/terraform/environments/staging-ha/tests/test_ha_telemetry.py` — sửa: bỏ phần đọc `infra/monitoring/main.tf`, thay bằng kiểm filter `helper` của dashboard staging-ha.
- `ops/ci-db-replication.sh`, `ops/bootstrap-db-primary-replication.sh`, `ops/bootstrap-db-replica.sh`, `ops/db-replica-lag-probe.sh`, `ops/tests/test_infra_layout.sh` — xoá.
- `ops/docker-compose.backend-vm.yml`, `scripts/deploy-backend-vm.sh`, `scripts/deploy-frontend-vm.sh`, `scripts/tests/test-backend-vm-cd-sync.sh` — xoá.
- `ops/promote-db-replica.sh` — sửa: hướng dẫn in ra không còn trỏ tới workflow và script đã gỡ.
- `docs/guide/env-secret-manager.md` — xoá (hướng dẫn riêng cho action đã gỡ).
- `docs/guide/trien-khai-job-cao-du-lieu.md` — sửa: mục deploy mô tả `staging-ha-crawler-cd.yml`.
- `docs/guide/van-hanh-db-replica.md` — sửa: thêm ghi chú đầu file là staging cũ đã ngừng. Phần thân còn mô tả quy trình cũ.

Không sửa, có chủ ý:

- `src/data_collection/README.md` còn ghi "CD `crawler-ci-cd.yml` chạy fresh-monitor". Câu này đã sai (crawler CD là `staging-ha-crawler-cd.yml`), nhưng sửa file này sẽ kích hoạt Crawler CD, tức là redeploy monitor cào trên VM. Sửa ở PR riêng.
- `Dockerfile.backend:53` và `scripts/deploy-staging-ha-crawler.sh:41,98` còn ghi chú nhắc script/workflow đã gỡ. Sửa `Dockerfile.backend` sẽ kích hoạt Backend CD.

Monitoring cũ đã xoá trên GCP (project `vinpearl-508801`, chỉ các tài nguyên `vota-staging*` và 3 policy do Compute Engine tạo): 18 alert policy, 4 log-metric, dashboard `vota-staging infrastructure`, uptime check `vota-staging-readiness`, exclusion `vota-staging-debug-and-health-ok`.

## Quyết định

- Giữ `ops/promote-db-replica.sh` vì `staging-ha/dns.tf` và `ha-checks` vẫn dùng. Giữ `ops/bootstrap-db-vm.sh` và `bootstrap-db-schema.sh` vì `ops/tests/test_db_image.sh` dùng chúng.
- Giữ 8 policy toàn project của stack cũ, log-metric và kênh email của chúng, vì đang bảo vệ VM staging-ha (container OOM/stop/disk, watcher, error logs, crawler, log ingest) và staging-ha chưa có bản thay thế. Mô tả trong PRD §1.1.
- Giữ metric descriptor `custom.googleapis.com/vota/container/*` (dashboard staging-ha vẽ; GCP chặn tạo lại trong 24 giờ sau khi xoá) và IP tĩnh `34.142.132.251` (bastion dùng).
- Không đụng tài nguyên GCP của stack cũ ngoài phần đã liệt kê. VM cũ vẫn ở trạng thái `TERMINATED`.
- Không sửa `docs/plan/*` và `docs/spec/2026-09-24-*`: đây là tài liệu lịch sử của từng giai đoạn.

## Kiểm tra

- Parse YAML mọi workflow: pass.
- `infra/terraform/environments/staging-ha/tests/test_*.py`: xem kết quả trong entry `2026-10-13-canh-bao-bo-nho-va-dia-app-ha.md` (cùng PR).
- `python3 -m unittest discover -s infra/monitoring/tests -p 'test_*.py'`: pass.
- `bash scripts/tests/test-install-vota-cron.sh`: pass. `bash ops/tests/test_promote_db_replica.sh`: pass.
- `bash -n` bốn script deploy staging-ha và `ops/promote-db-replica.sh`: pass. `terraform fmt -check` root staging-ha: pass.

## Còn lại / rủi ro

- Chưa import 8 policy, log-metric, kênh email, metric descriptor và IP còn lại vào root staging-ha. Đó là task riêng.
- Hai state `infra/staging` và `monitoring/staging` đã lệch so với GCP. Không chạy plan hay apply trên chúng.
- Khi merge, Backend CD và Frontend CD chạy vì `scripts/deploy-staging-ha-app.sh` đổi (allowlist), và Infra CD chạy vì `staging-ha/` đổi. Cả ba cùng dùng group `staging-ha-app`: theo review trước, job chờ có thể bị huỷ và cần chạy lại.
- Các secret và biến GitHub của stack cũ (`GCE_INSTANCE`, `GCE_ZONE`, `GCE_DB_INSTANCE`, `GCE_APP_INSTANCE`, `GCE_DB_REPLICA_INSTANCE`, `STAGING_UPTIME_HOST`, `GCE_BACKEND_ENV_SECRET`, `GCE_CRAWLER_ENV_SECRET`, `INFRA_ALLOW_*`) không còn workflow nào đọc; có thể gỡ ở Settings.
- `:buildcache` của `GAR_FRESH_IMAGE` không còn ai ghi (staging-ha dùng `:buildcache-ha`).
- `docs/guide/van-hanh-db-replica.md` phần thân và `docs/spec/2026-09-24-*` còn mô tả quy trình cũ; đã có ghi chú hoặc là tài liệu lịch sử.
