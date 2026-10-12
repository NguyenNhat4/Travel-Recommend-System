# Đọc nhanh phần UI của Itinerary Agent (widget trợ lý)

Dành cho người cần hiểu nhanh phần frontend của trợ lý lịch trình: code nằm ở đâu, một lượt chat chạy qua những file
nào, mỗi loại response hiện ra sao. Phục vụ FR-AGT-01, FR-AGT-03, FR-AGT-04, FR-AGT-05 (`docs/prd/requirements.md`
§1.4). File này chỉ hướng dẫn đọc code; quy tắc và hợp đồng nằm ở `docs/spec/hop-dong-tich-hop-frontend.md` §4.8, §9
và PRD `docs/prd/user-flow.md` §4.2. Khi lệch nhau thì các nguồn đó thắng.

Ảnh chụp code ngày 2026-10-05, nhánh `feat/agent`.

## 1. Tóm tắt trong 30 giây

- Trợ lý **không có route riêng**. Nó là một widget nổi, gắn một lần vào `AppShell` cho mọi trang trừ checkout.
- Code chia ba lớp:
  1. **`AssistantProvider`**: giữ state hội thoại, gọi API stream SSE, đẩy sự kiện vào reducer.
  2. **`useFloatingWidget`**: controller của widget. Đọc state của Provider, dựng `messages` và `activePlan`, giữ
     state giao diện (mở/đóng, toàn màn hình, tab ngày, sản phẩm đang xem).
  3. **Component `Widget*`**: chỉ render. Mỗi component nhận nguyên object `widget` (kiểu `FloatingWidgetController`).
- Frontend **không tự lập lịch trình**. Mọi tên, giá, ảnh, `productId` đều lấy từ response của backend.

## 2. Bản đồ file

Đường dẫn tính từ `src/frontend/src/`.

| Lớp | File | Việc chính |
|---|---|---|
| Gắn vào app | `app/providers.tsx` | Bọc toàn app bằng `AssistantProvider` |
| | `components/layout/AppShell.tsx` | Render `<AiFloatingWidget />` khi không ở checkout |
| | `components/assistant/AiFloatingWidget.tsx` | Chỉ re-export `FloatingWidget`, giữ entry point cũ |
| State và mạng | `context/AssistantProvider.tsx` | `sendMessage`, `retry`, `abort`, `resetConversation`, `loadConversation`, `openFloatingWidget`; huỷ run cũ, đo "chậm" |
| | `context/assistantState.ts` | Reducer thuần: `phase`, `transcript`, `response`, `progress`, `error`, `conversationId` |
| | `services/assistantStream.ts` | `POST /api/v1/assistant/itineraries/stream`, tự parse SSE |
| | `services/assistantHistory.ts` | `GET /assistant/conversations[/{id}]` |
| Controller | `features/itinerary/widget/useFloatingWidget.ts` | Nối Provider với giao diện; mọi handler của widget |
| | `features/itinerary/widget/widgetPlan.ts` | Response `COMPLETED` → `WidgetPlan`; `narrationProducts`, `locateProduct`, `isFreeToVisit` |
| | `features/itinerary/widget/widgetProgress.ts` | `node.completed` → 3 bước tiến độ |
| | `features/itinerary/widget/useWidgetCart.ts` | Trạng thái nút "Thêm vào giỏ" theo sản phẩm (đang thêm / đã thêm) |
| | `features/itinerary/widget/useWidgetFocus.ts` | Focus trap, trả focus về nút mở khi đóng |
| Khung | `features/itinerary/widget/FloatingWidget.tsx` | Ba trạng thái: nút mở, sidebar, toàn màn hình |
| Cột chat | `WidgetChat.tsx` | Transcript, tiến độ, khung lỗi, ô nhập |
| | `WidgetOpening.tsx` | Màn mở đầu: lời chào, ô nhập lớn, chip gợi ý, nút "Thêm thông tin chuyến đi" mở `TripDetailsForm` |
| | `WidgetComposer.tsx` | Ô nhập: Enter gửi, Shift+Enter xuống dòng, đang chạy thì nút Dừng (Esc cũng dừng) |
| | `WidgetNarration.tsx` | Lời diễn giải + thẻ sản phẩm chèn sau lần nhắc đầu |
| | `WidgetProgress.tsx` | Danh sách 3 bước ✓ |
| | `WidgetHistory.tsx` | Sidebar "Đoạn chat mới" và lịch sử |
| | `WidgetLauncher.tsx` | Mascot góc phải dưới + bong bóng mời |
| Cột phải | `WidgetPlanPanel.tsx` | Header lịch trình, tab ngày, tổng tiền (không có "Thanh toán tất cả"), bản đồ |
| | `WidgetDays.tsx` | Thẻ theo ngày/buổi, nút "Đặt ngay"/"Thêm vào giỏ" |
| | `WidgetProductDetail.tsx`, `WidgetProductGallery.tsx` | Panel chi tiết sản phẩm, tải `GET /products/{id}` |
| | `WidgetPlanEmpty.tsx` | Cột phải khi chưa có lịch trình |
| | `widgetVisuals.ts` | Ảnh dự phòng, tag khách sạn từ `attributes` |
| Dùng chung | `components/assistant/inlineBold.tsx` | Parse `**đậm**` và `[Tên](product:id)` thành React node (không chèn HTML) |
| | `components/assistant/TripDetailsForm.tsx` | Form thông tin chuyến đi: form hỏi lại (`clarificationForm`) và form ở màn mở đầu |
| | `components/assistant/SuggestionChips.tsx` | Chip `suggestions` |
| | `components/assistant/ItineraryMap.tsx` | Bản đồ Leaflet + OSM, tuyến đường OSRM |
| | `components/assistant/AssistantResultPanel.tsx` | Chỉ còn dùng `itineraryCartItems`, `isBookable` và kiểu `AssistantCartItem` (xem §9) |
| | `hooks/useAssistantCart.ts` | `useAssistantCart` (thêm vào giỏ), `useBookItinerary` (Đặt ngay một mục) |

