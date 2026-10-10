# Đề xuất hỏi đáp và đổi vé, khách sạn sau khi có lịch

- Ngày: 2026-10-09
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: dang dở
- Phạm vi: docs, agent

## Mục tiêu

Sau khi có lịch, người dùng hỏi tiếp về vé và khách sạn ("vé Phú Quốc → Hà Nội chuyến nào rẻ nhất", "đổi giờ bay",
"đổi khách sạn"). Agent cần trả lời từ dữ liệu đã tra, không chạy lại luồng lập lịch. Phạm vi chỉ gồm hỏi và đổi vé,
khách sạn.

## File thay đổi

- `docs/prd/update/2026-10-09-hoi-dap-doi-ve-khach-san-sau-lich.md` — thêm: đề xuất sửa FR-AGT-05, AC-AGT-02, thêm
  AC-AGT-05, sửa `architecture.md` §3 (nhánh mới, câu "giá luôn được tải lại").

## Quyết định

- Thay đổi lệch PRD: luồng mới chưa có trong sơ đồ `architecture.md` §3; đổi vé qua chat chưa có trong FR/AC; lưu giá đã
  tra trái với câu "Giá và tình trạng còn chỗ luôn được tải lại, không dùng bản lưu trong hội thoại". Vì vậy chỉ tạo đề
  xuất, chưa sửa code (AGENTS.md §8).
- Hướng đề xuất theo tiền lệ lượt "chọn phương án N" (AC-AGT-04): dùng lại dữ liệu lưu phía server, code viết lời đáp,
  không tìm lại. LLM chỉ dùng để hiểu câu hỏi.
- Hiện state chỉ lưu `previous_selection`, `previous_options`, `previous_plan`; `flight_options` và `candidates` không được
  lưu nên câu hỏi về các chuyến khác chưa trả lời được.

## Kiểm tra

- Không chạy test: chưa sửa code.

## Còn lại / rủi ro

- Chờ người dùng chốt đề xuất và ba điểm mở: giá trong câu trả lời dạng hỏi, kiểu response (đề xuất `COMPLETED`, không
  đổi contract), lời đáp do code hay LLM viết.
- Sau khi chốt: cập nhật PRD trước, rồi code theo mục "Thay đổi source sau khi chốt" của đề xuất.
- Working tree đang có thay đổi chưa commit của task khác (`2026-10-09-goi-nhieu-ngay-trung-dao-thu-tu-ten.md`); không
  chạm vào.
