# Lịch v2 kể theo ngày; trẻ em không hỏi riêng, câu cụt không phải dừng

- Ngày: 2026-10-14
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: codex/orc-autonomous-tools
- Trạng thái: hoàn thành
- Phạm vi: agent, evaluation, docs
- Mã FR/NFR: FR-AGT-01, AC-AGT-01, AC-AGT-07; PRD `user-flow.md` §4.2 (wireframe **Ngày 1** + thẻ sau câu)

## Mục tiêu

Chat 14/10, ba lỗi trợ lý v2:

1. Lịch mới "đang bị dạng liệt kê": lời đáp tóm tắt cả chuyến trong một đoạn, chỉ nhắc khách sạn, mọi thẻ điểm tham
   quan dồn xuống cuối. Câu hỏi sau "Xem chi tiết lịch theo từng ngày" thì ổn hơn, nên lỗi nằm ở cách orc viết lượt lập lịch.
2. Hỏi "Có trẻ em đi cùng không?", khách đáp "ko", trợ lý trả "Được nhé, mình dừng tại đây."
3. Người dùng hỏi thêm: các câu trả lời khác có thể làm agent dừng không?

## File thay đổi

- `src/backend/app/agents/orc_v2.py` — sửa PROMPT: (a) answer của itinerary/replace kể theo ngày: tiêu đề
  `**Ngày N — dd/mm**`, mỗi buổi một câu có đúng product của buổi đó, rồi nơi nghỉ; không viết lại nội dung disclosures;
  (b) trẻ em không bắt buộc, mặc định 0, không hỏi riêng; câu cụt ngay sau câu hỏi của trợ lý là câu trả lời cho câu
  hỏi đó, "ko" chỉ là từ chối khi câu vừa hỏi là lời mời; (c) số đi cùng "ngày/đêm" không dùng làm số người.
- `src/backend/app/application/itinerary/v2_final.py` — sửa `_join`: tiêu đề đậm đứng đầu đoạn, sau dấu kết câu hoặc
  sau link sản phẩm được tách thành dòng riêng (widget chỉ coi dòng chỉ có `**…**` là tiêu đề); đậm giữa câu giữ nguyên.
- `src/backend/tests/unit/application/test_assistant_v2_final.py` — thêm `test_day_heading_stands_on_its_own_line`.
- `src/evaluation/agent/assistant_v2_cases.py` — thêm ca `plan-by-day`, `kids-short-no`, `short-unknown`,
  `short-whatever`, `short-k`.
- `docs/spec/hop-dong-tich-hop-itinerary-assistant.md` — sửa §v2: quy ước kể lịch theo ngày, tách tiêu đề, trẻ em và câu cụt.
- `history/2026-10-14-lich-v2-ke-theo-ngay-va-cau-cut.md` — thêm: entry này.

## Quyết định

- Bằng chứng trước khi sửa (backend thứ hai ở :8001 cùng env với :8000, model thật, catalog thật), ca `plan-by-day`
  ×2 trên code cũ: lượt ra lịch viết "Ngày đầu, ghé bãi biển rồi dạo làng chài… Chỗ nghỉ là [khách sạn]" — ngày kể
  bằng chữ không có product nên thẻ dồn cuối; còn chép lại các câu cảnh báo mà code đã thêm. Lần còn lại hỏi trẻ em.
- Sửa ở prompt (LLM viết lời), không dựng lời theo ngày bằng code ở widget: kể theo ngày đúng wireframe PRD
  user-flow §4.2, không lệch PRD nên không cần đề xuất.
- Không thêm luật cấm tổng tiền trong lời: v2 không gửi `costBreakdown` nên widget v2 chưa có khối Ngân sách dự tính.
- "Dừng" do LLM quyết (`engagement`/`stopped`), không có bảng từ khoá; câu "mình dừng tại đây" là chữ LLM. Sửa bằng
  prompt theo quy tắc LLM hiểu câu. `stopped=true` gỡ consent; khách nói "lên lịch" lại vẫn là consent mới.
- Tiêu đề tách bằng code ở `_join` (bố cục, cùng chỗ đang tách đoạn quanh sản phẩm), không phải hiểu câu.

## Kiểm tra

- `pytest -q src/backend/tests/unit/application/test_assistant_v2_final.py -k heading` trên code cũ: 1 failed.
- `.venv/bin/python -m pytest -q src/backend/tests/unit/agents src/backend/tests/unit/application
  src/backend/tests/unit/domain`: 2649 passed, 3 xfailed.
- LLM thật, backend local :8001 (`assistant_v2_cases --repeat 3`):
  - `plan-by-day`: 3/3 ra lịch ở lượt 3; mỗi ngày có dòng tiêu đề riêng, thẻ ngay sau câu từng buổi. Trước khi tách
    tiêu đề bằng code, 2/3 lần tiêu đề nằm liền dòng trước.
  - `kids-short-no`: 3/3 không hỏi trẻ em, ra lịch ngay lượt 2; "ko" sau đó hiểu là không có trẻ em, giữ lịch, không dừng.
  - `short-unknown` ("ko biết"), `short-whatever` ("tùy bạn"), `short-k` ("k"): 0/9 dừng.
- Chưa chạy cả bộ backend, chưa chạy frontend (không đổi frontend).

## Còn lại / rủi ro

- "ko biết"/"tùy bạn" sau câu hỏi số ngày: trợ lý hỏi lại gần y nguyên câu cũ thay vì hiện form điền sẵn — lệch
  AC-AGT-07 (cộc lốc → form) và AC-AGT-01 (không lặp câu hỏi). Chưa sửa.
- Backend :8000 của demo chạy không `--reload`, cần khởi động lại để nhận prompt mới.
- Lượt "3 ngay, thu 6 tuan nay" ở lần đo đầu từng ra lịch với adults=3 (lấy số của "3 ngày"); đã thêm câu (c), 6 lần
  sau không lặp lại, chưa đo riêng.
