# Kế hoạch: Booking — giữ chỗ, thanh toán Stripe (MoR), thanh toán thất bại, khách huỷ

- Ngày: 2026-09-24
- Phục vụ: FR-BKG-01…04, NFR-REL-02, NFR-SEC-01, NFR-MAINT-01, NFR-MAINT-02 (`docs/prd/requirements.md` §1.5, §2); AC-BKG-01. Mã mới FR-BKG-05, FR-BKG-06, FR-BKG-07, NFR-SEC-03 và AC-BKG-02…04 nằm trong đề xuất, **chưa có hiệu lực**.
- Đề xuất PRD: `docs/prd/update-archive/2026-09-24-thanh-toan-stripe-mor.md` — **đã chốt và áp dụng vào PRD (2026-09-24)**; các bước 🔒 đã mở khoá.
- Sơ đồ sequence/activity: `docs/spec/booking/so-do-luong-dat-cho-thanh-toan.md`
- Căn cứ: `docs/spec/hop-dong-tich-hop-backend.md` §7, §8; `docs/spec/hop-dong-tich-hop-frontend.md` §4.4–§4.6, §8; `docs/spec/hop-dong-tich-hop-cdp.md` §3.3, §5; `docs/prd/architecture.md` §2, §5, §6
- Người làm: mihhquan / Claude Code, nhánh `feat/booking`
- Lịch sử: `history/2026-09-24-ke-hoach-thanh-toan-stripe.md`

## Tiến độ (cập nhật 2026-09-24)

| Bước | Trạng thái | Ghi chú |
|---|---|---|
| 0 — Chốt đề xuất, cập nhật PRD | Xong | `history/2026-09-24-ap-dung-de-xuat-thanh-toan-stripe-mor.md` |
| 1 — Giỏ hàng server-side (Backend + Web) | Xong | Web đọc/ghi giỏ qua BFF, `TravelContext` không còn giỏ local |
| 2 — Contract | Xong | Contract 1.5.0, 7 fixture mới, `validate_contract.py` PASS |
| 3 — Database | Xong | Migration `0003`, `0004`; `db/verify.sql` thêm 2 dòng |
| 4, 5, 6, 7 — Domain, application, infrastructure, API | Xong | Adapter Stripe dùng REST qua `httpx`, không thêm SDK `stripe` |
| 8 — Frontend | Xong | `/checkout`, `/booking/{referenceCode}` theo 5 trạng thái |
| 9 — Đồng bộ tài liệu | Xong | spec backend/frontend/CDP/product/DATABASE_SCHEMA, README |
| 10 — Nghiệm thu với Stripe test thật | **Chưa** | Cần khoá test + Stripe CLI (mục "Bước 10"); đã chạy E2E với `PAYMENT_PROVIDER=fake` |

Chi tiết và kết quả kiểm tra: `history/2026-09-24-trien-khai-booking-thanh-toan-stripe.md`.

## Mục tiêu

Thay luồng "bấm Xác nhận là xong đơn" bằng luồng thanh toán thật chạy trên Stripe test mode, V-OTA là Merchant of Record, xử lý đủ bốn tình huống:

| Tình huống | Kết quả mong muốn | Sơ đồ |
|---|---|---|
| Đặt chỗ thành công | Đơn `CONFIRMED` chỉ sau khi Stripe xác nhận thu tiền; event `purchase` đã ghi; gợi ý đổi ngay | spec §6 |
| Thanh toán thất bại | Phân biệt thẻ bị từ chối (thử lại tối đa 3 lần) với lỗi kỹ thuật (Stripe/DB/CDP); không mất giỏ; không mất tiền của khách | spec §7 |
| Giữ chỗ | Đơn `PENDING_PAYMENT` giữ giá 30 phút; mỗi người một đơn giữ; hết hạn thì `EXPIRED` | spec §8 |
| Khách huỷ | Chưa trả: huỷ ngay. Đã trả: hoàn 100% nếu còn hạn; huỷ event `purchase` | spec §9 |

## Phạm vi

**Trong phạm vi:** giỏ hàng server-side (đã có contract), tạo đơn giữ chỗ, Stripe Checkout hosted page, webhook, job đối soát, huỷ và hoàn tiền, trang `/checkout` và `/booking/{referenceCode}` của Web.

