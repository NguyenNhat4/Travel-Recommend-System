# Tách health check autohealing/LB và chặn test chạm dịch vụ thật

- Ngày: 2026-10-05
- Tác giả: Khoa / Claude
- Nhánh: khoa/ha-load-balancing
- Trạng thái: hoàn thành
- Phạm vi: frontend | backend (test) | infra

## Mục tiêu

(1) Việc 6.0 của `docs/plan/2026-10-05-ha-load-balancing.md`: autohealing và load balancer đang dùng chung health check readiness, nên Weaviate/DB gián đoạn làm MIG thay VM vô ích. (2) Test phải thôi đọc `.env` của dev (trỏ DB staging qua tunnel, Weaviate Cloud, khóa Cohere/OpenAI thật); lượt test trước đã suýt gọi dịch vụ thật.

## File thay đổi

- `src/frontend/src/app/health/live/route.ts` — thêm: liveness proxy backend `/health`, timeout 3 giây, không phụ thuộc RecSys/DB
- `src/frontend/tests/api/health-live.test.ts` — thêm: 4 test
- `infra/terraform/environments/staging-ha/main.tf` — sửa: health check `ready` (LB) và `live` (autohealing) tách riêng
- `infra/terraform/environments/staging-ha/tests/test_health_checks.py` — thêm: 5 test kiểm vai trò hai health check
- `src/backend/tests/conftest.py` — sửa: vô hiệu đọc `.env`, hook `pytest_configure` từ chối biến trỏ máy từ xa/tunnel staging
- `src/backend/tests/guard.py` — thêm: logic phát hiện dịch vụ không phải máy này (override `ALLOW_REMOTE_TEST_DEPS=1`)
- `src/backend/tests/unit/test_conftest_guard.py` — thêm: 9 test
- `docs/plan/2026-10-05-ha-load-balancing.md` — sửa: thêm use case 3 và dòng 6.0

## Quyết định

- Liveness đi qua frontend (cổng 3000) để một health check cover cả frontend lẫn backend; không mở thêm cổng 8000 cho dải health check.
- Test không đọc `.env` mà không cần đổi `Settings` production: conftest đặt `Settings.model_config["env_file"] = None` trước khi `main` import.
- Guard chỉ xét biến có trong môi trường shell; coi 127.0.0.1:15432/15433 là staging.
- Use case: autohealing thay VM liên tục khi Weaviate gián đoạn lúc autoscale (chi tiết ở plan §3b).

## Kiểm tra

- `npx vitest run tests/api/health-live.test.ts tests/api/health-ready.test.ts` (src/frontend): 6 passed.
- `terraform validate` (staging-ha): pass; `python3 infra/terraform/environments/staging-ha/tests/test_health_checks.py`: 5 passed. Lần sửa đầu để sót tham chiếu health check cũ ở backend service; validate và test bắt được và đã sửa.
- Có `.env` (APP_ENV=production, DSN staging) và không đặt biến môi trường: `pytest src/backend/tests --ignore=integration` 1120 passed (trước đây cần ghi đè biến mới sạch).
- Đặt `DATABASE_URL=...@127.0.0.1:15432/...`: pytest từ chối chạy với thông báo rõ.
- Chưa chạy: apply Terraform, quan sát GCE autohealing thật.

## Còn lại / rủi ro

- 4 test `test_assistant_contract.py` fail khi `AUTH_REDIS_URL` trỏ Redis thật (giả định bộ đếm trong bộ nhớ); có từ trước, ghi ở `2026-10-05-ha-load-balancing.md`.
- Việc 6.1–6.3 (DB endpoint, failover có script, tách DSN advisory lock) chưa làm.
