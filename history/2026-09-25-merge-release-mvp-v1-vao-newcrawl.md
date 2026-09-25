# Gộp release-mvp-v1 mới nhất vào test/newcrawl

- Ngày: 2026-09-25
- Tác giả: Đăng Khôi / Claude Code
- Nhánh: test/newcrawl
- Trạng thái: hoàn thành
- Phạm vi: backend, frontend, data, contract, db, docs, deployment

## Mục tiêu

Người dùng yêu cầu merge `origin/release-mvp-v1` (fetch 25/09, commit `8e5e69b`) vào `test/newcrawl`. Release có 25 commit
chưa merge (20 commit thường, 5 merge): đặt chỗ và thanh toán Stripe, trang chi tiết sản phẩm thật, CI/CD backend và cron
crawler của team deploy, endpoint phiên đăng nhập, CI frontend. `release-mvp-v1.1` và `release` đã nằm trọn trong nhánh
này. Phần việc của nhánh được commit trước (`8156c4a`) vì merge không chạy được khi file đang sửa trùng với release.
Chi tiết nghiệp vụ từng thay đổi của release nằm trong các entry history mà release mang theo (liệt kê bên dưới).

## File thay đổi

- `.env.example` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `.github/workflows/backend-ci-cd.yml` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `.github/workflows/frontend-ci.yml` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `Dockerfile.backend` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `db/init/01_vota.sql` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `db/migrations/0003_booking_payments.sql` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `db/migrations/0004_booking_item_special_request.sql` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `db/verify.sql` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `db/vota_schema.sql` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `docker-compose.yml` — sửa: gỡ xung đột — giữ khối Weaviate của nhánh này (Weaviate local, `BACKEND_WEAVIATE_*`, `CATALOG_REFRESH_SECONDS`) và thêm các biến Stripe của release.
- `docs/plan/2026-09-24-backend-cicd-cron.md` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `docs/plan/2026-09-24-booking-thanh-toan-stripe.md` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `docs/prd/architecture.md` — sửa: gỡ xung đột — giữ dòng Weaviate (hfresh, đề xuất đã chốt) và thêm dòng Stripe của release.
- `docs/prd/data-model.md` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `docs/prd/deployment-plan.md` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `docs/prd/project-brief.md` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `docs/prd/requirements.md` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `docs/prd/test-plan.md` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `docs/prd/update-archive/2026-09-24-sua-catalog-products-thanh-cdp-products.md` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `docs/prd/update-archive/2026-09-24-thanh-toan-stripe-mor.md` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `docs/prd/user-flow.md` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `docs/spec/2026-09-24-backend-cicd-crawler-timer-design.md` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `docs/spec/DATABASE_SCHEMA.md` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `docs/spec/booking/so-do-luong-dat-cho-thanh-toan.md` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `docs/spec/hop-dong-tich-hop-backend.md` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `docs/spec/hop-dong-tich-hop-cdp.md` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `docs/spec/hop-dong-tich-hop-frontend.md` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `docs/spec/product.md` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `history/2026-09-23-db-image-deployment.md` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `history/2026-09-24-ap-dung-de-xuat-thanh-toan-stripe-mor.md` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `history/2026-09-24-ap-dung-sua-catalog-products.md` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `history/2026-09-24-cicd-backend-data.md` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `history/2026-09-24-de-xuat-sua-catalog-products.md` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `history/2026-09-24-fix-frontend-e2e-assistant-drawer.md` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `history/2026-09-24-fix-frontend-runtime-dependencies.md` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `history/2026-09-24-fix-vercel-project-resolution.md` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `history/2026-09-24-frontend-ci-workflow.md` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `history/2026-09-24-ke-hoach-thanh-toan-stripe.md` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `history/2026-09-24-lam-ro-luong-chon-phuong-thuc-thanh-toan.md` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `history/2026-09-24-trien-khai-booking-thanh-toan-stripe.md` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `history/2026-09-25-merge-release-mvp-v1-vao-feat-booking.md` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `history/2026-09-25-trang-chi-tiet-san-pham-that-va-chon-hang-phong.md` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `ops/bootstrap-db-schema.sh` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `ops/bootstrap-db-vm.sh` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `ops/tests/test_db_image.sh` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `scripts/check-db-tunnel.sh` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `scripts/deploy-backend-vm.sh` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `scripts/install-vota-cron.sh` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/README.md` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/app/api/deps.py` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/app/api/errors.py` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/app/api/v1/router.py` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/app/api/v1/routes/booking.py` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/app/api/v1/routes/catalog.py` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/app/api/v1/routes/events.py` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/app/api/v1/routes/payments.py` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/app/api/v1/schemas/booking.py` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/app/application/booking/__init__.py` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/app/application/booking/cancel.py` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/app/application/booking/cart.py` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/app/application/booking/create_hold.py` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/app/application/booking/errors.py` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/app/application/booking/payment_events.py` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/app/application/booking/purchase_events.py` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/app/application/booking/queries.py` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/app/application/booking/reconcile.py` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/app/application/booking/settlement.py` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/app/application/booking/views.py` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/app/application/catalog/errors.py` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/app/application/catalog/use_cases.py` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/app/application/catalog/views.py` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/app/application/ports/booking_store.py` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/app/application/ports/cart_repository.py` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/app/application/ports/payment_gateway.py` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/app/application/ports/product_catalog.py` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/app/application/ports/product_query.py` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/app/application/search/use_cases.py` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/app/core/config.py` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/app/domain/booking/__init__.py` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/app/domain/booking/cancellation.py` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/app/domain/booking/hold.py` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/app/domain/booking/models.py` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/app/domain/booking/payment_failure.py` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/app/domain/booking/pricing.py` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/app/domain/booking/reference_code.py` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/app/domain/booking/status.py` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/app/domain/catalog/__init__.py` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/app/domain/catalog/listing.py` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/app/domain/catalog/models.py` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/app/infrastructure/embeddings/sentence_transformers_embedder.py` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/app/infrastructure/payments/__init__.py` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/app/infrastructure/payments/fake_gateway.py` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/app/infrastructure/payments/stripe_gateway.py` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/app/infrastructure/persistence/postgres_booking.py` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/app/infrastructure/persistence/postgres_catalog.py` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/app/main.py` — sửa: gỡ xung đột — giữ `RecsysRefresher`, thêm `build_catalog` và `BehaviourTracker` của release; catalog được dựng lại sau mỗi lần RecSys nạp (`on_publish`), RecSys không lên thì vẫn dựng một lần như release.
- `src/backend/tests/architecture/test_import_rules.py` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/tests/contract/test_booking_contract.py` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/tests/contract/test_catalog_contract.py` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/tests/fakes/booking.py` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/tests/fakes/catalog.py` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/tests/integration/test_booking_postgres.py` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/tests/integration/test_catalog_postgres.py` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/tests/unit/application/booking/test_booking_flow.py` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/tests/unit/application/test_catalog_use_cases.py` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/tests/unit/domain/booking/test_booking_domain.py` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/tests/unit/domain/test_catalog_listing.py` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/tests/unit/infrastructure/test_stripe_gateway.py` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/data_collection/seed/database.py` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/frontend/README.md` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/frontend/public/placeholders/attraction.svg` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/frontend/public/placeholders/combo.svg` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/frontend/public/placeholders/flight.svg` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/frontend/public/placeholders/golf.svg` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/frontend/public/placeholders/hotel.svg` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/frontend/src/app/(storefront)/booking/[referenceCode]/page.tsx` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/frontend/src/components/assistant/AiFloatingWidget.tsx` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/frontend/src/components/cart/CartView.tsx` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/frontend/src/components/checkout/CheckoutView.tsx` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/frontend/src/components/common/DebugPanel.tsx` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/frontend/src/components/common/Header.tsx` — sửa: gỡ xung đột — lấy nguyên bản release (`cartCount`).
- `src/frontend/src/components/common/MobileTabBar.tsx` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/frontend/src/components/common/PriceTag.tsx` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/frontend/src/components/confirmation/ConfirmationView.tsx` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/frontend/src/components/confirmation/bookingLabels.ts` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/frontend/src/components/detail/ProductDetailView.tsx` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/frontend/src/components/home/HomeView.tsx` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/frontend/src/components/search/SearchView.tsx` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/frontend/src/context/TravelContext.tsx` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/frontend/src/data/catalog.ts` — xóa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/frontend/src/hooks/useAssistantCart.ts` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/frontend/src/services/assistant.ts` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/frontend/src/services/booking.ts` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/frontend/src/services/catalog.ts` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/frontend/src/services/http.ts` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/frontend/src/services/recsys.ts` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/frontend/src/services/search.ts` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/frontend/src/types/api.gen.ts` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/frontend/src/types/travel.ts` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/frontend/tests/e2e/routes.spec.ts` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/frontend/tests/unit/bookingService.test.ts` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/frontend/tests/unit/catalogService.test.ts` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/frontend/tests/unit/checkoutView.test.tsx` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/frontend/tests/unit/confirmationView.test.tsx` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/frontend/tests/unit/productDetailView.test.tsx` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/frontend/tests/unit/recsysService.test.ts` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/frontend/tests/unit/searchService.test.ts` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/shared/contracts/openapi.yaml` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/shared/contracts/paths/booking.yaml` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/shared/contracts/paths/catalog.yaml` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/shared/contracts/paths/payments.yaml` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/shared/contracts/schemas/booking.yaml` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/shared/contracts/schemas/common.yaml` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/shared/mocks/booking/cancelBooking.409-too-late.json` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/shared/mocks/booking/createBooking.201-default.json` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/shared/mocks/booking/createBooking.201-two-groups.json` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/shared/mocks/booking/createBooking.409-pending-payment.json` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/shared/mocks/booking/createBooking.503-payment-unavailable.json` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/shared/mocks/booking/getBooking.200-cancelled-refunded.json` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/shared/mocks/booking/getBooking.200-default.json` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/shared/mocks/booking/getBooking.200-expired.json` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/shared/mocks/booking/getBooking.200-payment-failed.json` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/shared/mocks/catalog/getProduct.200-property.json` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/shared/mocks/catalog/listProducts.200-variants.json` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/shared/mocks/index.json` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/tests/unit/api/test_recsys_refresher.py` — sửa: thêm test catalog được dựng lại sau mỗi lần nạp thành công.
- `history/2026-09-25-merge-release-mvp-v1-vao-newcrawl.md` — thêm: entry này.

