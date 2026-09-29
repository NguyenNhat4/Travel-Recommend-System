# Tool Similar (`get_similar_products`) cho Itinerary Agent ở lượt đổi món

- Ngày: 2026-09-29
- Tác giả: tqanh123 / Claude Code
- Nhánh: bench/embed-search
- Trạng thái: hoàn thành
- Phạm vi: agent, backend, contract, docs, evaluation, frontend
- Đề xuất: docs/prd/update-archive/2026-09-28-tool-similar-cho-agent.md

## Mục tiêu

Phase B của plan đã duyệt, làm sau khi người dùng chốt P-B ngày 2026-09-29. PRD đã được áp dụng trước, xem `2026-09-29-ap-dung-de-xuat-agent-goi-engine-va-tool-similar.md`.

Khi người dùng muốn đổi một sản phẩm đã hiển thị mà không nêu tên thay thế ("đổi khách sạn khác giống cái này"), planner có thêm tool thứ ba `get_similar_products`, lấy từ `GET /products/{productId}/similar` (`same_taxonomy`). Sản phẩm gốc chỉ lấy từ lịch trình lượt trước, được lưu phía server.

Mã phục vụ: FR-AGT-02, FR-AGT-05, FR-SRC-04, FR-AGT-04, NFR-REL-01 (grounding 100%), NFR-PERF-03.

Mục 5 "Quy tắc của tool" và mục "Thay đổi source sau khi chốt" của P-B là ràng buộc.

## File thay đổi

Các file đã có trong entry `2026-09-28-*` được đánh dấu "(lần nữa)". Mô tả của các file đó chỉ nói phần Phase B.

**Contract**

- `src/shared/contracts/paths/catalog.yaml` — sửa: `getSimilarProducts` khai báo thêm `400`, `409`, `503` (`responses/Error`), cạnh 200/404/500 sẵn có. Không đổi schema.
- `src/shared/contracts/schemas/catalog.yaml` — sửa: chỉ mô tả `SimilarProductsResponse.strategy`. Mô tả nay nói `cross_taxonomy` có trong schema nhưng route chưa hiện thực (luôn trả `same_taxonomy`), và Agent chỉ dùng `same_taxonomy` ở lượt đổi món. Enum và default giữ nguyên.
- `src/shared/contracts/openapi.yaml` — sửa: `info.version` 1.8.0, số chung cho cả đợt (xem Quyết định).
- `src/frontend/src/types/api.gen.ts` — sửa (lần nữa): sinh lại bằng `npm run generate:api-types`. Phần của Phase B chỉ là `400`, `409`, `503` ở `operations.getSimilarProducts.responses` và JSDoc của `strategy`.

**Backend: tool, port, adapter, nối dây**

- `src/backend/app/application/itinerary/tool_contracts.py` — sửa: thêm hằng `SIMILAR_PRODUCTS = "get_similar_products"`, map tới `("/products/{productId}/similar", "get")`. Tham số GET nay lấy cả `in: query` lẫn `in: path`, nên tool có `productId` bắt buộc, `limit` 1–20 (mặc định 8) và không nhận khoá lạ.
- `src/backend/app/application/ports/itinerary_tools.py` — sửa: thêm Protocol `SimilarProductsPort.get_similar_products(product_id, limit)`. `ToolExecutorPort` không đổi.
- `src/backend/app/application/itinerary/engine_tools.py` — sửa (lần nữa):
  - `supports_similar = True`, và provider bắt buộc `similar_products`.
  - `get_similar_products` chạy qua `_guard` và trả thêm `requestId` giống route.
  - Provider None → 503 retryable. `CatalogError` giữ nguyên code.
  - Comment ghi ngoại lệ đã chấp nhận: use case chạy trên executor mặc định.
