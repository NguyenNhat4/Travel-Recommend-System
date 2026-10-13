# Gỡ luồng phân loại cũ: orchestrator là luồng duy nhất, bỏ cờ ITINERARY_ORCHESTRATOR

- Ngày: 2026-10-13
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: dang dở
- Bị thay thế bởi: `2026-10-13-d3-baseline-va-tai-lieu-orchestrator.md`
- Phạm vi: agent, backend, evaluation, docs (PRD)
- Thay thế: `2026-10-13-chot-orchestrator-mac-dinh.md` (phần "gỡ sau demo", luồng cũ giữ sau cờ `off`);
  `2026-10-13-d0-danh-dau-luong-cu.md` (ghi chú đóng băng trong code, nay xoá cùng code)

## Mục tiêu

Người dùng nhắn: "code ko dùng thì remove khỏi nodes và graph để ko phải đọc trùng". Khi được hỏi chọn giữa "chuyển ra
module riêng, giữ cờ quay về" và "gỡ hẳn ngay, bỏ cờ", người dùng chọn **gỡ hẳn ngay, bỏ cờ**. Đây là chốt đề xuất
`docs/prd/update-archive/2026-10-13-go-luong-cu-sau-demo.md`; quyết định này thay việc hoãn tới sau demo. Phục vụ
FR-AGT-01, FR-AGT-06, FR-AGT-07, NFR-SEC-04, NFR-REL-01. Đã đọc tài liệu theo AGENTS.md §1 và ghi xác nhận §1.3 trong
phiên.

## Đã làm (tới lúc ghi entry)

PRD và đề xuất:
- `docs/prd/architecture.md` §3: orchestrator là luồng duy nhất; `precheck` thay `ClassifyTurn`; "orchestrator" thay
  "phân luồng".
- `docs/prd/deployment-plan.md` §2: xoá dòng `ITINERARY_ORCHESTRATOR`.
- `docs/prd/requirements.md` AC-AGT-06: "luồng duy nhất từ 2026-10-13".
- `docs/prd/update-archive/2026-10-13-go-luong-cu-sau-demo.md`: đổi chỗ từ `update/` (file chưa git theo dõi, dùng
  `mv`); đã áp dụng, chốt bởi Nguyễn Minh Nhật 2026-10-13.

Code runtime:
- `agents/nodes.py`:
  - `precheck_node` là node riêng chứa các luật trước LLM, không còn gọi `classify_node`.
  - Bỏ `classify_node(_async)`, `explore_node(_async)`.
  - `converse_node(_async)` chỉ còn câu cố định khi guardrail hoặc tin rác bị chặn, không gọi LLM.
  - `extract` chưa đồng ý lập lịch thì trả lượt cho `gatekeep` bằng `plan_denied` (`_consented`), không còn đích
    `explore`, `converse`.
  - `intake_node` không còn tham số cờ.
- `agents/graph.py`, `agents/routing.py`: chỉ dựng luồng orchestrator.
  - Bỏ `route_after_classify`, `route_after_explore`.
  - `orchestrate` ra `error` thì đi `dead_letter`.
- `agents/steps/orchestration.py`: không có model (`ITINERARY_USE_LLM=false`, thiếu khoá) thì trả 503 `LLM_UNAVAILABLE`
  như contract, không trả câu dự phòng 200. Lỗi này lộ ra khi test contract chạy trên orchestrator.
- Xoá phần chỉ luồng cũ dùng:
  - `classification.py`: `route_input`, `route_result`, `understood`, `rejected_places` và 9 helper.
  - `models.py`: `TurnRoute`, `ExploreNarration`.
  - `prompts.py`: `CLASSIFY_PROMPT`, `EXPLORE_PROMPT`; một dòng `place_not_found` trong `CONVERSATION_PROMPT`.
  - `exploration.py`: 68 định nghĩa của node `explore`. Phần còn lại đổi tên thành `steps/replies.py` (`git mv`):
    `checked_suggestions`, `conversation_templates`, `CATALOG_HINT`, `once_praise`, `about`.
  - `conversation.py`: `place_not_found` và các regex kiểm "nói giờ, giá khi không có dữ liệu" (chỉ chạy khi `classify`
    ghi `explore_place`).
  - `messages.py`: 18 khoá `explore_*`, `unverified_fact` (×2 ngôn ngữ).
  - `state.py`, `phase.py`: trường `explore_place`, `explore_city`, `explore_focus`, `explore_price`, `explore_pick`,
    `explore_direct` (không còn ai ghi).
  - `domain/itinerary/exploration.py`: `cheapest_cards`, `dearest_cards`, `has_amenity`, `with_amenity`,
    `closest_named`, `ASKED`, `LOW_PRICE`, `HIGH_PRICE`.
  - `domain/itinerary/preferences.py`: `by_key`, `_BY_KEY`.
  - Event của các luật trước LLM mang tên node `precheck` trực tiếp (`changes.py`, `fares.py`, `classification.py`).
