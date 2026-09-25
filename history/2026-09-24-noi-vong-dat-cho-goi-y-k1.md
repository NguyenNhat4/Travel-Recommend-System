# Nối vòng "đặt xong → gợi ý đúng thứ vừa đặt" bằng engine thật (K1)

- Ngày: 2026-09-24
- Tác giả: nhatnm / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: backend, frontend, contract, docs

## Mục tiêu

Người dùng chốt mục tiêu cốt lõi: khách đặt phòng xong thì trang xác nhận và Home hiện gợi ý khớp với thứ vừa đặt, để chứng minh recommendation system chạy thật (handbook §2, §10; FR-REC-02, FR-BKG-01…04, FR-CAT-02, AC-REC-02, AC-BKG-01). Plan: `/home/nhatnm/.claude/plans/suggest-a-recommedation-solution-toasty-cook.md`.

Rà code thì thấy vòng này đang giả lập. Engine chưa bao giờ nhìn thấy lượt đặt nào:
- Trang chi tiết đọc catalog cứng 29 sản phẩm của frontend.
- Giỏ và checkout chỉ nằm trong React state.
- Backend không có `/products/{id}`, `/cart*`, `/bookings*`, dù contract đã định nghĩa.
- Trang xác nhận dùng simulator `calculateRecommendations`.
- Home gửi `destination` cứng của persona và lặng lẽ chuyển sang simulator khi lỗi.

Engine thì đã sẵn sàng: nó đọc `cdp.events` ở mỗi request, không cache.

## File thay đổi

Contract và tài liệu:
- `src/shared/contracts/schemas/catalog.yaml` — sửa: thêm `ProductDetail.variants[]` (tầng con đặt được: hạng phòng, chuyến bay). Tương thích ngược, người dùng đã chọn phương án này.
- `docs/spec/hop-dong-tich-hop-backend.md`, sửa:
  - §4.2: mô tả `variants[]`.
  - §7.1: chỉ đơn vị `is_bookable` mới vào được giỏ; lịch `attributes.availability` phải trống.
  - §7.2: kiểm lịch trống lúc checkout; một checkout một `eventGroupId` (theo DDL).
- `docs/spec/hop-dong-tich-hop-frontend.md` — sửa: §4.3, hộp đặt chọn phần tử của `variants[]`.
- `src/frontend/src/types/api.gen.ts` — sinh lại từ contract.

Backend:
- `domain/booking/errors.py`, `domain/booking/rules.py`, `domain/booking/__init__.py` — thêm luật thuần: đơn vị đặt được, số đêm, cửa sổ ngày, lịch trống (cùng quy tắc `open_nights` của seed), thành tiền, mã `VOTA-…`, mã chuyến `WEB…`.
- `domain/catalog/models.py`, `domain/catalog/__init__.py` — sửa: tách hàm `price_unit(taxonomy, unit_price)` để dòng booking dùng lại.
- `application/ports/product_catalog.py`, `cart_repository.py`, `booking_repository.py` — thêm ba port.
- `application/catalog/views.py`, `application/catalog/use_cases.py` — thêm `GetProductDetail` và chiếu sang `ProductSummary`/`ProductDetail`.
- `application/booking/views.py`, `cart.py`, `checkout.py`, `__init__.py`:
  - Thêm `CartService`, `Checkout`, `GetBooking`.
  - Checkout dùng lại `commit_with_purchase_events` (có sẵn trước đây nhưng chưa ai gọi).
  - `add_to_cart` ghi qua `BehaviourTracker.track_add_to_cart` (có sẵn trước đây nhưng chưa được nối).
- `infrastructure/persistence/postgres_catalog.py` (sửa: thêm `PostgresProductCatalog`), `postgres_cart.py`, `postgres_bookings.py` (thêm). Booking và việc xoá giỏ nằm trong cùng một transaction.
- `api/v1/routes/cart.py`, `bookings.py` (thêm), `routes/catalog.py` (sửa: `GET /products/{productId}`), `api/v1/schemas/booking.py` (thêm DTO).
- `api/deps.py`, `api/errors.py` (sửa: handler `BookingError` theo bảng mã §8.2), `api/v1/router.py`, `main.py` (nối use case vào composition root).
- Test:
  - Thêm `tests/fakes/booking.py`, `tests/unit/domain/test_booking_rules.py`, `tests/unit/application/test_booking.py` (gồm test K1), `tests/unit/api/test_booking_routes.py`, `tests/integration/test_booking_postgres.py`.
  - Sửa `tests/unit/api/test_backend_wiring.py`.

Frontend:
- `src/services/booking.ts` — thêm:
  - Gọi `/products/{id}`, `/cart*`, `/bookings*`.
  - `ApiError` theo Error Envelope.
  - Hàm chiếu sang kiểu UI.
  - `isOpen`/`firstOpenDate` hiển thị trước tình trạng chỗ, cùng quy tắc với backend.
- `src/context/TravelContext.tsx` — sửa:
  - Giỏ, tổng tiền và booking lấy từ backend; tải giỏ khi có phiên.
  - `addToCart` thành async, trả boolean.
  - Thêm `loadBooking`.
- `src/components/detail/ProductDetailView.tsx` — viết lại: dữ liệu từ backend, danh sách hạng phòng/chuyến bay kèm trạng thái còn chỗ theo ngày.
- `src/components/confirmation/ConfirmationView.tsx` — viết lại:
  - Đơn lấy từ state hoặc `GET /bookings/{ref}`.
  - Gợi ý thật `GET /recommendations?k=4&destination=…`.
  - Checklist chuyến và dòng "Vì bạn vừa đặt …".
  - Không dùng simulator.