**Ngoài phạm vi:** Stripe live mode (Stripe không mở tài khoản cho doanh nghiệp đăng ký tại Việt Nam), Payment Element nhúng, huỷ từng mục, phí huỷ, trả tiền cho nhà cung cấp, tự động xử lý tranh chấp, hoá đơn VAT, email xác nhận, trạng thái `COMPLETED`, tồn kho thời gian thực.

## Nghiệm thu

Theo AC trong đề xuất (sẽ vào `requirements.md` §3 khi chốt):

1. **AC-BKG-01:** thẻ `4242 4242 4242 4242` → đơn `CONFIRMED`, `app.payments` = `succeeded`, có event `purchase` trong CDP, trang `/booking/{ref}` hiện mã đơn; khối gợi ý đổi theo điểm đến vừa đặt (AC-REC-02).
2. **AC-BKG-02:** thẻ `4000 0000 0000 0002` ba lần → đơn `PAYMENT_FAILED`, `failureReason = TOO_MANY_ATTEMPTS`, không có event `purchase`, giỏ còn nguyên.
3. **AC-BKG-03:** không trả trong 30 phút → `EXPIRED`; bấm Thanh toán lần nữa khi đang giữ chỗ → `409 BOOKING_PENDING_PAYMENT`.
4. **AC-BKG-04:** huỷ đơn đã trả, còn hạn → `CANCELLED`, Stripe Dashboard (test) có refund toàn bộ, `list_events` không còn trả event của đơn; quá hạn → `409 BOOKING_NOT_CANCELLABLE`.
5. Không file nào trong `src/` chứa khoá Stripe; log không có số thẻ, email hay payload webhook đầy đủ.

## Hiện trạng (đối chiếu code ngày 2026-09-24)

| Hạng mục | Trạng thái | Bằng chứng |
|---|---|---|
| Contract giỏ và booking | Có, checkout giả lập: `status` luôn `CONFIRMED`, không có huỷ | `src/shared/contracts/paths/booking.yaml`, `schemas/booking.yaml` |
| Mock giỏ | Có (10 fixture cart) | `src/shared/mocks/index.json` mục `booking/` |
| DDL giỏ và booking | Có; `bookings.status` chỉ `confirmed \| cancelled`; không có bảng thanh toán, không có hạn giữ chỗ | `db/vota_schema.sql` dòng 191–248 |
| Route giỏ và booking ở Backend | **Chưa có** | `api/v1/routes/` chỉ có `assistant`, `auth`, `catalog`, `recommendations`, `search` |
| Domain/application booking | Chỉ có `commit_with_purchase_events` (ghi CDP rồi commit, lỗi thì huỷ event) | `application/booking/purchase_events.py`; `domain/booking/` rỗng |
| `CdpClient.record_purchases` / `cancel_purchases` | Có | `application/ports/cdp_client.py`, `infrastructure/cdp/local_cdp_client.py` |
| Web checkout | Có giao diện, chạy bằng state local (`useTravel().createBooking`), chưa gọi API | `components/checkout/CheckoutView.tsx`, `context/TravelContext.tsx` |
| Stripe | Chưa có gì (SDK, biến môi trường, port) | — |

Vì Backend chưa có route booking nào, bước 1 (giỏ hàng) làm được ngay theo contract hiện có. Toàn bộ phần thanh toán phải đợi chốt.

## Quyết định thiết kế

Chi tiết và lý do ở spec §2–§9. Các con số là phương án đề xuất, người chốt có thể đổi (Q1–Q8 trong đề xuất).

