# Form thông tin chuyến đi hiện cho tới khi đủ các trường

- Ngày: 2026-10-05
- Người đề xuất: Nguyễn Minh Nhật / Claude Code
- Trạng thái: đã áp dụng (2026-10-05)
- Chốt bởi / ngày: Nguyễn Minh Nhật, 2026-10-05
- PRD bị ảnh hưởng: `docs/prd/requirements.md` §3 (AC-AGT-01), `docs/prd/user-flow.md` (đoạn "Form gợi ý thông tin chuyến đi", dòng 184), `docs/prd/architecture.md` §3 (sơ đồ StateGraph)
- Mã FR/NFR: FR-AGT-01, FR-AGT-03

## Lý do

Golden TC-10 ("Đi Đà Nẵng 3 ngày" → "không biết") fail ngày 05/10: ở lượt 2 graph đi `classify → extract → tool`, lập lịch khi ngày đi, số người và ngân sách đều trống, và không hiện form.

Đề xuất đã chốt `2026-10-05-form-khi-chua-chot-chi-tiet.md` chỉ hiện form khi câu trả lời không thêm được trường nào, và mỗi hội thoại chỉ hiện một lần. Người dùng muốn chặt hơn: còn thiếu trường bắt buộc thì chưa lập lịch, và form tiếp tục hiện cho tới khi đủ. Người dùng trả lời một phần ("2 người") cũng nhận form, trong đó giá trị đã biết được điền sẵn.

## Nội dung đề xuất

Trường bắt buộc để lập lịch: **điểm đến, số ngày, ngày đi, số người**. Ngân sách vẫn được hỏi và có ô trên form nhưng không bắt buộc: có thì dùng, không có vẫn lập lịch.

**`docs/prd/requirements.md` §3, AC-AGT-01**

- Hiện tại: "Người dùng trả lời đủ hoặc trả lời một phần; khi đó trợ lý xuất ra lịch trình 3 ngày có cấu trúc; … Nếu câu trả lời không cho thêm được trường nào trong ba trường này (ví dụ "không biết", "chưa chốt"), trợ lý không lập lịch ngay mà hiển thị form …"
- Đề xuất: "Khi đủ điểm đến, số ngày, ngày đi và số người, trợ lý xuất ra lịch trình 3 ngày có cấu trúc; … Còn thiếu một trong bốn trường này (trả lời một phần, "không biết", "chưa chốt") thì trợ lý không lập lịch mà hiển thị form thông tin chuyến đi mô tả dưới đây; form điền sẵn giá trị người dùng đã nói và gợi ý cho phần còn thiếu. Form hiện ở mỗi lượt cho tới khi đủ bốn trường. Ngân sách không bắt buộc."
- Bỏ câu "Form cho ngày đi, số người, ngân sách chỉ hiện một lần mỗi hội thoại; người dùng bỏ qua form và vẫn không cho thêm thông tin thì trợ lý lập lịch với các trường còn trống."
- Câu "Người dùng đã được hỏi một lượt mà câu trả lời vẫn không cho biết điểm đến hoặc số ngày, hoặc không cho thêm được ngày đi, số người hay ngân sách" → "Người dùng đã được hỏi một lượt mà vẫn thiếu điểm đến, số ngày, ngày đi hoặc số người".

**`docs/prd/user-flow.md`** (dòng 184)

- Hiện tại: "khi trợ lý đã hỏi một lượt mà vẫn chưa biết điểm đến hoặc số ngày, hoặc người dùng không trả lời được ngày đi, số người, ngân sách, …"
- Đề xuất: "khi trợ lý đã hỏi một lượt mà vẫn thiếu điểm đến, số ngày, ngày đi hoặc số người, khung chat hiển thị form ở mỗi lượt cho tới khi đủ, …"

**`docs/prd/architecture.md` §3**

- Thêm: `ClassifyTurn --> SuggestForm: Câu trả lời không thêm được thông tin chuyến đi ("không biết") khi còn thiếu điểm đến/số ngày/ngày đi/số người`
- `AskUser --> SuggestForm: Đã hỏi một lượt mà vẫn thiếu điểm đến/số ngày, hoặc không thêm được ngày đi–số người–ngân sách` → `AskUser --> SuggestForm: Đã hỏi một lượt mà vẫn thiếu điểm đến, số ngày, ngày đi hoặc số người`
- `CheckClarification --> SearchCandidates: Đủ thông tin cơ bản` → `CheckClarification --> SearchCandidates: Đủ điểm đến, số ngày, ngày đi, số người`

**Hai đường tới form**

- `classify` có thêm nhãn `vague`: tin nhắn trả lời câu hỏi chuyến đi trong `last_assistant_message` nhưng không thêm được thông tin nào ("không biết", "tuỳ bạn"). Nhãn này đi thẳng `clarify` với form, không qua `extract`, nên bớt được một lượt gọi LLM. Luật tất định kèm theo: nếu `trip_so_far` đã đủ bốn trường hoặc chưa có lượt trợ lý nào thì `vague` được xử lý như `travel`.
- Câu trả lời một phần ("2 người") vẫn là `travel`, đi qua `extract` để giữ thông tin; còn thiếu trường thì `extract` route sang `clarify` kèm form (luật tất định).

**Đánh đổi**

- Thêm lượt bấm: người dùng chỉ thấy lịch trình khi đủ bốn trường. Câu đầu đã đủ thì vẫn lập lịch ngay.
- `start_date_undecided` ("chưa biết ngày") không còn miễn ngày đi: ngày đi thiếu thì vẫn hiện form, form gợi ý sẵn hôm nay.
- Nhãn `vague` do LLM quyết. Nếu LLM gắn nhầm `vague` cho một câu có thông tin, thông tin đó bị bỏ qua ở lượt này, nhưng form vẫn hiện để người dùng điền lại.

## Thay đổi source sau khi chốt

- `src/backend/app/agents/models.py` — `TurnRoute.route` thêm `vague`.
- `src/backend/app/agents/steps/prompts.py` — `CLASSIFY_PROMPT` định nghĩa `vague`.
- `src/backend/app/agents/steps/classification.py` — `route_result`: `vague` + còn thiếu trường bắt buộc + đã có lượt trợ lý → `decision = "clarify"`, `clarification_reason = "suggest_form"`. `extract_result`: đã hỏi gộp một lần mà vẫn thiếu trường bắt buộc, không phải lượt sửa bằng chip → `suggest_form`; bỏ nhánh "đã hỏi rồi thì lập lịch luôn".
- `src/backend/app/agents/routing.py`, `graph.py` — cạnh `classify → clarify`.
- `src/backend/app/agents/steps/conversation.py` — `_form_shown`: nhận `suggest_form` cho mọi trường bắt buộc.
- Contract, frontend: không đổi.
- Test: unit test `route_result`, `extract_result`, routing; sửa test mã hoá hành vi cũ; golden TC-10.
- Golden `--sweep`: câu lượt 2 phải có ngày đi và số người.
- Spec: `docs/spec/agent/langgraph-nodes.md`, `docs/spec/hop-dong-tich-hop-itinerary-assistant.md`, `docs/spec/agent/field-review.md`.
- Đề xuất `2026-10-05-form-khi-chua-chot-chi-tiet.md` được thay thế bởi đề xuất này; chuyển cả hai sang `update-archive/` khi áp dụng.
