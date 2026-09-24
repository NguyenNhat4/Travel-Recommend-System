# Triển khai booking: giỏ server-side, giữ chỗ, thanh toán Stripe (MoR), thất bại, huỷ và hoàn tiền

- Ngày: 2026-09-24
- Tác giả: mihhquan / Claude Code
- Nhánh: feat/booking
- Trạng thái: dang dở — code, test và tài liệu xong; nghiệm thu với Stripe test thật (plan bước 10) chưa chạy vì chưa có khoá test
- Phạm vi: contract | backend | frontend | db | docs

## Mục tiêu

Người dùng hỏi phần booking đã xong chưa và yêu cầu làm tiếp. Làm theo `docs/plan/2026-09-24-booking-thanh-toan-stripe.md` (bước 1–9) và spec `docs/spec/booking/so-do-luong-dat-cho-thanh-toan.md`. Phục vụ FR-BKG-01…07, NFR-REL-02, NFR-SEC-01, NFR-SEC-03; AC-BKG-01…04. Không lệch PRD: đề xuất `docs/prd/update-archive/2026-09-24-thanh-toan-stripe-mor.md` đã chốt và áp dụng (`history/2026-09-24-ap-dung-de-xuat-thanh-toan-stripe-mor.md`).

Lúc bắt đầu phiên này, working tree đã có contract, DDL/migration, domain, use case, adapter Stripe và route booking từ phiên trước nhưng **chưa có entry lịch sử và chưa commit**. Frontend vẫn chạy giỏ/checkout bằng state local; tài liệu spec (bước 9) chưa đồng bộ. Entry này ghi cả phần đã có trong working tree lẫn phần làm thêm.

## File thay đổi

Contract / mock
- `src/shared/contracts/openapi.yaml` — sửa: version 1.5.0; tag `payments-internal`; path `/bookings/{referenceCode}/cancel`, `/payments/stripe/webhook`; schema `BookingStatus`, `PaymentStatus`, `PaymentFailureReason`, `PaymentInfo`, `CancellationInfo`, `CancelBookingRequest`.
- `src/shared/contracts/paths/booking.yaml` — sửa: `POST /bookings` thành giữ chỗ + phiên Stripe (thêm `503`); thêm `POST /bookings/{referenceCode}/cancel`.
- `src/shared/contracts/paths/payments.yaml` — thêm: webhook Stripe, không `bearerAuth`, header `Stripe-Signature`.
- `src/shared/contracts/schemas/booking.yaml` — sửa: `BookingResponse` thêm `status` enum 5 giá trị, `holdExpiresAt`, `cancellableUntil`, `payment`, `cancellation`.
- `src/shared/contracts/schemas/common.yaml` — sửa: 5 mã lỗi mới; `retryable` cho `PAYMENT_PROVIDER_UNAVAILABLE`; `details` của `BOOKING_PENDING_PAYMENT` gồm `holdExpiresAt`.
- `src/shared/mocks/booking/createBooking.201-default.json`, `createBooking.201-two-groups.json`, `getBooking.200-default.json` — sửa: theo shape mới (`PENDING_PAYMENT` / `CONFIRMED`).
- `src/shared/mocks/booking/createBooking.409-pending-payment.json`, `createBooking.503-payment-unavailable.json`, `cancelBooking.409-too-late.json`, `getBooking.200-payment-failed.json`, `getBooking.200-expired.json`, `getBooking.200-cancelled-refunded.json` — thêm.
- `src/shared/mocks/index.json` — sửa: đăng ký fixture mới.

Database
- `db/vota_schema.sql`, `db/init/01_vota.sql` — sửa (giữ byte-identical): `app.bookings.status` 5 giá trị, mặc định `pending_payment`; cột `updated_at`, `hold_expires_at`, `confirmed_at`, `cancelled_at`, `cancel_reason`, `purchase_events_cancelled_at`; unique index `bookings_one_pending_per_user`; `app.booking_items.special_request`; bảng `app.payments`.
- `db/migrations/0003_booking_payments.sql`, `db/migrations/0004_booking_item_special_request.sql` — thêm: migration idempotent tương ứng; đơn cũ nhận dòng payment `provider = 'seed'`.
- `db/verify.sql` — sửa: thêm dòng kiểm cặp trạng thái đơn/thanh toán (theo bảng spec §5.2) và một đơn giữ chỗ mỗi user. Phiên này sửa lại dòng cặp trạng thái: bản trước đánh FAIL nhầm đơn `payment_failed` đã hoàn tiền (lệch số tiền) và bỏ sót payment `NULL` của đơn `pending_payment`.
- `src/data_collection/seed/database.py` — sửa: `--reset` truncate cả `app.payments`; booking seed nhận dòng payment `seed` + `confirmed_at`.

