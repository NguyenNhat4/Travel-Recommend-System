# Kế hoạch: chịu mất zone, DB tự failover, job cào độc lập, rolling update an toàn

- Ngày: 2026-10-07
- Nhánh: `khoa/ha-multizone-patroni-crawler`
- Phục vụ: NFR-REL-02 (toàn vẹn giao dịch: đơn giữ chỗ 30 phút, bù trừ khi lỗi hệ thống) và NFR-PERF-01 (độ trễ search/API) trong `docs/prd/requirements.md`. PRD **không có** mã NFR cho HA, zone hay failover.
- **Ghi chú quy trình:** phần hạ tầng này đã được người dùng chốt ngày 2026-10-08 và đề xuất `docs/prd/update-archive/2026-10-08-staging-ha-patroni.md` đã được áp dụng vào `docs/prd/deployment-plan.md`. Root/state `staging-ha` tách khỏi `infra/staging`; không sửa workflow CI/CD hiện hữu trong phạm vi triển khai này. Riêng phần backend (readiness chế độ mất-DB) đổi hành vi `/health/ready` khi bật cờ HA; mặc định tắt nên một VM chạy như cũ.
- Nối tiếp: `docs/plan/2026-10-05-ha-load-balancing.md` (các use case ở đó vẫn đúng; mục 5 của nó nay trỏ về đây).

Quy ước (§3b của plan trước): mỗi vấn đề có một use case có số liệu, hậu quả **đã kiểm trong code** (hoặc ghi rõ chưa kiểm), và hành vi sau khi sửa. Trạng thái runtime GCP trong phần DB HA dưới đây được kiểm ngày 2026-10-08; các mục chưa chạy vẫn được ghi rõ, không suy diễn từ kết quả Docker.

## 1. Tóm tắt

| # | Vấn đề | Cách sửa | Trạng thái |
|---|---|---|---|
| 1 | Replica cùng zone với primary | `db_replica_zone` (khác `zone`, validation chặn trùng); script CI/promote nhận zone riêng cho replica | Code + validate xong; chưa apply (đổi zone = thay VM replica, CI chặn trừ khi `allow_destroy`) |
| 2 | Failover do người quyết định, RTO 10–30 phút | Patroni 2 node + witness etcd 3 zone + ILB nội bộ trỏ leader (`patroni.tf`, `ops/patroni/`) | Failover thật trên GCP đã thành công; chưa có timestamp đủ tin cậy để công bố RTO; Docker vẫn có bằng chứng 28 giây |
| 3 | Sau failover chỉ còn một DB | Patroni tự đưa node cũ vào lại; probe + cảnh báo "KHÔNG CÒN REPLICA"; runbook dựng lại replica | Node cũ đã reset/rejoin và trở lại `sync_standby`/`streaming`, lag `0`; cảnh báo GCP chưa kiểm |
| 4 | Crawler: VM cũ, tunnel IP cố định, không khoá chống chồng | `db.vota.internal`, advisory lock DB, `catalog.freshness` + 3 cảnh báo; crawler vẫn chạy cron trên VM | Khoá kiểm trên Postgres thật; cảnh báo chưa kiểm trên GCP |
| 5 | `READY_REQUIRES_DB` loại mọi VM khi DB chết toàn cục | Sổ "VM nào còn DB" trong Redis: mất một mình thì loại, mất tất cả thì giữ lại (`mode: db_outage`) | 9 test đơn vị; LB thật chưa kiểm |
| 5.1 | Rolling update không chờ VM ready | `min_ready_sec = boot_to_ready_seconds (360)`; kịch bản diễn tập `ha-rolling-update-drill.sh` | `terraform validate` pass; diễn tập chưa chạy |
| 5.2 | Mất 1 VM đẩy VM còn lại lên 120% | `min_replicas = 3`, `cpu_target 0.55`, `memory 60`, validation công thức (N−1)/N | Xong, test cấu trúc pass |
| 5.3 | Cooldown 180s < boot 360s | `cooldown_period = boot_to_ready_seconds` | Xong; số 360 chưa đo trên GCP |
| 5.4 | SSE 90s bị cắt khi scale-in | Chuỗi 90 ≤ draining 100 ≤ stop_grace 110, uvicorn graceful 100 | Xong, test cấu trúc pass; stream thật chưa thử |

