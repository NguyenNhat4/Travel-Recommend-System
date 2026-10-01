# Merge origin/release-mvp-v2 vào feat/itinerary-agent-guardrails

- Ngày: 2026-09-29
- Tác giả: Nguyễn Minh Nhật / Claude Sonnet 5
- Nhánh: feat/itinerary-agent-guardrails
- Trạng thái: hoàn thành
- Phạm vi: agent, backend, frontend, docs, evaluation

## Mục tiêu

Người dùng yêu cầu kéo code mới nhất từ `release-mvp-v2` (53 commit, gồm tính năng agent gọi
Search/Recommendation/Similar trong tiến trình + contract 1.8.0) về nhánh đang làm. Trước khi merge,
working tree có 29 dòng thay đổi chưa commit (WIP `TripDetailsForm` + đề xuất vòng ReAct) nên đã `git stash
push -u` để giữ nguyên trạng, merge trên tree sạch, xong mới pop lại — tránh trộn lẫn hai việc không liên
quan trong cùng merge commit.

## File thay đổi

- 283 file (39.211 dòng thêm, 571 dòng xoá) từ merge; phần lớn là nội dung tự động từ `origin/release-mvp-v2`
  (contract 1.8.0, CI mới, bench search/recsys, in-process tool calling).
- 6 file có conflict thật, resolve thủ công (chi tiết ở mục Quyết định):
  `docs/spec/agent/README.md`, `docs/spec/agent/langgraph-nodes.md`, `docs/spec/agent/state-fields.md`,
  `docs/spec/agent/evaluation-plan.md` (giữ xoá — đã xoá ở commit `6ce92b2`),
  `src/backend/app/agents/tools/itinerary_gateway.py`, `src/backend/app/application/itinerary/retrieval.py`.
- `src/backend/tests/unit/agents/test_itinerary_tools.py` — sửa: 6 assertion trong `SimilarEvaluationTests`
  đổi từ tuple `(evaluated['evaluation_result'], evaluated['decision'])` sang chỉ `evaluated['decision']` —
  field `evaluation_result` đã bị gộp vào `decision` ở đợt refactor field-review.md (2026-09-28) trên nhánh
  này, còn test mới (upstream, auto-merge sạch không conflict) viết cho state shape cũ.
- `src/backend/tests/unit/agents/test_itinerary_runtime.py` — xoá: một test
  (`test_second_round_of_missing_destination_or_days_offers_a_prefilled_form`) bị lọt vào commit `6ce92b2`
  do sự cố thao tác git (xem mục Sự cố bên dưới); implementation của nó (`clarificationForm`) không nằm
  trong commit nào, chỉ có trong phần đã stash, nên test đứng một mình và fail. Xoá tạm; sẽ quay lại cùng
  lúc với implementation khi người dùng hoàn thiện tính năng `TripDetailsForm`.
- `docs/spec/agent/golden-run.md`, `docs/spec/agent/golden-dataset-how-to-add-more-case.md` — sửa thêm:
  sau khi merge xác nhận dataset thật có 76 case (không phải 14 như tài liệu mô tả), sửa các câu khẳng định
  sai; xem mục "Phát hiện ngoài phạm vi" bên dưới.

## Sự cố trong lúc thao tác (tự phát hiện)

Ở commit `6ce92b2` (trước merge), tôi dùng `git apply --cached` để tách một hunk ra khỏi file có 2 thay đổi
không liên quan (`test_itinerary_runtime.py`: hunk ngân sách của tôi + hunk `TripDetailsForm` của việc khác),
nhưng sau đó dùng `git commit -m ... -- <pathspec liệt kê file>`. `git commit <pathspec>` lấy nguyên nội dung
**working tree** của các path đó, không chỉ phần đã `git add`, nên hunk `TripDetailsForm` (chưa từng được
add) vẫn lọt vào commit `6ce92b2` dù tôi định tách riêng. Hệ quả: một test đứng một mình không có
implementation, phát hiện khi chạy lại toàn bộ suite sau merge (615 test, 1 fail). Đã xoá test đó khỏi
`test_itinerary_runtime.py` ở merge commit này (mục File thay đổi). Bài học: dùng `git commit` không kèm
pathspec sau khi `git add` chính xác, thay vì `git commit -- <path>`.

## Quyết định

- **`docs/spec/agent/evaluation-plan.md` (DU: đã xoá ở HEAD, upstream vẫn sửa).** Giữ xoá. Diff của upstream
  từ merge-base chỉ đổi "14 case" ngược lại thành "75 case" ở một dòng nhưng bỏ sót các dòng khác (vẫn tự
  mâu thuẫn 14/75 trong cùng file, và vẫn giữ nguyên claim sai về `priceUnit=UNKNOWN` cho cả 50 sản phẩm) —
  không có nội dung mới đáng giữ so với bản đã gộp vào `golden-run.md` ở commit trước.
- **`itinerary_gateway.py`, `retrieval.py` (code, 2 file).** Giữ cả hai phía: kiểu dữ liệu có tên
  (`ToolCall`/`ToolDefinition`/`ToolResult`, `Product`/`TripIntent`/`Constraints`) từ nhánh này, hành vi mới
  từ upstream (lọc `definitions()` theo tool đã nối port, logging mỗi lời gọi tool qua `current_request_id`,
  helper `_off_destination` dùng chung cho lọc điểm đến lẫn lọc gợi ý Similar). Xác minh bằng cách đọc code
  xung quanh conflict marker thay vì đoán từ text diff — ví dụ dòng dùng biến `name` ở `execute()` chỉ có ở
  nhánh upstream nhưng phần thân hàm bên dưới (đã auto-merge, không conflict) đã đọc biến đó, nên phải giữ.
