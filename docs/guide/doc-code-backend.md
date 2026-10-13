# Cách đọc code khi phát triển — tập trung backend

Dành cho người mới vào repo, hoặc người quen một workstream cần sửa sang workstream khác. Tài liệu này chỉ
chỉ **đọc cái gì, theo thứ tự nào**; quy tắc gốc vẫn nằm ở `AGENTS.md`, `docs/prd/` và contract. Khi hai bên
lệch nhau thì bên đó thắng, không phải file này.

## 1. Đọc gì trước khi mở code

Đừng mở code ngay. Mười lăm phút đầu dành cho các câu hỏi "làm gì" và "giao diện ra sao":

| Câu hỏi | Đọc ở đâu |
|---|---|
| Feature này thuộc yêu cầu nào? | `docs/prd/requirements.md` — tìm mã FR/NFR và AC |
| Có ai đang đề xuất đổi phần này không? | `docs/prd/update/` |
| Gần đây ai đã sửa gì, còn dở gì? | `history/` — xem mục 6 |
| Request/response trông thế nào? | `src/shared/contracts/paths/<domain>.yaml`, `schemas/<domain>.yaml` |
| Lớp nào được import lớp nào? | `docs/prd/architecture.md` §2 |
| Domain có hợp đồng tích hợp riêng không? | `docs/spec/hop-dong-tich-hop-<domain>.md` |

Bảng đầy đủ theo phạm vi thay đổi ở `AGENTS.md` §1.2.

Hai cạm bẫy hay gặp:

- `docs/prd/api-contract.md` chỉ là minh hoạ. Path và field thật lấy từ `openapi.yaml`; danh sách lệch đã biết
  ghi ở `AGENTS.md` §2.
- Persona trong PRD (`P1_family`...) khác persona trong DDL (`P1_frequent`...). Code theo DDL và contract
  (`AGENTS.md` §6.4).

## 2. Bản đồ backend trong một hình

```text
HTTP ─▶ api/v1/routes/*.py ──Depends──▶ api/deps.py ──▶ app.state.<use case>
                                                           │   (main.py gắn vào lúc khởi động)
                                                           ▼
                                         application/<domain>/use_cases.py
                                              │ gọi qua              │ gọi rule thuần
                                              ▼                      ▼
                                      application/ports/*.py     domain/<domain>/*.py
                                              ▲
                                              │ hiện thực
                        infrastructure/{cdp,persistence,vectors,embeddings,llm,auth,clients}
                        agents/ (LangGraph, hiện thực port ItineraryPlanner)
```

Hướng mũi tên là hướng import. `domain` không biết gì về FastAPI, Postgres hay LangGraph; `api` không import
`infrastructure` hay `agents`. Chỉ `main.py` được biết mọi lớp — đó là nơi duy nhất nối adapter vào use case.
`tests/architecture/test_import_rules.py` quét AST và đỏ ngay khi ai đó phá hướng này.

Hệ quả khi đọc: **muốn biết một port đang dùng adapter nào, đừng tìm trong use case — mở `main.py`.**

## 3. Thứ tự đọc lần đầu

Đọc theo thứ tự này, mỗi bước chỉ cần lướt đủ để trả lời câu hỏi bên phải.

1. `src/backend/README.md` — cách chạy, biến môi trường, bảng "chỗ nào làm gì".
2. `app/main.py` — **file quan trọng nhất.** Đọc `lifespan()`: nó dựng gì, gắn gì vào `app.state`, thiếu
   dịch vụ nào thì tắt tính năng nào. Đọc `build_recsys()` và `build_auth()` để thấy port nào được nối với
   adapter nào.
3. `app/api/v1/router.py` — danh sách router; từ đây nhảy tới route cần sửa.
4. `app/api/deps.py` — route lấy use case và danh tính (JWT) thế nào.
5. `app/application/ports/` — mỗi file một port, ngắn. Đọc hết là biết backend nói chuyện với thế giới bên
   ngoài qua những "cửa" nào.
6. `app/core/config.py` — một lớp `Settings` duy nhất; mọi biến môi trường đều khai ở đây.
7. `app/api/errors.py` — Error Envelope; lỗi nghiệp vụ biến thành HTTP status ở đây.

Sau bảy file này là đủ để lần theo bất kỳ request nào.

## 4. Lần theo một request — ví dụ `GET /api/v1/search`

Cách làm chung: **đi từ route vào trong, rồi tìm adapter ở `main.py`.**

