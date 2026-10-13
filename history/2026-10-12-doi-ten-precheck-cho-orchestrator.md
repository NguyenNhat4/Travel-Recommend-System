# Đổi tên bước đầu vào của orchestrator thành precheck

- Ngày: 2026-10-12
- Tác giả: Nguyễn Minh Nhật / Codex
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: agent, docs

## Mục tiêu

Người dùng nhận xét tên classify ở luồng mới gây hiểu nhầm là vẫn có LLM phân loại trước orchestrator.
Đổi tên node, router và event sau cờ thành precheck; không đổi hành vi. Phục vụ FR-AGT-06, AC-AGT-06/07,
NFR-REL-01 theo kiến trúc PRD §3 Rules → Orchestrator. Không thay PRD/API.

## File thay đổi

- `src/backend/app/agents/nodes.py` — sửa: entry precheck sync/async không nhận model; dùng luật có sẵn,
  bật nhánh orchestrator và đổi tên event classify thành precheck.
- `src/backend/app/agents/graph.py` — sửa: cờ on có precheck thay classify; tên Runnable/trace đồng nhất.
- `src/backend/app/agents/routing.py` — sửa: intake chọn precheck sau cờ và router có tên riêng; cờ off giữ mặc định cũ.
- `src/backend/tests/unit/agents/test_orchestrator_runtime.py` — sửa: kiểm topology/event và mock.assert_not_called
  xác nhận precheck sync/async không gọi classifier, cả tin hợp lệ và tin guardrail chặn.
- `docs/spec/agent/langgraph-nodes.md` — sửa: sơ đồ/giải thích precheck của đường on, giữ phần classify đường off.
- `docs/spec/agent/state-fields.md` — sửa: phân biệt tên node/event hai đường.
- `docs/spec/agent/working-context.md` — sửa: bản đồ runtime on.
- `docs/plan/2026-10-12-nho-ket-qua-da-xem.md` — sửa: tên node trong thiết kế sau cờ.

## Quyết định

- Chỉ đổi tên lớp entry/trace, dùng lại luật trước LLM hiện có. Luồng mặc định off giữ nguyên classify và snapshot.
- Không đưa model phân loại vào precheck; tin bình thường chuyển thẳng orchestrate. Guardrails/nút vé/chọn phương án
  giữ hành vi đã chốt. Không thêm regex, không thay prompt hay model.
- Chưa commit. Demo local sẽ nạp lại để người dùng thấy tên mới.

## Kiểm tra

- `WEAVIATE_URL=http://127.0.0.1:9 SEARCH_PREWARM=false HF_HUB_OFFLINE=1 LANGSMITH_TRACING=false
  .venv/bin/python -m pytest -q -p no:cacheprovider src/backend/tests/unit/agents src/backend/tests/unit/domain`
  → **2104 passed, 19.62 s**; log `/tmp/orchestrator-precheck-tests.log`, gồm snapshot off không đổi.
- Kiểm lại test runtime sau bổ sung mock.assert_not_called: `HF_HUB_OFFLINE=1 LANGSMITH_TRACING=false
  .venv/bin/python -m pytest -q -p no:cacheprovider src/backend/tests/unit/agents/test_orchestrator_runtime.py`
  → **21 passed, 3.25 s**; log `/tmp/orchestrator-precheck-focused.log`.
- `git diff --check`: PASS. NodeId của SSE là string, không enum; không đổi shape/endpoint/contract.
- Demo đang phục vụ là process group make web 64339, khác session demo cũ đã dừng; xác nhận đúng args,
  SIGTERM cả group, kiểm hai cổng :8000/:3000 đã nhả, chạy lại `HF_HUB_OFFLINE=1 SEARCH_PREWARM=false make web`.
  Không reset DB hoặc đổi env.
- HTTP/SSE qua Next BFF, script `/tmp/check_orchestrator_precheck.py`, chat mới gửi “di chua”: HTTP200, **25246 ms**,
  `intake → precheck → orchestrate → run_jobs → orchestrate → gatekeep → finalize`, 3 thẻ chùa;
  assert thứ tự node chính xác, không có classify: **PASS**. Request `0df35da8-1c24-40b3-9417-b7f90719d1cf`,
  raw event JSON `/tmp/orchestrator-precheck-http.json`. Đây là model/catalog thật, chưa phải kiểm giao diện DOM.


## Còn lại / rủi ro

- Không còn việc trong phạm vi đổi tên; demo đã nạp bản mới. Trace cũ giữ tên ở thời điểm chạy, không sửa lại.
- Cờ source mặc định off, local on theo env của người dùng; chưa deploy hoặc commit. Không tuyên bố SLA từ smoke một lượt.
