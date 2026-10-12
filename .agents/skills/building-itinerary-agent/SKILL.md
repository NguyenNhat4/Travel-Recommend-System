---
name: building-itinerary-agent
description: "Quy trình sửa, tune và đánh giá Itinerary Agent của V-OTA (LangGraph trong src/backend/app/agents, application/itinerary, domain/itinerary) và phần widget trợ lý hiển thị kết quả (src/frontend/src/features/itinerary/widget). Dùng khi thêm hoặc sửa node, prompt, tool, routing, guardrail, lời diễn giải (narrate), compose, grounding, golden dataset, trace LangSmith, hoặc thẻ/lịch trình/bản đồ trong widget. Từ khoá: itinerary agent, trợ lý lịch trình, LangGraph, node, prompt, narrate, compose, tool calling, grounding, golden, eval, assistant widget."
metadata:
  owner: nhatnm
  version: "1.1"
---

# Xây và sửa Itinerary Agent

Skill này chỉ là **quy trình**. Quy tắc nằm ở `AGENTS.md` (đọc tài liệu §1, lịch sử §5, đề xuất lệch PRD §8), bản đồ
code và invariant nằm ở `docs/spec/agent/working-context.md`. Khi lệch nhau, hai file đó thắng skill này.

## Quy trình

Chép checklist vào câu trả lời và đánh dấu khi xong từng bước:

```
Itinerary agent task:
- [ ] 1. Nạp context: AGENTS.md §1 + working-context.md §1 và đúng một hàng ở §2
- [ ] 2. Tái hiện bằng bằng chứng thật (trace, golden case, giá trị thô)
- [ ] 3. Chọn đúng lớp; LLM hiểu câu, code kiểm dữ liệu và phạm vi
- [ ] 4. Có test hoặc golden case fail trước khi sửa
- [ ] 5. Sửa và tự kiểm invariant
- [ ] 6. Chạy lệnh kiểm tra, ghi số thật kèm tầng bằng chứng
- [ ] 7. Docs, history; lệch PRD thì đề xuất rồi dừng
```

**1. Nạp context.** Ghi cho người dùng danh sách file đã đọc và mã FR/NFR theo AGENTS.md §1.3 trước lần sửa code đầu.

**2. Tái hiện bằng bằng chứng.**
- Lỗi đến từ đầu ra LLM: lấy giá trị thô ở chỗ nó bị từ chối trước khi sửa. Dùng trace LangSmith của đúng lượt
  (`docs/spec/agent/README.md` mục LangSmith), hoặc một dòng log tạm rồi gỡ.
- Lỗi chập chờn nghĩa là nguyên nhân không tất định. Đo bằng `--repeat`, đừng sửa theo giả thuyết đọc từ code.

**3. Chọn lớp** (chi tiết: working-context.md §2, §4):

| Triệu chứng | Sửa ở (dưới `src/backend/app/`, trừ khi ghi khác) |
|---|---|
| Hiểu sai ý, hỏi lại sai, giọng văn | `agents/steps/prompts.py` và step của node (`classification.py`, `conversation.py`, `narration.py`) |
| Ngày, tổng tiền, xếp lịch, lọc ứng viên | `domain/itinerary/` (hàm thuần, unit test) |
| Tool sai tham số hoặc thiếu dữ liệu | `agents/steps/tool_planning.py`, `agents/tools/itinerary_gateway.py`, `application/itinerary/` |
| Hình dạng request/response | Fragment OpenAPI trong `src/shared/contracts/` **trước**, rồi mới code |
| Hiển thị trong widget | `src/frontend/src/features/itinerary/widget/` |

Luật code dành cho tiền, ngày, grounding, an toàn và phạm vi thực thi. Hiểu câu sửa bằng prompt/ngữ cảnh và case
trong bộ đo; không vá bằng regex hay bảng từ khoá. Sau cờ orchestrator, LLM quyết hành động/việc/phạm vi/chọn thẻ và
viết lời, code thực thi qua port và gác cổng; nhánh lập lịch/narrate giữ nguyên (PRD architecture §3).

**4. Test trước.**
- Luật mới hoặc sửa luật: viết unit test cạnh test sẵn có.
- Hành vi end-to-end: thêm golden case theo [references/eval-loop.md](references/eval-loop.md).
- Test hoặc case phải fail trên code cũ.

**5. Invariant.** Đọc working-context.md §6 và PRD `architecture.md` §3, rồi tự trả lời trước khi bàn giao:
- Mọi `productId`, tên, giá, ảnh hiển thị đều đến từ kết quả tool, và widget chỉ lấy chúng từ `product`?
- Orchestrator chỉ dùng `[Tên](#n)` và placeholder từ bản rút gọn lượt này, code đổi thành link canonical; số so mốc có job?
- `compose` vẫn tất định và mọi nhánh đi qua `finalize`?
- Nhánh lập lịch chỉ gọi tool khi đã đồng ý và đủ trường bắt buộc; khám phá được gọi khi chưa có số ngày?
- Không log prompt có secret hay JWT?

**6. Kiểm tra** (từ repo root; chỉ chạy dòng thuộc phạm vi thay đổi):

```bash
.venv/bin/python -m pytest -q src/backend/tests/unit/agents src/backend/tests/unit/domain
.venv/bin/python -m pytest -q src/backend/tests                                      # trước khi bàn giao
PYTHONDONTWRITEBYTECODE=1 python3 src/shared/contracts/tests/validate_contract.py   # đổi contract/mock
.venv/bin/python -m pytest -q src/evaluation/tests/test_golden.py                  # sửa dataset golden
.venv/bin/python -m src.evaluation.agent.golden --only TC-NN                     # LLM thật: docs/spec/agent/golden-run.md
cd src/frontend && node_modules/.bin/vitest run && node_modules/.bin/tsc --noEmit  # sửa widget
```

Báo kết quả theo đúng tầng bằng chứng (working-context.md §5C): fixture/tất định, backend local + Postgres, LLM thật,
latency. `node outcome=completed` không có nghĩa là PASS.

**7. Bàn giao.**
- Entry `history/` theo AGENTS.md §5.
- Cập nhật spec hoặc docs khi quy ước đổi.
- Thay đổi lệch PRD thì tạo đề xuất trong `docs/prd/update/` và **dừng** chờ người dùng chốt (AGENTS.md §8).

## Tham khảo

- [references/eval-loop.md](references/eval-loop.md): biến lỗi thật thành golden case, đo pass^k, chạy cả bộ, ghi biên bản.
- [references/industry-patterns.md](references/industry-patterns.md): thực hành ngành khi xây agent và chỗ chúng nằm
  trong repo. Đọc khi thêm node, tool, bước LLM hoặc kiểu hiển thị mới.
