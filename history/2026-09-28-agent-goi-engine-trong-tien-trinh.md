# Itinerary Agent gọi engine Search/Recommendation trong tiến trình

- Ngày: 2026-09-28
- Tác giả: tqanh123 / Claude Code
- Nhánh: bench/embed-search
- Trạng thái: hoàn thành
- Phạm vi: agent, backend, contract, docs, evaluation
- Thay thế: 2026-09-22-noi-agent-voi-recsys-backend.md

## Mục tiêu

Với dữ liệu thật (`ITINERARY_DATA_MODE=http`), adapter `ItineraryHttpClients` gọi ngược `/api/v1/search`, `/recommendations`, `/destinations` của chính Backend, trong khi các engine đã nằm trên `app.state` cùng tiến trình. Người dùng muốn agent gọi thẳng engine như tool (FR-AGT-02, FR-AGT-04), giữ grounding 100% (NFR-REL-01, AC-AGT-01), không lộ token (NFR-SEC-01) và đúng phân lớp (NFR-MAINT-01/02). Entry này là Phase 0/A của plan đã duyệt; tool Similar (Phase B) chờ đề xuất P-B (xem `2026-09-28-de-xuat-agent-goi-engine-trong-tien-trinh.md`).

## File thay đổi

- `src/backend/app/application/itinerary/engine_tools.py` — thêm: `InProcessItineraryTools`, hiện thực port `itinerary_tools` bằng cách gọi engine qua provider đọc lại mỗi lời gọi; một hàm `_guard` map lỗi; kết quả round-trip JSON.
- `src/backend/app/application/auth/bearer.py` — thêm: `bearer_token`, `verified_principal`, `principal_from_header`, resolver Bearer duy nhất dùng chung cho route và tool.
- `src/backend/app/application/recommendation/responses.py` — thêm: `recommendation_response()` (thân lấy nguyên từ `_run` của route: `cdpUserId`, `diagnostics.latencyMs`).
- `src/backend/app/application/search/responses.py` — thêm: `search_tool_payload()` bỏ `cutoff` và `diagnostics`.
- `src/backend/app/application/catalog/views.py` — sửa: thêm `destination_list()`.
- `src/backend/app/api/deps.py` — sửa: `optional_principal`/`current_principal` gọi `application/auth/bearer.py`; xoá `_bearer`, `_verified`; tên và chữ ký giữ nguyên.
- `src/backend/app/infrastructure/auth/jwt_issuer.py` — sửa: docstring `verify` ghi điểm 9 (jti thu hồi) nay kiểm ở `application/auth/bearer.py`, dùng chung cho dependency HTTP và tool itinerary.
- `src/backend/app/api/v1/routes/recommendations.py` — sửa: hai route dùng `recommendation_response`; xoá `_run`.
- `src/backend/app/api/v1/routes/catalog.py` — sửa: `/destinations` dùng `destination_list`, vẫn trả `[]` khi index None.
- `src/backend/app/infrastructure/clients/itinerary_http_clients.py` — sửa: dùng `search_tool_payload`; sửa comment cũ sai về `/products/{id}`.
- `src/backend/app/core/config.py` — sửa: `itinerary_data_mode` thêm `inprocess`.
- `src/backend/app/main.py` — sửa: `ITINERARY_TOOL_WORKERS = 40`, helper `_inprocess_itinerary_tools`, nhánh `mode == "inprocess"` (pool riêng, đóng qua exit stack); kèm hai dòng của entry `2026-09-28-recsys-strategy-enum-va-cdp-fallback.md` (`PostgresCdpReader(..., timeout_seconds=...)`, `version="1.8.0"`).
- `src/backend/app/agents/tools/itinerary_gateway.py` — sửa: mỗi lời gọi kết thúc ghi một dòng INFO `itinerary.tool requestId= name= outcome= code= retryable= durationMs=`, không log tham số hay dữ liệu.
- `src/backend/app/agents/steps/tool_planning.py` — sửa: `run_calls` log WARNING `itinerary.tool.timeout requestId= name=` khi quá hạn.
- `src/evaluation/agent/golden.py` — sửa: biên bản ghi cứng `"dataMode": "http"` vì runner luôn dùng `ItineraryHttpClients`; docstring nói backend chạy `inprocess` (hoặc `http`, không `fixture`).
- `src/shared/contracts/schemas/itinerary-agent.yaml` — sửa: `AssistantStatus.dataMode` thêm `inprocess` và mô tả bốn mode.
- `src/shared/contracts/paths/search.yaml` — sửa: chỉ mô tả của GET/POST `/search`, bỏ câu "Agent gọi endpoint này", ghi rằng agent không gắn danh tính khi tìm kiếm ở cả hai mode.
- `Makefile` — sửa: `chat` và `web` mặc định `ITINERARY_DATA_MODE=inprocess`; `backend-local` vẫn `fixture`.
- `.env.example` — sửa: comment liệt kê bốn mode và mặc định khi để trống; `ITINERARY_SERVICE_BASE_URL` chỉ dùng cho `http`. Giá trị không đổi.
- `docker-compose.yml` — sửa: chỉ thêm comment; compose vẫn `fixture`.
- `src/backend/tests/unit/application/test_itinerary_engine_tools.py` — thêm: parity ba chiều route / `ItineraryHttpClients` / in-process cho search, recommendations (khách và token P1), destinations, product detail (kể cả id lạ → 404); hot-swap A → B → None; map lỗi; 401 cho token ký bằng khoá lạ, token hỏng dạng, hết hạn, bị thu hồi, `Basic`; 401 thắng 503 khi engine chưa sẵn sàng; Redis lỗi → 503; header rỗng là khách; request id và tên thread trên pool; deep copy; kwargs search.
- `src/backend/tests/unit/application/test_auth_bearer.py` — thêm: None, `Basic`, `Bearer ` rỗng, không phân biệt hoa thường, token hợp lệ, bị thu hồi, giả, hết hạn.
- `src/backend/tests/unit/application/test_response_helpers.py` — thêm: ba helper hậu xử lý, kết quả qua schema `RecommendationResponse`, `SearchResponse`, `DestinationListResponse`.
- `src/backend/tests/unit/agents/test_recsys_agent_integration.py` — sửa: thêm biến thể in-process (graph grounded, provider None → 503 sau đúng một lần retry, token ký bằng khoá lạ → 401 và engine không chạy).
- `src/backend/tests/unit/api/test_backend_wiring.py` — sửa: lifespan mode `inprocess` cho đúng adapter, `product_count` theo `app.state`, engine chạy trên thread `itinerary-tool*`, sau khi lifespan đóng thì pool đóng và lời gọi lạc ra 503.
- `src/backend/tests/contract/test_assistant_contract.py` — sửa: `/assistant/status` hợp lệ `AssistantStatus` với cả bốn mode.
- `src/backend/tests/unit/agents/test_itinerary_tools.py` — sửa: log gateway không chứa tham số hay token; timeout có log `itinerary.tool.timeout`; `HttpTests` cũ giữ nguyên.
- `docs/spec/hop-dong-tich-hop-itinerary-assistant.md` — sửa: §1.1, §2 (bảng ba adapter), §2.1, §2.4 (strategy mới và JWT trong tiến trình), §4.1 dòng `dataMode`, §4.6 và §9 mục 9 (503 retryable là thay đổi có chủ đích), §5, §7.2 (pool, timeout), §7.3 (các dòng log), §11.
- `docs/spec/hop-dong-tich-hop-auth.md` — sửa: §3.5 resolver nằm ở `application/auth/bearer.py`, `api/deps.py` là lớp bọc HTTP, tool trong tiến trình dùng lại; §22.3 điểm 9 (jti thu hồi) chuyển sang `verified_principal`.
- `docs/spec/agent/working-context.md` — sửa: §2, §3 (ba adapter theo `ITINERARY_DATA_MODE`), §4 (dòng `engine_tools.py`), §6 (bất biến).
- `docs/spec/agent/README.md` — sửa: dữ liệu thật dùng `inprocess`; golden cần backend đã nạp RecSys ở `inprocess` hoặc `http`, runner luôn gọi qua HTTP.
- `docs/spec/agent/golden-run.md` — sửa: backend chạy `inprocess` (nên dùng) hoặc `http`, không `fixture`; mode backend chỉ quyết định `productCount`; kiểm sẵn sàng chấp nhận cả hai mode.
- `src/backend/README.md` — sửa: bảng bốn mode, cấu hình chạy dữ liệu thật, pool, các dòng log, cách quay về `http`; bỏ `JWT_SECRET`/`JWT_ALGORITHM=HS256` đã cũ.
- `history/2026-09-22-noi-agent-voi-recsys-backend.md` — sửa: chỉ thêm dòng `Bị thay thế bởi`.