| Bước | File | Thấy gì |
|---|---|---|
| 1. Contract | `src/shared/contracts/paths/search.yaml` | Tham số, response, mã lỗi được hứa |
| 2. Route | `app/api/v1/routes/search.py` | Nhận `q/taxonomy/destination/limit/offset`; RecSys tắt thì trả trang rỗng thay vì 500 |
| 3. Dependency | `app/api/deps.py` → `get_search` | Lấy `app.state.search`, có thể là `None` |
| 4. Use case | `app/application/search/use_cases.py` → `SearchProducts` | Embed câu hỏi, lọc id, hỏi Weaviate top-K, cắt cutoff, phân trang, dựng `diagnostics` |
| 5. Rule thuần | `app/domain/search/scoring.py` → `candidate_filter_score` | CUTOFF → FACETS → SORT trên tập ứng viên top-K |
| 6. Port | `application/ports/embedder.py`, `unit_index.py`, `vector_search.py`, `vector_store.py` | Hợp đồng mà use case dựa vào |
| 7. Adapter | `main.py` → `build_recsys()`, `build_query_embedder()`, `RecsysRefresher` | Embedder từ `infrastructure/embeddings/factory.py` → `build_embedder(settings)` (`LocalE5Embedder` — `intfloat/multilingual-e5-small`, 384 chiều — mặc định; `CohereEmbedder` khi `EMBED_PROVIDER=cohere`) + `WeaviateVectorStore` (collection `ProductE5`); chỉ metadata nạp lúc khởi động và nạp lại theo chu kỳ |
| 8. Adapter chi tiết | `infrastructure/embeddings/local_e5_embedder.py` (đường lui: `cohere_embedder.py`), `infrastructure/vectors/weaviate_store.py` | Chạy model e5 trong tiến trình (tiền tố `query: ` cho câu hỏi, `passage: ` cho text catalog); `WeaviateVectorSearch` truy vấn `nearVector` qua gRPC; tên/giá lấy từ Postgres |

Điều rút ra từ ví dụ: vector không nằm trong bộ nhớ backend. `UnitIndex` chỉ giữ metadata (taxonomy, destination,
available…) để tính filter; mỗi request gửi danh sách id hợp lệ cùng vector truy vấn sang Weaviate và nhận top-K
(`ANN_CANDIDATE_SCORE`, nên `total`/`facets` là xấp xỉ). Chạy lại `make index-vectors` thì request sau thấy vector
mới ngay; catalog trong Postgres đổi thì `RecsysRefresher` nạp lại metadata sau tối đa `CATALOG_REFRESH_SECONDS`,
không cần khởi động lại backend.

Các luồng khác đi đúng khuôn này:

| Endpoint | Route | Use case | Rule thuần | Adapter chính |
|---|---|---|---|---|
| `/similar/{id}` | `routes/search.py` | `search/use_cases.py` → `SimilarProducts` | — | `UnitIndex` + `WeaviateVectorSearch` |
| `/recommendations` | `routes/recommendations.py` | `recommendation/use_cases.py` → `RecommendForUser` (khách → phổ biến) | `domain/recommendation/{profile,popularity}.py` | `PostgresCdpReader` (lịch sử qua `CDP_DATABASE_URL`) + `WeaviateVectorSearch` (vector event, top-K ứng viên) |
| `/destinations` | `routes/catalog.py` | — (đếm thẳng trên `UnitIndex`) | — | `UnitIndex` |
| `/auth/*` | `routes/auth.py` | `auth/use_cases.py` | `domain/auth/*` | `infrastructure/auth/*` |
| `/assistant/itineraries[/stream]` | `routes/assistant.py` | `itinerary/use_cases.py` → `PlanItinerary` | `domain/itinerary/*` | `agents/` qua port `ItineraryPlanner` |

## 5. Đọc Itinerary Agent

Agent là phần dài nhất và dễ lạc nhất. Đọc theo thứ tự:

1. `docs/prd/architecture.md` §3 và `docs/spec/agent/README.md` — agent phải làm gì, chuẩn grounding.
2. `app/application/itinerary/use_cases.py` — `PlanItinerary` chỉ biết port `ItineraryPlanner`, không biết
   LangGraph.
3. `main.py` → `_itinerary_runtime()` / `_itinerary_planner()` — mỗi request dựng một planner với tool, store,
   LLM và `Authorization` của chính request đó.
4. `app/agents/graph.py` — topology: `intake → precheck → orchestrate ⇄ run_jobs → gatekeep`; khi người dùng đồng ý
   lập lịch thì `orchestrate → extract → {clarify | tool}`, `tool → evaluate → {filter → compose → narrate | retry |
   clarify | dead_letter}`. Mọi nhánh kết thúc ở `finalize`. Sơ đồ đầy đủ: `docs/spec/agent/nghiep-vu/vong-doi-mot-luot.md`.
