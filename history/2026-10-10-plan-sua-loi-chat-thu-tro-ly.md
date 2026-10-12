# Plan sửa các lỗi từ đợt chat thử trợ lý (10/10)

- Ngày: 2026-10-10
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: docs

## Mục tiêu

Viết lại ghi chú chat thử trợ lý (lộn xộn) thành một plan task rõ ràng: lỗi người dùng gặp, nguyên nhân, đơn vị việc,
cách kiểm tra.

## File thay đổi

- `docs/plan/2026-10-10-sua-loi-chat-thu-tro-ly.md` — thêm: plan 6 đơn vị việc cho lỗi A–I.

## Quyết định

- Giữ cấu trúc 6 đơn vị song song của plan phiên trước; đối chiếu lại từng nguyên nhân với code ở `ab4e375`.
- Giả thuyết lỗi E "state lượt hỏi vé không có `previous_plan`" chưa xác nhận: code lưu (`nodes.py:709`) và nạp lại
  (`nodes.py:140`) khoá này, nên plan yêu cầu tái hiện trước khi sửa.
- Ghi rõ ba điểm cần người dùng chốt: phần hỏi giá vé sau khi có lịch thuộc đề xuất
  `docs/prd/update/2026-10-09-hoi-dap-doi-ve-khach-san-sau-lich.md` (chờ chốt); đổi hành vi NO_RESULTS của đơn vị 5;
  câu "vé" mơ hồ hỏi lại hay mặc định vé máy bay.

## Kiểm tra

- Chỉ thêm tài liệu; không chạy test.

## Còn lại / rủi ro

- Chờ người dùng chốt ba điểm ở mục 3 của plan trước khi giao đơn vị 3 (phần đã có lịch) và đơn vị 5.
