# HomeView gọi API endpoint recommendations của backend

- Ngày: 2026-09-21
- Tác giả: người dùng / Antigravity
- Nhánh: release-mvp-v1
- Trạng thái: hoàn thành
- Phạm vi: frontend

## Mục tiêu

Chuyển phần gợi ý (recommendations section) trong trang `HomeView.tsx` sang gọi trực tiếp backend API qua endpoint `GET /api/v1/recommendations` (proxied qua Next.js BFF `/api/v1/recommendations`), truyền `cdp_user_id` tương ứng với Persona đang chọn, và có cơ chế fallback an toàn nếu backend chưa sẵn sàng.

## File thay đổi

- `src/frontend/src/services/recsys.ts` — sửa: thêm bảng ánh xạ `PERSONA_CDP_USER_MAP` (P1: `VP0000001`, P2: `VP0000002`, P3: `VP0000003`, P4: `VP0000004`) và hàm `fetchRecommendations()` gọi API `/api/v1/recommendations`, map dữ liệu backend sang kiểu `RecommendationResponse`, fallback về `calculateRecommendations()` khi gặp lỗi mạng/502.
- `src/frontend/src/components/home/HomeView.tsx` — sửa: đổi sang quản lý state `recResponse` và `isLoadingRecs`, sử dụng `useEffect` với `AbortController` để tải gợi ý từ API khi đổi persona/activeEvents, thêm hiệu ứng chuyển mờ khi đang tải.
- `src/frontend/src/components/assistant/AiFloatingWidget.tsx` — sửa: khôi phục import `extractIntent`, `buildGroundedItinerary` và liên kết fallback `localMessages` để đảm bảo typecheck toàn bộ frontend pass.
- `src/frontend/tests/unit/recsysService.test.ts` — thêm: unit tests kiểm tra ánh xạ ID CDP, parse response backend, và kiểm tra nhánh fallback khi backend offline.
- `src/frontend/tests/unit/assistantProvider.test.tsx` — sửa: dùng `await waitFor` khi kiểm tra xóa `sessionStorage` để test chạy ổn định khi chạy song song.

## Quyết định

- Tuân thủ kiến trúc `ARCHITECTURE.md` §6: component không gọi `fetch` trực tiếp mà đi qua service (`services/recsys.ts`).
- URL gọi API đi qua route proxy `/api/v1/recommendations` của Next.js BFF (`app/api/[...path]/route.ts`), tự động chuyển tiếp tới `BACKEND_BASE_URL`.
- Tự động fallback về simulation engine `calculateRecommendations()` nếu backend trả lỗi hoặc chưa khởi chạy, tránh làm sập UI trong môi trường dev chưa bật FastAPI.

## Kiểm tra

- `npm run typecheck` trong `src/frontend` — PASS (0 errors).
- `npm run lint` trong `src/frontend` — PASS (0 errors, 7 warnings hooks cũ không liên quan).
- `npm test -- --reporter=dot` trong `src/frontend` — PASS (46/46 tests, 9/9 test files).
- `PYTHONDONTWRITEBYTECODE=1 python3 src/shared/contracts/tests/validate_contract.py` từ repo root — PASS (70 schemas, all local refs, 50 grounded products, minimal payloads).

## Còn lại / rủi ro

- Khi backend FastAPI và PostgreSQL được khởi chạy với seed database đầy đủ, endpoint `/api/v1/recommendations` sẽ trả về dữ liệu gợi ý động từ RecSys engine.
