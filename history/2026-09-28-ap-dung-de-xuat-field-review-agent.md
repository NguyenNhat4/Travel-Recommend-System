# Áp dụng đề xuất field-review.md: giữ/bỏ/gộp field của Itinerary Agent

- Ngày: 2026-09-28
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: agent, backend, frontend, docs

## Mục tiêu

`docs/spec/agent/field-review.md` (tạo ở `history/2026-09-24-review-field-agent.md`, còn dang dở) liệt kê
đề xuất giữ/bỏ/gộp cho field request/response và `AgentState` nhưng chưa có quyết định. Người dùng yêu
cầu áp dụng toàn bộ đề xuất trong tài liệu, đã chốt phạm vi và các điểm còn hai phương án qua
`AskUserQuestion` trước khi sửa code: (1) áp dụng cả Response lẫn AgentState, (2) `description` bỏ hẳn
(không cắt còn 200 ký tự), (3) `attributes` chỉ giữ 4 khoá FE đang đọc, (4) backend bắt đầu trả
`suggestedValues`/`suggestions` thay vì để FE bỏ đọc.

`AgentState` là state nội bộ (`docs/prd/architecture.md` §3 không liệt kê field state) nên bỏ/gộp field
state không lệch PRD, không cần đề xuất trong `docs/prd/update/` (đúng mục 0 của field-review.md). Không
có FR/NFR mới; phục vụ FR-AGT-01..05 và NFR-PERF-02 đã ghi ở đầu field-review.md.

## File thay đổi

- `docs/spec/agent/field-review.md` — sửa: điền cột "Quyết định" cho mọi dòng, sửa hai chỗ bằng chứng sai
  phát hiện khi áp dụng (`final_answer` thực ra có bị đọc; khoá `attributes.beachfront` không tồn tại,
  đúng là `privateBeach`).
- `docs/spec/agent/state-fields.md` — sửa: bỏ field đã xoá, gộp `route`/`evaluation_result` vào `decision`,
  cập nhật mô tả `details` (bị xoá sau khi `evaluate` dùng xong).
- `docs/spec/agent/langgraph-nodes.md` — sửa: bảng §6.1 và bảng tóm tắt §6 theo field mới.
- `docs/spec/agent/README.md` — sửa: mục lục `field-review.md` ghi đã chốt.
- `src/backend/app/agents/state.py` — sửa: bỏ `thread_id`, `scenario_id`, `messages`, `errors`,
  `pending_question`, `llm_used`; bỏ `Scenario`, `Route` (StrEnum), `initial_state()`; gộp `route` +
  `evaluation_result` vào `decision` (giữ `decision` sẵn có, xoá hai field kia khỏi `AgentState`).
- `src/backend/app/agents/routing.py` — sửa: bốn hàm route đọc `decision` thay vì `route`/`evaluation_result`;
  `route_after_evaluate` thêm nhánh `"error"→dead_letter` cho khớp giá trị `decision` do `messages.failure()` ghi.
- `src/backend/app/agents/nodes.py` — sửa: `intake_node` bỏ khởi tạo field đã xoá; `_travel_without_message`,
  `_llm_failed`, `classify_node(_async)` dùng `decision` thay `route`; `evaluate_node` bỏ nhánh
  `evaluation_result`, đọc/ghi `decision`; `retry_or_fallback_node` bỏ ghi `errors`; sửa docstring các node
  theo field mới.
- `src/backend/app/agents/steps/classification.py` — sửa: `route_result`/`extract_result` trả `decision`
  thay `route`, bỏ ghi `llm_used`.
- `src/backend/app/agents/steps/evaluation.py` — sửa: `_decision()` trả một giá trị `decision` duy nhất
  thay vì cặp `(evaluation_result, decision)`; `evaluate_retrieval` trả thêm `"details": {}` để xoá
  ProductDetail đã tiêu thụ khỏi state/trace.
- `src/backend/app/agents/steps/conversation.py` — sửa: bỏ ghi `pending_question`/`llm_used`;
  `_question_response` thêm `suggestedValues.destination` (khi `supported_destinations` đã có) và
  `suggestedValues.days` (1–7, khi `days` đang thiếu).
- `src/backend/app/agents/steps/composition.py` — sửa: thêm `_no_results_suggestions()` dựng tối đa 3 gợi
  ý tất định từ `constraints` đang bật, gắn vào response `NO_RESULTS.suggestions`.
- `src/backend/app/agents/steps/messages.py` — sửa: thêm 6 khoá message `suggestion_*` (vi/en) cho gợi ý
  `NO_RESULTS`.
- `src/backend/app/domain/itinerary/planning.py` — sửa: `SUMMARY_FIELDS` bỏ `description`; `summary()` cắt
  `attributes` còn `oceanView`, `privateBeach`, `pool`, `ticketed` (`SUMMARY_ATTRIBUTE_KEYS`).
- `src/frontend/src/components/assistant/AiFloatingWidget.tsx` — sửa: `getHotelVisuals` bỏ nhánh dò
  `product.description`, đổi `attributes.beachfront` (không tồn tại trong contract) thành
  `attributes.privateBeach`.
- `src/frontend/src/types/travel.ts` — sửa: `ProductAttributes.beachfront` đổi tên thành `privateBeach`
  cho khớp `src/shared/contracts/schemas/catalog.yaml`.
- `src/backend/tests/unit/agents/test_lab_copy.py`,`test_routing.py`, `test_classify.py`,
  `test_itinerary_tools.py`, `test_itinerary_runtime.py` — sửa: theo field `decision` gộp và field đã bỏ;
  `test_catalog_hydration_is_concurrent_and_bounded` đổi sang đếm `clients.calls` thay vì đọc
  `result['details']` (giờ bị xoá sau `evaluate`).
