# D3: baseline snapshot trên orchestrator, tài liệu agent theo luồng duy nhất

- Ngày: 2026-10-13
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành (chờ người dùng duyệt baseline, R2)
- Phạm vi: agent, docs, evaluation, frontend
- Thay thế: `2026-10-13-go-luong-cu-orchestrator-duy-nhat.md` (entry đó dừng ở trạng thái dang dở; entry này làm nốt mục "Còn lại")
- Phục vụ: FR-AGT-01, FR-AGT-05, FR-AGT-06, FR-AGT-07, NFR-REL-01, NFR-SEC-04

## Thay đổi

- `src/backend/tests/unit/agents/behavior_snapshot/{snapshot.json,cassette.json,tools.json.gz,scenarios.json}` — sửa: ghi
  lại toàn bộ trên orchestrator bằng `record --fresh` (63 kịch bản, 191 lượt, gồm `demo-K1`…`demo-K6`).
- `src/backend/tests/unit/agents/behavior_snapshot/harness.py` — sửa: event trong snapshot giữ mã `ROUND_LIMIT`/`TOOL_LIMIT`.
- `src/backend/tests/unit/agents/test_behavior_snapshot.py` — sửa: docstring.
- `src/evaluation/reports/eval-2026-10-13-d3-snapshot-orchestrator.md` — thêm: bảng so với luồng cũ, mỗi hội thoại một dòng, đánh giá theo AC.
- `src/backend/scripts/push_prompts_to_langsmith.py` — sửa: bỏ `CLASSIFY_PROMPT` (đã gỡ, script lỗi import), thêm `ORCHESTRATOR_PROMPT`.
- `src/backend/app/domain/itinerary/exploration.py`, `tests/unit/agents/test_fares_followups.py`, `test_fares_messy.py`,
  `test_extract.py` (đổi tên helper `classify` → `decide`) — sửa: docstring/tên còn nhắc `classify`.
- `src/backend/app/agents/steps/replies.py`, `domain/itinerary/preferences.py`, `tests/unit/agents/test_exploration.py` — sửa: bỏ dòng trống cuối file (`git diff --check`).
- `src/frontend/tests/unit/widgetProgress.test.ts` — sửa: dùng đường node thật (`precheck`, `orchestrate`, `gatekeep`).
- `docs/plan/2026-10-12-go-luong-cu-orchestrator-chinh.md` — sửa: đầu plan, mục 0, 1.1, 1.4, D0, D3 (kết quả), D5, mục 3, 4 (G0, G2, G5, G6, G7), 5, 6 theo việc đã gỡ luồng cũ.
- `docs/plan/2026-10-12-tien-trinh-tro-ly-co-ket-qua.md` — sửa: phạm vi, mục 6, 7 (luồng cũ đã gỡ, Phần C đạt tiêu chí).
- `docs/spec/agent/langgraph-nodes.md` — sửa: viết lại mục 1, 3, 3.1, bảng 6 và 6.1 cho 17 node của orchestrator.
- `docs/spec/agent/state-fields.md` — sửa: node ghi/đọc theo orchestrator; bỏ field đã gỡ; thêm `turn_limit_reason`.
- `docs/spec/agent/working-context.md` — sửa: §5A cách ghi/phát lại snapshot.
- `docs/spec/agent/nghiep-vu/{tro-chuyen-va-kham-pha,hieu-y-dinh-va-hoi-lai,tu-van-ve-may-bay,sua-lich-qua-nhieu-luot,tim-ung-vien,dien-giai-va-kiem-tra,glossary}.md` — sửa: theo orchestrator, ghi lỗi đã biết.
- `docs/guide/doc-code-backend.md`, `docs/guide/doc-code-ui-tro-ly.md`, `.agents/skills/building-itinerary-agent/references/industry-patterns.md` — sửa: tên node.

## Quyết định

- Snapshot dựng lại từ cassette (không gọi LLM) sau khi thêm mã phanh; so với bản vừa ghi chỉ thêm trường `reason`.
- Không thêm kịch bản `ROUND_LIMIT`/`TOOL_LIMIT` riêng: 6 lượt của bản ghi đã chạm `TOOL_LIMIT` (gồm demo-K2 lượt 3).
- Các lượt kém hơn luồng cũ là hành vi sẵn có của orchestrator: `precheck` giống hệt nhánh `orchestrator_active` tại `a50c5e62`.
- Không sửa `CONVERSATION_PROMPT` (còn phần chỉ `converse` cũ dùng) vì đổi payload của `clarify`; để làm khi ghi lại snapshot.

## Kiểm tra

- Phát lại snapshot offline: 4 passed, `cassetteMiss`/`toolMiss` rỗng.
- `WEAVIATE_URL=http://127.0.0.1:1 SEARCH_PREWARM=false .venv/bin/python -m pytest -q src/backend/tests`: **2853 passed, 36 skipped, 3 xfailed**.
- Frontend: `vitest run` xanh, `tsc --noEmit` exit 0.
- `push_prompts_to_langsmith.py --dry-run`: 6 prompt, không lỗi.
- `git diff --check`: sạch.
- Chưa chạy lại `src/evaluation/tests` sau lượt này (người dùng dừng lệnh); lần trước: golden + eval_app 88 passed.

## Còn lại

- Người dùng duyệt baseline D3 (R2), rồi D4 (T1–T4), D5 (D1-xx, D3-xx).
- Lỗi mới của D3: D3-01 (chặn demo, mất điểm đến sau câu hỏi lại), D3-02, D3-03, D3-04 (xấu), D3-05 (nhỏ). D1-07 và D1-04 rộng hơn D1 thấy.
- `dont_know_count` không còn node nào tăng (bậc "không biết" của `classify` cũ); `orchestrator_active` luôn `True`. Dọn hoặc làm lại ở G3.
- Chờ chốt đề xuất tiến trình Phần A, B, C.
