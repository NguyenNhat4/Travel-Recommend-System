# Vận hành cụm DB Patroni (staging HA)

Kế hoạch và use case: `docs/plan/2026-10-07-ha-vung-crawler-rolling.md` §2. Nếu lệch PRD, contract hoặc `AGENTS.md` thì các nguồn đó thắng. Cụm tắt mặc định (`create_patroni = false` trong `infra/terraform/environments/staging-ha`).

## 1. Cụm gồm gì

| Node | Zone | Chạy | Vai trò |
|---|---|---|---|
| `vota-ha-pg-a` | zone đầu của `patroni_zones` | etcd + Patroni + Postgres | leader hoặc replica |
| `vota-ha-pg-b` | zone thứ hai (KHÁC zone a) | etcd + Patroni + Postgres | replica đồng bộ hoặc leader |
| `vota-ha-pg-w` | `patroni_witness_zone` (khác cả hai) | etcd | đa số thứ ba, không giữ dữ liệu |

Backend, crawler nối `db.vota.internal:5432` = IP ILB nội bộ; ILB chỉ gửi tới node trả 200 ở `:8008/primary`. Failover không đổi DNS, env hay VM app.

Số liệu tham chiếu: leader chết → khoá hết hạn tối đa 30 giây → replica đồng bộ tự nâng → ILB đổi hướng sau khoảng 10 giây. Đo trong Docker là 28 giây. Failover thật trên GCP đã thành công ngày 2026-10-08, nhưng không có timestamp start/end đủ tin cậy để công bố RTO chính xác; không dùng số 28 giây của Docker làm RTO GCP.

## 2. Dựng lần đầu

1. Build và đẩy image (tag SHA, không `latest`):
   ```bash
   docker build -t <registry>/vota-patroni:<sha> ops/patroni && docker push <registry>/vota-patroni:<sha>
   ```
2. Tạo tài khoản dịch vụ riêng cho node DB (đọc secret Patroni, kéo image). Đặt `create_patroni = true`, `patroni_image`, `patroni_service_account_email` trong tfvars; `terraform plan`, duyệt rồi apply. Apply tạo secret rỗng `vota-ha-patroni-env`.
3. Nạp giá trị secret (KEY=VALUE mỗi dòng, ký tự an toàn trong URL; **không** commit):
   ```bash
   printf 'PATRONI_SUPERUSER_PASSWORD=%s\nPATRONI_REPLICATION_PASSWORD=%s\n' "$SU" "$REPL" | gcloud secrets versions add vota-ha-patroni-env --data-file=-
   ```
   Đặt secret trước khi VM khởi động lần đầu; nếu apply trước, khởi động lại VM sau khi nạp.
4. Kiểm cụm (mục 4).

## 3. Di trú từ primary hiện tại (một lần, cửa sổ bảo trì ngắn)

> **Trạng thái:** đã thực hiện ngày 2026-10-08, cutover xong (`history/2026-10-08-phase3-di-tru-db.md`). Các bước dưới là runbook đã dùng; không chạy lại khi chưa có quyết định mới. Hiện tại: `db.vota.internal` → ILB `10.148.0.34`, primary cũ `v-ota-db-dev` đang `TERMINATED` (xem trạng thái ở cuối mục này).

Mục tiêu: dữ liệu hiện có sang cụm Patroni, primary cũ giữ nguyên làm đường quay lại. Bản clone là **một điểm thời gian**: ghi mới trên primary cũ sau lúc `pg_basebackup` KHÔNG sang cụm mới, nên toàn bộ phần từ clone đến cutover phải nằm trong cửa sổ bảo trì có dừng ghi (dữ liệu staging cỡ trăm MB, basebackup mất vài giây đến vài phút).

Chuẩn bị (ngoài cửa sổ): role `replicator` trên primary hiện tại có đúng mật khẩu như `PATRONI_REPLICATION_PASSWORD`, và `pg_hba` có `host replication replicator <ip-node-a>/32 scram-sha-256` rồi `pg_reload_conf()` (primary hiện tại đã dùng role này cho replica nên thường đã có). Có thể diễn tập cả quy trình trên cụm Patroni dùng thử trước, rồi `terraform destroy` phần đó.