| Chủ đề | Quyết định |
|---|---|
| Giao diện thanh toán (Q1) | Stripe Checkout hosted page. Web chỉ chuyển trang tới `checkoutUrl`, không cần Stripe.js |
| Mô hình | MoR: một tài khoản Stripe của V-OTA, không Stripe Connect; tiền tệ `vnd` (không có số lẻ, `amount` = số đồng) |
| Giữ chỗ (Q2, Q3) | 30 phút = `expires_at` của phiên Stripe; một đơn `PENDING_PAYMENT` mỗi user; không trừ tồn kho; giỏ giữ nguyên tới khi `CONFIRMED` |
| Thất bại (Q4) | Đếm `payment_intent.payment_failed`; đủ 3 lần thì Backend đóng phiên, đơn `PAYMENT_FAILED` |
| Huỷ (Q5) | Cả đơn; đã trả thì hoàn 100% nếu trước 00:00 (giờ VN) của ngày liền trước `usingDate` sớm nhất |
| Nguồn sự thật | Webhook có chữ ký, hoặc Backend tự hỏi Stripe. Không tin redirect `success_url` |
| Thứ tự gọi | Tạo đơn: gọi Stripe → commit DB → lỗi thì đóng phiên. Xác nhận: `payment SUCCEEDED` (commit riêng) → `record_purchases` → commit `CONFIRMED`; lỗi thì **không** huỷ event, trả 500 để Stripe gửi lại. Huỷ đã trả: commit `CANCELLED + REFUND_PENDING` → Refund API → `cancel_purchases` |
| Idempotency | `Idempotency-Key` = `booking:{bookingId}` khi tạo phiên, `refund:{bookingId}` khi hoàn; webhook xử lý theo máy trạng thái nên gửi trùng không đổi gì |
| Job đối soát | Chạy trong Backend 5 phút/lần, `FOR UPDATE SKIP LOCKED`; lo webhook bị lỡ, xác nhận dở, hoàn tiền dở, huỷ event dở |
| Contract (Q6) | Sửa trong v1, vì chưa client nào gọi `POST /bookings` |
| Webhook (Q7) | Stripe gọi thẳng FastAPI `POST /api/v1/payments/stripe/webhook`, không qua BFF |

## Các bước

Thứ tự giữ đúng `AGENTS.md` §3: contract → DB → backend → frontend.

### Bước 0 — Chốt đề xuất và cập nhật PRD 🔒 (người dùng)

1. Người dùng chốt `docs/prd/update-archive/2026-09-24-thanh-toan-stripe-mor.md`: chọn phương án cho Q1–Q8, cấp mã FR-BKG-05…07 và NFR-SEC-03.
2. Cập nhật `docs/prd/` đúng nội dung đã chốt: `project-brief.md`, `requirements.md`, `data-model.md`, `architecture.md`, `deployment-plan.md`, `user-flow.md`, `test-plan.md`.
3. Đổi trạng thái đề xuất thành `đã áp dụng`, `git mv` sang `docs/prd/update-archive/`, ghi entry `history/`.
4. Nếu chốt khác đề xuất: sửa spec sơ đồ và plan này trước khi sang bước 2.

### Bước 1 — Giỏ hàng server-side (không lệch PRD, làm ngay được)

Hiện thực đúng contract đang có (`GET /cart`, `POST /cart/items`, `PATCH`/`DELETE /cart/items/{cartItemId}`, `hop-dong-tich-hop-backend.md` §7.1). Bước này cần cho cả luồng cũ lẫn luồng Stripe.

- `domain/booking/`: tính `lineTotal` theo §2.6; kiểm tra dùng chung cho thêm giỏ và tạo đơn: sản phẩm tồn tại, `available`, giá không đổi, `usingDate` trong cửa sổ bán. Trả lỗi nghiệp vụ dạng giá trị, không ném HTTP.
- `application/booking/`: use case `GetCart`, `AddCartItem` (cộng dồn cùng `productId` + `usingDate`, ghi `add_to_cart` ở nền qua `BrowseEventRecorder`), `UpdateCartItem`, `RemoveCartItem`; port repository giỏ.
- `infrastructure/persistence/`: `PostgresCartRepository` (`app.carts`, `app.cart_items`, qua `DATABASE_URL`).
- `api/v1/routes/booking.py`, `api/v1/schemas/booking.py`; nối trong `main.py`, `api/deps.py`.
- Web: `services/` gọi giỏ qua BFF; `TravelContext` lấy giỏ từ server thay cho state local.
- Test: unit domain/application; contract test response giỏ khớp `CartResponse`; integration với Postgres (`RUN_POSTGRES_INTEGRATION=1`).

### Bước 2 — Contract 🔒

- `paths/booking.yaml`:
  - `POST /bookings`: mô tả mới — `201` là "đã giữ chỗ, chờ thanh toán", trả `payment.checkoutUrl`; thêm `409 BOOKING_PENDING_PAYMENT`, `503 PAYMENT_PROVIDER_UNAVAILABLE`.
  - Thêm `POST /bookings/{referenceCode}/cancel` (body `CancelBookingRequest { reason?: string ≤ 500 }`), response `200 BookingResponse`, lỗi `404`, `409 BOOKING_NOT_CANCELLABLE | BOOKING_ALREADY_PAID`, `503`.
