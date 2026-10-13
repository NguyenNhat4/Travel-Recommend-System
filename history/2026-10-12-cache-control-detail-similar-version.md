# Cache-Control cho chi tiết và similar sản phẩm, bump contract 1.24.1

- Ngày: 2026-10-12
- Tác giả: Khoa15 / Claude Haiku 5.5
- Nhánh: Khoa15/khoa-cache-search-product
- Trạng thái: hoàn thành
- Phạm vi: backend | frontend | contract | docs
- Thay thế: 2026-10-12-cache-control-products.md (hai quyết định: không đổi `info.version`; chỉ áp dụng cho danh sách)

## Mục tiêu

Người dùng chốt ba điểm mở của `2026-10-12-cache-control-products.md`:

1. Bump `info.version` 1.24.0 → 1.24.1 cho thay đổi mô tả contract.
2. Mở rộng `Cache-Control` sang `GET /products/{productId}` và `GET /products/{productId}/similar`.
3. `requestId` trong body của response cache được: chưa đổi, chờ người dùng quyết (xem Còn lại).

## File thay đổi

- `src/backend/app/api/v1/routes/catalog.py` — sửa: hằng `PUBLIC_CATALOG_CACHE`; `get_product` và `similar_products` nhận `response: Response`, đặt header sau khi use case thành công.
- `src/backend/tests/contract/test_catalog_contract.py` — sửa: thêm `test_detail_and_similar_are_publicly_cacheable_and_errors_are_not`.
- `src/backend/app/main.py` — sửa: `FastAPI(version=…)` 1.24.0 → 1.24.1, theo `info.version`.
- `src/backend/tests/contract/test_search_contract.py`, `test_search_llm_contract.py` — sửa: hai assertion version 1.24.0 → 1.24.1. Hai test này ràng buộc `info.version == app.version`, nên phải đổi cùng lúc với bump.
- `src/shared/contracts/openapi.yaml` — sửa: `info.version` 1.24.0 → 1.24.1.
- `src/shared/contracts/paths/catalog.yaml` — sửa: thêm `description` cho `getProduct` và `getSimilarProducts`, ghi header 200 và các mã lỗi không có header.
- `src/frontend/src/types/api.gen.ts` — sửa: tái sinh bằng `npm run generate:api-types`; diff gồm đúng ba mô tả operation (`listProducts`, `getProduct`, `getSimilarProducts`).
- `docs/spec/hop-dong-tich-hop-backend.md` — sửa: đoạn "Bộ nhớ đệm HTTP" ở §4.1 áp dụng cho cả ba endpoint.
- `history/2026-10-12-cache-control-products.md` — sửa: thêm dòng `Bị thay thế bởi` (không đổi nội dung).

## Quyết định

- Version 1.24.1 cho thay đổi chỉ là mô tả và header bổ sung, không đổi schema hay tham số. Người dùng đã chốt.
- `PUBLIC_CATALOG_CACHE` là một hằng số dùng chung cho ba route, để giá trị không bị lệch giữa các endpoint.
- Header gắn sau khi use case thành công, nên 400, 404, 409, 503 không có header. Test khoá điều này cho cả ba route.
- `requestId` trong body không đổi. Lý do: trường này bắt buộc trong `ProductListResponse` và `SimilarProductsResponse` (`schemas/catalog.yaml`), api-contract cấm xoá field trong v1; frontend không đọc `requestId` của hai response này. Cần người dùng chốt có ghi chú vào mô tả contract không.
- Không sửa các chỗ nhắc "contract 1.24.0" trong spec, frontend và history. Đó là mốc lịch sử của FR-AGT-06 (thêm `searchResults`), vẫn đúng.

## Kiểm tra

- TDD: test detail và similar chạy trước khi sửa route, đỏ với `KeyError: 'cache-control'`; sau khi sửa, `test_catalog_contract.py`: 19 passed.
- `.venv/bin/python -m pytest -q src/backend/tests/unit src/backend/tests/contract src/backend/tests/architecture`: 2830 passed, 2 skipped. Lần chạy đầu có 2 đỏ do hai test ghim `1.24.0`; đã đổi theo bump và chạy lại.
- `.venv/bin/python src/shared/contracts/tests/validate_contract.py`: PASS (120 schemas, 95 fixture).
- `src/frontend`: `npx tsc --noEmit` exit 0; `npx vitest run` 80 file, 821 test pass.
- `git diff --check`: sạch.
- Chưa chạy eslint; chưa kiểm trên trình duyệt hay qua Cloudflare.

## Còn lại / rủi ro

- `requestId` trong body của response cache: chờ người dùng quyết giữ nguyên và ghi chú vào contract, hay phương án khác. Đề xuất: giữ nguyên, ghi chú rằng trên response cache đây là id của request đã tạo bản cache, không phải request hiện tại; không có log cho lượt trúng cache.
- Cloudflare trước load balancer staging HA: cần kiểm Cache Rule cho `/api/v1/products*` để `s-maxage` có tác dụng ở edge. Repo không cho biết cấu hình này.
- Chưa commit. Entry này và entry trước nằm cùng thay đổi khi commit.
