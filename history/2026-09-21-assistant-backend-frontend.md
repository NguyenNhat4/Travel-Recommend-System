# Frontend kết nối itinerary assistant với backend agent

- Ngày: 2026-09-21
- Tác giả: người yêu cầu / Codex
- Nhánh: release-mvp-v1 (nhánh hiện tại; không tạo nhánh)
- Trạng thái: hoàn thành
- Phạm vi: frontend

## Mục tiêu

Chuyển assistant UI sang dùng backend itinerary agent qua SSE; bỏ riêng trang `/assistant` và code chỉ phục vụ trang đó. Giữ các giao diện/route khác, FloatingWidget và HeaderDrawer, đồng thời không persist transcript hoặc itinerary ở frontend.

## File thay đổi

- `src/frontend/.env.example` — sửa: cấu hình `BACKEND_BASE_URL` trỏ FastAPI local.
- `src/frontend/README.md` — sửa: hướng dẫn chạy frontend và backend FastAPI.
- `src/frontend/package.json` — sửa: thêm script sinh API types, pin `openapi-typescript`, bỏ dependency assistant-only không còn consumer.
- `src/frontend/package-lock.json` — sửa: đồng bộ dependency.
- `src/frontend/playwright.config.ts` — sửa: chạy production E2E trên cổng riêng, không tái sử dụng server dev có sẵn.
- `src/frontend/server/app.ts` — sửa: giữ health API độc lập, bỏ endpoint assistant cũ và route trip-sharing chỉ dùng bởi trang assistant.
- `src/frontend/server/routes/health.ts` — sửa: tách payload health để test không cần mở cổng.
- `src/frontend/server/routes/trips.ts` — xóa: chỉ phục vụ luồng share của trang assistant đã bỏ.
- `src/frontend/server/stores/memory-shared-trip-store.ts` — xóa: không còn consumer.
- `src/frontend/server/stores/shared-trip-store.ts` — xóa: không còn consumer.
- `src/frontend/src/app/(storefront)/assistant/page.tsx` — xóa: loại route `/assistant`.
- `src/frontend/src/app/providers.tsx` — sửa: đặt `AssistantProvider` tại common ancestor cùng `TravelProvider`.
- `src/frontend/src/components/assistant/AIAssistantDrawer.tsx` — sửa: đọc shared runtime state từ provider.
- `src/frontend/src/components/assistant/AiFloatingWidget.tsx` — sửa: giữ widget và đọc shared runtime state.
- `src/frontend/src/components/assistant/AssistantConversation.tsx` — thêm: UI chung cho transcript, progress, response, retry, abort và intent override.
- `src/frontend/src/components/assistant/AssistantView.tsx` — xóa: chỉ phục vụ route `/assistant`.
- `src/frontend/src/components/assistant/ChatControls.tsx` — xóa: chỉ phục vụ route `/assistant`.
- `src/frontend/src/components/assistant/ChatMessageBubble.tsx` — xóa: chỉ phục vụ route `/assistant`.
- `src/frontend/src/components/assistant/ItineraryMap.tsx` — xóa: chỉ phục vụ route `/assistant`.
- `src/frontend/src/components/assistant/SavedTripsModal.tsx` — xóa: chỉ phục vụ route `/assistant`.
- `src/frontend/src/components/assistant/ShareItineraryModal.tsx` — xóa: chỉ phục vụ route `/assistant`.
- `src/frontend/src/components/assistant/SharedTripWelcomeBanner.tsx` — xóa: chỉ phục vụ route `/assistant`.
- `src/frontend/src/components/assistant/VoiceListeningBanner.tsx` — xóa: chỉ phục vụ route `/assistant`.
- `src/frontend/src/components/assistant/WeatherForecastCard.tsx` — xóa: chỉ phục vụ route `/assistant`.
- `src/frontend/src/components/cart/CartView.tsx` — sửa: CTA mở FloatingWidget, giữ nguyên giao diện giỏ hàng.
- `src/frontend/src/components/common/Header.tsx` — sửa: nút trợ lý mở HeaderDrawer dùng chung provider.
- `src/frontend/src/components/common/MobileTabBar.tsx` — sửa: CTA trợ lý mở FloatingWidget thay vì điều hướng route.
- `src/frontend/src/components/confirmation/ConfirmationView.tsx` — sửa: CTA mở FloatingWidget, giữ nguyên giao diện xác nhận.
- `src/frontend/src/components/detail/ProductDetailView.tsx` — sửa: CTA mở FloatingWidget, giữ nguyên giao diện chi tiết sản phẩm.
- `src/frontend/src/components/search/SearchView.tsx` — sửa: CTA trợ lý mở FloatingWidget, giữ nguyên giao diện tìm kiếm.
- `src/frontend/src/context/AssistantProvider.tsx` — thêm: provider chung, reducer lifecycle, sessionStorage chỉ lưu conversation ID, abort/run ID và stale-run guard.
- `src/frontend/src/context/assistantState.ts` — thêm: reducer và state cho lifecycle, transcript, response, progress, lỗi và presentation state.
- `src/frontend/src/services/assistantStream.ts` — thêm: typed same-origin SSE request, parser, terminal/error/abort handling.
- `src/frontend/src/services/assistant.ts` — xóa: service assistant cũ dựa trên mock/local planning.
- `src/frontend/src/services/localization.ts` — xóa: helper chỉ còn consumer trong trang assistant.
- `src/frontend/src/services/routeGeometry.ts` — xóa: itinerary map route helper không còn consumer.
- `src/frontend/src/services/shareService.ts` — xóa: share flow chỉ dùng bởi trang assistant.
- `src/frontend/src/types/api.gen.ts` — sửa: sinh lại từ OpenAPI với `openapi-typescript@7.13.0`.
- `src/frontend/src/types/travel.ts` — sửa: bỏ các kiểu itinerary assistant local-only, giữ kiểu màn hình khác.
- `src/frontend/tests/api/server.contract.test.ts` — sửa: kiểm tra health payload mà không cần bind port.
- `src/frontend/tests/api/proxy-stream.test.ts` — thêm: kiểm tra status/header, stream chunk pass-through và lan truyền abort.
- `src/frontend/tests/e2e/routes.spec.ts` — sửa: bỏ mọi case `/assistant`; thêm smoke test widget/drawer và clarification flow.
- `src/frontend/tests/e2e/assistant-live.spec.ts` — thêm: acceptance flow tùy chọn với FastAPI thật.
- `src/frontend/tests/routeGeometry.test.ts` — xóa: test cho helper không còn consumer.
- `src/frontend/tests/unit/assistantProvider.test.tsx` — thêm: hydration/storage, retry, expired/unsupported conversation, network error, slow state và stale-run tests.
- `src/frontend/tests/unit/assistantState.test.ts` — thêm: reducer lifecycle, reset và business status tests.
- `src/frontend/tests/unit/assistantStream.test.ts` — thêm: SSE chunking, CRLF/LF, malformed JSON, missing terminal, abort và request headers.

