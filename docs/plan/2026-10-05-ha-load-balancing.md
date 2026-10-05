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
| 5 | Weaviate dùng chung: tách khỏi app VM (VM riêng hoặc Weaviate Cloud), đặt `WEAVIATE_URL` trong secret | Chưa làm, **điều kiện tiên quyết để apply** |
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