## Quyết định

- Bốn xung đột được gỡ bằng cách giữ cả hai phía (xem các dòng "gỡ xung đột" ở trên); `Header.tsx` lấy nguyên bản
  release vì nhánh này không chủ động sửa frontend.
- `build_catalog` của release chụp `similar`, `listing_units`, `product_popularity` lúc khởi động. Với `RecsysRefresher`,
  các engine này được thay mỗi lần nạp, nên catalog được dựng lại trong `on_publish`; nếu không, `/products` và `/similar`
  dùng mãi bản lúc khởi động và không lên khi RecSys chỉ nạp được sau lần thử lại.
- Không sửa khoảng trắng thừa ở hai dòng `Header.tsx` để giữ đúng bản release.
- Cron của CI/CD release vẫn gọi `run_daily_docker.sh run` = job daily.py (quyết định ở
  `history/2026-09-25-tach-lenh-fresh-run.md`); job cào mới ở `fresh-run` chưa được CI/CD build hay lên lịch.

## Kiểm tra

- Giả lập merge trước (index tạm, không đụng working tree): đúng 4 file xung đột như khi merge thật.
- `PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider src/backend/tests` (Python 3.11, đã cài lại
  `src/backend/requirements.txt` của bản merge): 421 passed, 19 skipped.
- `cd src/data_collection && PYTHONPATH=<repo>/src python -m pytest -q tests`: 315 passed, 3 skipped.
- `validate_contract.py`: PASS (83 schema, 62 fixture). `docker compose config -q`: hợp lệ. `bash -n` cho
  `run_daily_docker.sh`, `scripts/*.sh`, `ops/*.sh`: sạch. `git diff --check`: chỉ còn khoảng trắng thừa của release ở
  `Header.tsx`.
- Frontend sau merge giống hệt `origin/release-mvp-v1` (`git diff origin/release-mvp-v1 -- src/frontend` rỗng), không
  chạy lại test frontend.
- Chưa chạy `db/verify.sql` bản mới của release và chưa `make db-migrate` 0003/0004 trên DB local.

## Còn lại / rủi ro

- DB đang chạy cần `make db-migrate` để có bảng thanh toán (0003, 0004) trước khi dùng luồng đặt chỗ mới.
- Muốn VM chạy job cào mới: team build/push `Dockerfile.fresh-catalog`, tạo thư mục dữ liệu và env file mới, rồi thay
  dòng cron `run` (do `scripts/install-vota-cron.sh` quản lý) bằng `fresh-run auto`.
- Chưa push; người dùng tự push khi sẵn sàng.