## 3. Một lượt chat đi qua đâu

```
Người dùng gõ, Enter
  └─ WidgetComposer.onSend
      └─ useFloatingWidget.handleSendMessage      (bỏ qua nếu đang chạy)
          └─ AssistantProvider.sendMessage        (dựng request: message, conversationId, context.language)
              └─ executeRequest                   (huỷ run cũ, tạo runId + AbortController, bật đồng hồ "chậm")
                  └─ requestAssistantStream       POST /api/v1/assistant/itineraries/stream
                      └─ BFF Next.js app/api/[...path] → services/server/proxy.ts
                         (gắn Authorization từ cookie phiên; client không tự đặt)
                          └─ FastAPI backend/app/api/v1/routes/assistant.py → LangGraph
                                                    ⇣ SSE
                  onEvent ─► dispatch(action) ─► assistantReducer ─► state mới
  useFloatingWidget đọc state:
    - transcript ─► messages (kèm plan / products / clarificationForm / suggestions)
    - response COMPLETED ─► activePlan (cột phải)
  Component render lại
```

Sự kiện SSE và tác động lên UI:

| Sự kiện backend | Action reducer | UI |
|---|---|---|
| `run.started` | `stream-started` | `phase = streaming` |
| `graph.topology` | `topology-received` | Lưu lại, hiện chưa render |
| `node.completed` | `node-completed` | Thêm vào `progress`, `WidgetProgress` đổi bước; đồng hồ "chậm" đặt lại |
| `run.completed` | `response-received` | Thêm tin trợ lý vào transcript, `phase` theo `status` |
| `run.failed` | `request-failed` / `request-refused` / tự gửi lại | Xem §5 |

`message` của `node.completed` là chuỗi debug của backend, **không bao giờ** hiện cho người dùng. Nhãn 3 bước do Web
sở hữu, map từ `nodeId` trong `widgetProgress.ts` (`AFTER_NODE`): xong `extract`/`tool`/`retry` thì bước 2 đang chạy,
xong `evaluate`/`compose` thì bước 3 đang chạy. Node khác (classify, converse, clarify, narrate...) không đẩy bước, nên nhánh trò chuyện
hay hỏi lại không có ✓ giả.

"Chậm" = 12 giây không có `node.completed` nào (`SLOW_NODE_MS`), đo theo từng node chứ không theo cả lượt.

## 4. Vòng đời `phase`

```
idle ─sendMessage─► connecting ─run.started─► streaming ─run.completed─► completed
                                                                      ├► needs_clarification
                                                                      ├► no_results
                                                                      └► fallback
                        bất kỳ lúc nào: abort ─► aborted     lỗi ─► failed     bị từ chối ─► idle
```