Các đoạn transport trong `docs/spec/hop-dong-tich-hop-backend.md` (§1.2, §5.1), `hop-dong-tich-hop-search-recommendation.md` (§1.2, §3.2, §11), `hop-dong-tich-hop-cdp.md` (§1.4, §11) và `docs/spec/data-collection/bao-cao-schema.md` (§8.6) cũng thuộc entry này, nhưng các file đó được liệt kê ở entry `2026-09-28-recsys-strategy-enum-va-cdp-fallback.md`.

## Quyết định

- Thay quyết định của `2026-09-22-noi-agent-voi-recsys-backend.md` "dùng backend thật phải bật `ITINERARY_DATA_MODE=http`": dữ liệu thật nay dùng `inprocess`. `http` giữ làm mode phụ để hoàn tác; `fixture` vẫn là mặc định dev/test; ngoài dev/test không đặt thì vẫn `disabled` (quyết định 2 của người dùng, 2026-09-28). Các quyết định khác của entry cũ (tool giữ `query`, search không nhận danh tính, token hỏng không hạ thành khách) vẫn giữ.
- Adapter đặt ở `application/itinerary/engine_tools.py`: chỉ điều phối use case có sẵn, không SDK/DB/HTTP (`docs/prd/architecture.md` §6.3 mục 3); không đặt ở `agents/` (quy tắc 7) hay `infrastructure/clients/` (nơi của HTTP/fixture). `tests/architecture/` không sửa. Đề xuất P-A nhờ người review chốt rõ cách đọc dòng `infrastructure/ # LỚP 3: hiện thực port`.
- Engine lấy qua provider đọc `app.state` mỗi lời gọi, vì `RecsysRefresher` thay engine theo chu kỳ và itinerary clients được nối trước khi RecSys nạp xong. Tên `app.state.itinerary_http_clients` giữ nguyên, có comment.
- JWT: một resolver ở `application/auth/bearer.py`. Tool chỉ xác thực khi `get_recommendations` chạy, và kiểm token trước engine nên 401 thắng 503. Token hỏng → 401, không bao giờ hạ thành khách; header vắng hoặc rỗng → khách, giống http mode; kho thu hồi lỗi → 503 retryable. Token không vào state, log hay kết quả (NFR-SEC-01, `hop-dong-tich-hop-auth.md` §3.11).
- Engine đồng bộ chạy trên `ThreadPoolExecutor(40, thread_name_prefix="itinerary-tool")`; 40 bằng số token mặc định của anyio. Mỗi job chạy trong `contextvars.copy_context().run` để giữ request id. Exit stack đóng pool bằng `shutdown(wait=False, cancel_futures=True)`. Theo plan đã duyệt: không semaphore fail-fast, không deadline ContextVar cho Cohere, không log thread bị bỏ.
- Output khớp route nhờ helper dùng chung (`recommendation_response`, `search_tool_payload`, `destination_list`); test parity khoá điều này.
- `_guard`: `ToolError` giữ nguyên; `CatalogError` giữ code, retryable, status; engine None hoặc lỗi khác → `SEARCH_UNAVAILABLE` 503 retryable. Đây là thay đổi có chủ đích (quyết định 3 của người dùng): ở http mode cùng lỗi đó là 500 dạng text, agent đọc thành `INVALID_TOOL_RESPONSE` và không thử lại. Route công khai giữ hành vi cũ khi RecSys tắt.
- Sau review cuối, WARNING `itinerary.tool.unavailable` ghi thêm các frame traceback (file, dòng, mã nguồn) nhưng vẫn không ghi thông điệp lỗi, vì thông điệp có thể chứa câu truy vấn. Không có frame thì một bug của engine bị thử lại mà không để lại dấu vết nào.
- Quan sát thay cho access log: dòng `itinerary.tool` chỉ ghi khi lời gọi kết thúc trong hạn. Lời gọi quá hạn bị huỷ (`CancelledError`) trước dòng đó nên chỉ có `itinerary.tool.timeout`. Review cuối phát hiện spec, README và P-A ghi sai điều này; đã sửa chữ thay vì đổi code.
- Golden runner giữ đường HTTP (plan A7, golden chạy in-process nằm ngoài phạm vi). Sau review cuối, tài liệu golden bỏ yêu cầu backend phải chạy `http`: runner không phụ thuộc mode của backend, chỉ `productCount` của biên bản lấy từ `/assistant/status` (`inprocess` trả số sản phẩm, `http` trả `null`, `fixture` trả 50 nên không dùng).
- Contract chỉ thêm (`dataMode: inprocess`) và sửa mô tả `/search`; cập nhật fragment trước, không sửa bundle (`AGENTS.md` §3). Version 1.8.0 dùng chung cho cả đợt (entry Strategy và tool Similar).
- Không sửa `docs/guide/doc-code-backend.md` vì đề xuất `docs/guide` của nó còn chờ. `docs/spec/agent/golden-dataset-how-to-add-more-case.md:172` vẫn ghi backend chạy `http`, vẫn đúng nên không sửa.
- Chưa làm Phase B: không có tool `get_similar_products`, không đổi `tool_contracts.OPERATIONS` hay planner.

