# Khách không trả lời câu hỏi thông tin chuyến: trợ lý đề xuất lựa chọn phổ biến, không đưa form

- Ngày: 2026-10-14
- Người đề xuất: Nguyễn Minh Nhật / Claude Code
- Trạng thái: đã áp dụng
- Chốt bởi / ngày: Nguyễn Minh Nhật, 2026-10-14 (chat: "stop sent the form", rồi "yes — the assistant proposes a common choice")
- PRD bị ảnh hưởng: `docs/prd/requirements.md` §3 AC-AGT-07 (đoạn **Cộc lốc**)
- Mã FR/NFR: FR-AGT-01, AC-AGT-01, AC-AGT-07

## Lý do

Trợ lý v2 chưa có form trong response. Đo 14/10 (model thật, 9 lần): khách đáp "ko biết", "tùy bạn" hay "k" sau câu
hỏi số ngày/ngày đi/số người thì trợ lý hỏi lại gần y nguyên câu cũ. Người dùng chọn không đưa form ở chỗ này: trợ lý
tự đề xuất một lựa chọn phổ biến để khách chỉ cần gật đầu, thay vì phải điền form hay trả lời lại.

## Nội dung đề xuất

`requirements.md` §3 AC-AGT-07, đoạn **Cộc lốc**:

- Hiện tại: "Đã đồng ý lập lịch mà không muốn trả lời câu hỏi thì hiện ngay form điền sẵn (AC-AGT-01), không hỏi thêm
  bằng câu chữ."
- Thay bằng: "Đã đồng ý lập lịch mà không muốn hoặc chưa biết trả lời câu hỏi (*"ko biết"*, *"tùy bạn"*) thì trợ lý
  tự đề xuất một lựa chọn phổ biến cho trường còn thiếu (ví dụ 3 ngày, khởi hành cuối tuần gần nhất, 2 người lớn) và
  xin xác nhận bằng một câu có/không kèm nút đồng ý; không lặp lại câu hỏi cũ, không đưa form. Khách đồng ý thì lập
  lịch ngay; khách nêu giá trị khác thì dùng giá trị đó. *(Chốt 14/10/2026,
  `update-archive/2026-10-14-de-xuat-lua-chon-pho-bien-khi-khach-khong-tra-loi.md`.)*"

Nút **Điền thông tin chuyến đi** của AC-AGT-01 khi còn thiếu trường vẫn giữ nguyên; đề xuất này chỉ đổi lượt khách né
câu hỏi.

## Thay đổi source sau khi chốt

- `src/backend/app/agents/orc_v2.py` — PROMPT, mục Lập lịch: câu né câu hỏi → đề xuất lựa chọn phổ biến + một nút.
- `src/evaluation/agent/assistant_v2_cases.py` — ca `short-unknown`, `short-whatever`, `short-k` đã có; đo lại.
- `docs/spec/hop-dong-tich-hop-itinerary-assistant.md` — ghi quy ước ở mục v2.
