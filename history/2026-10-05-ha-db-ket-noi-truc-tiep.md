# Nhóm HA nối DB trực tiếp, bỏ SSH tunnel (6.1)

- Ngày: 2026-10-05
- Tác giả: Khoa / Claude
- Nhánh: khoa/ha-load-balancing
- Trạng thái: hoàn thành
- Phạm vi: backend | infra | ops | docs

## Mục tiêu

VM sinh từ instance template không có `vota-db-tunnel.service` nên không nối được DB; cần tên DB ổn định và phát hiện lỗi sớm.

## File thay đổi

- `src/backend/app/core/config.py` — sửa: `shared_backend_violations` thêm `DATABASE_URL`, `CDP_DATABASE_URL`
- `src/backend/tests/unit/api/test_ha_readiness.py` — sửa: thêm 2 ca DB loopback (tổng 11 test)
- `infra/terraform/environments/staging-ha/dns.tf` — thêm: private zone `vota.internal.`, bản ghi `db` và `db-replica` (TTL 30 giây, bỏ qua thay đổi `rrdatas` để failover đổi ngoài Terraform)
- `infra/terraform/environments/staging-ha/variables.tf`, `outputs.tf`, `staging-ha.tfvars.example` — sửa: `db_primary_ip`, `db_replica_ip`, output `db_host`
- `ops/check-db-direct.sh` — thêm: kiểm kết nối trực tiếp và ngân sách `max_connections`
- `ops/tests/test_check_db_direct.sh` — thêm: 4 ca trên Postgres Docker tạm
- `docs/plan/2026-10-05-ha-load-balancing.md` — sửa: use case 4 và dòng 6.1

## Quyết định

- Không thêm firewall mới: `firewall.tf` ghi `default-allow-internal` cho phép primary nhận kết nối trong VPC; script kiểm tra thay vì giả định.
- Không sửa `pg_hba` bằng script: image Postgres chính thức đã có `host all all all scram-sha-256`, thêm dòng sau nó vô tác dụng.
- Use case: VM thứ 4 của autoscaler không có tunnel, không bao giờ ready (chi tiết ở plan §3b).

## Kiểm tra

- `pytest src/backend/tests/unit/api/test_ha_readiness.py`: 11 passed.
- `bash ops/tests/test_check_db_direct.sh`: PASS (đạt, loopback bị từ chối, vượt `max_connections`, sai mật khẩu) trên Postgres 16 Docker.
- `terraform validate` staging-ha: pass.
- Chưa chạy: kiểm trên VM và primary staging thật; `terraform apply`.

## Còn lại / rủi ro

- Cần chạy `ops/check-db-direct.sh` trên VM thật để xác nhận firewall và `pg_hba`.
- Sau khi bật `db.vota.internal`, đổi `DATABASE_URL` trong secret `vota-ha-backend-env`.
