# Áp dụng orchestrator và khám phá theo ý định (B5–B10)

- Ngày: 2026-10-12
- Tác giả: Nguyễn Minh Nhật / Codex
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: agent, backend, docs
- Tiếp nối: `2026-10-12-nho-ket-qua-da-xem-b1-b3.md`, ba entry `sua-plan-orchestrator-theo-review*` cùng ngày.

## Mục tiêu

Người dùng chốt plan `docs/plan/2026-10-12-nho-ket-qua-da-xem.md` và đề xuất orchestrator trong chat 12/10;
chốt cả bốn mức đề xuất. Phục vụ FR-AGT-01/06/07, AC-AGT-05/06/07/08, NFR-REL-01.
Hoàn thành B5–B10 sau cờ; B11–B13 làm sau như plan.

## File thay đổi

- `.agents/skills/building-itinerary-agent/SKILL.md` — sửa: cập nhật bước 3 theo B10; không áp dụng skill trong task này.
- `.env.example` — sửa: cấu hình cờ và model riêng.
- `docker-compose.yml` — sửa: truyền biến orchestrator vào backend.
- `docs/prd/requirements.md` — sửa: FR-AGT-06 và AC-AGT-06/07/08 theo đề xuất đã chốt.
- `docs/prd/architecture.md` — sửa: graph sau cờ, execution/grounding/consent theo PRD mới.
- `docs/prd/deployment-plan.md` — sửa: biến cấu hình orchestrator.
- `docs/prd/update-archive/2026-10-12-orchestrator-va-kham-pha-llm.md` — đổi tên từ docs/prd/update/: đánh dấu đã áp dụng, ghi người/ngày chốt.
- `docs/plan/2026-10-12-nho-ket-qua-da-xem.md` — sửa: trạng thái B4–B10, bốn quyết định đã chốt, cách chạy model thật và giới hạn kiểm nhanh.
- `docs/spec/agent/langgraph-nodes.md` — sửa: topology sau cờ, bộ đếm, giới hạn brief, vòng nút vé.
- `docs/spec/agent/state-fields.md` — sửa: state, con trỏ, shown.seen/via, waiting và hàng đợi nút vé.
- `docs/spec/agent/working-context.md` — sửa: bản đồ runtime mới.
- `docs/spec/agent/nghiep-vu/tro-chuyen-va-kham-pha.md` — sửa: hành vi khám phá theo intent sau cờ.
- `docs/spec/agent/nghiep-vu/vong-doi-mot-luot.md` — sửa: vòng đời orchestrator và phanh.
- `docs/spec/hop-dong-tich-hop-itinerary-assistant.md` — sửa: tích hợp orchestrator, không đổi API.
- `src/backend/README.md` — sửa: hướng dẫn bật cờ, model/provider và giới hạn.
- `src/backend/app/agents/models.py` — sửa: schema Job/Pending/Question/PlanOffer/OrchestratorTurn.
- `src/backend/app/agents/graph.py` — sửa: node/edge mới chỉ khi bật cờ.
- `src/backend/app/agents/routing.py` — sửa: route các action và vòng lặp.
- `src/backend/app/agents/runtime_dependencies.py` — sửa: tiêm model/cờ/ngân sách.
- `src/backend/app/agents/nodes.py` — sửa: classify/finalize tích hợp, export node mới.
- `src/backend/app/agents/state.py` — sửa: field trong/lưu qua lượt.
- `src/backend/app/agents/steps/jobs.py` — thêm: execution đọc-only, pagination, brief và giới hạn chung.
- `src/backend/app/agents/steps/orchestration.py` — thêm: payload, orchestrate/run_jobs/gatekeep và fallback.
- `src/backend/app/agents/steps/consent.py` — sửa: kiểm đồng ý có cấu trúc, nút vé chạy waiting jobs.
- `src/backend/app/agents/steps/phase.py` — sửa: tách carried/turn của cờ on, bảo toàn state cũ khi off.
- `src/backend/app/agents/steps/shown.py` — sửa tiếp file B2 chưa tracked: mã ổn định, via, bộ nhớ cả hội thoại.
- `src/backend/app/agents/steps/prompts.py` — sửa: prompt orchestrator, bare destination, placeholder và phụ thuộc.
- `src/backend/app/agents/steps/validation.py` — sửa: cho link vé đã xác minh từ khối code qua kiểm cuối.
- `src/backend/app/domain/itinerary/gatekeeper.py` — thêm: luật thuần cho grounding, phạm vi, số liệu, thẻ và khối vé.
- `src/backend/app/core/config.py` — sửa: biến cấu hình orchestrator.
- `src/backend/app/main.py` — sửa: composition root model riêng và ngân sách.
- `src/backend/app/infrastructure/llm/client.py` — sửa: adapter model riêng, OpenAI native JSON schema, tham số reasoning.
- `src/backend/app/infrastructure/llm/__init__.py` — sửa: export factory mới.
- `src/backend/tests/unit/agents/test_orchestrator_jobs.py` — thêm: phạm vi, query, giá, continuation, full seen và brief budget.
- `src/backend/tests/unit/agents/test_orchestrator_runtime.py` — thêm: graph, consent, phanh, waiting/buttons, repair/finalize.
- `src/backend/tests/unit/domain/test_orchestrator_gatekeeper.py` — thêm: intent/card/numeric/link/fare/offer checks.
- `src/backend/tests/unit/infrastructure/test_llm_factory.py` — sửa: provider/model/native schema và tham số hỗ trợ.