Backend
- `src/backend/app/domain/booking/` — thêm `status.py`, `hold.py`, `cancellation.py`, `payment_failure.py`, `pricing.py`, `reference_code.py`, `models.py`; sửa `__init__.py`.
- `src/backend/app/application/booking/` — thêm `cart.py`, `create_hold.py`, `payment_events.py`, `settlement.py`, `cancel.py`, `reconcile.py`, `queries.py`, `views.py`, `errors.py`; sửa `__init__.py`, `purchase_events.py` (thêm `record_then_commit` không bù trừ).
- `src/backend/app/application/ports/payment_gateway.py`, `booking_store.py`, `cart_repository.py`, `product_catalog.py` — thêm.
- `src/backend/app/infrastructure/payments/__init__.py`, `stripe_gateway.py`, `fake_gateway.py` — thêm.
- `src/backend/app/infrastructure/persistence/postgres_booking.py` — thêm. Phiên này sửa `get_by_id`: kiểm uuid trước khi truy vấn (xem Quyết định).
- `src/backend/app/api/v1/routes/booking.py`, `routes/payments.py`, `schemas/booking.py` — thêm.
- `src/backend/app/api/v1/router.py`, `api/deps.py` (`get_use_case`), `api/errors.py` (handler `BookingError`, `Retry-After`) — sửa.
- `src/backend/app/core/config.py` — sửa: biến Stripe, từ chối khoá `sk_live_`/`rk_live_`, `BOOKING_RECONCILE_INTERVAL_SECONDS`.
- `src/backend/app/main.py` — sửa: `build_booking`, job đối soát trong `lifespan`, version 1.5.0.
- `src/backend/tests/fakes/booking.py`, `tests/unit/domain/booking/test_booking_domain.py`, `tests/unit/application/booking/test_booking_flow.py` — thêm (từ phiên trước).
- `src/backend/tests/unit/infrastructure/test_stripe_gateway.py` — thêm: 17 test adapter Stripe trên `httpx.MockTransport` (mã hoá form, `Idempotency-Key`, retry 5xx, 4xx không retry, đóng phiên đã đóng, chữ ký webhook đúng/sai/cũ, từ chối khoá live).
- `src/backend/tests/contract/test_booking_contract.py` — thêm: 10 test HTTP khớp contract cho giỏ, giữ chỗ, `409`, `503` + `Retry-After`, webhook sai chữ ký, xác nhận, huỷ có hoàn tiền, huỷ đơn hết hạn, huỷ quá hạn.
- `src/backend/tests/integration/test_booking_postgres.py` — thêm: 2 test adapter Postgres (giỏ, đơn, unique index giữ chỗ, truy vấn đối soát), gated `RUN_POSTGRES_INTEGRATION=1`, tự dọn dữ liệu.
- `src/backend/README.md` — sửa: endpoint booking, biến Stripe, `stripe listen`, thẻ test, bảng lớp.