`isRunning` trong widget = `connecting` hoặc `streaming`. Khi đang chạy: khoá gửi, chip và form bị disable, nút gửi
thành nút Dừng.

## 5. Mỗi kiểu response hiện ra sao

| Response | Trong chat (`WidgetChat`) | Cột phải |
|---|---|---|
| `COMPLETED` | `WidgetNarration`: lời diễn giải `message` + thẻ sản phẩm. Ở chế độ sidebar có nút "Xem lộ trình & Bản đồ song song" | `WidgetPlanPanel`: tab ngày, thẻ, tổng tiền, bản đồ |
| `NEEDS_CLARIFICATION` | `question`; có `clarificationForm` thì hiện `TripDetailsForm`, có `suggestions` thì hiện chip. Chỉ ở tin nhắn **mới nhất** | Giữ nguyên |
| `NO_RESULTS` | `message` + chip `suggestions` (bấm là gửi luôn) | Giữ nguyên |
| `FALLBACK` | `message` + thẻ dựng từ `searchResults` | Giữ nguyên |
| `run.failed` mã `VALIDATION_ERROR` | Câu từ chối hiện như **tin nhắn thường** (yêu cầu ngoài phạm vi, chèn lệnh...) | — |
| `run.failed` mã `CONVERSATION_NOT_FOUND` | Tự gửi lại đúng tin nhắn với `conversationId = null`, chèn dòng "Đã bắt đầu cuộc trò chuyện mới." | — |
| Lỗi khác | Khung đỏ; `retryable` thì có nút "Thử lại" | — |
| Người dùng bấm Dừng | "Đã dừng..." + nút "Gửi lại" | — |

Lưu ý hành vi "điền chứ không gửi": chip ở màn mở đầu và prompt ở `WidgetPlanEmpty` chỉ **đặt câu vào ô nhập** để
người dùng đọc lại. `SuggestionChips` và nút Xác nhận của `TripDetailsForm` (form hỏi lại và form ở màn mở đầu) thì gửi
ngay (AC-AGT-01).

## 6. Bố cục và điều hướng trong widget

```
Đóng:        [mascot góc phải dưới]                       WidgetLauncher

Sidebar:     ┌──────────────┐
(mặc định)   │ ☰  tiêu đề ⤢ ✕│   chỉ cột chat, trượt từ mép trái, backdrop mờ
             │ WidgetChat   │
             └──────────────┘

Toàn màn:    ┌────────────┬─────────────────────┬──────────────┐
(isExpanded) │ WidgetChat │ WidgetDays          │ ItineraryMap │   = WidgetPlanPanel (2 cột)
             │   ~35%     │ (hoặc ProductDetail)│              │
             └────────────┴─────────────────────┴──────────────┘
```

Cột phải ở chế độ toàn màn hình chọn nội dung theo thứ tự:

1. Có `selectedProduct` mà chưa có `activePlan` (ví dụ thẻ của `FALLBACK`) → `WidgetProductDetail` chiếm cả cột.
2. Có `activePlan` → `WidgetPlanPanel`. Nếu đồng thời có `selectedProduct`, panel chi tiết thay chỗ danh sách ngày,
   bản đồ vẫn giữ.
3. Không có gì → `WidgetPlanEmpty`.

Bấm thẻ hoặc tên sản phẩm trong lời diễn giải gọi `openProductDetail(productId, message)`: chọn lịch trình của chính
tin nhắn đó, nhảy tới tab ngày chứa sản phẩm (`locateProduct`), focus ghim bản đồ, mở panel chi tiết và chuyển sang
toàn màn hình.

Esc đóng theo thứ tự: sidebar lịch sử → panel chi tiết → thoát toàn màn hình → đóng widget. Esc trong ô nhập lúc đang
chạy thì chỉ dừng run.

Mở widget từ trang khác: gọi `useAssistant().openFloatingWidget(câu)`. Câu được điền vào ô nhập, không tự gửi. Nơi
đang gọi: `PromoBanner`, `SearchView`, `SearchAssistantBanner`, `CartView`, `MobileTabBar`, `ConfirmationView`.

## 7. Grounding ở phía UI

