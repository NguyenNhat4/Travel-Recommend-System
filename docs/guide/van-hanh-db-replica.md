# Vận hành DB replica (staging)

Hướng dẫn dựng, kiểm tra và xử lý sự cố cho PostgreSQL replica. Kế hoạch: `docs/plan/2026-10-01-db-replica-terraform.md`. Nếu lệch PRD, contract hoặc `AGENTS.md` thì các nguồn đó thắng.

## 1. Dựng lần đầu

1. **Tạo VM bằng Terraform** (từ máy có quyền, hoặc workflow `Staging Infra Terraform` với `apply=true`):

   ```bash
   cd infra/terraform/environments/staging
   terraform init -backend-config=backend.staging.hcl
   terraform plan -var-file=staging.tfvars -out=staging.tfplan   # chỉ được thấy đúng 1 VM mới
   terraform apply staging.tfplan
   terraform output
   ```

2. **Chuẩn bị primary** (SSH vào VM db-primary, trong checkout repo). `REPLICA_IP` lấy từ `terraform output replica_private_ip`:

   ```bash
   REPLICA_IP=<replica_private_ip> sudo -E bash ops/bootstrap-db-primary-replication.sh
   ```

3. **Chuyển mật khẩu replicator** từ primary sang replica (file mode 600, không dán vào chat/log):

   ```bash
   gcloud compute scp --tunnel-through-iap --zone <zone> <primary>:/etc/vota/secrets/replicator_password /tmp/replicator_password
   gcloud compute scp --tunnel-through-iap --zone <zone> /tmp/replicator_password <replica>:/tmp/replicator_password && rm /tmp/replicator_password
   # trên replica:
   sudo install -D -m 600 /tmp/replicator_password /etc/vota/secrets/replicator_password && rm /tmp/replicator_password
   ```

4. **Dựng replica** (SSH vào VM replica, trong checkout repo). `PRIMARY_HOST` lấy từ `terraform output primary_private_ip`:

   ```bash
   IMAGE=pgvector/pgvector:0.8.6-pg18-bookworm PRIMARY_HOST=<primary_private_ip> sudo -E bash ops/bootstrap-db-replica.sh
   ```

   `IMAGE` phải đúng image của primary (`sudo docker inspect vota-postgres --format '{{.Config.Image}}'`). Image từ Docker Hub nên VM replica cần ra Internet (IP ngoài tạm thời).

5. **Bật giám sát**: trên replica chạy `sudo bash infra/monitoring/install-db-replica-monitoring.sh`; đặt biến GitHub `GCE_DB_REPLICA_INSTANCE` = tên VM replica rồi chạy lại workflow monitoring. Workflow tự kiểm VM có tồn tại (`gcloud compute instances describe`) trước khi bật alert replica; đặt biến sớm chỉ gây cảnh báo, không làm hỏng plan.

## 2. Kiểm tra

Trên primary:

```bash
sudo docker exec -u postgres vota-postgres psql -U postgres -c "SELECT client_addr, state, sync_state, replay_lag FROM pg_stat_replication"
sudo docker exec -u postgres vota-postgres psql -U postgres -c "SELECT slot_name, active, wal_status FROM pg_replication_slots"
```

Trên replica: `pg_is_in_recovery()` phải là `t`, và `tail -n 3 /var/log/vota/pg-replica.jsonl` phải có `"status":"ok"`.

Thử ghi đọc: tạo một bảng tạm trên primary, kiểm tra thấy trên replica, rồi xoá. Đối chiếu dữ liệu bằng `db/verify.sql` chạy qua tunnel replica (replica chỉ đọc, các câu lệnh verify chỉ SELECT).

## 3. Đọc từ máy/VM app qua tunnel

Primary dùng cổng 15432 như hiện tại. Replica dùng cổng 15433, tunnel thẳng tới IP private của replica:

```bash
ssh -N -L 127.0.0.1:15433:<replica_private_ip>:5432 <user>@<replica_private_ip>
bash scripts/check-db-tunnel.sh --port 15433
```

Backend và crawler không đổi: chúng vẫn dùng primary.

## 4. Xử lý sự cố

| Triệu chứng | Nguyên nhân thường gặp | Xử lý |
|---|---|---|
| Alert replication `broken` | Replica không streaming: primary đổi IP, mật khẩu sai, firewall, container chết | Xem `docker logs vota-postgres` trên replica; kiểm `pg_hba` và firewall nội bộ (`default-allow-internal`) |
| Alert `lagging` | Replica quá tải hoặc query đọc nặng giữ replay | Xem `pg_stat_activity` trên replica; giảm tải đọc. `max_standby_streaming_delay=60s` sẽ huỷ query dài |
| Slot `wal_status = lost` | Replica offline lâu hơn `max_slot_wal_keep_size` (mặc định 2 GB) | Dựng lại replica (mục 5) |
| Disk primary đầy do WAL | Replica offline, slot giữ WAL | `max_slot_wal_keep_size` đã chặn; vẫn kiểm `df -h`. Cần thì xoá slot rồi dựng lại replica |

`hot_standby_feedback=on` làm primary trì hoãn vacuum khi replica có query dài; không để query đọc chạy hàng giờ.

## 5. Dựng lại replica từ đầu

Chỉ làm khi replica hỏng hoặc slot `lost`. Trên VM replica:

```bash
sudo docker rm -f vota-postgres && sudo docker volume rm vota-pg18
IMAGE=<image của primary> PRIMARY_HOST=<primary_private_ip> sudo -E bash ops/bootstrap-db-replica.sh
```

## 6. Nâng replica thành primary (sự cố primary)

Làm tay, có người quyết định; không có failover tự động.

1. Xác nhận primary thật sự mất và tắt nó hẳn (tránh hai primary cùng ghi): `gcloud compute instances stop <primary>`.
2. Trên replica: `sudo docker exec -u postgres vota-postgres psql -U postgres -Atc "SELECT pg_promote()"`; kiểm `pg_is_in_recovery()` = `f`.
3. Đổi tunnel của backend và `DATABASE_URL`/`CDP_DATABASE_URL` sang replica (đã thành primary); chạy `scripts/deploy-backend-vm.sh` với `--db-tunnel-port` tương ứng.
4. Primary cũ không được bật lại vào cụm. Khi cần replica mới, dựng VM/volume mới và chạy lại mục 1 với primary mới.

## 7. Giới hạn đã biết

- Replica đọc có thể trễ vài giây. Đừng đọc-sau-ghi trên replica trong luồng booking/thanh toán.
- Lag được đo bằng probe mỗi phút; dưới ngưỡng 60 giây coi là `ok`.
- VM replica có IP ngoài tạm thời để apt/Docker ra được. VPC `default` có `default-allow-ssh` mở cho `0.0.0.0/0` (như hai VM kia) nên SSH tới replica cũng mở theo; Postgres 5432 không mở ra ngoài vì không có rule công khai cho cổng này. Có Cloud NAT thì đặt `assign_external_ip = false`.
