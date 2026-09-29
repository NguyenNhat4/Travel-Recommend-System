# Sửa backend CI đỏ sau commit merge "merge conflict agent"

- Ngày: 2026-09-29
- Tác giả: tqanh123 / Claude Code
- Nhánh: bench/embed-search
- Trạng thái: hoàn thành
- Phạm vi: backend, agent, docs

## Mục tiêu

CI chạy `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q src/backend/tests` và báo đỏ: 48 failed, 603 passed, 19 skipped. Cần sửa cho CI xanh.

Nguyên nhân là commit merge `a129fa0` ("merge conflict agent"), gộp hai nhánh vào `bench/embed-search`:
- **Phía bench:** `750ce43`, agent gọi engine trong tiến trình và có tool Similar (`history/2026-09-29-tool-similar-cho-agent.md`).
- **Phía release:** `627d5b9`:
  - tách classify/extract, ngữ cảnh `llm_context` (`history/2026-09-25-tach-classify-extract-hoi-chi-tiet-chuyen-di.md`);
  - chủ hội thoại theo user (`history/2026-09-25-chu-hoi-thoai-theo-user.md`).

Khi giải conflict, hai đoạn code của phía release được giữ lại, nhưng chúng gọi tên mà phía bench đã đổi hoặc bỏ.

Phục vụ FR-AGT-02, FR-AGT-05 (lập plan, đổi món), FR-USR-03 (chủ hội thoại theo JWT) và NFR-REL-01 (grounding). Chỉ sửa lỗi merge, không đổi hành vi so với PRD.

## File thay đổi

- `src/backend/app/agents/steps/tool_planning.py` — sửa:
  - `build_plan` truyền `offered=offered` mà biến chưa được định nghĩa → `NameError` ở mọi lượt lập plan (45/61 test lỗi);
  - hợp nhất hai phía: dùng lại `_planner_input` của phía bench (mời Similar, `SIMILAR_HINT`, `offered`; plan đã lưu chạy lại không đọc `definitions()`);
  - payload lấy ngữ cảnh chung `llm_context` của phía release, cộng khoá `intent`/`constraints`;
  - `_planner_input` nhận thêm `constraints` và không còn dùng `sanitize_conversation_history` (không còn được import).
- `src/backend/app/api/deps.py` — sửa: `conversation_owner` gọi `_bearer`/`_verified`, hai hàm phía bench đã chuyển sang `application/auth/bearer.py` → `NameError` (12 test). Nay dùng `principal_from_header`; hành vi giữ nguyên (không có hoặc hỏng Bearer → `None`, không 401).
- `src/backend/tests/unit/agents/test_itinerary_tools.py` — sửa: `test_similar_is_offered_only_with_a_selection_and_a_similar_port`, nhánh không mời Similar:
  - payload = `message`/`intent`/`constraints` + khoá của `llm_context`, thay cho bốn khoá cũ;
  - `previous_selection` là ngữ cảnh của state.
- `src/backend/tests/unit/agents/test_itinerary_runtime.py` — sửa:
  - `test_similar_is_offered_only_on_a_swap_turn`: lượt đầu có `previous_selection == []` thay vì không có khoá;
  - `swap_turns`: `Extraction(domain='travel', …)` → `Extraction(start_date_undecided=True, …)`. Phía release đã tách classify (`TurnRoute`) khỏi extract, nên `Extraction` không còn `domain` và route lấy từ `ScriptedLlm.route`. Sửa này làm 3 test đổi món chạy lại được.
- `src/backend/tests/unit/agents/test_recsys_agent_integration.py` — sửa: `run_graph` đặt `start_date_asked: True` như helper của `test_itinerary_runtime`. Bước "hỏi ngày đi/số người/ngân sách trước khi lập lịch" của phía release làm graph dừng ở `NEEDS_CLARIFICATION` trước khi tới tool, nên 3 test in-process (grounding, RecSys chưa sẵn sàng, token giả) nhận 200 thay vì kết quả cần kiểm.
- `docs/spec/hop-dong-tich-hop-itinerary-assistant.md` — sửa: §2.5 dòng "Chỉ mời ở lượt đổi món" ghi rõ:
  - payload mọi lượt mang `llm_context`, gồm `previous_selection` (rỗng ở lượt đầu);
  - khi mời Similar thì khoá này chỉ giữ `productId`/`name`/`taxonomy`.
