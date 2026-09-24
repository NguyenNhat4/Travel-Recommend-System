# Golden dataset + runner tự động cho Itinerary Agent, sửa 2 lỗi agent tìm được

- Ngày: 2026-09-23
- Tác giả: nhatnm / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: agent, evaluation, docs

## Mục tiêu

Yêu cầu: tạo bộ golden dataset để đánh giá agent (`src/backend/app/api/v1/routes/assistant.py`), rồi
"tiếp tục hoàn thiện". `docs/prd/test-plan.md` §2.4 đòi bộ 50 prompt đo Tool Calling Accuracy ≥ 95%,
Grounding Rate 100%, Structured Output Integrity 100% — chưa ai làm. Bộ 12 case sẵn có
(`docs/spec/agent/evaluation-plan.md` §1–9) chạy tay trên fixture 50 sản phẩm, không chạm catalog thật.

Người dùng chốt trước khi code: catalog Postgres thật (`ITINERARY_DATA_MODE=http`), runner in-process
tự chấm, 50 case. Phục vụ FR-AGT-01..05, NFR-REL-01, NFR-SEC-01, test-plan §2.4. Không lệch PRD — không
cần đề xuất trong `docs/prd/update/`.

## File thay đổi

- `src/evaluation/datasets/itinerary_agent_golden.yaml` — thêm: 50 case (57 lượt), kỳ vọng theo bất
  biến, không khoá `productId`/tên sản phẩm.
- `src/evaluation/agent/golden.py` — thêm: runner in-process, 4 nhóm quy tắc chấm (A gate cứng, B cấu
  trúc lịch trình, C hotel rẻ nhất từ `candidates`, D case khai báo), `--only`/`--sweep`/`--repeat`,
  `--trace-project` (gửi trace lên LangSmith), biên bản `.md` + `.json` trong `src/evaluation/reports/`.
- `src/evaluation/agent/grounding.py` — thêm: hàm đối chiếu sản phẩm với `cdp.products`, tách từ
  `check_real_data_grounding.py`. Sửa khi tách: so `available::text` với `"true"` (bản cũ so `"t"`,
  làm mọi sản phẩm bị báo lệch DB); id không đúng định dạng UUID trả `None` thay vì crash.
- `src/evaluation/tests/check_real_data_grounding.py` — sửa: dùng `grounding.py`; kiểm thêm
  `searchResults`.
- `src/evaluation/tests/test_golden.py` — thêm: 37 unit test (không cần LLM/DB).
- `src/evaluation/agent/cli.py` — sửa: bỏ `run-scenarios`/`validate-metrics` (agent "lab" cũ); giữ
  `itinerary`.
- `src/evaluation/agent/scenarios.py`, `metrics.py`, `report.py` — xóa: chỉ `cli.py` import;
  `report.py` còn `TODO(student)` / "Day 08 Lab Report".
