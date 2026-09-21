# Đưa việc hỏi thông tin thiếu từ `answer` về node `clarify`

- Ngày: 2026-09-21
- Tác giả: nhatutc2@gmail.com / Claude
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: backend, agent, docs
- Bị thay thế bởi: 2026-09-21-tach-converse-compose.md (phần việc còn lại: tách nốt `answer`)
- Thay thế: một phần `2026-09-19-route-conversation-through-llm-answer.md` (phần route `missing_info` qua `answer`)

## Mục tiêu

`answer` gánh quá nhiều việc (chào hỏi, từ chối, hỏi thông tin thiếu, hỏi lại điều kiện, NO_RESULTS, FALLBACK, dựng lịch trình), còn `clarify` là code chết vì `route_after_classify` ánh xạ `missing_info` → `answer`. Người dùng chốt thiết kế: `clarify` hỏi lại thông tin thiếu, `answer` (route `simple`) trả lời chào hỏi và ngoài phạm vi. Câu hỏi vẫn do LLM viết như trước.

## File thay đổi

- `src/backend/app/agents/routing.py` — sửa: `missing_info` → `clarify`; `route_after_evaluate` trả `clarify` khi `decision == constraint_clarification`.
- `src/backend/app/agents/graph.py` — sửa: `clarify` đăng ký như `answer` (sync + async, tiêm `llm` và timeout); mapping của `evaluate` thêm `clarify`.
- `src/backend/app/agents/nodes.py` — sửa: `ask_clarification_node` nhận `llm`, gọi LLM viết câu hỏi, lỗi/timeout thì dùng `_clarification_fallback` (câu cố định theo `clarification_reason`); thêm `ask_clarification_node_async`; `constraint_clarification` chuyển từ `_non_compose` sang `clarify` (câu cố định, không gọi LLM); `_needs_conversational_answer` chỉ còn chào hỏi và từ chối; `_conversational_fallback` gọi lại `_clarification_fallback`; `CONVERSATION_PROMPT` thêm hướng dẫn cho `conflict`/`unverified`.
- `src/backend/tests/unit/agents/test_routing.py` — sửa: kỳ vọng route mới.
- `src/backend/tests/unit/agents/test_lab_copy.py` — sửa: bọc `clarify` bằng LLM giả lỗi để test không gọi model thật.
- `src/backend/tests/unit/agents/test_itinerary_runtime.py` — sửa: `ScriptedLlm` thêm `fail_conversation`; thêm 3 test (đường đi node, fallback theo lý do, constraint không gọi LLM).
- `docs/agent/langgraph-nodes.md` — sửa: bảng node, sơ đồ luồng và các điểm cần nhớ theo routing mới.
- `docs/agent/README.md` — sửa: timeout LLM áp dụng cả cho `clarify`.
- `history/2026-09-19-route-conversation-through-llm-answer.md` — sửa: chỉ thêm dòng `Bị thay thế bởi`.

## Quyết định

- Giữ LLM ở `clarify` (phương án A đã được người dùng đồng ý) để câu hỏi vẫn tự nhiên; mục tiêu của entry 2026-09-19 vẫn giữ, chỉ đổi node chịu trách nhiệm.
- Chào hỏi (`domain=conversation`) vẫn đi `answer` và vẫn trả `NEEDS_CLARIFICATION` kèm `missingFields`, đúng kỳ vọng của test hiện có.
- `constraint_clarification` dùng câu cố định vì lúc đó tool đã chạy và prompt hội thoại cấm nói về kết quả tìm kiếm.
- Sửa kèm một lỗi nhỏ: fallback cũ trong `answer` bỏ qua `clarification_reason`, nên mâu thuẫn ngày bị hỏi thành "mấy ngày"; nay fallback theo đúng lý do.
- Không đổi OpenAPI, tên node hay hình dạng response.

## Kiểm tra

- `python -m pytest -q src/backend/tests/unit/agents src/backend/tests/contract/test_assistant_contract.py`: pass.
- `python -m pytest -q src/backend/tests`: 143 passed, 2 skipped.
- `validate_contract.py`: không chạy vì không đổi contract hay mock.
- Chưa smoke test bằng LLM thật qua `make chat`.

## Còn lại / rủi ro

- Chất lượng câu hỏi của `clarify` phụ thuộc model; cần smoke test với key thật.
- `answer` vẫn còn dựng NO_RESULTS/FALLBACK/COMPLETED cùng chỗ với nhánh LLM chào hỏi; tách `converse` và `compose` là bước riêng nếu muốn.
- Bản sync và async của `answer`/`clarify` vẫn lặp code.
