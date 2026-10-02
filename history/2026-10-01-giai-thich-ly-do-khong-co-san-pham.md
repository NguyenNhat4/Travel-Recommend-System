# Agent nêu lý do thật khi không có sản phẩm ("không có hotel à")

- Ngày: 2026-10-01
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/itinerary-agent-guardrails
- Trạng thái: hoàn thành
- Phạm vi: agent, backend, frontend, contract, docs

## Mục tiêu

Trace LangSmith `nhat-10-1`, thread `97b12b95-ddd2-49c5-9009-d106d5214c83` (Hà Nội 3 ngày từ 02/10/2026): lượt "ngày mai"
ra lịch trình không có khách sạn mà không nói vì sao; lượt "không có hotel à" (search ra 10 khách sạn, `evaluate` loại cả
10 vì `PRODUCT_DROPPED_DATE`) chỉ nhận câu chung "Không tìm thấy sản phẩm đáp ứng điều kiện bắt buộc…". Người dùng hỏi
giải pháp khi người dùng hỏi "tại sao"; plan đã duyệt: `/home/nhatnm/.claude/plans/khi-ng-i-d-ng-h-i-validated-rabbit.md`.
Phục vụ FR-AGT-01, FR-AGT-04, NFR-REL-01, `docs/prd/user-flow.md` §3.2 (nhánh "Thiếu → hỏi thêm người dùng").

Đã đọc trước khi code: `docs/prd/README.md`, `requirements.md` (§1.4, §2.2, AC-AGT-01), `user-flow.md` (§3.2, §4.2),
`architecture.md` (§2, §3, §6.2–6.3), `api-contract.md` (§3, §4); `docs/prd/update/` (trống); `contracts-guide.md`,
`mvp-minimal-fields-1.2.0.md`, spec Itinerary §4.3–4.4, `docs/spec/agent/README.md`, `langgraph-nodes.md`,
`state-fields.md`, `hop-dong-tich-hop-frontend.md`, `openapi.yaml`, `schemas/itinerary-agent.yaml`, README mock agent,
`src/backend/README.md`, `src/frontend/README.md`; `history/README.md`, 10 entry mới nhất,
`2026-09-29-no-results-goi-y-bam-duoc.md`, `2026-09-21-tach-clarify-khoi-answer.md`, `2026-09-30-tieu-de-cho-moi-cau-tra-loi.md`.

## File thay đổi

- `src/shared/contracts/schemas/itinerary-agent.yaml` — sửa: `ItineraryNeedsClarification.suggestions` tuỳ chọn (tối đa 3).
- `src/shared/contracts/openapi.yaml` — sửa: version 1.12.0 → 1.13.0.
- `src/backend/app/domain/itinerary/types.py` — sửa: thêm `DropSummary`.
- `src/backend/app/application/itinerary/retrieval.py` — sửa: `nearest_open_date(..., taxonomy=None)`; thêm `drop_summary` (lý do từng taxonomy không còn candidate, cùng luật `_drop_reason`).
- `src/backend/app/agents/state.py`, `src/backend/app/agents/nodes.py` — sửa: field `drop_summary`, `intake` đặt `{}`.
- `src/backend/app/agents/steps/evaluation.py` — sửa: ghi `drop_summary` khi `compose`/`constraint_clarification`; cảnh báo `PRODUCT_DROPPED_DATE` ghi cửa sổ mở bán thật.
- `src/backend/app/agents/steps/explanations.py` — thêm: `constraint_question` (câu cố định theo lý do + chip), `missing_stay_note`.
- `src/backend/app/agents/steps/conversation.py` — sửa: `constraint_clarification` dùng câu có lý do và `suggestions`, không biết lý do thì giữ `CLARIFY_CONSTRAINT`.
- `src/backend/app/agents/steps/composition.py` — sửa: cảnh báo `NO_STAY_AVAILABLE` khi lịch không có chỗ ở.
- `src/backend/app/agents/steps/narration.py` — sửa: mục "**Chưa có khách sạn**" do backend chèn trước mục chi phí (cả câu LLM lẫn bản dựng bằng luật); payload có `no_stay_explained`.
- `src/backend/app/agents/steps/prompts.py` — sửa: `NARRATE_PROMPT` không tự nói lý do thiếu khách sạn; `EXTRACT_PROMPT` thêm "giá trị mới khác chuyến cũ là đổi, không phải mâu thuẫn".
- `src/backend/app/agents/steps/classification.py` — sửa: bỏ cờ `conflict` khi LLM tự xếp lượt là đổi (`change_without_value`) kể cả khi có giá trị mới.
- `src/backend/app/agents/steps/messages.py` — sửa: câu vi/en `unmet_*`, `no_stay_*`, `dropped_date`, `suggestion_change_date`, `suggestion_no_stay`.
- `src/backend/tests/conftest.py` — sửa: tắt `LANGSMITH_TRACING` trong test.
- `src/backend/tests/unit/agents/test_explanations.py` — thêm (10 test); `test_itinerary_runtime.py` (+2), `test_narration.py` (+3), `test_turn_context.py` (+1), `src/backend/tests/unit/application/test_itinerary_retrieval.py` (+5) — sửa.
- `src/frontend/src/types/api.gen.ts` — sửa: sinh lại.
- `src/frontend/src/features/itinerary/widget/useFloatingWidget.ts` — sửa: chip cho cả `NEEDS_CLARIFICATION`.
- `src/frontend/src/components/assistant/SuggestionChips.tsx` — sửa: comment.
- `src/frontend/tests/unit/floatingWidgetOpening.test.tsx` — sửa: thêm test chip của câu hỏi lại.
- `docs/spec/hop-dong-tich-hop-itinerary-assistant.md` (§4.3 bảng tiêu đề, §4.4, thêm §4.4.1), `docs/spec/agent/langgraph-nodes.md`, `docs/spec/agent/state-fields.md`, `docs/spec/hop-dong-tich-hop-frontend.md` — sửa.
- `history/2026-10-01-giai-thich-ly-do-khong-co-san-pham.md` — thêm: entry này.