- `paths/payments.yaml` mới: `POST /payments/stripe/webhook`, không `bearerAuth`, header `Stripe-Signature` bắt buộc, `200` không body, `400 INVALID_WEBHOOK_SIGNATURE`. Gắn tag riêng `payments-internal` để client sinh từ OpenAPI của Web bỏ qua.
- `schemas/booking.yaml`, `BookingResponse`:
  - `status`: `const CONFIRMED` → enum `PENDING_PAYMENT | CONFIRMED | PAYMENT_FAILED | EXPIRED | CANCELLED`.
  - Thêm `holdExpiresAt` (date-time | null), `cancellableUntil` (date-time | null), `payment` (`status`, `amount`, `currency`, `checkoutUrl` (chỉ khác null khi `OPEN`), `failedAttempts`, `failureReason`, `refundedAmount`), `cancellation` (`cancelledAt`, `reason`, `refundAmount`) | null.
- `schemas/common.yaml`: thêm 5 mã lỗi `BOOKING_PENDING_PAYMENT`, `BOOKING_ALREADY_PAID`, `BOOKING_NOT_CANCELLABLE`, `PAYMENT_PROVIDER_UNAVAILABLE`, `INVALID_WEBHOOK_SIGNATURE`; `retryable: true` chỉ cho `PAYMENT_PROVIDER_UNAVAILABLE`.
- `openapi.yaml`: thêm ref path và schema.
- Mock `src/shared/mocks/booking/`: `createBooking.201-pending-payment`, `getBooking.200-confirmed`, `getBooking.200-payment-failed`, `getBooking.200-expired`, `getBooking.200-cancelled-refunded`, `createBooking.409-pending-payment`, `cancelBooking.409-too-late`; cập nhật `index.json`.
- Kiểm: `PYTHONDONTWRITEBYTECODE=1 python3 src/shared/contracts/tests/validate_contract.py`.
- Reviewer: Web và Backend (`architecture.md` §6.4).

### Bước 3 — Database 🔒

- `db/vota_schema.sql` và `db/init/01_vota.sql`:
  - `app.bookings.status` CHECK → `pending_payment, confirmed, payment_failed, expired, cancelled`; mặc định `pending_payment`.
  - Thêm cột `hold_expires_at`, `confirmed_at`, `cancelled_at`, `cancel_reason`, `purchase_events_cancelled_at`, `updated_at`.
  - Unique index một phần `bookings_one_pending_per_user ON app.bookings (cdp_user_id) WHERE status = 'pending_payment'`.
  - Bảng `app.payments` theo đề xuất (`booking_id` UNIQUE FK, `checkout_session_id` UNIQUE, `payment_intent_id` UNIQUE, `amount bigint`, `status` CHECK 7 giá trị, `failed_attempts`, `last_failure_code`, `refund_id`, `checkout_url`); index `(status, updated_at)` cho job đối soát.
  - `GRANT` cho `vota_app` trên `app.payments`.
- `db/migrations/0003_booking_payments.sql`: idempotent (`ADD COLUMN IF NOT EXISTS`, đổi CHECK bằng `DROP CONSTRAINT IF EXISTS` rồi `ADD`), đơn cũ giữ `confirmed`.
- `db/verify.sql`: thêm dòng kiểm cặp trạng thái đơn/thanh toán hợp lệ (spec §5.2), không có hai đơn `pending_payment` cùng user.
- Seed `src/data_collection/seed/`: booking của P1 thêm một dòng `app.payments` `provider = 'seed'`, `status = succeeded` (thêm `seed` vào CHECK của `provider`). Dòng verify "P1 booking <-> event" giữ nguyên.
- Cập nhật `docs/spec/DATABASE_SCHEMA.md` trong cùng commit.
- Kiểm: `make db-migrate` trên DB local có dữ liệu; `psql "$SEED_DATABASE_URL" -f db/verify.sql` PASS (trừ hai dòng FAIL dự kiến của catalog tổng hợp, `AGENTS.md` §6.5).

### Bước 4 — Domain booking 🔒

`src/backend/app/domain/booking/`, không import SDK hay DB:

