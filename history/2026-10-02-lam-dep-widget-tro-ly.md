# Làm đẹp giao diện widget trợ lý du lịch

- Ngày: 2026-10-02
- Tác giả: người dùng / Codex
- Nhánh: feat/itinerary-agent-guardrails
- Trạng thái: hoàn thành
- Phạm vi: frontend

## Mục tiêu

Làm giao diện chat, lịch trình, chi tiết dịch vụ và bản đồ dễ đọc hơn theo ảnh người dùng cung cấp, sử dụng skill `frontend-ui-engineering` theo yêu cầu. Phục vụ FR-AGT-03, FR-AGT-04 và AC-AGT-01; giữ grounding theo NFR-REL-01.

## File thay đổi

- `src/frontend/src/features/itinerary/widget/FloatingWidget.tsx` — sửa: header thống nhất, biểu tượng trợ lý và tỷ lệ cột chat.
- `src/frontend/src/features/itinerary/widget/WidgetChat.tsx` — sửa: phân cấp người gửi, khoảng cách và cỡ chữ lời diễn giải.
- `src/frontend/src/features/itinerary/widget/WidgetComposer.tsx` — sửa: viền, focus và lời gợi ý điều chỉnh chuyến đi.
- `src/frontend/src/features/itinerary/widget/WidgetNarration.tsx` — sửa: trình bày tiêu đề/đoạn văn và thẻ sản phẩm; giới hạn địa chỉ dài trong cột chat.
- `src/frontend/src/features/itinerary/widget/WidgetDays.tsx` — sửa: nền timeline, nhãn ngày, giá và khoảng cách.
- `src/frontend/src/features/itinerary/widget/WidgetPlanPanel.tsx` — sửa: header bản đồ, vùng lịch trình có nhãn, trạng thái nút ngày và footer tổng tiền.
- `src/frontend/src/features/itinerary/widget/WidgetProductDetail.tsx` — sửa: gallery cân đối, nội dung cuộn riêng và giá/nút thao tác cố định ở đáy panel.
- `src/frontend/tests/e2e/widget-opening.spec.ts` — sửa: chờ focus sau reset và giới hạn truy vấn trong vùng lịch trình.
- `src/frontend/tests/e2e/widget-detail.spec.ts` — thêm: kiểm tra bàn phím, mở/đóng chi tiết, footer khi cuộn và không tràn ngang ở 1024/1440 px.
- `history/2026-10-02-lam-dep-widget-tro-ly.md` — thêm: ghi phạm vi, quyết định và kết quả kiểm tra.

## Quyết định

- Bám `docs/prd/user-flow.md` §4.2 và hợp đồng frontend: chi tiết thay cột timeline, bản đồ vẫn hiện bên phải. Đây là thay đổi trình bày trong phạm vi PRD; không cần đề xuất mở rộng.
- Dùng Tailwind, font sans và màu xanh/slate hiện có; không thêm thư viện hay sửa component ProductCard dùng chung.
- Giữ nguyên sản phẩm, giá, ảnh, tọa độ, API, tracking và thao tác giỏ hàng. Tiêu đề trong lời diễn giải chỉ phân cấp lại văn bản backend đã trả về.
- Giữ panel chi tiết trong phạm vi desktop hiện hành; không thêm luồng panel mới trên mobile.
- `src/frontend/next-env.d.ts` đã có thay đổi trước task. Khôi phục đúng nội dung đó sau khi build sinh lại file; không đưa vào phạm vi thay đổi này.

## Kiểm tra

- `npm run build:web` — PASS trên source cuối. Build trong sandbox gặp lỗi subprocess TypeScript; chạy lại ngoài sandbox đã được automatic approval cho phép và hoàn tất.
- `npm run typecheck` — PASS sau khi build cập nhật cache `.next` cũ và khôi phục `next-env.d.ts`.
- ESLint trên 7 file widget và 2 file E2E trong phạm vi — PASS.
- `node_modules/.bin/vitest run tests/unit/widgetNarration.test.tsx tests/unit/widgetProductDetail.test.tsx tests/unit/widgetDays.test.tsx tests/unit/floatingWidgetOpening.test.tsx tests/unit/widgetPlan.test.ts --maxWorkers=2` — PASS: 5 file, 32 test.
- `npm exec -- playwright test tests/e2e/widget-opening.spec.ts tests/e2e/widget-detail.spec.ts` — PASS trên source cuối: 8 test Chromium, 44,8 giây, exit 0. Server có cảnh báo proxy `ECONNREFUSED 127.0.0.1:8000` ở các request không mô phỏng vì backend local không chạy; kết quả này chỉ xác minh UI với API mô phỏng.
- Đã xem screenshot tại 320/1024/1440 px; ảnh screenshot giúp phát hiện và sửa tràn địa chỉ trong thẻ ở 1024 px.
- `git diff --check` — PASS.

## Còn lại / rủi ro

- E2E dùng API mô phỏng và fixture hiện có; chặn tile OSM và yêu cầu OSRM để kiểm tra độc lập. Chưa xác minh backend/LLM trực tiếp hoặc bản đồ nền/ảnh bên ngoài; một số ảnh chưa tải xong trong screenshot.
- Chưa commit hoặc triển khai production.