## Quyết định

- Backend là source of truth cho conversation, intent, itinerary và product; assistant dùng `POST /api/v1/assistant/itineraries/stream` qua BFF same-origin.
- `AssistantProvider` quản lý runtime; FloatingWidget và HeaderDrawer chia sẻ transcript, response, progress và conversation ID, nhưng giữ presentation state riêng.
- `sessionStorage` chỉ chứa `vota.assistant.conversationId`; reload chỉ hydrate ID, không khôi phục transcript.
- `CONVERSATION_NOT_FOUND` xóa ID nhưng giữ nguyên request để người dùng chủ động retry; không auto-retry.
- Các route Home, Search, Product Detail, Cart, Checkout, Confirmation, Login, Register và Booking không bị loại bỏ. Chỉ `/assistant` cùng thành phần/dependency riêng của route này được xóa.
- Không commit, không tạo branch và không tạo worktree. Các thay đổi ngoài phạm vi trong shared checkout được giữ nguyên.

## Kiểm tra

- `npm run generate:api-types` — PASS; OpenAPI sinh types với phiên bản pin `7.13.0`.
- `PYTHONDONTWRITEBYTECODE=1 python3 src/shared/contracts/tests/validate_contract.py` — PASS; 70 schemas, local refs và các contract/fixture checks.
- `npm test -- --reporter=dot` — PASS; 20 tests trong 5 files.
- `npm run typecheck` — PASS.
- `npm run lint` — 0 errors, 4 warnings hooks tại `ProductDetailView.tsx` và `HomeView.tsx`.
- `git diff --check` — báo trailing whitespace trong các dòng hiện có của `Footer.tsx`, `Header.tsx` và `SearchBox.tsx`; không chỉnh dọn ngoài phạm vi assistant.
- `npm run build:web` — PASS; route manifest không có `/assistant`.
- `npm run build:api` — PASS.
- `npm run test:e2e` — PASS; 10 Playwright tests pass, 1 live FastAPI test skip theo điều kiện cấu hình.
- Acceptance grep — PASS; không còn route/navigation `/assistant`, API cũ `/api/assistant/chat` hoặc `/api/assistant/plan`, local assistant planner/catalog import, hay `fetch` trong assistant component/provider.
- Live backend check `http://127.0.0.1:8000/api/v1/assistant/status` — chưa chạy được vì FastAPI không lắng nghe trên cổng 8000; live-agent E2E chưa được xác minh.

## Còn lại / rủi ro

- Chạy `RUN_ASSISTANT_LIVE_E2E=1 npm run test:e2e` khi FastAPI backend agent hoạt động để xác minh streaming end-to-end với backend thật.
- Bốn lint warnings hooks hiện còn cần được xử lý trong phạm vi phù hợp.