- `src/backend/app/infrastructure/clients/itinerary_http_clients.py` — sửa (lần nữa): `supports_similar = True`. Gọi `GET products/{quote(id, safe='')}/similar?limit=` và không gửi `Authorization`.
- `src/backend/app/infrastructure/clients/itinerary_fixture_clients.py` — sửa: `supports_similar = True`. `get_similar_products`:
  - chỉ trả sản phẩm cùng taxonomy và còn chỗ;
  - bỏ cả cụm của anchor (theo `attributes.parentProductId`);
  - xếp sản phẩm cùng điểm đến trước, `score` 1.0, tối đa `limit`;
  - id lạ → 404 `PRODUCT_NOT_FOUND`.
- `src/backend/app/agents/tools/itinerary_gateway.py` — sửa (lần nữa):
  - Tham số keyword `similar=None`; dispatch qua dict `_handlers`.
  - `definitions()` chỉ trả tool có handler.
  - Tool lạ hoặc chưa nối trả `TOOL_NOT_ALLOWED` trước khi chuẩn hoá hay ghi tham số.
- `src/backend/app/main.py` — sửa (lần nữa):
  - `_inprocess_itinerary_tools` truyền `similar_products=lambda: getattr(app.state, "get_similar_products", None)`.
  - `_itinerary_runtime` truyền `similar=` khi adapter khai báo `supports_similar`.
  - `version="1.8.0"`.

**Backend: planner, retrieval, đánh giá**

- `src/backend/app/agents/steps/tool_planning.py` — sửa (lần nữa):
  - `_planner_input` chỉ mời Similar khi lượt có `previous_selection` và gateway có port Similar. Khi mời thì nối `SIMILAR_HINT` và thêm khoá `previous_selection` (`productId`, `name`, `taxonomy`) vào payload.
  - `validated_plan(..., offered=)` làm theo thứ tự:
    1. Lọc lời gọi Similar trước khi đếm độ dài: anchor phải có trong `previous_selection`, khử trùng, tối đa 2 lời gọi, log lý do.
    2. Plan chỉ có anchor bịa → một search theo điểm đến.
    3. Plan quá 5 lời gọi vì Similar → bỏ Similar cuối.
    4. `destination` chỉ chèn vào tool có khai báo tham số đó; `limit` của Similar cố định.
    5. `get_recommendations` bắt buộc được xếp chỗ trước.
    6. Lưới an toàn: thêm search cho mỗi loại đang đổi.
    7. Đánh số lại id.
  - Plan đã lưu chạy lại mà không gọi `definitions()`.
- `src/backend/app/agents/steps/prompts.py` — sửa: thêm `SIMILAR_HINT`, chỉ nối sau `TOOL_PLAN_PROMPT` ở lượt đổi món, và nói rõ Similar tính vào trần 5 lời gọi. `TOOL_PLAN_PROMPT` không đổi.
- `src/backend/app/agents/steps/evaluation.py` — sửa: `tool_errors` bỏ lỗi mềm của Similar.
  - `SIMILAR_NO_ALTERNATIVE` (404, 409) luôn mềm.
  - `_similar_unavailable` (`SEARCH_UNAVAILABLE`, `TOOL_TIMEOUT`, mọi 5xx, `TOOL_HTTP_ERROR` không có `httpStatus`) mềm khi có `search_products` trả dữ liệu.
- `src/backend/app/application/itinerary/retrieval.py` — sửa: `collect` bỏ lặng lẽ kết quả Similar lệch điểm đến, trước khi tính lý do loại. Tách hàm `_off_destination`.
- `src/backend/README.md` — sửa (lần nữa): dòng lớp `agents`, bảng `ITINERARY_DATA_MODE` thêm Similar, và một đoạn ngắn về tool thứ ba.

**Evaluation**

- `src/evaluation/agent/golden.py` — sửa (lần nữa):
  - `build_runtime` truyền `similar=clients`.
  - Thêm khoá `expect` mới `toolsInclude` vào `EXPECT_KEYS`, và tham số `planned_tools` cho `dataset_findings` (tên tool trong `tool_plan` cuối của lượt). `run_case` truyền giá trị này vào.
