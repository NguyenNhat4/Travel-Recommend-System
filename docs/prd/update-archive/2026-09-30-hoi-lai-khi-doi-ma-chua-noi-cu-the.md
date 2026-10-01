# Hỏi lại khi người dùng muốn đổi mà chưa nói đổi thành gì

- Ngày: 2026-09-30
- Người đề xuất: Nguyễn Minh Nhật / Claude Code
- Trạng thái: đã áp dụng
- Chốt bởi / ngày: Nguyễn Minh Nhật, 2026-09-30 ("i confirmed. go implement this plan")
- PRD bị ảnh hưởng: `docs/prd/architecture.md` §3 (sơ đồ trợ lý). `docs/prd/requirements.md` (AC-AGT-01) không sửa câu chữ, theo tiền lệ các đề xuất ngày 30/09; quy tắc ghi ở spec agent.
- Mã FR/NFR: FR-AGT-01, FR-AGT-05

## Lý do

Sau khi đã có lịch trình, người dùng nhắn "đổi ngày" hoặc "đổi địa điểm" mà không nói đổi thành gì. Trợ lý hiện lập lại
đúng lịch cũ và trả "Lịch trình đã được hoàn tất.", như thể đã làm theo yêu cầu. Người dùng không biết lịch có đổi hay
không, và không được hỏi muốn đổi sang ngày nào hay điểm đến nào.

## Nội dung đề xuất

**Quy tắc.** Người dùng muốn đổi một thông tin chuyến đi (điểm đến, số ngày, ngày khởi hành, số người, ngân sách) mà chưa
nói giá trị mới thì trợ lý không gọi tool và không lập lại lịch cũ. Nó hỏi lại đúng thông tin đó, có nêu giá trị hiện
tại, ví dụ: "Bạn muốn đổi ngày khởi hành từ 01/10 sang ngày nào?". Lượt sau người dùng nêu giá trị mới thì trợ lý lập
lịch như thường.

- Việc nhận ra "muốn đổi nhưng chưa nói đổi thành gì" do LLM hiểu ở bước trích intent, không dùng luật so sánh intent
  cũ và mới. Backend làm theo kết quả đó; chỉ bỏ qua khi LLM tự mâu thuẫn (vừa báo chưa có giá trị, vừa trích được giá
  trị cho cùng trường).
- Câu hỏi do LLM viết, có dòng tiêu đề như mọi câu hỏi lại khác; có câu cố định khi LLM lỗi.
- Không đổi contract: vẫn là `NEEDS_CLARIFICATION`, `missingFields` gồm đúng các trường cần hỏi (enum đã có đủ năm trường).
- Ngoài phạm vi đề xuất này: "không đi nữa", "ngày nào cũng được", "gợi ý lịch khác".

**`docs/prd/architecture.md` §3, sơ đồ trợ lý.**

Hiện tại:

> `CheckClarification --> AskUser: Lượt đầu thiếu thông tin, hoặc chưa hỏi ngày đi–số người–ngân sách`

Thêm ngay sau:

> `CheckClarification --> AskUser: Người dùng muốn đổi thông tin chuyến đi mà chưa nói đổi thành gì`

## Thay đổi source sau khi chốt

- `src/backend/app/agents/models.py` (`Extraction.change_without_value`), `steps/prompts.py` (`EXTRACT_PROMPT`,
  `CONVERSATION_PROMPT`), `steps/classification.py` (`extract_result`: lý do `change_without_value`),
  `steps/conversation.py`, `steps/messages.py`, docstring `nodes.py`, `state.py`.
- Test `src/backend/tests/unit/agents/`; golden G-079 trong `src/evaluation/datasets/itinerary_agent_golden.yaml`.
- Spec: `docs/spec/agent/langgraph-nodes.md`, `docs/spec/agent/state-fields.md`,
  `docs/spec/hop-dong-tich-hop-itinerary-assistant.md` §4.3.
