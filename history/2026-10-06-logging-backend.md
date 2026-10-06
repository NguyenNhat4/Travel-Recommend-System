# Log JSON có cấu trúc cho backend

- Ngày: 2026-10-06
- Tác giả: Khoa / Claude (agent)
- Nhánh: khoa/logging-backend (PR vào khoa/logging)
- Trạng thái: hoàn thành
- Phạm vi: backend

## Mục tiêu

Triển khai phần backend của `docs/spec/logging-schema.md` và `docs/plan/2026-10-06-logging-he-thong.md`: log JSON một dòng ra stdout, giờ Hà Nội, có `request_id`, che dữ liệu nhạy cảm, sự kiện `http.request` và sự kiện nghiệp vụ theo từng workflow. Người dùng cho phép bỏ qua PRD cho việc này.

## File thay đổi

- `src/backend/app/core/logging_config.py` — thêm: `configure_logging()`, `JsonFormatter`, `log_event()` (allowlist trường theo event), `redact()`/`mask_text()`, `hash_user_id()`, `truncate_json()`.
- `src/backend/app/core/request_context.py` — sửa: thêm holder người gọi (`open_actor`, `note_actor`) để middleware biết `user_kind`/`user_id_hash`.
- `src/backend/app/api/middleware.py` — sửa: `HttpLogMiddleware` (ASGI thuần) + `install_http_logging`; phát `http.request`, body theo bảng schema §3.
- `src/backend/app/api/deps.py`, `src/backend/app/application/auth/bearer.py` — sửa: ghi người gọi (user/guest/service) cho log.
- `src/backend/app/main.py` — sửa: gọi `configure_logging()` một lần, cài middleware, thay `print` bằng log, `app.startup`/`app.shutdown`, `readiness.degraded` + `db.unavailable` (chỉ khi đổi trạng thái).
- `src/backend/app/application/auth/use_cases.py` — sửa: `auth.login/register/session.revoke/password.change`.
- `src/backend/app/application/search/use_cases.py`, `src/backend/app/api/v1/routes/search.py` — sửa: `search.run`, `search.embed.failed`.
- `src/backend/app/application/recommendation/use_cases.py`, `.../responses.py` — sửa: `recsys.recommend`, `recsys.fallback`.
- `src/backend/app/api/v1/routes/booking.py` — sửa: `cart.item.add/remove`, `draft.create/update`.
- `src/backend/app/application/booking/{create_hold,settlement,purchase_events,cancel,payment_events,reconcile,guest_merge}.py` — sửa: `booking.*`, `payment.settled/failed`, `guest.merge`.
- `src/backend/app/api/v1/routes/payments.py` — sửa: `payment.webhook.received`, `payment.signature.invalid`.
- `src/backend/app/api/v1/routes/events.py` — sửa: `events.ingest`.
- `src/backend/app/api/v1/routes/assistant.py` — sửa: `assistant.run.start/end`, `assistant.node`, `assistant.stream.open/close`.
- `src/backend/app/agents/steps/messages.py` — sửa: `chat_model()` trả proxy ghi `assistant.llm.call` (schema, thời gian, kết quả; không ghi prompt/response).
- `src/backend/app/agents/steps/tool_planning.py`, `src/backend/app/agents/nodes.py` — sửa: `assistant.tool.call`, `assistant.grounding`, `assistant.llm.call` khi lỗi.
- `Dockerfile.backend` — sửa: thêm `--no-access-log`.
- `ops/docker-compose.backend-vm.yml` — sửa: thêm `LOG_LEVEL`, `LOG_BODIES` vào `environment` của backend.
- `src/backend/tests/unit/core/test_logging.py` — thêm: test formatter, redact, allowlist, middleware.

## Quyết định

- Múi giờ cố định `+07:00` (`timezone(timedelta(hours=7))`): Việt Nam không có giờ mùa hè, image `python:slim` không chắc có tzdata.
- Log cũ (`logger.info("startup.x.y k=v")`) không đổi: formatter lấy từ đầu có dấu chấm làm `event`, thông điệp đi qua `mask_text`. Chỉ các sự kiện trong schema mới dùng `log_event` với allowlist.
- Middleware là ASGI thuần (không `BaseHTTPMiddleware`) để đọc body mà không phá luồng SSE; giữ tối đa 64 KiB mỗi phía rồi cắt về 2.048 byte khi ghi. Đặt trước `install_request_id` để nằm trong và đọc được `X-Request-ID`.
- `/auth/*` không log request; response chỉ giữ `user.id` băm và vai trò. Webhook Stripe không log body. Booking/cart dùng danh sách khoá cho phép (productId, quantity, usingDate, referenceCode, status, totalAmount), nên hành khách/liên hệ không bao giờ vào log.
- `readiness.degraded` chỉ ghi khi trạng thái đổi, vì load balancer gọi `/health/ready` liên tục.
- `LOG_BODIES` mặc định bật trong code; tắt khi chạy tải.

## Kiểm tra

- `pytest src/backend/tests -q`: 1205 passed, 30 skipped (gồm `tests/architecture`). Lần chạy đầu có 1 test cũ fail vì thứ tự log của `itinerary.tool.timeout`; đã sửa thứ tự và chạy lại pass.
- `pytest src/backend/tests/unit/core -q`: 15 test mới pass (formatter, `ts` có `+07:00`, redact password/JWT/DSN/email/thẻ/Bearer/`sk_live_`/`whsec_`/số điện thoại, allowlist, health ở DEBUG, body bị cắt, `/auth` không log request, lỗi 500 có stack đã làm sạch).
- Chạy thử `TestClient(app)` in ra dòng `http.request` và `search.run` đúng JSON một dòng.
- Chưa chạy: uvicorn thật trong container, ingest Ops Agent/Cloud Logging, test với Redis/Postgres/Stripe thật.

## Còn lại / rủi ro

- Không deploy backend JSON trước khi sửa metric trong nhánh `khoa/logging-monitoring` (metric requests/5xx lọc `jsonPayload.event="http.request"`), nếu không SLO về 0.
- Chưa có `db.pool.exhausted` (adapter Postgres hiện không có pool để đo); `auth.mfa.verify` chưa dùng vì 2FA ngoài phạm vi P0.
- `assistant.llm.call` ghi theo tên schema (TurnRoute, Extraction...) chứ không theo tên node; chưa ghi số token.
- Compose HA và `ops/` khác chưa thêm `LOG_LEVEL`/`LOG_BODIES`; dùng mặc định trong code.
- Log của thư viện bên thứ ba vẫn ra dạng `event="log"` kèm `logger`.
