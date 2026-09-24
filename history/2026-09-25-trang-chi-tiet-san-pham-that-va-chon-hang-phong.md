# Trang chi tiết sản phẩm thật, chọn hạng phòng và bỏ catalog giả ở Web

- Ngày: 2026-09-25
- Tác giả: mihhquan / Claude Code
- Nhánh: feat/booking
- Trạng thái: hoàn thành
- Phạm vi: contract | backend | frontend | docs

## Mục tiêu

Người dùng báo bấm vào sản phẩm nào cũng ra "Sản phẩm này không còn trên V-OTA" dù `cdp.products` có hơn 10 nghìn sản phẩm. Nguyên nhân:

1. `ProductDetailView` tra sản phẩm trong catalog tĩnh `src/frontend/src/data/catalog.ts` (28 sản phẩm giả, id `nt-hotel-01`…), trong khi Search/Recommendation/Assistant trả id UUID thật.
2. Backend chưa có `GET /products`, `/products/{id}`, `/products/{id}/similar` và `POST /events` dù contract đã định nghĩa (`noi-lai-chuan-hoa-diem-den-o-http-mode` đã ghi rủi ro này).
3. Trang chủ, gợi ý, tìm kiếm và widget trợ lý đều lui về catalog giả khi backend lỗi, và còn ghi đè tên sản phẩm thật bằng tên giả.

Người dùng yêu cầu làm cả hai bước: sửa trang chi tiết, và bỏ hẳn catalog giả. Khi khảo sát lộ thêm: khách sạn cấp property (thứ Search trả về) không đặt được — FR-CAT-02 bắt đặt qua hạng phòng — mà contract không có cách lấy hạng phòng. Người dùng chọn thêm lọc tầng con vào contract ("tôi muốn đặt được phòng chứ khách sạn thì sao đặt").

Phục vụ FR-CAT-01…03, FR-SRC (Similar), FR-REC-01 (khối Phổ biến), FR-CDP-01 (`product_view`), NFR-PERF-01 (chi tiết ≤ 100 ms), NFR-REL-01 (không hiển thị sản phẩm bịa).

## File thay đổi

Contract / mock
- `src/shared/contracts/paths/catalog.yaml` — sửa: `GET /products` thêm query tùy chọn `parentProductId` và mô tả tầng cha/tầng con.
- `src/shared/contracts/openapi.yaml` — sửa: version 1.6.0.
- `src/shared/mocks/catalog/getProduct.200-property.json`, `listProducts.200-variants.json` — thêm: khách sạn có `variantSummary` và danh sách hạng phòng của nó.
- `src/shared/mocks/index.json` — sửa: đăng ký hai fixture mới.

Backend
- `src/backend/app/domain/catalog/listing.py` — thêm: `ListingItem`, `VariantSummary`, `summarize_variants`, `filter_items`, `sort_items` (popular = lượt mua → gợi ý được → có giá → tên; giá null luôn cuối).
- `src/backend/app/domain/catalog/models.py` — sửa: `Product.rating`, `review_count`, `max_occupancy`, `has_variants`.
- `src/backend/app/domain/catalog/__init__.py` — sửa: export mới.
- `src/backend/app/application/ports/product_query.py` — thêm: port `ProductQuery` (`get`, `variants`, `search_units`).
- `src/backend/app/application/catalog/use_cases.py`, `views.py`, `errors.py` — thêm: `GetProductDetail`, `ListProducts`, `GetSimilarProducts`; chuyển sang `ProductSummary`/`ProductDetail` (bỏ key `false` theo [C2]); lỗi `PRODUCT_NOT_FOUND` 404, `PRODUCT_NOT_INDEXED` 409, `SEARCH_UNAVAILABLE` 503, `VALIDATION_ERROR` 400.
- `src/backend/app/application/search/use_cases.py` — sửa: `SimilarProducts.lookup` trả lý do (`not_in_index`, `no_vector`); `__call__` giữ hành vi cũ.
- `src/backend/app/infrastructure/persistence/postgres_catalog.py` — sửa: thêm `PostgresProductQuery`.
- `src/backend/app/api/v1/routes/catalog.py` — sửa: `GET /products`, `/products/{id}`, `/products/{id}/similar`.
- `src/backend/app/api/v1/routes/events.py` — thêm: `POST /events` (`product_view`), gọi `BehaviourTracker` có sẵn.
- `src/backend/app/api/v1/router.py`, `api/errors.py` — sửa: gắn router events; handler `CatalogError` và `ProductNotFoundError` của tracking.
- `src/backend/app/main.py` — sửa: `build_catalog`, `build_recsys` trả thêm `listing_units` và `product_popularity`, gắn `behaviour_tracker`; version 1.6.0.
- `src/backend/tests/fakes/catalog.py` — thêm: `InMemoryProductQuery`.
- `src/backend/tests/unit/domain/test_catalog_listing.py` (10 test), `tests/unit/application/test_catalog_use_cases.py` (21 test), `tests/contract/test_catalog_contract.py` (13 test), `tests/integration/test_catalog_postgres.py` (4 test, gated `RUN_POSTGRES_INTEGRATION=1`) — thêm.
- `src/backend/README.md` — sửa: thêm `product_query.py` vào bảng port.

