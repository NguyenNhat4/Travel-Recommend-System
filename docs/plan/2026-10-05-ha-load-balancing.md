# Kế hoạch: High availability, phân tải và cân bằng CPU/RAM

- Ngày: 2026-10-05
- Nhánh: `khoa/ha-load-balancing`
- Phục vụ: NFR về độ sẵn sàng và hiệu năng trong `docs/prd/requirements.md` (đối chiếu mã NFR-REL/NFR-PERF khi nghiệm thu).
- **Ghi chú quy trình:** PRD chưa mô tả HA/LB/autoscaling cho staging. Theo yêu cầu của người dùng (2026-10-05), kế hoạch này được làm **không qua đề xuất `docs/prd/update/`**. Nếu cần PRD khớp, tạo đề xuất sau.

## 1. Hiện trạng (đã kiểm trong repo)

| Thành phần | Hiện tại | Rủi ro |
|---|---|---|
| App | 1 VM `e2-medium`, 1 container backend + 1 frontend, host network | VM chết = sập |
| Backend | `uvicorn` 1 process | 1 core, không chịu tải song song CPU |
| LB | Chỉ Caddy trên chính VM | Không phân tải |
| Autoscale | Không | Không co giãn theo CPU/RAM |
| DB | Primary + 1 streaming replica, promote tay | Chưa failover tự động |
| Redis, Weaviate | 1 container trên app VM | SPOF; Redis giữ session nên không scale ngang được |
| Giới hạn tài nguyên | Không | 1 container ăn hết RAM của VM |

## 2. Kiến trúc đích (giai đoạn 1)

```
Client -> Global HTTPS LB (health /health/ready) -> Regional MIG (>=2 VM, nhiều zone, autoscale CPU 60% + RAM 80%)
                                                   VM: frontend :3000 -> backend :8000 (UVICORN_WORKERS)
                                   dùng chung: Memorystore Redis STANDARD_HA · Postgres · Weaviate
```

Trạng thái phải nằm ngoài VM: session BFF, rate limit và working memory trợ lý (`ITINERARY_REDIS_URL` bắt buộc ở production, nếu trống backend dùng bộ nhớ trong process nên các bản sao sẽ lệch nhau).

## 3. Giai đoạn và việc làm

| # | Việc | Trạng thái |
|---|---|---|
| 1 | Giới hạn `mem_limit`/`cpus` và `stop_grace_period` trong `docker-compose.yml` và `ops/docker-compose.backend-vm.yml` | Xong trong nhánh |
| 2 | Backend nhiều worker qua `UVICORN_WORKERS` (mặc định 1), `--timeout-graceful-shutdown 30` để SSE kịp kết thúc khi rút VM | Xong trong nhánh |
| 3 | Terraform `infra/terraform/environments/staging-ha/`: instance template, regional MIG (rolling update, autohealing), autoscaler CPU + RAM, Global LB (HTTP hoặc HTTPS managed cert), firewall cho dải health check, Memorystore Redis HA | Viết xong, `terraform validate` pass, **chưa apply** |
| 4 | Kịch bản tải `ops/loadtest/k6-ha.js` | Viết xong, chưa chạy (máy chưa có k6) |
| 4b | Job đối soát đơn chạy một nơi duy nhất trong cả cụm (Postgres advisory lock, `BookingStore.reconcile_leader`); trước đó mỗi worker × VM đều chạy (use case ở §3b) | Xong trong nhánh, test đơn vị pass; test Postgres thật chưa chạy |
| 5 | Weaviate dùng chung: VM riêng + đĩa riêng + snapshot hằng ngày (`weaviate.tf`, hoặc `create_weaviate=false` để dùng Weaviate Cloud); readiness phụ thuộc RecSys (`READY_REQUIRES_RECSYS`); chặn Weaviate/Redis loopback (`REQUIRE_SHARED_BACKENDS`) | Code và Terraform xong, test pass, **chưa apply**; còn chạy job index vào Weaviate mới trước khi nhận traffic |
| 6.0 | Tách health check: autohealing dùng liveness `/health/live`, LB dùng readiness `/health/ready` (use case ở §3b) | Xong, test pass, chưa apply |
| 6.1 | Bỏ SSH tunnel cho nhóm HA: private DNS `db.vota.internal`, backend từ chối DB loopback, script kiểm kết nối và ngân sách kết nối | Xong, test pass, chưa apply |
| 7 | Cloud NAT cho VM không IP public, vỏ secret và quyền đọc, cổng `require_secret_versions` (use case ở §3b) | Xong, test pass, chưa apply |
| 6.5 | `/health/ready` thăm dò DB (`READY_REQUIRES_DB`, chỉ cho LB; use case ở §3b) | Xong, test pass, chưa apply |
| 6.3 + 6.4 | pgbouncer sidecar (transaction pooling) trên mỗi VM + `LEADER_LOCK_DATABASE_URL` cho khoá leader; đã đo trước/sau (use case ở §3b) | Xong, test pass trên Postgres và pgbouncer thật, chưa apply |
| 6 | DB: endpoint ổn định cho MIG (thay `vota-db-tunnel` trên 127.0.0.1:15432), cân nhắc Cloud SQL HA hoặc Patroni + pgbouncer | Chưa làm |
| 7 | Cloud NAT cho VM không có IP public; tạo secret `vota-ha-backend-env` | Chưa làm |
| 8 | Alert MIG: số VM khỏe < min, autoscaler chạm max, 5xx của LB | Chưa làm |