Frontend
- `src/frontend/src/services/booking.ts` — thêm: client giỏ/đơn/huỷ qua BFF, kiểu sinh từ OpenAPI, hằng polling.
- `src/frontend/src/services/http.ts` — sửa: thêm `ApiError`, `toApiError`, `apiJson` (lỗi mạng → `NETWORK_ERROR`).
- `src/frontend/src/context/TravelContext.tsx` — sửa: giỏ là `CartResponse` phía server (tải lại khi đăng nhập, bỏ response cũ về muộn), `addToCart`/`removeFromCart`/`updateCartItem` gọi API; bỏ `createBooking`, `clearCart` local; `bookings` là các `BookingResponse` đã thấy trong phiên.
- `src/frontend/src/components/cart/CartView.tsx` — sửa: dữ liệu và tổng tiền từ `CartResponse`; mục hết chỗ viền đỏ, khoá nút đặt; "Thường được đặt cùng" gọi `/recommendations`.
- `src/frontend/src/components/checkout/CheckoutView.tsx` — sửa: form liên hệ + tên khách theo từng mục, chọn phương thức (chỉ Stripe, còn lại "Sắp có"), `POST /bookings` rồi chuyển sang Stripe; xử lý `BOOKING_PENDING_PAYMENT` (hộp thoại tiếp tục/huỷ), `PRICE_CHANGED`, `PRODUCT_UNAVAILABLE`, `DATE_OUT_OF_RANGE`, `503`, lỗi mạng.
- `src/frontend/src/components/confirmation/ConfirmationView.tsx` — sửa: trang đơn theo 5 trạng thái, đồng hồ giữ chỗ, polling sau khi quay về từ Stripe, hộp thoại huỷ, gợi ý chỉ khi `CONFIRMED`.
- `src/frontend/src/components/confirmation/bookingLabels.ts` — thêm: nhãn trạng thái, lý do thất bại, định dạng tiền/giờ Việt Nam.
- `src/frontend/src/app/(storefront)/booking/[referenceCode]/page.tsx` — sửa: truyền `?payment=` từ `searchParams`.
- `src/frontend/src/hooks/useAssistantCart.ts` — sửa: thêm từng mục tuần tự qua API, tổng kết một toast.
- `src/frontend/src/services/assistant.ts` — sửa: `mapProductSummaryToProduct` giữ `availableFrom/To` để chọn ngày mặc định hợp lệ.
- `src/frontend/src/components/common/Header.tsx`, `MobileTabBar.tsx`, `DebugPanel.tsx` — sửa: dùng `cartCount` và `BookingResponse`.
- `src/frontend/src/types/travel.ts` — sửa: bỏ `CartItem`, `BookingRecord`, `BookingContact`, `BookingGuestDetails` (không còn dùng).
- `src/frontend/src/types/api.gen.ts` — sửa: sinh lại bằng `npm run generate:api-types`.
- `src/frontend/tests/unit/bookingService.test.ts`, `checkoutView.test.tsx`, `confirmationView.test.tsx` — thêm: 21 test.
- `src/frontend/README.md` — sửa: một đoạn về luồng giỏ/checkout/Stripe.

Tài liệu
- `docs/spec/booking/so-do-luong-dat-cho-thanh-toan.md` — sửa: trạng thái "đã chốt và đã triển khai"; §5.2 thêm cặp `PAYMENT_FAILED`/`EXPIRED` + `REFUND_*`; §8.2 ghi khác biệt job đối soát; §9, §10.1 bỏ chữ "chờ chốt".
- `docs/spec/hop-dong-tich-hop-backend.md` — sửa: §1, §7.2 (giữ chỗ, webhook, `PRICE_CHANGED`), §7.3 (huỷ), §7.4 (ghi `purchase` khi đã thu tiền), §8.2 (5 mã lỗi), §8.5, tiêu chí 11–13.
- `docs/spec/hop-dong-tich-hop-frontend.md` — sửa: §3 query `payment`, §4.5, §4.6, §8, §11.
- `docs/spec/hop-dong-tich-hop-cdp.md` — sửa: §5 viết lại theo luồng thu tiền rồi mới ghi `purchase`, không bù trừ sau khi đã thu; §7.
- `docs/spec/product.md` — sửa: §1.3, §4.5, §4.6.
- `docs/spec/DATABASE_SCHEMA.md` — sửa: số bảng, §2, ERD `app`, §7, khối DDL §11 chép lại từ `db/vota_schema.sql`.
- `docs/plan/2026-09-24-booking-thanh-toan-stripe.md` — sửa: thêm bảng tiến độ.
- `history/2026-09-24-trien-khai-booking-thanh-toan-stripe.md` — thêm: entry này.

Ngoài `src/`, `docs/`, `db/`
- `.env.example`, `docker-compose.yml` — sửa: biến `STRIPE_*`, `PAYMENT_PROVIDER`, `BOOKING_HOLD_MINUTES`, `PAYMENT_MAX_FAILED_ATTEMPTS`, `PUBLIC_WEB_URL` (giá trị rỗng/mặc định).

