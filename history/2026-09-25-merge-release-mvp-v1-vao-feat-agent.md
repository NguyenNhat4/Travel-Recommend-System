# Merge origin/release-mvp-v1 vào feat/agent

- Ngày: 2026-09-25
- Tác giả: nhatnm / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: backend | frontend | contract | docs

## Mục tiêu

Người dùng yêu cầu lấy `release-mvp-v1` (26 commit, tới `8e5e69b`) về `feat/agent`, rồi mở PR `feat/agent → release-mvp-v1`.

## Xung đột và cách xử lý

Merge ra 29 file xung đột, gần hết ở giỏ hàng/checkout/chi tiết sản phẩm. Nguyên nhân: `feat/agent` (commit K1 `8cf8511`, `history/2026-09-24-noi-vong-dat-cho-goi-y-k1.md`) và `feat/booking` (đã vào release qua PR #17) cùng dựng một chức năng — `/cart*`, `/bookings*`, `GET /products/{id}` kèm hạng phòng — theo hai thiết kế khác nhau. Bản release đầy đủ hơn (giữ chỗ, thanh toán Stripe, huỷ/hoàn tiền, trang chi tiết đọc backend thật).

Quyết định: **lấy toàn bộ bản release cho phần booking/cart/catalog**, bỏ bản K1 trùng.

- Lấy bản release (`--theirs`) cho cả 29 file xung đột: `docs/spec/hop-dong-tich-hop-{backend,frontend}.md`, `src/backend/app/{main.py,api/errors.py,api/v1/router.py,api/v1/routes/catalog.py,api/v1/schemas/booking.py}`, `application/booking/*`, `application/catalog/*`, `application/ports/{cart_repository,product_catalog}.py`, `domain/{booking,catalog}/__init__.py`, `infrastructure/persistence/postgres_catalog.py`, `tests/fakes/booking.py`, `tests/integration/test_booking_postgres.py`, và ở frontend `CartView`, `CheckoutView`, `ConfirmationView`, `ProductDetailView`, `HomeView`, `TravelContext`, `useAssistantCart`, `services/{booking,recsys}.ts`, `tests/unit/{bookingService,recsysService}.test.ts`.
- Xoá file chỉ K1 có, đã trùng chức năng với bản release: `api/v1/routes/{bookings,cart}.py`, `application/booking/checkout.py`, `application/ports/booking_repository.py`, `domain/booking/{errors,rules}.py`, `infrastructure/persistence/{postgres_bookings,postgres_cart}.py`, `tests/unit/api/test_booking_routes.py`, `tests/unit/application/test_booking.py`, `tests/unit/domain/test_booking_rules.py`.
- Trả về bản release các file dùng chung mà K1 từng sửa: `api/deps.py`, `domain/catalog/models.py`, `shared/contracts/schemas/catalog.yaml` (bỏ `ProductDetail.variants[]` của K1), `tests/unit/api/test_backend_wiring.py`.
- Xoá `docs/spec/gio-hang-checkout-va-vong-lap-k1.md`: mô tả code K1 đã gỡ, các đường dẫn trong đó không còn tồn tại. Đặc tả booking hiện hành: `docs/spec/booking/so-do-luong-dat-cho-thanh-toan.md`, `docs/plan/2026-09-24-booking-thanh-toan-stripe.md`.
- `src/frontend/src/components/detail/ProductDetailView.tsx`: bản release có banner "Hỏi Trợ lý AI"; gỡ lại theo quyết định của `history/2026-09-24-go-banner-tro-ly-ai-trang-chi-tiet.md`.
- `src/frontend/src/types/api.gen.ts`: sinh lại bằng `npm run generate:api-types`. Bản trên release có khai báo trùng (`SessionState`, `PasswordChangeRequest`…) làm `tsc` lỗi; sinh lại từ contract thì hết.

Giữ nguyên phần của `feat/agent`: memory hội thoại Itinerary Agent, form mở đầu trợ lý (`AssistantTripStarter`, `destinations.ts`), tài liệu/slide agent.

## Kiểm tra

- `PYTHONDONTWRITEBYTECODE=1 python3 src/shared/contracts/tests/validate_contract.py`: PASS (83 schemas, 62 fixtures).
- `LANGSMITH_TRACING=false pytest -q src/backend/tests`: 415 passed, 19 skipped.
- Frontend: `npx tsc --noEmit` sạch; `npx vitest run` 119/119 passed (20 file).
- Không chạy E2E qua trình duyệt và không chạy integration Postgres (`RUN_POSTGRES_INTEGRATION`).

## Còn lại / rủi ro

- Vòng K1 "đặt xong → gợi ý" chưa kiểm lại trên bản booking của release (Confirmation/Home dùng code release). Cần chạy demo đặt phòng rồi xem gợi ý.
- Entry `history/2026-09-24-noi-vong-dat-cho-goi-y-k1.md` và `history/2026-09-24-doc-gio-hang-checkout-k1.md` mô tả code đã bị thay bằng bản release; không sửa entry cũ theo `history/README.md`.
