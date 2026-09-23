# Nối tool Itinerary Agent với Search và Recommendation backend

- Ngày: 2026-09-22
- Tác giả: người dùng / Codex
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: backend, agent, contract, docs

## Mục tiêu

Cho hai tool planner `search_products` và `get_recommendations` dùng các endpoint RecSys thật trong
Backend, thay vì chỉ chạy fixture. Giữ input `query` của tool nhưng gọi GET `/api/v1/search?q=...`,
forward JWT chỉ cho Recommendation, và trả đủ dữ liệu catalog để Agent không cần Product Detail.

## File thay đổi

- `.env.example` — sửa: thêm cấu hình JWT HS256, không chứa secret thật.
- `src/shared/contracts/paths/search.yaml` — sửa: thêm GET `/search?q=...` vào OpenAPI; giữ POST v1 để tương thích ngược.
- `docs/spec/hop-dong-tich-hop-backend.md` — sửa: mô tả GET compatibility endpoint và POST v1 còn được giữ.
- `docs/spec/hop-dong-tich-hop-itinerary-assistant.md` — sửa: mô tả request Search thật mà Agent gọi.
- `src/backend/README.md` — sửa: cập nhật Recommendation JWT và cách bật HTTP data mode.
- `src/backend/requirements.txt` — sửa: thêm PyJWT.
- `src/backend/app/core/config.py` — sửa: thêm `JWT_SECRET` và thuật toán HS256.
- `src/backend/app/core/security.py` — thêm: xác minh Bearer JWT và claim `cdp_user_id`, fail closed.
- `src/backend/app/domain/catalog/models.py` — sửa: giữ currency/ngày availability và dẫn xuất `priceUnit`.
- `src/backend/app/infrastructure/vectors/postgres_store.py` — sửa: nạp các trường catalog cần cho payload giàu.
- `src/backend/app/application/search/use_cases.py` — sửa: trả projection đầy đủ và clamp score vào `[0,1]`.
- `src/backend/app/application/recommendation/use_cases.py` — sửa: lọc theo destination, trả projection đầy đủ và `daysAgo` integer.
- `src/backend/app/api/v1/routes/search.py` — sửa: thêm latency engine vào response.
- `src/backend/app/api/v1/routes/recommendations.py` — sửa: lấy user từ JWT, nhận destination, thêm `cdpUserId`/latency.
- `src/backend/app/application/itinerary/tool_contracts.py` — sửa: tool dùng response GET nhưng giữ `SearchRequest` giàu cho planner.
- `src/backend/app/application/ports/itinerary_tools.py` — sửa: khai báo capability Catalog của executor.
- `src/backend/app/infrastructure/clients/itinerary_http_clients.py` — sửa: ánh xạ `query` sang `q`, chỉ gửi filter GET hỗ trợ.
- `src/backend/app/infrastructure/clients/itinerary_fixture_clients.py` — sửa: khai báo fixture có Catalog capability.
- `src/backend/app/agents/tools/itinerary_gateway.py` — sửa: công khai capability Catalog cho graph.
- `src/backend/app/agents/nodes.py` — sửa: không gọi danh sách điểm đến khi HTTP client không có Catalog API.
- `src/backend/app/api/v1/routes/assistant.py` — sửa: chỉ tiêm Catalog port khi client thực sự hỗ trợ.
- `src/backend/tests/unit/agents/test_itinerary_tools.py` — sửa: khóa method GET, ánh xạ query, auth và filter compatibility.
- `src/backend/tests/unit/test_engines.py` — sửa: kiểm payload giàu, score/reason và destination Recommendation.
- `src/backend/tests/unit/test_security.py` — thêm: kiểm JWT hợp lệ, hết hạn, sai chữ ký, thiếu cấu hình và route auth.
- `src/backend/tests/unit/test_recsys_agent_integration.py` — thêm: kiểm adapter → endpoint backend → gateway contract.
- `history/2026-09-22-noi-agent-voi-recsys-backend.md` — thêm: entry này.

## Quyết định

- Giữ `search_products(query=...)` ở bề mặt planner; HTTP adapter là nơi duy nhất đổi sang `q`.
- GET `/search` chỉ nhận `q`, taxonomy, destination, limit, offset. Giá, sao và availability tiếp tục
  được Agent hậu kiểm trên payload giàu; không âm thầm tuyên bố backend GET đã áp các filter đó.
- Giữ POST `/search` trong OpenAPI v1 vì xóa/đổi method là breaking change; GET được thêm như compatibility surface.
- Search không nhận JWT từ Agent. Recommendation chỉ dùng `cdp_user_id` từ JWT đã xác minh; token lỗi
  không được rơi về anonymous. Thiếu secret chỉ ảnh hưởng request có Authorization.
- HTTP RecSys client không giả vờ có Catalog API. Hai endpoint trả đủ `description`, `attributes`,
  currency, price unit và ngày availability nên hydration không phát sinh Product Detail.
- Fixture vẫn là mặc định development/test; dùng backend thật phải bật `ITINERARY_DATA_MODE=http`.
- Không chạm thay đổi Data đang có trong `src/data_collection/README.md`, `.claude/` hoặc entry history untracked của task khác.

## Kiểm tra

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python src/shared/contracts/tests/validate_contract.py`: PASS — 70 schema, 50 fixture và negative checks.
- Test tập trung tool/engine/JWT/integration: **29 passed, 1 deselected**; case deselected là graph test đã có lịch sử treo.
- `compileall` backend: PASS; file cache tracked bị chạm đã được khôi phục về HEAD.
- `git diff --check`: PASS.
- `test_assistant_contract.py` có 1 test in dấu `.` rồi không teardown; lệnh bị timeout sau 30 giây (exit 124). Không ghi nhận pass cho suite này.
- Suite unit gộp cũng bị timeout ở teardown/invocation đã biết; không dùng output dấu chấm làm bằng chứng pass.
- PostgreSQL container đang healthy; `RUN_POSTGRES_INTEGRATION=1 ... test_local_postgres_adapters.py`
  không in kết quả và bị timeout sau 60 giây (exit 124), nên chưa có bằng chứng integration pass.
- Chưa chạy live Uvicorn với model embedding/LLM thật.

## Còn lại / rủi ro

- POST `/search` được giữ trong contract v1 nhưng route RecSys hiện hành vẫn chỉ triển khai GET; hoàn thiện toàn bộ semantics POST là việc tương thích Web riêng.
- GET compatibility endpoint chưa áp price/star/sort/includeVariants; ranking có thể không lấy đủ candidate trước khi Agent hậu kiểm.
- JWT verifier cần dùng cùng `JWT_SECRET` với Auth backend; module Auth phát hành token chưa tồn tại trong checkout này.
- Chưa có bằng chứng latency hoặc chất lượng ranking trên catalog PostgreSQL thật.