## Quyết định

- **Adapter Stripe gọi REST bằng `httpx`, không thêm SDK `stripe`** (plan bước 6 định thêm SDK). Bốn endpoint là đủ, test offline bằng `MockTransport`, không thêm dependency. Idempotency-Key, timeout 10 giây, thử lại 2 lần với lỗi mạng/5xx/429 giữ đúng plan.
- **Sửa lỗi `PostgresBookingStore.get_by_id`** (test integration phát hiện): bản trước bắt `InvalidTextRepresentation` khi `booking_id` không phải uuid rồi trả `None`, nhưng Postgres đã huỷ transaction, nên truy vấn tiếp theo trong cùng transaction (ví dụ webhook tìm lại theo `session_id`) lỗi `InFailedSqlTransaction` → webhook trả 500 mãi. Giờ kiểm uuid ở Python trước khi truy vấn.
- **`PRICE_CHANGED` xử lý bằng `PATCH` mục giỏ**: Backend so với giá snapshot lúc thêm giỏ, `GET /cart` không đổi snapshot, nên cách cũ "gọi lại `GET /cart` rồi bấm lại" sẽ lặp `PRICE_CHANGED`. `PATCH` với `quantity` hiện tại ghi lại snapshot (hành vi có sẵn của `CartService.update`). Đã sửa `hop-dong-tich-hop-frontend.md` §8 và backend §7.2 cho khớp.
- **Một `eventGroupId` cho cả đơn**: theo DDL (`app.bookings.event_group_id` UNIQUE) và `DATABASE_SCHEMA.md` §5 ("một checkout = một chuyến") — hai nguồn ưu tiên cao hơn hợp đồng tích hợp theo `AGENTS.md` §2. Tiêu chí 12 cũ của `hop-dong-tich-hop-backend.md` ("hai điểm đến sinh hai `eventGroupId` khác nhau") mâu thuẫn; đã ghi rõ là đang chờ người dùng quyết định, không đổi DDL.
- **Job đối soát không chờ 5 phút ân hạn** như sơ đồ §8.2: mọi bước khoá dòng đơn và idempotent nên chạy trùng với webhook không sinh sai lệch. Đã ghi khác biệt vào spec.
- **Frontend giữ cấu trúc `components/` hiện có**, không tạo `features/booking/` (`architecture.md` §6.1): toàn bộ frontend hiện chưa có `features/`; tạo riêng cho booking sẽ làm cấu trúc lệch nửa vời. Nhãn hiển thị đặt ở `components/confirmation/bookingLabels.ts`, theo tiền lệ `components/assistant/assistantLabels.ts`.
- **`bookings` trong `TravelContext` chỉ là các đơn đã thấy trong phiên**: contract không có API liệt kê đơn; Header hiển thị các đơn đó theo trạng thái thật.
- Thêm giỏ không chọn ngày (thêm nhanh) dùng ngày mai giờ Việt Nam hoặc `availableFrom` nếu muộn hơn; Backend vẫn kiểm cửa sổ bán và trả `DATE_OUT_OF_RANGE` kèm khoảng ngày để toast.

## Kiểm tra

