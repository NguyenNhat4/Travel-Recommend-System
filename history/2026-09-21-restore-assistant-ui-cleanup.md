# Khôi phục Assistant UI và dọn dẹp code dư

- Ngày: 2026-09-21
- Tác giả: user / Antigravity
- Nhánh: release-mvp-v1
- Trạng thái: hoàn thành
- Phạm vi: frontend

## Mục tiêu

- Khôi phục các thành phần và file quan trọng của Assistant UI từng bị xóa dư (~10,000 dòng code gồm bản đồ Leaflet OSM/OSRM, trang `/assistant`, tính năng chia sẻ và lưu lịch trình, đa ngôn ngữ, định tuyến).
- Ưu tiên giữ lại và sử dụng giao diện gốc của `AiFloatingWidget.tsx` (1,559 dòng với linh vật chào đón, bong bóng chat gõ chữ, sidebar trượt đa phiên, làm rõ thông tin du lịch và phóng to toàn màn hình).
- Đảm bảo tích hợp mượt mà giữa Floating Widget, Header Assistant Drawer và trang `/assistant`.

## File thay đổi

- `src/frontend/src/components/assistant/AiFloatingWidget.tsx` — khôi phục: UI phong phú đầy đủ tính năng (mascot, đa phiên hội thoại, lọc hành trình, mở rộng toàn màn hình với Leaflet).
- `src/frontend/src/components/assistant/ItineraryMap.tsx` — khôi phục: bản đồ lộ trình Leaflet OSM/OSRM hỗ trợ hiển thị điểm dừng, ngày đi và tính khoảng cách/thời gian.
- `src/frontend/src/components/assistant/SavedTripsModal.tsx` — khôi phục: modal quản lý các chuyến đi và lịch trình đã lưu trên trình duyệt.
- `src/frontend/src/components/assistant/ShareItineraryModal.tsx` — khôi phục: modal chia sẻ lịch trình du lịch qua link/mạng xã hội.
- `src/frontend/src/components/assistant/SharedTripWelcomeBanner.tsx` — khôi phục: banner chào đón khi người dùng truy cập từ link chia sẻ.
- `src/frontend/src/components/assistant/VoiceListeningBanner.tsx` — khôi phục: banner hiệu ứng khi đang thu âm giọng nói.
- `src/frontend/src/components/assistant/ChatControls.tsx` — khôi phục: thanh điều khiển chat đa phiên.
- `src/frontend/src/components/assistant/ChatMessageBubble.tsx` — khôi phục: bubble tin nhắn trợ lý với thẻ sản phẩm.
- `src/frontend/src/app/(storefront)/assistant/page.tsx` — khôi phục: route tĩnh `/assistant` phục vụ workspace lịch trình chuyên dụng.
- `src/frontend/src/components/assistant/AssistantView.tsx` — sửa: tích hợp `ItineraryMap` động khi có lịch trình hợp lệ, tránh trùng landmark aria-label với map panel con.
- `src/frontend/src/services/assistant.ts` — sửa: bổ sung hàm `convertItineraryResponseToGroundedPlan` chuyển đổi DTO backend sang `GroundedPlan` cho `ItineraryMap`.
- `src/frontend/src/types/travel.ts` — khôi phục: định nghĩa kiểu dữ liệu `GroundedPlan`, `ItineraryDay`, `ItinerarySlot`, `SavedTrip`, `TravelIntent`.
- `src/frontend/src/services/routeGeometry.ts` — khôi phục: logic giải mã polyline và tính toán lộ trình OSRM.
- `src/frontend/src/services/localization.ts` — khôi phục: từ điển đa ngôn ngữ cho trợ lý và bản đồ.
- `src/frontend/src/services/shareService.ts` — khôi phục: tiện ích mã hóa và tạo link chia sẻ chuyến đi.
- `src/frontend/package.json` — sửa: cập nhật `build:web` tự động sao chép `public/` và `.next/static` vào `.next/standalone/`, bổ sung script `start:web`.
- `src/frontend/tests/e2e/routes.spec.ts` — sửa: cập nhật test E2E để kiểm tra cả Floating Widget UI gốc và luồng streaming backend qua Header Drawer và `/assistant`.

## Quyết định

- Giữ trọn vẹn 1,559 dòng của `AiFloatingWidget.tsx` từ `origin/release-mvp-v1` theo yêu cầu ưu tiên giao diện cũ của người dùng.
- Đồng bộ hóa kiến trúc Next.js standalone: cấu hình `build:web` sao chép đầy đủ thư mục `static` và `public` vào `.next/standalone` để đảm bảo client-side JS và tài nguyên webp/css tải thành công 100% trong chế độ production standalone.
- Thêm bridge converter `convertItineraryResponseToGroundedPlan` để nối kết nối dữ liệu giữa contract OpenAPI của backend (`ItineraryResponse`) với `ItineraryMap` Leaflet.

## Kiểm tra

- `npm run typecheck`: PASS (0 errors).
- `npm test`: PASS (toàn bộ 48 tests trên 10 suites pass).
- `npm run lint`: PASS (0 errors, 7 warnings).
- `PYTHONDONTWRITEBYTECODE=1 python3 src/shared/contracts/tests/validate_contract.py`: PASS (70 OpenAPI schemas).
- `npm run build:web`: PASS (tất cả 9 routes biên dịch thành công, bao gồm `/assistant`).
- `npx playwright test tests/e2e/routes.spec.ts`: PASS (13/13 tests pass, bao gồm route matrix, assistant workspace, floating widget interaction, header drawer backend streaming, và clarification intent override).

## Còn lại / rủi ro

- Không còn rủi ro tồn đọng liên quan đến việc khôi phục giao diện trợ lý hay vỡ giao diện.
