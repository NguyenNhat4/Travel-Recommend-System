# Vận hành cụm DB Patroni (staging HA)

Kế hoạch và use case: `docs/plan/2026-10-07-ha-vung-crawler-rolling.md` §2. Nếu lệch PRD, contract hoặc `AGENTS.md` thì các nguồn đó thắng. Cụm tắt mặc định (`create_patroni = false` trong `infra/terraform/environments/staging-ha`).

## 1. Cụm gồm gì

| Node | Zone | Chạy | Vai trò |
|---|---|---|---|
| `vota-ha-pg-a` | zone đầu của `patroni_zones` | etcd + Patroni + Postgres | leader hoặc replica |
| `vota-ha-pg-b` | zone thứ hai (KHÁC zone a) | etcd + Patroni + Postgres | replica đồng bộ hoặc leader |
| `vota-ha-pg-w` | `patroni_witness_zone` (khác cả hai) | etcd | đa số thứ ba, không giữ dữ liệu |

Backend, crawler nối `db.vota.internal:5432` = IP ILB nội bộ; ILB chỉ gửi tới node trả 200 ở `:8008/primary`. Failover không đổi DNS, env hay VM app.

Số liệu: leader chết → khoá hết hạn tối đa 30 giây → replica đồng bộ tự nâng → ILB đổi hướng sau ~10 giây. Đo trong Docker: 28 giây. Chưa đo trên GCP.

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

Mục tiêu: dữ liệu hiện có sang cụm Patroni, primary cũ giữ nguyên làm đường quay lại. Bản clone là **một điểm thời gian**: ghi mới trên primary cũ sau lúc `pg_basebackup` KHÔNG sang cụm mới, nên toàn bộ phần từ clone đến cutover phải nằm trong cửa sổ bảo trì có dừng ghi (dữ liệu staging cỡ trăm MB, basebackup mất vài giây đến vài phút).

Chuẩn bị (ngoài cửa sổ): role `replicator` trên primary hiện tại có đúng mật khẩu như `PATRONI_REPLICATION_PASSWORD`, và `pg_hba` có `host replication replicator <ip-node-a>/32 scram-sha-256` rồi `pg_reload_conf()` (primary hiện tại đã dùng role này cho replica nên thường đã có). Có thể diễn tập cả quy trình trên cụm Patroni dùng thử trước, rồi `terraform destroy` phần đó.

Trong cửa sổ bảo trì:

1. Dừng ghi: dừng job cào (gỡ cron hoặc tắt Scheduler), đưa app về chế độ bảo trì hoặc dừng backend.
2. Đặt `patroni_clone_from_host = "<IP private primary hiện tại>"`, apply. Node a `pg_basebackup` từ primary rồi thành leader; node b vào làm replica. Đường này đã kiểm trong Docker (`ops/tests/test_patroni_clone_bootstrap.sh`). Chờ node b `streaming` (mục 4) và đối chiếu số dòng bảng chính giữa primary cũ và leader mới.
3. Cutover: đổi bản ghi DNS sang IP ILB (`terraform output patroni_ilb_ip`):
   ```bash
   gcloud dns record-sets update db.vota.internal. --zone vota-ha-internal --type A --ttl 30 --rrdatas <patroni_ilb_ip>
   ```
   Backend/pgbouncer mở kết nối mới sang ILB trong ~30 giây; chạy `ops/check-db-direct.sh` từ một app VM.
4. Mở lại app và job cào; theo dõi `/health/ready` của từng VM và cảnh báo.
5. **Quay lại** nếu có sự cố: cùng lệnh DNS với `--rrdatas <IP primary cũ>`. Primary cũ không bị đổi gì, nhưng ghi sau cutover nằm ở cụm mới và không tự quay về; cân nhắc trước khi mở lại ghi.
6. Sau vài ngày ổn định: xoá `patroni_clone_from_host` khỏi tfvars (node đang chạy không đổi; node dựng mới không bootstrap lại từ primary cũ), đặt `db_primary_ip` = IP ILB, nghỉ hưu primary/replica cũ.
7. Job cào dùng `db.vota.internal`: xem `docs/guide/van-hanh-crawler-db-noi-bo.md`.

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

## 5. Dựng lại replica (cảnh báo "KHÔNG CÒN REPLICA")

Cảnh báo kêu khi cụm chỉ còn leader quá 5 phút.

- Node cũ chỉ tạm tắt (VM còn, đĩa còn): khởi động VM; Patroni tự `pg_rewind` và vào lại làm replica. Theo dõi `patronictl list` tới khi `streaming`.
- Node hỏng hẳn (VM hoặc đĩa mất): Terraform tạo lại VM (và đĩa nếu cần: `terraform apply -replace='google_compute_instance.patroni["b"]'`; đĩa có `prevent_destroy`, muốn thay đĩa thì gỡ bảo vệ có chủ đích). Node mới khởi động với đĩa trống nên Patroni tự `pg_basebackup` từ leader. Không phải chạy script nào.
- Trong lúc chưa có replica: **không** thực hiện thay đổi schema hay migration lớn; xem lag và `df -h` trên leader (slot giữ WAL tối đa `max_slot_wal_keep_size = 2GB`).

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

- Chưa dựng trên GCP: số liệu thời gian là từ Docker (28 giây) và ước tính; sau lần dựng đầu, chạy một lần failover thật (`gcloud compute instances stop vota-ha-pg-a`) và ghi kết quả vào `history/`.
- Bản clone lúc di trú là điểm thời gian: xem mục 3.
- Đồng bộ không nghiêm ngặt: khi mất replica rồi mất nốt leader trong khoảng đó, ghi sau thời điểm mất replica có thể mất. Probe và cảnh báo "không còn replica" là lớp bảo vệ cho khoảng này.
- Cập nhật image Patroni: thay `patroni_image` rồi khởi động lại từng VM, **replica trước**, chờ `streaming`, rồi `patronictl switchover` sang node đã cập nhật và cập nhật node còn lại.