- `src/evaluation/agent/cli.py` — sửa: lệnh itinerary truyền `similar=clients`.
- `src/evaluation/datasets/itinerary_agent_golden.yaml` — sửa: thêm G-076 (`multi_turn`, FR-AGT-02/04/05), đặt cuối file. Lượt 2 là "đổi sang khách sạn khác tương tự khách sạn này" và kỳ vọng:
  - `COMPLETED` và có chỗ ở;
  - không lặp lại chỗ ở của lượt 1;
  - không có warning `PRODUCT_DROPPED_DESTINATION`;
  - `toolsInclude: [get_similar_products]`.
- `src/evaluation/tests/test_golden.py` — sửa: đếm 76 case, thêm test `toolsInclude`, và test G-076 có kỳ vọng Similar.

**Test backend**

- `src/backend/tests/contract/test_catalog_contract.py` — sửa: 400 (`limit` 0 và 21), 409 `PRODUCT_NOT_INDEXED` và 503 `SEARCH_UNAVAILABLE` đều qua `assert_contract`.
- `src/backend/tests/contract/test_assistant_contract.py` — sửa (lần nữa): truyền `similar_products=lambda: None` cho `InProcessItineraryTools`.
- `src/backend/tests/unit/agents/test_itinerary_tools.py` — sửa (lần nữa):
  - ContractTests: ba tool, `limit`, `productId`.
  - HttpTests Similar: URL-encode, không gửi `Authorization`, 409/404/503.
  - GatewayTests: dispatch và `TOOL_NOT_ALLOWED`.
  - SimilarPlanTests: anchor, trần lời gọi, lưới an toàn theo loại, idempotent.
  - SimilarEvaluationTests: lỗi mềm, gồm 5xx ở mode http qua MockTransport.
- `src/backend/tests/unit/agents/test_itinerary_runtime.py` — sửa:
  - `ScriptedLlm` ghi lại tool và prompt; `run_graph` nối `similar=` theo `supports_similar`.
  - Lượt đầu không có Similar, lượt đổi món thì có.
  - Lượt đổi món ra stay mới, grounded, nguồn `SEARCH`.
  - Similar 503 hoặc timeout không bị retry.
  - Similar `PRODUCT_NOT_INDEXED` vẫn ra stay nhờ lưới an toàn.
- `src/backend/tests/unit/agents/test_recsys_agent_integration.py` — sửa (lần nữa): `inprocess_tools()` truyền `similar_products` (use case `GetSimilarProducts`, như `main.py`).
- `src/backend/tests/unit/application/test_itinerary_engine_tools.py` — sửa (lần nữa):
  - Parity route / `ItineraryHttpClients` / in-process cho Similar.
  - 404 và 409.
  - Provider None và engine None → 503 retryable.
  - Log không chứa anchor id.
- `src/backend/tests/unit/application/test_itinerary_retrieval.py` — thêm:
  - Kết quả Similar lệch điểm đến bị bỏ lặng lẽ; kết quả cùng điểm đến thành candidate nguồn `search`.
  - Các luật loại khác giữ nguyên.
  - Kết quả thiếu trường chi tiết được hydrate.
- `src/backend/tests/unit/infrastructure/test_itinerary_fixture_similar.py` — thêm: Similar của fixture cùng taxonomy, bỏ cả cụm, cùng điểm đến trước, tôn trọng `limit`, id lạ → 404.
- `src/backend/tests/unit/api/test_backend_wiring.py` — sửa (lần nữa): gateway ở mode `inprocess` có `get_similar_products`, provider đọc `app.state` mỗi lần gọi, và việc nối dây theo cờ `supports_similar`.

**Spec và tài liệu**

- `docs/spec/hop-dong-tich-hop-itinerary-assistant.md` — sửa (lần nữa):
  - "Cập nhật" 2026-09-29.
  - §1.1; §2 (ba tool, `TOOL_NOT_ALLOWED`, bảng adapter).
  - §2.5 mới: endpoint, quy tắc mời, anchor, giới hạn, lưới an toàn, lỗi mềm, kết quả, bảng ba mode.
  - §5.1 nguồn grounding; §6; §7.2.