Frontend
- `src/frontend/src/services/catalog.ts` — thêm: `getProduct`, `listProducts`, `listVariants`, `getSimilarProducts`, `trackProductView`, `productFromApi` (tọa độ/địa chỉ đọc từ `attributes` thật, giá null giữ null).
- `src/frontend/src/components/detail/ProductDetailView.tsx` — viết lại: đọc API; khách sạn/tuyến bay liệt kê hạng phòng/chuyến bay để chọn, giỏ nhận id tầng con; trang 404 kèm sản phẩm phổ biến; Tương tự và Hoàn thiện chuyến từ API; ghi `product_view` một lần khi đã đăng nhập; trạng thái tải/lỗi/Thử lại.
- `src/frontend/src/components/home/HomeView.tsx` — sửa: bỏ hai mảng khách sạn gõ tay (giá gạch giả, thêm sản phẩm giả vào giỏ); hai carousel đọc `GET /products?sort=popular` (khách sạn, và "Phổ biến tại các điểm đến Việt Nam"); gợi ý lỗi thì hiện "Chưa tải được gợi ý · Thử lại".
- `src/frontend/src/services/recsys.ts` — viết lại: bỏ bộ giả lập `calculateRecommendations`, `getSimilarProducts` cục bộ và `PERSONA_CDP_USER_MAP`; lỗi ném `ApiError`.
- `src/frontend/src/services/search.ts`, `components/search/SearchView.tsx` — sửa: bỏ tìm kiếm cục bộ; lỗi hiện ErrorState + Thử lại; băng "kết quả yếu" theo `topScore < 0.35` (frontend §6.4); giá null xếp cuối.
- `src/frontend/src/services/assistant.ts`, `components/assistant/AiFloatingWidget.tsx` — sửa: map qua `productFromApi`, không tra catalog giả; hiển thị giá null an toàn.
- `src/frontend/src/components/common/DebugPanel.tsx` — sửa: chẩn đoán lấy từ `/recommendations` thật.
- `src/frontend/src/components/cart/CartView.tsx`, `components/confirmation/ConfirmationView.tsx` — sửa: bỏ tham số fallback; placeholder `.svg`.
- `src/frontend/src/components/common/PriceTag.tsx` — sửa: giá null → "Chưa có giá"; golf "/ lượt" (frontend §6.2).
- `src/frontend/src/types/travel.ts` — sửa: `Product.unitPrice: number | null`, thêm `level`, `parentProductId`.
- `src/frontend/src/types/api.gen.ts` — sửa: sinh lại (`npm run generate:api-types`).
- `src/frontend/src/data/catalog.ts` — xóa.
- `src/frontend/public/placeholders/{hotel,flight,attraction,combo,golf}.svg` — thêm: ảnh thay thế theo taxonomy (111 tuyến bay không có ảnh; đường dẫn `.webp` cũ không tồn tại).
- `src/frontend/tests/unit/catalogService.test.ts` (6 test), `productDetailView.test.tsx` (7 test) — thêm; `recsysService.test.ts`, `searchService.test.ts` — sửa (bỏ kiểm fallback giả, thêm kiểm grounding và lỗi).
- `src/frontend/README.md` — sửa: một đoạn về nguồn dữ liệu catalog và chọn hạng phòng.

Tài liệu
- `docs/spec/hop-dong-tich-hop-backend.md` — sửa: §4.1 tham số `parentProductId`, tầng cha/con, nguồn `popular`; §4.2 `variantSummary`; §4.3 `resolvedFrom` và mã lỗi.
- `docs/spec/hop-dong-tich-hop-frontend.md` — sửa: §4.1 ④, §4.3 hàng chọn hạng phòng/chuyến bay và quy tắc giỏ nhận id tầng con.
- `docs/spec/product.md` — sửa: §4.3.3 hộp đặt khách sạn/chuyến bay.
- `history/2026-09-25-trang-chi-tiet-san-pham-that-va-chon-hang-phong.md` — thêm: entry này.

## Quyết định