- Bỏ cờ:
  - `core/config.py` bỏ `itinerary_orchestrator`; `infrastructure/llm/client.py` bỏ điều kiện cờ.
  - `main.py` bỏ tham số cờ và log `startup.itinerary_legacy_flow_active` (D0).
  - `runtime_dependencies.py` bỏ tham số cờ, thêm `orchestrator_budget()` dùng chung.
  - `docker-compose.yml`, `.env.example` bỏ biến.
- `src/evaluation/agent/golden.py`: dựng model riêng của orchestrator và ngân sách như `main.py`.
  `src/evaluation/agent/cli.py`: sửa comment.

Test:
- Xoá `test_explore_asked_place.py`, `test_explore_storytelling.py`, `test_open_question.py`, và các ca chỉ kiểm nhãn
  `classify` hoặc node `explore` trong `test_exploration.py`, `test_extract.py` (đổi tên từ `test_classify.py`),
  `test_itinerary_runtime.py`, `test_messy_replies.py`, `test_place_facts.py`, `test_fares.py`.
- Chuyển sang orchestrator, `precheck`, `converse` cố định:
  - `test_guardrails.py`, `test_routing.py`, `test_shown.py`, `test_lab_copy.py`, `test_option_swap.py`.
  - `test_assistant_contract.py`, `test_llm_factory.py`.
  - `test_itinerary_runtime.py`: LLM giả trả `OrchestratorTurn`.
  - `test_fares.py`: job `fare`.
- `test_replies.py` (mới): giữ ca của `once_praise`, `about`.
- Ba ca của AC-AGT-08 mang `xfail(strict=True)`: nút do code tạo cho câu trả lời vé bị mất trên orchestrator; sửa ở D5.
- Bộ golden `agent_test_cases_nhat.yaml` (TC-10, 12, 13, 15) và `agent_scenarios_v5.yaml`: kỳ vọng node theo
  orchestrator. `test_golden.py` đổi event mẫu.

## Kiểm tra (tới lúc ghi entry)

- `src/backend/tests`: **2851 passed, 36 skipped, 3 xfailed, 2 failed**. Hai ca đỏ là `test_behavior_snapshot.py`, vì
  snapshot còn là của luồng cũ và phải ghi lại trên orchestrator (D3). Không ca nào khác đỏ.
- `src/evaluation/tests/test_golden.py`, `test_eval_app.py`: **88 passed**.
- `src/evaluation/tests` còn 12 ca đỏ (CDP reader, RecSys prototypes, temporal). Trên worktree sạch ở HEAD `a50c5e62`, đúng
  các ca này cũng đỏ (13 ca, gồm thêm `test_postgres_cdp_reader.py`). Vậy chúng có sẵn từ trước, không do thay đổi này.
- `HF_HUB_OFFLINE=1 .venv/bin/python -c "import src.backend.app.main, src.evaluation.agent.golden"` → chạy được;
  `build_graph()` có 17 node, không còn `classify`, `explore`.

## Còn lại

1. D3: ghi lại snapshot trên orchestrator.
   - Lệnh `record --fresh`, thêm K1–K6 và một kịch bản chạm `ROUND_LIMIT`/`TOOL_LIMIT`.
   - Phát lại offline phải xanh.
   - Bảng tóm tắt khác biệt cho người dùng duyệt.
2. Docstring và comment còn nhắc `classify` trong code:
   - `nodes.py` (đầu module, sơ đồ graph), `steps/__init__.py`, `consent.py`, `changes.py`, `fares.py`, `history.py`,
     `phase.py`, `prompts.py`, `state.py`, `graph.py`.
   - Docstring của `models.Extraction` là mô tả trong JSON schema gửi LLM, nên đổi cùng lúc ghi lại snapshot.
3. Tài liệu:
   - `AGENTS.md` §3: thay ghi chú đóng băng bằng "đã gỡ".
   - `docs/spec/agent/` (`working-context.md`, `README.md`, `langgraph-nodes.md`, `state-fields.md`,
     `response-and-errors.md`, `nghiep-vu/*`); `docs/spec/hop-dong-tich-hop-itinerary-assistant.md` §6;
     `src/backend/README.md`; skill `building-itinerary-agent`.
   - Hai plan (gộp các bước gỡ vào trước demo).
4. Báo cáo D1 (`src/evaluation/reports/`) và danh sách lỗi D1 trong plan. Lỗi đã thấy:
   - Mốc "Hồ Gươm" không khớp "Hồ Hoàn Kiếm" nên 0 thẻ, ở cả 3 lần chạy K1.
   - Nút của câu trả lời vé bị mất.
   - Lập lịch đủ thông tin vẫn hỏi ngân sách.
5. Ghi các ca test đã xoá vào mục kiểm kê G0 của plan (danh sách ở scratchpad `g0/deleted_explore_tests.txt`), để kiểm
   lại ý AC trên orchestrator.
6. Frontend: kiểm còn chỗ nào dựa vào tên node `classify`, `explore` không (`widgetProgressView.ts`).
7. Chạy cả bộ backend, frontend; cập nhật entry này sang `hoàn thành`.