- `src/backend/tests/unit/agents/test_suggestions.py` — thêm: test `_no_results_suggestions` và
  `_question_response.suggestedValues` (destination có/không có catalog, days, không có gì ngoài
  destination/days thiếu).
- `src/backend/tests/unit/domain/test_itinerary_composition.py` — sửa: thêm `SummaryTests` cho
  `planning.summary()` (bỏ `description`, cắt `attributes`, field rỗng thì bỏ khoá, input không phải dict).

## Quyết định

- Phạm vi: áp dụng toàn bộ đề xuất (Response + AgentState), theo lựa chọn của người dùng qua
  `AskUserQuestion`.
- `description` trong `ProductSummary` của lịch trình: bỏ hẳn, không cắt còn ~200 ký tự.
- `attributes`: chỉ giữ 4 khoá FE thật sự đọc; **không** dùng tên `beachfront` như đề xuất gốc vì khoá đó
  không tồn tại trong `ProductAttributes` (`src/shared/contracts/schemas/catalog.yaml` chỉ có
  `privateBeach`) — đây là bug có sẵn ở frontend (điều kiện luôn `undefined`, tag "View biển" chỉ hiện khi
  có `oceanView`), tiện sửa luôn vì đang cắt đúng field này.
- `suggestedValues`/`suggestions`: backend bắt đầu trả. `suggestedValues.destination` chỉ có khi
  `state.supported_destinations` đã nạp (sau lượt đầu từng gọi `tool`) vì `converse`/`clarify` chưa được
  nối với port `tools` để tự gọi `list_destinations()` — lượt hỏi thiếu điểm đến *đầu tiên* của một hội
  thoại mới vẫn chưa có mảng gợi ý điểm đến (ghi lại làm hạn chế đã biết trong field-review.md, không mở
  rộng graph để giữ rủi ro thấp). `suggestedValues.days` (1–7) và `suggestions` của `NO_RESULTS` luôn tính
  được tất định, không phụ thuộc gọi tool.
- Gộp `route`/`decision`/`evaluation_result` thành một field `decision`: xác minh bằng cách đọc hết
  `steps/classification.py`, `steps/evaluation.py`, `routing.py` — mỗi điểm rẽ nhánh chỉ đọc giá trị do
  đúng node liền trước vừa ghi (không có node nào đọc lại giá trị cũ từ một chặng trước), nên gộp không
  mất thông tin định tuyến. Domain giá trị theo từng chặng ghi trong `state-fields.md`/`field-review.md`.
- Xoá `details` khỏi state ngay sau khi `evaluate` dùng xong (không giữ lại "chỉ id" như phương án 2, vì
  không có node nào cần id riêng của `details` — `candidates` đã đủ).
- Hai bằng chứng sai trong `field-review.md` gốc, phát hiện khi verify trước khi sửa (theo nguyên tắc
  "lấy bằng chứng trước khi sửa"): `final_answer` thực ra bị `finalize_node_async` đọc (qua biến cục bộ
  `update`, không phải `state.get()`, nên grep gốc bỏ sót) để ghi archive hội thoại — **giữ nguyên field
  này**, không bỏ như đề xuất; `errors` (state field) thực ra vẫn đang được `retry_or_fallback_node` ghi
  lúc review (không phải "code không còn" như ghi chú cũ) nhưng đúng là không ai đọc lại — vẫn bỏ.
- `AgentState` là state nội bộ nên không cần đề xuất `docs/prd/update/`; không có mục nào trong lần sửa
  này lệch PRD.

## Kiểm tra

- `.venv/bin/python -m pytest -q src/backend/tests/unit src/backend/tests/contract src/backend/tests/architecture`:
  530 passed trước khi thêm `test_suggestions.py`/`SummaryTests`; 540 passed sau khi thêm (10 test mới).
- `.venv/bin/python -m pytest -q src/backend/tests/integration`: 19 skipped (cần Postgres/Redis thật,
  không chạy trong phiên này).
- `PYTHONDONTWRITEBYTECODE=1 python3 src/shared/contracts/tests/validate_contract.py`: PASS (không đổi
  contract, chỉ đổi dữ liệu backend thật sự trả).
- `node_modules/.bin/tsc --noEmit -p tsconfig.json` (trong `src/frontend`): không lỗi.
- Không chạy bộ golden dataset (`src/evaluation/agent/golden.py`): cần Postgres đã seed và backend chạy
  thật; thay đổi ở lớp domain/steps đã có unit test đủ phủ (bao gồm `test_itinerary_runtime.py` chạy
  graph đầy đủ bằng fake tool/LLM).

## Còn lại / rủi ro

- `suggestedValues.destination` chưa có ở lượt hỏi điểm đến đầu tiên của một hội thoại mới (xem mục
  "Quyết định"); muốn đầy đủ hơn cần nối `tools`/`list_destinations()` vào `converse`/`clarify`, coi là
  việc riêng nếu người dùng cần.
- `warnings[].productId` của `PRODUCT_DROPPED_*` trùng nhau chưa được gộp (mục "cân nhắc" tuỳ chọn trong
  field-review.md §2.3, không bắt buộc).
- `tool_results` chưa bỏ `data` sau `evaluate` để trace nhẹ hơn (mục "cân nhắc" tuỳ chọn trong
  field-review.md §3.2, không bắt buộc).
- Chưa chạy golden dataset thật để đo lại grounding rate sau khi cắt `ProductSummary` — theo phân tích
  tĩnh (`steps/validation.py`, `src/evaluation/agent/grounding.py` không đọc `attributes`/`description`)
  thì không ảnh hưởng, nhưng chưa có số đo thật.