Đây là phần dễ bị hỏi nhất khi bảo vệ demo (FR-AGT-04, NFR-REL-01).

- LLM chỉ nhắc sản phẩm qua cú pháp `[Tên](product:<productId>)`. `parseAssistantText` chỉ nhận `**đậm**` và link
  sản phẩm; mọi markdown/HTML khác hiện nguyên chữ.
- Thẻ trong chat chỉ dựng từ `narrationProducts(response)`, tức sản phẩm có thật trong `itinerary.stay`, các slot và
  `searchResults` của **chính response đó**. `productId` lạ mà LLM viết ra không thành thẻ, chỉ là chữ.
- Panel chi tiết luôn tải lại `GET /products/{id}`; `summary` từ response chỉ để hiện tạm trong lúc tải.
- Giá: `estimatedTotal = null` thì hiện "Chưa tính được", không coi giá thiếu là 0. Điểm tham quan tự do
  (`isFreeToVisit`) hiện "Tham quan tự do".
- Tag khách sạn (`hotelTags`) chỉ đọc `attributes.starRating`, `oceanView`, `privateBeach`, `pool`; không suy từ tên
  hay ghi chú.
- Ghim bản đồ chỉ dùng toạ độ trong `attributes` của catalog; thiếu thì không vẽ, không đặt ghim giả ở tâm thành phố.

## 8. Giỏ hàng và đặt chỗ

- `itineraryCartItems` (trong `AssistantResultPanel.tsx`) gom các mục **đặt được** của lịch trình, mỗi `productId`
  một lần: `available`, có `unitPrice`, `bookable !== false`, `attributes.ticketed !== false`. Ngày dùng lấy theo
  `day.date`; lưu trú có check-in = ngày đầu, check-out = check-in + `nights`; số khách theo `intent.party`.
- Hai khái niệm khác nhau: `isBookable` (đặt được) và `isCartEligible(taxonomy)` (vào giỏ được). Khách sạn và vé máy
  bay chỉ có "Đặt ngay"; tour, golf, combo có thêm "Thêm vào giỏ".
- "Đặt ngay" một mục qua `useBookItinerary` → `startBooking` (đơn nháp
  `POST /booking-drafts`, một mục mỗi đơn; lịch trình không có thanh toán gộp). "Thêm vào giỏ" qua `useAssistantCart`, gọi tuần tự từng mục,
  gom lỗi vào một toast.

## 9. Chỗ dễ nhầm và code thừa

Kiểm bằng `grep` ngày 2026-10-05; chưa sửa gì.

- **Hai hàm chuyển response sang plan.** Widget dùng `convertItineraryCompletedToGroundedPlan` ở `widgetPlan.ts`.
  Hàm `convertItineraryResponseToGroundedPlan` ở `services/assistant.ts` (gán mặc định `family_with_kids` và
  interests `['theme_park', 'beach']`) không còn nơi nào gọi ngoài test. Sửa hiển thị lịch trình thì sửa bản trong
  `widgetPlan.ts`.
- **Component `AssistantResultPanel` không còn được render.** File vẫn sống vì `widgetPlan.ts` và `useAssistantCart.ts`
  import `itineraryCartItems`, `isBookable`, `AssistantCartItem` từ đó.
- **`openHeaderDrawer` / `isHeaderDrawerOpen`** có trong Provider và reducer nhưng không ai gọi.
- **Lịch sử hội thoại chỉ nằm trong bộ nhớ tab.** `WidgetHistory` hiển thị mảng `conversations` cục bộ, chỉ được thêm
  khi bấm "Đoạn chat mới"; tải lại trang là mất. `listAssistantConversations` đã có trong `services/assistantHistory.ts`
  nhưng widget chưa gọi, trong khi hợp đồng Frontend §9.6 và FR-AGT-01 yêu cầu tải danh sách từ backend cho người đã
  đăng nhập. Mở lại một mục trong danh sách thì có gọi backend (`loadConversation`).
- **Tên hàm trong spec cũ.** Hợp đồng Frontend §9.3 nhắc `useFloatingWidget.focusProduct`; trong code hiện tại là
  `openProductDetail`.