- `status.py`: enum `BookingStatus`, `PaymentStatus`; bảng chuyển trạng thái hợp lệ; hàm chuyển ném lỗi domain khi sai (máy trạng thái ở spec §5).
- `hold.py`: `HoldPolicy(minutes ≥ 30)`, `is_active(now)`.
- `cancellation.py`: `cancellable_until(items, tz = Asia/Ho_Chi_Minh)`, `decide(booking, now) → CancelDecision` (`EXPIRE_SESSION`, `REFUND_FULL`, `ALREADY_CANCELLED`, `TOO_LATE`, `NOT_ACTIVE`).
- `payment_failure.py`: đổi `decline_code` của Stripe sang `failureReason` (spec §10.2); `MAX_FAILED_ATTEMPTS`.
- `reference_code.py`: `VOTA-YYYYMMDD-XXXX`.
- Test: `tests/unit/domain/booking/` phủ mọi cạnh của máy trạng thái, biên `cancellableUntil` (23:59 và 00:00), đơn nhiều `usingDate`, bảng `decline_code`. Mục tiêu phủ ≥ 80%.

### Bước 5 — Application: port và use case 🔒

- `application/ports/payment_gateway.py` (một port một file):
  - `create_checkout_session(booking, lines, expires_at, urls, idempotency_key) → CheckoutSession`
  - `expire_checkout_session(session_id) → ExpireResult` (`EXPIRED | ALREADY_COMPLETE | ALREADY_EXPIRED`)
  - `retrieve_checkout_session(session_id) → CheckoutSession`
  - `create_refund(payment_intent_id, amount, idempotency_key) → Refund`
  - `parse_webhook(raw_body, signature_header) → PaymentEvent` (lỗi chữ ký ném `InvalidWebhookSignature`)
  - `PaymentProviderUnavailable` cho timeout/5xx.
- Port repository `BookingRepository`, `PaymentRepository` (khoá dòng `for_update`, tìm theo `checkout_session_id`, danh sách cần đối soát).
- Use case trong `application/booking/`:
  - `CreateBookingHold` (spec §6.2): kiểm giỏ, chặn đơn giữ thứ hai (đơn cũ quá hạn thì đối soát ngay), gọi gateway rồi commit, lỗi commit thì đóng phiên.
  - `GetBooking`: chỉ chủ đơn; `checkoutUrl` chỉ khi `OPEN`.
  - `HandlePaymentEvent` (spec §6.3, §7.3, §8.3, §9.2): `checkout.session.completed`, `checkout.session.expired`, `payment_intent.payment_failed`, `refund.updated`, `charge.dispute.created` (chỉ log); event khác bỏ qua.
  - `CancelBooking` (spec §9.3).
  - `ReconcileBookings` (spec §8.2): bốn việc dở dang.
- `purchase_events.py`: tách thêm hàm `record_then_commit` **không** bù trừ, dùng cho đường xác nhận sau khi đã thu tiền; giữ `commit_with_purchase_events` cho đường cũ. Ghi rõ lý do trong docstring (CDP §3.3 mục 4).
- `tests/fakes/fake_payment_gateway.py`: giả lập phiên, từ chối N lần, timeout, phiên đã complete, refund pending/failed; không gọi mạng.
- Test: `tests/unit/application/booking/` với fake gateway + fake CDP + repository in-memory, mỗi nhánh đỏ trong spec một test.

### Bước 6 — Infrastructure 🔒