## 3b. Quy ước: mỗi vấn đề HA phải kèm một use case cụ thể

Mỗi mục xử lý vấn đề HA cần một tình huống có số liệu (khách, tiền, số VM/worker), các bước xảy ra, hậu quả **đã kiểm trong code** (ghi rõ phần nào chưa kiểm), và hành vi sau khi sửa. Use case ghi trong plan này, entry `history/` và thông điệp commit.

## Use case: đối soát đơn khi scale ngang (2 VM × 2 worker = 4 vòng)

Tình huống: khách đặt khách sạn Vinpearl Phú Quốc trị giá 12 triệu, thanh toán bằng Stripe.

1. Khách trả tiền thành công nhưng webhook Stripe bị lỡ, đơn vẫn `PENDING_PAYMENT`.
2. Khách huỷ đơn trước khi xác nhận xong; đơn sang `REFUND_PENDING`, chưa có `refund_id`.
3. Đến chu kỳ 5 phút, cả 4 vòng đối soát thức dậy gần như cùng lúc. `find_reconcile_ids` chạy trong một transaction ngắn đóng ngay, nên cả 4 vòng đều thấy đơn này.
4. Cả 4 vòng cùng gọi `settlement.refund(...)` tới Stripe và `cancel_purchase_events` tới CDP.

Hiện trạng đã kiểm trong code: `Settlement.refund` và `cancel_purchase_events` giữ khoá dòng `FOR UPDATE` suốt lời gọi ngoài, kiểm lại trạng thái sau khi có khoá, và refund có idempotency key `refund:{booking_id}`. Vì vậy **hoàn tiền kép không xảy ra**; vòng sau thấy `refund_id` đã có và thoát. Tác hại còn lại là:

* 3 vòng thừa xếp hàng chờ khoá dòng, mỗi vòng giữ một connection Postgres trong lúc vòng đầu chờ Stripe; Stripe/CDP chậm thì pool connection bị chiếm.
* Tải đối soát và lời gọi `retrieve_checkout_session` tới Stripe tăng 4 lần với mọi đơn quá hạn giữ chỗ, vì phần đó không có khoá toàn cục.
* Log đầy cảnh báo `reconcile.deferred` / `reconcile.failed` lặp lại, khó phân biệt lỗi thật.

Sau khi sửa: vòng đầu lấy được advisory lock nên được đối soát. 3 vòng còn lại thấy `leader = False`, bỏ qua lượt và trả 0. Nếu VM giữ khoá chết giữa chừng, Postgres tự nhả khoá và chu kỳ sau một vòng khác tiếp quản.
Với 1 VM 1 worker (staging hiện tại) vấn đề chưa lộ; nó chỉ lộ khi scale ngang, đúng mục tiêu HA của nhánh này.

Kiểm chứng: `test_reconcile_runs_only_on_the_leader_replica` (đơn vị) và `test_reconcile_leader_is_exclusive_across_connections` (Postgres thật, cần `RUN_POSTGRES_INTEGRATION=1`).

## Use case: Weaviate dùng chung và bản sao có RecSys rỗng (2 VM)

