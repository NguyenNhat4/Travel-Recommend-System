# DB replica PostgreSQL và Terraform cho hạ tầng VM (staging)

- Phục vụ: NFR-REL-02, NFR-SEC-01, NFR-SEC-02, NFR-MAINT-01 (không mở rộng FR)
- Phạm vi: chỉ staging. Không Cloud SQL, không HA tự động, không đổi code app
- Lệch PRD: `docs/prd/deployment-plan.md` chưa nhắc Terraform cho VM và DB replica. Chủ dự án chọn tạm bỏ qua PRD; cần đề xuất trong `docs/prd/update/` trước khi coi là chính thức

## Mục tiêu

Thêm một PostgreSQL replica chỉ đọc cho nhu cầu đọc/báo cáo và dự phòng, có giám sát, mà không đổi mô hình 2 VM hiện tại. Phần hạ tầng mới do Terraform quản lý; hai VM tạo tay giữ nguyên.

## Thiết kế

```text
VM app (tạo tay)   ──ssh tunnel 15432──►  VM db-primary (tạo tay)  Postgres 18, Docker
   (frontend, backend, crawler, redis,                │ streaming replication, slot vota_replica
    weaviate)      ──ssh tunnel 15433──►  VM db-replica (Terraform) Postgres 18 standby, Docker
```

| VM | Cấu hình | Quản lý |
|---|---|---|
| app | giữ nguyên | tay và script cũ |
| db-primary | giữ nguyên (v-ota-db-dev, e2-small, disk 50 GB, Postgres 18, image `pgvector/pgvector:0.8.6-pg18-bookworm`) | tay và script cũ |
| db-replica | e2-small (2 vCPU chia sẻ, 2 GB), disk 50 GB bằng primary, cùng zone (`asia-southeast1-a`), VPC `default`, cùng service account và scope với primary, chạy đúng image của primary | Terraform |

Backend vẫn dùng một `DATABASE_URL` trỏ primary. Replica phục vụ tab DB của monitor, `db/verify.sql`, truy vấn báo cáo. Việc cho backend đọc từ replica (`REPLICA_DATABASE_URL`) là bước sau, đổi code app.

## Thành phần

- `infra/terraform/environments/staging/`: root Terraform mới, state riêng (`prefix = infra/staging`). Hai VM cũ chỉ là `data`; Terraform chỉ tạo VM replica. Không tạo firewall: VPC `default` đã có `default-allow-internal` (replica tới primary cổng 5432) và `default-allow-ssh`.
- `ops/bootstrap-db-primary-replication.sh`: chuẩn bị primary (role `replicator`, slot, `pg_hba` /32, giới hạn WAL giữ cho slot). Idempotent, không restart.
- `ops/bootstrap-db-replica.sh`: `pg_basebackup -R` rồi chạy hot standby; bắt buộc truyền `IMAGE` đúng image của primary, PGDATA mặc định `/var/lib/postgresql/18/docker`.
- `ops/db-replica-lag-probe.sh`: mỗi phút ghi một dòng JSON, trạng thái `ok | lagging | broken`.
- `infra/monitoring/`: `replica.tf` (alert VM mất, memory, disk, replication lỗi, probe im), `ops-agent-db-replica.yaml`, `install-db-replica-monitoring.sh`. Biến `db_replica_vm_name` mặc định rỗng nên chưa có replica thì không tạo gì.
- `.github/workflows/infra-terraform-staging.yml`: validate khi PR/push, plan/apply chỉ chạy tay (`workflow_dispatch`, `apply=false` mặc định).

## Chi phí ước tính thêm

Khoảng 18-22 USD/tháng (VM e2-small, disk 50 GB, IP ngoài tạm thời). Cần đối chiếu bảng giá GCP.

## Ngoài phạm vi

Import hai VM cũ vào Terraform, failover tự động, pgBouncer, Cloud NAT, đọc replica trong backend.

## Preflight bên ngoài repo

- Primary hiện: Postgres 18, `PGDATA=/var/lib/postgresql/18/docker`, local peer auth, disk 50 GB.
- GitHub Environment `staging` có `GCE_DB_INSTANCE`, `GCE_ZONE`, `TF_STATE_BUCKET`; thêm `GCE_DB_REPLICA_INSTANCE` (tên VM) sau khi tạo replica để bật monitoring.
- Primary cần `wal_level=replica` và `max_wal_senders` > 0 (mặc định PG18 là replica và 10); script in ra giá trị để đối chiếu.