- `requirements.txt`: thêm `stripe` (ghim phiên bản chính khi cài).
- `infrastructure/payments/stripe_gateway.py`: `StripeClient` với timeout 10 giây, tự thử lại 2 lần; mọi lệnh ghi có `Idempotency-Key`; Checkout Session `mode=payment`, `currency=vnd`, `line_items[].price_data` (tên sản phẩm, `unit_amount` = đơn giá VND), `expires_at`, `client_reference_id` và `metadata.bookingId`, `payment_intent_data.metadata.bookingId`, `customer_email`, `locale=vi`, `submit_type=book`, `payment_method_types=[card]`; kiểm chữ ký bằng `STRIPE_WEBHOOK_SECRET` với raw body. Nếu SDK không có hàm async thì chạy trong threadpool.
- `infrastructure/persistence/`: `PostgresBookingRepository`, `PostgresPaymentRepository`.
- `core/config.py`: `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `PAYMENT_PROVIDER` (`stripe | fake`), `BOOKING_HOLD_MINUTES` (≥ 30), `PAYMENT_MAX_FAILED_ATTEMPTS`, `PUBLIC_WEB_URL`. Từ chối khởi động khi khoá bắt đầu bằng `sk_live_`.
- Test integration: repository với Postgres thật; gateway Stripe chỉ chạy khi có `RUN_STRIPE_INTEGRATION=1` và khoá test.

### Bước 7 — API và composition root 🔒

- `api/v1/routes/booking.py`: `POST /bookings`, `GET /bookings/{referenceCode}`, `POST /bookings/{referenceCode}/cancel`.
- `api/v1/routes/payments.py`: `POST /payments/stripe/webhook` đọc raw body (`await request.body()`) trước mọi parse JSON; trả `200` nhanh, không trả chi tiết lỗi cho Stripe.
- `api/errors.py`: 5 mã lỗi mới, `Retry-After` cho `503`.
- `main.py`: chọn gateway theo `PAYMENT_PROVIDER`; chạy `ReconcileBookings` 5 phút/lần trong `lifespan` (tắt được bằng cấu hình cho test).
- `tests/architecture/`: chạy lại, không import `stripe` ngoài `infrastructure/payments/`.
- `docker-compose.yml`, `.env.example`: truyền biến Stripe vào backend (giá trị rỗng).

### Bước 8 — Frontend 🔒

- `services/booking.ts`: `createBooking`, `getBooking`, `cancelBooking` qua BFF; kiểu sinh từ OpenAPI.
- `CheckoutView`: bỏ `createBooking` local; gửi `POST /bookings`, thành công thì `window.location.assign(payment.checkoutUrl)`; `409 BOOKING_PENDING_PAYMENT` mở hộp thoại Tiếp tục / Huỷ đơn đó; thay băng "Bản demo: không có thanh toán thật" bằng ghi chú chế độ test.
- `/booking/[referenceCode]`: hiển thị theo 5 trạng thái (spec §5.1); đồng hồ đếm ngược theo `holdExpiresAt`; `?payment=return` thì hỏi lại 2 giây/lần, tối đa 15 lần; `payment.status = SUCCEEDED` mà đơn chưa `CONFIRMED` thì hiện "Đã nhận thanh toán, đang xác nhận"; hộp thoại huỷ hiện số tiền hoàn và `cancellableUntil`; gọi `/recommendations` chỉ khi `CONFIRMED`.
- Bảng lỗi `hop-dong-tich-hop-frontend.md` §8 thêm 4 mã mới (spec §10.1).
- Test: component test cho từng trạng thái và từng mã lỗi.

### Bước 9 — Đồng bộ tài liệu 🔒

- `hop-dong-tich-hop-backend.md` §7.2–§7.4 (luồng mới, bỏ câu "Không có huỷ, không có hoàn tiền"), §8.2 (mã lỗi).
- `hop-dong-tich-hop-frontend.md` §4.5, §4.6, §8.
- `hop-dong-tich-hop-cdp.md` §5: `purchase` ghi khi thanh toán thành công; không huỷ event khi tiền đã thu; `cancel_purchases` dùng cả cho khách huỷ.
- `product.md` §1.3 và §4.5.
- `src/backend/README.md`: endpoint mới, biến môi trường, cách chạy `stripe listen`.
- Entry `history/` cho từng bước.

### Bước 10 — Kiểm thử và nghiệm thu 🔒

Chuẩn bị một lần: tài khoản Stripe test của nhóm, cài Stripe CLI, `stripe login`, rồi `stripe listen --forward-to localhost:8000/api/v1/payments/stripe/webhook` và chép `whsec_…` vào `.env`.

| # | Kịch bản | Cách tạo | Kỳ vọng |
|---|---|---|---|
| 1 | Thành công | Thẻ `4242 4242 4242 4242` | `CONFIRMED`, event `purchase`, gợi ý đổi |
| 2 | Từ chối chung | `4000 0000 0000 0002` ba lần | Lần 1–2 còn `PENDING_PAYMENT`; lần 3 `PAYMENT_FAILED`, `TOO_MANY_ATTEMPTS` |
| 3 | Không đủ số dư | `4000 0000 0000 9995` | `failureReason = INSUFFICIENT_FUNDS` |
| 4 | Thẻ hết hạn | `4000 0000 0000 0069` | `EXPIRED_CARD` |
| 5 | 3DS | `4000 0027 6000 3184`, chọn Complete / Fail | Complete → `CONFIRMED`; Fail → `AUTHENTICATION_FAILED` |
| 6 | Stripe không phản hồi | `PAYMENT_PROVIDER=fake` chế độ timeout | `503 PAYMENT_PROVIDER_UNAVAILABLE`, không có dòng nào trong `app.bookings` |
| 7 | CDP lỗi khi xác nhận | Fake CDP ném lỗi, sau đó bỏ lỗi; `stripe events resend <evt_id>` | Payment `SUCCEEDED`, đơn chờ; sau khi gửi lại: `CONFIRMED`, event không bị huỷ |
| 8 | Webhook trùng | `stripe events resend` với event đã xử lý | Không đổi trạng thái, không có event CDP thứ hai |
| 9 | Webhook sai chữ ký | Gửi tay với header sai | `400`, dữ liệu không đổi |
| 10 | Hết hạn giữ chỗ | Để hết 30 phút, hoặc `stripe checkout sessions expire <cs_id>` | `EXPIRED`, giỏ còn |
| 11 | Đơn thứ hai khi đang giữ | Bấm Thanh toán lần nữa | `409 BOOKING_PENDING_PAYMENT` |
| 12 | Huỷ trước khi trả | Nút Huỷ ở trang giữ chỗ | `CANCELLED`, phiên Stripe `expired` |
| 13 | Huỷ sau khi trả, trong hạn | Đơn có `usingDate` sau 3 ngày | `CANCELLED`, refund trong Dashboard, event `purchase` bị huỷ |
| 14 | Huỷ quá hạn | Đơn có `usingDate` là ngày mai | `409 BOOKING_NOT_CANCELLABLE`, `TOO_LATE` |
| 15 | Webhook lỡ | Tắt Backend khi phiên hết hạn, bật lại | Job đối soát chuyển đơn `EXPIRED` trong 10 phút |

Kịch bản 2–15 cũng có bản unit/application test chạy với fake gateway trong CI (không cần mạng). Definition of Done: `docs/prd/implementation-plan.md` §4 — contract PASS, phủ ≥ 80% cho `domain`/`application` booking, `db/verify.sql` PASS, tài liệu và `history/` cập nhật.

## Rủi ro và câu hỏi mở

1. **Webhook cần URL công khai trên staging.** Hiện Web đi qua BFF; chưa rõ FastAPI staging có mở ra Internet không. Cần chốt cách mở riêng đường `/api/v1/payments/stripe/webhook` (reverse proxy) hoặc chọn phương án Q7 đi qua Next.js.
   - **Đã chốt 2026-10-13:** nginx đưa thẳng `/api/v1/payments/stripe/webhook` tới backend của slot đang hoạt động, không qua Next.js (phương án C). Chi tiết: `history/2026-10-13-stripe-webhook-nginx-truc-tiep.md`.
2. **Tài khoản Stripe của nhóm.** Cần một tài khoản test chung (đăng ký với quốc gia Stripe hỗ trợ, chỉ dùng test mode), chia khoá test qua kênh bí mật. Mỗi dev chạy `stripe listen` nhận `whsec_` riêng.
3. **Mức tiền tối thiểu của Stripe** tính theo tiền tệ thanh toán về tài khoản (ví dụ 0,50 USD). Đơn VND trong catalog đều vượt xa mức này; chỉ cần lưu ý nếu có sản phẩm giá 0.
4. **`eventGroupId` đang lệch sẵn giữa contract và DDL:** contract cho mỗi nhóm điểm đến một `eventGroupId` (`BookingGroup.eventGroupId`), DDL để một `event_group_id` UNIQUE mỗi booking. Không thuộc phạm vi plan này nhưng ảnh hưởng cách ghi `purchase`; cần quyết định trước bước 5.
5. **ERD trong `data-model.md` lệch DDL từ trước** (`booking_code`/`reference_code`, `user_id`/`cdp_user_id`). Đề xuất chỉ thêm phần thanh toán, không sửa các chỗ lệch cũ.
6. **Job đối soát chạy trong tiến trình Backend.** Đủ cho MVP nhờ `SKIP LOCKED`; nếu sau này tách worker thì chỉ chuyển nơi gọi `ReconcileBookings`.
7. **Giữ chỗ không trừ tồn kho.** Hai khách có thể cùng giữ chỗ và cùng trả tiền cho một phòng có lịch `1`. Chấp nhận trong MVP vì không có tồn kho; nếu không chấp nhận thì phải mở rộng phạm vi (đề xuất riêng).