Danh sách trên đối chiếu `git status` cuối task và phân biệt thay đổi có sẵn trước khi bắt đầu:
`tu-van-ve-may-bay.md`, `steps/fares.py`, `history.py`, `messages.py`, `turn_notes.py`,
`test_fares_followups.py`, `test_fares_messy.py`, `test_shown.py`, ba file behavior_snapshot và bảy entry lịch sử
plan/design/review đã có từ B1–B3. Không ghi lại cassette/snapshot hoặc sửa các entry cũ trong task này.
Các file `nodes.py`, `state.py`, `phase.py`, `prompts.py`, spec đã có diff B1–B3 được sửa tiếp tại chỗ.

## Quyết định

- Áp dụng PRD trước source. Đề xuất chuyển từ `update/` sang `update-archive/`; vì file chưa tracked nên dùng rename,
  không thể `git mv`. Ghi trạng thái đã áp dụng và người/ngày chốt.
- Tối đa 3 thẻ tham quan/tour; 2 khách sạn khi hỏi chung, 4 khi chỉ hỏi chỗ ở. Muốn thêm loại thẻ đã hiện cả hội thoại
  theo điểm đến + taxonomy. Tối đa 3 việc/vòng, 3 vòng execute/lượt.
- Cờ mặc định `off`; topology/payload lưu cũ khi off không thêm state mới. Không bật mặc định, không gỡ đường cũ.
- Code thực thi và gác cổng; hiểu câu bằng prompt/context, không thêm regex ý định. Tra giá/giờ/đánh giá mới trong lượt,
  LLM chỉ dùng mã và placeholder. Finalize kiểm lại bản trước điền số, ghi shown chỉ sau response hợp lệ.
- shown.seen giữ ID/mã/phạm vi/via cho cả hội thoại; cap 40 dòng facts mỗi nơi không được làm more quên thẻ cũ.
- Brief giới hạn 8 mục/1.500 ký tự mỗi việc, 3.000 ký tự toàn bộ JSON kể cả metadata và tóm tắt các vòng trước.
  Giữ dữ liệu đầy đủ ở code; cursor dùng chung qua alias. BudgetTools dành số lời gọi trước await để job song song
  không vượt 10 tool/lượt. Nút vé có hơn 3 yêu cầu chờ được chia vòng trong cùng ngân sách.