- `PYTHONDONTWRITEBYTECODE=1 python3 src/shared/contracts/tests/validate_contract.py` (venv backend): **PASS** — 83 schemas, 60 fixtures; CDP clone 12 schemas, 7 fixtures.
- Backend, không DB: `python -m pytest -q src/backend/tests` → 357 passed, 15 skipped (gồm 17 test Stripe adapter, 10 test contract booking mới; test kiến trúc pass).
- Backend + Postgres local (`RUN_POSTGRES_INTEGRATION=1`), đo độ phủ bằng `coverage run`: 369 passed, 2 skipped, **1 failed không liên quan**: `test_local_postgres_adapters.py::test_database_roles_enforce_the_two_connection_boundary` đòi `cdp.products = 11387`, DB local đang có 10320 (catalog cũ). Độ phủ: `domain/booking` 98%, `application/booking` 88%, `infrastructure/payments` 94%, `postgres_booking.py` 95%.
- `make db-migrate-status`: 0001–0004 đã áp trên DB local. `db/verify.sql` (psql trong container, superuser): hai dòng booking mới **PASS**; `products >= 11387: FAIL (10320)` và `profiles = 2000: FAIL (2001)` là trạng thái DB local có từ trước (catalog cũ, một tài khoản đăng ký thêm), không do thay đổi này.
- E2E qua HTTP thật (uvicorn cổng 8010, Postgres + `LocalCdpClient`, `PAYMENT_PROVIDER=fake`, user `test50@vota.demo`): 15/15 bước PASS — đăng nhập; thêm phòng + vé; `201 PENDING_PAYMENT` có `checkoutUrl`, tổng đơn = tổng giỏ; đơn thứ hai `409` kèm mã đơn cũ; webhook sai chữ ký `400`; thẻ bị từ chối giữ đơn, đếm lần, `INSUFFICIENT_FUNDS`; webhook đã trả tiền → `CONFIRMED`; webhook trùng vẫn đúng 2 event `purchase`; mục đã đặt rời giỏ; huỷ → `CANCELLED` + `REFUNDED`, event bị huỷ trên CDP; huỷ lặp lại trả kết quả cũ; không token → `401`. Dữ liệu test đã dọn. Log không chứa email, số điện thoại hay token.
- Frontend: `npx tsc --noEmit` sạch; `npx eslint .` 0 lỗi (7 cảnh báo có sẵn ở file khác); `npx vitest run` 97 passed (21 test mới); `npx next build --webpack` build thành công (đã hoàn nguyên `next-env.d.ts` do build sửa).
- **Chưa chạy**: 15 kịch bản plan bước 10 với Stripe test thật (thẻ `4242…`, `4000…0002`, 3DS, `stripe events resend`), chưa thử trên trình duyệt.

## Còn lại / rủi ro

- **Cần người dùng cung cấp** để nghiệm thu AC-BKG-01…04 với Stripe thật: khoá test `sk_test_…` của tài khoản Stripe chung của nhóm (đặt vào `.env` là `STRIPE_SECRET_KEY`, không gửi qua chat), cài Stripe CLI và `stripe login` để lấy `STRIPE_WEBHOOK_SECRET` từ `stripe listen`.
- **Cần người dùng quyết định**: giữ một `eventGroupId` cho cả đơn (DDL hiện hành) hay tách theo điểm đến như tiêu chí 12 cũ của hợp đồng backend. Tách thì phải đổi DDL (`event_group_id` sang `booking_items` hoặc bảng nhóm), migration và luồng ghi `purchase`.
- Webhook trên staging cần URL công khai tới FastAPI (`/api/v1/payments/stripe/webhook`); chưa chốt cách mở (plan, rủi ro 1).
- Trang chi tiết sản phẩm và vài khối gợi ý ở Web vẫn dùng catalog tĩnh (`src/frontend/src/data/catalog.ts`, id kiểu `nt-hotel-01`); Backend chưa có `GET /products/{id}`. Thêm các sản phẩm tĩnh đó vào giỏ sẽ nhận `PRODUCT_NOT_FOUND` ("hiện không bán trên V-OTA"); sản phẩm thật từ Search, Recommendation, Assistant thêm được. Ngoài phạm vi booking (catalog).
- `app.booking_items.line_total` (cột GENERATED `unit_price * quantity`) không nhân số đêm khách sạn; code không đọc cột này (tổng tính ở domain), nhưng truy vấn SQL tay sẽ ra sai với khách sạn. DDL có từ trước, chưa sửa.
- Trùng mã đặt chỗ (xác suất rất nhỏ) khiến `CreateBookingHold` sinh mã mới sau khi phiên Stripe đã tạo với `success_url` của mã cũ; đơn vẫn xác nhận qua webhook nhưng trang quay về sẽ 404.
- `FakeGateway` (`PAYMENT_PROVIDER=fake`) trả `checkoutUrl` giả, không mở được trên trình duyệt; chỉ dùng cho test/offline.
- DB local cần `make demo-db-reset` (xoá state local) để về catalog snapshot 11.387 nếu muốn `db/verify.sql` và test integration cũ PASS hết.
