# Tích hợp endpoint /search backend cho luồng tìm kiếm từ HomeView và SearchView

- Ngày: 2026-09-21
- Tác giả: người dùng / Antigravity
- Nhánh: release-mvp-v1
- Trạng thái: hoàn thành
- Phạm vi: backend, frontend

## Mục tiêu

Kết nối thanh tìm kiếm đầu tiên trong `HomeView.tsx` với endpoint `/search` của backend. Theo yêu cầu người dùng, luồng tìm kiếm từ trang chủ chuyển hướng toàn bộ sang trang `/search` của frontend, và tại trang `/search`, hệ thống gọi trực tiếp endpoint `/api/v1/search` của backend FastAPI qua Next.js BFF proxy thay vì dùng mock nội bộ.

## File thay đổi

- `src/backend/app/api/v1/routes/search.py` — sửa: hỗ trợ thêm method `POST /search` với body `SearchRequestPayload` theo chuẩn contract OpenAPI (`paths/search.yaml`, `schemas/search.yaml`), bổ sung van an toàn xử lý khi `state.search` chưa khởi tạo hoặc query rỗng, đồng thời giữ nguyên `GET /search`.
- `src/frontend/src/services/search.ts` — sửa: thêm hàm async `searchProductsApi()` gọi `POST /api/v1/search` qua BFF proxy, trích xuất `results`, `total`, `cutoff`, `facets`, map sang kiểu `Product` và `SearchResultItem` với fallback an toàn về `searchProducts()` cục bộ khi backend offline.
- `src/frontend/src/components/search/SearchView.tsx` — sửa: cập nhật logic tìm kiếm sang `searchProductsApi()` bất đồng bộ thông qua `useEffect`, hiển thị trạng thái `isLoading` kèm spinner `Loader2` tại số lượng kết quả và hiệu ứng chuyển đổi mượt mà.
- `src/frontend/tests/unit/searchService.test.ts` — thêm: unit test cho `searchProductsApi()` kiểm tra gọi đúng `POST /api/v1/search` và cơ chế fallback an toàn.

## Quyết định

- Chuyển hướng toàn bộ từ HomeView sang route `/search` theo chỉ dẫn của người dùng, giữ URL trạng thái có thể bookmark/share và tập trung luồng xử lý kết quả tại `SearchView`.
- Backend hỗ trợ cả `POST` và `GET` cho `/search` để đảm bảo tuân thủ đầy đủ contract OpenAPI v1.4.0 vừa tương thích với các lệnh gọi GET trước đó.
- Dùng BFF proxy `/api/[...path]` của Next.js để định tuyến `/api/v1/search` tới backend `BACKEND_BASE_URL` mà không gặp vấn đề CORS.

## Kiểm tra

- `PYTHONDONTWRITEBYTECODE=1 python3 src/shared/contracts/tests/validate_contract.py`: PASS (70 schemas, all local refs, minimal payloads).
- `cd src/frontend && npm run typecheck`: PASS (0 errors).
- `cd src/frontend && npm test -- --reporter=dot`: PASS (10/10 files, 48/48 tests passed).
- `pytest src/backend/tests/unit`: PASS (116/116 tests passed).

## Còn lại / rủi ro

- Cần đảm bảo backend FastAPI đang chạy trên cổng 8000 (`http://127.0.0.1:8000`) khi chạy demo thực tế để frontend nhận được kết quả semantic search trực tiếp từ pgvector / database seed.