### 1.1 Kết quả xác minh staging-ha ngày 2026-10-08

Các kiểm tra dưới đây chỉ đọc trạng thái của root/state `infra/terraform/environments/staging-ha` và các tài nguyên có tiền tố `vota-ha`; không chạy root `infra/terraform/environments/staging`.

| Hạng mục | Bằng chứng hiện tại | Kết quả |
|---|---|---|
| Terraform state/config | `terraform plan -input=false -var-file=staging-ha.tfvars` | `No changes. Your infrastructure matches the configuration.` |
| Cụm Patroni | `vota-ha-pg-a` ở `10.148.0.35` là `sync_standby`, `streaming`; `vota-ha-pg-b` ở `10.148.0.37` là `leader`; witness `vota-ha-pg-w` ở zone thứ ba | Một leader, một replica đồng bộ, timeline `3` |
| Replication | Kiểm tra trạng thái Patroni/PostgreSQL sau reset/rejoin | Replication lag `0`; node `a` đã trở lại cụm |
| ILB | VIP `10.148.0.34`, forwarding rule `vota-ha-pg-primary`, health check `:8008/primary` | Backend leader `b` healthy; replica `a` unhealthy theo thiết kế leader-only |
| App HA | Backend service `vota-ha-app` và MIG `vota-ha-app` | 3/3 VM healthy; không restart hoặc thay đổi app staging cũ |
| Failover thật | Leader đã chuyển sang node `b`, node `a` quay lại làm replica | Thành công; chưa đủ mốc thời gian để công bố RTO chính xác trên GCP |
| Dữ liệu | Đối chiếu `cdp.products` giữa primary cũ và leader HA | `old_rows=17679`, `ha_rows=17679`, `same=17522`, `different=157`, không thiếu dòng ở phía nào; hash `cdp.profiles` và `catalog.combo_items` khớp |
| DNS/ghi | `db.vota.internal` vẫn trỏ `10.148.0.2`, primary staging cũ | Chưa cutover DNS, chưa mở ghi vào HA |

Vì clone/đồng bộ được thực hiện theo một điểm thời gian và staging cũ vẫn có thể phát sinh ghi, do đó 157 dòng sản phẩm chưa khớp hoàn toàn, mà chưa được phép cutover DNS hoặc mở ghi vào HA. Hairpin từ node `a` vào ILB trả `in_recovery=true` là hành vi mong đợi vì node này là replica; tiêu chí nghiệm thu ILB được kiểm từ các HA app VM và health check leader-only.

## 2. DB: đa zone và tự failover

### Kiến trúc đích

```
zone a: vota-ha-pg-a  (Patroni+Postgres, etcd)  \
zone b: vota-ha-pg-b  (Patroni+Postgres, etcd)   >  ILB nội bộ :5432 -- health check :8008/primary (chỉ leader 200)
zone c: vota-ha-pg-w  (chỉ etcd, witness)       /      ^
                                                       db.vota.internal (private DNS) -> IP của ILB
```

- Hai node DB ở **hai zone khác nhau**; witness etcd ở zone thứ ba để mất một zone vẫn còn 2/3 thành viên etcd (đủ đa số cho Patroni bầu leader).
- `synchronous_mode: true` (không nghiêm ngặt): bình thường mọi commit đã nằm ở replica zone khác (RPO 0); mất replica thì leader tự hạ về bất đồng bộ thay vì chặn ghi.
- `ttl 30 / loop_wait 10 / retry_timeout 10`, `use_pg_rewind: true`, `maximum_lag_on_failover 1 MiB`.
- Node bị hạ cấp hoặc cô lập không giữ kết nối cũ (`connection_persistence_on_unhealthy_backends = NEVER_PERSIST`), kẻo client nối nhầm vào primary cũ.
- Đĩa dữ liệu riêng cho mỗi node (`prevent_destroy`, snapshot hằng ngày 03:00 giờ Việt Nam): thay VM không mất dữ liệu.
- Tắt mặc định (`create_patroni = false`), nên merge không đổi gì cho tới khi người dùng bật.

