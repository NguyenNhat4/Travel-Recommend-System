# Working context cho Itinerary Agent

File này là điểm nạp context ngắn cho người hoặc coding agent khi cần **sửa, tune hoặc đánh giá**
Itinerary Agent. Không đọc toàn bộ `docs/` ngay từ đầu. Đọc mục 1, chọn đúng một nhánh ở mục 2, rồi
mở source được chỉ ra trong mục 3.

## 1. Context tối thiểu — đọc trước mọi task Agent

1. `docs/spec/agent/working-context.md` — file này.
2. `docs/prd/architecture.md` §2, §3 — phân lớp/quy tắc phụ thuộc và grounding; quality gate ở `evaluation-plan.md`.
3. `src/shared/contracts/openapi.yaml`, sau đó chỉ mở fragment liên quan:
   - Assistant: `paths/itinerary-agent.yaml`, `schemas/itinerary-agent.yaml`.
   - Tool Search: `paths/search.yaml`, `schemas/search.yaml`, `schemas/catalog.yaml`.
   - Tool Recommendation: `paths/recommendations.yaml`, `schemas/recommendations.yaml`.
4. `history/README.md`, 10 entry mới nhất và entry từng chạm đúng file sắp sửa.

Không dùng tài liệu này thay OpenAPI. Nếu nội dung lệch nhau, OpenAPI và fragment của nó thắng.

## 2. Chọn context theo loại việc

Chỉ đọc hàng khớp với task hiện tại. Không cần nạp các nhánh khác.

| Việc cần làm | Đọc thêm | Source bắt đầu từ |
|---|---|---|
| Hiểu hoặc đổi topology/routing | `langgraph-nodes.md` | `agents/graph.py`, `agents/routing.py`, `agents/state.py` |
| Tune classify/clarify/converse hoặc prompt | `langgraph-nodes.md`, phần hội thoại trong spec Itinerary | `agents/steps/prompts.py`, `agents/steps/classification.py`, `agents/steps/conversation.py`, `infrastructure/llm/` |
| Tune tool planning, Search/Recommendation | spec Itinerary §2, `src/backend/README.md` | `agents/steps/tool_planning.py`, `agents/tools/itinerary_gateway.py`, `application/itinerary/tool_contracts.py` |
| Tune lọc candidate/grounding | `langgraph-nodes.md` §5, spec Itinerary §5 | `application/itinerary/retrieval.py`, `domain/itinerary/planning.py` |
| Tune Search ranking | handbook §12 và spec Backend mục Search | `application/search/use_cases.py`, `domain/search/`, `infrastructure/vectors/` |
| Tune Recommendation | handbook §8, §12 và spec Backend mục Recommendation | `application/recommendation/use_cases.py`, `domain/recommendation/` |
| Đổi API/request/response | `src/shared/contracts/README.md`, `MVP.md`, baseline contract | fragment OpenAPI trước, rồi `api/v1/routes/assistant.py` |
| Eval hành vi Agent | `evaluation-plan.md` | `src/evaluation/agent/streamlit_app.py`, tests Agent |
| Debug runtime/trace | `README.md` mục LangSmith, `response-and-errors.md` | `api/v1/routes/assistant.py`, `agents/report.py` |

Đường dẫn source trong bảng đều tương đối với `src/backend/app/`, trừ khi ghi đầy đủ.

## 3. Bản đồ runtime hiện hành

```text
POST /api/v1/assistant/itineraries hoặc /stream
  -> api/v1/routes/assistant.py        nhận request, validate, gọi use case qua Depends
  -> application/itinerary/use_cases.py
                                      PlanItinerary: input graph, timeout, nhãn trace
  -> application/ports/itinerary_planner.py
                                      port; main.py nối agents/runtime_dependencies.py vào theo request
  -> agents/graph.py                   topology LangGraph và dependency injection
  -> agents/nodes.py                   hàm của từng node (luật chi tiết ở agents/steps/)
       intake -> classify
         |- thiếu dữ liệu -> clarify -> finalize
         |- hội thoại/refusal -> converse -> finalize
         `- đủ dữ liệu -> tool -> evaluate
                              |- candidate hợp lệ -> compose -> finalize
                              |- lỗi tạm thời -> retry -> tool
                              |- cần hỏi điều kiện -> clarify -> finalize
                              `- lỗi vĩnh viễn -> dead_letter -> finalize
  -> agents/tools/itinerary_gateway.py allowlist, validate và dispatch tool
  -> application/ports/itinerary_tools.py
                                      interface Agent phụ thuộc
  -> infrastructure/clients/
       itinerary_fixture_clients.py   fixture local
       itinerary_http_clients.py      gọi Search/Recommendation backend
  -> api/v1/routes/search.py hoặc recommendations.py
  -> application/*/use_cases.py       search/ranking/personalization thật
  -> infrastructure/vectors + CDP     dữ liệu catalog và hành vi
```

Kết quả tool quay lại `retrieval.py` để gộp, hậu kiểm và ghi nguồn; `planning.py` xếp lịch tất định;
`finalize` kiểm OpenAPI, grounding và lưu conversation trước khi trả response.

## 4. Trách nhiệm các lớp — dùng để tránh sửa sai chỗ

| Lớp | Chịu trách nhiệm | Không đặt ở đây |
|---|---|---|
| `agents` | Khi nào gọi node/tool, state và routing | SQL, đọc DB trực tiếp, sản phẩm do LLM tạo |
| `application/ports` | Interface ổn định mà Agent cần | HTTP/FastAPI/DB implementation |
| `infrastructure/clients` | Fixture hoặc HTTP adapter | Quyết định nghiệp vụ của graph |
| `api/v1/routes` | HTTP parsing, auth, response boundary | Ranking/personalization |
| `application/*/use_cases` | Search/Recommendation orchestration | FastAPI hoặc prompt Agent |
| `domain` | Rule thuần: scoring, planning, validation | Network và database driver |
| OpenAPI | Shape request/response giữa các team | Thuật toán implementation |

## 5. Ba vòng tune không được trộn

### A. Tune Agent

Đối tượng: prompt, intent extraction, tool plan, routing, retry, câu hỏi clarification.

Bằng chứng tối thiểu: state trước/sau node, node path, tool name/arguments, final status. Không dùng chất
lượng ranking để kết luận prompt tốt hoặc xấu.

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
- JWT nằm ngoài `AgentState`; Search không nhận JWT, Recommendation chỉ dùng claim đã xác minh.
- `ITINERARY_DATA_MODE=fixture` và `http` phải cùng hiện thực các port, nhưng bằng chứng của chúng khác nhau.
- `compose` là tất định; LLM không được tự xếp hoặc thêm sản phẩm.
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