Trong cửa sổ bảo trì:

1. Dừng ghi: dừng job cào (gỡ cron hoặc tắt Scheduler), đưa app về chế độ bảo trì hoặc dừng backend.
2. Đặt `patroni_clone_from_host = "<IP private primary hiện tại>"`, apply. Terraform chỉ truyền giá trị này cho node `a`; node `b` nhận chuỗi rỗng và vào cụm qua DCS sau khi node `a` có leader. Vì vậy không có hai node cùng chạy `pg_basebackup` từ primary cũ. Đường clone đã kiểm trong Docker (`ops/tests/test_patroni_clone_bootstrap.sh`). Chờ node `b` `streaming` (mục 4) và đối chiếu số dòng bảng chính giữa primary cũ và leader mới.
3. Cutover: đổi bản ghi DNS sang IP ILB (`terraform output patroni_ilb_ip`):
   ```bash
   gcloud dns record-sets update db.vota.internal. --zone vota-ha-internal --type A --ttl 30 --rrdatas <patroni_ilb_ip>
   ```
   Backend/pgbouncer mở kết nối mới sang ILB trong ~30 giây; chạy `ops/check-db-direct.sh` từ một app VM.
4. Mở lại app và job cào; theo dõi `/health/ready` của từng VM và cảnh báo.
5. **Quay lại** nếu có sự cố: cùng lệnh DNS với `--rrdatas <IP primary cũ>`. Primary cũ không bị đổi gì, nhưng ghi sau cutover nằm ở cụm mới và không tự quay về; cân nhắc trước khi mở lại ghi.
6. Sau vài ngày ổn định: xoá `patroni_clone_from_host` khỏi tfvars (node đang chạy không đổi; node dựng mới không bootstrap lại từ primary cũ), đặt `db_primary_ip` = IP ILB, nghỉ hưu primary/replica cũ.
7. Job cào dùng `db.vota.internal`: xem `docs/guide/van-hanh-crawler-db-noi-bo.md`.

### Trạng thái lần dựng/kiểm tra ngày 2026-10-08 (lịch sử)

Các gạch đầu dòng dưới đây là ảnh chụp ngày 2026-10-08, không phải trạng thái hiện tại. Trạng thái hiện tại xem bên dưới.

- Lúc đó `vota-ha-pg-b` (`10.148.0.37`, `asia-southeast1-b`) là `leader`; `vota-ha-pg-a` (`10.148.0.35`, `asia-southeast1-a`) là `sync_standby`, `streaming`; timeline `3`, replication lag `0`. Leader có thể đã đổi; kiểm bằng `patronictl list`.
- Node `b` đã được reset/rejoin theo handoff trước khi trở thành leader; node replica được giữ lại và tự vào cụm sau failover. Không reset node đang là leader trong trạng thái hiện tại.
- Mật khẩu role `replicator` trên node `a` đã được đồng bộ từ `/etc/vota/patroni.env` qua stdin; giá trị không được in ra output, argv, history hoặc tài liệu.
- ILB VIP là `10.148.0.34`; forwarding rule `vota-ha-pg-primary` chỉ coi node trả `200` ở `/primary` là healthy. Kiểm tra từ HA app VM cho thấy ILB trỏ đúng leader; việc node replica tự gọi VIP và thấy `in_recovery=true` là hairpin expected, không phải lỗi ILB.
- Đã cutover: `db.vota.internal` trỏ ILB `10.148.0.34` (xác nhận 2026-10-12 bằng `gcloud dns record-sets list --zone=vota-ha-internal`). Ghi mở trên cụm HA.
- Sau clone, checksum `md5(cdp.products)` khớp trên primary cũ, leader và replica (`history/2026-10-08-phase3-di-tru-db.md`). Ảnh chụp trước clone (`17522/157` dòng khác) đã lỗi thời.

### Trạng thái hiện tại (cập nhật 2026-10-12)

