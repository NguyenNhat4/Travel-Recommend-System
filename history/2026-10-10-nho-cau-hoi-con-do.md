# Nhớ câu hỏi còn dở khi trợ lý hỏi lại nơi; khách sạn "gần phố cổ" theo khoảng cách (lỗi G, chat thử 10/10)

- Ngày: 2026-10-10
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: agent, docs
- Mã FR/NFR: FR-AGT-01 (hội thoại đa lượt), FR-AGT-06 (đề xuất `docs/prd/update/2026-10-09-goi-y-truoc-khi-lap-lich.md`,
  đã chốt), NFR-REL-01
- Plan: `docs/plan/2026-10-10-sua-loi-chat-thu-tro-ly.md`, đơn vị 4

## Mục tiêu

"có khách sạn nào có hồ bơi gần phố cổ không?" → trợ lý (LLM) hỏi "điểm đến nào" → "hà nội cha ơi" → ra "Hà Nội có gì"
chung chung (2 điểm tham quan + 2 khách sạn, một khách sạn không có hồ bơi). Kịch bản bản 5 cảnh 5: danh sách khách sạn có
hồ bơi quanh phố cổ.

## File thay đổi

- `src/backend/app/agents/steps/exploration.py` — sửa: `ask_old_quarter` (hỏi Hà Nội hay Hội An kèm 2 nút), `resumed`
  (câu trả lời ngắn nêu điểm đến → trả lời câu hỏi gốc), `near_phrase` + lượt tìm mốc (`NEAR_CALL_ID`) + `_landmark`, `pick`
  lọc khách sạn trong 1,5 km quanh mốc (lý do `near`), `near_place` cho LLM, `open_question` ghi khi hỏi lại và xoá khi khám
  phá xong; `_relinked` bỏ in đậm và dấu cách thừa trong chữ link.
- `src/backend/app/domain/itinerary/exploration.py` — sửa: thêm `within_km`.
- `src/backend/app/agents/nodes.py` — sửa: `CONVERSATION_PHASE` thêm `open_question`; `_fare_settled` bỏ nó khi lượt đi
  nhánh khác.
- `src/backend/app/agents/state.py` — sửa: field `open_question`.
- `src/backend/app/agents/steps/messages.py` — sửa: `explore_ask_old_quarter`, `chip_old_quarter`, `explore_filtered_near`.
- `src/backend/app/agents/steps/prompts.py` — sửa: `EXPLORE_PROMPT` luật `near_place`.
- `src/backend/tests/unit/agents/test_open_question.py` — thêm: 8 test.
- `docs/spec/agent/state-fields.md`, `docs/spec/agent/langgraph-nodes.md` — sửa: `open_question`, hai dòng bảng `classify`
  (nơi chưa rõ thành phố; hỏi về một nơi — bổ sung cho lỗi B).
- `history/2026-10-10-nho-cau-hoi-con-do.md` — thêm: entry này.

## Quyết định

- Tên field là `open_question`, không dùng lại `pending_question` (field cũ đã gỡ có chủ đích ngày 28/09,
  `test_lab_copy` khoá việc đó).
- Chỉ nối lại khi câu trả lời ngắn (≤ 6 từ) và nêu một điểm đến catalog; câu dài là câu hỏi mới.
- "Gần" khi hỏi chỗ ở = 1,5 km đường chim bay quanh mốc catalog (kịch bản dùng 1 km; nới chút vì toạ độ mốc là tâm khu
  phố cổ). Không tìm được mốc có toạ độ thì giữ cách chọn cũ, không tự nói "gần".

## Kiểm tra

- `pytest src/backend/tests/unit/agents src/backend/tests/unit/domain`: 1940 passed.
- Backend local (`inprocess`, LLM thật, catalog snapshot 30/09):
  - "có khách sạn nào có hồ bơi gần phố cổ không?" → "Bạn muốn tìm quanh phố cổ Hà Nội hay phố cổ Hội An?" + 2 nút (3/3 lần);
    "hà nội cha ơi" → 4 khách sạn có hồ bơi, cách Khu Phố Cổ 0,2–1,1 km (Classyc Hang Buom, Proverb, Rue de L'amour, Grand
    Sol), câu mở "Quanh phố cổ Hà Nội…"; trước khi lọc khoảng cách có L7 West Lake (5,9 km).
  - "Phố cổ Hội An" → khách sạn có hồ bơi ở Hội An.

## Còn lại / rủi ro

- Câu hỏi gốc đi `classify` → `travel` (thay vì `explore`) thì chưa ghi `open_question` (chỉ ghi ở `explore`).