- `docs/spec/hop-dong-tich-hop-search-recommendation.md` — sửa (lần nữa): §1.2 Team Agent dùng `/products/{productId}/similar` (`same_taxonomy`) ở lượt đổi món. §3.6 ghi `cross_taxonomy` chưa hiện thực và Agent không dùng.
- `docs/spec/hop-dong-tich-hop-backend.md` — sửa (lần nữa): §1.2 Team Agent gọi cả Similar (chỉ ở lượt đổi món). §4.3 thêm lỗi `limit` ngoài 1–20 → `400 VALIDATION_ERROR`.
- `docs/spec/agent/langgraph-nodes.md` — sửa: §6 và §6.1 (node `tool`, `evaluate`, `finalize`) theo Similar.
- `docs/spec/agent/state-fields.md` — sửa: các dòng `previous_selection`, `sources`, `tool_plan`, `tool_results`.
- `docs/spec/agent/working-context.md` — sửa (lần nữa): fragment contract của Similar, bảng tune, adapter http, bất biến.
- `docs/spec/agent/README.md` — sửa (lần nữa): 75 → 76 case.
- `docs/spec/agent/golden-run.md` — sửa (lần nữa): 76 case (91 lượt).
- `docs/spec/agent/evaluation-plan.md` — sửa: 75 → 76 case.
- `docs/spec/agent/golden-dataset-how-to-add-more-case.md` — sửa: thêm khoá `toolsInclude`; `multi_turn` 11 → 12 kèm G-076.

## Quyết định

**Khi nào mời tool và anchor**

- Chỉ mời ở lượt đổi món. Tool, `SIMILAR_HINT` và khoá `previous_selection` chỉ có khi `previous_selection` khác rỗng và gateway có port Similar. Lượt đầu giữ nguyên bộ tool, prompt và bốn khoá payload như trước; runtime test khoá điều này.
- `previous_selection` chỉ đến từ ConversationStore phía server.
- Anchor ngoài danh sách đó bị bỏ. Log `itinerary.tool_plan.similar_dropped requestId= reason=` chỉ ghi lý do (`not_offered`, `unknown_anchor`, `duplicate_anchor`, `similar_limit`, `call_budget`), không ghi id.

**`limit` và trần lời gọi**

- `limit` cố định ở mức tối đa của contract (20), đọc từ `contracts()`. Engine không lọc theo điểm đến và kết quả lệch điểm đến bị bỏ sau truy xuất, nên lấy nhiều nhất có thể.
- `MAX_SIMILAR_CALLS = 2`, khử trùng theo anchor, vẫn trong `MAX_CALLS = 5`.
- Sửa sau review: trước đây plan quá 5 lời gọi vì Similar ném `INVALID_TOOL_PLAN`, và lượt thành 503 `LLM_UNAVAILABLE`. Nay server bỏ Similar cuối cho tới khi vừa trần. Plan quá trần mà không có Similar vẫn sai như trước. `SIMILAR_HINT` nói Similar tính vào trần; `TOOL_PLAN_PROMPT` không đổi.

**Lưới an toàn (sửa sau review)**

- P-B §5 ghi "plan luôn giữ một lời gọi `search_products` cho loại đang đổi". Bản đầu chỉ bảo đảm có một `search_products` bất kỳ. Review đã chạy thử: plan `[similar(khách sạn), search(attraction)]` gặp Similar lỗi 409 thì ra `COMPLETED` nhưng không có chỗ ở.
- Nay, khi planner đề xuất Similar (kể cả lời gọi đã bị bỏ), mỗi loại đang đổi phải có search cùng loại hoặc search không lọc loại. Loại lấy từ `previous_selection`, bỏ loại người dùng đã loại trừ. Thiếu thì server thêm `search_products(query=<điểm đến>, taxonomy=<loại>)` tất định, qua `_validated_args` (nên với khách sạn thì áp cả `priceMax`/`starRatingMin`).
- Search không lọc loại được tính là đã phủ, vì đó là tìm theo điểm đến trên mọi loại. Cả hai reviewer đều đề xuất như vậy.
- Ưu tiên khi thiếu chỗ:
  - `get_recommendations` bắt buộc (request có JWT) được xếp chỗ trước.
  - Search của lưới an toàn cần chỗ thì Similar nhường.
  - Hết chỗ mà không còn Similar để bỏ thì search theo loại bị bỏ qua. Plan lúc đó giống plan không có Similar, nên không huỷ lượt.
  - Plan không còn `search_products` nào mà hết chỗ thì vẫn là `INVALID_TOOL_PLAN`.
