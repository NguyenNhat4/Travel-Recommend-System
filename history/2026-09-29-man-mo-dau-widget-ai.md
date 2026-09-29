# Màn mở đầu dạng ô tìm kiếm cho widget trợ lý du lịch AI

- Ngày: 2026-09-29
- Tác giả: người dùng / Codex
- Nhánh: feat/itinerary-agent-guardrails
- Trạng thái: hoàn thành
- Phạm vi: frontend, docs

## Mục tiêu

Khi vừa mở icon AI và chưa gửi câu đầu tiên, hiển thị lời chào ngắn và một ô nhập yêu cầu tự nhiên ở trung tâm. Chuyển sang chat sau lần gửi đầu, thu gọn form chọn nhanh, giữ mọi file code của task dưới 300 dòng và commit riêng thay đổi của task.

## File thay đổi

- `src/frontend/src/components/assistant/AiFloatingWidget.tsx` — sửa: giữ entry point, chuyển implementation vào feature itinerary.
- `src/frontend/src/features/itinerary/widget/FloatingWidget.tsx` — thêm: bố cục sidebar/fullscreen, điều khiển và ghép các component widget.
- `src/frontend/src/features/itinerary/widget/WidgetOpening.tsx` — thêm: mascot, lời chào ngắn, ô nhập, chip điền bản nháp và form chọn nhanh thu gọn.
- `src/frontend/src/features/itinerary/widget/WidgetComposer.tsx` — thêm: textarea tự giãn, giới hạn 1.000 ký tự, Enter gửi/Shift+Enter xuống dòng, chặn gửi rỗng/đang chạy và xử lý nhập IME.
- `src/frontend/src/features/itinerary/widget/WidgetChat.tsx` — thêm: chuyển màn mở đầu sang transcript, tiến trình, lỗi/thử lại, dừng và một ô nhập ở đáy.
- `src/frontend/src/features/itinerary/widget/WidgetLauncher.tsx` — thêm: nút mascot và lời mời mở trợ lý; chuyển effect gõ chữ ra khỏi controller.
- `src/frontend/src/features/itinerary/widget/WidgetHistory.tsx` — thêm: tách drawer lịch sử, dùng nút có accessible name và hỗ trợ bàn phím.
- `src/frontend/src/features/itinerary/widget/WidgetPlanEmpty.tsx` — thêm: tách khu vực chưa có lịch trình; gợi ý điền vào bản nháp trước khi gửi.
- `src/frontend/src/features/itinerary/widget/WidgetPlanPanel.tsx` — thêm: tách tab ngày, tổng tiền, bookmark, checkout và map nạp client-only.
- `src/frontend/src/features/itinerary/widget/WidgetDays.tsx` — thêm: chuyển timeline ngày/khách sạn/hoạt động và hover ghim map từ widget cũ.
- `src/frontend/src/features/itinerary/widget/widgetPlan.ts` — thêm: chuyển adapter lịch trình và danh sách mục giỏ từ widget cũ.
- `src/frontend/src/features/itinerary/widget/widgetVisuals.ts` — thêm: chuyển các helper hình ảnh từ widget cũ, giữ nguyên hành vi.
- `src/frontend/src/features/itinerary/widget/widgetTypes.ts` — thêm: kiểu dữ liệu UI của widget.
- `src/frontend/src/features/itinerary/widget/useFloatingWidget.ts` — thêm: tách state, transcript, gửi/reset, bản nháp, lưu phiên trong bộ nhớ và hành động checkout; mở phiên qua `loadConversation` sẵn có, báo lỗi khi không nạp được.
- `src/frontend/src/features/itinerary/widget/useWidgetFocus.ts` — thêm: focus trong dialog/history, trap Tab và trả focus về icon khi đóng.
- `src/frontend/tests/unit/floatingWidgetOpening.test.tsx` — thêm: 7 regression test cho màn mở đầu, gợi ý, gửi/chuyển chat, form điểm đến, bản nháp, cuộc mới, lỗi mở phiên và thử lại.
- `src/frontend/tests/e2e/widget-opening.spec.ts` — thêm: 6 test Chromium cho bốn breakpoint, bàn phím/ngữ cảnh/reset và lịch trình/map sau tách widget.
- `src/frontend/tests/e2e/routes.spec.ts` — sửa: selector của ô nhập ban đầu và nhãn phiên; smoke nhập không phụ thuộc phản hồi từ backend thật.
- `docs/spec/hop-dong-tich-hop-frontend.md` — sửa: mô tả trạng thái mở đầu widget tại §4.8.
- `history/2026-09-29-man-mo-dau-widget-ai.md` — thêm: ghi lại task này.