### Use case 1 — replica cùng zone: mất zone là mất cả hai

Tình huống: staging có primary `vota-staging-db` và replica `vota-staging-db-replica`, **cả hai ở `asia-southeast1-a`**. 10:20 zone a gián đoạn. Hai VM DB đều mất. Ba app VM ở zone a/b/c còn chạy nhưng mọi lượt đăng nhập, đặt chỗ, thanh toán (đơn khách sạn Vinpearl Phú Quốc 12 triệu đang ở `PENDING_PAYMENT`) trả lỗi. Cách phục hồi duy nhất là dựng DB từ snapshot đĩa hằng ngày: mất tối đa ~24 giờ ghi (đơn, thanh toán).
Đã kiểm trong code: `staging/main.tf` đặt replica ở `var.zone`, tức cùng zone primary; `ops/ci-db-replication.sh` dùng một `GCE_ZONE` cho cả hai VM.
Sau khi sửa: `db_replica_zone` mặc định `asia-southeast1-b`, validation `db_replica_zone != zone`; `ci-db-replication.sh` và `promote-db-replica.sh` nhận `GCE_REPLICA_ZONE`/`REPLICA_ZONE`; workflow truyền `vars.GCE_DB_REPLICA_ZONE`. Mất zone a thì replica ở b còn nguyên. Cụm Patroni đặt hai node ở hai zone ngay từ validation.
Chưa kiểm: replica hiện có vẫn ở zone a; đổi sang zone b là **thay VM** nên CI chặn, cần chạy workflow với `allow_destroy=true` rồi job replication dựng lại bằng `pg_basebackup` (primary không bị đụng).

### Use case 2 — failover do người, RTO 10–30 phút so với giữ chỗ 30 phút

Tình huống: 02:12 khách bắt đầu thanh toán đơn 12 triệu (giữ chỗ 30 phút, `booking_hold_minutes ≥ 30` trong `config.py`). 02:14 primary chết. Cảnh báo đến 02:19; người trực mở máy, đọc runbook, chạy `ops/promote-db-replica.sh --yes` lúc 02:35–02:50. DB mất 21–36 phút, tức **70–120%** thời gian giữ chỗ của đơn tạo ngay trước sự cố; webhook Stripe và job đối soát chỉ tiếp tục sau đó.
Đã kiểm: script chạy được trên cặp primary/replica thật trong Docker, mất 3 giây (`ops/tests/test_promote_db_replica.sh`); thời gian còn lại là thời gian người. Không có tự động.
Sau khi sửa (Patroni): leader chết, khoá DCS hết hạn tối đa `ttl = 30s`, replica đồng bộ tự nâng, ILB thấy `/primary` 200 trên node mới sau ~10 giây (2 lần kiểm × 5 giây). **Đo trong Docker (`ops/tests/test_patroni_failover.sh`, `docker kill` leader): `/primary` 200 trên node mới sau 28 giây, không mất dòng nào, node cũ khởi động lại tự vào làm replica.** Failover thật trên GCP đã thành công: node `b` là leader, node `a` quay lại `sync_standby`/`streaming`, ILB healthy ở node `b`, không cần đổi env hoặc DNS. Chưa có timestamp start/end đủ tin cậy để công bố RTO GCP, nên không dùng ước tính 45–60 giây làm số liệu nghiệm thu.
Chưa kiểm: RTO GCP có timestamp chính xác, cảnh báo khi mất cả etcd đa số và rolling-update drill dưới tải.

### Use case 3 — script chỉ promote: sau failover hệ thống là một DB đơn lẻ

