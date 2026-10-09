# Hàng thẻ phương án thay khách sạn ở mục "Nơi nghỉ"

- Ngày: 2026-10-08
- Người đề xuất: Nguyễn Minh Nhật / Claude Code
- Trạng thái: đã áp dụng
- Chốt bởi / ngày: Nguyễn Minh Nhật, 2026-10-08 (chọn "Chỉ bỏ thẻ khách sạn"; bổ sung: mục "Nơi nghỉ" là chỗ của hàng
  thẻ, không hiện khách sạn cố định nữa)
- PRD bị ảnh hưởng: `docs/prd/requirements.md` §3 (AC-AGT-04), `docs/prd/user-flow.md` §4.2 (mục "Thẻ trong khung chat")
- Mã FR/NFR: FR-AGT-05, AC-AGT-04
- Bổ sung cho: `update-archive/2026-10-08-bam-the-doi-ngay.md`

## Lý do

Khi dùng thử, mục "Nơi nghỉ" có dòng chữ khách sạn ("Đêm 1 — Venus Hotel Phu Quoc …"), thẻ gọn của khách sạn đó, rồi hàng
thẻ phương án mà thẻ đầu lại là chính khách sạn đó: khách sạn hiện hai, ba lần. Sau khi bấm đổi, chữ và thẻ cũ (giữ nguyên)
vẫn nói khách sạn trước, trái với lịch đã đổi. Hàng thẻ đã đủ để thấy khách sạn đang chọn và các lựa chọn khác.

Phần nâng lên tối đa 5 phương án trong bản nháp **không được chốt**: giữ tối đa 3.

## Nội dung đề xuất

### `docs/prd/requirements.md` §3, AC-AGT-04

Hiện tại:

> Hàng thẻ nằm ngay dưới khách sạn của mục "Nơi nghỉ".

Thay bằng:

> Hàng thẻ là nội dung của mục "Nơi nghỉ", thay cho dòng chữ và thẻ gọn của khách sạn: khi có hàng thẻ, mục "Nơi nghỉ"
> không hiện khách sạn cố định nào khác, các mục ngày vẫn giữ chữ của mình. Bấm thẻ thì thẻ đó thành "Đang chọn" với
> hiệu ứng chuyển mượt, thứ tự các thẻ trong hàng giữ nguyên.

### `docs/prd/user-flow.md` §4.2, mục 1 "Thẻ trong khung chat"

Thêm cuối mục:

> Khi câu trả lời có hàng thẻ "Phương án khác" (AC-AGT-04), mục "Nơi nghỉ" chỉ hiện hàng thẻ đó: khách sạn không có dòng
> chữ hay thẻ gọn riêng.

## Thay đổi source sau khi chốt

- Frontend: `WidgetNarration.tsx`, `WidgetChat.tsx` (hàng thẻ thay dòng chữ và thẻ khách sạn của mục "Nơi nghỉ"),
  `WidgetStayOptions.tsx` (giữ thứ tự, hiệu ứng chọn), `useFloatingWidget.ts` (không tự cuộn chat khi chỉ đổi khách sạn).
- Spec: `docs/spec/hop-dong-tich-hop-frontend.md`.
