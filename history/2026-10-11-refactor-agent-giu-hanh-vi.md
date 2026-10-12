# Refactor Itinerary Agent giữ nguyên hành vi: lưới snapshot, luật đồng ý, cờ hội thoại

- Ngày: 2026-10-11
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: agent, docs

## Mục tiêu

Trả nợ kiến trúc của agent (đánh giá 11/10) mà người dùng không thấy hành vi đổi. Plan:
`docs/plan/2026-10-11-refactor-agent-giu-hanh-vi.md`. Phục vụ FR-AGT-01..07, NFR-REL-01. Graph, prompt, contract không đổi,
nên không lệch PRD.

## File thay đổi

- `docs/plan/2026-10-11-refactor-agent-giu-hanh-vi.md` — thêm: plan, nguyên tắc, lưới an toàn, kết quả từng bước.
- `src/backend/tests/unit/agents/behavior_snapshot/harness.py` — thêm: chạy hội thoại qua graph runtime; tool phát lại từ cassette ghi ở chế độ `inprocess` (khoá theo tên tool + tham số, lưu gzip, sản phẩm trùng lưu một lần), LLM phát lại từ cassette khoá theo hash payload, "hôm nay" cố định 2026-10-11, uuid tất định theo kịch bản.
- `src/backend/tests/unit/agents/behavior_snapshot/record.py` — thêm: dựng app backend thật (lifespan, `ITINERARY_DATA_MODE=inprocess`), ghi cassette tool + LLM và snapshot (`--only`, `--fresh`).
- `src/backend/tests/unit/agents/behavior_snapshot/__init__.py` — thêm: package.
- `src/backend/tests/unit/agents/behavior_snapshot/scenarios.json` — thêm: 57 kịch bản (166 lượt), chép từ `chat_messy_v1`, `chat_review_v1`, `agent_scenarios_v5`, `agent_test_cases_nhat` (ngày quy về 2026-10-11) và 14 kịch bản thêm.
- `src/backend/tests/unit/agents/behavior_snapshot/cassette.json` — thêm: 365 câu trả lời LLM thật (chỉ đầu ra, không có prompt).
- `src/backend/tests/unit/agents/behavior_snapshot/tools.json.gz` — thêm: 199 kết quả tool từ `inprocess` (catalog local, khách chưa đăng nhập).
- `src/backend/tests/unit/agents/behavior_snapshot/snapshot.json` — thêm: hành vi từng lượt trước refactor.
- `src/backend/tests/unit/agents/test_behavior_snapshot.py` — thêm: phát lại và so từng lượt; báo đường dẫn chỗ lệch đầu tiên.
- `src/backend/tests/unit/agents/test_phase.py` — thêm: khôi phục hội thoại lưu theo dạng cũ, cờ trong lượt bắt đầu lại, `settled`.
- `src/backend/app/agents/steps/consent.py` — thêm: mọi luật đồng ý lập lịch (`asks_for_plan`, `says_yes`, `planning_implied`, `plan_consented`, `consent_update`, `newly_consented`, `implied_update`, `restored`).
- `src/backend/app/agents/steps/phase.py` — thêm: vòng đời cờ hội thoại (`CARRIED`, `TURN_ONLY`, `carried`, `turn_defaults`, `settled`).
- `src/backend/app/agents/steps/classification.py` — sửa: bỏ luật đồng ý (chuyển sang `consent.py`, vẫn import lại tên cũ); hai chỗ dựng cập nhật đồng ý dùng `newly_consented`, `extract_result` dùng `implied_update`.
- `src/backend/app/agents/nodes.py` — sửa: bỏ `CONVERSATION_PHASE`, `_phase`, `_fare_settled` (chuyển sang `phase.py`, giữ alias `_fare_settled` cho test); `intake` dùng `phase.carried`, `phase.turn_defaults`, `consent.restored`.
- `src/backend/app/agents/steps/exploration.py` — sửa: import `asks_for_plan` từ `consent`.
- `docs/spec/agent/langgraph-nodes.md`, `docs/spec/agent/state-fields.md`, `docs/spec/agent/nghiep-vu/tro-chuyen-va-kham-pha.md` — sửa: trỏ tới `consent.py`, `phase.py`.
- `docs/spec/agent/working-context.md` — sửa: §5A thêm snapshot hành vi và cách ghi lại khi đổi prompt có chủ ý.

