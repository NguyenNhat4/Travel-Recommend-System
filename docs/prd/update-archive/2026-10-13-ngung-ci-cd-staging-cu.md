# Ngừng CI/CD và Terraform của staging cũ, staging-ha là môi trường staging duy nhất

- Ngày: 2026-10-13
- Người đề xuất: hp09.com@gmail.com / Claude Code (agent)
- Trạng thái: đã áp dụng
- Chốt bởi / ngày: hp09.com@gmail.com, 2026-10-13 (chọn "Chốt, xoá cả Terraform cũ")
- PRD bị ảnh hưởng: `docs/prd/deployment-plan.md` §1.1, §6.3
- Mã FR/NFR: không đổi FR/NFR (dọn hạ tầng vận hành)
- Thay thế: `2026-10-09-cd-staging-ha.md` (đề xuất đó giữ CD staging cũ song song; CD staging-ha đã chạy thực tế từ 2026-10-09)

## Lý do

Staging cũ (một VM app, cặp DB primary/replica) không còn nhận deploy. Job deploy lên VM đã bị tắt bằng `if: false` rồi xoá ngày 2026-10-13. Cặp DB cũ đã nghỉ khi chuyển sang Patroni. Dù vậy, ba workflow vẫn kích hoạt khi push và nhắm vào tài nguyên cũ: `infra-terraform-staging.yml`, `monitoring-terraform-staging.yml`, `monitoring-agent-cd-staging.yml`. Chúng chiếm runner tự host chung với CD staging-ha, và lỗi của chúng gây nhiễu khi đọc trạng thái CI/CD.

## Nội dung đề xuất

`deployment-plan.md` §1.1, đoạn hiện tại:

> `staging-ha` là Terraform root và state riêng (`infra/staging-ha`), tách khỏi root/state `infra/staging`. Vì hai root có state khác nhau, thay đổi Patroni không làm thay đổi tài nguyên do workflow `infra-terraform-staging.yml` quản lý; các workflow CI/CD ứng dụng và crawler cũng không bị sửa trong phạm vi này.

Đoạn thay thế:

> `staging-ha` là môi trường staging duy nhất, có Terraform root và state riêng (`infra/staging-ha`). Staging cũ (root `infra/staging` và `infra/monitoring`) đã ngừng ngày 2026-10-13: repo không còn Terraform hay workflow CI/CD của nó. Tài nguyên GCP cũ và hai state `infra/staging`, `monitoring/staging` vẫn còn. **Không destroy hai state này:** chúng còn giữ những tài nguyên staging-ha đang dùng, gồm alert và log-metric áp cho toàn project (container stop/OOM/disk, crawler failure, error logs, log ingestion), metric descriptor `custom.googleapis.com/vota/container/*` mà dashboard staging-ha vẽ, cấu hình retention/exclusion log, và IP tĩnh `34.142.132.251` của bastion. Các tài nguyên này phải được chuyển (import) vào root staging-ha trước khi dọn staging cũ. Thư mục `infra/monitoring/` chỉ còn agent và collector mà startup script của staging-ha cài lên VM.

`deployment-plan.md` §6.3, câu hiện tại:

> Không chạy `terraform apply` của root `infra/terraform/environments/staging` để rollback Patroni; hai state có ranh giới riêng.

Câu thay thế:

> Không dùng state `infra/staging` của staging cũ (đã gỡ khỏi repo) để rollback Patroni; hai state có ranh giới riêng.

## Thay đổi source sau khi chốt

- Xoá workflow: `.github/workflows/infra-terraform-staging.yml`, `monitoring-terraform-staging.yml`, `monitoring-agent-cd-staging.yml`.
- Xoá Terraform cũ: `infra/terraform/environments/staging/`. Trong `infra/monitoring/`, xoá các file `.tf`, lock, ví dụ tfvars/backend, `modules/`, `tests/test_staging_layout.sh`, cùng ba file chỉ VM cũ dùng: `install-backend-monitoring.sh`, `install-db-replica-monitoring.sh`, `ops-agent-db-replica.yaml`. Giữ các file staging-ha nạp qua `main.tf`/startup script: `install-vota-docker-event-watcher.sh`, `ops-agent-staging.yaml`, `ops-agent-crawler.yaml`, `vota-*.py|service`, `vota-monitoring-logrotate.conf`, cùng các test Python của chúng.
- Xoá script chỉ staging cũ dùng: `ops/ci-db-replication.sh`, `ops/bootstrap-db-primary-replication.sh`, `ops/bootstrap-db-replica.sh`, `ops/db-replica-lag-probe.sh`, `ops/tests/test_infra_layout.sh`.
- Xoá CD lên VM cũ: action `.github/actions/sync-env-from-secret-manager/`, `scripts/deploy-backend-vm.sh`, `scripts/deploy-frontend-vm.sh`, `ops/docker-compose.backend-vm.yml`, `scripts/tests/test-backend-vm-cd-sync.sh`, `docs/guide/env-secret-manager.md` (hướng dẫn riêng cho action này), cùng job `publish` của `crawler-ci-cd.yml`.
- `backend-ci-cd.yml`, `frontend-ci-cd.yml`, `crawler-ci-cd.yml`: chỉ còn CI, bỏ các path và bước kiểm thuộc VM cũ.
- Cập nhật tài liệu và ghi chú còn trỏ tới các file đã xoá.
- Không đổi hành vi: các workflow `staging-ha-*.yml`, `ops/promote-db-replica.sh` (staging-ha dùng qua `dns.tf`). `ha-checks.yml` nhận thêm phần kiểm agent trong `infra/monitoring/` (trước đây do `monitoring-agent-cd-staging.yml` kiểm). `staging-ha/tests/test_ha_telemetry.py` bỏ phần đọc `infra/monitoring/main.tf`. Tài nguyên GCP của staging cũ không bị destroy.
- Sau khi chốt, người dùng chọn thêm (2026-10-13): vẫn xoá Terraform cũ dù một phần tài nguyên phục vụ staging-ha; ghi cảnh báo cấm destroy ở PRD §1.1 và `infra/monitoring/README.md`; việc import các tài nguyên đó vào staging-ha là task sau.
- Đề xuất `2026-10-09-cd-staging-ha.md` chuyển sang `docs/prd/update-archive/` với trạng thái `từ chối`, bị thay thế bởi đề xuất này.
