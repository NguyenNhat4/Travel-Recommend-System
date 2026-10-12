# Thực hiện Phase 1–4 của kế hoạch todo; Phase 2 apply và Phase 3–4 bị chặn

- Ngày: 2026-10-08
- Tác giả: Khoa15 / Claude (agent)
- Nhánh: khoa/ha-runtime-bootstrap-fix
- Trạng thái: dang dở
- Phạm vi: infra | backend | frontend | ops | docs

## Mục tiêu

Người dùng yêu cầu làm ngay Phase 1 đến Phase 4 của kế hoạch hoàn thành todo, với các quyết định D1–D6. Entry này ghi lại đã làm được gì, đã kiểm chứng gì, và dừng ở đâu.

## Quyết định của người dùng

- D1: merge `khoa/backend-db-unavailable-degraded` → đã làm (`00dab1a`).
- D2: email alert `nguyentrongdangkhoa15@gmail.com` → đã có trong `staging-ha.tfvars` (file local, bị `.gitignore`), giá trị trùng với dòng đã có.
- D3: xoá `db.pool.exhausted` → đã làm (`15b9582`).
- D4: báo lỗi có hướng dẫn thay vì tự nối lại SSE → đã làm (`2f98761`).
- D5: quyền GCP → `gcloud` đăng nhập `nguyentrongdangkhoa15@gmail.com`, project `vinpearl-508801`, ADC hoạt động.
- D6: người dùng tự nạp secret. Secret `vota-ha-backend-env` đã có 5 phiên bản đang bật (tạo 07/10, phiên bản mới nhất là 9). Chưa kiểm nội dung. Xem mục "Khoá cần có" bên dưới.

## Đã làm

- **Phase 1.1** — commit `9dece87`: chỉ node `a` clone từ primary cũ, node `b` chờ leader; kèm entry 08/10 và đề xuất PRD đã áp dụng (đã có sẵn). `staging-ha` unit test 51 PASS, `terraform validate` PASS, cú pháp template PASS.
- **Phase 1.2** — commit `15b9582`: đổi `widgetProgress.ts` → `widgetProgressView.ts` để tránh xung đột chữ hoa/thường với `WidgetProgress.tsx`. Sau khi chạy `npm install` để cài `pino` (có trong `package.json` nhưng chưa có trong `node_modules`), vitest: 71 file, 717 test PASS.
- **Phase 1.3** — commit `15b9582`: bỏ `db.pool.exhausted` khỏi `logging_config.py` và `docs/spec/logging-schema.md`. Test `unit/core` + `architecture`: 23 PASS.
- **Phase 1.4** — commit `15b9582`: thêm anchor `x-logging` (json-file 50 MB × 5) cho pgbouncer, backend, frontend trong `compose.ha.yml`; thêm `--log-opt` cho container Postgres trong `ops/bootstrap-db-vm.sh`. Kiểm bằng `docker compose config` trên bản sao không có `env_file` (vì `/etc/vota` không tồn tại trên máy này): hợp lệ, cả ba service có `max-size: 50m`.
- **Phase 1.5** — ghi trong entry `2026-10-08-sse-bao-loi-co-huong-dan-va-trang-thai-logging.md` (commit `2f98761`): trạng thái logging đã merge.
- **Phase 1.6** — merge `00dab1a` (`khoa/backend-db-unavailable-degraded`). Xung đột và cách giải quyết ghi trong `2026-10-08-merge-db-unavailable-degraded.md`. Quyết định quan trọng: giữ readiness HA của HEAD (VM mất DB trả 503). Nhánh kia ghi `/health/ready` luôn 200; hai thiết kế mâu thuẫn và đây cần người chốt.
- **Phase 1.7** — test Patroni trên Docker cục bộ (image build từ `ops/patroni`): `test_patroni_failover.sh` PASS (failover trong 29 s, không mất dữ liệu); `test_patroni_clone_bootstrap.sh` PASS.
- **D4 (frontend)** — `assistantStream.ts`: thông báo khi stream bị đứt là hướng dẫn tiếng Việt ("Bấm 'Thử lại'…"). UI đã có nút "Thử lại" cho lỗi retryable. Test assistant: 24 PASS.
- **Contract** — `validate_contract.py` PASS sau merge.

## Phase 2 — dừng ở bước apply

