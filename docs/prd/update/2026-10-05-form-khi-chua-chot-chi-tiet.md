# Đưa form gợi ý khi người dùng không trả lời được ngày đi, số người, ngân sách

- Ngày: 2026-10-05
- Người đề xuất: Nguyễn Minh Nhật / Claude Code
- Trạng thái: đã chốt
- Chốt bởi / ngày: Nguyễn Minh Nhật, 2026-10-05
- PRD bị ảnh hưởng: `docs/prd/requirements.md` §3 (AC-AGT-01), `docs/prd/user-flow.md` (đoạn "Form gợi ý thông tin chuyến đi", dòng 181), `docs/prd/architecture.md` §3 (sơ đồ, cạnh `AskUser --> SuggestForm`)
- Mã FR/NFR: FR-AGT-01, FR-AGT-03

## Lý do

Tái hiện ngày 05/10 trên LangSmith (`nhat-10-1`, conversation `9841548a-089e-4fd7-9d12-129112ce3b4a`):

```text
T1: Đi Đà Nẵng   → hỏi số ngày (câu chữ)
T2: 3 ngày       → hỏi gộp ngày đi, số người, ngân sách
T3: không biết   → lập lịch ngay, không có form
```

AC-AGT-01 hiện ghi: người dùng "nói chưa chốt" thì xuất lịch trình, và form gợi ý chỉ hiện khi vẫn thiếu **điểm đến hoặc số ngày**. Vì vậy ở T3 agent lập lịch luôn với ngày đi, số người, ngân sách đều trống. Người dùng mong thấy form: người không nghĩ ra câu trả lời thì chọn từ giá trị gợi ý dễ hơn tự gõ, và lịch trình dựa trên số người, ngày đi mà người dùng đã duyệt thay vì để trống.

## Nội dung đề xuất

**`docs/prd/requirements.md` §3, AC-AGT-01**

- Hiện tại: "Người dùng trả lời đủ, trả lời một phần hoặc nói chưa chốt; khi đó trợ lý xuất ra lịch trình 3 ngày có cấu trúc; …"
- Đề xuất: "Người dùng trả lời đủ hoặc trả lời một phần; khi đó trợ lý xuất ra lịch trình 3 ngày có cấu trúc; … Nếu câu trả lời không cho thêm được trường nào trong ba trường này (ví dụ 'không biết', 'chưa chốt'), trợ lý không lập lịch ngay mà hiển thị form thông tin chuyến đi đã điền sẵn giá trị gợi ý như mô tả dưới đây, kèm một câu mời chọn hoặc giữ nguyên gợi ý."
- Câu mở đầu đoạn form, hiện tại: "Người dùng đã được hỏi một lượt mà câu trả lời vẫn không cho biết điểm đến hoặc số ngày thì trợ lý không hỏi lại bằng câu chữ nữa: nó hiển thị …"
- Đề xuất: "Người dùng đã được hỏi một lượt mà câu trả lời vẫn không cho biết điểm đến hoặc số ngày, hoặc không cho thêm được ngày đi, số người hay ngân sách, thì trợ lý không hỏi lại bằng câu chữ nữa: nó hiển thị …"
- Thêm cuối ô: "Form cho ngày đi, số người, ngân sách chỉ hiện một lần mỗi hội thoại; người dùng bỏ qua form và vẫn không cho thêm thông tin thì trợ lý lập lịch với các trường còn trống như hiện nay."

**`docs/prd/user-flow.md`** (dòng 181)

- Hiện tại: "khi trợ lý đã hỏi một lượt mà vẫn chưa biết điểm đến hoặc số ngày, khung chat hiển thị …"
- Đề xuất: "khi trợ lý đã hỏi một lượt mà vẫn chưa biết điểm đến hoặc số ngày, hoặc người dùng không trả lời được ngày đi, số người, ngân sách, khung chat hiển thị …"

**`docs/prd/architecture.md` §3**

- Hiện tại: `AskUser --> SuggestForm: Đã hỏi một lượt mà vẫn thiếu điểm đến/số ngày`
- Đề xuất: `AskUser --> SuggestForm: Đã hỏi một lượt mà vẫn thiếu điểm đến/số ngày, hoặc không thêm được ngày đi–số người–ngân sách`

**Đánh đổi**

- Thêm một lượt bấm trước khi thấy lịch trình. Người nói "cứ lập lịch đi" mà không cho thêm thông tin cũng nhận form; xác nhận ngay thì giá trị gợi ý được dùng. Không tách hai trường hợp này để luật vẫn tất định, không phụ thuộc LLM đoán ý.
- Chỉ xét lượt **ngay sau** câu hỏi gộp. Hỏi đã bị chen ngang thì theo đề xuất đang chờ `2026-10-02-hoi-tiep-khi-cau-hoi-bi-cat-ngang.md`.

**Liên quan đề xuất đang chờ `2026-10-02-hoi-tiep-khi-cau-hoi-bi-cat-ngang.md`:** đề xuất đó coi "nói chưa chốt" là đã trả lời câu hỏi gộp. Hai đề xuất khớp nhau nếu hiểu là: "chưa chốt" vẫn tính là đã trả lời (không hỏi lại bằng câu chữ), nhưng lượt đó đưa form thay vì lập lịch ngay. Chốt cả hai thì câu "nói chưa chốt" trong đề xuất 2026-10-02 được sửa theo nghĩa này.

## Thay đổi source sau khi chốt

- `src/backend/app/agents/steps/classification.py` — `extract_result`: lượt ngay sau câu hỏi gộp, đủ điểm đến và số ngày, không thêm được trường nào trong `startDate`/`party`/`budget`, không phải lượt sửa bằng chip, form chi tiết chưa từng hiện → `decision="missing_info"`, `clarification_reason="suggest_form"`, `missing_fields` là các trường còn trống. Thêm cờ state đánh dấu form chi tiết đã hiện để không lặp.
- `src/backend/app/agents/steps/conversation.py` — `_form_shown`: nhận thêm trường hợp `suggest_form` cho ngày đi, số người, ngân sách; `reply_title`, `prompts.py`, `messages.py`, `turn_notes.py` dùng lại `suggest_form`, chỉ chỉnh câu chữ nếu cần.
- `src/backend/app/agents/state.py` (hoặc nơi khai báo state) — thêm cờ mới.
- Contract: không đổi (`clarificationForm` đã có). Frontend: không đổi (widget đã render form, xác nhận gửi ngay).
- Test: unit test `extract_result` cho hội thoại trên (fail trên code cũ); golden case "Đi Đà Nẵng → 3 ngày → không biết".
- Spec: `docs/spec/hop-dong-tich-hop-itinerary-assistant.md`, `docs/spec/agent/field-review.md` — đồng bộ điều kiện hiện form.
