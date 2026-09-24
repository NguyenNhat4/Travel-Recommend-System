# Tách `agents/nodes.py`: file chỉ còn hàm node, luật chi tiết vào `agents/steps/`

- Ngày: 2026-09-23
- Tác giả: người dùng / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: agent, docs

## Mục tiêu

Người dùng báo `src/backend/app/agents/nodes.py` (709 dòng) quá dày đặc, khó đọc; yêu cầu:
thêm doc cho từng node, file chỉ chứa các hàm node ("bao nhiêu node bấy nhiêu hàm"), và gom các
module helper mới vào một thư mục. Refactor thuần, không đổi hành vi.

## File thay đổi

- `src/backend/app/agents/nodes.py` — sửa: còn 321 dòng, chỉ gồm 15 hàm node (10 node; `intake`,
  `classify`, `clarify`, `converse`, `finalize` có thêm bản `_async` vì LangGraph cần cả sync lẫn
  async). Mỗi node có docstring ghi "đọc field nào / ghi field nào / đi tiếp node nào"; docstring
  module có sơ đồ luồng và trỏ tới `docs/spec/agent/langgraph-nodes.md` §6.
- `src/backend/app/agents/steps/__init__.py` — thêm: mục lục một dòng cho từng module.
- `src/backend/app/agents/steps/prompts.py` — thêm: `EXTRACT_PROMPT`, `CONVERSATION_PROMPT`, và hai
  prompt trước đây viết inline trong `tool_node` (`TOOL_PLAN_PROMPT`, `DESTINATION_PROMPT`).
- `src/backend/app/agents/steps/messages.py` — thêm: bảng `MESSAGES` song ngữ, các câu cố định
  trước đây rải rác trong thân hàm, và `message`/`event`/`failure`/`chat_model` (trước là `_message`,
  `_event`, `_failure`, `_chat_model`).
- `src/backend/app/agents/steps/classification.py` — thêm: `extraction_input`, `classify_result`,
  tách thân `_classify_result` thành `_merged_intent`, `_merged_constraints`, `_days_from_end_date`.
- `src/backend/app/agents/steps/tool_planning.py` — thêm: `catalog_destinations`,
  `canonical_destination`, `validated_plan`, `build_plan`, `run_calls` (tách từ thân `tool_node`).
- `src/backend/app/agents/steps/evaluation.py` — thêm: `tool_errors`, `_relaxed_constraints`,
  `_decision`, `evaluate_retrieval`.
- `src/backend/app/agents/steps/conversation.py` — thêm: helper của `clarify` và `converse`.
- `src/backend/app/agents/steps/composition.py` — thêm: `grouped`, `fallback`, `retrieval_outcome`,
  `composed`, `compose_or_fallback`; các message cảnh báo gom vào hằng `WARNINGS`.
- `src/backend/app/agents/steps/failures.py` — thêm: `terminal_failure` (thân `dead_letter_node`).
- `src/backend/app/agents/steps/validation.py` — thêm: `response_issues`, `answer_text`,
  `selection_snapshot`.
- `src/backend/tests/unit/agents/test_classify.py`, `test_contract_derived_models.py`,
  `test_lab_copy.py` — sửa: import `classify_result`/`message` từ `agents.steps.*` thay vì tên
  private trong `nodes`.
- `src/backend/app/application/ports/llm.py` — sửa: docstring nêu thêm `agents/steps/tool_planning.py`
  là nơi gọi `with_structured_output`/`bind_tools`.
- `docs/spec/agent/working-context.md`, `state-fields.md`, `langgraph-nodes.md` — sửa: bảng "source
  bắt đầu từ" và các câu nguồn hành vi trỏ sang `agents/steps/*`.
- `docs/prd/update/2026-09-23-agents-steps-folder.md` — thêm: đề xuất (chờ chốt) bổ sung `steps/`
  vào dòng mô tả `agents/` trong cây thư mục `docs/prd/architecture.md` §2.

## Quyết định

- Giữ nguyên 15 hàm thay vì gộp sync/async: `graph.py` nối từng node bằng
  `RunnableLambda(func, afunc=...)`, gộp lại sẽ đổi cách graph được dựng, tức đổi hành vi.
- Đặt tên module theo trách nhiệm, không tạo `utils` chung — `docs/prd/architecture.md` §6.3 quy tắc 5.
- Bỏ tiền tố `_` cho các hàm đã thành API của module mới; test đang import `nodes._classify_result`
  và `nodes._message` được sửa import thay vì giữ alias, để `nodes.py` đúng yêu cầu "chỉ có hàm node".
- Hai chỗ suýt đổi hành vi khi tách, đã giữ đúng bản gốc:
  1. `classify`: `days` suy từ `end_date` phải luôn chạy, không được để `or` ngắn mạch khi
     `result.conflict` đã là True.
  2. `evaluate`: ba kiểm tra sau `decision = "compose"` chạy tuần tự, nên "không còn sản phẩm xếp
     được lịch" ghi đè `constraint_clarification` thành `fallback` — không đổi thành early return.
- Không tự sửa `docs/prd/architecture.md`: theo `AGENTS.md` §8, phần lệch PRD (thư mục `steps/`
  chưa có trong cây thư mục PRD) phải qua đề xuất và người dùng chốt trước.

## Kiểm tra

- `python3 -m pytest src/backend/tests/unit -q` → 160 passed (bằng đúng số test trước refactor).
- `python3 -m pytest src/backend/tests/architecture -q` → 8 passed.
- `python3 -m pytest src/backend/tests/architecture src/backend/tests/contract -q` → 19 passed (6 phút).
- `uvx ruff check --select F src/backend/app/agents` → All checks passed (không còn import thừa).
- Chưa chạy `validate_contract.py` vì không đổi contract/mock.

## Còn lại / rủi ro

- Đề xuất `docs/prd/update/2026-09-23-agents-steps-folder.md` đang **chờ người dùng chốt**; chốt
  xong mới cập nhật `docs/prd/architecture.md` §2 rồi chuyển đề xuất sang `update-archive/`.
- `src/backend/app/core/config.py` và `src/backend/tests/unit/agents/test_itinerary_runtime.py` có
  thay đổi uncommitted từ các task trước, không thuộc entry này.
