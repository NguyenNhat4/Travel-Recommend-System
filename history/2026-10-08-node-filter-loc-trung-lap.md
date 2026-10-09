# Node `filter`: bỏ điểm tham quan trùng (luật cùng tên + LLM chỉ ra cặp) trước `compose`

- Ngày: 2026-10-08
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: agent, evaluation, docs

## Mục tiêu

Lịch Phú Quốc 3 ngày (trace LangSmith `01a11adf-0747-72c0-9dd6-b302e00a4c20`, project `nhat-10-7`) có 5/6 buổi trùng nơi:
"hòn Thơm", "Sun World Hòn Thơm", "Cáp Treo Hòn Thơm" và hai vé "[Grand World Phú Quốc] - Vé đi thuyền Venice (Water Taxi)"
khác mã. Người dùng chốt đề xuất `docs/prd/update-archive/2026-10-08-loc-trung-lap-bang-llm.md` (đổi tên node thành
`filter`): sau bước tất định, đưa danh sách mã + tên cho LLM chỉ ra cặp trùng, giữ một trong hai; eval có mục "Đã loại".
Thay thế trạng thái `dang dở` của `history/2026-10-08-lich-trinh-trung-dia-diem-phu-quoc.md`.

## File thay đổi

- `docs/prd/update-archive/2026-10-08-loc-trung-lap-bang-llm.md` — thêm (chuyển từ `docs/prd/update/`): trạng thái
  `đã áp dụng`, chốt bởi Nguyễn Minh Nhật 2026-10-08, `dedupe` → `filter`.
- `docs/prd/architecture.md` — sửa: §3 sơ đồ thêm `FilterCandidates`; Grounding nêu việc LLM chỉ ra cặp trùng.
- `docs/prd/requirements.md` — sửa: AC-AGT-04 thêm luật "không có hai điểm tham quan cùng một nơi" và ghi chú chốt.
- `src/backend/app/domain/itinerary/dedupe.py` — thêm: `filterable`, `same_name_pairs`, `apply_pairs` (duyệt theo `keep_rank`, không bắc cầu, bỏ mã lạ).
- `src/backend/app/domain/itinerary/planning.py` — sửa: `keep_rank` (Search trước Recommendation, rẻ hơn, mã nhỏ hơn).
- `src/backend/app/agents/steps/filtering.py` — thêm: bước luật, payload LLM (mã + tên + điểm đến), cảnh báo.
- `src/backend/app/agents/models.py` — sửa: `DuplicatePair` (`ids`, `reason`, `duplicate`), `DuplicatePairs`.
- `src/backend/app/agents/steps/prompts.py` — sửa: `FILTER_PROMPT`.
- `src/backend/app/agents/steps/messages.py` — sửa: câu `dropped_duplicate` (vi/en).
- `src/backend/app/agents/nodes.py` — sửa: `filter_node`, `filter_node_async`.
- `src/backend/app/agents/graph.py` — sửa: node `filter` (timeout `ITINERARY_LLM_TIMEOUT_SECONDS`, 2 s khi không truyền),
  cạnh `filter → compose`, mười bốn node.
- `src/backend/app/agents/routing.py` — sửa: `route_after_evaluate`/`route_after_retry` trả `filter` thay `compose`.
- `src/backend/app/agents/state.py` — sửa: `dropped_duplicates`.
- `src/backend/tests/unit/domain/test_itinerary_dedupe.py` — thêm.
- `src/backend/tests/unit/agents/test_filter_node.py` — thêm.
- `src/backend/tests/unit/agents/test_routing.py`, `test_itinerary_tools.py`, `test_lab_copy.py`,
  `test_itinerary_runtime.py` — sửa: `compose` → `filter` ở routing, topology mười bốn node, đường đi node, LLM giả trả
  `DuplicatePairs` rỗng.
- `src/evaluation/agent/golden.py` — sửa: `TurnResult.dropped`, báo cáo JSON/markdown có mục "## Đã loại", event
  `turn_done` mang `dropped`; `schedule_findings` báo tên lặp lại (khác mã) trong lịch.
- `src/evaluation/agent/eval_app.py` — sửa: khung "Đã loại" ở mỗi lượt.
- `src/evaluation/agent/streamlit_app.py` — sửa: expander "Đã loại vì trùng".
- `src/evaluation/agent/case_builder.py` — sửa: `PRODUCT_DROPPED_DUPLICATE` trong `WARNING_CODES`.
- `src/evaluation/datasets/agent_test_cases_nhat.yaml`, `src/evaluation/agent/agent-test-cases-nhat.md` — sửa: TC-11.
- `src/evaluation/reports/eval-2026-10-08-node-filter-tc11.md` — thêm: biên bản golden TC-11 với LLM thật.
- `src/evaluation/tests/test_golden.py`, `src/evaluation/tests/test_eval_app.py` — sửa: test tên lặp, mục "Đã loại",
  danh sách case có TC-11.