Tình huống: 03:12 zone a mất, người trực chạy `promote-db-replica.sh` lúc 03:40. Từ đó `vota-staging-db-replica` (zone b) là DB duy nhất. Không ai dựng replica mới vì script chỉ in "việc còn lại" ở cuối và primary cũ không vào lại được nếu không `pg_rewind` hoặc dựng lại. 09:05 đĩa của node b lỗi: mất toàn bộ ghi từ 03:12 đến 09:05 (khoảng 6 giờ đơn hàng và thanh toán), trong khi snapshot gần nhất là 03:00.
Đã kiểm: `promote-db-replica.sh` không tạo VM, không gọi bootstrap replica; không có cảnh báo nào kêu khi chỉ còn một DB (alert replication chỉ nhìn VM replica đã chết, vắng mặt).
Sau khi sửa:
- Patroni: node cũ khi quay lại tự `pg_rewind` (hoặc basebackup lại) và thành replica; **đã kiểm trong Docker**. `cluster_probe.py` mỗi phút báo `ok` / `no_replica` / `no_leader` / `broken`; trong test failover probe chuyển `ok → no_replica` ngay khi chỉ còn leader mới và `ok` lại khi node cũ vào lại. Cảnh báo "KHÔNG CÒN REPLICA" kêu sau 5 phút (`patroni_monitoring.tf`), để Patroni có thời gian tự phục hồi trước khi gọi người.
- Đường cũ (không Patroni): `promote-db-replica.sh` in khung cảnh báo "HỆ THỐNG KHÔNG CÒN REPLICA" kèm các bước dựng replica ở zone khác; runbook ở `docs/guide/van-hanh-db-replica.md` §6.1.
Chưa kiểm: cảnh báo log-based chạy trên GCP (tên trường `jsonPayload` sau `parse_json` của Ops Agent).

### Di trú sang Patroni (một lần)

`docs/guide/van-hanh-db-patroni.md` §3: dựng cụm với `patroni_clone_from_host` = IP primary hiện tại (node đầu `pg_basebackup` từ primary, `ops/tests/test_patroni_clone_bootstrap.sh` đã kiểm đường này trong Docker); cửa sổ bảo trì ngắn để đổi `db.vota.internal` sang IP ILB; primary cũ giữ nguyên làm đường quay lại.

## 3. Readiness: một VM mất DB so với mọi VM mất DB

### Use case 5 — DB chết toàn cục

Tình huống: 3 VM × 2 worker. 14:00 primary chết, failover xong sau ~3 phút (đường cũ: dài hơn). Một khách tìm "Vinpearl Phú Quốc", một khách khác đăng nhập.
Trước khi sửa (đã kiểm trong `main.py`): `READY_REQUIRES_DB=true` → `SELECT 1` hỏng ở cả 3 VM → cả 3 trả 503 ở `/health/ready` → LB không còn backend sẵn sàng. Tài liệu GCP nói LB ứng dụng ngoài khi không chọn được backend trả 502 `failed_to_pick_backend`, tức catalog và search cũng sập dù không cần DB. Chưa kiểm: LB thật trả 502 hay fail-open; và việc `/search` thật sự chạy được khi DB chết (nhánh degraded chưa merge, search log ghi vào DB).
Ngược lại, nếu chỉ pgbouncer của VM #2 chết thì VM #2 **phải** bị loại, nếu không 1/3 lượt đăng nhập lỗi.
Sau khi sửa: mỗi VM ghi dấu "DB ổn" (thời điểm) vào sorted set Redis `vota:ready:db_ok`; VM tự thấy DB hỏng thì **xoá dấu của mình trước**, rồi đếm dấu còn mới của VM khác. Còn VM khác ổn → VM này bị loại (503). Không còn VM nào (hoặc Redis không đọc được) → coi là mất toàn cục, giữ 200 với `mode: "db_outage"`, `db: false`. Tính chất: hai VM hỏng cùng lúc không thể cùng bị loại (VM hỏng sau cùng luôn thấy 0). Đã kiểm bằng `src/backend/tests/unit/api/test_db_outage_readiness.py` (9 test, gồm: mất một mình bị loại, mất tất cả giữ lại, hỏng lần lượt không bao giờ cả 3 cùng 503, dấu hết hạn, Redis chết, hồi phục).
Đánh đổi chấp nhận: Redis chết cùng lúc một VM hỏng cục bộ thì VM đó vẫn ở trong LB và trả `DATABASE_UNAVAILABLE` cho ~1/3 lượt cần DB; chọn vậy vì loại hết là kết cục tệ hơn.
**Quyết định chung với nhánh `khoa/backend-db-unavailable-degraded` (commit `d5452fc`, chưa merge):** nhánh đó làm `/health/ready` luôn 200 khi app đã sẵn sàng và thêm trường `database`, còn đường cần DB trả 503 `DATABASE_UNAVAILABLE`. Hai thay đổi bổ sung nhau nhưng đụng cùng hàm `health_ready` và cùng file `db_probe.py` (nhánh đó thêm `DatabaseProbe` khác tên phương thức). Khi merge: giữ cờ `READY_REQUIRES_DB` làm công tắc (tắt = hành vi của nhánh degraded, bật = loại VM mất DB một mình), dùng `DbPeerRegistry` ở đây để phân biệt, giữ `DATABASE_UNAVAILABLE` cho đường cần DB, và rebase nhánh đó lên nhánh này. Chưa merge nên mặc định không đổi.

