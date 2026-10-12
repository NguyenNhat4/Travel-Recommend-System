# Phase 3: di trú DB từ primary staging cũ sang cụm Patroni HA (hướng A)

- Ngày: 2026-10-08
- Tác giả: Khoa15 / Claude (agent), theo yêu cầu chấp thuận của người vận hành
- Nhánh: khoa/ha-runtime-bootstrap-fix
- Trạng thái: đã hoàn thành cutover; còn theo dõi ổn định (xem "Còn lại")
- Phạm vi: infra (GCP `vinpearl-508801`), Terraform `infra/terraform/environments/staging-ha`, cấu hình env trên VM crawler. Không đổi code ứng dụng.
- Liên quan: `docs/plan/2026-10-08-hoan-thanh-todo-ha.md` (Phase 3), `docs/guide/van-hanh-db-patroni.md` §3, `history/2026-10-08-db-ha-1vcpu-1gb.md`

## Mục tiêu

Đưa dữ liệu từ primary cũ `v-ota-db-dev` (`10.148.0.2`, Postgres 18.6) sang cụm Patroni (`vota-ha-pg-a` leader, `vota-ha-pg-b` sync replica, `vota-ha-pg-w` witness etcd), rồi cutover `db.vota.internal` sang ILB `10.148.0.34`. Primary cũ và replica staging `vota-staging-db-replica` không bị dừng.

## Sao lưu trước khi làm thao tác phá hủy

Snapshot READY (`gcloud compute snapshots list --filter=pre-phase3`):
- `vota-ha-pg-a-data-20261008-pre-phase3` (50 GB)
- `vota-ha-pg-b-data-20261008-pre-phase3` (50 GB)
- `v-ota-db-dev-20261008-pre-phase3` (50 GB)

Baseline số dòng trước khi đóng băng (`vota`): `cdp.products` 17679, `cdp.events` 40234, `cdp.profiles` 7005, `catalog.combo_items` 445, `app.users` 59, `app.bookings` 13. Database `insider` cũng có baseline riêng (`channel_events` 19517, `identifiers` 6020, `insider_events` 4155, `insider_profiles` 2000, `partners` 1).

## Các bước đã thực hiện

1. **Dừng job cào** trên `vota-backend-crawler-recsys`: `docker stop vota-backend vota-fresh-catalog-monitor`.
2. **Đóng băng ghi trên primary cũ**: `ALTER SYSTEM SET default_transaction_read_only = on`, reload, ngắt 12 kết nối client. Kiểm tra: `INSERT`/`UPDATE` trong transaction bị từ chối với `cannot execute INSERT in a read-only transaction`. Số dòng sau đóng băng khớp baseline.
3. **Cho phép replication từ pg-a** trên primary cũ: thêm `host replication replicator 10.148.0.35/32 scram-sha-256` vào `pg_hba.conf` (có bản sao lưu `pg_hba.conf.pre-phase3`), reload.
4. **Đồng bộ mật khẩu replicator tạm thời**: role `replicator` trên primary cũ có mật khẩu khác `PATRONI_REPLICATION_PASSWORD` nên clone bị từ chối. Lưu SCRAM verifier cũ, đặt tạm `PATRONI_REPLICATION_PASSWORD` (đọc từ Secret Manager qua stdin, không in ra), xác nhận đăng nhập replication từ pg-a được, và sau khi clone xong khôi phục verifier cũ (bước 9). Replica staging không bị ảnh hưởng: vẫn `streaming`.
5. **Xoá dữ liệu cụm HA cũ**: dừng `vota-patroni` trên pg-a và pg-b; xoá khoá `/service/vota-ha-pg/` trong etcd; xoá nội dung `/mnt/disks/pgdata/postgresql` trên pg-a (252 MB) và pg-b (288 MB), sau khi kiểm tra có `PG_VERSION` và đã có snapshot. etcd vẫn chạy 3/3.
6. **Clone**: `gcloud compute instances reset vota-ha-pg-a`. Log: `pg_basebackup` chạy thành công từ `10.148.0.2` (`starting backup recovery ... on timeline ID 1`).
7. **Sự cố trong lúc clone (đã xử lý)**: `post_bootstrap` lỗi `cannot execute ALTER ROLE in a read-only transaction` vì `postgresql.auto.conf` copy từ primary cũ có `default_transaction_read_only = on`. Patroni xoá khoá initialize và promote node, nên leader chạy ở chế độ read-only (timeline 2). Patroni không rename được thư mục dữ liệu (`Permission denied`), không ảnh hưởng dữ liệu.
8. **Kiểm tra dữ liệu sau clone**: số dòng toàn bộ bảng `vota` và `insider` khớp baseline; checksum `md5(cdp.products)` = `16f9a07e225f964364f141a1d8cc32b5` trên primary cũ, leader và replica.
9. **Sửa sau clone**:
   - Leader: `ALTER SYSTEM RESET default_transaction_read_only` và reload → `off`, không còn recovery.
   - Leader: đặt mật khẩu superuser `postgres` theo `PATRONI_SUPERUSER_PASSWORD` (post_bootstrap đã không chạy).
   - Primary cũ: khôi phục SCRAM verifier cũ của `replicator`. Replica staging vẫn `streaming`.