## Kiểm tra

- `PYTHONUTF8=1 PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python src/shared/contracts/tests/validate_contract.py`: PASS — 83 schemas, 64 existing fixtures; CDP clone 12 schemas, 7 fixtures, 11 negative checks.
- `PYTHONUTF8=1 PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python -m pytest -q -p no:cacheprovider src/backend/tests src/evaluation/tests/test_golden.py`: 611 passed, 19 skipped trong 107,56 giây (baseline 537 passed, 19 skipped).
- `git diff --quiet -- src/backend/tests/architecture`: không đổi; test kiến trúc chạy xanh trong suite trên.
- `ITINERARY_DATA_MODE=inprocess ... pytest src/backend/tests/unit/api src/backend/tests/contract src/backend/tests/unit/agents src/backend/tests/unit/application/test_itinerary_engine_tools.py`: 189 passed (test không phụ thuộc mode của môi trường, dù `make chat`/`make web` nay export `inprocess`).
- Test tập trung sau các sửa của review cuối (`test_itinerary_engine_tools.py`, `test_postgres_cdp_reader.py`, `test_backend_wiring.py`, `test_recsys_agent_integration.py`, `test_recommendation_cdp_fallback.py`, `tests/architecture`): 63 passed.
- Coverage (`coverage run -m pytest -q src/backend/tests`: 569 passed, 19 skipped): `application/*` + `domain/*` 95% (3060 stmts, 145 miss), đạt DoD ≥ 80%. Module mới/sửa: `application/itinerary/engine_tools.py` 100% (91/91), `application/recommendation/responses.py` 100% (9/9), `application/search/responses.py` 100% (5/5), `application/catalog/views.py` 100% (18/18); `application/auth/bearer.py` 100% (19/19, đo ở lượt coverage của bước verify, file không đổi sau đó). Ngoài phạm vi DoD (lượt verify): `api/deps.py` 94%, `agents/tools/itinerary_gateway.py` 83%, `agents/steps/tool_planning.py` 88%, `main.py` 88%, hai route 100%.
- Kiểm import thừa bằng AST trên mọi file `.py` mới/sửa (venv không có ruff/pyflakes): không có. Grep secret/debug trên toàn bộ diff: chỉ có DSN giả làm canary trong `test_postgres_cdp_reader.py`, không phải secret thật.
- Frontend (typecheck, lint, test, build) ghi ở entry Strategy vì `api.gen.ts` thuộc entry đó.
- Chưa chạy tay với dữ liệu thật (cần Postgres đã seed, Weaviate đã index, `COHERE_API_KEY`; máy này không có Postgres local và Docker daemon không chạy): chưa kiểm `/assistant/status` báo `inprocess`, log `itinerary.tool … outcome=ok` không kèm access log `/api/v1/search`, 503 sau một lần retry khi `WEAVIATE_URL` sai, `check_real_data_grounding.py`, và `ITINERARY_DATA_MODE=http make chat` cùng golden runner.