## 4. Crawler

### Use case 4 — VM staging cũ là điểm chết duy nhất, ghi lỗi âm thầm, tick chồng

Tình huống: job cào `fresh-run tick` mỗi 15 phút trên VM staging cũ, nối DB `127.0.0.1:15432` qua đường hầm SSH tới IP cố định; lượt full 02:00 chạy 3 giờ.
(1) 22:00 VM chết: không ai cào; catalog (11.387 sản phẩm theo snapshot 2026-09-23) cũ dần. Cảnh báo SLA trong monitor (`sla.maxCatalogAgeHours`, 48 giờ) chỉ ghi file `alerts.jsonl` trên chính VM đã chết.
(2) 02:30 primary failover sang replica: đường hầm vẫn trỏ IP cũ, nạp DB lỗi. **Đã kiểm, và sửa lại nhận định ban đầu "ghi lỗi âm thầm":** trên VM cũ lỗi này không hoàn toàn âm thầm, vì `infra/monitoring/main.tf` có cảnh báo "crawler failed" (container thoát khác 0 hoặc OOM) và "crawler partial run" (`exit_code=3`). Điểm yếu thật là (a) cả hai cảnh báo chỉ lọc `resource.type="gce_instance"` + nhãn của docker event watcher trên VM đó, nên chuyển job sang nơi khác ngoài VM đó là mất cả hai; (b) tick rảnh không chạm DB, nên đường hầm hỏng chỉ lộ ra ở lượt cào kế tiếp (có thể nhiều giờ sau), không phải lúc failover.
(3) 02:15 tick thứ hai vào lúc lượt full còn chạy: trên cùng VM, khoá tệp `fresh_catalog.lock` chặn được (đã kiểm `lock_busy`). Nếu hai tick chạy ở hai máy/container khác nhau (ví dụ chạy tay trên máy khác trong lúc cron chạy), khoá tệp không thấy nhau, hai bên cùng cào Trip/Booking và cùng nạp DB (giao dịch nạp vẫn tuần tự nhờ `pg_advisory_xact_lock(7791024)` nên không hỏng dữ liệu, chỉ gấp đôi lượt cào và nguy cơ bị chặn IP).
Sau khi sửa:
- `CLOUD_SEED_DATABASE_URL` mẫu dùng `db.vota.internal:5432` (không còn tunnel), theo leader sau failover.
- `catalog_run_lock.py`: `pg_try_advisory_lock(7791025)` giữ suốt lượt bằng một kết nối riêng; tick đến sau thoát với `catalog.lock.busy scope=database`. **Đã kiểm trên Postgres thật** (`CATALOG_TEST_DATABASE_URL`): holder thứ hai bị từ chối cho tới khi holder đầu chết thì nhận được. Failover làm mất khoá (kết nối đứt); khi đó giao dịch nạp vẫn tuần tự nhờ khoá giao dịch, nên chỉ rủi ro cào đôi.
- Mỗi tick phát `catalog.freshness` (`state`, `age_hours`); `crawler_monitoring.tf` có ba cảnh báo độc lập với nơi chạy job: **job cào không chạy** (vắng dòng này 60 phút), **catalog không đổi quá hạn** (`state=late`) và **lượt cào thất bại** (`run.end status=failed`, thay cho cảnh báo chỉ nhìn container VM). "X giờ" là `sla.maxCatalogAgeHours` của job (48 mặc định, nên hạ theo chu kỳ thật); cảnh báo vắng mặt của GCP tối đa 23,5 giờ nên không đặt trực tiếp "không có lượt thành công quá X giờ" ở Terraform.
Đã bỏ phương án Cloud Run Job theo yêu cầu (2026-10-07); crawler tiếp tục chạy cron trên VM. Chưa kiểm: cảnh báo trên GCP. VM cron vẫn là điểm chết duy nhất của việc làm mới dữ liệu, giờ có cảnh báo `JOB CÀO KHÔNG CHẠY` thay vì im lặng.