Tình huống: hệ thống chạy 2 VM sau load balancer, mỗi VM 1 backend. Staging hiện tại chạy container `vota-weaviate` ngay trên app VM (monitoring và test container disk đều tham chiếu `vota-weaviate`; comment trong `app.tf`). Khách tìm "Vinpearl Phú Quốc" trong giờ cao điểm.

1. VM mới (hoặc VM bị autohealing thay) lên với Weaviate local rỗng: volume `weaviate_data` mới, chưa chạy job index.
2. `RecsysRefresher.reload()` thất bại ở lần nạp đầu, backend ghi `startup.recsys.disabled` rồi vẫn đặt `app.state.ready = True`.
3. LB probe `/health/ready` nhận 200, đưa VM vào rotation; autohealing cũng thấy khoẻ.
4. Khi RecSys tắt, `/search` **không báo lỗi**: `deps.get_search` trả `None` và route trả trang rỗng với HTTP 200 (`_safe_search`).

Hậu quả đã kiểm trong code: khoảng 1/2 lượt tìm kiếm (theo cách LB chia) trả "không có kết quả" với HTTP 200. Không có 5xx nên cảnh báo 5xx của LB không kêu, và VM lỗi không bị loại. Kể cả khi có Weaviate dùng chung, nếu `WEAVIATE_URL` hay Redis vẫn là `localhost` trong env secret thì từng VM nhìn thấy dữ liệu và phiên riêng (đăng nhập ở VM A, request kế tiếp sang VM B mất phiên).

Sau khi sửa:
* Cả hai VM trỏ một Weaviate dùng chung (VM riêng, đĩa riêng, snapshot hằng ngày). Cùng một câu hỏi cho cùng kết quả bất kể LB chọn VM nào.
* `READY_REQUIRES_RECSYS=true`: `/health/ready` trả 503 khi chưa nạp được RecSys; LB không gửi traffic, autohealing thay VM sau 3 lần probe lỗi.
* `REQUIRE_SHARED_BACKENDS=true`: backend từ chối khởi động nếu `WEAVIATE_URL`, `AUTH_REDIS_URL` hoặc `ITINERARY_REDIS_URL` trống/loopback, nên cấu hình sai lộ ra ngay lúc rollout (rolling update dừng vì VM mới không healthy).
* Staging một VM giữ nguyên hành vi vì cả hai cờ mặc định tắt.

Chưa kiểm: gRPC 50051 từ VM tới Weaviate qua firewall thật; thời gian dựng lại index từ đầu (job index phụ thuộc quota Cohere); Weaviate một node nên mất VM Weaviate = search ngừng tới khi dựng lại hoặc khôi phục snapshot (đã chấp nhận, ghi ở `weaviate.tf`).

Kiểm chứng: `src/backend/tests/unit/api/test_ha_readiness.py` (9 test).

## Use case: autohealing thay VM liên tục khi Weaviate gián đoạn (3 VM, autoscale)

Tình huống: 20:00, giờ cao điểm, nhóm có 3 VM. Weaviate VM khởi động lại 8 phút do bảo trì. 20:01 autoscaler thêm VM thứ 4 vì CPU vượt 60%.

1. VM thứ 4 lên (khoảng 2–3 phút), `RecsysRefresher` nạp lần đầu thất bại vì Weaviate đang tắt, nên backend chưa có `index` và `/health/ready` trả 503 (đúng thiết kế ở việc 5).
2. Cấu hình cũ dùng **cùng** health check readiness cho autohealing. Sau `initial_delay_sec = 300` VM bị coi là hỏng nên MIG xoá và tạo lại nó (khoảng 20:06), dù lỗi nằm ở Weaviate chứ không phải VM.
3. VM mới lại boot trong lúc Weaviate chưa về (về lúc 20:08), tiếp tục vòng lặp. Mỗi vòng tốn tài nguyên và VM thứ 4 không giúp được gì trong đúng lúc cần dung lượng. Rolling update trong cùng lúc cũng bị kẹt.

Đã kiểm trong code: 3 VM cũ không bị ảnh hưởng vì `RecsysRefresher` giữ index đang phục vụ khi nạp lại thất bại; `RecsysRefresher.run` thử lại sau `RECSYS_RETRY_SECONDS` khi chưa có index.
Chưa kiểm: thời điểm thật GCE xoá VM unhealthy (dựa trên tài liệu `initial_delay_sec` và `unhealthy_threshold`, chưa quan sát trên cloud).

