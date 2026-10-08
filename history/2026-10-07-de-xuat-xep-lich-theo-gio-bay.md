# Đề xuất: xếp hoạt động của lịch trình theo giờ máy bay

- Ngày: 2026-10-07
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: dang dở
- Phạm vi: docs
- Bị thay thế bởi: history/2026-10-07-xep-lich-theo-gio-bay.md

## Mục tiêu

Sửa rủi ro còn lại của `history/2026-10-06-ve-may-bay-trong-lich-trinh.md`: lịch trình xếp hoạt động trước giờ máy bay
hạ cánh, ví dụ chặng đi 19:50 ngày 1 mà Bà Nà vẫn ở sáng ngày 1. Sửa việc này là thêm hành vi vào AC-AGT-02, nên theo
AGENTS.md §8 phải có đề xuất được chốt trước khi sửa source.

## File thay đổi

- `docs/prd/update/2026-10-07-xep-lich-theo-gio-bay.md` — thêm, trạng thái `chờ chốt`. Nội dung: thêm luật cửa sổ giờ
  vào AC-AGT-02.

## Quyết định

- **Xếp lịch theo giờ bay, giữ thứ tự chọn vé.** Người dùng chọn phương án này thay cho việc ưu tiên giờ bay khi chọn vé.
  Đổi thứ tự chọn vé không sửa tận gốc: nếu chỉ có chuyến tối thì lỗi vẫn còn.
- **Có dòng di chuyển** (slot `TRANSFER`, không gắn sản phẩm) vào ngày đến và ngày về. Người dùng chọn. Contract đã có
  `ActivityType.TRANSFER` và widget đã hiển thị loại slot này.
- **Khoảng đệm:** 90 phút sau giờ hạ cánh, 150 phút trước giờ cất cánh.
- **Hoạt động vẫn chỉ xếp buổi sáng và chiều**, không mở thêm buổi tối. Lý do: compose chưa đọc `openingHours` (có ở
  413/610 điểm tham quan, snapshot 2026-09-30).
- **Vé thiếu giờ bay thì ngày đó không bị giới hạn**: không đoán giờ.

## Kiểm tra

- Không chạy lệnh nào: thay đổi chỉ là tài liệu đề xuất.

## Còn lại / rủi ro

- **Đang dừng ở bước 1 của AGENTS.md §8: chờ người dùng chốt đề xuất.** Chưa sửa PRD, spec hay code.
- Sau khi chốt, làm theo thứ tự:
  1. cập nhật AC-AGT-02;
  2. thêm `day_windows` (domain);
  3. sửa `compose_plan`/`validate_plan`;
  4. chọn vé trước compose trong `composition.py`;
  5. test;
  6. spec;
  7. chuyển đề xuất sang `docs/prd/update-archive/`.