- **2.1 `terraform plan` (chỉ đọc)**: `init` với bucket `vinpearl-508801-staging-tfstate`, prefix `infra/staging-ha` → thành công. Plan: 1 add / 1 change / 1 destroy, thực chất là:
  - `google_compute_instance_template.app` phải thay (thêm `logging: *default-logging` vào compose trong startup script, từ Phase 1.4).
  - `google_compute_region_instance_group_manager.app` cập nhật tại chỗ (rolling replace, `max_unavailable = 0`).
  - Không có resource mới nào khác; `alert_emails` không tạo kênh mới.
- **2.2 `terraform apply` của plan đã review: BỊ CHẶN.** Bộ phân loại an toàn từ chối lệnh apply (phạm vi IaC được bảo vệ). Không thử cách khác để apply. Đây là thay đổi làm thay toàn bộ VM app của nhóm HA theo rolling update, nên cần người dùng cho phép rõ ràng.
- **2.3–2.6**: không làm. 2.4 (kiểm trên VM) và 2.5 (cài Ops Agent trên VM staging) cần SSH vào VM. 2.6 (`terraform plan` cho `infra/monitoring`) chưa làm.

## Phase 3 và Phase 4 — chưa làm

- Phase 3 phụ thuộc Phase 2 apply, và cần quyết định hướng đồng bộ `cdp.products` (157 dòng lệch) cùng cửa sổ bảo trì. Không làm cutover DNS hay đổi `DATABASE_URL` khi chưa có các điều kiện này.
- Phase 4: stack Docker đầy đủ, crawler thật (gọi nguồn bên ngoài và ghi dữ liệu), chi phí Cloud Logging sau 7 ngày — chưa làm.

## Khoá cần có trong `vota-ha-backend-env` (tên khoá, không có giá trị)

Lấy từ `src/backend/app/core/config.py` (quy tắc `shared_backend_violations`) và `startup.sh.tftpl`:

- `DATABASE_URL` — qua pgbouncer sidecar `127.0.0.1:6432` (được phép loopback).
- `CDP_DATABASE_URL` — qua pgbouncer sidecar `127.0.0.1:6432`.
- `LEADER_LOCK_DATABASE_URL` — DSN trực tiếp tới Postgres, không qua pooler.
- `AUTH_REDIS_URL`, `ITINERARY_REDIS_URL`, `BOOKING_REDIS_URL`, `SESSION_REDIS_URL` — Memorystore, không loopback. Host lấy từ output `redis_host`.
- `WEAVIATE_URL`, `WEAVIATE_API_KEY` — không loopback.
- `JWT_PRIVATE_KEY_B64`, `JWT_PUBLIC_KEY_B64` — startup script giải mã ra `/etc/vota/secrets/*.pem`.
- `AUTH_SERVICE_TOKEN`, `CDP_SERVICE_TOKEN`, `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `PUBLIC_WEB_URL`, `ALLOWED_ORIGINS`, và các biến khác theo `.env.example`.

Lệnh nạp (người dùng tự chạy trên máy của mình, file `backend.env` không commit):

```bash
gcloud secrets versions add vota-ha-backend-env --project=vinpearl-508801 --data-file=backend.env
```

Kiểm tra phiên bản (chỉ metadata):

```bash
gcloud secrets versions list vota-ha-backend-env --project=vinpearl-508801 --format='table(name,state,createTime)'
```

Không đọc giá trị secret ở bước này.

## Kiểm tra

- `staging-ha`: 51 unit test PASS; `terraform validate` PASS.
- Frontend: vitest 71 file / 717 test PASS (sau `npm install`); assistant 24 test PASS.
- Backend: toàn bộ unit (`pytest src/backend/tests --ignore=src/backend/tests/integration`, venv nháp): 1834 passed, 2 skipped, exit 0, sau khi merge và viết lại `test_db_probe.py`.
- Contract: `validate_contract.py` PASS.
- Patroni Docker: failover PASS, clone bootstrap PASS.
- Terraform plan (2.1) đã chạy; apply không chạy.

## Còn lại / rủi ro

- Apply Phase 2 (thay instance template và rolling update MIG). Cần người dùng cho phép trực tiếp.
- Phase 2.4, 2.5, 2.6 và toàn bộ Phase 3, Phase 4.
- Hướng readiness khi DB mất (HA giữ 503 khi chỉ một VM mất DB; nhánh kia giữ 200) cần người chốt.
- Đề xuất PRD `2026-10-08-staging-ha-patroni` ghi đường dẫn `infra/staging-ha`; đường dẫn thật là `infra/terraform/environments/staging-ha`. Không sửa vì đã được chốt; người dùng quyết định.
