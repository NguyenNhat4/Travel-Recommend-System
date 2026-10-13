# Plan: agent nhớ kết quả đã cho xem, bớt cứng nhắc

- Ngày: 2026-10-12
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: dang dở
- Phạm vi: agent, docs
- Bị thay thế bởi: `2026-10-12-chinh-thiet-ke-orchestrator.md`

## Mục tiêu

"hà nội" → "ngoài ra còn gì nữa" (và "đi rồi") trả lại đúng 4 thẻ cũ. Tìm nguyên nhân gốc thay vì vá câu, và viết plan cho
coding agent khác implement sau.

## File thay đổi

- `docs/plan/2026-10-12-nho-ket-qua-da-xem.md` — thêm: bằng chứng, nguyên nhân gốc (lỗi lặp và sự cứng nhắc), hướng chia
  việc LLM/code, giai đoạn 1 (state `shown`, trường `followup`), giai đoạn 2 (LLM dẫn lượt khám phá), bộ đo, bản nháp đề
  xuất PRD, việc còn mở.

## Quyết định

- Luật kiểm trên 57 hội thoại snapshot: 15/39 cặp lượt lặp, 4 lỗi thật cùng kiểu (câu nói về quan hệ với kết quả lượt
  trước), còn lại lặp hợp lý.
- Nguyên nhân gốc: state không lưu kết quả đã hiện; `TurnRoute` không có trường quan hệ với lượt trước; chê nơi bằng regex;
  `fares.answer_text` bỏ qua `cheaper` khi có ngày đi; snapshot ghi cả hành vi sai. Cứng nhắc vì AC-AGT-06 viết như kịch
  bản, vòng chat thử → vá, LLM chỉ viết lời, ~30 regex đoán ý. LangGraph không phải nguyên nhân.
- Người dùng chọn hướng LLM hiểu câu và tự quyết tool, code chỉ kiểm và tính; **giai đoạn 2 là hướng chính**, đo và test
  hồi quy làm sau (mục 8 của plan, cờ giữ `rules` tới khi đo). Bỏ trường `followup`. Orchestrator–worker chưa làm.
- Thêm bước "ngữ cảnh chung, gọn cho mọi node LLM": khối "đã gợi ý" dựng bằng luật, mỗi sản phẩm một dòng với trường cần
  thiết theo loại (mã ngắn, giá niêm yết, tiện ích, giờ mở…), lịch tóm theo ngày, thứ tự payload tránh *lost in the
  middle*. Bước này và state `shown` hiện thực đúng `architecture.md` §3 ("Ngữ cảnh cho LLM", "Hội thoại") nên không chờ
  chốt.
- Viết lại plan chi tiết theo hướng orchestrator để Claude Code thực thi ở phiên sau: `classify` thành orchestrator
  (`TurnPlan` 1–3 việc, chê/đồng ý/xin form do LLM); một việc đi nhánh cũ, worker tự viết lời; nhiều việc chạy node
  `workers` song song (chỉ trả dữ liệu) rồi node `synthesize` (orchestrator lần 2) viết một câu trả lời, khối vé chèn bằng
  `[[fare_block]]`; worker khám phá LLM tự gọi tool chỉ đọc; gác cổng `domain/itinerary/gatekeeper.py`; mã ngắn `#n`
  thay `productId` trong ngữ cảnh LLM; cờ `ITINERARY_ORCHESTRATOR`, `ITINERARY_EXPLORE_MODE`. Không đổi contract (vé + khám
  phá dùng chung `searchResults`).
- Orchestrator là vòng lặp: giao việc → đọc kết quả → giao tiếp (`delegate`, kể cả việc khác loại phụ thuộc kết quả
  trước, ví dụ vé rẻ nhất rồi khám phá nơi đó), hỏi lại, hoặc trả lời (`answered`, `not_found`, `failed`). Node `workers` và
  `orchestrate`; đường tắt cho lượt một việc đã trả lời xong; phanh do code: tối đa 3 vòng, ngân sách thời gian, trần lời
  gọi tool, không giao lại việc y hệt, mỗi việc phải có kết cục, tối đa một câu hỏi mỗi lượt.
- Theo yêu cầu người dùng, gộp plan, đề xuất PRD và hai entry history của cùng việc thành một plan: đề xuất PRD
  (`docs/prd/update/2026-10-12-nho-ket-qua-da-xem.md`, chưa commit) đã xoá, nội dung thành mục 6 của plan; người thực thi
  tạo lại đề xuất khi người dùng chọn hướng.

## Kiểm tra

- Script scratchpad đo lặp trên `snapshot.json`; tái hiện `["hà nội","đi rồi","tạm biệt","khách sạn","Đà Nẵng có gì chơi?"]`
  trên `feat/agent` (`e4f0bb86`), `inprocess` + LLM thật: "đi rồi" lặp 4 thẻ, ba lượt còn lại đúng. Kiểm `says_stop`: có ở
  `origin/release-mvp-v2`, `origin/feat/agent`, không có ở `origin/main`. Chưa sửa code, chưa chạy test.

## Còn lại / rủi ro

- Toàn bộ plan; đề xuất PRD chưa tạo (phần khám phá lệch AC-AGT-06, phải chốt trước khi sửa code).
- Chờ người dùng: hướng (giai đoạn 1 đủ hay đi thẳng giai đoạn 2), số thẻ, phạm vi `shown`.
- Môi trường người dùng test chạy bản chưa có luật dừng: deploy `release-mvp-v2` rồi test lại.