## Còn lại / rủi ro

- Reviewer cần duyệt trước khi merge: Web + Backend + Agent (spec itinerary, theo `hop-dong-tich-hop-backend.md` §9); Backend Core/Auth (spec auth, `application/auth/bearer.py`, `api/deps.py`, `main.py`); Team Recommendation/Search (các đoạn transport của spec search-rec); AI Agent team (`agents/`).
- Ops: khi RecSys chạy ổn trên VM, đặt `ITINERARY_DATA_MODE=inprocess` trong `/etc/vota/backend.env`. Hoàn tác: `ITINERARY_DATA_MODE=http` kèm `ITINERARY_SERVICE_BASE_URL`, hoặc `disabled`.
- Khi P-A "đã chốt": sửa PRD (`requirements.md` FR-AGT-02, `architecture.md` §2, `deployment-plan.md` §2), `git mv` đề xuất sang `docs/prd/update-archive/`, tạo entry mới. Nếu P-A bị từ chối: hoàn tác theo danh sách trong mục "Nếu bị từ chối" của P-A.
- Phase B (tool Similar) bị chặn tới khi P-B "đã chốt".
- Theo dõi sau, vì http mode hiện cũng gặp đúng vấn đề này: deadline theo ContextVar cho `CohereEmbedder`; semaphore fail-fast cho pool; chuyển `GetSimilarProducts` sang pool riêng. Thread đã bắt đầu vẫn chạy tiếp sau khi tool quá hạn (Cohere backoff, Weaviate timeout), giống thread route sync ở http mode.
- In-process thử lại cả những lỗi mà http mode không thử lại (thay đổi có chủ đích); test parity chỉ phủ đường thành công.
- Mặc định `ITINERARY_TOOL_TIMEOUT_SECONDS` lệch nhau: `core/config.py` 10.0, `.env.example` và `docker-compose.yml` 1. Timeout 1 giây có thể ngắn so với độ trễ Weaviate Cloud; đo qua log `itinerary.tool.timeout`, không dùng làm bằng chứng NFR-PERF.