- Anchor bịa không cho biết loại: chỉ thêm một search theo điểm đến.
- Hệ quả: kiểm lại một plan đã kiểm cho ra đúng plan đó, và không plan nào hợp lệ khi bỏ Similar lại thành sai khi có Similar (xem mục Kiểm tra).

**Lỗi mềm**

- 404 `PRODUCT_NOT_FOUND` và 409 `PRODUCT_NOT_INDEXED` luôn mềm.
- 503 `SEARCH_UNAVAILABLE` và `TOOL_TIMEOUT` mềm khi có `search_products` trả dữ liệu.
- Sửa sau review, cho mode `http`: route Similar ném lỗi bất ngờ thì Starlette trả 500 dạng text. Adapter đọc thành `INVALID_TOOL_RESPONSE` kèm `httpStatus` 500, không retry, nên lượt đổi món rơi vào `FALLBACK`. Lỗi kết nối thì thành `TOOL_HTTP_ERROR`.
  - Hai loại này nay được coi như `SEARCH_UNAVAILABLE`, giống cách mode `inprocess` map lỗi engine. Lý do: P-B nêu mục đích "similar hỏng không đẩy lượt đổi món sang thử lại rồi `FALLBACK`".
  - Chọn sửa ở `evaluation.py` thay vì adapter, để hành vi http của search/recommendation giữ nguyên như quyết định của P-A.
  - Response 2xx sai hợp đồng vẫn là lỗi vĩnh viễn.

**Kết quả và grounding**

- Kết quả Similar mang nhãn `ItemSource.SEARCH`; không thêm giá trị enum.
- Kết quả lệch điểm đến bị bỏ lặng lẽ, trước khi tính lý do loại. Vì vậy kết quả lệch điểm đến nằm trong `exclude_products` cũng không sinh `PRODUCT_DROPPED_EXCLUDED`.
- Grounding không đổi: tên, giá, `productId` lấy nguyên từ kết quả engine.
- `compose` không đổi (câu hỏi mở 1). Vì lưới an toàn thêm search khách sạn, stay mới có thể đến từ search, không từ Similar. Runtime test kiểm rằng kết quả Similar cùng điểm đến thành candidate nguồn `search`, không kiểm rằng chúng thắng.

**Adapter, gateway, cấu trúc**

- `GetSimilarProducts` chạy trên executor mặc định, không dùng pool `itinerary-tool`. Đây là ngoại lệ đã chấp nhận (Decision 25): use case không embed, bị chặn bởi timeout Weaviate, và tối đa 2 lời gọi mỗi lượt. Có ghi ở spec §7.2.
- Gateway dispatch qua dict. Nối dây kiểm cờ tường minh `supports_similar`, không dùng `hasattr`.
- `InProcessItineraryTools.similar_products` là tham số bắt buộc như năm provider còn lại. Hai test cũ được cập nhật theo.
- Thêm tool theo cấu trúc `tool_contracts.py` hiện tại (câu hỏi mở 3, mặc định của P-B). Việc này nối dài chỗ lệch còn mở về vị trí code kiểm contract của itinerary, ghi ở `2026-09-23-tai-thiet-lap-cau-truc-backend.md` (hướng (a)/(b) chưa chọn).

**Contract và version**

- Chỉ khai báo thêm mã lỗi mà route đã trả, và sửa một mô tả. Đã sửa fragment trước, không sửa bundle (`AGENTS.md` §3).
- Cả đợt (entry `2026-09-28-recsys-strategy-enum-va-cdp-fallback.md`, `2026-09-28-agent-goi-engine-trong-tien-trinh.md` và entry này) tăng version một lần: 1.6.0 → 1.8.0, `main.py` phản chiếu cùng số (P-B §5 "tăng minor version"). Bỏ qua 1.7.0 vì `origin/release-mvp-v1` đã dùng số này cho thay đổi khác (commit `dbc22c1`, lưu hội thoại trợ lý).