## 5. Autoscaler, MIG và tắt êm

### 5.1 Rolling update không chờ VM ready
Tình huống: đổi image backend khi 3 VM đang nhận tải k6 150 VU. MIG chỉ có health check **liveness** (`/health/live`, 60 giây, không gồm RecSys/DB) và không có `min_ready_sec`, nên MIG coi VM mới "đã cập nhật" ngay khi tiến trình trả lời (~1–2 phút), trước khi nạp xong RecSys (boot-to-ready ước tính 4–6 phút). Với `max_surge 3`, `max_unavailable 0`, MIG xoá VM cũ lúc ~3 phút (cộng draining 60s) trong khi VM mới ready lúc ~6 phút: khoảng 3 phút không còn backend ready, tức 5xx kéo dài. Plan 2026-10-05 §5 từng khẳng định "không có 5xx kéo dài" nhưng chưa kiểm.
Sau khi sửa: `update_policy.min_ready_sec = boot_to_ready_seconds` (mặc định 360, validation `>= 360`); resource MIG dùng `google-beta` vì `min_ready_sec` chưa có ở `google` 6.50 (kiểm schema). Kiểm bằng `ops/loadtest/ha-rolling-update-drill.sh --yes`: k6 + `rolling-action replace`, lấy mẫu số backend HEALTHY mỗi 10 giây, đạt khi không xuống dưới `MIN_HEALTHY` và k6 qua ngưỡng. **Chưa chạy** (không có k6/GCP ở máy này).

### 5.2 Mất 1 VM làm VM còn lại quá tải
Tình huống: `min_replicas = 2`, `cpu_target = 0.6`. Hai VM cùng 60%; một VM mất zone, VM còn lại nhận 60% × 2 = **120%** CPU trong ~5 phút tới khi VM thay thế ready: request xếp hàng, p95 vượt 800 ms, 5xx.
Công thức: sống sót khi mất 1 trong N VM thì mức dùng ổn định phải ≤ (N−1)/N. Sau khi sửa: `min_replicas = 3` (một VM mỗi zone), `cpu_target = 0.55` (mất 1 VM → 82,5% trên hai VM còn lại), `memory_target_percent = 60`; **validation Terraform ép công thức** (đổi giá trị vi phạm là plan lỗi). Chi phí: thêm một `e2-standard-2`. Chưa kiểm: RSS thật của backend (bộ nhớ ít phụ thuộc tải hơn CPU nên 60% là bảo thủ, cần đo).

