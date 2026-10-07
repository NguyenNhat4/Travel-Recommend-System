# Chỉnh DB replica theo cấu hình thật của primary

- Ngày: 2026-10-01
- Tác giả: Khoa / Claude Sonnet 5.5
- Nhánh: khoa/db-replica-terraform
- Trạng thái: hoàn thành
- Phạm vi: docs (hạ tầng/vận hành)
- Thay thế: một phần `2026-10-01-db-replica-terraform.md` (giả định PG16, image `vota-db:pg16`, 2 firewall rule, disk 30 GB)

## Mục tiêu

Sau khi người dùng chạy lệnh kiểm trên VM primary và tôi đọc GCP bằng `gcloud` (chỉ đọc), các giả định ban đầu sai nên sửa lại cho khớp thực tế.

## File thay đổi

- `infra/terraform/environments/staging/main.tf`, `data.tf`, `variables.tf`, `staging.tfvars.example`, `README.md` — sửa: bỏ 2 firewall rule, bỏ data VM app và biến `app_vm_name`, `iap_ssh_source_range`; disk mặc định 50 GB.
- `.github/workflows/infra-terraform-staging.yml` — sửa: bỏ `TF_VAR_app_vm_name`.
- `ops/bootstrap-db-primary-replication.sh`, `ops/db-replica-lag-probe.sh` — sửa: psql chạy bằng `docker exec -u postgres`.
- `ops/bootstrap-db-replica.sh` — sửa: `IMAGE` bắt buộc (đúng image của primary), PGDATA mặc định `/var/lib/postgresql/18/docker`, volume `vota-pg18`, chỉ đăng nhập Artifact Registry khi image nằm ở đó.
- `ops/tests/test_replica_scripts.sh` — sửa: kiểm theo các thay đổi trên.
- `docs/plan/2026-10-01-db-replica-terraform.md`, `docs/guide/van-hanh-db-replica.md` — sửa: PG18, image, disk, firewall.

## Quyết định

- Sự thật đo được: primary `v-ota-db-dev` (e2-small, zone a, disk 50 GB, VPC `default`) chạy `pgvector/pgvector:0.8.6-pg18-bookworm`, `PGDATA=/var/lib/postgresql/18/docker`, local peer auth (`psql -U postgres` qua socket phải chạy bằng user hệ thống `postgres`). Repo không còn khớp (`bootstrap-db-vm.sh` nói PG16, `vota-db:pg16`).
- Replica phải cùng major version và image với primary (physical replication yêu cầu), nên `IMAGE` là tham số bắt buộc thay vì mặc định đoán.
- VPC `default` có `default-allow-internal` (10.128.0.0/9, mọi tcp) và `default-allow-ssh` (0.0.0.0/0), nên 2 firewall rule viết trước đó là thừa: bỏ để ít tài nguyên hơn. Đổi lại replica phụ thuộc các rule mặc định này.
- Replica dùng cùng service account compute mặc định với primary, nên cũng chịu các rule công khai cổng 8000/8765 nhắm theo service account đó; không có dịch vụ nào nghe ở các cổng này trên replica.
- Giữ IP ngoài tạm thời (cùng kiểu với 2 VM hiện có, và cần cho Docker Hub/apt).

## Kiểm tra

- `terraform fmt -check`, `init -backend=false`, `validate` cho root staging: pass.
- `bash ops/tests/test_replica_scripts.sh`: pass; `bash -n` các script: pass.
- Chưa chạy `plan/apply` và script thật. Chưa đối chiếu dữ liệu primary (volume, mount, mạng Docker, kích thước dữ liệu) vì chưa có output các lệnh đó.

## Còn lại / rủi ro

- Cần thêm output từ VM primary: mounts/volume, mạng Docker, kích thước dữ liệu, wal settings, các extension đang dùng.
- VM app thật là `vota-backend-crawler-recsys` (e2-medium), không phải e2-small như nói miệng; không ảnh hưởng replica.
