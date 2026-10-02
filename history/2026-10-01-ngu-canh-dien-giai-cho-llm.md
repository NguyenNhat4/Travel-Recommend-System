# Ngữ cảnh đã diễn giải cho LLM, hiểu "đi biển", "đổi" không phải mâu thuẫn

- Ngày: 2026-10-01
- Tác giả: nhatnm / Claude Code
- Nhánh: feat/itinerary-agent-guardrails
- Trạng thái: hoàn thành
- Phạm vi: agent, docs

## Mục tiêu

Người dùng thấy agent "không hiểu hội thoại". Hội thoại thật (LangSmith `nhat-10-1`, 01/10 08:27–08:34 UTC):
"đi hà nội" → "3 ngày" → "doi diem di" → "không đổi nữa" (lịch trình Hà Nội) → "mình muốn đi biển cơ" → "biển hà nội"
(×2). Bằng chứng từ input/output LLM trong trace:

- T3 "doi diem di": `extract` trả cả `conflict=true` lẫn `change_without_value=["destination"]`; `conflict` được xét
  trước nên agent hỏi "xác nhận lại điểm đến và số ngày" thay vì "đổi sang đâu" (việc còn lại của
  `history/2026-10-01-khong-hoi-lai-khi-rut-lai-yeu-cau-doi.md`).
- T5 "mình muốn đi biển cơ": `extract` điền `destination="biển"` → ngoài catalog → câu "chỉ hỗ trợ trong nước" (sai lý
  do). Cùng lượt, LLM chép `specific_hotel="The Sun Ha Noi Hotel"`, `hotel_price_max=550000 PER_NIGHT`,
  `require_hotel`, `party_type_hint=COUPLE` từ lịch trình cũ trong lịch sử.
- T6/T8 "biển hà nội": `extract` không có điểm đến → `suggest_form`; `clarify` không biết vì sao thiếu điểm đến nên
  chép lại lý do "chỉ trong nước" từ lịch sử, lặp nguyên câu.
- Gốc chung: payload mọi lượt LLM là bản dump thô — cả lịch sử, lịch trình cũ kèm giá xuất hiện hai lần
  (`conversation_history` và `last_assistant_message`), `known_intent` dạng JSON; không LLM nào được cho biết lượt
  trước trợ lý đã làm gì và vì sao. Người dùng đề xuất "enrich input" thay vì ném nguyên JSON vào prompt.

Phục vụ FR-AGT-01 (làm rõ địa điểm, phong cách du lịch), FR-AGT-05, AC-AGT-01. Không lệch PRD:
`docs/prd/architecture.md` §3 "Ngữ cảnh cho LLM" vẫn đủ bốn phần (lịch sử có giới hạn, chuyến đi đã chốt, sản phẩm đã
cho xem, câu hỏi gần nhất), chỉ đổi cách trình bày. Không đổi contract.

## File thay đổi

- `src/backend/app/agents/steps/turn_notes.py` — thêm: `trip_summary` (chuyến đi một dòng + trường còn thiếu), `stage`, `question_note` (lượt hỏi lại: hỏi gì, vì sao), `turn_note` (ghi chú câu trả lời vừa chốt, không có giá).
- `src/backend/app/agents/steps/history.py` — sửa: tin trợ lý lưu thêm `note`; `llm_context` trả `trip_so_far`, `stage`, `conversation_history` (tin trợ lý = ghi chú), `last_assistant_message` (nguyên văn khi ≤ 500 ký tự, không thì ghi chú), `known_constraints`, `previous_selection`; bỏ `known_intent`. Lịch sử cũ không có `note` dùng câu gọn hoặc tiêu đề.
- `src/backend/app/agents/nodes.py` — sửa: `finalize` dựng `turn_note` và lưu kèm tin trợ lý; `intake` khởi tạo `destination_kind`.
- `src/backend/app/agents/state.py` — sửa: thêm `destination_kind`.
- `src/backend/app/agents/models.py` — sửa: `Extraction.destination_kind`.
- `src/backend/app/agents/steps/classification.py` — sửa: lý do `destination_kind` (không tăng `clarification_rounds`, giữ intent); bỏ `conflict` của LLM khi đó là xin đổi chưa có giá trị; bỏ loại nơi bị điền nhầm vào `patch.destination`; bỏ `specific_hotel`/`specific_activity` chép từ `previous_selection` mà câu chat không nhắc.
- `src/backend/app/agents/steps/tool_planning.py` — sửa: `check_destination` nạp `supported_destinations` cho lý do `destination_kind` kể cả khi chưa có điểm đến.
- `src/backend/app/agents/steps/conversation.py` — sửa: payload có `this_turn`; lý do `destination_kind` có `destination_kind` + `supported_destinations`, tiêu đề và câu dự phòng riêng (không liệt kê điểm đến), không kèm `clarificationForm`.
- `src/backend/app/agents/steps/prompts.py` — sửa: CLASSIFY (khoá payload mới; "ok"/"được"/"bỏ qua"/"không" trả lời câu hỏi chuyến đi là `travel`), EXTRACT (loại nơi, đổi ≠ mâu thuẫn, ràng buộc chỉ từ câu mới nhất), CONVERSATION (`this_turn`, `trip_so_far`, lý do `destination_kind`, `unsupported_destination` chỉ nói "trong Việt Nam" khi nơi đó ở nước ngoài).
- `src/backend/app/agents/steps/messages.py` — sửa: `money`, `party_text` (chuyển từ `narration`); câu ghi chú/tóm tắt vi + en; tiêu đề/câu dự phòng `destination_kind`; câu `unsupported_destination` không còn nói "chỉ trong Việt Nam".
- `src/backend/app/agents/steps/narration.py` — sửa: dùng `money`/`party_text` của `messages`.
- `src/backend/app/agents/steps/__init__.py` — sửa: mô tả `turn_notes`.
- `src/backend/tests/unit/agents/test_turn_context.py` — thêm: 23 test (ghi chú, `llm_context` không còn giá, lịch sử cũ, đổi ≠ mâu thuẫn, `destination_kind`, khách sạn chép từ lịch trình cũ, nạp catalog, payload/form/câu dự phòng, `finalize` lưu ghi chú).
- `src/backend/tests/unit/agents/test_classify.py`, `test_conversation_history.py`, `test_itinerary_runtime.py` — sửa: theo khoá ngữ cảnh mới, `note` trong lịch sử, câu `unsupported_destination` tiếng Anh mới.
- `docs/spec/agent/langgraph-nodes.md` — sửa: mục "Ngữ cảnh cho LLM", `destination_kind`, bảng node `classify`/`extract`/`clarify`/`finalize`.
- `docs/spec/agent/state-fields.md` — sửa: `conversation_history.note`, `clarification_reason = destination_kind`, field `destination_kind`.
- `docs/spec/hop-dong-tich-hop-itinerary-assistant.md` — sửa: §6 ngữ cảnh đã diễn giải; bảng tiêu đề thêm dòng loại nơi.
- `history/2026-10-01-ngu-canh-dien-giai-cho-llm.md` — thêm: entry này.

