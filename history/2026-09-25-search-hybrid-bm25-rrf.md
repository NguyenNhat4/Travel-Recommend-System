# /search hybrid: BM25 + dense, RRF ở app (HYBRID_CANDIDATE_SCORE)

- Ngày: 2026-09-25
- Tác giả: tqanh123 / Claude Code
- Nhánh: feat/hybrid-search (tách từ origin/release-mvp-v1 @ bcc8a95)
- Trạng thái: hoàn thành (phần backend, contract, spec, frontend `search.ts`); còn lại ghi ở cuối
- Phạm vi: backend, contract, docs (spec), frontend
- Đề xuất PRD: **không có** — người dùng (tqanh123) chốt ngày 2026-09-25 làm thẳng và ghi phần lệch PRD vào entry này (xem "Lệch PRD")

## Mục tiêu

Demo 25/09 cần `/search` trên backend release chạy được cả tìm theo từ khoá lẫn theo ngữ nghĩa (FR-SRC-01). Trước thay đổi, `/search` chỉ có dense: truy vấn tên riêng/thương hiệu cho rất ít kết quả vì cosine của chúng nằm dưới cutoff 0.62 ("VinWonders" chỉ ra 2 kết quả, "melia vinpearl hue" ra 0). Collection `Product` chỉ có `productId/modelVersion/textHash`, không có text nào để BM25 khớp.

## File thay đổi

Contract (sửa trước code, AGENTS.md §3):
- `src/shared/contracts/schemas/common.yaml` — sửa: `SearchMode` thêm `HYBRID_CANDIDATE_SCORE` (thêm giá trị enum, tương thích ngược theo spec §7.4) và mô tả quy tắc R/SORT.
- `src/shared/contracts/schemas/search.yaml` — sửa: `EngineDiagnostics` thêm trường tuỳ chọn `fusion`, `rrfK`, `lexicalK`, `lexicalCutoff`, `lexicalMinCoverage`, `lexicalCandidates`, `lexicalCount`; bổ sung mô tả `approximate`, `total`, `cutoff`, thứ tự xử lý `[C4]`.

Spec:
- `docs/spec/hop-dong-tich-hop-search-recommendation.md` — sửa: §2.2 thêm khối hybrid của `/search`; §2.3 bất biến 3 có ngoại lệ cho phần vớt; §2.4 `search` sang `HYBRID_CANDIDATE_SCORE` + cờ lùi `SEARCH_HYBRID=false`; §9 tiêu chí 4, 10, thêm 10b; §10 S8 cập nhật, thêm S9 (tham số lexical chưa benchmark).

Backend:
- `src/backend/app/domain/search/lexical.py` — thêm: `fold` (chép từ `src/evaluation/vector_bench/lexical.py`), `tokens`, `query_tokens`, `coverage`, `STOPWORDS`.
- `src/backend/app/domain/search/hybrid.py` — thêm: `HybridConfig`, `HybridOutcome`, `rrf`, `hybrid_filter_score`.
- `src/backend/app/domain/search/__init__.py` — sửa: export các hàm mới.
- `src/backend/app/application/ports/vector_search.py`, `ports/__init__.py` — sửa: thêm `LexicalHit`, `LexicalSearchPort.bm25`.
- `src/backend/app/application/search/use_cases.py` — sửa: `SearchProducts` nhận `lexical`, `hybrid`, `lexical_candidate_k`; nhánh hybrid; `HYBRID_DIAGNOSTICS`; `topScore` = cosine lớn nhất trong R (không còn là phần tử đầu, vì thứ tự theo RRF). Nhánh dense giữ nguyên khi không bật hybrid.
- `src/backend/app/infrastructure/vectors/weaviate_store.py` — sửa: `LEXICAL_PROPERTIES` (`nameAscii`, `searchTextAscii`, tokenization `word`, searchable), `invertedIndexConfig` (bm25 k1/b, stopwords `none`) khi tạo collection; thêm property thiếu cho class đã có; `patch_properties`; `VectorMetadata.lexical`; `WeaviateVectorSearch.bm25`; `lexical_properties()`.
- `src/backend/app/infrastructure/vectors/numpy_search.py` — sửa: thêm `bm25()` trong RAM (tham số `texts`) cho test offline.
- `src/backend/jobs/embed_products.py` — sửa: ghi `nameAscii`/`searchTextAscii` cho object mới; báo `missingLexical`; cờ `--backfill-lexical` (PATCH property cho object cũ, không gọi Cohere). Vẫn chỉ dùng REST (Dockerfile.daily không có weaviate-client).
- `src/backend/app/core/config.py` — sửa: `search_hybrid`, `search_rrf_k`, `search_lexical_candidate_k`, `search_lexical_k`, `search_lexical_cutoff`, `search_lexical_min_coverage`, `search_bm25_k1`, `search_bm25_b`.
- `src/backend/app/main.py` — sửa: dựng `HybridConfig` (lexicalCutoff kẹp ≤ cutoff), truyền adapter vector làm nhánh BM25, log `startup.recsys.search.mode`.
- `.env.example` — sửa: thêm `SEARCH_HYBRID`, `SEARCH_LEXICAL_K`, `SEARCH_LEXICAL_CUTOFF`.
- `src/backend/tests/fakes/in_memory_vector_store.py` — sửa: truyền text BM25 cho `NumpyVectorSearch`.
- `src/backend/tests/unit/domain/test_lexical.py`, `test_hybrid.py`, `src/backend/tests/unit/application/test_hybrid_search.py` — thêm.
- `src/backend/tests/unit/infrastructure/test_weaviate_store.py` — sửa: test `bm25`, schema tạo mới, thêm property cho class cũ, cờ `lexical` khi fetch, `patch_properties`.

