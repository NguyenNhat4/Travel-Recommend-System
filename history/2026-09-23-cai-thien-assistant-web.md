# Cải thiện Itinerary Assistant trên web: thẻ sản phẩm có hành động, đặt trọn lịch trình, chỉnh nhanh

- Ngày: 2026-09-23
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: frontend, docs

## Mục tiêu

Màn `/assistant` chưa đạt FR-AGT-04 / AC-AGT-01: thẻ sản phẩm không có link chi tiết hay nút giỏ hàng, không đặt được trọn lịch trình (`docs/prd/user-flow.md` §1.2 bước 4, §4.2). Chưa có thao tác chỉnh nhanh (FR-AGT-05). UI lộ enum thô và chữ "backend". Bản đồ đặt mọi slot vào buổi sáng và ghim giả ở tâm thành phố. Plan: `docs/plan/2026-09-23-cai-thien-assistant-web.md`.

## File thay đổi

- `src/frontend/src/components/assistant/assistantLabels.ts` — thêm: nhãn buổi, ngân sách, nhóm khách, loại hoạt động, taxonomy, hậu tố giá, tên bước graph.
- `src/frontend/src/components/assistant/AssistantResultPanel.tsx` — sửa: link `/product/{productId}`, nút "Thêm vào giỏ" và "Thêm cả lịch trình vào giỏ", thanh ngân sách, chip Bớt/Thêm 1 ngày, "Đổi khách sạn", "Đổi lựa chọn khác" theo slot; prop mới `onAddToCart`, `busy`, `readOnly`; export `itineraryCartItems`, `isCartEligible`, `AssistantCartItem`; bỏ enum thô và chữ "backend".
- `src/frontend/src/components/assistant/AssistantConversation.tsx` — sửa: tiến trình hiện tên bước thay cho `nodeId`, kèm thời lượng; nối giỏ hàng và khoá chỉnh khi đang chạy; lịch trình cũ trong transcript chỉ đọc.
- `src/frontend/src/components/assistant/AssistantView.tsx` — sửa: nối giỏ hàng; banner giá cũ khi xem lịch trình đã lưu/chia sẻ, kèm nút quay lại cuộc trò chuyện; chỉ vẽ bản đồ khi có ít nhất một tọa độ thật và ghi số điểm thiếu vị trí; bỏ chữ "backend".
- `src/frontend/src/hooks/useAssistantCart.ts` — thêm: thêm một/nhiều mục vào giỏ, gom kết quả vào một toast, mở LoginModal một lần cho khách.
- `src/frontend/src/services/assistant.ts` — sửa: tách `mapProductSummaryToProduct` (giá chỉ lấy từ response, bỏ fallback giá/tọa độ); map `SlotTime` đúng; thêm `planLocationCoverage`; xoá `extractIntent`, `buildGroundedItinerary` và helper Đà Lạt (bộ dựng lịch trình phía client dùng `CATALOG` mock, không còn nơi gọi).
- `src/frontend/src/components/assistant/AiFloatingWidget.tsx` — sửa: bỏ import không dùng tới `extractIntent`, `buildGroundedItinerary`.
- `src/frontend/tests/unit/assistantResultPanel.test.tsx` — sửa: thêm `cleanup`; test link chi tiết, nhãn, gom mục giỏ hàng, nút giỏ, giới hạn 1–7 ngày, khoá khi đang chạy, chế độ chỉ đọc.
- `src/frontend/tests/unit/assistantService.test.ts` — thêm: test map `SlotTime`, không tạo tọa độ giả, giữ tên/giá từ API.
- `docs/spec/hop-dong-tich-hop-frontend.md` — sửa: §4.8 ghi tiêu chí mục đủ điều kiện thêm giỏ, nguồn ngày dùng, hành động chỉnh nhanh.
- `docs/plan/2026-09-23-cai-thien-assistant-web.md` — thêm: plan và việc còn lại.

## Quyết định

- Không lệch PRD: đây là hiện thực đúng FR-AGT-04/05, AC-AGT-01 và wireframe `user-flow.md` §4.2; không đổi OpenAPI.
- Mục đủ điều kiện thêm giỏ dùng cùng tiêu chí với `bookableCount` trong contract: `available`, `unitPrice` khác null, `bookable` khác `false`, `attributes.ticketed` khác `false`.
- Link chi tiết mở tab mới để không mất lịch trình đang hiển thị (response chỉ nằm trong bộ nhớ), giống cách `AiFloatingWidget` đang làm.
- Chỉnh nhanh chỉ dùng `intentOverride.days` và tin nhắn soạn sẵn. Tin nhắn nêu tên sản phẩm, ngày và buổi để agent có ngữ cảnh loại trừ.
- Lịch trình đã lưu/chia sẻ và các lượt cũ trong transcript chỉ đọc, vì conversation có thể đã hết hạn (24 giờ, `hop-dong-tich-hop-itinerary-assistant.md` §6).
- Giữ nguyên `addToCart` local của `TravelContext`. Chuyển sang `POST /cart/items` là tồn đọng riêng.

## Kiểm tra

- `npm run typecheck`: PASS.
- `npm run lint`: 0 errors, 7 warnings (bằng số cảnh báo có từ trước, không có cảnh báo mới trong file đã sửa).
- `npm test` (vitest): PASS 59/59, 11 file.
- `npm run build:web`: PASS.
- `npx playwright test tests/e2e/routes.spec.ts` với Chrome hệ thống (config tạm ngoài repo, vì máy chưa cài browser của Playwright): 12/13 PASS. Test `header assistant drawer streams a backend result` FAIL vì không tìm thấy `#aiAssistantBtn`; id này không còn ở đâu trong `src/`, nên lỗi có từ trước và không do thay đổi này.
- Chưa chạy thủ công với backend thật và chưa chạy `tests/e2e/assistant-live.spec.ts`.

## Còn lại / rủi ro

- `tests/e2e/routes.spec.ts` và `assistant-live.spec.ts` dùng `#aiAssistantBtn` không còn tồn tại, cần sửa selector.
- Bản đồ chỉ có tọa độ cho sản phẩm trùng `CATALOG` local. Muốn có dữ liệu thật thì thêm `coordinates` vào `ProductSummary` (đổi contract, cần đề xuất `docs/prd/update/`).
- `AiFloatingWidget.tsx` vẫn có hàm map riêng, đặt tọa độ mặc định; nên hợp nhất với `AssistantResultPanel`.
- Hiệu quả của tin nhắn "Đổi … sang lựa chọn khác" phụ thuộc agent hiểu và loại trừ đúng sản phẩm; nên thêm case vào golden dataset.
