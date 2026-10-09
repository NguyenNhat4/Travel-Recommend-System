# Khoá thẻ phương án theo khách sạn và đêm; thẻ đổi khách sạn ghi rõ đêm

- Ngày: 2026-10-08
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: frontend, docs

## Mục tiêu

Người dùng báo lỗi console Next.js: "Encountered two children with the same key
`4afe1590-…+7e74c08e-…`" ở `WidgetStayOptions`. Chuyến dài có đổi khách sạn: hai phương án cùng hai khách sạn nhưng chia
đêm khác nhau. Backend coi đó là hai phương án (`routing._signature` = `(productId, nights)`), còn `stayCardKey` chỉ ghép
id khách sạn nên trùng khoá; trên thẻ hai phương án này cũng trông giống hệt nhau.

## File thay đổi

- `src/frontend/src/features/itinerary/widget/widgetPlan.ts` — `stayCardKey` = `productId:fromNight:nights` của từng
  khách sạn (từ `plan.stays`).
- `src/frontend/src/features/itinerary/widget/WidgetStayOptions.tsx` — thẻ có từ 2 khách sạn ghi mỗi khách sạn một dòng
  "Đêm x–y · Tên" (thay dòng "+ Tên").
- `src/frontend/src/features/itinerary/widget/WidgetPlanPanel.tsx` — khoá hiệu ứng trượt dùng `stayCardKey` (đổi giữa hai
  cách chia đêm cũng có hiệu ứng).
- `src/frontend/tests/unit/widgetStayOptions.test.tsx` — thêm test hai phương án cùng hai khách sạn, chia đêm khác.
- `docs/spec/hop-dong-tich-hop-frontend.md` — sửa: mô tả `stayCardKey`, dòng đêm trên thẻ.

## Kiểm tra

- Test mới fail trên code cũ (3 thẻ chỉ ra 2 khoá), pass sau khi sửa.
- `cd src/frontend && node_modules/.bin/vitest run`: 72 files, 732 tests passed; `node_modules/.bin/tsc --noEmit`: sạch.
- Chưa tái hiện trên trình duyệt (cần chuyến ≥ 5 ngày có đổi khách sạn).