Sau khi sửa: autohealing dùng `/health/live` (frontend sống và backend trả lời `/health`), không phụ thuộc RecSys hay DB. VM thứ 4 sống tiếp, bị load balancer loại khỏi rotation nhờ readiness, tự thử nạp lại và vào rotation khoảng 30 giây sau khi Weaviate về (khoảng 20:08:30). VM chỉ bị thay khi thật sự treo liên tục 60 giây.

Kiểm chứng: `src/frontend/tests/api/health-live.test.ts` (route live không bao giờ gọi `/health/ready`), `infra/terraform/environments/staging-ha/tests/test_health_checks.py` (MIG dùng `live`, LB dùng `ready`), `terraform validate`.

## Use case: VM sinh từ template không có đường tới DB (tunnel SSH)

Tình huống: 20:01, giờ cao điểm, autoscaler thêm VM thứ 4 (nhóm tối đa 4 VM × 2 worker). Staging hiện nối DB qua `vota-db-tunnel.service` (`127.0.0.1:15432` → `10.148.0.2:5432`), cấu hình tay trên app VM.

1. VM thứ 4 sinh từ instance template, **không có tunnel**. Env secret còn `DATABASE_URL=...@127.0.0.1:15432/...` (sao chép từ staging) nên mọi kết nối DB bị từ chối.
2. Backend nạp RecSys từ Postgres lúc khởi động nên thất bại, `/health/ready` trả 503 (do `READY_REQUIRES_RECSYS`) và VM không bao giờ vào rotation.
3. VM vẫn "sống" (liveness chỉ hỏi `/health`) nên MIG giữ nó: chiếm 1/4 `max_replicas`, tính tiền, nhưng dung lượng đỉnh không tăng. Không có thông báo nào nói nguyên nhân là DB.

Đã kiểm: Postgres staging publish trên IP private `${db_private_ip}:5432` với xác thực scram (`ops/bootstrap-db-vm.sh`), nên VM trong VPC nối được trực tiếp, tunnel không bắt buộc. Chưa kiểm: firewall và `pg_hba` của primary thật cho phép dải subnet của MIG (cần chạy `ops/check-db-direct.sh` trên VM thật); `default-allow-internal` được ghi nhận trong `firewall.tf` nhưng chưa quan sát.

Sau khi sửa:
* Tên ổn định `db.vota.internal` (Cloud DNS private zone, TTL 30 giây, `dns.tf`); env secret dùng tên này, không có tunnel.
* `REQUIRE_SHARED_BACKENDS=true` mở rộng sang `DATABASE_URL` và `CDP_DATABASE_URL`: URL loopback làm backend **từ chối khởi động** với thông báo `DATABASE_URL`, nên rollout dừng ngay thay vì để VM câm lặng không bao giờ ready.
* `ops/check-db-direct.sh` chạy trên VM: kiểm kết nối trực tiếp, từ chối loopback, và tính `VM × worker × kết nối/worker + dự trữ` so với `max_connections` (ví dụ 4 × 2 × 10 + 10 = 90 so với 30 thì báo lỗi).

Kiểm chứng: `src/backend/tests/unit/api/test_ha_readiness.py` (11 test, thêm 2 ca DB loopback), `ops/tests/test_check_db_direct.sh` (4 ca trên Postgres Docker thật), `terraform validate`.

## Use case: VM không IP public không gọi được Stripe/Cohere, và secret chưa có giá trị

Tình huống A (đường ra): nhóm HA có VM không IP public (chỉ nhận traffic qua load balancer). Khách đặt khách sạn Vinpearl Phú Quốc 12 triệu lúc 20:05 và bấm thanh toán.
1. Backend tạo phiên Checkout bằng `https://api.stripe.com` (`stripe_gateway.py`). VM không có IP public và VPC không có Cloud NAT, nên kết nối hết thời gian chờ.
2. Cùng lúc `/search` cần embed truy vấn qua `https://api.cohere.com` và trợ lý gọi LLM; các lời gọi này cũng thất bại.
3. Staging một VM không gặp vì VM có IP public; lỗi chỉ xuất hiện khi chuyển sang nhóm HA không IP public. Ngoài ra VM Weaviate kéo image `cr.weaviate.io` cũng cần đường ra.