Working tree còn thay đổi chưa commit của `history/2026-10-01-ap-dung-diem-tham-quan-tu-do-tinh-0-vao-tong.md` trong cùng
một số file (`composition.py`, `messages.py`, `narration.py`, `prompts.py`, `test_itinerary_runtime.py`, `api.gen.ts`,
`itinerary-agent.yaml`, hai spec). Entry này chỉ mô tả phần của nó; không đụng `planning.py`, `docs/prd/architecture.md`,
`WidgetDays.tsx`, `WidgetPlanPanel.tsx`, `widgetPlan.ts` và test tương ứng.

## Quyết định

- **Không lệch PRD.** PRD không quy định nội dung câu hỏi lại; user-flow §3.2 đã có nhánh hỏi thêm. `suggestions` là field
  tuỳ chọn mới, được phép trong v1 (`api-contract.md` §3), bump minor 1.13.0. Không cần đề xuất `docs/prd/update/`.
- **Lý do do backend dựng tất định**, không để LLM diễn đạt: số khách sạn, cửa sổ mở bán, ngày gần nhất đều lấy từ kết quả
  tool của lượt đó. Vẫn không tự nới điều kiện bắt buộc thay người dùng (giữ quyết định ở entry 2026-09-29).
- **Khác plan:** mục "Chưa có khách sạn" trong lời diễn giải do backend chèn (như mục gói nhiều ngày), không giao LLM viết
  theo quy tắc prompt — LLM hay quên câu bắt buộc. Một mã chung `NO_STAY_AVAILABLE` (message nêu lý do) thay cho
  `STAY_UNAVAILABLE_FOR_DATES` của plan, vì khách sạn có thể bị loại vì giá/tiêu chí chứ không chỉ ngày.
- **Chip ngày là câu đổi rõ ràng** "Đổi ngày khởi hành sang dd/mm/yyyy", không dùng lại "Đi … từ ngày …" của NO_RESULTS:
  chạy thật, câu "Đi Hà Nội 3 ngày từ ngày 15/10/2026" sau một chuyến đã có ngày 02/10 bị extract (gpt-4o-mini) đặt
  `conflict=true` 2/2 lần và hỏi "Xác nhận ngày khởi hành". Câu "đổi sang …" khớp ví dụ sẵn có trong `EXTRACT_PROMPT`.
- **Sửa `conflict` hẹp**: trace thật cho `conflict=true` + `change_without_value=['startDate']` + patch có ngày mới. LLM đã tự
  xếp là "đổi" nên bỏ `conflict`; mâu thuẫn trong cùng câu (ngày đi/về lệch số ngày) vẫn do `conflicting_days` tất định.
