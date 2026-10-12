# Cache-Control cho GET /products

- Ngày: 2026-10-12
- Tác giả: Khoa15 / Claude Haiku 5.5
- Nhánh: Khoa15/khoa-cache-search-product
- Trạng thái: hoàn thành
- Phạm vi: backend | frontend | contract | docs
- Bị thay thế bởi: 2026-10-12-cache-control-detail-similar-version.md (hai quyết định: không đổi `info.version`; chỉ áp dụng cho danh sách)

## Mục tiêu

Giảm tải origin: danh mục `GET /products` là dữ liệu công khai, không đọc người dùng, nên response thành công có `Cache-Control: public, max-age=60, s-maxage=300` mặc định. Nhất quán với `GET /search/suggestions` (`public, max-age=300`).

Ghi chú về yêu cầu: "/search đã có max-age=300" thực tế là `GET /search/suggestions`. `GET /search` không đặt header nào và không nằm trong phạm vi này.

## File thay đổi

- `src/backend/app/api/v1/routes/catalog.py` — sửa: `list_products` nhận `response: Response`, đặt `Cache-Control` sau khi use case thành công. Lỗi 400 không mang header.
- `src/backend/tests/contract/test_catalog_contract.py` — sửa: thêm `test_listing_is_publicly_cacheable_and_errors_are_not`.
- `src/shared/contracts/paths/catalog.yaml` — sửa: mô tả `GET /products` ghi header 200 và việc 400 không có header. Chỉ đổi description, không đổi schema hay tham số.
- `src/frontend/src/types/api.gen.ts` — sửa: tái sinh bằng `npm run generate:api-types`; diff đúng một dòng `@description` của `listProducts`.
- `src/frontend/tests/api/bff-catalog-cache.test.ts` — thêm: BFF chuyển nguyên `cache-control` của `GET /api/v1/products` ra trình duyệt.
- `docs/spec/hop-dong-tich-hop-backend.md` — sửa: §4.1 thêm đoạn "Bộ nhớ đệm HTTP".

## Quyết định

- Giá trị `public, max-age=60, s-maxage=300` lấy đúng theo yêu cầu. `s-maxage` chỉ có tác dụng ở lớp cache trung gian; trình duyệt dùng `max-age`.
- Header gắn sau khi use case trả kết quả. Lỗi 400 (`VALIDATION_ERROR`) do exception handler tạo response mới nên không mang header; test khoá điều này.
- Route không đọc principal (`list_products` không nhận identity), contract cho phép cả anonymous lẫn bearer, nên response giống nhau cho mọi người và `public` là đúng.
- Frontend không đổi logic: `apiFetch` không đặt option `cache`, và BFF `services/server/proxy.ts` đã có `cache-control` trong `FORWARDED_RESPONSE_HEADERS`. Chỉ thêm test giữ đường đi này.
- Không sửa PRD: PRD không quy định HTTP cache cho `/products`, cùng cách `/search/suggestions` đã được ghi ở spec và contract, không ở PRD. Không có lệch PRD cần đề xuất.
- Không đổi `info.version` (1.24.0). Repo không có quy ước bump cho thay đổi chỉ là mô tả, nên để người dùng quyết định (xem Còn lại).
- Chỉ áp dụng cho `GET /products`. `GET /products/{id}` và `GET /products/{id}/similar` chưa đổi.

## Kiểm tra

- TDD: viết test trước, chạy thấy đỏ đúng lý do `KeyError: 'cache-control'`, sau đó mới sửa route.
- `.venv/bin/python -m pytest -q src/backend/tests/contract/test_catalog_contract.py`: 18 passed.
- `.venv/bin/python -m pytest -q src/backend/tests/unit src/backend/tests/contract src/backend/tests/architecture`: 2829 passed, 2 skipped.
- `.venv/bin/python src/shared/contracts/tests/validate_contract.py`: PASS (120 schemas, 95 fixture).
- `src/frontend`: `npx tsc --noEmit` exit 0; `npx vitest run` 80 file, 821 test pass (gồm test BFF mới; test này xanh ngay vì hành vi forward đã có sẵn, nên là test bảo vệ chứ không phải test đỏ trước).
- Môi trường cục bộ: tạo `.venv` (bỏ `torch`, `transformers` khỏi requirements vì test catalog không dùng) và `src/frontend/node_modules` bằng `npm ci`. Cả hai đã nằm trong `.gitignore`.
- Chưa chạy eslint và chưa kiểm trên trình duyệt hay qua Cloudflare thật.

## Còn lại / rủi ro

- Staging HA đặt Cloudflare proxy trước load balancer (`infra/terraform/environments/staging-ha/main.tf`). Để `s-maxage=300` thật sự giảm tải origin ở edge, cần kiểm Cloudflare có cache `/api/v1/products` không (JSON thường cần Cache Rule). Repo không cho biết cấu hình này; cần kiểm trên dashboard Cloudflare.
- `requestId` nằm trong body (`catalog.py` ghi `current_request_id() or "catalog"`). Khi trúng cache, body mang `requestId` của request gốc, không khớp `X-Request-ID` của lần gọi hiện tại. Không ảnh hưởng logic hiển thị, nhưng nếu dựa vào `requestId` trong body để truy vết thì phải biết điều này.
- Câu hỏi cho người dùng: có bump `info.version` 1.24.0 → 1.24.1 cho thay đổi mô tả này không, và có mở rộng header cho `GET /products/{id}` và `/similar` không.
- Chưa commit. Entry này nằm cùng thay đổi khi commit.