Tình huống B (secret): `google_secret_manager_secret` đã tạo nhưng chưa có phiên bản. VM boot, startup script chạy `gcloud secrets versions access latest` và thất bại, container không bao giờ lên. `/health/live` không trả lời nên sau 300 giây autohealing xoá VM và tạo lại, lặp vô hạn, tính tiền mỗi vòng, không có lỗi rõ ràng nào ngoài log startup script.

Đã kiểm trong code: Stripe (`stripe_gateway.py: STRIPE_API`), Cohere (`cohere_base_url`) là địa chỉ ngoài Internet; template không có `access_config` (test).
Chưa kiểm: egress thật qua Cloud NAT trên GCP; VPC staging có sẵn Cloud NAT hay chưa (biến `create_nat` để tắt nếu đã có).

Sau khi sửa: Cloud NAT cho cả region (`network.tf`, 256 cổng mỗi VM) và VM chờ NAT trước khi tạo; secret có quyền đọc cho service account của VM và **giá trị không bao giờ nằm trong Terraform/state** (nạp tay bằng `gcloud secrets versions add`); với `require_secret_versions = true` plan dừng ngay nếu secret chưa có phiên bản, nên vòng lặp thay VM không bao giờ bắt đầu.

Kiểm chứng: `infra/terraform/environments/staging-ha/tests/test_egress_and_secrets.py` (6 test), `terraform validate`.

## Use case: một VM mất đường tới DB nhưng vẫn "ready" (3 VM)

Tình huống: nhóm 3 VM chạy bình thường. 21:10 sidecar kết nối DB trên VM #2 bị OOM, nên VM #2 mất đường tới Postgres (3 VM vẫn thấy DB bình thường).
1. VM #2 vẫn trả `/health` và `/health/ready` 200 (readiness cũ chỉ nhìn cờ `ready` và RecSys đã nạp, không nhìn DB; đã kiểm trong code).
2. Load balancer chia đều, nên 1/3 lượt đăng nhập, đặt chỗ và webhook Stripe rơi vào VM #2 và trả 5xx. Cảnh báo 5xx sẽ kêu nhưng VM lỗi không bị loại.
3. Autohealing (liveness) cố ý không phụ thuộc DB (việc 6.0), nên không thay VM; VM #2 hỏng cho tới khi có người can thiệp.

Đã kiểm: probe `SELECT 1` trên Postgres Docker thật: DB chạy trả True sau 0,05 giây; dừng DB thì trả False ngay; khởi động lại thì tự hồi phục. Unit test: cache 5 giây (probe liên tiếp của LB không mở kết nối mỗi lần), 20 probe đồng thời chỉ chạy 1 lượt, mọi lỗi đều là "chưa sẵn sàng".
Chưa kiểm: hành vi trên cloud với LB thật (3 lần probe × 10 giây).

Sau khi sửa: `READY_REQUIRES_DB=true` (chỉ bật trong compose HA). `/health/ready` thăm dò DSN mà request dùng (nên sidecar pgbouncer hỏng cũng bị phát hiện), timeout 2 giây, cache 5 giây. VM #2 trả 503, LB loại nó sau 3 lần probe lỗi (khoảng 30 giây cộng cache), 2 VM còn lại gánh tải; lỗi 5xx dừng. Khi DB sập toàn bộ thì cả 3 VM unready: LB trả 503 rõ ràng, nhưng autohealing **không** thay VM, nên khi DB về VM tự vào lại rotation trong vài giây.

Kiểm chứng: `src/backend/tests/unit/api/test_db_readiness.py` (9 test), chạy thật trên Postgres Docker như trên, `test_health_checks.py` (liveness vẫn tách khỏi readiness).

## Use case: khuyến mãi 20:00, 250 request đồng thời hết kết nối Postgres (4 VM × 2 worker)