- **Tắt LangSmith trong test**: người dùng thấy hàng loạt trace < 0,05 s trên `nhat-10-1`. Nguyên nhân: contract test dựng
  app, `.env` bật `LANGSMITH_TRACING` nên `main._enable_langsmith` ghi cờ vào `os.environ`, mọi lượt graph với LLM giả sau
  đó trong cùng tiến trình pytest bị gửi lên project thật (tên "LangGraph", "lên lịch giúp mình", "conv-khong-co").

## Kiểm tra

- `PYTHONDONTWRITEBYTECODE=1 python3 src/shared/contracts/tests/validate_contract.py`: PASS.
- `.venv/bin/python -m pytest -q src/backend/tests`: 1095 passed, 21 skipped (trước lần đổi chip); sau đó
  `src/backend/tests/unit src/backend/tests/architecture`: 1023 passed.
- `.venv/bin/python -m pytest -q src/backend/tests src/evaluation/tests`: 5 failed, 1143 passed, 21 skipped — 5 test
  `test_golden.py` fail sẵn (ghi ở `history/2026-10-01-ap-dung-diem-tham-quan-tu-do-tinh-0-vao-tong.md`).
- Frontend `npx vitest run`: 490 passed (49 file) ở 3 lần; một lần chạy ngay sau pytest nặng ra 9 failed / 8 file, chạy lại
  hai lần đều pass — chập chờn do tải máy, không lặp lại. `npx tsc --noEmit`: chỉ 3 lỗi sẵn có trong `.next/types`;
  `npx eslint` các file đổi: sạch.
- Chạy thật: backend riêng cổng 8010 (`ITINERARY_DATA_MODE=inprocess`, gpt-4o-mini, Postgres/Weaviate local), phát lại thread
  Hà Nội, trace 15:19–15:34 UTC trên `nhat-10-1` (mỗi lượt 4–17 s). Lượt "ngày mai": `COMPLETED`, mục "Chưa có khách sạn"
  nêu 15/10–16/10/2026 và gợi ý dời sang 15/10. Lượt "không có hotel à": `NEEDS_CLARIFICATION`
  "**Khách sạn ở Hà Nội chưa mở bán cho ngày đi**… 10 khách sạn… 15/10/2026–16/10/2026…", chip
  `Đổi ngày khởi hành sang 15/10/2026`, `Đi Hà Nội 3 ngày, không cần khách sạn`. Bấm chip đổi ngày: 2/2 lần ra `COMPLETED`
  có khách sạn Box Hotel từ 15/10.
- Sau khi tắt tracing trong test: chạy 17 contract test assistant, LangSmith không có trace mới từ test.

## Còn lại / rủi ro

- **Chip "không cần khách sạn" chưa ra lịch trình**: thử 1 lần ra `NO_RESULTS`. Bằng chứng trong trace: extract chỉ đặt
  `require_hotel=false` (không thêm `hotel` vào `exclude_taxonomies`), planner tìm điểm tham quan bằng query một từ "tour"
  → search trả 0 (ngưỡng điểm; "Hà Nội" trả 24, "tham quan Hà Nội" trả 82) và lượt đó không gọi `get_recommendations`.
  Là vấn đề sẵn có của planner/search, chưa sửa.
- Extract (gpt-4o-mini) vẫn hay báo `conflict` nhầm: một lần chạy đặt `require_hotel=true` ngay ở "ngày mai" rồi báo
  `conflict` ở "không có hotel à". Chưa có cách tất định chặn hết.
- **Gốc dữ liệu chưa sửa**: loader cắt cửa sổ khách sạn còn đúng đêm đã cào giá (`queried_stay_not_a_general_date_range`),
  9.927/10.059 khách sạn chỉ đặt được 1–2 ngày. Agent nay giải thích đúng dữ liệu, nhưng muốn khách sạn thật sự xuất hiện
  thì cần đề xuất đổi quy tắc AGENTS.md §6.2 qua `docs/prd/update/`.
- Lời diễn giải LLM đôi khi vẫn nhắc "không bao gồm chỗ ở" ở mục Lưu ý dù prompt dặn không — không sai dữ liệu.
- Sở thích "biển" của câu đầu thread bị giữ sang chuyến Hà Nội và thành query search — chưa sửa.
- `docs/spec/hop-dong-tich-hop-frontend.md` còn nhắc `AssistantConversation.tsx` đã không còn trong code.
- Backend demo cổng 8000 cần khởi động lại để có code mới. Chưa commit.