- Primary cũ `v-ota-db-dev` (`10.148.0.2`) đang `TERMINATED`, không có IP public. Không còn là đường vào DB. Trước đó nó được giữ `default_transaction_read_only = on` làm hàng rào chống split-brain.
- Replica cũ `vota-staging-db-replica` (`10.148.0.4`) cũng `TERMINATED`.
- Cụm Patroni chạy: `vota-ha-pg-a` (`10.148.0.35`), `vota-ha-pg-b` (`10.148.0.37`), `vota-ha-pg-w` (`10.148.0.36`, witness). Không có node nào có IP public. Đường vào từ laptop chưa được thiết lập (xem mục 7).
- Các tệp Terraform còn `db_primary_ip = "10.148.0.2"` (`staging-ha.tfvars`, `.example`) chưa cập nhật theo cutover. Xem mục 7.

## 4. Kiểm tra cụm

Từ một node DB (SSH qua IAP):

```bash
curl -s http://127.0.0.1:8008/cluster | python3 -m json.tool        # members: một leader, một sync_standby streaming
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8008/primary   # 200 chỉ trên leader
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8008/replica   # 200 chỉ trên replica
sudo docker exec vota-patroni /opt/patroni/bin/patronictl -c /etc/patroni list
tail -n 3 /var/log/vota/patroni-cluster.jsonl                        # "status":"ok"
```

`status` của probe: `ok` · `no_replica` (chỉ còn leader) · `no_leader` · `broken` (không hỏi được Patroni).

Khi kiểm ILB, không dùng kết quả hairpin từ một node replica làm tiêu chí leader. Kiểm từ một HA app VM hoặc máy client trong VPC, đồng thời đối chiếu `/cluster` và `:8008/primary` trên từng node.

## 5. Dựng lại replica (cảnh báo "KHÔNG CÒN REPLICA")

Cảnh báo kêu khi cụm chỉ còn leader quá 5 phút.

- Node cũ chỉ tạm tắt (VM còn, đĩa còn): khởi động VM; Patroni tự `pg_rewind` và vào lại làm replica. Theo dõi `patronictl list` tới khi `streaming`.
- Node hỏng hẳn (VM hoặc đĩa mất): Terraform tạo lại VM (và đĩa nếu cần: `terraform apply -replace='google_compute_instance.patroni["b"]'`; đĩa có `prevent_destroy`, muốn thay đĩa thì gỡ bảo vệ có chủ đích). Node mới khởi động với đĩa trống nên Patroni tự `pg_basebackup` từ leader. Không phải chạy script nào.
- Trong lúc chưa có replica: **không** thực hiện thay đổi schema hay migration lớn; xem lag và `df -h` trên leader (slot giữ WAL tối đa `max_slot_wal_keep_size = 2GB`).

### 5.1 Đồng bộ password `replicator` an toàn

Khi cần đồng bộ role trên node `a`, đọc `PATRONI_REPLICATION_PASSWORD` trực tiếp trên node từ `/etc/vota/patroni.env`, truyền qua pipe vào `psql` và không dùng `set -x`, `echo`, tham số dòng lệnh hoặc file tạm chứa secret. Ví dụ lệnh đã dùng theo mẫu sau; output của `psql` bị loại bỏ:

```bash
gcloud compute ssh vota-ha-pg-a \
  --project=vinpearl-508801 --zone=asia-southeast1-a \
  --tunnel-through-iap \
  --command='set -euo pipefail
sudo awk -F= '\''$1 == "PATRONI_REPLICATION_PASSWORD" {sub(/^[^=]*=/, ""); print; exit}'\'' \
  /etc/vota/patroni.env |
sudo docker exec -i -u postgres vota-patroni sh -ceu '\''
  IFS= read -r REPL_PASSWORD
  test -n "$REPL_PASSWORD"
  printf "\\password replicator\\n%s\\n%s\\n\\\\q\\n" "$REPL_PASSWORD" "$REPL_PASSWORD" |
    psql -X -v ON_ERROR_STOP=1 -d postgres >/dev/null
'\'''
```

Chỉ xác minh trạng thái, không in hash hay `rolpassword`:

```bash
gcloud compute ssh vota-ha-pg-a \
  --project=vinpearl-508801 --zone=asia-southeast1-a \
  --tunnel-through-iap \
  --command='sudo docker exec -u postgres vota-patroni psql -X -At -d postgres -c "select rolname, rolcanlogin, rolreplication, rolpassword is not null from pg_authid where rolname = '\''replicator'\'';"'
```

