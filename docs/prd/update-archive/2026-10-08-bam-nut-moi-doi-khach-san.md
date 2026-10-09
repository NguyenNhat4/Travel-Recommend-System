# Bấm thẻ chỉ làm nổi thẻ, bấm nút "Đổi" mới đổi khách sạn

- Ngày: 2026-10-08
- Người đề xuất: Nguyễn Minh Nhật / Claude Code
- Trạng thái: đã áp dụng
- Chốt bởi / ngày: Nguyễn Minh Nhật, 2026-10-08 (chọn "Nổi thẻ + xem trước")
- PRD bị ảnh hưởng: `docs/prd/requirements.md` §3 (AC-AGT-04)
- Mã FR/NFR: FR-AGT-05, AC-AGT-04
- Bổ sung cho: `update-archive/2026-10-08-bam-the-doi-ngay.md`, `update-archive/2026-10-08-hang-the-thay-khach-san-noi-nghi.md`

## Lý do

Khi lướt hàng thẻ, người dùng hay chạm vào thẻ để xem kỹ. Hiện chạm thẻ là đổi khách sạn ngay, nên dễ đổi nhầm. Người dùng
muốn chạm thẻ chỉ làm nổi thẻ đó (như hover) và xem trước lịch ở cột phải, còn bấm nút "Đổi sang khách sạn này" mới đổi lịch và tính lại chênh tiền, chênh
km của các thẻ.

## Nội dung đề xuất

### `docs/prd/requirements.md` §3, AC-AGT-04

Hiện tại:

> Bấm vào một thẻ là đổi ngay sang phương án đó: bảng lịch trình bên phải, bản đồ và tổng tiền đổi theo, lựa chọn được lưu
> lại cho các lượt sau, và khung chat không thêm tin nhắn nào; thẻ vừa bấm thành "Đang chọn", khách sạn vừa bỏ thành một thẻ
> để quay lại được.

Thay bằng:

> Bấm vào một thẻ thì thẻ đó nổi lên và bảng lịch trình bên phải, bản đồ, tổng tiền hiện lịch của phương án đó để xem
> trước, chưa đổi lịch đã lưu; trong lúc xem trước, cột phải ghi rõ "Đang xem trước" kèm nút đổi và nút quay lại, nút thanh
> toán tạm khoá. Mỗi thẻ phương án có nút "Đổi sang khách sạn này"; bấm nút là đổi ngay
> sang phương án đó: bảng lịch trình bên phải, bản đồ và tổng tiền đổi theo, chênh tiền và chênh km của các thẻ tính lại so
> với lịch mới, lựa chọn được lưu lại cho các lượt sau, và khung chat không thêm tin nhắn nào; thẻ vừa đổi thành "Đang
> chọn", khách sạn vừa bỏ thành một thẻ để quay lại được.

## Thay đổi source sau khi chốt

- Frontend: `src/frontend/src/features/itinerary/widget/WidgetStayOptions.tsx` (chạm thẻ: nổi thẻ + xem trước; nút "Đổi sang
  khách sạn này" riêng), `useFloatingWidget.ts` (trạng thái xem trước), `WidgetPlanPanel.tsx` (dải "Đang xem trước", khoá
  thanh toán); test `src/frontend/tests/unit/widgetStayOptions.test.tsx`.
- Spec: `docs/spec/hop-dong-tich-hop-frontend.md` (dòng `stayOptions`).
- Backend, contract: không đổi.