## Quyết định

- Ghi chú lượt trợ lý dựng bằng luật ở `finalize` từ state đã chốt, không gọi LLM thêm; lưu trong working state (Redis/
  archive `workingState`) nên khôi phục từ archive vẫn còn. API lịch sử hội thoại đọc `app.conversation_messages`, không
  lộ `note`.
- Mọi node vẫn nhận cùng một `llm_context` (không thu gọn riêng `classify` — đề xuất đó đã bị xoá, xem
  `history/2026-09-30-xoa-ba-de-xuat-cho-chot.md`).
- "biển" là loại nơi chứ không phải điểm đến: LLM của `clarify` chọn 3–4 tên hợp loại **chỉ trong** `supported_destinations`
  (tên điểm đến từ catalog, không phải dữ liệu sản phẩm, nên không đụng grounding). Câu dự phòng không liệt kê tên vì luật
  không biết nơi nào có biển.
- Lưới an toàn ràng buộc chỉ bỏ `specific_hotel`/`specific_activity` trùng sản phẩm đã cho xem mà câu chat không nhắc; không
  lọc `hotel_price_max` theo chữ số vì người dùng viết số bằng chữ ("dưới một triệu"). Giá đã không còn trong ngữ cảnh.
- Đã thử cờ `repeated` (lượt này hỏi y hệt lượt trước) để LLM không lặp câu: gpt-4o-mini vẫn trả gần nguyên văn, nên bỏ,
  không giữ luật chưa có tác dụng.
- Trong lúc làm, một phiên khác dùng chung cây làm việc đã khôi phục `nodes.py`, `history.py`, `messages.py`,
  `narration.py`, `state.py` về HEAD (16:27:36); các thay đổi trên được áp dụng lại.

## Kiểm tra

- `.venv/bin/python -m pytest -q src/backend/tests`: 1069 passed, 21 skipped (trước khi chỉnh CLASSIFY_PROMPT lần cuối);
  sau đó `src/backend/tests/unit/agents src/backend/tests/architecture src/backend/tests/contract`: 401 passed.
- Chạy lại hội thoại với LLM thật (`.env`, gpt-4o-mini), graph đầy đủ, catalog fixture 50 sản phẩm, script trong scratchpad:
  - T3 "doi diem di" → `change_without_value`, hỏi đổi sang đâu (hiện là Hà Nội); T4 "không đổi nữa" → lịch trình Hà Nội.
  - T5 "mình muốn đi biển cơ" → `destination_kind`, gợi ý Phú Quốc, Nha Trang, Hạ Long, Đà Nẵng; `constraints = {}`.
  - T6/T7 "biển hà nội" → "Hà Nội không có biển, …" kèm cùng gợi ý; không còn câu "chỉ hỗ trợ trong nước", không có form.
  - "đi biển 3 ngày" → hỏi chọn điểm đến biển → "đà nẵng" → hỏi ngày đi/số người/ngân sách. Chuỗi Hà Nội → biển → "ok nha
    trang" → lịch trình Nha Trang.
- Hồi quy: "ok" trả lời câu hỏi ngân sách bị xếp `conversation` 3/6 lần với ngữ cảnh mới (HEAD: `travel` 3/3, chạy trong
  worktree tạm của HEAD). Sau khi thêm câu vào CLASSIFY_PROMPT: `travel` 6/6.
- So HEAD và bản mới trên 4 kịch bản đa lượt, mỗi kịch bản 2 lần (hỏi dần → lịch; đổi khách sạn; "chưa biết"; "đổi ngày"
  → "20/10"): chuỗi status giống hệt nhau.
- Chưa chạy golden eval (`src/evaluation/agent/golden.py`), chưa thử qua trình duyệt.

## Còn lại / rủi ro

- Người dùng lặp lại đúng câu ("biển hà nội" lần hai) vẫn nhận câu trả lời gần như y hệt.
- Chạy golden eval để đo trên bộ 76 case: ngữ cảnh đổi cho mọi node nên có thể lệch ở case chưa thử.
- "đổi điểm đi" được hiểu là đổi điểm đến (contract không có điểm xuất phát).
- LLM không tất định; số đo trên là một model, catalog fixture, vài lần chạy.
