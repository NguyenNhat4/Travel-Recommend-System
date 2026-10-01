# Thêm DB replica PostgreSQL và Terraform cho VM replica (staging)

- Ngày: 2026-10-01
- Tác giả: Khoa / Claude Sonnet 5.5
- Nhánh: khoa/db-replica-terraform
- Trạng thái: hoàn thành
- Phạm vi: docs (hạ tầng/vận hành)

## Mục tiêu

Chuyển phần hạ tầng mới sang Terraform và thêm một PostgreSQL replica chỉ đọc, có giám sát, mà vẫn giữ mô hình 2 VM nhỏ hiện có (app, db-primary). Kế hoạch trước đó đã bị bác vì quá đắt, thừa và phức tạp; bản này chỉ thêm một VM e2-small.

## File thay đổi

- `infra/terraform/environments/staging/` (`versions.tf`, `backend.tf`, `provider.tf`, `variables.tf`, `data.tf`, `main.tf`, `outputs.tf`, `staging.tfvars.example`, `backend.staging.hcl.example`, `README.md`, `.terraform.lock.hcl`) — thêm: root Terraform; 2 VM cũ chỉ là `data`, tạo VM replica và 2 firewall.
- `ops/bootstrap-db-primary-replication.sh` — thêm: chuẩn bị primary (role, slot, pg_hba /32, giới hạn WAL của slot), idempotent.
- `ops/bootstrap-db-replica.sh` — thêm: `pg_basebackup -R` rồi chạy hot standby, cùng khuôn với `bootstrap-db-vm.sh`.
- `ops/db-replica-lag-probe.sh` — thêm: probe mỗi phút ghi JSON `ok|lagging|broken`.
- `ops/tests/test_replica_scripts.sh` — thêm: kiểm tra script và layout Terraform.
- `infra/monitoring/replica.tf`, `ops-agent-db-replica.yaml`, `install-db-replica-monitoring.sh` — thêm: log metric và alert cho replica, cấu hình Ops Agent, script cài trên VM replica.
- `infra/monitoring/variables.tf`, `data.tf`, `outputs.tf` — sửa: biến `db_replica_vm_name` (mặc định rỗng), data và output cho replica.
- `infra/monitoring/tests/test_staging_layout.sh` — sửa: yêu cầu các file replica mới.
- `.github/workflows/infra-terraform-staging.yml` — thêm: validate khi PR/push; plan/apply chỉ chạy tay.
- `.github/workflows/monitoring-terraform-staging.yml` — sửa: truyền `TF_VAR_db_replica_vm_name`.
- `docs/plan/2026-10-01-db-replica-terraform.md`, `docs/guide/van-hanh-db-replica.md` — thêm: kế hoạch và runbook.

## Quyết định

- Không Cloud SQL, không HA tự động, không import hai VM tạo tay: giữ chi phí khoảng 17-20 USD/tháng và rủi ro thấp. Hai VM cũ chỉ được đọc bằng `data`.
- Replica cùng zone, cùng VPC, dùng lại service account và scope của primary để pull image `vota-db:pg16` như primary.
- Firewall nhắm primary theo service account vì VM tạo tay không có network tag. Replica nhận SSH chỉ từ IAP và IP VM app.
- Replica có IP ngoài tạm thời (biến `assign_external_ip`, mặc định true) để apt/Docker/Artifact Registry ra được khi chưa có Cloud NAT. Đây là điểm khác bản kế hoạch nói miệng trước đó ("không IP public"); ingress vẫn đóng.
- `max_slot_wal_keep_size` mặc định 2GB để replica chết không làm đầy disk primary.
- Giám sát lag bằng probe log (lag = 0 khi đã replay hết, để primary rảnh không báo lag giả), alert theo log-based metric. Toàn bộ monitoring replica bị bỏ qua khi `db_replica_vm_name` rỗng, nên merge trước khi có replica là an toàn.
- Workflow infra: apply chỉ chạy tay (`apply=false` mặc định) vì tạo hạ tầng nên có chủ đích.
- Backend không đổi; vẫn một `DATABASE_URL` trỏ primary. Đọc từ replica trong backend để sau.
- Chủ dự án chọn tạm bỏ qua PRD. `docs/prd/deployment-plan.md` chưa nhắc Terraform VM/replica, nên theo `AGENTS.md` §8 vẫn cần đề xuất trong `docs/prd/update/` để chính thức hoá; chưa tạo.

## Kiểm tra

- `terraform fmt -check -recursive` + `terraform init -backend=false` + `terraform validate` cho `infra/terraform/environments/staging` và `infra/monitoring`: pass.
- `bash ops/tests/test_replica_scripts.sh`: pass. `bash infra/monitoring/tests/test_staging_layout.sh`: pass.
- `bash -n` cho 4 script mới: pass. Probe thử với `docker` giả cho 5 tình huống (ok, lagging, không streaming, không recovery, lỗi): đúng trạng thái.
- Chưa chạy: `terraform plan/apply`, script bootstrap và alert trên GCP/VM thật (không có quyền/ý định đụng hạ tầng thật trong phiên này). `Dockerfile.db` không có trong repo nên chưa kiểm được đường dẫn dữ liệu của image `vota-db:pg16`; script giả định PGDATA là `/var/lib/postgresql/data` với volume mount tại `/var/lib/postgresql` như `bootstrap-db-vm.sh`.

## Còn lại / rủi ro

- Lần chạy thật đầu tiên cần theo runbook `docs/guide/van-hanh-db-replica.md`; xác nhận `disk_size_gb`, tên VM, `PROJECT_ID`/`IMAGE` mặc định khớp primary, và `pg_hba` ghi được trong container.
- Tạo đề xuất `docs/prd/update/` nếu muốn chính thức hoá.
- Chưa có cơ chế đọc replica trong backend, chưa có failover tự động (promote làm tay).
- Nên thêm biến GitHub `GCE_DB_REPLICA_INSTANCE` sau khi replica tồn tại để bật monitoring.
