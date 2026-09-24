# RecSys truy vấn Weaviate top-K mỗi request

- Ngày: 2026-09-24
- Tác giả: nhatnm / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: backend, contract, spec, PRD (deployment-plan), frontend
- Đề xuất: `docs/prd/update-archive/2026-09-24-recsys-truy-van-weaviate-top-k.md` (chốt bởi nhatnm khi duyệt plan, 2026-09-24)

## Mục tiêu

Backend tải toàn bộ 3.183 vector từ Weaviate Cloud lúc khởi động, mất 453 giây, vượt ngưỡng 300 giây của `make web`, nên RecSys không lên. Chuyển sang truy vấn top-K mỗi request, đúng `docs/prd/architecture.md` §5 và NFR-PERF-03 (FR-SRC-02, FR-REC).

## File thay đổi

Tài liệu và contract:
- `docs/prd/update-archive/2026-09-24-recsys-truy-van-weaviate-top-k.md` — chuyển từ `docs/prd/update/`, trạng thái `đã áp dụng`.
- `docs/prd/deployment-plan.md` — §2: thêm biến `WEAVIATE_GRPC_PORT`.
- `docs/spec/hop-dong-tich-hop-search-recommendation.md` — §2.2–2.4 (FILTER → TOP-K → CUTOFF, bất biến tính trên tập ứng viên, mode `ANN_CANDIDATE_SCORE`), §3.4, §3.6, §7.1, S8 chốt hướng (b), §9 tiêu chí 2, 3, 10, 11.
- `docs/guide/doc-code-backend.md` — §4: search không còn giữ vector trong bộ nhớ.
- `src/shared/contracts/schemas/common.yaml` (mô tả `SearchMode`), `schemas/recommendations.yaml` (ghi chú `[C4]`), `schemas/search.yaml` (mô tả `approximate`). Không đổi field hay enum.
- `.env.example` — thêm `WEAVIATE_GRPC_PORT=50051`.

Backend:
- `src/backend/app/application/ports/vector_search.py` — thêm: `VectorSearchPort` (`near_vector`, `vectors`) và `VectorHit`.
- `src/backend/app/application/ports/unit_index.py` — bỏ ma trận `E`, thêm `allowed_ids(mask)`.
- `src/backend/app/application/ports/vector_store.py`, `ports/__init__.py` — `load()` trả `(UnitIndex, VectorSearchPort)`; export port mới.
- `src/backend/app/application/search/use_cases.py` — Search lọc id rồi gọi `near_vector` (`candidate_k`); Similar lấy vector anchor rồi gọi `near_vector`; hằng `ANN_DIAGNOSTICS`.
- `src/backend/app/application/recommendation/use_cases.py` — `_LocalSpace` đánh số lại vector event và ứng viên để dùng nguyên hàm domain; ứng viên = top-K quanh `u_short` và `u_long`, cộng `popular_k = 50` món có popularity cao nhất.
- `src/backend/app/domain/search/scoring.py`, `domain/search/__init__.py` — thêm `candidate_filter_score`.
- `src/backend/app/infrastructure/vectors/weaviate_store.py` — thêm `connect_weaviate` (client v4; cloud dùng `connect_to_weaviate_cloud`, còn lại `connect_to_custom` với cổng gRPC) và `WeaviateVectorSearch`. `WeaviateVectorStore.load` chỉ nạp metadata và kiểm số vector đúng model bằng aggregate. Giữ `WeaviateClient` REST cho job embed.
- `src/backend/app/infrastructure/vectors/numpy_search.py` — thêm: `VectorSearchPort` quét ma trận trong RAM, cho fallback offline và test.
- `src/backend/app/infrastructure/vectors/postgres_store.py` — `to_index` không nhận vector; `PostgresVectorStore.load` trả kèm `NumpyVectorSearch`.
- `src/backend/app/main.py` — `build_recsys` dựng `WeaviateVectorSearch`, dọn kết nối khi khởi động lỗi, đóng kết nối ở shutdown (`recsys_vectors`).
- `src/backend/app/api/v1/routes/search.py` — nhánh trả rỗng dùng `ANN_DIAGNOSTICS`.
- `src/backend/app/core/config.py` — thêm `weaviate_grpc_port`, `search_candidate_k`.
- `src/backend/requirements.txt` — thêm `weaviate-client>=4.9,<5`.
- `src/backend/tests/fakes/in_memory_vector_store.py`, `tests/conftest.py` — fake trả `(UnitIndex, NumpyVectorSearch)`.
- `src/backend/tests/unit/application/test_engines.py` — sửa test diagnostics; thêm test lọc trước, `total`/`facets` ổn định giữa các trang, `total` bị chặn bởi `candidate_k`, Similar cùng taxonomy, popularity bù ứng viên.
- `src/backend/tests/unit/infrastructure/test_weaviate_store.py` — viết lại cho adapter v4; thêm test phân trang cursor của REST `fetch`.

