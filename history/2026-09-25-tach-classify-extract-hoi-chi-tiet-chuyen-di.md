# Tách `classify` / `extract`, ngữ cảnh chung cho mọi lượt gọi LLM, hỏi gộp ngày đi – số người – ngân sách

- Ngày: 2026-09-25
- Tác giả: nhatutc2 / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: agent, contract, frontend, evaluation, docs

## Mục tiêu

Người dùng yêu cầu:
1. `classify` chỉ phân luồng bằng prompt rất ngắn: ngoài phạm vi / trò chuyện → `converse`; du lịch → trích intent → `clarify` nếu thiếu; lỗi → `dead_letter`.
2. Mọi node gọi LLM có ngữ cảnh cả hội thoại.
3. `clarify` hỏi thêm số người và ngân sách (chọn: hỏi một lần; gộp một câu với ngày đi).

Đề xuất: `docs/prd/update-archive/2026-09-25-tach-classify-extract-va-hoi-chi-tiet-chuyen-di.md` (đã áp dụng). Phục vụ FR-AGT-01, FR-AGT-02, NFR-SEC-01, AC-AGT-01.

## File thay đổi

- `docs/prd/architecture.md` — sửa §3: sơ đồ thêm `ClassifyTurn` và nhánh `Converse`; `AnalyzeIntent` trích thêm số người; điều kiện hỏi lại; dòng "Ngữ cảnh cho LLM".
- `docs/prd/requirements.md` — sửa AC-AGT-01: hỏi gộp một lần ngày đi, số người, ngân sách.
- `docs/prd/update-archive/2026-09-25-tach-classify-extract-va-hoi-chi-tiet-chuyen-di.md` — thêm.
- `src/backend/app/agents/models.py` — sửa: thêm `TurnRoute`; bỏ `Extraction.domain`.
- `src/backend/app/agents/steps/prompts.py` — sửa: thêm `CLASSIFY_PROMPT` (7 dòng); `EXTRACT_PROMPT` bỏ phần phân loại; câu hỏi gộp trong `CONVERSATION_PROMPT`; `DESTINATION_PROMPT` biết có ngữ cảnh.
- `src/backend/app/agents/steps/history.py` — sửa: thêm `llm_context` (lịch sử có giới hạn, `last_assistant_message`, `known_intent`, `known_constraints`, `previous_selection`).
- `src/backend/app/agents/steps/classification.py` — sửa: `route_input`/`route_result` cho `classify`; `classify_result` đổi tên `extract_result`, bỏ luật domain; `trip_details_missing` và hỏi gộp một lần.
- `src/backend/app/agents/nodes.py`, `graph.py`, `routing.py` — sửa: node `extract` (sync/async), `route_after_extract`; `classify` bỏ qua LLM khi chỉ có `intentOverride`; graph 11 node.
- `src/backend/app/agents/steps/tool_planning.py`, `conversation.py` — sửa: chọn điểm đến, lập tool plan, `clarify`/`converse` dùng `llm_context`; câu cố định cho câu hỏi gộp.
- `src/backend/app/agents/steps/messages.py` — sửa: câu hỏi gộp vi/en thay câu hỏi ngày đi.
- `src/shared/contracts/schemas/itinerary-agent.yaml` — sửa: `missingFields` thêm `party`, `budget`.
- `src/frontend/src/types/api.gen.ts` — sinh lại (kèm các thay đổi contract đang làm song song của phần lưu hội thoại).
- `src/frontend/src/components/assistant/assistantLabels.ts` — sửa: nhãn node `extract`.
- Test: `src/backend/tests/unit/agents/test_classify.py` (thêm `RouteTests`, viết lại test hỏi chi tiết), `test_itinerary_runtime.py` (LLM giả trả `TurnRoute`; mặc định `start_date_asked=True`; thay test luật cũ "conversation có chi tiết vẫn là travel" bằng test nhãn quyết luồng; test chip bỏ qua LLM; test hỏi gộp), `test_routing.py`, `test_lab_copy.py` (11 node), `test_itinerary_tools.py`, `tests/contract/test_assistant_contract.py`.
- `src/evaluation/datasets/itinerary_agent_golden.yaml` — sửa: G-051 nêu đủ số người và ngân sách, kiểm `party`, `budget`; comment đầu file.
- `docs/spec/hop-dong-tich-hop-itinerary-assistant.md`, `hop-dong-tich-hop-frontend.md`, `docs/spec/agent/langgraph-nodes.md`, `state-fields.md`, `field-review.md`, `README.md`, `golden-run.md`, `golden-dataset-how-to-add-more-case.md` — sửa theo graph và quy tắc mới.
- `docs/spec/agent/presentation-slides.html`, `presentation-script.md` — sửa: slide 1 (11 node), slide 3, slide 5 (vẽ lại dải "Hiểu người dùng" có `extract`), slide 7 (bốn đường mới), slide 9 (lỗi `extract`), lời nói tương ứng.

## Quyết định

- Giữ tên cờ `start_date_asked` (nay nghĩa là "đã hỏi chi tiết chuyến đi") vì phần lưu hội thoại Redis/Postgres đang làm song song đã dùng tên này trong store và test.
- Chỉ hỏi chi tiết trước lần lập lịch đầu tiên: lượt đi tới `tool` cũng đặt cờ, để đổi điểm đến sau đó không bị hỏi lại.
- Giữ giới hạn lịch sử 20 message / 8.000 ký tự (người dùng không chọn khác); thông tin cũ giữ qua `known_intent`/`known_constraints`.
- Bỏ luật "câu bị gọi conversation mà có chi tiết chuyến đi vẫn là travel"; `classify` dựa vào câu hỏi gần nhất để nhận câu trả lời ngắn.
- Đề xuất `update/2026-09-25-goi-y-ngay-hom-nay-khi-chua-chot-ngay-di.md` vẫn chờ chốt; nếu chốt phải viết lại theo câu hỏi gộp.

## Kiểm tra

- `pytest src/backend/tests/unit/agents src/backend/tests/contract src/backend/tests/architecture src/evaluation/tests/test_golden.py` (bỏ `test_conversation_archive.py`): 220 passed.
- `test_conversation_archive.py` (của phần lưu hội thoại làm song song): 3 test fail vì `.venv` thiếu `pytest-asyncio`, không do thay đổi này.
- `validate_contract.py`: PASS. `npx tsc --noEmit`: pass. `npx vitest run tests/unit`: 86 passed.
- Chụp slide 5 và 7 bằng Playwright: không chồng cạnh, không tràn.
- Chưa chạy golden thật (LLM + catalog) và E2E Playwright của Web.

## Còn lại / rủi ro

- Mỗi lượt du lịch thêm một lần gọi LLM (`classify`); cần đo lại độ trễ. Có thể dùng model nhẹ hơn cho `classify`.
- Chất lượng phân luồng của `CLASSIFY_PROMPT` chỉ đo được bằng golden thật (đặc biệt G-047, G-049 và các lượt trả lời ngắn "chưa chốt ngày đi").
- Điểm đến ngoài catalog vẫn bị hỏi chi tiết trước rồi mới báo 422.
