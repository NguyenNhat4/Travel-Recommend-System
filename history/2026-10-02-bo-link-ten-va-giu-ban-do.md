# Bỏ link ở tên sản phẩm đã có thẻ, giữ bản đồ khi mở panel chi tiết

- Ngày: 2026-10-02
- Tác giả: nhatnm / Claude
- Nhánh: feat/itinerary-agent-guardrails
- Trạng thái: hoàn thành
- Phạm vi: frontend, docs

## Mục tiêu

Áp dụng `docs/prd/update-archive/2026-10-02-bo-link-ten-va-giu-ban-do.md`, người dùng yêu cầu trực tiếp. Hai thay đổi:

- Tên sản phẩm đã có thẻ không còn là link xanh.
- Mở panel chi tiết vẫn thấy bản đồ.

## File thay đổi

- `docs/prd/user-flow.md` — sửa §3.2 (nhãn bước H) và §4.2 (wireframe, quy tắc 2).
- `docs/prd/update-archive/2026-10-02-bo-link-ten-va-giu-ban-do.md` — thêm: đề xuất đã áp dụng.
- `src/frontend/src/components/assistant/inlineBold.tsx` — sửa: `AssistantText` nhận `plainIds`.
- `src/frontend/src/features/itinerary/widget/WidgetNarration.tsx` — sửa: sản phẩm có thẻ thì tên in đậm, không link;
  id lạ vẫn là link.
- `src/frontend/src/features/itinerary/widget/WidgetPlanPanel.tsx` — sửa: panel chi tiết thay cột danh sách ngày, cột
  bản đồ giữ nguyên và đã focus điểm qua `openProductDetail`.
- `src/frontend/src/features/itinerary/widget/FloatingWidget.tsx` — sửa: panel toàn cột chỉ khi không có lịch trình
  (gói nhiều ngày mở từ hội thoại không có kế hoạch).
- `src/frontend/tests/unit/widgetNarration.test.tsx` — sửa: tên có thẻ là chữ thường, id lạ vẫn mở panel.
- `history/2026-10-02-bo-link-ten-va-giu-ban-do.md` — thêm: entry này.

## Kiểm tra

- `vitest run`: 52 file, 515 test PASS. `tsc --noEmit`: không có lỗi ngoài `.next/`. eslint widget: sạch.

## Còn lại / rủi ro

- Chưa xem lại trên trình duyệt. Panel chi tiết nay chỉ rộng nửa cột phải, nên bộ ảnh nhỏ hơn.