- **3 file doc agent (`README.md`, `langgraph-nodes.md`, `state-fields.md`).** Bên nào mô tả đúng **code sau
  khi merge** thì giữ, không mặc định lấy HEAD hay upstream. Xác minh bằng cách đối chiếu ngược lại code:
    - Đếm node thật trong `graph.py` (`add_node`) ra 11 → giữ "mười một node" của HEAD, bỏ "mười node" của
      upstream (stale, từ trước khi node `dead_letter` tách riêng).
    - `git diff <merge-base> origin/release-mvp-v2 -- state.py` và `-- nodes.py` đều rỗng: upstream chưa hề
      đụng hai file này. Field `errors`/`pending_question`/`llm_used`/`route` trong mô tả của upstream chỉ
      là tàn dư trước đợt dọn field-review.md (2026-09-28) của nhánh này, không phải tính năng mới — xác
      nhận bằng `grep` không tìm thấy `state['errors']`/`TRANSIENT_TOOL_FAILURE` ở đâu trong code hiện tại.
      Bỏ hẳn các dòng này.
    - Ngược lại, `previous_selection` dùng làm whitelist cho `get_similar_products` và `tool_plan` bị chặn
      tối đa 5 lời gọi (2 Similar) là tính năng thật, xác nhận bằng `grep` ra `_allowed_similar_calls`,
      `MAX_CALLS`, `_pop_last_similar` trong `tool_planning.py` (file này auto-merge sạch, thuộc về upstream)
      — giữ các dòng mô tả tương ứng của upstream, gộp vào bảng của HEAD.
- **Không đụng bộ golden dataset (theo yêu cầu người dùng).** `src/evaluation/tests/test_golden.py` giả định
  đúng 14 case/category nhưng `itinerary_agent_golden.yaml` có 76 case — xác minh bằng `git worktree` tại
  commit `6ce92b2` (trước merge của tôi): 3 test đã fail y hệt từ trước, không phải regression do merge gây
  ra. Người dùng xác nhận bộ golden test này "outdate", không cần sửa/chạy trong task này. `pytest
  src/evaluation` vẫn còn 3 test FAIL sau merge — cố ý để nguyên, không phải bỏ sót.

## Phát hiện ngoài phạm vi (đã sửa nhẹ vì tiện thể, không phải yêu cầu chính)

Trong lúc đối chiếu số case thật, phát hiện `docs/spec/agent/golden-run.md` (do chính tôi viết ở commit
`6ce92b2`, sao chép nguyên văn từ `evaluation-plan.md` cũ) khẳng định sai "14 case" trong khi
`itinerary_agent_golden.yaml` thật luôn có ≥ 75 case kể từ trước khi tôi bắt đầu phiên này — bộ rút gọn 14
case từng có (`history/2026-09-25-rut-gon-golden-14-case.md`) nhưng chưa bao giờ có mặt trong file dataset
mà nhánh này kế thừa, nhiều khả năng bị một lần merge/rebase trước đó ghi đè. Sửa các câu khẳng định số case
trong `golden-run.md` và `golden-dataset-how-to-add-more-case.md` để khớp thực tế 76 case, có ghi chú đối
chiếu ngày 2026-09-29 và trỏ tới lịch sử. Không sửa `test_golden.py` hay dataset — nằm ngoài phạm vi người
dùng cho phép ở task này.

## Kiểm tra

- `.venv/bin/python -m pytest src/backend/tests/unit src/backend/tests/architecture -q` → **615 passed**.
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python src/shared/contracts/tests/validate_contract.py` → **PASS**
  (88 schemas, 64 fixtures — tăng từ 62 do contract 1.8.0 của upstream).
- `cd src/frontend && npx tsc --noEmit` → sạch.
- `cd src/frontend && npm test` → **135 passed** (23 file; `tripDetailsForm.test.tsx` tạm vắng mặt vì đang
  nằm trong stash, không phải bị xoá).
- `.venv/bin/python -m pytest src/evaluation/tests/test_golden.py -q` → **3 failed, 49 passed** — **cố ý để
  nguyên** theo quyết định của người dùng (mục Quyết định).

## Còn lại / rủi ro

- Sau `git stash pop`, phần WIP `TripDetailsForm` + đề xuất ReAct loop sẽ nằm trên nền code mới; có thể có
  conflict nhỏ giữa stash và merge (ví dụ `docs/spec/agent/golden-dataset-how-to-add-more-case.md` vừa bị cả
  hai bên chạm). Cần kiểm lại sau khi pop.
- 3 test golden 14-case vẫn fail, cố ý theo yêu cầu người dùng — chưa có quyết định xử lý dứt điểm (sửa test
  theo 76 case thật, hay khôi phục bộ rút gọn). Để lại cho một task riêng.
- Không kiểm tra 283 file thay đổi một cách chi tiết từng dòng — dựa vào full test suite (backend +
  frontend + contract) làm lưới an toàn chính, cộng đối chiếu code cho 6 file có conflict thật.
