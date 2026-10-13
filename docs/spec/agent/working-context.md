# Working context cho Itinerary Agent

File này là điểm nạp context ngắn cho người hoặc coding agent khi cần **sửa, tune hoặc đánh giá**
Itinerary Agent. Không đọc toàn bộ `docs/` ngay từ đầu. Đọc mục 1, chọn đúng một nhánh ở mục 2, rồi
mở source được chỉ ra trong mục 3.

## 1. Context tối thiểu — đọc trước mọi task Agent

1. `docs/spec/agent/working-context.md` — file này.
   Chưa nắm agent đang làm gì về nghiệp vụ (hỏi lại, tìm, vé, xếp lịch, diễn giải) thì đọc trước
   [nghiep-vu/README.md](nghiep-vu/README.md) và [nghiep-vu/glossary.md](nghiep-vu/glossary.md).
2. `docs/prd/architecture.md` §2, §3 — phân lớp/quy tắc phụ thuộc và grounding; quality gate ở `golden-run.md` mục 5.
3. `src/shared/contracts/openapi.yaml`, sau đó chỉ mở fragment liên quan:
   - Assistant: `paths/itinerary-agent.yaml`, `schemas/itinerary-agent.yaml`.
   - Tool Search: `paths/search.yaml`, `schemas/search.yaml`, `schemas/catalog.yaml`.
   - Tool Recommendation: `paths/recommendations.yaml`, `schemas/recommendations.yaml`.
   - Tool Similar (chỉ ở lượt đổi món): `paths/catalog.yaml` (`getSimilarProducts`), `schemas/catalog.yaml`
     (`SimilarProductsResponse`).
4. `history/README.md`, 10 entry mới nhất và entry từng chạm đúng file sắp sửa.

Không dùng tài liệu này thay OpenAPI. Nếu nội dung lệch nhau, OpenAPI và fragment của nó thắng.

## 2. Chọn context theo loại việc

Chỉ đọc hàng khớp với task hiện tại. Không cần nạp các nhánh khác.

| Việc cần làm | Đọc thêm | Source bắt đầu từ |
|---|---|---|
| Hiểu hoặc đổi luật nghiệp vụ (hỏi lại, lọc, vé, xếp lịch, tiền, diễn giải) | đúng một file trong `nghiep-vu/` theo mục lục [nghiep-vu/README.md](nghiep-vu/README.md) | file ở mục "Code liên quan" của file đó |
| Hiểu hoặc đổi topology/routing | `langgraph-nodes.md` | `agents/graph.py`, `agents/routing.py`, `agents/state.py` |
| Tune orchestrator (hiểu câu, chọn việc, chọn thẻ, hỏi lại, câu vé) | `docs/prd/architecture.md` §3 (đoạn orchestrator) | `agents/steps/orchestration.py`, `agents/steps/jobs.py`, `agents/steps/fares.py`, `domain/itinerary/gatekeeper.py`, `ORCHESTRATOR_PROMPT` trong `agents/steps/prompts.py` |
| Tune `extract`, `clarify` hoặc prompt nhánh lập lịch | `langgraph-nodes.md`, phần hội thoại trong spec Itinerary | `agents/steps/prompts.py`, `agents/steps/classification.py` (`extract`), `agents/steps/conversation.py` (`clarify`), `infrastructure/llm/` |
| Tune tool planning, Search/Recommendation/Similar | spec Itinerary §2 (Similar: §2.5), `src/backend/README.md` | `agents/steps/tool_planning.py`, `agents/tools/itinerary_gateway.py`, `application/itinerary/tool_contracts.py`, `application/itinerary/engine_tools.py` |
| Tune lọc candidate/grounding | `langgraph-nodes.md` §5, spec Itinerary §5 | `application/itinerary/retrieval.py`, `domain/itinerary/planning.py` |
| Tune Search ranking | handbook §12 và spec Backend mục Search | `application/search/use_cases.py`, `domain/search/`, `infrastructure/vectors/` |
| Tune Recommendation | handbook §8, §12 và spec Backend mục Recommendation | `application/recommendation/use_cases.py`, `domain/recommendation/` |
| Đổi API/request/response | `src/shared/contracts/README.md`, `MVP.md`, baseline contract | fragment OpenAPI trước, rồi `api/v1/routes/assistant.py` |
| Eval hành vi Agent | `golden-run.md` (giao diện: mục 2.1) | `src/evaluation/agent/golden.py`, `src/evaluation/agent/eval_app.py`, `src/evaluation/agent/streamlit_app.py`, tests Agent |
| Debug runtime/trace | `README.md` mục LangSmith, `response-and-errors.md` | `api/v1/routes/assistant.py`, `agents/report.py` |

