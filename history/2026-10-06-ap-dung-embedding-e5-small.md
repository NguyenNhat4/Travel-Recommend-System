# Áp dụng đổi embedding sang e5-small local, bỏ Cohere (FR-SRC-02)

- Ngày: 2026-10-06
- Tác giả: Đăng Khôi / Claude Code
- Nhánh: test/newcrawl (sau merge `origin/release-mvp-v2` → `1ac45f3`)
- Trạng thái: dang dở (chưa commit; image Docker chưa build thử; gate nghiệm thu trên VM chưa chạy)
- Phạm vi: backend, data, contract, docs

## Mục tiêu

Người dùng chốt đề xuất `2026-10-05-fr-src-02-embedding-local-e5-small.md` ngày 06/10 ("đã chốt như đề xuất", "chỉ e5-small", làm trên nhánh crawl), rồi cùng ngày quyết bỏ hẳn đường lui Cohere ("bỏ Cohere, chỉ có e5 small thôi") — đề xuất `docs/prd/update-archive/2026-10-06-bo-duong-lui-cohere.md` ghi lại và đã áp dụng. Trước khi sửa, merge `origin/release-mvp-v2` vào `test/newcrawl` (nhánh chậm 110 commit backend; người dùng chọn merge trước): merge sạch, không conflict.

## File thay đổi

- `docs/prd/requirements.md` (FR-SRC-02, NFR-PERF-03), `docs/prd/architecture.md` (sơ đồ, cây thư mục, bảng công nghệ, §5 mục 5), `docs/prd/data-model.md` (§1, ERD Weaviate), `docs/prd/deployment-plan.md` (§2 biến môi trường, §5 readiness), `docs/prd/project-brief.md`, `docs/prd/implementation-plan.md` — sửa theo đề xuất đã chốt.
- `docs/prd/update-archive/2026-10-06-bo-duong-lui-cohere.md` — thêm: đề xuất bỏ đường lui Cohere, đã chốt + áp dụng (PRD bỏ `EMBED_PROVIDER`, `COHERE_API_KEY`).
- `docs/prd/update-archive/2026-10-05-fr-src-02-embedding-local-e5-small.md` — thêm: bản đề xuất trạng thái `đã áp dụng` + mục điều chỉnh khi chốt (chỉ e5-small, collection `ProductE5Small`, revision ghim). Bản gốc vẫn nằm ở `docs/prd/update/` trên `bench_search_recomSys` — xoá ở đó khi gộp nhánh.
- `src/backend/app/infrastructure/embeddings/local_e5_embedder.py` — thêm: `LocalE5Embedder` (transformers + torch CPU, mean pooling, L2, tiền tố `passage: ` / `query: `, cắt đuôi 512 token, nạp lười có khoá).
- `src/backend/app/infrastructure/embeddings/factory.py` — thêm: `build_embedder(settings)` dựng e5-small.
- `src/backend/app/infrastructure/embeddings/cohere_embedder.py`, `src/backend/tests/unit/infrastructure/test_cohere_embedder.py` — xoá (bỏ Cohere).
- `src/backend/app/core/config.py` — sửa: bỏ mọi `cohere_*`; `embed_model` chỉ e5-small, `embed_model_revision` (`614241f6…`), `embed_dimension` (chỉ 384), `embed_device/batch_size/max_tokens`; `weaviate_collection` mặc định `ProductE5Small`; `search_cutoff` 0,84.
- `src/backend/app/main.py`, `src/backend/jobs/embed_products.py` — sửa: dùng factory; job từ chối ghi vào collection chứa vector model khác (`foreign_models`); embed tuần tự lô 96 (bỏ limiter/chạy song song của Cohere). Comment cũ nhắc Cohere ở `search/prewarm.py`, `query_cache.py`, `use_cases.py`, `vectors/*` sửa theo.
- `src/backend/app/infrastructure/vectors/weaviate_store.py` — sửa câu mô tả (không còn ghi Cohere).
- `src/backend/requirements.txt`, `src/backend/jobs/requirements.txt` — thêm `transformers`, `torch`.
- `Dockerfile.backend`, `Dockerfile.fresh-catalog` — sửa: cài torch CPU từ download.pytorch.org, tải sẵn e5-small đúng revision vào `/opt/hf`, `HF_HUB_OFFLINE=1`.
- `.env.example`, `src/data_collection/.env.example`, `docker-compose.yml`, `Makefile` — sửa: bỏ biến Cohere của backend/job index, `WEAVIATE_COLLECTION=ProductE5Small`, `SEARCH_CUTOFF=0.84`; bỏ `EMBEDDING_MODEL_NAME` (không trường nào đọc). Khoá Cohere của bench `src/evaluation` giữ.
- `src/data_collection/fresh_catalog.py` — sửa: bước index không đòi khoá embedding; chế độ local chặn cả `ProductE5Small`.
- `src/data_collection/monitor.py`, `monitor_ui/index.html` — sửa: ô thử truy vấn embed bằng e5-small (giữ model giữa các lần bấm), trường `cohereMs` → `embedMs`, chữ trên UI.
- `src/data_collection/tests/test_live_monitor.py` — sửa theo monitor.
- `src/shared/contracts/schemas/search.yaml`, `src/frontend/src/types/api.gen.ts` — sửa chỉ `description` (stageMs.embed, embedCache); không đổi schema.
- `docs/spec/hop-dong-tich-hop-search-recommendation.md` (cache, cutoff 0,84, ngân sách embed, S7), `src/backend/README.md` — sửa theo model mới.
- Test: `src/backend/tests/unit/infrastructure/test_local_e5_embedder.py` (thêm: tiền tố, normalize, batch, sai chiều, cấu hình + env chuỗi, factory, job từ chối collection Cohere, smoke model thật khi `E5_SMOKE=1`); `test_embed_products_job.py` (sửa: tiêm embedder qua `build_embedder`; bỏ test song song/limiter/HTTP vốn cho Cohere, thêm test ghi theo lô 96); `src/data_collection/tests/test_fresh_catalog_job.py` (sửa: không cần khoá Cohere với e5).

