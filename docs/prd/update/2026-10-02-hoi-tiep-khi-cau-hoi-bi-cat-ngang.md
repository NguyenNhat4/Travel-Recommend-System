# Hỏi tiếp khi câu hỏi chi tiết bị cắt ngang và xác nhận khi rút lại yêu cầu đổi

- Ngày: 2026-10-02
- Người đề xuất: Nguyễn Minh Nhật / Claude Code
- Trạng thái: chờ chốt
- Chốt bởi / ngày:
- PRD bị ảnh hưởng: `docs/prd/requirements.md` §3 (AC-AGT-01)
- Mã FR/NFR: FR-AGT-01, FR-AGT-05

## Lý do

Test case TC-04 và TC-08 (`src/evaluation/agent/agent-test-cases-nhat.md`), tái hiện ngày 02/10 trên LangSmith (`nhat-10-1`, run `01a0fba2-32b3-7ca3-b81e-b71101762192`):

```text
T1: đi hà nội 3 ngày   → hỏi ngày đi, số người, ngân sách
T2: đổi điểm đi        → hỏi đổi sang đâu
T3: không đổi nữa      → lập lịch Hà Nội 3 ngày ngay
```

Agent hiểu đúng câu T3 là rút lại yêu cầu đổi, nhưng sau đó có hai lỗi:

1. **Lập lịch khi người dùng chưa trả lời câu hỏi chi tiết.** AC-AGT-01 ghi "hỏi một lần", và hệ thống tính "đã hỏi" ngay khi hỏi xong. Câu hỏi ở T1 bị T2 cắt ngang, chưa được trả lời, nhưng vẫn bị coi là xong. TC-08 cũng vậy: "đi hà nội 3 ngày" → hỏi chi tiết → "đi PQ 3 ngày" → lập lịch Phú Quốc ngay, không có ngày đi.
2. **Không xác nhận lại điểm đến cũ.** Người dùng vừa đổi ý hai lần (muốn đổi, rồi không đổi). TC-04 yêu cầu trợ lý hỏi lại "vẫn đi Hà Nội chứ?" trước khi làm tiếp. PRD hiện chưa nói gì về trường hợp này.

## Nội dung đề xuất

**`docs/prd/requirements.md` §3, AC-AGT-01** — giữ nguyên toàn bộ, thêm hai câu sau câu "Câu đầu đã đủ ngày đi, số người và ngân sách thì xuất lịch ngay.":

- Thêm: "Câu hỏi về ngày đi, số người và ngân sách chỉ tính là đã hỏi khi người dùng đã trả lời nó: trả lời một phần, nói chưa chốt, hoặc bảo cứ lập lịch. Nếu người dùng chen ngang bằng việc khác (đổi điểm đến, đổi số ngày, xin đổi mà chưa nói đổi thành gì), trợ lý xử lý việc đó rồi hỏi lại những chi tiết còn thiếu, không lập lịch ngay."
- Thêm: "Khi trợ lý vừa hỏi người dùng muốn đổi thành gì mà người dùng rút lại ('không đổi nữa', 'thôi giữ nguyên'), trợ lý xác nhận giữ thông tin cũ (ví dụ 'Vậy mình giữ chuyến Hà Nội 3 ngày nhé?'). Nếu câu hỏi chi tiết còn chưa được trả lời thì hỏi lại trong cùng câu đó. Trợ lý không lập lịch ở lượt này; người dùng đồng ý thì lập lịch như bình thường."

Mỗi chi tiết vẫn chỉ hỏi lại khi câu hỏi trước chưa được trả lời. Người dùng đã trả lời, kể cả "không biết", "chưa chốt" hay "cứ lên lịch đi", thì trợ lý không hỏi thêm.

## Ảnh hưởng

- Thêm một lượt hỏi đáp khi người dùng rút lại yêu cầu đổi, và khi người dùng chen ngang câu hỏi chi tiết. Không ảnh hưởng tới yêu cầu đầy đủ ngay từ câu đầu.
- Đảo quyết định trong `history/2026-10-01-khong-hoi-lai-khi-rut-lai-yeu-cau-doi.md`: rút lại yêu cầu đổi khi đã hỏi chi tiết thì trước đây lập lịch ngay, nay hỏi xác nhận trước.
- Contract: không đổi. Vẫn là `NEEDS_CLARIFICATION`; `missingFields` có các chi tiết còn thiếu nếu hỏi lại.
- Golden: case nào có lượt rút lại yêu cầu đổi hoặc chen ngang câu hỏi chi tiết thì phải sửa kỳ vọng. Thêm case cho TC-04 và TC-08.

## Thay đổi source sau khi chốt

- `src/backend/app/agents/steps/classification.py`: thay cách tính "đã hỏi" bằng "câu hỏi chi tiết còn chờ trả lời" (`details_pending`); nhận diện câu rút lại theo lý do hỏi của lượt trước (`change_without_value`) và trả `clarification_reason = "change_withdrawn"`.
- `src/backend/app/agents/state.py`, `nodes.py`: lưu `details_pending` và lý do hỏi của lượt trước theo hội thoại (`intake` khôi phục, `finalize` lưu).
- `src/backend/app/agents/steps/prompts.py`, `messages.py`, `conversation.py`, `turn_notes.py`: câu xác nhận (vi/en), tiêu đề, câu dự phòng, ghi chú lượt.
- `docs/spec/agent/langgraph-nodes.md`, `docs/spec/agent/state-fields.md`, `docs/spec/hop-dong-tich-hop-itinerary-assistant.md`: cập nhật quy tắc hỏi.
- Test: unit test cho `extract_result` (chen ngang, rút lại, trả lời "cứ lên lịch"), test đồ thị nhiều lượt cho TC-04 và TC-08; case tương ứng (TC-04, TC-08) trong `src/evaluation/datasets/agent_test_cases_nhat.yaml`.
