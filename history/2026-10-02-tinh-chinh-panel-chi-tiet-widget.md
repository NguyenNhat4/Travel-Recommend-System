# Tinh chỉnh panel chi tiết của widget

- Ngày: 2026-10-02
- Tác giả: người dùng / Codex
- Nhánh: feat/itinerary-agent-guardrails
- Trạng thái: hoàn thành
- Phạm vi: frontend

## Mục tiêu

Tiếp tục làm đẹp widget sau `2026-10-02-lam-dep-widget-tro-ly.md`: giải quyết nút thao tác xuống dòng ở cột hẹp, gallery ít ảnh và trạng thái tải chi tiết. Phục vụ FR-AGT-03/04, AC-AGT-01 và NFR-REL-01.

## File thay đổi

- `src/frontend/src/features/itinerary/widget/WidgetProductDetail.tsx` — sửa: nút thao tác xếp dọc ở cột hẹp, skeleton khi chưa có dữ liệu, nút thử lại đủ kích thước và thông tin dài được ngắt dòng.
- `src/frontend/src/features/itinerary/widget/WidgetProductGallery.tsx` — thêm: tách trình bày gallery; giữ kích thước ảnh khi đổi, xếp thumbnail theo số lượng, nhãn đúng số ảnh gốc và chính sách referrer thống nhất với thẻ sản phẩm.
- `src/frontend/tests/unit/widgetProductDetail.test.tsx` — sửa: kiểm tra trạng thái chờ catalog và đổi ảnh rồi trở lại ảnh đầu bằng nhãn đúng.
- `src/frontend/tests/e2e/widget-detail.spec.ts` — sửa: kiểm tra đổi ảnh bằng nút và chiều cao gallery ổn định ở 1024/1440 px.
- `history/2026-10-02-tinh-chinh-panel-chi-tiet-widget.md` — thêm: ghi phần tiếp tục này; không sửa entry lịch sử trước.

## Quyết định

- Bám PRD `user-flow.md` §4.2: giữ nguyên panel desktop thay timeline, bản đồ bên cạnh và dữ liệu catalog. Không thêm luồng hay dữ liệu sản phẩm; không lệch PRD.
- Gallery là component trình bày; tải catalog, retry, tracking, lựa chọn ảnh và giỏ hàng vẫn do panel/controller hiện có quản lý.
- Dùng Tailwind và màu/spacing có sẵn. Skeleton tắt animation khi người dùng yêu cầu giảm chuyển động.
- Giữ các thay đổi có sẵn từ lượt trước, gồm `next-env.d.ts`; không đưa file sinh tự động vào phạm vi task.

## Kiểm tra

- Vitest trên `widgetNarration`, `widgetProductDetail`, `widgetDays`, `floatingWidgetOpening`, `widgetPlan` với `--maxWorkers=2` — PASS: 5 file, 34 test.
- ESLint trên 2 component và 2 file test của phần tiếp tục — PASS.
- `git diff --check` — PASS.
- `npm run build:web` — PASS. Lần automatic approval đầu hết thời gian xét duyệt; thử lại một lần được cho phép và build hoàn tất (exit 0).
- `npm run typecheck` — PASS.
- `npm exec -- playwright test tests/e2e/widget-opening.spec.ts tests/e2e/widget-detail.spec.ts` — PASS: 8 test Chromium, 42,4 giây, exit 0. Đã xem screenshot mới ở 1024 px, xác nhận các nút xếp thành hai hàng.

## Còn lại / rủi ro

- Kiểm thử trình duyệt dùng API mô phỏng và fixture hiện có; không chứng minh backend/LLM hoặc tile bản đồ trực tiếp. Request không mô phỏng có cảnh báo proxy ECONNREFUSED vì backend local không chạy; ảnh bên ngoài chưa tải xong trong screenshot.
- Chưa commit hoặc triển khai.