- OpenAI dùng native JSON schema strict, không function calling; model `gpt-6.1-sol`, reasoning `low`, không gửi
  temperature. Đối chiếu [model](https://developers.openai.com/api/docs/models/gpt-6.1-sol) và
  [hướng dẫn GPT-6](https://developers.openai.com/api/docs/guides/latest-model); model không nhận none/minimal.
  Tham số/latency chính thức vẫn phải đo ở B12.
- Không dùng skill theo chỉ dẫn người dùng, không spawn subagent, không commit, không reset dữ liệu.

## Kiểm tra

- Backend cuối: `WEAVIATE_URL=http://127.0.0.1:9 SEARCH_PREWARM=false HF_HUB_OFFLINE=1 LANGSMITH_TRACING=false
  .venv/bin/python -m pytest -q -p no:cacheprovider src/backend/tests` → **2935 passed, 36 skipped, 1 warning, 38.06 s**.
  Log `/tmp/orchestrator-backend-tests.log`. Warning là Starlette/anyio BlockingPortal deprecation. Có regression
  snapshot cờ off, kiểm architecture và wiring; skipped không được coi là pass.
- Unit agent + domain trước kiểm cuối: cùng env offline, `.venv/bin/python -m pytest -q -p no:cacheprovider
  src/backend/tests/unit/agents src/backend/tests/unit/domain` → **2089 passed, 19.41 s**.
- `PYTHONDONTWRITEBYTECODE=1 python3 src/shared/contracts/tests/validate_contract.py` → **PASS**:
  120 schema/96 fixture; CDP 12 schema/7 fixture/11 negative case. Không đổi contract hay mock.
- `docker compose config --quiet` và `git diff --check` → **PASS**.
- Gatekeeper line coverage: `PYTHONPATH=. .venv/bin/python /tmp/orchestrator_coverage.py` dùng stdlib trace và 22 test
  domain → **192/233 dòng, 82,4%**. Số tính bảo thủ, gồm dòng declaration/import đã load trước tracing;
  không suy ra coverage toàn backend/application. Venv chưa có pytest-cov/coverage, không cài thêm dependency.
- Gọi API model thật bằng `/tmp/check_orchestrator_model.py`: gpt-6.1-sol/low/native JSON schema thành công **6,31 s**.
- Smoke B10: model thật + port Search/Catalog/DB thật qua `inprocess_app` và composition root `_itinerary_runtime`;
  không dùng scripted LLM. Cờ on, provider openai/model gpt-6.1-sol/reasoning low, HF_HUB_OFFLINE=1,
  SEARCH_PREWARM=false, LANGSMITH_TRACING=false. Chạy `PYTHONPATH=. .venv/bin/python /tmp/orchestrator_live.py`;
  7 hội thoại, 13 lượt trong `/tmp/orchestrator-live.json` và log cùng tên. Mã 200 là http_status của graph,
  chưa phải bài kiểm qua HTTP endpoint hoặc trình duyệt.

| Hội thoại | Kết quả kiểm nhanh | Latency từng lượt (ms), lần chạy này |
|---|---|---|
| Hà Nội → ngoài ra còn gì nữa | Mỗi lượt 3 tham quan + 2 khách sạn, giao productId hai lượt rỗng | 16180 / 12921 |
| Hà Nội → đi rồi | Không lặp thẻ, ghi Hà Nội bị chê và hỏi nơi khác | 16933 / 4744 |
| Cứ chọn đại → chán, đi rồi | Tự khám phá; lượt chê không lặp và xoá lời mời cũ | 12764 / 4063 |
| Vé sg ra hn → có chuyến nào rẻ hơn | Trả mốc vé vừa tra; đã rẻ nhất thì nói rõ, không bịa chuyến rẻ hơn | 5450 / 5008 |
| Vé sg ra hn bao nhiêu, Hà Nội có gì chơi | Khối vé code nguyên văn + 3 thẻ tham quan, trả đủ hai yêu cầu | 11051 |
| Hà Nội → khách sạn thứ hai giá bao nhiêu | about_shown tra đúng Rue de L'amour, không tìm khách sạn mới | 11541 / 7465 |
| Hà Nội → mấy chỗ lúc nãy cái nào có hồ bơi | Tra đúng hai khách sạn cũ, phân biệt có hồ bơi và chưa có dữ kiện | 11967 / 9110 |

- Smoke phát hiện bare destination bị hỏi loại trước khi khám phá: sửa prompt, không regex; lần chạy bảng trên đã đúng.
  Phát hiện unit bị lặp `/đêm/đêm`: sửa formatter và prompt, thêm test. Cập nhật giới hạn brief tính cả metadata/vòng cũ.
- Kiểm lại sau các sửa cuối bằng `/tmp/orchestrator_live_final.py`, 2 hội thoại/3 lượt, JSON/log
  `/tmp/orchestrator-live-final.*`: Hà Nội trả 3 tham quan + 2 khách sạn (**27983 ms**); hỏi thứ hai tra đúng
  **REY Hotel Hanoi**, ID khớp thẻ thứ hai và chỉ một about_shown, giá không lặp unit (**18748 ms**);
  tin vé + vui chơi trả 4 flight + 3 attraction và cả hai phần (**26769 ms**).
- Có một lần kiểm cuối provider trả HTTP 500 trước khi có structured output; log ghi OpenAIAPIError,
  graph fallback không bịa thẻ. Bằng chứng lỗi giữ ở `/tmp/orchestrator-live-provider500.*`; chạy lại thành công
  như dòng trên. Không che lần lỗi hoặc coi HTTP200/fallback là đạt câu hỏi giá.
- Hai lần kiểm trong sandbox ban đầu bị treo, đã ngắt exit130; chạy ngoài sandbox hoàn tất.
  Lần unit mới đầu tiên 34 pass/1 fail (force_answer bị reset sau repair), đã sửa và suite cuối pass.

## Còn lại / rủi ro

- B11–B13: bộ luật trên snapshot, đánh giá nhiều hội thoại/nhiều lần, latency p50/p95/chi phí, bật mặc định và gỡ regex.
  Ngoài lần thực thi B5–B10 theo plan đã chốt. Smoke một lần không chứng minh độ ổn định hoặc đạt SLA.
- Cờ local/compose vẫn mặc định off; chưa deploy, chưa kiểm FE bằng trình duyệt. Không thay schema/seed.
- Các JSON/log/script trong /tmp là scratch, có thể mất khi dọn máy; plan mục 0 có script tái chạy, số liệu quan trọng
  đã ghi ở entry này. Prompt/model/catalog có thể đổi kết quả thẻ và latency giữa các lần chạy.
