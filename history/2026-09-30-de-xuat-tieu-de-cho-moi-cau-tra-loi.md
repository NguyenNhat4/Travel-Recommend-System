# Đề xuất dòng tiêu đề in đậm cho các câu trả lời của trợ lý

- Ngày: 2026-09-30
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/itinerary-agent-guardrails
- Trạng thái: hoàn thành
- Phạm vi: agent, docs

## Mục tiêu

Câu báo giá trị không hợp lệ đã có dòng đầu in đậm tóm tắt phần chi tiết. Người dùng muốn mọi câu trả lời khác của trợ lý (hỏi thiếu thông tin, form gợi ý, mâu thuẫn, ngoài phạm vi, không có kết quả, dự phòng) cũng có dòng tiêu đề tóm tắt như vậy. Bước đề xuất; phần áp dụng ở `history/2026-09-30-tieu-de-cho-moi-cau-tra-loi.md`.

## File thay đổi

- `docs/prd/update-archive/2026-09-30-tieu-de-cho-moi-cau-tra-loi.md` — thêm: đề xuất (tạo ở `docs/prd/update/`, đã chốt và chuyển sang archive cùng ngày) kèm danh sách trường hợp và tiêu đề đề xuất.

## Quyết định

- Theo AGENTS.md §8: hành vi mới lệch spec/golden hiện hành nên dừng ở đề xuất tới khi người dùng chốt; người dùng chốt bằng "oke code di" (2026-09-30) với phạm vi mặc định (các dòng "Có").
- Định dạng giữ nguyên chuỗi `**Tiêu đề**\nchi tiết` trong các trường sẵn có, không thêm field vào contract.
- Không sửa `docs/prd/requirements.md` (quyết định trước đó của người dùng).

## Kiểm tra

- Không có (chỉ thêm tài liệu).

## Còn lại / rủi ro

- Không có; xem entry áp dụng.