- **Không lệch PRD, không cần đề xuất.** FR-CAT-02 đã yêu cầu đặt qua hạng phòng; các endpoint đã có trong contract. `parentProductId` là tham số tùy chọn mới (tương thích ngược, contract sửa trước theo AGENTS.md §3), người dùng đồng ý trong phiên. Đồng thời điền `variantSummary` (đánh dấu `[CHỜ DUYỆT: C5]` trong schema) theo đúng định nghĩa đã có, người dùng đồng ý cùng lựa chọn đó.
- **Danh sách tầng cha đọc `UnitIndex` trong RAM**, không đọc view `catalog.product_meta` mỗi request: đo view mất 80–130 ms, vượt ngân sách 100 ms. RecSys tắt thì mới đọc view (`search_units`). Chi tiết và tầng con đọc thẳng `cdp.products` (khoá chính, `products_parent_idx`), đo 30–36 ms qua BFF.
- **`sort=popular` dùng `Popularity.unit_scores()` (90 ngày) của RecSys**, không đọc `cdp.events` từ connection app (vota_app không có quyền — AGENTS.md §6.1).
- **`/similar` phân biệt 404 và 409** bằng `SimilarProducts.lookup`, không embed lại (dùng vector đã lưu). Weaviate client đồng bộ nên use case chạy nó bằng `asyncio.to_thread`.
- **`POST /events` trả 400, không 422,** cho body sai (contract khai báo 400); kiểm thủ công vì `TrackEventRequest` là `additionalProperties: false`.
- **Bỏ mọi đường lui về dữ liệu giả ở Web**: lỗi thì ẩn khối/hiện lỗi + Thử lại (product.md §1.4-4, §4.1.5; frontend §8). Test cũ `recsysService` còn kỳ vọng tên thật bị ghi đè bằng tên giả ("…(Cáp Treo Hai Chiều)") — đó là lỗi grounding, đã sửa test.
- Giữ cấu trúc `components/` hiện có, không tạo `features/` (cùng lý do entry booking 2026-09-24). Route Web vẫn là `/product/{id}` theo contract Web (PRD `user-flow.md` ghi `/products/:id` là lệch tồn đọng, không đổi ở đây).
- Không chạy `next build` vì dev server đang dùng chung `.next`.

## Kiểm tra

- `PYTHONDONTWRITEBYTECODE=1 python3 src/shared/contracts/tests/validate_contract.py`: **PASS** — 83 schemas, 62 fixtures; CDP clone 12 schemas, 7 fixtures.
- Backend: test mới 10 + 21 + 13 pass; integration `RUN_POSTGRES_INTEGRATION=1 pytest tests/integration/test_catalog_postgres.py` 4/4 (gồm chi tiết < 100 ms trên DB local); `tests/architecture` 8/8. Bộ đầy đủ lần 1: 409 passed, 19 skipped, **1 failed** `test_recsys_agent_integration.py::test_agent_gateway_consumes_enriched_backend_endpoints`; chạy riêng, chạy lại unit + contract, và chạy contract → test đó theo đúng thứ tự đều pass (53/53) — chưa tái hiện được. Bộ đầy đủ lần 2 (`RUN_POSTGRES_INTEGRATION=1`): **426 passed, 2 skipped, 1 failed** — `test_local_postgres_adapters.py::test_database_roles_enforce_the_two_connection_boundary` (`assert 10320 == 11387`), lỗi đã biết do DB local dùng catalog cũ (ghi ở entry booking 2026-09-24), không liên quan; test agent ở trên pass.
- Frontend: `npx tsc --noEmit` sạch; `npx eslint .` 0 lỗi (4 cảnh báo có sẵn ở file khác, trước là 7); `npx vitest run` 111/111, chạy 3 lần liên tiếp đều pass (một lần trước đó `productDetailView` timeout do tải máy — đã nới thời gian chờ).
- Chạy thật (backend Docker build lại, Weaviate Cloud, Next BFF `localhost:3000`):
  - `GET /products?taxonomy=hotel&sort=popular` → 2.116 khách sạn; `GET /products?sort=popular` → 2.897 search unit.
  - `GET /products/{JW Marriott Phú Quốc}` → 200 trong 36 ms, `variantSummary {count 7, minPrice 9.900.000, maxPrice 32.400.000}`; `?parentProductId=` → 7 hạng phòng; `/similar` → 3 khách sạn Phú Quốc cùng taxonomy; `/products/nt-hotel-01` → 404 `PRODUCT_NOT_FOUND`.
  - Tài khoản `test50@vota.demo`: thêm hạng phòng vào giỏ → 200, `lineTotal` 19.800.000 (2 đêm); thêm khách sạn → `PRODUCT_UNAVAILABLE`; `POST /events product_view` → 202 và có dòng `product_view` (taxonomy `hotel`) trong `cdp.events`. Đã xoá mục giỏ test.
  - Trang `/`, `/product/{id}`, `/product/nt-hotel-01`, `/search`, `/cart` → 200, dev server biên dịch sạch.

## Còn lại / rủi ro

- **Độ trễ Weaviate Cloud:** `/similar` 0,6–1,1 giây, `/search` ~2 giây (Cohere + Weaviate qua mạng tới eu-central-1), vượt ngân sách 300 ms của backend §8.5. Có từ trước (entry `recsys-weaviate-top-k`); section Tương tự tải riêng nên không chặn trang. Chưa tối ưu.
- `test_agent_gateway_consumes_enriched_backend_endpoints` fail một lần trong bộ đầy đủ lần 1, pass ở mọi lần chạy sau; nghi chập chờn, chưa tìm được nguyên nhân.
- Event test (`product_view`, `add_to_cart` của `VP0000054`) còn trong `cdp.events` local.
- `docs/spec/product.md` §1.5 (bảng tình trạng frontend 21/09) đã cũ, chưa sửa.
- Bộ lọc giá/sao ở `/search` vẫn lọc phía client trên trang đã nhận (request chưa gửi `priceMin/priceMax/starRatingMin`), như trước.
- Chưa thử trên trình duyệt thật bằng mắt; mới kiểm bằng test component và HTTP.