- `history/2026-09-29-fix-backend-ci-sau-merge-agent.md` — thêm: entry này.

## Quyết định

**Hai quyết định cũ va nhau khi merge, chọn theo PRD.**
- `history/2026-09-29-tool-similar-cho-agent.md` khoá "lượt đầu giữ nguyên bộ tool, prompt và bốn khoá payload".
- Phía release thì đưa `llm_context` vào mọi lượt gọi LLM, kể cả lập tool plan.
- `docs/prd/architecture.md` §3 ("Ngữ cảnh cho LLM") ghi rõ lập tool plan nhận cùng ngữ cảnh: lịch sử, chuyến đã chốt, sản phẩm đã cho xem, câu hỏi gần nhất. `docs/spec/agent/langgraph-nodes.md` dòng 28 ghi tương tự. Vì vậy payload lập plan mang `llm_context` ở mọi lượt.
- Phần của contract §2.5 vẫn giữ nguyên: tool Similar và `SIMILAR_HINT` chỉ có ở lượt đổi món; lượt đầu giữ nguyên bộ tool và system prompt.
- Không cần đề xuất PRD, vì đây là hiện thực đúng cả hai mục PRD đã chốt.

**Sửa phía code, không gỡ test.**
- Test của phía release (`test_conversation_history.py::test_tool_planner_receives_bounded_history`) và mọi test Similar đều giữ.
- Chỉ sửa ba chỗ trong test, đều vì test của phía bench viết trên API agent cũ:
  - hai assert khoá bộ khoá payload cũ;
  - `Extraction(domain=…)`;
  - thiếu `start_date_asked`.
- Nội dung kiểm tra của các test không bị nới.

## Kiểm tra

- Tái hiện CI trong Docker `python:3.11`:
  - môi trường: Linux, `pip install -r src/backend/requirements.txt`, đúng các bước của job `quality` trong `.github/workflows/backend-ci-cd.yml`;
  - mã nguồn: `git -c core.autocrlf=false archive`, tức LF như checkout của CI. Để `autocrlf=true` thì `bash -n` báo lỗi CRLF giả ở `scripts/`.
- **Trước khi sửa** (`HEAD` = `a129fa0`):
  - `validate_contract.py` PASS, `compileall` ok;
  - pytest **61 failed, 590 passed, 19 skipped**. Log có 45 lần `NameError: offered` và 12 lần `NameError: _bearer`;
  - sửa xong hai lỗi này, lượt chạy trung gian còn **6 failed**: 3 test đổi món (`Extraction.domain`) và 3 test in-process (thiếu `start_date_asked`), đã sửa như ở trên;
  - CI báo 48 failed, có lẽ vì chạy trên commit merge của PR.
- **Sau khi sửa** (`git stash create` → `git archive`, đúng nội dung sẽ commit):
  - `validate_contract.py`: PASS (88 schemas, 64 fixtures, CDP clone 12 schemas);
  - `compileall`: ok;
  - pytest `src/backend/tests`: **651 passed, 19 skipped**, 0 failed;
  - bước "Validate deployment scripts" (`bash -n` + `scripts/tests/test-backend-vm-cd-sync.sh`): passed.
- `pyflakes src/backend`: không còn tên chưa định nghĩa; chỉ còn các cảnh báo import thừa có sẵn.
- Không chạy được pytest bằng `.venv` local: Windows Application Control chặn DLL của `psycopg` binary.

## Còn lại / rủi ro

- Ai giải conflict tương tự giữa `release-mvp-*` và nhánh có `750ce43` thì nhớ hai chỗ này: `deps.conversation_owner` và `tool_planning.build_plan`.
- Chưa push; CI thật sẽ chạy lại khi push hoặc mở PR.