Frontend:
- `src/frontend/src/services/search.ts` — sửa: bỏ sắp lại theo `score` khi `sort === 'relevance'` (giữ thứ tự backend). Banner "kết quả yếu" trên bản release đã dùng `topScore` nên không cần sửa.
- `src/frontend/src/types/api.gen.ts` — sinh lại bằng `npm run generate:api-types` (enum `HYBRID_CANDIDATE_SCORE`, trường diagnostics mới).

## Quyết định

- **Hai lệnh gọi + RRF ở app**, không dùng `collection.query.hybrid()` của Weaviate: cần biết hit nào đến từ nhánh nào để áp quy tắc vớt, `score` phải giữ nghĩa cosine (contract `catalog.yaml` ScoredProduct), và RANKED của Weaviate nhân trọng số theo alpha. Nhánh BM25 lấy kèm vector để tính cosine cho hit chỉ có ở BM25.
- **Quy tắc vớt (Option L):** hit BM25 có rank ≤ `lexicalK` (10), cosine ≥ `lexicalCutoff` (0.50) và tên phủ ≥ `lexicalMinCoverage` (0.6) token của truy vấn. Thử DF ("token hiếm") trước, bỏ vì trên catalog 2026-09-21 `vinwonders` có mặt ở 4,9% tên còn `trang` 5,0% — không tách được; và `mau` (DF 2) làm "khách sạn ở Cà Mau" vớt nhầm "Hoa Mau Don Homestay". Độ phủ giải quyết cả hai.
- **Fold dấu ở app (shadow)**: Weaviate local là 1.27.0 (compose), chưa có `text_analyzer(ascii_fold)` (cần ≥ 1.37). Chỉ lưu bản đã fold; tên/giá/ảnh vẫn lấy từ Postgres.
- **stopwords `none`**: preset `en` mặc định bỏ âm tiết tiếng Việt như "an", "to" (đã đo ở bench, `history/2026-09-23-search-bench-embed-weaviate-ngay-1.md`).
- **Đảo quyết định 24/09** ("không thêm property nào vào Weaviate", `history/2026-09-24-recsys-weaviate-top-k.md`): BM25 cần text trong collection. `TEXT_BUILDER_VERSION`/`textHash` không đổi nên không phải embed lại.
- `SEARCH_HYBRID=false` đưa `/search` về đúng hành vi release (ANN, dense-only). Nhánh BM25 lỗi thì chạy dense-only, vẫn khai HYBRID với `lexicalCandidates = 0`, không 500.

## Lệch PRD

Người dùng chốt ngày 25/09 không tạo đề xuất trong `docs/prd/update/`; `docs/prd/` không sửa. Các chỗ PRD nay khác với code:
- `docs/prd/architecture.md` §5 (dòng "Weaviate chỉ giữ vector và `productId`") — collection có thêm `nameAscii`, `searchTextAscii`.
- `docs/prd/data-model.md` `WEAVIATE_PRODUCT` (dòng ~106-112) — thêm hai property trên.
- `docs/prd/requirements.md` AC-SRC-01 ("sắp xếp theo độ tương đồng ngữ nghĩa") — `/search` sắp theo RRF của hai nhánh.
- `docs/prd/implementation-plan.md` Giai đoạn 2 (dòng ~53, "`hybrid` của Weaviate, tham số `alpha`") — dùng hai truy vấn + RRF ở app.
FR-SRC-01 (từ khoá + ngữ nghĩa) và `architecture.md` §4 (Weaviate hỗ trợ hybrid) được đáp ứng.