Tình huống: 20:00 khuyến mãi khách sạn Vinpearl Phú Quốc, nhóm HA có 4 VM × 2 worker. Mỗi request đăng nhập, xem giỏ hoặc đặt chỗ mở **một connection Postgres mới** (backend gọi `psycopg ... connect` khoảng 30 chỗ, không có pool). Primary là `e2-small` với `max_connections` mặc định 100.
1. 250 request cùng lúc tạo 250 connection. Postgres từ chối từ connection thứ ~100 bằng `too many clients already`; các request đó trả 5xx cho khách đang đặt chỗ.
2. Các VM khác và job đối soát (cũng cần connection) cũng bị đói; superuser và replication có thể không còn chỗ.
3. Giải pháp đơn giản "tăng max_connections" làm mỗi connection tốn thêm RAM trên VM 2 GB.

Đã đo thật (Postgres 16 Docker `max_connections=100`, pgbouncer 1.26 transaction mode, 250 client đồng thời, mỗi client giữ 0,2 giây, lặp 3 lần): **trực tiếp** lỗi 42, 83, 81 trên 250 request, đỉnh khoảng 91/100 connection; **qua pgbouncer** lỗi 0/250 và đỉnh chỉ 12 connection thật. Chạy lại toàn bộ 20 test tích hợp (booking, auth, catalog, CDP) qua pooler đều pass, gồm auto-prepare của psycopg.
Điều chỉnh sau khi đo: pool 10 (+2 dự phòng) cho mỗi (database, role), nên trần xấu nhất của 4 VM × 2 role = 96 connection, được tính bằng `POOLED=1 ops/check-db-direct.sh`.

Rủi ro kèm theo đã tái hiện: khoá advisory mức session của job đối soát (vấn đề 1) không dùng được qua pooler transaction mode: hai bản sao cùng thấy mình là leader (`(True, True)`, test `test_session_advisory_lock_is_not_exclusive_through_the_pooler`). Sửa: `LEADER_LOCK_DATABASE_URL` đi thẳng tới Postgres; guard `REQUIRE_SHARED_BACKENDS` bắt buộc đặt nó khi dùng pooler, và chấp nhận loopback `127.0.0.1:6432` (pgbouncer sidecar) nhưng vẫn từ chối tunnel `127.0.0.1:15432`.

Chưa kiểm: chạy trên VM thật (image kéo qua NAT, quyền ghi `/etc/vota/pgbouncer`, `nc` trong image cho healthcheck); mật khẩu role có ký tự cần mã hoá URL bị script từ chối (kiểm bằng test).

## 4. Điều kiện trước khi `terraform apply`

1. Việc 5, 6, 7 xong; env secret trỏ Redis/Weaviate/DB dùng chung, không phải `localhost`.
2. Image backend/frontend ghim tag (không `:latest`).
3. `TRUSTED_PROXIES` bao dải LB (130.211.0.0/22, 35.191.0.0/16) vì client IP đi qua `X-Forwarded-For`; sai giá trị thì rate limit sai.
4. Chạy `terraform plan` và người dùng duyệt; apply chỉ trên staging.

## 5. Nghiệm thu

- p95 < 800 ms, lỗi < 1% với 150 VU (k6).
- Autoscaler tăng VM khi CPU > 60% và giảm sau khi hết tải.
- Xoá 1 VM giữa lúc chạy tải: lỗi < 1%, VM mới tự lên và vào rotation.
- Rolling update image không có request 5xx kéo dài (max_unavailable = 0).
- Mất 1 zone vẫn phục vụ được (cần min ≥ 2 trải nhiều zone).

Lệnh: `k6 run -e BASE_URL=http://<lb-ip> ops/loadtest/k6-ha.js`.

## 6. Rủi ro và chưa quyết

- RAM mỗi worker: mỗi worker nạp cache catalog riêng. Đo RSS trước khi tăng `UVICORN_WORKERS` > 1.
- Giới hạn `mem_limit 3g` của backend vượt RAM `e2-medium` (4 GB) nếu để chung với Weaviate; dùng cho tầng HA (`e2-standard-2` trở lên, Weaviate tách riêng).
- Memorystore `transit_encryption_mode = DISABLED` để khớp URL `redis://`; đổi sang `rediss://` nếu yêu cầu bảo mật cao hơn.
- Advisory lock mức session cần connection trực tiếp tới Postgres; không dùng qua pgbouncer chế độ transaction (việc 6 phải tính điều này).
- Chi phí staging tăng (≥ 2 VM + Memorystore HA + LB).
