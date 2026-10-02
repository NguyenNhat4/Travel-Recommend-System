# Áp dụng đề xuất và triển khai: khách sạn, vé máy bay đặt trực tiếp qua đơn nháp

- Ngày: 2026-10-01
- Tác giả: mihhquan / Claude Code
- Nhánh: feat/booking
- Trạng thái: hoàn thành (chờ người dùng nghiệm thu; còn ba kịch bản chưa chạy trên stack thật, xem "Còn lại")
- Phạm vi: docs | contract | db | backend | frontend

## Mục tiêu

Người dùng chốt đề xuất `docs/prd/update-archive/2026-10-01-khach-san-ve-may-bay-dat-truc-tiep.md` (trả lời Q1–Q14 và các câu phụ) và yêu cầu làm theo `docs/plan/2026-10-01-khach-san-ve-may-bay-dat-truc-tiep.md`. Phục vụ FR-BKG-01, FR-BKG-05, FR-BKG-10, FR-BKG-13, FR-AGT-04, FR-CDP-01, FR-USR-03; AC-BKG-13…17. Đề xuất và kế hoạch: entry `2026-10-01-de-xuat-va-plan-khach-san-ve-may-bay-dat-truc-tiep.md`.

Kết quả: giỏ chỉ giữ tour, trải nghiệm, tiện ích (`attraction`, `golf`, `combo`); khách sạn và vé máy bay chỉ đặt trực tiếp qua đơn nháp 30 phút ("Đặt ngay"); khách chưa đăng nhập dùng giỏ và đơn nháp (Redis, 3 ngày) rồi gộp vào tài khoản khi đăng nhập.

## File thay đổi

Đối chiếu bằng `git status`; chia theo nhóm.

PRD, spec, plan (bước 0, 1, 7):

- `docs/prd/requirements.md`, `user-flow.md`, `data-model.md`, `deployment-plan.md`, `test-plan.md` — sửa theo đề xuất đã chốt (FR-BKG-01, FR-AGT-04, FR-BKG-05/10/13, FR-USR-03, FR-CDP-01, AC-BKG-01/02/09/11, thêm AC-BKG-13…17, biến môi trường mới).
- `docs/prd/update-archive/2026-10-01-khach-san-ve-may-bay-dat-truc-tiep.md` — thêm (chuyển từ `update/`, trạng thái `đã áp dụng`).
- `docs/plan/2026-10-01-khach-san-ve-may-bay-dat-truc-tiep.md` — thêm; bảng bước cập nhật trạng thái.
- `docs/spec/booking/dat-truc-tiep-theo-don-nhap.md` — thêm: bộ luật R-DIR, R-DRF, R-CPY, R-CHK, R-RBK, R-GST, R-MRG, R-BFF.
- `docs/spec/hop-dong-tich-hop-backend.md` (§7.1, 7.1a, 7.1b, 7.2, 7.4, 8.2), `hop-dong-tich-hop-frontend.md` (§4.1b, 4.3–4.8, 8), `product.md`, `hop-dong-tich-hop-cdp.md`, `hop-dong-tich-hop-auth.md` (§3.7a, 3.11, 6, 14.1, 16.1), `booking/so-do-luong-dat-cho-thanh-toan.md`, `booking/checkout-nhieu-buoc-hanh-khach.md`, `DATABASE_SCHEMA.md` — sửa cho khớp.
- `docs/guide/hien-thi-hang-ve-may-bay.md` — sửa: vé máy bay đặt qua đơn nháp, không qua giỏ.
- `src/backend/README.md`, `src/frontend/README.md`, `.env.example`, `docker-compose.yml` — sửa: biến `BOOKING_DRAFT_TTL_MINUTES`, `GUEST_BOOKING_TTL_DAYS`, `BOOKING_REDIS_URL`, mô tả luồng mới.

Contract và mock (bước 2):

- `src/shared/contracts/openapi.yaml` (1.13.0), `paths/booking.yaml`, `paths/events.yaml`, `schemas/booking.yaml`, `schemas/catalog.yaml`, `schemas/common.yaml`, `tests/validate_contract.py` — sửa, chỉ thêm: `/booking-drafts*` (gồm `DELETE` mục), `/guest-bookings/merge`, `draftId`, ba mã lỗi.
- `src/shared/mocks/index.json` — sửa (85 fixture); `src/shared/mocks/booking/` — thêm 15 fixture mới (đơn nháp, `410`, `404`, `422 DIRECT_BOOKING_ONLY`, giỏ khách, gộp) và sửa 8 fixture giỏ để bỏ khách sạn, vé máy bay.