Đường dẫn source trong bảng đều tương đối với `src/backend/app/`, trừ khi ghi đầy đủ.

## 3. Bản đồ runtime hiện hành

Orchestrator là luồng duy nhất (chốt 13/10/2026, `docs/prd/architecture.md` §3); luồng phân loại cũ và cờ
`ITINERARY_ORCHESTRATOR` đã gỡ.

```text
POST /api/v1/assistant/itineraries hoặc /stream
  -> api/v1/routes/assistant.py        nhận request, validate, gọi use case qua Depends
  -> application/itinerary/use_cases.py
                                      PlanItinerary: input graph, timeout, nhãn trace
  -> application/ports/itinerary_planner.py
                                      port; main.py nối agents/runtime_dependencies.py vào theo request
  -> agents/graph.py                   topology LangGraph và dependency injection
  -> agents/nodes.py                   hàm của từng node (luật chi tiết ở agents/steps/)
       intake -> precheck (luật trước LLM, không gọi LLM)
         |- guardrail/tin rác -> converse (câu cố định) -> finalize
         |- nút vé do code tạo -> run_jobs
         |- chọn phương án, đổi vé/khách sạn bằng luật, đồng ý lập lịch có sẵn -> extract | tool | clarify
         `- còn lại -> orchestrate (LLM, steps/orchestration.py)
              |- answer/ask -> gatekeep -> finalize
              |- execute -> run_jobs (steps/jobs.py) -> orchestrate | gatekeep
              `- plan (đồng ý đã kiểm) -> extract
                   |- chưa đồng ý -> gatekeep (lời mời lập lịch)
                   |- thiếu dữ liệu -> clarify -> finalize
                   `- đủ dữ liệu -> tool -> evaluate
                        |- candidate hợp lệ -> filter -> compose -> narrate -> finalize
                        |     (filter: luật cùng tên + LLM chỉ ra cặp điểm tham quan trùng)
                        |- lỗi tạm thời -> retry -> tool
                        |- cần hỏi điều kiện -> clarify -> finalize
                        `- lỗi vĩnh viễn -> dead_letter -> finalize
  -> agents/tools/itinerary_gateway.py allowlist, validate và dispatch tool
  -> application/ports/itinerary_tools.py
                                      interface Agent phụ thuộc
  -> adapter theo ITINERARY_DATA_MODE (main.py chọn):
       fixture    infrastructure/clients/itinerary_fixture_clients.py
                                      fixture local 50 sản phẩm
       inprocess  application/itinerary/engine_tools.py
                                      gọi engine trên app.state trong tiến trình, pool riêng
       http       infrastructure/clients/itinerary_http_clients.py
                                      tuỳ chọn: qua api/v1/routes/search.py, recommendations.py,
                                      catalog.py (similar)
  -> application/*/use_cases.py       search/ranking/personalization thật
  -> infrastructure/vectors + CDP     dữ liệu catalog và hành vi
```

Kết quả tool quay lại `retrieval.py` để gộp, hậu kiểm và ghi nguồn; `planning.py` xếp lịch tất định;
`finalize` kiểm OpenAPI, grounding và lưu conversation trước khi trả response.

Orchestrator (chốt 12/10, luồng duy nhất từ 13/10): `precheck` giữ luật đầu vào (không LLM phân loại), chuyển hội thoại tới
`steps/orchestration.py` (`orchestrate` → `run_jobs` → `gatekeep`). `steps/jobs.py` thực thi qua port, domain
`gatekeeper.py` kiểm nguồn/phạm vi/số/thẻ; `steps/shown.py` ghi trí nhớ từ response ở finalize. Model riêng nằm tại
`app.state.itinerary_orchestrator_llm`, không vào state. Nhánh lập lịch và narrate giữ nguyên.
Phanh của lượt có mã nguyên nhân (`steps/limits.py`: hết giờ, trần vòng, trần tool, model hoặc tool quá hạn), ghi ở
metadata event, `turn_limit_reason` và log `itinerary.turn_limit`. B11 (bộ đo so sánh) bỏ; B12 (chuyển mặc định) đã thay
bằng việc gỡ luồng cũ; B13 (gỡ regex) chưa làm.