- `src/components/cart/CartView.tsx`, `checkout/CheckoutView.tsx` — sửa:
  - Tiền lấy từ `CartResponse.total`.
  - Phần "Thường được đặt cùng" dùng engine thật.
  - Kiểm số điện thoại theo pattern của contract; hiện lỗi của backend.
  - Chặn lối "giỏ rỗng → /cart" đè lên trang xác nhận.
- `src/components/home/HomeView.tsx` — sửa: bỏ state khởi đầu bằng simulator, bỏ `destination` cứng của persona, lỗi thì hiện "Chưa tải được gợi ý · Thử lại" (frontend §4.1).
- `src/services/recsys.ts` — sửa: `fetchRecommendations` ném lỗi thay vì trả gợi ý mô phỏng.
- `src/hooks/useAssistantCart.ts` — sửa: thêm tuần tự, chờ backend.
- `tests/unit/bookingService.test.ts` — thêm. `tests/unit/recsysService.test.ts` — sửa: lỗi phải ném ra.

## Quyết định

- **Chọn phòng ở trang chi tiết qua `variants[]`** (người dùng chốt). Property và route không vào giỏ được, backend trả `400 VALIDATION_ERROR` với `reason: NOT_BOOKABLE_LEVEL`. Căn cứ: FR-CAT-02 ("không đặt chỗ trực tiếp trên property mà đặt qua phòng con"), AGENTS.md §6.2, `catalog.product_meta.is_bookable`. Không lệch PRD nên không cần đề xuất.
- **Bỏ ý "dùng lại `eventGroupId` của chuyến đang mở" trong plan**, vì `app.bookings.event_group_id` là `UNIQUE`. Mỗi checkout sinh một mã `WEB…` dùng chung cho mọi nhóm điểm đến; spec §7.2 lệch điểm này và đã được sửa theo DDL.
- `app.booking_items.line_total` là cột sinh `unit_price * quantity`, không nhân số đêm. Backend không đọc cột này mà tính thành tiền bằng `domain.booking.line_total`. Không sửa DDL.
- DDL chỉ có một `special_request` cho cả đơn: yêu cầu đặc biệt được gộp lại và lặp trên từng mục của response.
- Frontend vẫn chiếu payload sang `types/travel.ts` như code hiện có (`recsys.ts`, `search.ts`). Đây là lệch tồn đọng với frontend spec §5 "không có lớp map", không mở rộng thêm.
- Chuyến bay chỉ gửi một tên khách (form chưa có ô nhập từng hành khách), không bịa thêm tên.

## Kiểm tra

- `PYTHONDONTWRITEBYTECODE=1 python3 src/shared/contracts/tests/validate_contract.py`: PASS.
- `LANGSMITH_TRACING=false pytest src/backend/tests`: 318 passed, 16 skipped (gồm `tests/architecture/`).
- `RUN_POSTGRES_INTEGRATION=1 pytest src/backend/tests/integration/test_booking_postgres.py`: 3 passed trên DB local đã seed. Test tự dọn; đã kiểm lại không còn giỏ hay đơn test.
- Frontend: `npx tsc --noEmit` sạch. `npx vitest run` 90/90. eslint trên các file đã sửa chỉ còn một cảnh báo cũ (`AI_PLACEHOLDERS` ở HomeView).
- E2E thật: backend chạy riêng ở cổng 8765, trỏ Weaviate local (3.183 vector), tài khoản `test01@vota.demo`:
  - Trước khi đặt: `long_term`, gợi ý rải rác Huế, Nha Trang, Phan Thiết.
  - Thêm property thẳng vào giỏ: `400` "Vui lòng chọn một hạng phòng…".
  - Thêm hạng phòng Đà Nẵng 2 đêm: `lineTotal 1.408.000`. Checkout: `201`, có purchase trong `cdp.events` với `event_group_id WEB…`.
  - Sau khi đặt: `cross_vertical`, `destination Đà Nẵng`, `excluded [hotel]`. Gợi ý gồm vé máy bay HCM–Đà Nẵng, Công viên nước Mikazuki, combo Đà Nẵng, Cáp treo Bà Nà; `because` là purchase vừa đặt, `daysAgo 0`. Đúng AC-REC-02.
  - Đã xoá booking và 2 event test sau khi kiểm.
- Chưa chạy qua giao diện web (BFF + trình duyệt).

## Còn lại / rủi ro

- `make web` đang trỏ Weaviate Cloud, mà mạng hiện tại không vào được, nên RecSys tắt. Để demo phải đặt `WEAVIATE_URL=http://localhost:8080` (Weaviate local đã bật và đã index đủ).
- Engine vẫn trả strategy `long_term` (không có trong enum contract) cho khách không có chuyến đang mở; thấy ở E2E. Ngoài phạm vi lần này.
- Đặt lần hai cùng điểm đến trong một checkout khác sẽ thành chuyến mới, nên gợi ý có thể quay lại khách sạn. Cần đổi DDL hoặc engine; chưa làm.
- Nút "Thêm vào giỏ" của trợ lý cho mục lưu trú (property) giờ bị backend từ chối. Người dùng phải mở trang chi tiết để chọn phòng.
- Chưa có route `POST /events` (`product_view`) và `/products/{id}/similar`; `DebugPanel` vẫn dùng simulator.
