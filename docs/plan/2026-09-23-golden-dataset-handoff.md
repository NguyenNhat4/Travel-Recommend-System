# Bàn giao: golden dataset Itinerary Agent (2026-09-23)

Phục vụ: FR-AGT-01..05, NFR-REL-01, NFR-SEC-01 (`docs/prd/requirements.md`), `docs/prd/test-plan.md` §2.4.
Nhánh: `feat/agent`. Trạng thái: **đã xong và đã commit** trên `feat/agent` (commit `feat(evaluation): golden dataset ...`).

Đọc theo thứ tự nếu tiếp tục việc này:

1. `AGENTS.md` (quy tắc repo — bắt buộc).
2. File này.
3. `history/2026-09-23-golden-dataset-itinerary-agent.md` — danh sách file, quyết định, bằng chứng.
4. `docs/spec/agent/evaluation-plan.md` §0 — luật chấm; `docs/spec/agent/golden-dataset.md` — cấu trúc
   case và cách bổ sung.
5. `src/evaluation/reports/eval-2026-09-23-golden.md` — biên bản lần chạy cuối.

## 1. Đã làm

| Việc | File |
|---|---|
| Dataset 50 case (57 lượt), kỳ vọng theo bất biến | `src/evaluation/datasets/itinerary_agent_golden.yaml` |
| Runner chấm tự động (in-process, `--only`/`--sweep`/`--repeat`) | `src/evaluation/agent/golden.py` |
| Đối chiếu sản phẩm với `cdp.products` (dùng chung) | `src/evaluation/agent/grounding.py` |
| 37 unit test cho bộ chấm | `src/evaluation/tests/test_golden.py` |
| Xoá harness lab cũ (`scenarios.py`, `metrics.py`, `report.py`, 2 lệnh CLI) | `src/evaluation/agent/` |
| Sửa lỗi agent #1: planner bịa tham số `excludeProducts` → 503 ở lượt đa turn | `agents/steps/tool_planning.py`, `application/itinerary/tool_contracts.py`, test hồi quy trong `tests/unit/agents/test_itinerary_tools.py` |
| Sửa lỗi agent #2: mất `party` khi nói "N người lớn" | `agents/steps/prompts.py` (`EXTRACT_PROMPT`) |
| Sửa lỗi runner: `conversationId` của lỗi 422 nằm trong `error.details` | `src/evaluation/agent/golden.py` (`conversation_of`) |
| Tài liệu | `docs/spec/agent/evaluation-plan.md` §0, `docs/spec/agent/golden-dataset.md`, `docs/spec/agent/README.md` |

## 2. Kết quả lần chạy cuối

`--sweep` (50 case + 35 điểm đến = 92 lượt), `gpt-4o-mini`, catalog 10.320 sản phẩm:

- Grounding Rate **100%**, Structured Output Integrity **100%**, Tool Calling Accuracy **100%** (86 lượt).
- (Lần chạy trước) PASS 90/92. Hai lượt fail là nhiễu phân loại của `classify`: G-032 (Bangkok → `NEEDS_CLARIFICATION`
  thay vì 422, ~1/5 lần) và G-047 (đặt phòng → `NEEDS_CLARIFICATION` thay vì 400, thỉnh thoảng).
- Latency p50 4,2s, p95 ~6s, max 7,6s (mục tiêu < 5s, không gate). Lần chạy cuối có trace ở LangSmith
  project `claude-golden` (93 root run = 92 lượt + 1 lượt thử); p50 LangSmith 4,18s khớp runner.
  Thời gian dồn vào `classify` (LLM) và `tool` (LLM lập plan + Search/Recommendation).
- Test: `src/evaluation/tests/test_golden.py` 37 passed; `src/backend/tests/unit/agents` 84 passed;
  toàn bộ `src/backend/tests` 180 passed, 2 skipped.

## 3. Cách chạy

```bash
docker compose up -d --wait postgres
.venv/bin/uvicorn src.backend.app.main:app --port 8000     # .env đã có ITINERARY_DATA_MODE=http
.venv/bin/python -m src.evaluation.agent.golden            # 50 case, ~4 phút
.venv/bin/python -m src.evaluation.agent.golden --sweep    # + 35 điểm đến, ~6 phút
.venv/bin/python -m src.evaluation.agent.golden --only G-032,G-047 --repeat 5   # đo độ ổn định
.venv/bin/python -m src.evaluation.agent.golden --sweep --trace-project claude-golden  # kèm trace LangSmith
.venv/bin/python -m pytest src/evaluation/tests/test_golden.py -q
```

Backend phải khởi động xong recsys (log `startup.recsys.index.load.ready`, mất 1–2 phút); nếu Postgres
tắt thì recsys bị tắt và mọi case ra sai. Mỗi lần chạy ghi đè `src/evaluation/reports/eval-<ngày>-golden.{md,json}`.

## 4. Việc còn lại (chưa ai nhận)

1. **Nhiễu phân loại của `classify`** (G-032, G-047). Cần người dùng chọn hướng: few-shot trong
   `EXTRACT_PROMPT` (`src/backend/app/agents/steps/prompts.py`) hay chấp nhận và theo dõi tỷ lệ bằng
   `--repeat`. Không tự nới kỳ vọng G-032/G-047 — hai luồng này có spec.
2. `src/backend/app/core/config.py` còn thay đổi timeout chưa commit — có từ trước, không thuộc việc này;
   hỏi người dùng trước khi commit hay bỏ. Không commit `.claude/`.
3. Dọn `Scenario`/`initial_state`/`Route` trong `src/backend/app/agents/state.py` (chỉ phục vụ harness lab
   đã xoá) — ngoài phạm vi, cần hỏi người dùng.
4. Latency p50 4,2s, p95 ~6s — vượt mục tiêu 5s ở đuôi, chưa xử lý.
5. Chặn pytest gửi trace thật lên LangSmith (ví dụ ép `LANGSMITH_TRACING=false` trong `conftest.py`).

## 5. Bẫy đã gặp (đừng lặp lại)

- Giả thuyết lỗi #2 ban đầu ("children bắt buộc nên LLM bỏ trống party") **sai**; nguyên nhân thật là
  `normalize_party` xoá party khi `FAMILY_WITH_KIDS` + `children=0`. Luôn trace state trước khi sửa.
- Dashboard LangSmith của project dev (`nhat-23-9`) bị lẫn ~140 trace giả 0 token, ~30ms từ
  `pytest src/backend/tests`: `TestClient` chạy `lifespan` → `_forward_langsmith_env` đọc `.env` thật
  (`LANGSMITH_TRACING=true`). Đừng đọc P50/token của project đó như số đo agent. Chưa chặn (việc còn lại).
- G-042 trông như lỗi agent nhưng là lỗi runner. Nếu case đa lượt fail ở lượt 2, kiểm `conversationId`
  runner truyền vào trước.
- Câu hỏi ngoài phạm vi có thể ra 400 (`out_of_domain`) hoặc 200 (`conversation`) — đều hợp lệ theo code;
  G-046 chỉ khoá "không gọi tool".