**Golden**

- Thêm G-076 ở cuối file với id kế tiếp, theo `golden-dataset-how-to-add-more-case.md` §3/§7, không đặt ngay sau G-041. Comment trong YAML dẫn G-041 và P-B.
- Khoá `toolsInclude` mới để case đo được việc planner thật sự dùng Similar (review: không có khoá này thì G-076 vẫn pass khi thiếu cả tính năng). Khoá đọc `tool_plan` cuối của lượt, nên lời gọi bị server bỏ không được tính.

**Phạm vi không đổi**

- Route cũ `/similar/{product_id}` (`routes/search.py`) không đổi.
- Không có `cross_taxonomy`, không có tham số `destination` cho Similar, không có `ItemSource.SIMILAR`.
- `domain/` và `compose` không đổi. `tests/architecture/` không đổi.

## Kiểm tra

Tất cả lệnh chạy từ repo root, trừ nhóm frontend.

- `PYTHONUTF8=1 PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python src/shared/contracts/tests/validate_contract.py`: PASS — 83 schemas, all local refs, 50 grounded products, 4 itinerary statuses, negative checks, 64 existing fixtures; CDP clone 12 schemas, 7 fixtures, 11 negative checks. Chạy lại sau khi sửa mô tả `schemas/catalog.yaml`: vẫn PASS.
- `COVERAGE_FILE=<scratchpad> PYTHONUTF8=1 PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python -m coverage run -m pytest -q -p no:cacheprovider src/backend/tests src/evaluation/tests/test_golden.py -rfE`: 660 passed, 19 skipped trong 156,84 giây. Trước Phase B là 611 passed, 19 skipped. Trong các test có từ trước, chỉ đổi ba chỗ bắt buộc và không có assertion nào bị xoá hay nới:
  - số case golden 75 → 76;
  - tập tool 2 → 3 tên;
  - danh sách tham số sai được thêm ca của Similar.

  Trong test mới của Phase B, runtime test đổi món bỏ kiểm "stay mới nằm trong kết quả Similar" và thay bằng kiểm "kết quả Similar cùng điểm đến là candidate nguồn `search`" cộng "plan có search khách sạn". Lý do: sau khi sửa lưới an toàn, stay có thể đến từ search (xem Quyết định).
- Coverage (`coverage report --include=application/*,domain/*`):
  - `application/*` + `domain/*`: 95% (3075 stmts, 143 miss). `application/*` 95% (1822/97), `domain/*` 96% (1253/46). Đạt DoD ≥ 80%.
  - Theo file: `engine_tools.py` 100%, `prompts.py` 100%, `tool_contracts.py` 99%, `evaluation.py` 97%, `tool_planning.py` 95%, `itinerary_http_clients.py` 93%, `retrieval.py` 89%, `itinerary_gateway.py` 85%, `itinerary_fixture_clients.py` 75%.
  - Mọi dòng chưa phủ là đường cũ: listing lỗi, search theo loại bị loại trừ, plan không phải list, LLM lỗi, lỗi thực thi tool, `get_product_detail`/`get_recommendations` của fixture, helper catalog và `TimeoutError` của gateway. Nhánh mới của Phase B đều được phủ. File `.coverage` đã xoá.
- `git diff --quiet -- src/backend/tests/architecture`: không đổi; test kiến trúc xanh trong suite trên.
- Fuzz `validated_plan` (script ở scratchpad, không vào repo): 30.000 plan ngẫu nhiên, trộn Similar hợp lệ/bịa, search có hoặc không lọc loại, recommendation, `require_recommendations`, `offered` và `exclude_taxonomies`. Kết quả: 22.417 hợp lệ, 7.583 lỗi.
  - Mọi plan hợp lệ đều có ≤ 5 lời gọi và ≤ 2 Similar, có `get_recommendations` khi bắt buộc, và có `search_products` khi plan gốc có Similar.
  - Kiểm lại cho ra đúng plan đó.
  - 0 trường hợp plan hợp lệ khi bỏ Similar lại thành sai khi có Similar.
  - 582 trường hợp thiếu search theo loại, và tất cả đều là plan đủ 5 lời gọi, không còn Similar.
