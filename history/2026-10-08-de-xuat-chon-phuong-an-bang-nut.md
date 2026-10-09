# Đề xuất: chọn "Phương án khác" bằng một lần bấm

- Ngày: 2026-10-08
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: dang dở
- Phạm vi: docs, agent

## Mục tiêu

Người dùng muốn bấm chọn nhanh một phương án trong mục "Phương án khác" thay vì nhắn "lấy phương án 1"; lượt chọn không
chạy lại phân luồng, trích ý định, lập tool plan và tìm lại, mà đổi lịch tất định rồi chỉ viết lời ngắn.

## File thay đổi

- `docs/prd/update/2026-10-08-chon-phuong-an-bang-nut.md` — thêm: đề xuất sửa AC-AGT-04 (chọn bằng nút, đổi lịch đúng như
  phương án đã báo, không tìm lại).

## Quyết định

- AC-AGT-04 ghi "chọn phương án bằng lượt nhắn tiếp theo" nên chọn bằng nút là lệch PRD → đề xuất trước, chưa sửa source
  (AGENTS.md §8).
- Bằng chứng: trace LangSmith project `nhat-10-7`, hội thoại `f403f203-b026-4c42-8165-82eeabdb4958`, lượt "di ngay 15":
  16,5 s (classify 1,7 s, extract 2,9 s, tool plan LLM 4,1 s, compose 0,01 s, narrate 7,4 s). `compose_node` đã trả
  `stay_options` có cấu trúc; lượt "lấy phương án N" hiện vẫn đi extract → tool → search lại → compose → narrate đầy đủ.
- Hướng triển khai sau khi chốt: lưu sẵn lịch của từng phương án lúc compose; node `apply_option` lấy lịch đó ra
  (intake → apply_option → narrate ngắn → finalize); contract thêm `stayOptions` (response) và `selectStayOption` (request).

## Kiểm tra

- Chưa chạy lệnh nào: chỉ thêm tài liệu đề xuất.

## Còn lại / rủi ro

- Chờ người dùng chốt đề xuất. Sau khi chốt: cập nhật AC-AGT-04, rồi contract → backend → frontend theo mục "Thay đổi source"
  của đề xuất.
