# Guardrail tất định cho itinerary agent: chặn chèn lệnh đầu vào, lộ secret/tuyên bố đặt chỗ đầu ra

- Ngày: 2026-09-28
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/itinerary-agent-guardrails
- Trạng thái: hoàn thành
- Phạm vi: agent

## Mục tiêu

Agent đã có lớp phân luồng bằng LLM (`classify`) gắn `out_of_scope` cho chèn lệnh/đòi secret/đặt chỗ, và
`finalize` kiểm schema + grounding. Còn hở hai chỗ: (1) câu chữ do LLM tự viết (`question`, `error.message`)
không được kiểm lúc chạy — lộ secret hay tuyên bố "đã đặt/đã thanh toán" chỉ được bắt bởi bộ chấm offline
(`src/evaluation/agent/golden.py`), không có gì chặn khi chạy thật; (2) nhận diện chèn lệnh chỉ dựa vào một
lần gọi LLM, LLM phân nhầm thì câu độc hại đi tiếp vào `extract`/tool plan. Thêm guardrail tất định (regex,
không gọi LLM, không thêm thư viện) ở đầu vào (`classify`) và đầu ra (`finalize`) để hai lỗ này có bảo đảm
lúc chạy, không chỉ đo được sau. Phục vụ NFR-SEC-01, NFR-REL-01, FR-AGT-04 (`docs/prd/requirements.md`).
Không lệch PRD (PRD đã yêu cầu đúng hành vi này) nên không cần đề xuất `docs/prd/update/`.

Đã research và loại các thư viện guardrail có sẵn (LangChain guardrail middleware, NeMo Guardrails,
Guardrails AI, LLM Guard, Llama Prompt Guard 2) trước khi quyết định tự viết — lý do trong PR/plan: agent
dùng `StateGraph` tự dựng (không phải `create_agent`), NeMo trùng vai trò LangGraph đang có, Guardrails AI
dư thừa vì contract đã validate structured output, LLM Guard ngừng cập nhật, Prompt Guard 2 không hỗ trợ
tiếng Việt. Người dùng chốt dùng code tất định.

## File thay đổi

- `src/backend/app/agents/steps/guardrails.py` — thêm: `input_violation()` (regex chèn lệnh/đòi secret) và
  `output_violations()` (regex secret + cụm tuyên bố đặt chỗ, chỉ quét `question`/`error.message`).
- `src/backend/app/agents/steps/__init__.py` — sửa: thêm dòng mô tả module `guardrails`.
- `src/backend/app/agents/state.py` — sửa: thêm field `blocked_by_guardrail: str | None` vào `AgentState`.
- `src/backend/app/agents/nodes.py` — sửa: `intake_node` khởi tạo `blocked_by_guardrail=None`; thêm helper
  `_guardrail_blocked_input()`; `classify_node`/`classify_node_async` gọi guardrail trước khi gọi LLM;
  `converse_node`/`converse_node_async` bỏ qua LLM khi `blocked_by_guardrail` đã đặt; `finalize_node` quét
  `guardrails.output_violations()` sau khi response qua được kiểm schema/grounding, thay câu chữ vi phạm
  bằng `conversation.conversational_fallback(state)`, giữ nguyên `status`/`http_status`, thêm mục
  `guardrail:*` vào `validation_issues`.
- `src/backend/tests/unit/agents/test_guardrails.py` — thêm: test cho `input_violation`/`output_violations`,
  test `classify_node`/`classify_node_async` không gọi LLM khi bị chặn (đếm lượt gọi bằng `CountingLlm`,
  không dùng exception vì hai node này nuốt mọi exception của LLM thành `LLM_UNAVAILABLE`),
  test `converse_node`/`converse_node_async` bỏ qua LLM khi `blocked_by_guardrail`, test `finalize_node`
  thay câu chữ vi phạm và giữ nguyên status/HTTP, test câu du lịch bình thường (kể cả có từ "bỏ qua khách
  sạn"/"hủy đặt phòng") không bị chặn nhầm.
- `docs/spec/agent/langgraph-nodes.md` — sửa: thêm đoạn giải thích guardrail tất định ở mục 1, thêm dòng
  vào bảng việc của `finalize` ở mục 2, cập nhật mô tả `classify`/`converse`/`finalize` ở bảng tra cứu mục 6
  và bảng field-level mục 6.1.
- `docs/spec/agent/state-fields.md` — sửa: thêm dòng `blocked_by_guardrail` vào bảng field.

## Quyết định

- Guardrail chỉ dùng regex tất định, không LLM, không model, không thêm thư viện (người dùng chốt sau khi
  xem bảng so sánh thư viện guardrail phổ biến — không cái nào khớp kiến trúc `StateGraph` tự dựng của repo
  hoặc hỗ trợ tiếng Việt).
- Mẫu chèn lệnh cố ý hẹp (`ignore/disregard/forget ... instructions`, `bỏ qua/quên hướng dẫn trước`,
  `system prompt`, `in ra/hiện/reveal ... api key/secret/token/mật khẩu`) để không chặn nhầm câu du lịch
  hợp lệ như "bỏ qua khách sạn" — có test âm tính đi kèm.
- Guardrail đầu ra chỉ quét hai field thực sự do LLM tự viết (`question` từ `clarify`/`converse`,
  `error.message` từ nhánh từ chối của `converse`) — không quét field `message` của `NO_RESULTS`/`FALLBACK`
  vì đó là câu cố định trong `messages.py`, quét vào sẽ không có tác dụng và có thể gây hiểu nhầm phạm vi.
- Khi `classify` chặn được câu chèn lệnh, `converse` không gọi LLM lần nào nữa (dùng thẳng
  `conversation.conversational_fallback`) — vừa đỡ tốn lượt gọi, vừa không đưa câu độc hại vào ngữ cảnh LLM
  thêm lần nào.
- `finalize` khi phát hiện vi phạm guardrail đầu ra không đổi `status`/`http_status`, chỉ thay câu chữ, khác
  với vi phạm schema/grounding (đổi hẳn thành `ITINERARY_VALIDATION_FAILED` 500) — vì đây là lỗi câu chữ,
  không phải lỗi dữ liệu sản phẩm hay hợp đồng.

## Kiểm tra

- `python -m pytest src/backend/tests/unit/agents/test_guardrails.py -q` — 14 passed.
- `python -m pytest src/backend/tests/unit src/backend/tests/architecture src/backend/tests/contract -q` —
  554 passed (bao gồm toàn bộ test agent cũ, không hồi quy).
- `PYTHONDONTWRITEBYTECODE=1 python3 src/shared/contracts/tests/validate_contract.py` — PASS (không đổi
  contract nên không có thay đổi số liệu).

## Còn lại / rủi ro

- Chưa chạy golden set (`src/evaluation/agent`, case G-049 và case 11 trong `evaluation-plan.md`) vì cần
  LLM thật/mock provider và `LANGSMITH_API_KEY`/API key model — để người dùng hoặc CI chạy riêng.
- Mẫu regex là danh sách cố định, không tự học; mở rộng mẫu chèn lệnh mới thì cần thêm cả test âm tính
  tương ứng để tránh chặn nhầm câu du lịch hợp lệ.
