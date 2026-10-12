# Ghi chú requestId trên response được cache

- Ngày: 2026-10-12
- Tác giả: Khoa15 / Claude Haiku 5.5
- Nhánh: Khoa15/khoa-cache-search-product
- Trạng thái: hoàn thành
- Phạm vi: contract | docs | frontend

## Mục tiêu

Người dùng chốt phương án 3 của `2026-10-12-cache-control-detail-similar-version.md`: giữ trường `requestId` trong body của `GET /products` và `GET /products/{id}/similar`, và ghi chú trong contract rằng trên response được cache, giá trị này không phải id của lần gọi hiện tại.

## File thay đổi

- `src/shared/contracts/schemas/catalog.yaml` — sửa: thêm `description` cho `requestId` của `ProductListResponse` và `SimilarProductsResponse`. Không đổi kiểu hay trường bắt buộc.
- `src/frontend/src/types/api.gen.ts` — sửa: tái sinh bằng `npm run generate:api-types`; diff gồm hai dòng `@description` mới.
- `docs/spec/hop-dong-tich-hop-backend.md` — sửa: đoạn "Bộ nhớ đệm HTTP" ở §4.1 thêm câu về `requestId` và header `X-Request-ID` trên response được cache.

## Quyết định

- Không bỏ `requestId`: trường bắt buộc trong hai schema trên, api-contract cấm xoá field trong v1. Chỉ bổ sung mô tả, không đổi cấu trúc, nên không cần bump version.
- Ghi cả header `X-Request-ID` vào spec. Đã kiểm tra `install_request_id` (`src/backend/app/api/middleware.py`): middleware gắn header này lên mọi response, nên bản cache cũng mang id của request đã tạo bản cache.
- Frontend không đọc `requestId` của hai response này, nên không cần sửa code.

## Kiểm tra

- `.venv/bin/python src/shared/contracts/tests/validate_contract.py`: PASS (120 schemas, 95 fixture).
- `.venv/bin/python -m pytest -q src/backend/tests/unit src/backend/tests/contract src/backend/tests/architecture`: 2830 passed, 2 skipped.
- `src/frontend`: `npx tsc --noEmit` exit 0.
- `npx vitest run`: 4 lần chạy. Lần 1 có 1 test đỏ, tên không ghi lại được; ba lần sau đều 821 passed. Chưa xác định được test nào, chưa biết đó là lỗi thật hay flaky. Lần sửa này chỉ đổi comment trong `api.gen.ts`, không chạm code chạy được.
- `git diff --check`: sạch.

## Còn lại / rủi ro

- Test vitest đỏ một lần chưa rõ nguyên nhân. Cần chạy lại nhiều lần với log đầy đủ để tìm test nào không ổn định.
- Cloudflare trước load balancer staging HA: cần kiểm Cache Rule cho `/api/v1/products*` để `s-maxage` có tác dụng ở edge.
- Chưa commit. Entry này nằm cùng thay đổi khi commit.
