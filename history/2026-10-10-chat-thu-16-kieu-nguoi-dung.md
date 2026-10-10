# Chat thử thủ công 16 kiểu người dùng nhắn lộn xộn

- Ngày: 2026-10-10
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: evaluation
- Mã FR/NFR: FR-AGT-01, FR-AGT-04, FR-AGT-06, NFR-REL-01

## Mục tiêu

Người dùng muốn thay bộ golden bằng chạy thử từng case, quan sát và đánh giá, vì người dùng thật nhắn rất lộn xộn ("chín
người mười ý") nên không giống câu mẫu.

## File thay đổi

- `src/evaluation/reports/eval-2026-10-10-chat-thu-16-kieu-nguoi-dung.md` — thêm: đánh giá 16 hội thoại (Tốt/Tạm/Lỗi, nguyên
  nhân, đề xuất sửa) và toàn văn hội thoại.
- `history/2026-10-10-chat-thu-16-kieu-nguoi-dung.md` — thêm: entry này.

## Quyết định

- Đánh giá bằng đọc nguyên văn, không chấm tự động; mỗi hội thoại chạy một lần trên backend local, LLM thật.
- Chỉ ghi nguyên nhân đã kiểm bằng code, log hoặc DB; nguyên nhân chưa kiểm ghi rõ "chưa kiểm".

## Kiểm tra

- 16 hội thoại, 50 lượt, commit `4d0f139`: 4 tốt, 6 tạm, 6 lỗi (chi tiết trong báo cáo).

## Còn lại / rủi ro

- Chưa sửa các lỗi tìm thấy; thứ tự đề xuất ở mục "Đề xuất thứ tự sửa" của báo cáo. Lỗi Search chưa lọc khách sạn theo ngày
  đi thuộc team Search.