## Kiểm tra

- `PYTHONDONTWRITEBYTECODE=1 python src/shared/contracts/tests/validate_contract.py` — PASS (83 schemas, 62 fixture).
- `pytest src/backend/tests` — lần chạy đầy đủ trước khi đổi DF → độ phủ: 428 passed, 19 skipped, 1 failed (test mới gửi `cutoff=2.0` ngoài miền contract; đã sửa test). Sau khi đổi: `PYTHONDONTWRITEBYTECODE=1 pytest src/backend/tests` — **429 passed, 19 skipped** (gồm `tests/architecture`).
- Index local (Weaviate 1.27.0, `trp-release-weaviate-1`): `python -m src.backend.jobs.embed_products` — 31 batch Cohere, 2.897/2.897 search unit; `--dry-run` sau đó: `unchanged 2897, embedded 0, missingLexical 0`. Schema: `nameAscii`/`searchTextAscii` word + searchable, `stopwords.preset none`, bm25 k1 1.2 b 0.75.
- Backend thật (`uvicorn … --reload`, log `startup.recsys.search.mode=HYBRID_CANDIDATE_SCORE`, 2.897 search unit), `GET /api/v1/search`:
  - "VinWonders": 2 → 11 kết quả (`lexicalCount` 9).
  - "melia vinpearl hue": 0 → 4, Meliá Vinpearl Hue ở #1 (`lexicalCount` 4).
  - "vé Bà Nà Hills": Sun World Bà Nà Hills (vớt); "Ana Mandara Villas Đà Lạt", "cáp treo Hòn Thơm": đúng tên ở #1.
  - "khách sạn ở Cà Mau": `lexicalCount` 0; nhánh dense vẫn trả 4 khách sạn Huế/Cần Thơ ≥ 0.62 (có từ trước, thuộc S1 cutoff).
  - "resort nha trang cho gia dinh co tre nho": 82 kết quả, `lexicalCount` 0 (câu mô tả để dense lo).
  - Độ trễ 0,4–0,6 s/truy vấn, phần lớn là embed Cohere (như release).
- `POST /auth/login` (minh.anh@example.com) → 200; `GET /recommendations` có Bearer → `cross_vertical`, Nha Trang, loại hotel, `because` có nội dung; khách → `popular`, 4 section.
- Frontend (Node 24.19, `npm ci`): `npm run typecheck` sạch; `npm run test:unit` 75/75 pass. `npm run dev` + `.env.local` (gitignored): qua BFF `http://localhost:3000` — `GET /api/auth/session` 200; `POST /api/v1/search` "VinWonders" 200, `HYBRID_CANDIDATE_SCORE`, total 11; `/api/v1/recommendations` khách → `popular`; `POST /api/auth/login` 200 rồi `/api/v1/recommendations` → `cross_vertical` Nha Trang; trang `/search?q=VinWonders` 200. npm 11 chặn install script của `esbuild`, `unrs-resolver` (allow-scripts) — không ảnh hưởng `next dev`, vitest vẫn chạy.
- Môi trường local: đã áp migration 0001–0004 qua `db/migrations/run.py` (shim `os.uname` vì Windows); Redis/Weaviate bật bằng `docker compose up -d --wait --no-deps` (không đụng container Postgres đã seed).

## Còn lại / rủi ro

- Weaviate Cloud: class đã có thì job tự thêm property, nhưng object cũ cần `python -m src.backend.jobs.embed_products --backfill-lexical` (PATCH, không gọi Cohere) và `PUT /v1/schema/Product` để đặt `invertedIndexConfig` (stopwords `none`) trước khi backfill. Chưa chạy trên cloud.
- `lexicalK`/`lexicalCutoff`/`lexicalMinCoverage` chưa benchmark (spec §10 S9) — đo ở cổng S2 của bench trên gold.
- Chưa bấm thử bằng trình duyệt thật (Playwright chưa cài browser); luồng UI đã kiểm qua đúng các request BFF mà trình duyệt gửi.
- `db/migrations/run.py` dùng `os.uname()` → lỗi trên Windows khi áp migration; chưa sửa.
- `/similar` và `/recommendations` vẫn `ANN_CANDIDATE_SCORE`.
- Trên worktree Windows, `uvicorn --reload` không nạp lại code sau khi sửa (1 lần reload không có hiệu lực); restart tay khi đổi code backend.
