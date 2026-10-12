# Người dùng không muốn đi nữa: cảm ơn, hẹn gặp lại, không hiện form

- Ngày: 2026-10-12
- Người đề xuất: tqanh123 / Claude Code
- Trạng thái: đã áp dụng (2026-10-12)
- Chốt bởi / ngày: tqanh123, 2026-10-12 (tin nhắn "duyệt các thay đổi trên cho PRD": giữ chuyến đang lên để nối lại; lời
  chào do LLM viết, có câu cố định khi LLM lỗi; không thêm lưới luật)
- PRD bị ảnh hưởng: `docs/prd/requirements.md` §3 (AC-AGT-01), `docs/prd/architecture.md` §3 (sơ đồ, thêm cạnh
  `ClassifyTurn --> Converse`), `docs/prd/user-flow.md` (đoạn "Form gợi ý thông tin chuyến đi")
- Mã FR/NFR: FR-AGT-01, AC-AGT-01

## Lý do

Người dùng nhắn "ko đi nữa", "ko đi du lịch nữa" hay câu cùng ý thì trợ lý lại hiện form thông tin chuyến đi:

- Bước phân luồng cố ý xếp "không đi nữa" vào nhãn du lịch (`history/2026-09-30-sua-prompt-classify.md`, để không bị từ
  chối như yêu cầu ngoài phạm vi), nhưng chưa có cách trả lời riêng. Câu đó đi tiếp vào luồng thu thập thông tin.
- AC-AGT-01 ghi "form hiện ở mỗi lượt cho tới khi đủ bốn trường", không có ngoại lệ cho người dùng không muốn đi nữa. Vì
  vậy đã đồng ý lập lịch mà còn thiếu trường thì hiện form; đủ trường thì trợ lý tìm và lập lại lịch.
- Chưa đồng ý lập lịch (FR-AGT-06) thì câu này bị coi như nêu điểm đến và trợ lý giới thiệu điểm đến, mời lập lịch.

Người dùng muốn trợ lý cảm ơn và hẹn gặp lại.

## Nội dung đề xuất

**`docs/prd/requirements.md` §3, AC-AGT-01**

- Hiện tại: "…form hiện ở mỗi lượt cho tới khi đủ bốn trường."
- Đề xuất: "…form hiện ở mỗi lượt cho tới khi đủ bốn trường, trừ lượt người dùng nói không muốn đi hoặc không muốn lên lịch
  nữa."
- Thêm sau câu "rút lại ('không đổi nữa', 'thôi giữ nguyên') …": "Khi người dùng cho biết không muốn đi hoặc không muốn lên
  lịch nữa ('không đi nữa', 'ko đi du lịch nữa', 'thôi để lúc khác'), trợ lý không lập lịch và không hiển thị form: nó cảm ơn
  và hẹn gặp lại, không hỏi thêm, không thuyết phục; thông tin chuyến đi đang có được giữ nguyên để người dùng nối lại khi cần
  ('thôi đi tiếp')."

**`docs/prd/architecture.md` §3 (sơ đồ)**

- Thêm: `ClassifyTurn --> Converse: Người dùng không muốn đi/lên lịch nữa ("không đi nữa"): cảm ơn, hẹn gặp lại, không form,
  giữ chuyến đang lên`
- `Converse --> [*]: Trả lời hoặc từ chối, không gọi tool` → `Converse --> [*]: Trả lời, chào tạm biệt hoặc từ chối, không
  gọi tool`

**`docs/prd/user-flow.md`** (đoạn "Form gợi ý thông tin chuyến đi")

- Hiện tại: "(form hiện ở mỗi lượt cho tới khi đủ; ngân sách không bắt buộc)"
- Đề xuất: "(form hiện ở mỗi lượt cho tới khi đủ, trừ lượt người dùng nói không muốn đi hoặc lên lịch nữa; ngân sách không bắt
  buộc)"

**Đánh đổi**

- Giữ nguyên chuyến đang lên (cả việc đã đồng ý lập lịch), chỉ bỏ lời mời lập lịch đang chờ. Nhắn "thôi đi tiếp" là nối lại
  được; đủ thông tin thì lập lịch ngay.
- Không thêm luật nhận câu: nhãn do LLM phân luồng chọn, nên kết quả phụ thuộc prompt và cần đo nhiều lần.

**Liên quan tới đề xuất đang chờ**

- `docs/prd/update/2026-10-09-goi-y-truoc-khi-lap-lich.md` (đã chốt, PRD chưa cập nhật) sửa cùng AC-AGT-01 và dòng
  `ClassifyTurn --> Converse` hiện có. Cạnh mới ở đây là một dòng riêng; khi áp đề xuất đó vào PRD cần giữ câu và cạnh này.
  Trước khi đồng ý lập lịch, "để sau", "chưa" trả lời lời mời lập lịch vẫn theo AC-AGT-06 của đề xuất đó.

## Thay đổi source sau khi chốt

- `src/backend/app/agents/models.py`: thêm nhãn `stop` cho `TurnRoute`.
- `src/backend/app/agents/steps/classification.py`: `route_result` đưa `stop` sang `converse`, không trường thiếu, không form,
  không nút, bỏ lời mời đang chờ, giữ chuyến.
- `src/backend/app/agents/steps/prompts.py`: định nghĩa `stop` trong `CLASSIFY_PROMPT`, bỏ "không đi nữa" khỏi `travel`; lời chào
  trong `CONVERSATION_PROMPT`.
- `src/backend/app/agents/steps/conversation.py`, `turn_notes.py`, `messages.py`: không tiêu đề, câu cố định khi LLM lỗi, ghi chú
  lượt cho lượt sau.
- `src/backend/app/agents/nodes.py`, `src/backend/scripts/push_prompts_to_langsmith.py`: docstring, mô tả.
- Test: `src/backend/tests/unit/agents/test_classify.py`, `test_reply_titles.py`, `test_turn_context.py`,
  `test_itinerary_runtime.py`; case TC-15 trong `src/evaluation/datasets/agent_test_cases_nhat.yaml` và
  `src/evaluation/agent/agent-test-cases-nhat.md`, `src/evaluation/tests/test_golden.py`.
- Spec: `docs/spec/agent/nghiep-vu/hieu-y-dinh-va-hoi-lai.md`, `docs/spec/agent/langgraph-nodes.md`,
  `docs/spec/agent/state-fields.md`, `docs/spec/agent/nghiep-vu/vong-doi-mot-luot.md`, `docs/spec/agent/response-and-errors.md`,
  `docs/spec/agent/nghiep-vu/dien-giai-va-kiem-tra.md`, `docs/spec/agent/working-context.md`,
  `docs/spec/hop-dong-tich-hop-itinerary-assistant.md`.
- Contract và frontend không đổi: câu trả lời là `NEEDS_CLARIFICATION` chỉ có `question`, như câu chào hỏi, cảm ơn hiện nay.
