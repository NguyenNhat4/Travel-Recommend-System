# Hàng thẻ phương án là nội dung mục "Nơi nghỉ"; hết giật khi bấm thẻ, chuyển mượt

- Ngày: 2026-10-08
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: frontend, docs

## Mục tiêu

Người dùng thử hàng thẻ và báo: (1) bấm thẻ khách sạn lần đầu thì khung chat bị giật; (2) mục "Nơi nghỉ" hiện khách sạn
2–3 lần (dòng chữ, thẻ gọn, rồi thẻ đầu của hàng thẻ), hàng thẻ là đủ; (3) muốn tối đa 5 phương án; (4) muốn hiệu ứng mượt
khi chọn. Đề xuất `docs/prd/update-archive/2026-10-08-hang-the-thay-khach-san-noi-nghi.md`: người dùng chốt phần (2)
("Chỉ bỏ thẻ khách sạn", bổ sung "mục Nơi nghỉ là chỗ của hàng thẻ, không hiện khách sạn cố định nữa"); phần (3) **không
chốt**, giữ tối đa 3. (1) và (4) không lệch PRD.

## Nguyên nhân giật (đọc từ code)

- `useFloatingWidget`: effect cuộn chat xuống cuối chạy theo `[isOpen, messages, isExpanded]`. Bấm thẻ lần đầu vừa mở panel
  (`setIsExpanded(true)`) vừa thay `response` của tin cuối (`messages` tính lại) nên chat bị kéo xuống cuối hai lần.
- `WidgetNarration`: khách sạn của các phương án nằm trong `narrationProducts`, lời diễn giải không nhắc nên bị nối thành
  thẻ ở cuối bong bóng; hàng thẻ neo theo thẻ khách sạn cuối cùng nên nhảy chỗ sau khi đổi.
- `WidgetStayOptions`: server đưa lịch vừa chọn lên đầu và đánh số lại, khoá React theo `index` nên các thẻ đổi chỗ.

## File thay đổi

- `docs/prd/requirements.md` — sửa: AC-AGT-04, hàng thẻ là nội dung mục "Nơi nghỉ", chuyển mượt, giữ thứ tự.
- `docs/prd/user-flow.md` — sửa: §4.2 mục "Thẻ trong khung chat", khách sạn không có dòng chữ hay thẻ gọn khi có hàng thẻ.
- `docs/prd/update-archive/2026-10-08-hang-the-thay-khach-san-noi-nghi.md` — thêm: đề xuất, `đã áp dụng` (chỉ phần đã chốt).
- `docs/spec/hop-dong-tich-hop-frontend.md` — sửa: dòng `stayOptions`.
- `src/frontend/src/features/itinerary/widget/WidgetNarration.tsx` — sửa: `narrationBlocks` nhận `slotIds`, mục chứa dòng
  đầu nhắc khách sạn của hàng thẻ bỏ mọi dòng nhắc chúng và đặt một khối `slot`; prop `after` → `stays`; khách sạn của hàng
  thẻ không có thẻ gọn, tên ở mục ngày vẫn là link.
- `src/frontend/src/features/itinerary/widget/WidgetChat.tsx` — sửa: truyền `stays`, `selectingKey`.
- `src/frontend/src/features/itinerary/widget/WidgetStayOptions.tsx` — sửa: giữ thứ tự lần hiện đầu (khoá theo khách sạn),
  thẻ vừa bấm thành "Đang chọn" ngay ("Đang lưu…"), hàng trượt tới thẻ, chuyển màu/viền 300 ms; bỏ tiêu đề trùng "Phương án
  khác" (đã nằm dưới "Nơi nghỉ").
- `src/frontend/src/features/itinerary/widget/useFloatingWidget.ts` — sửa: `selectingStay` là khoá khách sạn; chat chỉ tự
  cuộn khi có tin mới hoặc chữ tin cuối dài thêm.
- `src/frontend/src/features/itinerary/widget/widgetPlan.ts` — sửa: `stayCardKey`; comment `narrationProducts`.
- `src/frontend/src/features/itinerary/widget/WidgetPlanPanel.tsx`, `WidgetDays.tsx`, `src/frontend/src/app/globals.css` —
  sửa: lịch và tổng tiền ở cột phải trượt vào khi đổi khách sạn (`stay-swap-in`, tắt khi `prefers-reduced-motion`).
- `src/frontend/tests/unit/widgetNarration.test.tsx`, `src/frontend/tests/unit/widgetStayOptions.test.tsx` — sửa/thêm.

## Quyết định

- Mục "Nơi nghỉ" nhận diện bằng dòng đầu tiên nhắc khách sạn của hàng thẻ (tiêu đề do LLM viết, không neo theo chữ); mục kết
  thúc ở tiêu đề `**…**` kế tiếp. Dòng không nhắc khách sạn trong mục (lý do chọn) giữ lại.
- Không đổi backend: `apply_option` vẫn chạy như trước.
- Tối đa 3 phương án giữ nguyên (người dùng không chốt nâng lên 5).

## Kiểm tra

- `cd src/frontend && node_modules/.bin/vitest run`: 72 files, 729 tests passed; `node_modules/.bin/tsc --noEmit`: sạch.
- Chưa xem trên trình duyệt (hiệu ứng và việc hết giật chỉ kiểm qua code + jsdom).

## Còn lại / rủi ro

- Cần thử thật trên trình duyệt: bấm thẻ cuối lần đầu, mobile.
- Đề xuất `docs/prd/update/2026-10-08-ung-vien-da-dang-va-diem-mien-phi.md` vẫn chờ chốt.
