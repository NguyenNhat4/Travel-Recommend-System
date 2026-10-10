# Chạm thẻ khách sạn để xem trước, bấm nút "Đổi" mới đổi; giữ vị trí chat khi widget mở rộng

- Ngày: 2026-10-08
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: frontend, docs
- Thay thế: quyết định "bấm thẻ là đổi ngay" trong `history/2026-10-08-bam-the-doi-ngay.md`

## Mục tiêu

Người dùng yêu cầu: chạm thẻ thì chưa đổi mà chỉ nổi thẻ lên; bấm nút đổi mới chuyển và tính lại các giá trị cộng/trừ. Đề
xuất `docs/prd/update-archive/2026-10-08-bam-nut-moi-doi-khach-san.md`, người dùng chốt "Nổi thẻ + xem trước" (chạm thẻ:
cột phải và bản đồ xem trước lịch của thẻ, chưa lưu).

## File thay đổi

- `docs/prd/requirements.md` — sửa: AC-AGT-04 (chạm thẻ xem trước, nút "Đổi sang khách sạn này" mới đổi, dải "Đang xem
  trước", khoá thanh toán khi xem trước).
- `docs/prd/update-archive/2026-10-08-bam-nut-moi-doi-khach-san.md` — thêm: đề xuất, `đã áp dụng`.
- `docs/spec/hop-dong-tich-hop-frontend.md` — sửa: dòng `stayOptions`.
- `src/frontend/src/features/itinerary/widget/WidgetStayOptions.tsx` — sửa: thẻ gồm nút xem trước (thân thẻ) và nút
  "Đổi sang khách sạn này" (chân thẻ) tách riêng; thẻ xem trước nổi lên, nhãn "Đang xem trước", nút đổi tô xanh; hàng trượt
  tới thẻ đang xem trước/đang lưu cả khi vừa dựng lại; thẻ lịch cũ trong lúc lưu không có nút đổi (chưa có số phương án).
- `src/frontend/src/features/itinerary/widget/useFloatingWidget.ts` — sửa: `stayPreview`, `previewStayOption`,
  `cancelStayPreview`, `previewedStay`; response mới thì hết xem trước; mở rộng widget vì chạm thẻ thì giữ hàng thẻ ở giữa
  khung chat (`useLayoutEffect` theo `isExpanded`), còn lại về tin mới nhất như trước.
- `src/frontend/src/features/itinerary/widget/WidgetPlanPanel.tsx` — sửa: dải "Đang xem trước … · chưa đổi" với "Quay lại"
  và "Đổi sang khách sạn này"; khoá "Thanh toán tất cả" khi xem trước.
- `src/frontend/src/features/itinerary/widget/WidgetChat.tsx` — sửa: `data-message-id`, truyền `previewKey`/`onPreview`.
- `src/frontend/tests/unit/widgetStayOptions.test.tsx` — sửa/thêm: chạm thẻ chỉ xem trước, nút mới đổi, thẻ xem trước nổi
  mà không thành "Đang chọn", khoá khi đang lưu và ở câu trả lời cũ, giữ thứ tự.

## Quyết định

- Chạm thẻ đang chọn thì thôi xem trước (về lịch đã lưu).
- Xem trước không gọi server; chỉ nút đổi gửi `selectStayOption` như trước. Backend, contract không đổi.
- Trong lúc xem trước khoá thanh toán, vì lịch xem trước chưa lưu và có thể khác lịch agent dùng ở lượt sau.

## Kiểm tra

- `cd src/frontend && node_modules/.bin/vitest run`: 72 files, 731 tests passed; `node_modules/.bin/tsc --noEmit`: sạch.
  Test mới bắt một lỗi trước khi sửa: thẻ lịch cũ lúc đang lưu hiện "phương án null" và nút đổi.
- Trình duyệt thật (Playwright headless, 1440×900, frontend :3000, backend :8000 LLM thật), yêu cầu "đi HCM 3 ngày 2 đêm từ
  20/10, 2 vợ chồng 1 đứa con, xuất phát từ Hà Nội, ngân sách 40 triệu", 2 phương án:
  - lần chạy đầu: chạm thẻ cuối khi widget chưa mở rộng làm chat về `scrollTop` 0 (khung chat dựng lại khi mở rộng) — đã
    sửa; chạy lại: `scrollTop` 649 → 649, hàng thẻ ở 65–572 px trong khung chat cao 637 px, hàng trượt tới thẻ đang xem;
  - xem trước: có dải "Đang xem trước", nút thanh toán bị khoá;
  - bấm "Đổi": "Đang chọn: Hotel Sunny Saigon", thứ tự thẻ giữ nguyên (Best Hotel, Hoang Long Son 2, Hotel Sunny Saigon),
    chênh km/tiền tính lại, vẫn 2 tin nhắn.

## Còn lại / rủi ro

- Chưa thử trên mobile.
- Thu gọn rồi mở rộng lại widget sau khi đã đổi thì hàng thẻ dựng lại theo thứ tự server (khách sạn đang chọn lên đầu).