Database (bước 3):

- `db/vota_schema.sql`, `db/init/01_vota.sql` (giống hệt nhau), `db/migrations/0007_booking_drafts.sql` (thêm), `db/verify.sql`, `src/data_collection/seed/database.py`.

Backend (bước 4):

- Mới: `domain/booking/draft.py`; `application/booking/{drafts,guest_merge,lines,owner}.py`; `application/ports/{booking_draft_repository,guest_booking_store}.py`; `infrastructure/persistence/guest_booking_store.py`.
- Sửa: `api/deps.py`, `api/errors.py`, `api/v1/routes/booking.py`, `api/v1/schemas/booking.py`, `application/booking/{__init__,cart,create_hold,errors,reconcile,views}.py`, `application/ports/{booking_store,cart_repository}.py`, `core/config.py`, `domain/booking/__init__.py`, `infrastructure/persistence/postgres_booking.py`, `main.py`.
- Test: mới `unit/application/booking/test_booking_drafts.py`, `unit/infrastructure/test_guest_booking_store.py`, `integration/test_guest_booking_redis.py`; sửa `fakes/booking.py`, `contract/test_booking_contract.py`, `integration/test_booking_postgres.py`, `test_booking_flow.py`, `test_checkout_travelers.py`, `test_flight_booking.py`.

Frontend và BFF (bước 5):

- BFF: `services/server/bffSession.ts`, `services/server/proxy.ts` (cookie `vota_guest`, `X-Guest-Id`, tự gộp khi đăng nhập, chặn `guest-bookings` từ trình duyệt).
- Mới: `components/checkout/checkoutSource.ts`.
- Sửa: `services/booking.ts`, `context/TravelContext.tsx` (`startBooking`), `components/checkout/{CheckoutView,OrderSummary,ReviewStep,ServicesStep,TravelersStep,useCheckout}`, `app/(storefront)/checkout/page.tsx` (Suspense), `components/common/{Header,BecauseLine,WhyPopover}.tsx`, `components/detail/ProductDetailView.tsx`, `features/flights/results/FlightResultsView.tsx`, `hooks/useAssistantCart.ts`, `features/itinerary/widget/{WidgetDays,WidgetPlanPanel,useFloatingWidget}`, `components/assistant/{AssistantResultPanel,ItineraryMap}.tsx`, `components/cart/CartView.tsx`, `components/confirmation/{ConfirmationView.tsx,bookingLabels.ts}`, `types/api.gen.ts` (sinh lại).
- Test: mới `tests/api/bff-guest-booking.test.ts`; sửa `assistantResultPanel`, `bookingService`, `cartView`, `checkoutView`, `confirmationView`, `flightResultsView`, `floatingWidgetOpening`, `productDetailView`, `tripPrefill`, `useAssistantCart`.

## Quyết định

- **Coi việc trả lời hết các câu hỏi là chốt đề xuất** ("trả lời hết thì mới bắt tay vào làm"); PRD sửa trước, rồi spec, contract, DDL, code (`AGENTS.md` §8).
- **Cookie `vota_guest` (3 ngày) tách khỏi phiên khách `anon_id` (30 phút).** `anon_id` không giữ được dữ liệu 3 ngày. BFF gắn `X-Service-Token` + `X-Guest-Id`; `guestId` chỉ ở cookie và Redis, không xuống PostgreSQL, không sang CDP. Chạm bề mặt auth nên cần người phụ trách auth rà `hop-dong-tich-hop-auth.md` §3.7a.
- **BFF tự gộp khi đăng nhập** (idempotent); mục trùng giữ bản của tài khoản; `add_to_cart` chỉ ghi cho mục thực sự được chép sang.
- **Bản chép vào giỏ lúc tạo đơn nháp (R-CPY)** thay cho việc dò "bỏ dở thanh toán": tour, tiện ích tự nằm lại giỏ; khách sạn, vé máy bay thì không.
- **Thêm `DELETE /booking-drafts/{id}/items/{cartItemId}`** (bản đầu của spec nói sai là checkout không bỏ mục được).
- **Đọc `?draft=` bằng `useSearchParams`**, không đọc `window.location`: sau `router.push`, trang mới render trước khi location cập nhật, làm trang tưởng là thanh toán giỏ rỗng và đẩy về `/cart`. Header dùng cùng cách, bọc Suspense.
- **Khách chưa đăng nhập không bị kiểm email ở bước Hành khách** (email lấy theo tài khoản khi đăng nhập lúc bấm Thanh toán).
- **Test dùng helper `Basket`** (đi qua đơn nháp) cho các test cũ từng thêm khách sạn, vé máy bay vào giỏ.
- **Q11c:** khách sạn trong lịch trình chưa có hạng phòng thì không có nút Đặt ngay, thẻ vẫn mở trang chi tiết; phần trả hạng phòng do team trợ lý đang xây.