Frontend:
- `src/frontend/src/types/api.gen.ts` — sinh lại từ contract (chỉ đổi mô tả).
- `src/frontend/src/services/search.ts`, `src/components/search/SearchView.tsx` — hiện "Tìm thấy N+ dịch vụ" khi `totalExact === false`.

## Quyết định

- Filter theo `id` object (uuid5 từ `productId`, đã có sẵn trong `WeaviateClient.object_uuid`), nên không thêm property nào vào Weaviate; collection vẫn chỉ giữ vector và `productId`, đúng `data-model.md`.
- Không sửa công thức domain (`build_profile`, `score_candidates`, `mmr_select`, `explain`): use case đưa cho chúng một ma trận nhỏ đánh số lại.
- Thêm ứng viên theo popularity. Lý do: lần đo đầu, người dùng `long_term` chỉ nhận 2/4 gợi ý, vì 200 hàng xóm theo vector đều là khách sạn mà MMR giới hạn 2 món mỗi loại. `W_POP = 0.25` đủ lớn để món phổ biến xa profile vẫn lọt top.
- Giữ `grpcio 1.81.1` trong `.venv` local, dù `weaviate-client 4.23` ghim `<1.80`, vì `langgraph-api` (cài tay, ngoài requirements) cần `>=1.81`. Đã chạy thử client v4 với 1.81.1 và mọi thao tác đều chạy.
- Đã xoá `.venv/.../protobuf-7.36.1.dist-info`: thư mục rác từ một lần cài dở, chỉ có file `REQUESTED`, làm pip không cài được. Bản protobuf thật là 6.33.6.

## Kiểm tra

- `PYTHONDONTWRITEBYTECODE=1 python3 src/shared/contracts/tests/validate_contract.py`: PASS.
- `LANGSMITH_TRACING=false pytest src/backend/tests`: **290 passed, 13 skipped** trong 29 giây (gồm `tests/architecture/`). Để tracing bật thì mất 7 phút, vì LangSmith cố gửi trace qua mạng đang lỗi.
- Frontend: `npx tsc --noEmit` sạch, `npx vitest run` 76/76, eslint trên 2 file đã sửa sạch.
- Chạy thật với Weaviate local (`WEAVIATE_URL=http://localhost:8080`, index 3.183 vector bằng `embed_products`):
  - Backend khởi động và báo `startup.recsys.ready search_units=3183`, không tải vector; `build_recsys` mất 8,7 giây, chủ yếu đọc Postgres và dựng popularity.
  - `GET /search`, `/similar/{id}`, `/recommendations` (khách) đều trả 200. `diagnostics`: `ANN_CANDIDATE_SCORE`, `approximate: true`, `totalExact: false`, `facetsExact: false`.
  - So với thuật toán quét toàn bộ cũ (chạy code HEAD trên cùng vector): Recommendations trùng khớp **60/60 người dùng** (13 cross_vertical, 22 long_term, 23 dormant, 2 cold_start_content). Search top-10 trùng trên 5/5 truy vấn; `total` lệch tối đa 2 (121 so với 119) do HNSW xấp xỉ.
  - Recommendations với Weaviate local: p50 127 ms, p95 143 ms. Search khoảng 0,5–0,6 giây, chủ yếu do gọi Cohere embed.
- Chưa đo coverage vì `pytest-cov` chưa cài.

## Còn lại / rủi ro

- **Weaviate Cloud không vào được từ mạng hiện tại.** Mọi kết nối IPv4 tới AWS eu-central-1 đều timeout; chỉ IPv6 qua NAT64 thông, và DNS lúc trả AAAA lúc không. `connect_weaviate` vào cloud đang lỗi `ConnectTimeout`, nên phiên `make web` đang chạy (trỏ cloud) có RecSys tắt. Đây là lỗi mạng, không phải code. Đổi mạng, hoặc trỏ `.env` sang Weaviate local (đã index đủ 3.183 vector), thì RecSys lên.
- Chưa chạy thật đường gRPC tới cloud (`aggregate`, `near_vector` qua `grpc-<cluster>:443`), vì lỗi mạng ở trên.
- Mỗi request gửi danh sách id hợp lệ (tới khoảng 3.000 uuid) làm filter. Local thì nhanh; qua cloud trên mạng chậm có thể tốn thêm. Có thể tối ưu bằng cách bỏ filter khi mask gần phủ toàn bộ.
- Đề xuất `docs/prd/update/2026-09-23-weaviate-cloud-index-hfresh.md` (HNSW so với hfresh trên cloud) vẫn chờ chốt; thay đổi này không phụ thuộc loại index.
