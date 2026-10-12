# Thẻ khách sạn: bấm Chọn là đổi ngay, mỗi thẻ một số chính

- Ngày: 2026-10-12
- Người đề xuất: Nguyễn Minh Nhật / Claude Code
- Trạng thái: chờ chốt
- Chốt bởi / ngày:
- PRD bị ảnh hưởng: `docs/prd/requirements.md` §3 AC-AGT-04 (đoạn hàng thẻ "Phương án khác" và bổ sung chốt 12/10)
- Mã FR/NFR: FR-AGT-04

## Lý do

Góp ý UX ngày 12/10 về hàng thẻ khách sạn trong câu trả lời của trợ lý:

- Cơ chế hai bước (chạm thẻ để xem trước, bấm nút để đổi) phải có dòng hướng dẫn mới dùng được. Thẻ đang xem trước trông nổi bật ngang thẻ đang chọn.
- Mỗi thẻ có khoảng 6 con số cùng cỡ chữ. Mắt không biết nhìn vào đâu.
- Dòng giải thích dưới nhãn lặp lại chính nhãn ("Tiết kiệm nhất" → "Chi phí lưu trú thấp nhất").
- Hai lưu ý về km trái nhau: lưu ý cũ ghi "đường chim bay", lưu ý trong PRD ghi "quãng đường di chuyển cả hành trình". Thực tế backend tính theo đường thẳng.

Phần không lệch PRD đã sửa ngày 12/10 (`history/2026-10-12-the-khach-san-theo-gop-y-ux.md`): chỉ dùng tên "Đang chọn", thẻ xem trước không còn nổi hơn thẻ đang chọn, số chính là "Tổng chuyến", tiền được làm tròn, chip ghi rõ "so với lựa chọn hiện tại", điểm khách chấm tách khỏi hạng sao, bỏ ghi chú "đường chim bay" thừa. Các mục dưới đây đổi điều AC-AGT-04 đang ghi, nên cần chốt.

## Nội dung đề xuất

AC-AGT-04, đoạn hàng thẻ:

1. **Bỏ xem trước, bấm Chọn là đổi ngay.**
   - Hiện tại: "Bấm vào một thẻ thì thẻ đó nổi lên và bảng lịch trình bên phải, bản đồ, tổng tiền hiện lịch của phương án đó để xem trước … trong lúc xem trước, cột phải ghi rõ "Đang xem trước" kèm nút đổi và nút quay lại, nút thanh toán tạm khoá. Mỗi thẻ phương án có nút "Đổi sang khách sạn này" …"
   - Thay bằng: "Mỗi thẻ phương án có nút "Chọn". Bấm nút thì đổi ngay sang phương án đó (bảng lịch trình, bản đồ và tổng tiền đổi theo, lựa chọn được lưu, khung chat không thêm tin nhắn), đồng thời hiện thông báo "Đã đổi sang <tên khách sạn> · Hoàn tác". Bấm Hoàn tác thì chọn lại khách sạn trước đó. Chạm thân thẻ không làm gì, chỉ rê chuột thì thẻ nhấc nhẹ lên. Không còn dòng hướng dẫn trên hàng thẻ."
   - Bản đồ "cả chuyến" (vẽ dần đường mọi ngày, gồm sân bay) chuyển sang hiện ngay khi vừa đổi khách sạn, thay cho lúc xem trước.
2. **Một tên trạng thái.** Thẻ của lịch đang dùng có viền xanh đậm, nhãn "✓ Đang dùng" và nút tắt. Các thẻ khác viền xám, nút viền xanh. Từ "Đang chọn" trong AC đổi thành "Đang dùng".
3. **Mỗi thẻ một số chính.**
   - Hiện tại (bổ sung 12/10): "Mỗi thẻ có … giải thích tiêu chí, tiền lưu trú và tổng lịch trình, tổng km ước tính; chênh lệch là phụ."
   - Thay bằng: "Mỗi thẻ có nhãn loại, tên khách sạn, điểm đánh giá và hạng sao, một số chính là tổng chuyến, và chênh tiền, chênh km so với lựa chọn hiện tại (thẻ đang dùng không có chênh lệch). Tiền lưu trú cả chuyến, giá một đêm và tổng km nằm trong phần "Xem chi tiết" của thẻ. Không có dòng giải thích tiêu chí dưới nhãn."
4. **Một lưu ý km, nói đúng cách tính.**
   - Hiện tại: "Số km là ước tính quãng đường di chuyển cả hành trình, gồm cả đường sân bay."
   - Thay bằng: "Khoảng cách là ước tính theo đường thẳng, tổng cho cả hành trình, gồm cả đường sân bay." (không có chặng bay thì bỏ vế cuối).

## Thay đổi source sau khi chốt

- `src/frontend/src/features/itinerary/widget/WidgetStayOptions.tsx`: bỏ `onPreview`/`previewKey`, nút "Chọn", nhãn "Đang dùng", phần "Xem chi tiết", câu lưu ý km mới.
- `src/frontend/src/features/itinerary/widget/WidgetChat.tsx`, `useFloatingWidget.ts`, `WidgetPlanPanel.tsx`: bỏ trạng thái xem trước và dải "Đang xem trước", thêm toast Hoàn tác (gọi lại `selectStayOption` với khách sạn trước, đã có trong `stayOptions` mới). Bản đồ `overview` bật sau khi đổi.
- `src/frontend/tests/unit/widgetStayOptions.test.tsx` và các test xem trước liên quan.
- `docs/spec/hop-dong-tich-hop-frontend.md` (dòng `stayOptions`).
- Không đổi contract: `selectStayOption` giữ nguyên.

## Chưa đề xuất

- Tên khách sạn kèm câu quảng cáo ("… - Free Shuttle Bus to Beach") và ảnh có chữ quảng cáo đến từ dữ liệu catalog. Cắt tên bằng luật ở widget dễ cắt nhầm tên thật ("Vinpearl Resort - Phú Quốc"), nên nếu cần thì sửa ở khâu làm sạch dữ liệu (`src/data_collection`).
