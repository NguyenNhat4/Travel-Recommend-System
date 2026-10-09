# Đề xuất chọn phương án bằng nút: đổi thành hàng thẻ khách sạn lướt ngang

- Ngày: 2026-10-08
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: dang dở
- Phạm vi: docs

## Mục tiêu

Người dùng tinh chỉnh đề xuất `docs/prd/update/2026-10-08-chon-phuong-an-bang-nut.md`: trong câu trả lời của trợ lý có một
hàng thẻ khách sạn lướt ngang, 3–4 thẻ, lướt qua thấy ngay đánh đổi, bấm để chọn.

## File thay đổi

- `docs/prd/update/2026-10-08-chon-phuong-an-bang-nut.md` — sửa: đoạn thay thế cho AC-AGT-04 mô tả hàng thẻ (thẻ "Đang
  chọn" + phương án khác, chênh tiền/km/vượt ngân sách trên từng thẻ), thêm mục giao diện để review, sửa mục frontend.

## Quyết định

- 3–4 thẻ = khách sạn đang chọn + tối đa 3 phương án, khớp luật hiện hành của AC-AGT-04 (tối đa 3 phương án, chênh từ 2 km).
  Không nới luật 2 km để luôn đủ 4 thẻ; khi không đủ phương án thì hàng thẻ ít thẻ hơn.
- Khách sạn vừa bỏ thành một thẻ trong hàng thẻ mới để quay lại được.
- Mockup ASCII chỉ để review, không đưa vào PRD.
- Bấm thẻ là **xem trước** (bảng lịch bên phải + bản đồ `ItineraryMap` sẵn có đổi sang phương án đó, không gọi server);
  nút "Dùng phương án này" mới đổi lịch đã lưu. Vì vậy `stayOptions` mang lịch đầy đủ của từng phương án trong response.

## Kiểm tra

- Chưa chạy lệnh nào: chỉ sửa tài liệu đề xuất.

## Còn lại / rủi ro

- Đề xuất vẫn chờ chốt; chưa sửa source.