10. **Reset pg-b** để nhân bản từ leader: `sync_standby`, `streaming`, lag 0. etcd 3/3.
11. **Kiểm tra trước cutover**: ghi thử trong transaction trên leader thành công (rollback); ILB: pg-a HEALTHY, pg-b UNHEALTHY (đúng: chỉ leader trả 200 ở `/primary`).
12. **Cutover DNS**: `gcloud dns record-sets update db.vota.internal. --zone vota-ha-internal --ttl 30 --rrdatas 10.148.0.34` (từ `10.148.0.2`).
13. **App**: `getaddrinfo(db.vota.internal)` trên app VM = `10.148.0.34`. Restart `vota-pgbouncer` để bỏ kết nối pool cũ. Trên leader có phiên `vota_db_dev` từ `10.148.0.40` (app). Primary cũ không còn phiên app. `/health/ready` = 200, `db: true`. Smoke test `GET /search?q=ha long` trả 200 với dữ liệu catalog thật.
14. **Crawler**: đổi `127.0.0.1:15432` → `db.vota.internal:5432` trong `/etc/vota/backend.env`, `daily.env`, `fresh-catalog.env` (có bản sao `*.pre-phase3`). Đóng hai tiến trình autossh/ssh tunnel tới primary cũ (PID 384889, 683886). Khởi động lại `vota-backend` và `vota-fresh-catalog-monitor`. Log `vota-backend`: `startup.recsys.catalog.query.ready products=17679` (đọc từ DB mới).
15. **Gỡ `patroni_clone_from_host`** khỏi `staging-ha.tfvars` (vì node không được clone lại từ primary cũ). `terraform plan` chỉ có 1 thay đổi in-place: metadata `startup-script` của pg-a. Áp dụng. Sau đó `terraform plan`: `No changes`.

## Trạng thái sau cutover

- Cụm: leader `vota-ha-pg-a` (timeline 2), sync standby `vota-ha-pg-b` lag 0, witness `vota-ha-pg-w`, etcd 3/3.
- Primary cũ `v-ota-db-dev` (`10.148.0.2`): **vẫn `default_transaction_read_only = on`** (ALTER SYSTEM) làm hàng rào chống split-brain. Không nhận ghi từ app/crawler. Replica staging `vota-staging-db-replica` vẫn streaming từ đây.
- `db.vota.internal` = `10.148.0.34` (TTL 30).

## Vấn đề phát hiện thêm

- `vota-fresh-catalog-monitor` (cổng 8765 trên crawler) nhận nhiều kết nối bị reset từ IP `45.79.115.59`. Không liên quan DB, nhưng cổng này đang mở ra ngoài. Xem mục xử lý trong báo cáo cuối.

## Còn lại

- Theo dõi ổn định cụm sau cutover (cảnh báo "không còn replica", "không có leader").
- Khi cụm ổn định vài ngày: xem xét nghỉ hưu primary cũ (runbook §3 bước 6).
- Rollback nếu cần: DNS `db.vota.internal` về `10.148.0.2` và `ALTER SYSTEM RESET default_transaction_read_only` trên primary cũ. Lưu ý: ghi sau cutover nằm ở cụm mới và không tự đồng bộ ngược lại.

## Lệnh tái kiểm tra

```bash
gcloud dns record-sets list --zone=vota-ha-internal --name=db.vota.internal. --format='table(name,ttl,rrdatas)'
gcloud compute ssh vota-ha-pg-a --zone=asia-southeast1-a --project=vinpearl-508801 --tunnel-through-iap --command 'curl -s localhost:8008/cluster; echo'
gcloud compute ssh v-ota-db-dev --zone=asia-southeast1-a --project=vinpearl-508801 --tunnel-through-iap --command 'sudo docker exec -u postgres vota-postgres psql -X -d postgres -Atc "show default_transaction_read_only"'
terraform -chdir=infra/terraform/environments/staging-ha plan -var-file=staging-ha.tfvars -no-color
```