## Quyết định

- Chỉ e5-small, không còn Cohere (người chốt): e5-base hay Cohere đều không chạy được trong code sản phẩm.
- Collection mới `ProductE5Small`; `Product` (vector Cohere) không còn được đọc, giữ trên Weaviate tới khi chủ động xoá (quay lại Cohere = deploy image cũ). Job không tự xoá collection và từ chối trộn model.
- `embed_dimension` để `int` (không `Literal`): biến môi trường là chuỗi, `Literal[384, 1024]` từ chối `"384"` khiến `.env.example` không khởi động được (phát hiện khi chạy test); validator vẫn giới hạn 384/1024.
- Văn bản dài hơn 512 token cắt đuôi như `truncate: END` của Cohere (bench từ chối thay vì cắt).

## Kiểm tra

- Backend `pytest src/backend --ignore=tests/integration` (vsf2): 1.158 passed trước khi sửa → **1.154 passed, 1 skipped** sau khi sửa (bớt test Cohere đã xoá, thêm test e5). Smoke model thật `E5_SMOKE=1 HF_HUB_OFFLINE=1`: pass (384 chiều, đoạn khớp xếp trên).
- `pytest src/data_collection/tests`: 476 passed, 18 skipped.
- `PYTHONDONTWRITEBYTECODE=1 python3 src/shared/contracts/tests/validate_contract.py`: PASS (109 schemas, 87 fixtures).
- Chưa build image Docker (torch CPU + model ~0,7 GB tải từ mạng); chưa đo RAM/CPU trên VM.

## Còn lại / rủi ro

- Gate nghiệm thu trong đề xuất (dev/test không thua Cohere, p95 `/search` ≤ 250 ms trên VM, parity, RecSys baseline mới, thời gian index trên VM) chưa chạy.
- Rollout: không còn đường lui bằng env. Deploy image mới → backend chưa có vector `ProductE5Small` nên RecSys tắt và thử lại cho tới khi bước index (job cào hoặc chạy tay) dựng xong collection. Nên dựng `ProductE5Small` trước (chạy job index bằng image mới) rồi mới deploy backend. Env VM không được đặt `WEAVIATE_COLLECTION=Product` / `SEARCH_CUTOFF=0.62`.
- Code xử lý lỗi 429 của Cohere trong `src/data_collection` (`daily.py`, `pipeline_errors.py`, cooldown index) còn nhưng không còn đường kích hoạt; chưa gỡ.
- Image job cào thêm torch + model: VM 2 vCPU / 4 GB cần theo dõi RAM bước index (chạy sau khi cào, không song song Chromium).
- `sentence_transformers_embedder.py` (toàn bộ đã comment) chưa xoá.
