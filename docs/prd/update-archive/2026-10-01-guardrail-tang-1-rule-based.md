# Guardrail tầng 1: lọc tin nhắn rác và rate limit cho trợ lý

- Ngày: 2026-10-01
- Người đề xuất: nhatnm / Claude
- Trạng thái: đã áp dụng
- Chốt bởi / ngày: nhatnm, 2026-10-01
- PRD bị ảnh hưởng: `docs/prd/requirements.md` §2.3 (NFR-SEC), §1.4 (FR-AGT-01); `docs/prd/architecture.md` §3 (node `classify`)
- Mã FR/NFR: mới — cần cấp mã (đề xuất `NFR-SEC-04`)

## Lý do

Tin nhắn rác ("aaaaaa", "?????", "asdfjkl", toàn emoji, chửi thề) hiện vẫn đi tới LLM ở `classify` rồi `converse`: tốn hai
lượt gọi LLM cho một câu không có nội dung, và không có giới hạn số tin một người gửi liên tục. PRD chưa có yêu cầu nào về việc
này. Một lớp luật tất định chạy trước LLM chặn được phần lớn rác với chi phí gần như 0.

## Nội dung đề xuất

`docs/prd/requirements.md` §2.3 — thêm sau NFR-SEC-03:

> - **NFR-SEC-04 (Lọc đầu vào trợ lý và giới hạn tần suất):** Trước khi gọi LLM, trợ lý lọc tin nhắn rác bằng luật tất định
>   (rỗng/chỉ ký hiệu, ký tự lặp, tỉ lệ chữ cái thấp, gõ bậy theo tỉ lệ âm tiết tiếng Việt/từ tiếng Anh hợp lệ, tục tĩu theo
>   blacklist). Rác thì trả câu cố định "chưa hiểu" (`NEEDS_CLARIFICATION`, 200); tục tĩu không kèm yêu cầu hợp lệ thì từ chối
>   (400 `VALIDATION_ERROR`). Không gọi LLM ở cả hai trường hợp. Câu trả lời ngắn hợp lệ (số ngày, ngày, số người, ngân sách,
>   "ok") không bị chặn. Mỗi người dùng/khách bị giới hạn số tin gửi trợ lý trong một cửa sổ thời gian; vượt ngưỡng trả 429
>   `TOO_MANY_ATTEMPTS` kèm `Retry-After`.

`docs/prd/architecture.md` §3 — mô tả node `classify`: thêm "chạy guardrail tầng 1 (luật tất định) sau guardrail chèn lệnh,
trước LLM".

## Thay đổi source sau khi chốt

Chi tiết từng luật, ngoại lệ và các bước: `docs/spec/agent/langgraph-nodes.md` mục "Guardrail tầng 1".

- Contract: `src/shared/contracts/paths/itinerary-agent.yaml` thêm `'429'` cho hai route `/assistant/itineraries*`.
- Agent: `src/backend/app/agents/steps/guardrails.py`, `steps/messages.py`, `steps/conversation.py`, `nodes.py`, `state.py`.
- Rate limit: `src/backend/app/domain/auth/rate_limits.py` (hoặc bảng luật dùng chung), `api/v1/routes/assistant.py`, `main.py`.
- Test: `src/backend/tests/unit/agents/test_guardrails.py`, test contract/route cho 429.
- Spec: `docs/spec/hop-dong-tich-hop-itinerary-assistant.md` §4.3, `docs/spec/agent/state-fields.md`.