Tiến trình 1.27.0 (AC-AGT-09): `LangGraphItineraryPlanner.astream` phát state/custom; `graph.timed` phát activity, gắn progress vào event và preview sau compose. Collector `steps/progress.py` chỉ sống trong stream của request, số đếm từ `application/itinerary/progress_counts.py` tại các bộ lọc. Không vào working memory hay payload LLM. Route chuyển thành `node.activity`, `node.completed.progress`, `run.preview`; Web gộp theo nhóm và viết nhãn, chẩn đoán mức 1 tại Shift+D. Snapshot vẫn dùng `ainvoke`, không ghi lại cho thay đổi tiến trình.

### 3.1. Assistant v2 (orc tự chủ, chạy song song v1)

```text
POST /api/v2/assistant/itineraries hoặc /stream
  -> api/v2/routes/assistant.py        validate request, rate limit, SSE
  -> application/itinerary/v2_use_cases.py
                                      khoá lượt (clientTurnId), nút server đã cấp, ghi đúng một lần
  -> agents/orc_v2.py                  OrcV2Runtime + graph: precheck → decide ⇄ dispatch → guard; PROMPT
       decide   model trả OrcDecision (schema: application/itinerary/orc_contracts.py), code kiểm schema
       dispatch application/itinerary/orc_dispatch.py: chạy đúng tool orc gọi, ngân sách 10 request nguồn,
                lookup_flights ở flight_lookup.py, build_itinerary kiểm bằng domain/itinerary/draft_validation.py
       guard    domain/itinerary/orc_guardrails.py kiểm câu trả lời; v2_final.py dựng response theo contract v2
  -> infrastructure/persistence/assistant_v2_store.py  working memory 24h (memory/Redis), mở tiếp hội thoại v1
```

Giới hạn mỗi lượt: 3 lượt gọi tool (1–3 tool mỗi lượt), 10 request nguồn, 5 lần gọi model, sửa câu trả lời 1 lần.
Mã sản phẩm `p1, p2…` và mã lời gọi `c1, c2…` do server cấp; số liệu trong lời đáp đi qua đoạn `fact`, tên sản phẩm qua
đoạn `product` (code điền tên và đặt thẻ). Test: `tests/unit/agents/test_orc_*.py`, `tests/unit/application/test_assistant_v2_*.py`,
`tests/unit/domain/test_orc_*.py`, `tests/contract/test_assistant_v2_contract.py`; model giả ở `tests/fakes/orc_tools.py`.

## 4. Trách nhiệm các lớp — dùng để tránh sửa sai chỗ

| Lớp | Chịu trách nhiệm | Không đặt ở đây |
|---|---|---|
| `agents` | Khi nào gọi node/tool, state và routing | SQL, đọc DB trực tiếp, sản phẩm do LLM tạo |
| `application/ports` | Interface ổn định mà Agent cần | HTTP/FastAPI/DB implementation |
| `infrastructure/clients` | Fixture hoặc HTTP adapter | Quyết định nghiệp vụ của graph |
| `application/itinerary/engine_tools.py` | Adapter `inprocess`: gọi use case có sẵn, map lỗi thành `ToolError`, xác minh JWT qua `application/auth/bearer.py` | SDK/DB/HTTP, quyết định của graph |
| `api/v1/routes` | HTTP parsing, auth, response boundary | Ranking/personalization |
| `application/*/use_cases` | Search/Recommendation orchestration | FastAPI hoặc prompt Agent |
| `domain` | Rule thuần: scoring, planning, validation | Network và database driver |
| OpenAPI | Shape request/response giữa các team | Thuật toán implementation |

## 5. Ba vòng tune không được trộn

### A. Tune Agent

Đối tượng: prompt, intent extraction, tool plan, routing, retry, câu hỏi clarification.

Bằng chứng tối thiểu: state trước/sau node, node path, tool name/arguments, final status. Không dùng chất
lượng ranking để kết luận prompt tốt hoặc xấu.

**Snapshot hành vi** (`tests/unit/agents/test_behavior_snapshot.py`, chạy cùng unit test agent). Phát lại mọi hội thoại
của `behavior_snapshot/scenarios.json` (63 ngày 13/10, gồm `demo-K1`…`demo-K6`) với tool ghi từ chế độ `inprocess` (dữ
liệu thật) và LLM ghi sẵn, rồi so từng lượt (response, node path, mã `ROUND_LIMIT`/`TOOL_LIMIT`, state lưu, payload gửi
LLM, tham số gọi tool). Đồng hồ đứng yên (`agents/clock.now`), nên phát lại không phụ thuộc tốc độ máy. Phát lại không cần
DB hay mạng. Refactor phải giữ nó xanh. Đổi prompt hoặc hành vi **có chủ ý** thì test fail. Khi đó ghi lại bằng
`inprocess` và LLM thật (cần Postgres, Weaviate local), chỉ những kịch bản bị ảnh hưởng, rồi đọc diff của `snapshot.json`
trước khi commit:

```bash
HF_HUB_OFFLINE=1 .venv/bin/python -m src.backend.tests.unit.agents.behavior_snapshot.record --only X01-plan-doi,v5-SC-A
```

- Không `--fresh`: lời gọi LLM có payload không đổi được phát lại từ cassette, chỉ payload mới gọi model thật. `--fresh`
  ghi lại toàn bộ hai cassette; chỉ dùng khi đổi kiến trúc hay model.
- Lượt hết giờ hoặc model/tool thật quá hạn, lỗi (`TIME_LIMIT`, `MODEL_TIMEOUT`, `MODEL_ERROR`, `TOOL_TIMEOUT`) không
  phát lại được: `record` ghi lại kịch bản đó tối đa 3 lần rồi dừng và báo, không lưu.
- Baseline hiện hành và bảng so với luồng cũ: `src/evaluation/reports/eval-2026-10-13-d3-snapshot-orchestrator.md`.

Chi tiết: `src/backend/tests/unit/agents/behavior_snapshot/harness.py`, plan `docs/plan/2026-10-11-refactor-agent-giu-hanh-vi.md`.

### B. Tune retrieval/recommendation

Đối tượng: embedding, filter, candidate pool, score, MMR, profile và cold-start.

Bằng chứng tối thiểu: dataset cố định, version model/index, Recall@20, NDCG@10, coverage và latency.
Không dùng một itinerary nhìn hợp lý để kết luận ranking tốt.

### C. Eval end-to-end

Đối tượng: toàn đường API -> graph -> tool -> response.

Bằng chứng tối thiểu: commit SHA, model, data mode, catalog/index version, config timeout, request/trace
ID và artifact kết quả. Báo riêng:

- fixture/deterministic;
- backend local với PostgreSQL;
- model/provider thật;
- production-like latency.

`node outcome=completed` chỉ nói node chạy xong, không phải evaluation PASS. Fixture PASS chỉ chứng
minh routing/grounding vào fixture, không chứng minh dữ liệu, ranking hay SLA production.

## 6. Các invariant cần giữ khi sửa/tune

- Mọi `productId`, tên, giá và thuộc tính trong itinerary phải đến từ tool/backend.
- JWT nằm ngoài `AgentState`; Search không nhận JWT, Recommendation chỉ dùng claim đã xác minh (`inprocess` xác
  minh qua `application/auth/bearer.py`, cùng resolver với route).
- `ITINERARY_DATA_MODE=fixture`, `inprocess` và `http` phải cùng hiện thực các port và trả cùng hình dạng, nhưng bằng
  chứng của chúng khác nhau. Golden runner vẫn đi `http`, còn staging/production chạy `inprocess`.
- Tool `get_similar_products` chỉ được mời khi `previous_selection` khác rỗng; sản phẩm gốc chỉ lấy từ danh sách đó,
  tối đa 2 lời gọi mỗi lượt, lỗi của nó là best-effort (spec Itinerary §2.5). Lượt đầu giữ nguyên bộ tool và prompt.
- `compose` là tất định; LLM không được tự xếp hoặc thêm sản phẩm. `filter` chỉ nhận từ LLM cặp mã trùng có trong danh
  sách; giữ mã nào do luật (`domain/itinerary/dedupe.py`).
- Mọi nhánh response phải đi qua `finalize`.
- Thiếu destination/days thì chưa gọi product tool.
- Thay contract: sửa fragment OpenAPI trước, không sửa bundle sinh tự động.
- Không ghi prompt chứa secret, JWT hoặc API key vào log/report.

## 7. Checklist mở task tiết kiệm token

```text
1. git status --short --branch
2. Đọc file này + đúng một hàng ở mục 2
3. Mở graph/routing hoặc route đang thực sự gọi code cần sửa
4. rg symbol cụ thể; không đọc toàn bộ package
5. Đọc history theo chính đường dẫn sắp sửa
6. Ghi rõ data mode và tầng bằng chứng trước khi chạy eval
```

Khi bàn giao, ghi riêng: thay đổi gì, invariant nào bị ảnh hưởng, test nào thực sự hoàn tất, test nào
timeout/chưa chạy, và kết quả chỉ chứng minh fixture, local backend hay provider thật.