### 5.2 Reset/rejoin node

Chỉ reset node đã xác nhận là replica hoặc node không giữ leader lock. Trước khi reset phải xem `patronictl list` và `/cluster`; nếu node đang là leader thì dừng thao tác và dùng switchover có kiểm soát trong cửa sổ riêng. Mẫu lệnh reset node `b` đã dùng trong lần triển khai:

```bash
gcloud compute instances reset vota-ha-pg-b \
  --zone=asia-southeast1-b \
  --project=vinpearl-508801 \
  --quiet
```

Sau reset, chờ node tự rejoin, không chạy `pg_basebackup` thủ công nếu đĩa còn `PG_VERSION`:

```bash
gcloud compute ssh vota-ha-pg-b \
  --project=vinpearl-508801 --zone=asia-southeast1-b \
  --tunnel-through-iap \
  --command='sudo docker exec vota-patroni /opt/patroni/bin/patronictl -c /etc/patroni list'
```

Thay thành viên etcd (witness hỏng): với etcd 3 thành viên, mất 1 vẫn đủ đa số; dựng lại VM witness với cùng IP (địa chỉ tĩnh) và `--initial-cluster-state existing` cần xoá thành viên cũ bằng `etcdctl member remove` rồi `member add`; làm tuần tự, từng thành viên một.

## 6. Sự cố

| Triệu chứng | Nguyên nhân thường gặp | Xử lý |
|---|---|---|
| Cảnh báo "KHÔNG CÓ LEADER" > 2 phút | Mất đa số etcd (2/3), hoặc Patroni của cả hai node chết | `docker logs vota-patroni` và `vota-etcd` ở cả hai node; kiểm firewall `*-pg-peers` (2379/2380/8008/5432) |
| ILB không có backend healthy | Không node nào trả 200 ở `/primary` (không có leader) hoặc firewall health check | `curl :8008/primary` từng node; rule `*-pg-health` mở 130.211.0.0/22, 35.191.0.0/16 cho 8008 |
| Cả hai node đều tự cho là leader | Không thể xảy ra khi etcd còn đa số (khoá DCS); nếu thấy, dừng ngay node nghi ngờ và báo | `patronictl list`, dừng `vota-patroni` ở node không có khoá |
| Ghi bị chặn sau khi mất replica | `synchronous_mode_strict` đang là `false` nên không chặn; nếu bị chặn là cấu hình đã đổi | `patronictl show-config` |
| Failover chậm hơn dự kiến | `ttl` 30 giây là cận trên chờ khoá hết hạn | Đo bằng `ops/tests/test_patroni_failover.sh` rồi chỉnh `ttl/loop_wait` trong `ops/patroni/patroni.yml` (không dưới `loop_wait + 2*retry_timeout`) |

## 7. Giới hạn đã biết

- Failover thật trên GCP đã thành công, nhưng thiếu timestamp start/end đủ tin cậy nên chưa công bố RTO chính xác; 28 giây chỉ là kết quả Docker tham chiếu.
- Bản clone lúc di trú là điểm thời gian: xem mục 3.
- Điểm dữ liệu chỉ có tại thời điểm clone (2026-10-08): checksum `cdp.products` khớp sau clone. Muốn đối chiếu lại, phải dùng `SEED_DATABASE_URL` hoặc tương đương trên một node; không có primary cũ để so sánh nữa.
- Ghi vào `db.vota.internal` đang đi vào cụm HA. Không đưa DNS về `10.148.0.2`: máy đó đã dừng. Quay lại cần quyết định mới (mục 3, bước 5).
- Đồng bộ không nghiêm ngặt: khi mất replica rồi mất nốt leader trong khoảng đó, ghi sau thời điểm mất replica có thể mất. Probe và cảnh báo "không còn replica" là lớp bảo vệ cho khoảng này.
- Cập nhật image Patroni: thay `patroni_image` rồi khởi động lại từng VM, **replica trước**, chờ `streaming`, rồi `patronictl switchover` sang node đã cập nhật và cập nhật node còn lại.
