# D0: ghi rõ trong code rằng luồng phân loại cũ đã đóng băng, không dùng

- Ngày: 2026-10-13
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: agent, backend

## Mục tiêu

Người dùng chốt ngày 13/10: "dùng orchestrator làm mặc định, code cũ nếu chưa xoá thì cần làm rõ không dùng". PRD đã ghi
câu này (`docs/prd/architecture.md` §3, `update-archive/2026-10-12-orchestrator-thanh-luong-chinh.md`). Bước D0 của
`docs/plan/2026-10-12-go-luong-cu-orchestrator-chinh.md`: đánh dấu mọi chỗ chỉ luồng cũ dùng, để nhóm không test hay tối
ưu nhầm trên luồng sắp gỡ. Chỉ comment và một log cảnh báo, không đổi hành vi. Phục vụ FR-AGT-06, FR-AGT-07, NFR-SEC-04.

## File thay đổi

- `src/backend/app/agents/nodes.py` — sửa: thêm đoạn đóng băng vào docstring của các hàm sau.
  - `classify_node`, `classify_node_async`: chỉ phần LLM đóng băng; các luật trước LLM vẫn dùng chung qua `precheck`.
  - `converse_node`, `converse_node_async`: chỉ phần LLM; hai nhánh câu cố định vẫn dùng chung.
  - `explore_node`, `explore_node_async`.
- `src/backend/app/agents/routing.py` — sửa: comment ở `route_after_classify`; docstring `route_after_extract` (hai đích
  cũ) và `route_after_explore`.
- `src/backend/app/agents/models.py` — sửa: comment `#` trên `TurnRoute`, `ExploreNarration`.
- `src/backend/app/agents/steps/classification.py` — sửa: docstring `route_input`, `route_result`, `understood`.
- `src/backend/app/agents/steps/prompts.py` — sửa: comment trên `CLASSIFY_PROMPT`, `EXPLORE_PROMPT`, ngoài chuỗi prompt.
- `src/backend/app/agents/steps/exploration.py` — sửa: docstring module ghi module đóng băng và liệt kê phần còn dùng chung
  (`once_praise`, `checked_suggestions`, `CATALOG_HINT`, `conversation_templates`, `about`).
- `src/backend/app/main.py` — sửa: log `startup.itinerary_legacy_flow_active orchestrator=off` (WARNING) lúc khởi động khi
  `ITINERARY_ORCHESTRATOR` khác `on`.
- `src/backend/tests/unit/agents/test_explore_storytelling.py`, `test_open_question.py`, `test_explore_asked_place.py` —
  sửa: đoạn đóng băng trong docstring module, "không thêm ca mới".
- `docs/plan/2026-10-12-go-luong-cu-orchestrator-chinh.md` — sửa: mục D0 ghi đúng cách đã làm và trạng thái xong.
- `history/2026-10-13-d0-danh-dau-luong-cu.md` — thêm: entry này.

## Quyết định

- Mọi ghi chú bắt đầu bằng cùng một cụm `LUỒNG CŨ — ĐÓNG BĂNG (chốt 13/10/2026)`, để
  `grep -rn "LUỒNG CŨ — ĐÓNG BĂNG" src/` ra đúng danh sách. G6 xoá chúng cùng code.
- Model Pydantic dùng comment `#`, không dùng docstring. Docstring của class thành `description` trong JSON schema gửi
  LLM, nên sửa nó là đổi payload và làm lệch cassette của snapshot. Đã so `model_json_schema()` của `TurnRoute`,
  `ExploreNarration`, `OrchestratorTurn`, `ConversationalAnswer` giữa HEAD và working tree: giống hệt.
- Log cảnh báo đặt ở startup trong `main.py`, cạnh `startup.itinerary_orchestrator.fallback`, chứ không ở `graph.py`
  như plan ghi trước đó. `build_graph` chạy lại mỗi request, nên log ở đó sẽ lặp; startup chạy một lần mỗi tiến trình.
  Đã sửa plan cho khớp.
- Chỉ đánh dấu file test mà toàn bộ nội dung là node `explore` cũ. File trộn phần dùng chung (`test_classify.py` có
  `extract_result`, `test_exploration.py` có đồng ý lập lịch, `test_routing.py`, `test_itinerary_runtime.py`,
  `test_place_facts.py`) để G0 phân loại theo từng ca.
- `converse_node` không đóng băng cả node: orchestrator vẫn đi qua nó khi guardrail chặn hoặc tin rác (chạy thử ngày
  12/10: 0,0 giây, không gọi LLM).

## Kiểm tra

- Trước lần sửa code đầu đã đọc tài liệu theo AGENTS.md §1.1–1.2 và ghi xác nhận §1.3 cho người dùng trong phiên.
- `WEAVIATE_URL=http://127.0.0.1:9 SEARCH_PREWARM=false HF_HUB_OFFLINE=1 LANGSMITH_TRACING=false .venv/bin/python -m pytest
  -q -p no:cacheprovider src/backend/tests/unit/agents src/backend/tests/unit/domain src/backend/tests/architecture` →
  **2112 passed** (20,67 s). Có `test_behavior_snapshot.py` của luồng cũ, không ghi lại snapshot.
- Cùng env, `src/backend/tests` → **2938 passed, 36 skipped, 1 warning** (38,65 s). Warning là deprecation của
  Starlette/anyio, có từ trước.
- `HF_HUB_OFFLINE=1 .venv/bin/python -c "import src.backend.app.main"` → chạy được.
- `git diff --check` → không lỗi.

## Còn lại / rủi ro

- Code vẫn mặc định `off` tới D3, nên chạy local theo `.env.example` thì log cảnh báo sẽ hiện. Đây là chủ ý: nhắc người
  chạy đặt `ITINERARY_ORCHESTRATOR=on`.
- Tiếp theo: D2 (mã nguyên nhân, đồng hồ tiêm được, harness) và D1 (kiểm chứng demo với LLM thật).