## Kiểm tra

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python src/shared/contracts/tests/validate_contract.py`: PASS (107 schema, 85 fixture; CDP clone 12 schema, 7 fixture).
- `cmp db/vota_schema.sql db/init/01_vota.sql`: giống hệt; `db/migrations/run.py --status`: 7 đã áp, 0 chờ.
- Backend: `RUN_POSTGRES_INTEGRATION=1 RUN_REDIS_INTEGRATION=1 .venv/bin/python -m pytest -q -p no:cacheprovider src/backend/tests/unit/domain src/backend/tests/unit/application/booking src/backend/tests/unit/infrastructure src/backend/tests/unit/api/test_backend_wiring.py src/backend/tests/contract src/backend/tests/architecture src/backend/tests/integration/test_booking_postgres.py src/backend/tests/integration/test_guest_booking_redis.py`: 580 passed.
- Frontend (`src/frontend`): `node_modules/.bin/vitest run --maxWorkers=1`: 49 file, 511 test passed; `tsc --noEmit` không lỗi; `eslint` các file đã đổi không lỗi (chỉ cảnh báo hook có sẵn ở `ItineraryMap.tsx`). Chỉ chạy `--maxWorkers=1` vì máy 7,7 GB RAM từng bị OOM khi chạy song song.
- Chạy thử trên stack thật (Postgres, Redis, Backend build lại bằng `make backend`, web dev `localhost:3000`):
  - Khách chưa đăng nhập: giỏ, Đặt ngay, đăng nhập, gộp (cookie, TTL Redis 259200 s, `guestId` không có trong PostgreSQL, trình duyệt khác không thấy dữ liệu, mục trùng chỉ giữ một): 21/21.
  - Trình duyệt headless (Playwright): trang chi tiết khách sạn không có nút thêm giỏ, `/checkout?draft=` giữ `draft` qua các bước, đồng hồ 30 phút, đăng nhập tại bước Thanh toán rồi tự gửi `POST /bookings` kèm `draftId`, giỏ không còn khối gợi ý: 18/18.
  - Backend cổng thanh toán giả (`PAYMENT_PROVIDER=fake`, cổng 8010, đã tắt): đơn nháp đến `CONFIRMED`, `purchase` +2, giỏ bị gỡ bản chép; `EXPIRED` giữ vé trong giỏ; đặt lại; `410`/`404`; thanh toán giỏ không kèm đơn nháp: 22/22.
- `db/verify.sql`: ba dòng mới PASS ở lần chạy sau bước 3; chưa chạy lại sau code. Hai dòng FAIL từ trước (`profiles = 2000`, `max events per user <= 15`) do dữ liệu local, không liên quan.
- Dữ liệu thử trên DB local (đơn của `test43@vota.demo`, event CDP của `test41`–`test44`) chưa dọn hết; giỏ và đơn nháp đã xoá.

## Còn lại / rủi ro

- Chưa chạy trên stack thật: kịch bản 2 (khứ hồi trên `/flights`), 4 ("Thanh toán tất cả" của trợ lý, nút từng thẻ và ghim bản đồ), 6 (giá đổi giữa chừng). Mới có test tự động.
- Chạy lại `db/verify.sql` trước khi merge.
- Người phụ trách auth rà §3.7a của spec auth.
- Khách sạn trong lịch trình chưa có hạng phòng cần team trợ lý (Q11c).
- Redis đặt chỗ lỗi thì giỏ và đơn nháp của khách trả `503`; production bắt buộc có `BOOKING_REDIS_URL`.