## Quyết định

- Lưới snapshot dựng trước khi sửa dòng code nào. Lần đầu dùng fixture 50 sản phẩm; người dùng yêu cầu dùng `inprocess`, nên
  ghi lại trên worktree tạm ở HEAD `95438116` (code trước refactor, chỉ chép thêm harness) với `inprocess` + LLM thật,
  rồi phát lại trên code đã refactor. Phát lại dùng kết quả tool đã ghi chứ không gọi `inprocess` mỗi lần, vì catalog
  nạp lại (cửa sổ mở bán theo ngày) sẽ làm snapshot lệch dù code không đổi, và CI không có DB. Payload gửi LLM
  đổi thì cassette không có bản ghi và test fail, nên lưới bắt cả thay đổi đầu vào LLM.
- Không sửa kỳ vọng của test sẵn có. Tên cũ được giữ bằng import lại (`classification.plan_consented`…) và alias
  (`nodes._fare_settled`).
- Bỏ bước 3 (tách `exploration.py`) và bước 4 (bỏ node sync), vì cả hai buộc phải sửa test (khoảng 15 hàm private, 116 chỗ
  gọi node sync). Đánh giá ngày 11/10 rằng `exploration.py` chứa nhánh tư vấn vé là sai: nhánh đó đã ở `steps/fares.py`.
- Không chạy `chat_replay` với LLM thật: snapshot đã chứng minh payload gửi LLM không đổi.
- Không commit (người dùng chưa yêu cầu).

## Kiểm tra

- Ghi trên code gốc (`inprocess` + LLM thật): 57 kịch bản, 166 lượt, 365 bản ghi LLM, 199 bản ghi tool; không lượt nào
  5xx hay timeout.
- Phát lại trên code gốc: xanh với `PYTHONHASHSEED` = 1, 777, 31337. Hai lỗi harness đã sửa trong lúc làm (không đổi code
  agent): danh sách lời gọi LLM dùng chung giữa các kịch bản chạy song song; thứ tự lời gọi tool song song trong `tool`
  theo độ trễ thật (nay sắp xếp trước khi so).
- Phát lại bản ghi của code gốc trên code đã refactor (bước 1, 2): xanh với cả ba seed.
- Thử gây lỗi (trong bộ nhớ): thêm một dấu cách vào prompt planner → 15/57 kịch bản lệch. Bỏ luật "ok" sau lời mời → 0
  kịch bản lệch, vì ở các câu đó LLM cũng báo `plan_request` (với fixture, cùng thay đổi này làm X04 lệch).
- Sau bước 1 và bước 2: `pytest src/backend/tests/unit/agents src/backend/tests/unit/domain src/backend/tests/architecture`
  → 1996 passed.
- Cả bộ backend: `WEAVIATE_URL=http://127.0.0.1:9 SEARCH_PREWARM=false .venv/bin/python -m pytest -q -p no:cacheprovider
  src/backend/tests` → 2787 passed, 36 skipped.

## Còn lại / rủi ro

- Snapshot chưa phủ `retry`, `dead_letter`, `NO_RESULTS`, `FALLBACK`; các nhánh này dựa vào unit test.
- Dung lượng: `tools.json.gz` khoảng 4,7 MB, `snapshot.json` khoảng 2,4 MB; mỗi lần ghi lại toàn bộ thêm chừng đó vào git.
- Ghi lại cần Postgres + Weaviate local đã nạp catalog; ghi vào ngày khác 2026-10-11 thì đổi `FROZEN_TODAY` và ngày trong
  `scenarios.json`.
- Từ nay đổi prompt có chủ ý thì phải ghi lại cassette bằng LLM thật (`behavior_snapshot.record --only …`). Cassette giữ cả
  bản ghi cũ không còn dùng; thỉnh thoảng ghi lại bằng `--fresh`.
- Còn lại từ đánh giá kiến trúc: gom quyết định rẽ nhánh của `classify` (`route_result`) thành bảng rõ hơn; thay regex bằng
  LLM (việc đổi hành vi, cần đánh giá riêng).
