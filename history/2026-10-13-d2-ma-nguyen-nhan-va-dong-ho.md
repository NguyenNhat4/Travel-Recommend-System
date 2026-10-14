# D2: mã nguyên nhân cho câu dự phòng, đồng hồ tiêm được, snapshot từ chối lượt không phát lại được

- Ngày: 2026-10-13
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: agent, backend (test)

## Mục tiêu

Bước D2 của `docs/plan/2026-10-12-go-luong-cu-orchestrator-chinh.md`, là refactor runtime không đổi hành vi. Mục đích:
- Phân biệt hết giờ, quá giờ của model hoặc tool với trần vòng và trần tool.
- Cho snapshot ghi và phát lại orchestrator không phụ thuộc tốc độ mạng hay model. Đây là điều kiện để ghi baseline
  trên orchestrator ở D3.

Phục vụ FR-AGT-06, FR-AGT-07, NFR-REL-01. Đã đọc tài liệu và ghi xác nhận AGENTS.md §1.3 trong phiên (xem
`2026-10-13-d0-danh-dau-luong-cu.md`).

## File thay đổi

- `src/backend/app/agents/clock.py` — thêm: `now()`, chỗ đọc giờ duy nhất của ngân sách thời gian.
- `src/backend/app/agents/steps/limits.py` — thêm: sáu mã nguyên nhân, tập `UNREPLAYABLE`, `model_failure(exc)`.
- `src/backend/app/agents/steps/orchestration.py` — sửa:
  - Thêm `limit_reason()` dùng chung cho `orchestrate`, `run_jobs`, `gatekeep`; điều kiện tương đương bản cũ.
  - Event có `reason`; `turn_limit_reason`; `failed_reasons`.
  - Log `itinerary.turn_limit`.
  - Đọc giờ qua `clock`.
- `src/backend/app/agents/steps/jobs.py` — sửa:
  - `BudgetTools` gắn `reason` (`TOOL_LIMIT`, `TIME_LIMIT`, `TOOL_TIMEOUT`); vẫn ném đúng kiểu lỗi cũ.
  - Job hỏng ghi `reason`.
  - Đọc giờ qua `clock`.
- `src/backend/app/agents/nodes.py` — sửa: `started_at`, `latency_ms` đọc qua `clock`; `_llm_failed` gắn `reason`.
- `src/backend/app/agents/state.py` — sửa: thêm `turn_limit_reason`.
- `src/backend/app/agents/steps/phase.py` — sửa: `turn_limit_reason: None` trong mặc định của lượt orchestrator.
- `src/backend/tests/unit/agents/behavior_snapshot/harness.py` — sửa:
  - Đồng hồ đứng yên.
  - Graph theo mặc định cờ trong code; orchestrator có ngân sách 600 giây.
  - `CassetteLlm(model=...)`.
  - Ghi nhận lời gọi thật hỏng khi ghi; `unreplayable()`.
- `src/backend/tests/unit/agents/behavior_snapshot/record.py` — sửa: ghi cả model orchestrator; `rejected()`; từ chối và
  ghi lại tối đa 3 lần; không lưu snapshot khi còn kịch bản bị từ chối.
- `src/backend/tests/unit/agents/test_turn_limits.py` — thêm: 20 ca, mỗi nguyên nhân một ca.
- `docs/plan/2026-10-12-go-luong-cu-orchestrator-chinh.md` — sửa: mục D2 ghi đúng cách đã làm, trạng thái xong.
- `history/2026-10-13-d2-ma-nguyen-nhan-va-dong-ho.md` — thêm: entry này.

## Quyết định

- Không đổi chữ của `message`, node path hay mã lỗi trả ra ngoài. Mã nằm ở metadata event (snapshot chỉ so `node` và
  `message`), ở `turn_limit_reason` và ở log. `turn_limit_reason` không vào payload LLM, nên cassette không lệch.
- Quá hạn của tool vẫn là `TimeoutError` (gắn thêm `reason`), không đổi thành `ToolError`. Lý do: các nơi gọi (`_one`,
  `flight_options`, `_origin_routes`) đang xử lý theo kiểu lỗi; đổi kiểu là đổi hành vi.
- Lệch so với plan cũ: không gắn mã ở 13 chỗ `wait_for` của nhánh lập lịch. Lúc ghi snapshot, cassette tự ghi nhận lời gọi
  thật hỏng, nên phủ mọi chỗ gọi mà không sửa runtime ở đó. Đã sửa plan cho khớp.
- Harness theo mặc định cờ trong code, không theo `.env`: `.env` của máy dev đang `on`, CI không có `.env`.
- Thêm log `itinerary.turn_limit` để D1, D6 đọc được nguyên nhân dừng sớm theo `requestId`, vì SSE không mang metadata
  event.

## Kiểm tra

- `.venv/bin/python -m pytest -q src/backend/tests/unit/agents/test_turn_limits.py` → **20 passed**.
- `WEAVIATE_URL=http://127.0.0.1:9 SEARCH_PREWARM=false HF_HUB_OFFLINE=1 LANGSMITH_TRACING=false .venv/bin/python -m pytest
  -q -p no:cacheprovider src/backend/tests/unit/agents src/backend/tests/unit/domain src/backend/tests/architecture` →
  **2132 passed** (19,73 s).
- `.../test_behavior_snapshot.py` → **4 passed**: snapshot luồng cũ phát lại khớp, không ghi lại. Đây là bằng chứng bước
  này không đổi hành vi.

## Còn lại / rủi ro

- Người dùng chốt gỡ hẳn luồng cũ ngay (13/10). Snapshot luồng cũ sẽ được thay bằng snapshot orchestrator ở D3, nên lưới
  "không đổi hành vi" của các bước sau dựa trên baseline mới đó.
- Chưa chạy cả bộ backend sau bước này; chạy ở cuối đợt gỡ.
