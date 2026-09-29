# Tách `classify` / `extract`, ngữ cảnh hội thoại cho mọi lượt gọi LLM, hỏi gộp ngày đi – số người – ngân sách

- Ngày: 2026-09-25
- Người đề xuất: Nguyễn Minh Nhật / Claude Code
- Trạng thái: đã áp dụng
- Chốt bởi / ngày: Nguyễn Minh Nhật, 2026-09-25 (chốt trong phiên làm việc: "go do" cho phần tách node; chọn "hỏi một lần" và "gộp một câu" cho số người, ngân sách)
- PRD bị ảnh hưởng: `docs/prd/architecture.md` §3 (sơ đồ trợ lý), `docs/prd/requirements.md` §3 (AC-AGT-01)
- Mã FR/NFR: FR-AGT-01, FR-AGT-02, NFR-SEC-01

## Lý do

- `classify` cũ vừa phân loại vừa trích intent bằng một prompt dài; câu có lệnh chèn lọt sang nhánh du lịch, và lỗi phân loại khó đo riêng. Người dùng muốn `classify` chỉ phân luồng bằng prompt rất ngắn: ngoài phạm vi / trò chuyện → `converse`; du lịch → trích intent rồi `clarify` nếu thiếu; lỗi → `dead_letter`.
- Mọi node gọi LLM phải có ngữ cảnh cả hội thoại; trước đây bước chọn tên điểm đến không có.
- Người dùng muốn trợ lý hỏi thêm số người và ngân sách, không chỉ ngày đi.

## Nội dung đã áp dụng

**`docs/prd/architecture.md` §3:** sơ đồ thêm bước `ClassifyTurn` trước `AnalyzeIntent` (ngoài phạm vi và trò chuyện trả lời ngay, du lịch đi tiếp); ghi mọi lượt gọi LLM nhận cùng ngữ cảnh hội thoại (lịch sử có giới hạn + chuyến đi đã chốt + sản phẩm đã cho xem + câu hỏi gần nhất).

**`docs/prd/requirements.md` §3, AC-AGT-01:** câu hỏi thêm sau khi có điểm đến và số ngày là một câu gộp ngày đi, số người, ngân sách (chỉ phần còn thiếu), hỏi một lần; người dùng bỏ qua mục nào thì vẫn lập lịch.

Quy tắc chi tiết (spec):
- Graph 11 node: `intake → classify ─┬→ extract ─┬→ tool …` / `├→ clarify`; `classify ─┬→ converse`; lỗi → `dead_letter`.
- `classify` output một nhãn `travel | conversation | out_of_scope`. Đặt chỗ, thanh toán, chèn lệnh, đòi secret là `out_of_scope` (400 qua `converse`). Yêu cầu chỉ có `intentOverride` bỏ qua LLM của `classify`.
- Bỏ luật cũ "câu bị gọi là conversation mà có chi tiết chuyến đi vẫn là travel": `classify` quyết luồng một mình, dựa vào câu hỏi gần nhất của trợ lý.
- Chi tiết chuyến đi (`startDate`, `party`, `budget`) hỏi gộp một lần, chỉ trước lần lập lịch đầu tiên; "chưa chốt ngày" ngay câu đầu thì ngày không tính là thiếu.
- Giữ giới hạn lịch sử ở spec §6 (20 message, 8.000 ký tự); thông tin cũ được giữ qua tóm tắt chuyến đi.

## Ảnh hưởng

- Thêm một lượt gọi LLM cho mỗi lượt du lịch (khoảng 0,5–1 giây).
- Contract: `ItineraryNeedsClarification.missingFields` thêm `party`, `budget` (thêm, không phá vỡ).
- Đề xuất `update/2026-09-25-goi-y-ngay-hom-nay-khi-chua-chot-ngay-di.md` vẫn chờ chốt, cần viết lại theo câu hỏi gộp nếu chốt.

## Thay đổi source

Xem `history/2026-09-25-tach-classify-extract-hoi-chi-tiet-chuyen-di.md`.