- **Màn hình hẹp (chưa kiểm trên thiết bị thật).** Ở chế độ toàn màn hình, theo class Tailwind, dưới breakpoint `lg`
  cột phải bị ẩn (`hidden lg:flex`) và nút thu cột chat cũng ẩn, nên trên điện thoại có thể không thấy được lịch trình
  và bản đồ. Cần mở bằng viewport mobile để xác nhận.

## 10. Muốn sửa X thì mở file nào

| Muốn sửa | File |
|---|---|
| Chữ, chip, form ở màn mở đầu | `WidgetOpening.tsx`, `TripDetailsForm.tsx` |
| Nhãn hoặc cách đánh dấu 3 bước tiến độ | `widgetProgress.ts` (`STEPS`, `AFTER_NODE`) |
| Cách hiện lời diễn giải, vị trí thẻ | `WidgetNarration.tsx` (`narrationBlocks`), `inlineBold.tsx` |
| Thẻ theo ngày, nút trên thẻ | `WidgetDays.tsx`, `useFloatingWidget.itemActions` |
| Tổng tiền | `WidgetPlanPanel.tsx` |
| Mục nào được đặt / vào giỏ | `AssistantResultPanel.tsx` (`isBookable`, `itineraryCartItems`), `services/booking.ts` (`isCartEligible`) |
| Ghim, tuyến đường, màu theo ngày | `components/assistant/ItineraryMap.tsx`, `services/routeGeometry.ts` |
| Panel chi tiết sản phẩm | `WidgetProductDetail.tsx` |
| Xử lý lỗi, tự gửi lại, từ chối | `AssistantProvider.tsx` (`executeRequest`), `assistantState.ts` |
| Một trường mới trong response | Contract `src/shared/contracts/` **trước**, sinh lại `types/api.gen.ts`, rồi `widgetPlan.ts` |

Nội dung chữ của trợ lý (câu hỏi lại, lời diễn giải, giọng văn) do backend sinh, không sửa ở frontend. Xem bảng
"Chọn lớp" trong skill `.agents/skills/building-itinerary-agent/SKILL.md`.

## 11. Chạy và kiểm tra

```bash
cd src/frontend
node_modules/.bin/vitest run tests/unit      # unit test
node_modules/.bin/tsc --noEmit               # kiểm kiểu
npm run test:e2e                             # Playwright, build trước rồi chạy
```

Test sẵn có theo file nguồn (trong `src/frontend/tests/`):

| Nguồn | Test |
|---|---|
| `AssistantProvider.tsx`, `assistantState.ts` | `unit/assistantProvider.test.tsx`, `unit/assistantState.test.ts` |
| `assistantStream.ts`, `assistantHistory.ts`, `assistant.ts` | `unit/assistantStream.test.ts`, `unit/assistantHistoryService.test.ts`, `unit/assistantService.test.ts` |
| `widgetPlan.ts`, `widgetProgress.ts` | `unit/widgetPlan.test.ts`, `unit/widgetProgress.test.ts` |
| `WidgetNarration.tsx`, `inlineBold.tsx` | `unit/widgetNarration.test.tsx`, `unit/inlineBold.test.ts` |
| `WidgetDays.tsx`, `WidgetProductDetail.tsx` | `unit/widgetDays.test.tsx`, `unit/widgetProductDetail.test.tsx` |
| `WidgetOpening.tsx`, `TripDetailsForm.tsx` | `unit/floatingWidgetOpening.test.tsx`, `unit/tripDetailsForm.test.tsx` |
| `useWidgetCart.ts`, `useAssistantCart.ts` | `unit/useWidgetCart.test.tsx`, `unit/useAssistantCart.test.tsx` |
| Luồng thật trên trình duyệt | `e2e/widget-opening.spec.ts`, `e2e/widget-detail.spec.ts` |

## 12. Đọc thêm

- `docs/spec/hop-dong-tich-hop-frontend.md` §4.8 (endpoint của widget), §9 (shape request/response, grounding,
  hội thoại).
- `docs/prd/user-flow.md` §4.2 (wireframe widget).
- `docs/spec/product.md` §6.1 (pipeline → 3 bước tiến độ), §6.4 (quy tắc grounding trên UI).
- `src/shared/contracts/paths/itinerary-agent.yaml`, `schemas/itinerary-agent.yaml` (nguồn sự thật của shape).
- Phía backend của cùng luồng: `src/backend/app/api/v1/routes/assistant.py` (phát SSE) và `docs/spec/agent/README.md`.
