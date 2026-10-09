# Bấm thẻ khách sạn là đổi ngay, không thêm tin nhắn

- Ngày: 2026-10-08
- Người đề xuất: Nguyễn Minh Nhật / Claude Code
- Trạng thái: đã áp dụng
- Chốt bởi / ngày: Nguyễn Minh Nhật, 2026-10-08 (chọn "Bấm thẻ là đổi luôn" và "Lưu ngầm lên server")
- PRD bị ảnh hưởng: `docs/prd/requirements.md` §3 (AC-AGT-04)
- Mã FR/NFR: FR-AGT-05, AC-AGT-04
- Bổ sung cho: `update-archive/2026-10-08-chon-phuong-an-bang-nut.md`

## Lý do

Khi dùng thử hàng thẻ, người dùng thấy hai bước "bấm thẻ để xem trước, rồi bấm Dùng phương án này", cộng thêm một tin nhắn
người dùng và một câu trả lời mới trong chat, là thừa. Đổi khách sạn nên giống đổi một lựa chọn bình thường: bấm là lịch
và tổng tiền đổi ngay.

## Nội dung đề xuất

### `docs/prd/requirements.md` §3, AC-AGT-04

Hiện tại:

> Bấm vào một thẻ thì bảng lịch trình bên phải hiện ngay lịch của phương án đó kèm bản đồ, chưa đổi lịch đã lưu. Người
> dùng chọn phương án bằng nút "Dùng phương án này", hoặc nhắn "lấy phương án N" / tên khách sạn. Khi chọn đúng một
> phương án đã hiện, lịch đổi đúng như phương án đã báo (cùng khách sạn, cùng chênh tiền và chênh km), không tìm lại sản
> phẩm; câu trả lời chỉ nêu ngắn phần thay đổi, kèm hàng thẻ mới, trong đó khách sạn vừa bỏ thành một thẻ để quay lại
> được.

Thay bằng:

> Hàng thẻ nằm ngay dưới khách sạn của mục "Nơi nghỉ". Bấm vào một thẻ là đổi ngay sang phương án đó: bảng lịch trình
> bên phải, bản đồ và tổng tiền đổi theo, lựa chọn được lưu lại cho các lượt sau, và khung chat không thêm tin nhắn nào;
> thẻ vừa bấm thành "Đang chọn", khách sạn vừa bỏ thành một thẻ để quay lại được. Người dùng cũng có thể nhắn "lấy
> phương án N" / tên khách sạn; khi đó câu trả lời chỉ nêu ngắn phần thay đổi. Khi chọn đúng một phương án đã hiện, lịch
> đổi đúng như phương án đã báo (cùng khách sạn, cùng chênh tiền và chênh km), không tìm lại sản phẩm.

## Thay đổi source sau khi chốt

- Backend: lượt `selectStayOption` không có `message`, không thêm lượt vào lịch sử hội thoại; archive cập nhật câu trả
  lời gần nhất (`ConversationArchivePort.update_last_turn`) thay vì thêm tin nhắn. Lượt gõ "lấy phương án N" giữ câu trả
  lời ngắn.
- Frontend: bỏ xem trước và nút "Dùng phương án này"; bấm thẻ đổi ngay (lạc quan), gửi `selectStayOption` ở nền, lỗi thì
  quay lại lịch cũ; hàng thẻ đặt dưới khách sạn của mục "Nơi nghỉ".
- Spec: `docs/spec/hop-dong-tich-hop-frontend.md`, `docs/spec/hop-dong-tich-hop-itinerary-assistant.md`,
  `docs/spec/agent/nghiep-vu/sua-lich-qua-nhieu-luot.md`.