### 5.3 Cooldown ngắn hơn thời gian boot
`cooldown_period = 180s` trong khi VM cần ~360s mới ready: autoscaler tính cả CPU lúc nạp model (cao, chưa nhận traffic) vào trung bình, có thể thêm VM quá tay. Sau khi sửa: `cooldown_period = boot_to_ready_seconds` (360) cùng biến với `min_ready_sec` và `initial_delay_sec`. **Số 360 chưa đo**: sau lần apply đầu đo thời gian từ lúc tạo VM đến log `startup.recsys.ready` rồi chỉnh biến.

### 5.4 SSE trợ lý bị cắt khi rút VM
Tình huống: khách bắt đầu stream lịch trình Phú Quốc 4 ngày (tối đa 90 giây, `ITINERARY_REQUEST_TIMEOUT_SECONDS`) lúc 10:00:00; 10:00:05 autoscaler scale-in rút đúng VM đó. Draining LB 60s, `stop_grace_period` 40s, uvicorn graceful 30s: stream bị ngắt sau tối đa ~60 giây trong khi cần 90 (cắt 30 giây cuối, lịch trình dở dang).
Sau khi sửa: chuỗi **90 ≤ draining 100 ≤ stop_grace 110**; uvicorn graceful 100 (đọc từ `UVICORN_TIMEOUT_GRACEFUL_SHUTDOWN`; image trước đây hard-code 30); frontend (proxy SSE) cũng 110. Mọi giá trị suy ra từ một biến `lb_connection_draining_seconds` có validation `>= sse_max_seconds`. Chưa kiểm stream thật khi scale-in; phương án dự phòng (client tự nối lại với `run.failed` kèm retry) **chưa làm**, nằm ngoài thay đổi này.

## 6. Kiểm chứng và điều kiện trước khi apply

Đã chạy và ghi nhận trong lần xác minh ngày 2026-10-08: test Patroni trên Docker (failover + clone), probe, khoá DB trên Postgres thật, test backend, test cấu trúc Terraform; trên GCP `staging-ha` đã kiểm tra cụm Patroni, replication, ILB, app MIG/backend health, failover thật và đối chiếu dữ liệu. Terraform plan read-only sau triển khai trả `No changes. Your infrastructure matches the configuration.`

Kết quả DB HA trên GCP: `vota-ha-pg-b` là leader, `vota-ha-pg-a` là `sync_standby`/`streaming`, lag `0`, timeline `3`; ILB VIP là `10.148.0.34` và backend leader healthy. Failover đã thành công nhưng chưa có timestamp đủ tin cậy để công bố RTO chính xác. Dữ liệu `cdp.products` có `17.679` dòng ở cả hai phía, `17.522` dòng khớp và `157` dòng khác; không thiếu dòng ở phía nào. Hash `cdp.profiles` và `catalog.combo_items` khớp.

Chưa chạy hoặc chưa đủ bằng chứng để chốt: rolling-update drill dưới tải, scale-in SSE thật, cảnh báo GCP/Ops Agent, và RTO có timestamp chính xác. Không thực hiện DNS cutover: `db.vota.internal` vẫn trỏ primary staging cũ `10.148.0.2`, chưa mở ghi vào HA. Vì clone/đồng bộ là một điểm thời gian và 157 dòng sản phẩm còn khác, không được mở ghi hoặc cutover cho tới khi có quyết định xử lý chênh lệch dữ liệu.

Thứ tự đề nghị:
1. Xử lý chênh lệch `cdp.products` và xác nhận một điểm dữ liệu chung trước khi cho phép cutover; tiếp tục giữ DNS và ghi ở staging cũ.
2. Nếu cần bổ sung bằng chứng SLO, chạy `ha-rolling-update-drill.sh`, scale-in SSE và kiểm alert trong một cửa sổ riêng; không thực hiện chung với cutover DB.
3. Ghi lại timestamp start/end của một lần failover GCP trong lần diễn tập tiếp theo nếu cần công bố RTO.
4. Chỉ sau khi dữ liệu đạt tiêu chí và được phê duyệt riêng mới đổi URL crawler/app sang `db.vota.internal` (ILB) và mở ghi.
5. Quyết định merge nhánh degraded (mục 3).
