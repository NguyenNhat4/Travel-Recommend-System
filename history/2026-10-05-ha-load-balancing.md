# HA, phân tải và giới hạn tài nguyên cho tầng app

- Ngày: 2026-10-05
- Tác giả: Khoa / Claude
- Nhánh: khoa/ha-load-balancing
- Trạng thái: hoàn thành cho phần đối soát; dang dở cho các giai đoạn còn lại của plan
- Phạm vi: docs | infra (ops, Terraform)

## Mục tiêu

Hạ tầng staging chỉ có 1 app VM, 1 worker uvicorn, không LB, không autoscale, không giới hạn tài nguyên. Cần nền tảng HA và cân bằng CPU/RAM.

## File thay đổi

- `docs/plan/2026-10-05-ha-load-balancing.md` — thêm: kế hoạch giai đoạn, điều kiện apply, nghiệm thu
- `Dockerfile.backend` — sửa: thêm `--timeout-graceful-shutdown 30`
- `docker-compose.yml` — sửa: `UVICORN_WORKERS`, `mem_limit`, `cpus`, `stop_grace_period`
- `ops/docker-compose.backend-vm.yml` — sửa: như trên cho VM staging hiện hữu
- `infra/terraform/environments/staging-ha/` — thêm: MIG regional, autoscaler CPU+RAM, Global LB, firewall health check, Memorystore Redis HA, compose và startup script cho VM
- `ops/loadtest/k6-ha.js` — thêm: kịch bản tải
- `src/backend/app/application/ports/booking_store.py` — sửa: thêm `BookingStore.reconcile_leader()`
- `src/backend/app/infrastructure/persistence/postgres_booking.py` — sửa: `reconcile_leader` bằng `pg_try_advisory_lock` trên connection riêng
- `src/backend/app/application/booking/reconcile.py` — sửa: chỉ leader mới chạy đối soát, bản sao khác bỏ qua lượt
- `src/backend/tests/fakes/booking.py`, `src/backend/tests/unit/application/booking/test_booking_flow.py` — sửa: fake khoá leader và test mới
- `src/backend/tests/integration/test_booking_postgres.py` — sửa: test khoá loại trừ giữa hai connection (cần `RUN_POSTGRES_INTEGRATION=1`)

## Quyết định

- Theo yêu cầu người dùng, bỏ qua bước đề xuất PRD (`AGENTS.md` mục 8); ghi rõ trong plan.
- Root Terraform mới tách khỏi `environments/staging` để không đụng VM đang chạy (`prevent_destroy`).
- Số worker mặc định 1 để không đổi hành vi hiện tại; tầng HA đặt 2.
- LB probe route `/health/ready` của frontend (proxy sang backend) để VM rời rotation khi một trong hai nửa chết.
- Biến môi trường cho frontend chỉ gồm `AUTH_SERVICE_TOKEN` và `SESSION_REDIS_URL`, không chuyển cả `backend.env` sang frontend.

## Kiểm tra

- `terraform fmt` + `terraform init -backend=false` + `terraform validate` trong `staging-ha`: pass.
- `docker compose config -q` (docker-compose.yml): pass. Compose của VM không validate được cục bộ vì thiếu `/etc/vota/backend.env`.
- `pytest src/backend/tests/unit/application/booking`: 63 passed (gồm test leader mới).
- `APP_ENV=test pytest src/backend/tests --ignore=integration`: 1094 passed, 8 failed. 8 fail đều ở `test_assistant_contract.py` do `ConnectionRefused 127.0.0.1:6379` (`.env` cục bộ trỏ Redis, Docker đang tắt); baseline sạch (worktree không có `.env`) 1101 passed. Không liên quan đối soát.
- Chưa chạy: test Postgres thật cho advisory lock (Docker tắt), `terraform plan/apply`, k6, `UVICORN_WORKERS` với backend thật, image build. Không đụng contract/DB nên không chạy `validate_contract.py`/`verify.sql`.

## Vấn đề HA đã giải: đối soát đơn chạy trùng khi scale ngang

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

## Còn lại / rủi ro

- Weaviate dùng chung, endpoint DB ổn định, Cloud NAT, secret env, alert MIG chưa làm (plan §3 việc 5–8).
- Kiểm bộ nhớ khi tăng worker; chưa đo.
- Chưa có PRD/đề xuất cho HA nếu cần đồng bộ tài liệu gốc.