- `docs/spec/agent/langgraph-nodes.md`, `state-fields.md`, `working-context.md`, `README.md`, `response-and-errors.md`,
  `nghiep-vu/xep-lich.md`, `nghiep-vu/vong-doi-mot-luot.md`, `docs/spec/hop-dong-tich-hop-itinerary-assistant.md` — sửa:
  node `filter`, field `dropped_duplicates`, cảnh báo `PRODUCT_DROPPED_DUPLICATE`, sơ đồ luồng.

## Quyết định

- LLM chỉ thấy mã + tên điểm tham quan và tên điểm đến (không giá, không ngữ cảnh hội thoại); cặp có mã lạ, mã không phải
  điểm tham quan hay hai mã giống nhau bị bỏ qua, nên grounding giữ 100%. Giữ mã nào do `keep_rank`.
- Luật cùng tên chạy trước để LLM không phải xử lý ca hiển nhiên; LLM lỗi/quá giờ thì chỉ dùng luật. Lượt không đi tới
  lịch (`decision` khác `compose`) hoặc còn dưới hai điểm tham quan thì không gọi LLM.
- Routing trả `filter` thay vì giữ khoá `compose` và đổi đích ở graph, để tên cạnh khớp node thật.
- Contract không đổi: `ItineraryWarning.code` là chuỗi tự do.
- Mục "Đã loại" của eval đọc `state["dropped_duplicates"]` (có `by` = rule/llm và mã được giữ), không phải finding.
- TC-11 hai lượt: câu gốc ở hội thoại mới bị hỏi ngân sách (luật hỏi chi tiết của `extract`); hội thoại gốc đã trả lời ở
  lượt trước.

## Kiểm tra

- `.venv/bin/python -m pytest -q src/backend/tests`: 1912 passed, 35 skipped (lần chạy trước khi sửa test cũ: 1 fail đúng
  dự kiến ở `test_itinerary_runtime` vì đường đi node có thêm `filter`).
- `.venv/bin/python -m pytest -q src/evaluation/tests`: 101 passed, 13 failed — đều ở `test_temporal.py`,
  `test_recommender_prototypes.py`, `test_cdp_all_events.py`, `test_postgres_cdp_reader.py` (`LocalCdpClient` không có
  `all_events`, `UnitIndex` nhận khoá lạ); không file nào chạm code của thay đổi này, có từ trước. `test_golden.py`,
  `test_case_builder.py`, `test_eval_app.py`, `test_eval_runs.py`: 98 passed.
- `validate_contract.py`: PASS (contract không đổi).
- LLM thật (`gpt-6-luna`, backend local + Postgres, dataMode `http`): golden TC-11 `--repeat 3` — lỗi gốc hết cả 3 lần (Hòn
  Thơm còn một, Water Taxi còn một), giám khảo "không hai điểm cùng nơi" đạt 3/3; 3 FAIL còn lại đều do kiểm tra cũ "stay =
  hotel rẻ nhất" của eval (có từ 23/09, lệch luật quãng đường 07/10), không do `filter`. Biên bản:
  `src/evaluation/reports/eval-2026-10-08-node-filter-tc11.md`.
- Lần đo LLM thật đầu (bắc cầu, chưa có `duplicate`) gộp nhầm Bảo tàng Gấu với Water Taxi (qua combo) và bỏ Vinpearl Safari
  (LLM trả cặp với lý do "hai địa điểm khác nhau"); đã sửa bằng bỏ bắc cầu + trường `duplicate`, có test cho cả hai.
- Latency: LLM của `filter` 2,4–3,4 s mỗi lượt (LangSmith).

## Còn lại / rủi ro

- Mỗi lượt lập lịch thêm một lời gọi LLM (2,4–3,4 s); lịch có thể khác giữa các lần nếu LLM nhận cặp khác nhau.
- LLM bỏ sót một cặp thì có thể còn trùng (không bắc cầu nên thiếu cặp không được bù); chọn hướng này vì gộp nhầm làm mất
  hoạt động thật.
- Kiểm tra "stay = hotel rẻ nhất" của `golden.schedule_findings` đã lỗi thời so với AC-AGT-04; chưa sửa (ngoài phạm vi).
- Giữ mã rẻ hơn có thể giữ điểm tự do ("hòn Thơm") thay cho vé cáp treo — đúng luật đã chốt, cần người dùng xem lại nếu
  muốn ưu tiên khác.
- Server demo local (`uvicorn` không `--reload`) đang chạy code cũ; cần khởi động lại để thấy node `filter` trên web.