## Quyết định

- Phục vụ FR-AGT-01, hỗ trợ AC-AGT-01 (`docs/prd/requirements.md` §1.4, §3). Không lệch PRD, không đổi contract/backend hoặc quy tắc ngày khởi hành đang chờ chốt.
- Thay thế cách trình bày form trong bong bóng chào của widget ở `history/2026-09-24-form-mo-dau-tro-ly.md`. Trang `/assistant` giữ bố cục hiện hành; task tập trung widget mở từ icon.
- Form chỉ tải danh sách điểm đến qua service hiện có khi người dùng mở phần thu gọn. Không có điểm đến dự phòng hardcode.
- Chip chỉ điền bản nháp. Đóng/mở và mở rộng giữ bản nháp; tạo cuộc mới xóa bản nháp. Sau câu đầu chỉ render một composer ở đáy.
- Tách file 1.368 dòng theo trách nhiệm vào `features/itinerary/widget` theo kiến trúc frontend. Mọi file code thay đổi/thêm của task dưới 300 dòng, lớn nhất 231 dòng.
- Giữ cách chuyển dữ liệu lịch trình, hình ảnh và tương tác map của widget cũ; giữ `itineraryCartItems` và `useAssistantCart`, chờ thêm giỏ tuần tự trước checkout theo `history/2026-09-25-widget-thanh-toan-them-du-gio.md`.
- Mở lại phiên dùng API qua provider hiện có, giữ cùng `conversationId`; failure có toast thay cho Promise rejection không được xử lý. Lịch sử bền vững vẫn chịu auth của backend.
- Chỉ stage các file liệt kê trên. Không đưa `.env`, ảnh chụp/test output, `next-env.d.ts` tự sinh hoặc đề xuất/history khác trong worktree vào commit.

## Kiểm tra

- `npx --no-install vitest run tests/unit --maxWorkers=2` (trong `src/frontend`): PASS 97/97, 19 file. Lần đầu chạy mặc định đồng thời build có một test service điểm đến timeout 5 giây; chạy lại với 2 worker hoàn tất sau 4,65 giây.
- `npm run typecheck` (trong `src/frontend`): PASS.
- `npx --no-install eslint src/features/itinerary/widget src/components/assistant/AiFloatingWidget.tsx tests/unit/floatingWidgetOpening.test.tsx tests/e2e/widget-opening.spec.ts tests/e2e/routes.spec.ts`: PASS, không lỗi/cảnh báo.
- `npm run build:web --prefix src/frontend`: PASS, production build và 9/9 static pages hoàn tất.
- `npx --no-install playwright test tests/e2e/routes.spec.ts tests/e2e/widget-opening.spec.ts`: PASS 19/19 trên Chromium, 1,6 phút. Đã sửa JSON import attribute theo Node runtime và scope assertion đếm composer vào dialog sau lần chạy 18 PASS/1 FAIL (assertion cũ đếm cả textbox của trang chủ phía sau).
- Breakpoint 320/768/1024/1440 px: PASS; xem trực quan ảnh chụp mobile/tablet trong `/tmp/travel-ai-opening-*.png`. Kiểm tra draft, focus, Shift+Enter, Enter, Escape, gửi tiếp với cùng phiên, reset và hiển thị timeline sau response COMPLETED.
- `git diff --check`: PASS. Kiểm tra số dòng các file code thuộc task: PASS, tất cả < 300.
- Không sửa contract/mock dùng chung hoặc schema/seed; không chạy contract validator, DB verification hoặc golden agent.

## Còn lại / rủi ro

- Browser regression dùng API SSE/điểm đến mô phỏng và fixture completed hiện có; chưa xác minh agent với LLM/catalog thật trong task này.
- Smoke route cũ chạy standalone production thiếu `SESSION_REDIS_URL` nên có log lỗi session ở server; 19 test đều PASS. Các test mới mô phỏng phiên anonymous và API nền để không phụ thuộc Redis/backend.
- Giữ các hạn chế có sẵn của adapter/hình ảnh/map và các quy tắc giỏ hàng; task không sửa dữ liệu catalog hoặc logic agent.