- `src/backend/app/application/itinerary/tool_contracts.py` — sửa: thêm `argument_names(name)`.
- `src/backend/app/agents/steps/tool_planning.py` — sửa: `validated_plan` bỏ tham số planner tự thêm
  mà hợp đồng tool không khai báo, thay vì để `normalize_arguments` huỷ cả plan (lỗi #1 dưới).
- `src/backend/app/agents/steps/prompts.py` — sửa: `EXTRACT_PROMPT` thêm quy tắc cho số người lớn
  tường minh không kèm trẻ em (lỗi #2 dưới).
- `src/backend/tests/unit/agents/test_itinerary_tools.py` — sửa: thêm test hồi quy
  `test_unknown_argument_from_planner_is_dropped_not_fatal`.
- `docs/spec/agent/evaluation-plan.md` — sửa: thêm §0 golden dataset; §0.1 ghi các lỗi đã tìm/sửa.
  Không sửa §1–9.
- `docs/spec/agent/golden-dataset.md` — thêm: cấu trúc case, bảng khoá `expect`, những gì runner tự kiểm,
  cách chọn độ chặt kỳ vọng, quy trình thêm case, xử lý khi case fail, giới hạn của schema.
- `docs/spec/agent/README.md` — sửa: mục lục + mục "Chạy đánh giá tự động (golden dataset)".
- `docs/plan/2026-09-23-golden-dataset-handoff.md` — thêm: file bàn giao cho agent/người làm tiếp.
- `src/evaluation/reports/eval-2026-09-23-golden.md` — thêm: biên bản lần chạy cuối.
- `history/2026-09-23-golden-dataset-itinerary-agent.md` — thêm: entry này.

Không thuộc task này: `src/backend/app/core/config.py` đã có thay đổi chưa commit (tăng timeout mặc
định lên 10s) từ trước khi bắt đầu — không đụng, không gộp vào entry.

## Quyết định

- **Runner in-process** giống `main.py:_itinerary_runtime`, để đọc được `intent`/`tool_plan`/
  `candidates`/`events` — gọi qua HTTP không đo được Tool Calling Accuracy hay quy tắc hotel rẻ nhất.
- **Kỳ vọng theo bất biến**, không khoá sản phẩm: catalog đổi theo mỗi lần seed. `--sweep` tự sinh case
  cho mọi điểm đến từ `GET /api/v1/destinations`.
- **Tool Calling Accuracy suy từ response**: thiếu field → không gọi tool; COMPLETED/FALLBACK/
  NO_RESULTS/UNSUPPORTED_DESTINATION → phải gọi; VALIDATION_ERROR → không gọi;
  `constraint_clarification` loại khỏi mẫu số.
- **Lỗi #1 — planner bịa `excludeProducts`.** Khi `constraints.exclude_products` khác rỗng, planner
  thêm `excludeProducts` vào `search_products`; `SearchRequest` có `additionalProperties: false` nên
  `normalize_arguments` ném `INVALID_ARGUMENTS` trong `validated_plan`, huỷ cả plan → 503
  `LLM_UNAVAILABLE` cho lượt "rút ngắn còn 2 ngày" (4/4 lần). Sửa bằng cách lọc khoá theo
  `argument_names` trước khi validate. Không mất hành vi: sản phẩm bị loại đã được lọc sau truy xuất
  ở `application/itinerary/retrieval.py:45`. Chọn sửa tất định ở code thay vì dặn thêm trong prompt vì
  LLM vẫn có thể bịa khoá khác. Tool không có trong hợp đồng vẫn bị từ chối (`TOOL_NOT_ALLOWED`).
- **Lỗi #2 — mất `party` khi nói "4 người lớn".** Đã kiểm chứng giả thuyết trước khi sửa: giả thuyết
  đầu ("children bắt buộc nên LLM bỏ trống") **sai** — LLM trích đúng `adults=4` nhưng gán
  `type=FAMILY_WITH_KIDS, children=0`; `domain/itinerary/normalization.py:normalize_party` (chủ ý chặn
  số người do LLM đoán khi user chỉ nói "gia đình") xoá cả `party`. Giữ nguyên guard đó, sửa gốc ở prompt:
  số người lớn không kèm trẻ em → SOLO/COUPLE/FRIENDS, không bao giờ FAMILY_WITH_KIDS khi children=0.
  Lần sửa prompt thứ nhất (mô tả chung) không đủ, LLM vẫn gán FAMILY_WITH_KIDS; lần hai nêu rõ quy tắc
  chọn type mới có tác dụng.
- **G-042 là lỗi của runner, không phải agent.** Response lỗi có thể tiếp tục (422
  `UNSUPPORTED_DESTINATION`) đặt `conversationId` trong `error.details`; runner chỉ đọc cấp ngoài cùng
  nên lượt 2 mở hội thoại mới và mất `days`. Thêm `conversation_of()` đọc cả hai chỗ, giống frontend.
- **G-046 (câu hỏi thời tiết) nới về bất biến "không gọi tool".** Trace cho thấy LLM xếp vào
  `conversation` → 200 `NEEDS_CLARIFICATION` (5/5 lần gần nhất), có lần khác xếp `out_of_domain` → 400.
  PRD không quy định nhánh nào; điều phải giữ là không truy xuất sản phẩm.
- **`--trace-project` bật tracing ngay trong runner.** Người dùng hỏi vì sao dashboard LangSmith
  (project dev `nhat-23-9`) báo P50 0,03s và chỉ 7.814 token. Đọc thẳng 145 root run: ~140 là trace
  0 token ~30ms từ `pytest src/backend/tests` (`TestClient` chạy `lifespan` → `_forward_langsmith_env`
  đọc `.env` thật), 3 trace thật (5.616 + 2.198 = 7.814 token), và **không** lượt golden nào — runner
  không qua `lifespan` nên chưa từng gửi trace. Thêm `enable_tracing` (đặt 4 biến `LANGSMITH_*` với
  project do người dùng chọn) và `trace_config` (tên `G-xxx#n <câu>`, tag `golden`/id/category,
  metadata `case_id`, `turn`, `fr`, `request_id`); cuối lượt chạy gọi `wait_for_all_tracers()`.
- **G-032 (Bangkok) giữ kỳ vọng chặt 422** dù 4/5: luồng `UNSUPPORTED_DESTINATION` có spec
  (`response-and-errors.md`), lượt fail là tín hiệu chất lượng thật chứ không phải kỳ vọng sai.

## Kiểm tra

- `pytest src/evaluation/tests/test_golden.py`: 37 passed.
- `pytest src/backend/tests/unit/agents`: 84 passed (gồm test hồi quy mới).
- `pytest src/backend/tests` sau mọi thay đổi: 180 passed, 2 skipped.
- Kiểm chứng từng sửa đổi bằng LLM thật:
  - Lỗi #1: sau khi sửa, G-039/040/043/044 pass ở lần chạy toàn bộ.
  - Lỗi #2: "Hạ Long 2 ngày cho 4 người lớn" → `FRIENDS, adults=4` 3/3; "Đà Nẵng 3 ngày cho gia đình"
    vẫn `party=None` 3/3 (guard không bị phá); "2 người lớn 1 trẻ em" vẫn `FAMILY_WITH_KIDS` 3/3.
    G-022 pass 5/5 với `--repeat 5`.
  - G-042: pass 3/3 chạy riêng sau khi sửa runner.
- Lần chạy cuối (`--sweep`, 50 case + 35 điểm đến = 92 lượt, `gpt-4o-mini`, catalog 10.320 sản phẩm):
  **Grounding 100%, Structured Output 100%, Tool Calling 100% (86 lượt)**, PASS 90/92, p95 4.755ms.
  Hai lượt fail: G-032 (Bangkok → NEEDS_CLARIFICATION) và G-047 (đặt phòng → NEEDS_CLARIFICATION) —
  cả hai là nhiễu phân loại của `classify`, đã pass ở các lần chạy khác.
- Chạy lại `--sweep --trace-project claude-golden` (người dùng yêu cầu): cùng kết quả 3 chỉ số 100%,
  PASS 90/92 (G-032, G-047 như trên), latency runner p50 4.180ms / p95 6.007ms / max 7.626ms. Đọc lại
  project `claude-golden` bằng LangSmith SDK: 93 root run (92 lượt + 1 lượt thử `--only G-003`), 0 lỗi,
  261.823 token (trung vị 2.889/lượt, không lượt nào 0 token), p50 4,18s — khớp runner. Lượt chậm nhất
  (8,3s): `classify` 4,76s + `tool` 3,23s. Biên bản commit là của lần chạy này.
- Chạy lại lần nữa `--sweep --trace-project claude-golden` (người dùng yêu cầu; biên bản commit là của
  lần này): 3 chỉ số 100%, PASS 91/92, runner p50 4.392ms / p95 5.564ms / max 7.328ms. G-032, G-047
  pass lần này. Fail mới: G-013 (`tphcm 2 ngày` → `NEEDS_CLARIFICATION`, destination chưa chuẩn hoá).
  Lặp riêng 8 lần: 7/8 `COMPLETED` đúng `TP. Hồ Chí Minh`, 1/8 `clarification_reason=conflict` dù LLM
  trả `conflict=False` — nghi `_days_from_end_date` (LLM trích `end_date` lệch với `days`), chưa kiểm.
- Không chạy `validate_contract.py`: không chạm `src/shared/contracts/` hay `src/shared/mocks/`.

## Còn lại / rủi ro

- **Nhiễu phân loại của `classify`** (G-032 ~1/5, G-047 thỉnh thoảng): cùng câu, LLM lúc chọn
  `side_effect`/travel-unsupported, lúc chọn travel-thiếu-field. Chưa xử lý. Hướng có thể: few-shot
  trong `EXTRACT_PROMPT`, hoặc chạy `--repeat` định kỳ để theo dõi tỷ lệ. Cần người dùng chọn hướng.
- Latency p50 4,2s, p95 ~6s — đuôi vượt mục tiêu 5s (không gate); dồn vào `classify` và `tool`.
- `pytest src/backend/tests` vẫn gửi trace giả lên project LangSmith trong `.env` khi
  `LANGSMITH_TRACING=true` — chưa chặn (đề xuất ép tắt trong `conftest.py`).
- `Scenario`/`initial_state`/`Route` trong `agents/state.py` chỉ phục vụ harness lab đã xoá — có thể
  dọn, chưa làm vì ngoài phạm vi.
- Bộ 12 case chạy tay (`evaluation-plan.md` §1–9) vẫn dùng cho fixture; chưa hợp nhất.