5. `app/agents/routing.py` — điều kiện rẽ nhánh (ngắn, đọc hết).
6. `app/agents/state.py` — state đi qua các node.
7. `app/agents/nodes.py` — mỗi node mỏng; luật thật nằm ở `agents/steps/` (`classification`, `tool_planning`,
   `orchestration`, `jobs`, `validation`, `composition`...).
8. `app/agents/tools/itinerary_gateway.py` — tool gọi Search/Recommendation/Catalog và **validate response
   theo contract**; đây là nơi giữ grounding 100%.

Hai điều cần nhớ khi đọc agent:

- Credential và client LLM không bao giờ nằm trong graph state; chúng được "đóng gói" vào node qua `partial`
  trong `graph.py`.
- `ITINERARY_DATA_MODE=fixture` (mặc định dev) dùng 50 sản phẩm giả ở
  `infrastructure/clients/itinerary_fixture_clients.py`, không gọi Search thật. Kết quả lạ thì kiểm biến này
  trước.

## 6. Đọc lịch sử trước khi sửa

Git cho biết dòng nào đổi; `history/` cho biết **vì sao**. Nhiều đoạn code trông thừa thật ra là quyết định có
chủ đích (ví dụ route `/assistant/chat` bị gỡ cố ý).

```bash
ls history/ | grep -v README | sort | tail -10                    # 10 entry mới nhất
grep -l "src/backend/app/application/search" history/*.md         # ai từng chạm đường dẫn này
grep -l "Trạng thái: dang dở" history/*.md                        # việc bỏ dở
git log --oneline -- src/backend/app/application/search/           # commit liên quan
```

## 7. Dùng test để đọc code

Test là tài liệu chạy được, thường rõ hơn docstring:

| Thư mục | Đọc để biết |
|---|---|
| `tests/unit/domain/` | Rule thuần nhận gì, trả gì — ví dụ nhỏ nhất |
| `tests/unit/application/` | Use case phối hợp port ra sao, dùng bản giả ở `tests/fakes/` |
| `tests/unit/agents/` | Từng node, từng nhánh của graph |
| `tests/contract/` | Response thật có khớp OpenAPI không |
| `tests/integration/` | Adapter với Postgres/Redis thật (cần `RUN_POSTGRES_INTEGRATION=1`) |
| `tests/architecture/` | Quy tắc import giữa các lớp |

```bash
python -m pytest -q src/backend/tests                       # không cần Postgres; integration tự skip
python -m pytest -q src/backend/tests/unit/application/test_engines.py  # chỉ phần đang đọc
```

`tests/fakes/` còn cho thấy **port tối thiểu cần gì**: bản giả là hiện thực ngắn nhất của một port.

## 8. Mẹo tìm nhanh

```bash
grep -rn "app.state.search" src/backend/app                       # ai gắn / ai đọc một use case
grep -rln "CdpClient" src/backend/app                              # ai dùng một port
grep -rn "@router\.\(get\|post\|put\)" src/backend/app/api         # toàn bộ endpoint
```

Chạy backend rồi mở `http://localhost:8000/docs` để thử endpoint; `GET /api/v1/assistant/status` cho biết
LLM đang `live`, `disabled` hay `unavailable`.

## 9. Trước khi sửa: tự trả lời năm câu

1. Thay đổi phục vụ mã FR/NFR nào?
2. Có đổi request/response không? Có thì sửa `src/shared/contracts/` **trước**.
3. Code mới thuộc lớp nào? Rule thuần → `domain`; điều phối → `application`; SDK/DB/HTTP → `infrastructure`.
4. Cần port mới không? Có thì một file mới trong `application/ports/`, nối adapter ở `main.py`, bản giả ở
   `tests/fakes/`.
5. Có lệch PRD không? Có thì viết đề xuất ở `docs/prd/update/` và chờ chốt (`AGENTS.md` §8).

## 10. Frontend — tóm tắt

Cùng cách tiếp cận, khác bản đồ:

1. `src/frontend/README.md`, `docs/prd/user-flow.md` (route table).
2. `src/frontend/src/app/` — trang và route handler. `app/api/` là BFF: giữ cookie phiên, gắn Bearer khi gọi
   FastAPI; trình duyệt không bao giờ thấy JWT.
3. `src/frontend/src/features/<feature>/` — component, hook, state của từng nghiệp vụ.
4. `src/frontend/src/services/` — mọi HTTP call; kiểu dữ liệu sinh từ OpenAPI.

Quy tắc đầy đủ ở `docs/prd/architecture.md` §6.2.
