# Thẻ khách sạn trong câu trả lời trợ lý theo góp ý UX

- Ngày: 2026-10-12
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: dang dở
- Phạm vi: frontend, docs

## Mục tiêu

Sửa hàng thẻ khách sạn "Phương án khác" (`WidgetStayOptions`, AC-AGT-04, FR-AGT-04) theo góp ý UX ngày 12/10: trạng thái chọn mâu thuẫn, quá nhiều số cùng cỡ, chip chênh lệch không có nhãn, hạng sao lẫn với điểm đánh giá, chữ lộ tiêu chí lọc nội bộ, hai ghi chú km trái nhau, chữ xám nhỏ, nút "N" của Next.js đè lên nội dung.

## File thay đổi

- `src/frontend/src/features/itinerary/widget/WidgetStayOptions.tsx` — sửa: chỉ thẻ đang chọn có viền xanh đậm và nhãn "✓ Đang chọn" (nút đáy cũng ghi "Đang chọn", bỏ "Đang dùng"). Thẻ đang xem trước nổi lên với nhãn trắng, nút viền thay vì xanh đặc. "Phương án N" chuyển từ ảnh xuống cạnh nhãn loại. Số chính là "Tổng chuyến", dòng phụ "Lưu trú … · ≈x km cả chuyến". Bỏ giá một đêm và dòng "Đi lại" lặp km. Tiền làm tròn ("3,98 triệu", "850 nghìn"). Chip ghi "So với lựa chọn hiện tại" + "Rẻ hơn/Đắt hơn x", "Gần hơn/Xa hơn ≈x km". Tách "★ 4,3/5 (410 đánh giá)" khỏi "Khách sạn 5 sao". Số phòng ghi cạnh tên. Copy nhãn Cao cấp bỏ ngưỡng nội bộ. Bỏ ghi chú "đường chim bay" trên hàng thẻ. Chữ phụ 13px, `slate-600`. Sau khi xem trên trình duyệt: ảnh `absolute` trong khung 16:9 (ảnh dọc kéo thẻ cao 752px), điểm đánh giá và hạng sao mỗi thứ một dòng (dấu "·" treo cuối dòng), lưu trú và km thành hai dòng nhãn–số canh phải (chữ "chuyến" rơi dòng), chip đi liền sau số tiền thay vì `mt-auto` (khoảng trống lớn trên chip).
- `src/frontend/tests/unit/widgetStayOptions.test.tsx` — sửa theo chữ mới; thêm test tách điểm khách và hạng sao, không lộ ngưỡng lọc.
- `src/frontend/next.config.ts` — sửa: `devIndicators: false`.
- `docs/spec/hop-dong-tich-hop-frontend.md` — sửa: dòng `stayOptions` km và bản đồ, mô tả chữ mới của thẻ.
- `docs/prd/update/2026-10-12-the-khach-san-chon-mot-cham.md` — thêm: đề xuất chờ chốt cho phần lệch PRD.

## Quyết định

- Chỉ làm phần không lệch AC-AGT-04. Bỏ bước xem trước, nút "Chọn" + Hoàn tác, đổi tên "Đang dùng", dời tiền lưu trú/km vào "Xem chi tiết", bỏ dòng giải thích nhãn, đổi câu lưu ý km đều đổi điều AC ghi, nên đưa vào đề xuất và dừng.
- Giữ dòng hướng dẫn "Chạm thẻ để xem trước" vì cơ chế xem trước vẫn còn cho tới khi đề xuất được chốt.
- Giữ "Phương án N" (dạng chữ nhỏ) vì người dùng vẫn được nhắn "lấy phương án N".
- Không cắt câu quảng cáo trong tên khách sạn ở widget: dễ cắt nhầm tên thật. Ghi vào đề xuất là việc của khâu làm sạch dữ liệu.

## Kiểm tra

- `node_modules/.bin/tsc --noEmit`: sạch.
- `node_modules/.bin/vitest run`: 80 file, 832/832 passed.
- `eslint` trên file sửa: 0 lỗi.
- Trình duyệt (Playwright Chromium headless; extension Claude in Chrome chưa kết nối), backend :8000 + frontend :3000 local, LLM thật. Yêu cầu "1 ngày Đà Nẵng 2 người", trợ lý hỏi lại, trả lời "20/10, 5 triệu, xuất phát từ Hà Nội" → hàng 3–4 thẻ. Ở 1440px (widget sidebar) và 390px: console không lỗi/cảnh báo, không request lỗi; mọi thẻ cùng chiều cao, nút đáy cùng toạ độ, không thẻ nào tràn hay bị cắt; ảnh cao 143px (trước khi sửa: ảnh dọc làm thẻ cao 752px).
- Chrome thật (Claude in Chrome), cùng kịch bản, widget sidebar rộng 584px: 3 thẻ cao 612px, nút đáy cùng toạ độ, ảnh 143px, không phần tử nào tràn; console từ lần nạp trang đầu qua hai lượt hội thoại chỉ có log React DevTools/HMR, không lỗi hay cảnh báo. Nút "N" vẫn hiện vì `next dev` chưa khởi động lại.
- `vitest run` sau lần sửa cuối: 832/832 passed; `tsc --noEmit` sạch; eslint 0 lỗi.

## Còn lại / rủi ro

- Chờ chốt `docs/prd/update/2026-10-12-the-khach-san-chon-mot-cham.md`, rồi sửa `WidgetStayOptions.tsx`, `WidgetChat.tsx`, `useFloatingWidget.ts`, `WidgetPlanPanel.tsx` theo đề xuất.
- `devIndicators: false` chỉ có hiệu lực sau khi khởi động lại `next dev`.
- Ở 390px thẻ cao khoảng 670px, cao hơn vùng chat nhìn thấy; phần "Xem chi tiết" trong đề xuất sẽ làm thẻ thấp lại.
- Tiền làm tròn trên thẻ có thể lệch vài nghìn so với bảng chi phí cột phải (số đầy đủ).
- Chưa commit theo yêu cầu người dùng.
