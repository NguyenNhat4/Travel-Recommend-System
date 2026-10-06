# Xác nhận giữ chuyến cũ khi người dùng rút lại yêu cầu đổi

- Ngày: 2026-10-02 (rút gọn 2026-10-05)
- Người đề xuất: Nguyễn Minh Nhật / Claude Code
- Trạng thái: đã áp dụng (2026-10-05)
- Chốt bởi / ngày: Nguyễn Minh Nhật, 2026-10-05 (chốt bản rút gọn)
- PRD bị ảnh hưởng: `docs/prd/requirements.md` §3 (AC-AGT-01)
- Mã FR/NFR: FR-AGT-01, FR-AGT-05

## Lý do

Test case TC-04 (`src/evaluation/agent/agent-test-cases-nhat.md`), tái hiện ngày 02/10 trên LangSmith (`nhat-10-1`, run `01a0fba2-32b3-7ca3-b81e-b71101762192`):

```text
T1: đi hà nội 3 ngày   → hỏi ngày đi, số người, ngân sách
T2: đổi điểm đi        → hỏi đổi sang đâu
T3: không đổi nữa      → lập lịch Hà Nội 3 ngày ngay
```

Bản 02/10 nêu hai lỗi:

1. **Lập lịch khi người dùng chưa trả lời câu hỏi chi tiết.** Đề xuất `2026-10-05-classify-route-clarify.md` (đã áp dụng) giải quyết lỗi này: còn thiếu ngày đi hoặc số người thì trợ lý hiện form, không lập lịch. Bản rút gọn bỏ phần này, bỏ luôn cờ `details_pending`.
2. **Không xác nhận lại chuyến cũ.** Người dùng vừa đổi ý hai lần (muốn đổi, rồi thôi). Golden 05/10 (`claude-golden-vague`): lượt T3 đã hiện form đúng, nhưng câu trả lời chỉ nói "Còn thiếu ngày khởi hành, số người và ngân sách…", không cho người dùng biết chuyến Hà Nội 3 ngày vẫn được giữ.

## Nội dung đề xuất

**`docs/prd/requirements.md` §3, AC-AGT-01** — thêm sau câu "Ngân sách không bắt buộc: có thì dùng, không có vẫn lập lịch.":

- Thêm: "Khi trợ lý vừa hỏi người dùng muốn đổi thông tin chuyến đi thành gì mà người dùng rút lại ('không đổi nữa', 'thôi giữ nguyên'), trợ lý giữ thông tin cũ và nói rõ điều đó trong câu trả lời (ví dụ 'Mình giữ chuyến Hà Nội 3 ngày nhé'), rồi làm tiếp như bình thường: còn thiếu trường bắt buộc thì hiển thị form, đã đủ thì lập lịch."

So với bản 02/10: không thêm lượt hỏi xác nhận riêng. Chuyến đi đã đủ trường thì lập lịch luôn, kèm câu nói giữ chuyến cũ.

## Ảnh hưởng

- Chỉ đổi câu chữ của lượt rút lại yêu cầu đổi; luồng graph và contract không đổi.
- Đảo một phần quyết định trong `history/2026-10-01-khong-hoi-lai-khi-rut-lai-yeu-cau-doi.md`: rút lại vẫn không hỏi lại, nhưng câu trả lời phải nói rõ giữ chuyến cũ.

## Thay đổi source sau khi chốt

- `src/backend/app/agents/steps/prompts.py`: `CONVERSATION_PROMPT` (lượt hỏi/form) và `NARRATE_PROMPT` (lượt lập lịch) thêm chỉ dẫn xác nhận giữ chuyến cũ khi người dùng rút lại yêu cầu đổi. Nhận diện "rút lại" là việc hiểu câu chữ, để LLM viết câu dựa trên `last_assistant_message` và `message`.
- Test: unit test cho prompt; golden TC-04 (đã có tiêu chí judge "Trợ lý xác nhận vẫn đi Hà Nội 3 ngày.").
