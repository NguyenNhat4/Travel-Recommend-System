# Đề xuất thêm AC-AGT-07: nút gợi ý ba hướng, thẻ có câu dẫn, xử lý người dùng khó

- Ngày: 2026-10-09
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: dang dở
- Phạm vi: docs, agent

## Mục tiêu

Người dùng review kịch bản mô phỏng và yêu cầu thêm:

- Câu trả lời thân thiện cho "mình không biết đi đâu hết, mình ở nhà".
- Xử lý được người dùng khó: nhắn khó hiểu, khó tính, cộc lốc, không quen công nghệ.
- Nút gợi ý không lặp cùng một mẫu câu ("Đà Nẵng có gì", "Hà Nội có gì"). Ba nút phải là ba việc khác nhau, ví dụ lập
  kế hoạch, khám phá.
- Thẻ không liệt kê thành một khối, mà dẫn dắt từng thẻ một.

## File thay đổi

- `docs/prd/update/2026-10-09-goi-y-truoc-khi-lap-lich.md` — sửa:
  - thêm AC-AGT-07: nút gợi ý, thẻ có câu dẫn, giọng điệu, bốn nhóm người dùng khó;
  - thêm điểm cần chốt 8 (ai viết nút gợi ý);
  - thêm vào mục "Lý do" lỗi nghi ngờ: câu hỏi cách đặt có thể bị xếp `out_of_scope`;
  - cập nhật "Thay đổi source" và danh sách golden case.
- `history/2026-10-09-de-xuat-nut-goi-y-the-dan-dat-nguoi-dung-kho.md` — thêm: entry này.

## Quyết định

- Ba hướng cho nút gợi ý: đi tiếp (lập lịch), xem sâu một khía cạnh, đổi hướng.
  - Không lặp nút lượt trước, trừ nút lập lịch; nút này được viết lại theo thông tin mới.
  - Đề xuất để LLM viết nút, code kiểm và thay bằng mẫu khi không đạt.
- Thẻ dẫn dắt dùng lại cơ chế đã có của Web: `WidgetNarration.tsx` đặt thẻ ngay sau dòng đầu tiên nhắc
  `[Tên](product:id)`, như lời diễn giải lịch trình (`user-flow.md` §4.2). Phía Web chỉ cần áp cho lượt khám phá.
- Người dùng khó:
  - Khó tính: nhớ nơi hoặc sản phẩm bị chê, không gợi ý lại; đổi hẳn một chiều; nêu chênh lệch bằng số; nói rõ đánh đổi.
  - Cộc lốc: tối đa 2 câu; đã đồng ý lập lịch thì hiện ngay form điền sẵn. Vẫn không tự đoán ngày như AC-AGT-01.
  - Câu có tục tĩu xen nội dung thì trả lời phần nội dung. Câu chỉ có tục tĩu vẫn từ chối như hiện nay.
  - Tin rác vẫn đi luật tầng 1 (không gọi LLM), chỉ sửa câu cố định và thêm nút.
- Phát hiện khi soạn tình huống: `CLASSIFY_PROMPT` xếp "booking, payment or cart actions" vào `out_of_scope`, nên câu
  "k bit dat phong sao" có thể bị từ chối 400. Đề xuất ghi rõ: hỏi cách dùng là trong phạm vi, chỉ từ chối khi yêu cầu
  trợ lý tự đặt, thanh toán.
- Mọi ví dụ trong trang mô phỏng dùng dữ liệu thật của snapshot catalog 30/09/2026: giá, điểm, giờ mở cửa, khoảng cách
  tính từ toạ độ. Ví dụ: hostel gần phố cổ 158.149–220.014 ₫, Sun World Fansipan Legend, khách sạn Đà Lạt dưới 400.000 ₫.

## Kiểm tra

- Chỉ sửa tài liệu, không chạy test.
- Đã đọc `src/frontend/src/features/itinerary/widget/WidgetNarration.tsx` để xác nhận Web đã đặt thẻ sau lần nhắc đầu.
- Lỗi `out_of_scope` với câu hỏi cách đặt mới suy ra từ prompt, chưa có trace.

## Còn lại / rủi ro

- Chờ người dùng chốt đề xuất (tám điểm mở và AC-AGT-07).
- Lấy trace cho "k bit dat phong sao" và "mình không biết đi đâu hết, mình ở nhà" để xác nhận hành vi hiện tại trước khi
  code.
- Kiểm tự động "giọng điệu" (tối đa một câu hỏi, nút không trùng mẫu câu) cần luật chấm mới cho golden; chưa thiết kế.