- `cd src/frontend && npm run generate:api-types`: OK (openapi-typescript 7.13.0). So với bản ngay trước, chỉ khác một dòng JSDoc của `strategy`. Trước đó unit contract đã thêm `400`/`409`/`503`, 3 dòng.
- `npm run typecheck`: exit 0. `npm run lint`: 0 lỗi, 4 cảnh báo `react-hooks/exhaustive-deps` có sẵn. `npm run test`: 20 file, 119 test passed.
- `npm run build` do bước verify chạy trước khi sửa mô tả: exit 0. `next-env.d.ts` đã khôi phục, `dist-api/` đã xoá. Sau đó chỉ đổi một chuỗi mô tả nên không chạy build lại.
- Bước verify grep diff Phase B: không có `print`/`breakpoint`. Các dòng log mới (`itinerary.tool_plan.similar_dropped`, `itinerary.tool`, `itinerary.tool.timeout`, `itinerary.tool.unavailable`) không ghi anchor id, tham số hay token; test kiểm anchor id không có trong `caplog`.
- Chưa chạy: G-076 và golden runner trên catalog thật, và một lượt đổi món thật (inprocess, Postgres đã seed, Weaviate, Cohere, LLM thật). Máy này không có Postgres local và Docker.

## Còn lại / rủi ro

- Câu hỏi mở 1 của P-B: compose chưa ưu tiên kết quả Similar cho ô đang đổi. Nay càng rõ hơn, vì lưới an toàn thêm search cùng loại và compose chọn rẻ nhất trên cả hai nguồn. G-076 với `toolsInclude` đo được planner có dùng Similar không, nhưng không đo được Similar có thắng không. Muốn làm thì cần đề xuất mới.
- Câu hỏi mở 2: tham số `destination` hoặc chế độ `cross_taxonomy` cho Similar — để sau.
- Chạy tay với dữ liệu thật, rồi chạy golden (`python -m src.evaluation.agent.golden`) và xem G-076 lượt 2: tỉ lệ planner gọi Similar, stay có đổi không, độ trễ Similar.
- Reviewer cần duyệt trước khi merge:
  - Web + Backend + Agent: spec itinerary §2.5, planner, gateway, evaluation.
  - Team Recommendation/Search: spec search-rec §1.2/§3.6, mô tả `strategy` trong `schemas/catalog.yaml`, mã 400/409/503.
  - Backend Core: nối dây trong `main.py`.
  - AI Agent team: `agents/`, và `toolsInclude` trong golden.
- Commit: nhiều file dùng chung giữa các entry (`engine_tools.py`, `main.py`, gateway, test, spec, `api.gen.ts`) nên không tách commit theo từng entry; đợt này commit thành hai: PRD và đề xuất (entry áp dụng PRD), rồi code, contract, spec cùng ba entry còn lại.
- Fixture search bỏ qua `includeVariants` (có sẵn, ngoài phạm vi). Vì vậy trong fixture, lượt đổi khách sạn có thể chọn một hạng phòng của chính khách sạn cũ, lấy từ search của lưới an toàn. Engine thật chỉ trả tầng cha khi `includeVariants=false`.
- `?limit=abc` trên `/products/{productId}/similar` trả 422 `VALIDATION_ERROR` mà operation chưa khai báo. Đây là chỗ hở có sẵn ở các operation catalog khác, ngoài phạm vi P-B.
- File `.pyc` được track (`src/shared/contracts/scripts/__pycache__/…`) bị ghi lại nếu chạy Python không có `PYTHONDONTWRITEBYTECODE=1`. Hiện vẫn sạch.
- Lệch có sẵn: `ITINERARY_TOOL_TIMEOUT_SECONDS` mặc định 10 s trong `core/config.py` nhưng 1 s trong `.env.example` và `docker-compose.yml`. Similar cũng chịu timeout này.
