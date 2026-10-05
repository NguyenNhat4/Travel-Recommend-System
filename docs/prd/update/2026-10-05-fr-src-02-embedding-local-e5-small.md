# Đổi model embedding tìm kiếm từ Cohere `embed-multilingual-v3.0` sang `intfloat/multilingual-e5-small` (local, 384 chiều)

- Ngày: 2026-10-05
- Người đề xuất: nhóm Search (chốt nội bộ 05/10) / Claude (agent soạn)
- Trạng thái: chờ chốt
- Chốt bởi / ngày:
- PRD bị ảnh hưởng: `docs/prd/requirements.md` FR-SRC-02, NFR-PERF-03; `docs/prd/architecture.md` §4 (bảng công nghệ, dòng "Mô hình
  Embedding"), §5 mục 5 (Backend ↔ Weaviate / Cohere), sơ đồ và cây thư mục (`CohereEmbedder`); `docs/prd/data-model.md` §1 (collection
  `Product` 1024 chiều, entity Weaviate); `docs/prd/deployment-plan.md` §2 (`COHERE_API_KEY`, `EMBEDDING_MODEL_NAME`), §5 (health check
  Cohere); `docs/prd/implementation-plan.md` (job embed gọi Cohere)
- Mã FR/NFR: FR-SRC-02, NFR-PERF-01, NFR-PERF-03; ảnh hưởng gián tiếp FR-SRC-01/03/04, FR-REC-01/04 (dùng chung vector)

## Lý do

1. **Chất lượng không thua trên gold_v3 (131 câu, 4.991 nhãn), nhưng bằng chứng còn một lỗ hổng.**
   - So 5 model local cùng thang đo condensed-deep (`src/evaluation/reports/eval-2026-10-02-search-local-fair.md`): e5-small nDCG@10
     **0,712** hoà thống kê với e5-base 0,697, BGE-M3 0,710, GTE 0,688 (mọi CI95 chứa 0); e5-large-instruct kém có ý nghĩa. Chọn e5-small
     vì rẻ nhất: tạo vector câu hỏi p95 **11,4 ms** (laptop i5), 384 chiều, re-index 3.183 document 4m47s, cache model ≈ 471 MB.
   - Số full (unjudged = 0) của e5-small là 0,635 với Judged@10 0,789 (còn 277 kết quả top-10 chưa có nhãn), Cohere v3 (B0) 0,685 với
     Judged 1,000 (`eval-2026-10-01-search-day4-local.md` §5). Hai số này **không cùng thang**.
   - **Chưa có phép so e5-small với Cohere v3 trên cùng thang đo** (condensed-deep chỉ chạy cho 5 model local; nhóm quyết định bỏ bước này
     ngày 05/10). Đề xuất vì vậy **không** khẳng định e5-small thắng Cohere v3; khẳng định an toàn là "không kém có ý nghĩa trong nhóm
     model đã so" và cần gate nghiệm thu bên dưới trước khi bật trên production.
   - **Qua pipeline thật** (`SearchProducts` hybrid + normalize của backend, chạy trong bench trên collection e5-small, 05/10 —
     `src/evaluation/reports/eval-2026-10-05-search-e5s-dest-nodia.md`): nDCG@10 full **0,677** / condensed 0,687, Judged@10 0,842 khi
     không cutoff; dense-only 0,635 / 0,647. Hybrid + normalize giúp `abbrev_typo` +30,7 và `no_diacritics` +34,1 điểm nhưng làm
     `cross_vertical` −20,1 so dense-only (luật vớt BM25 theo tên) — cùng hình dạng với Cohere trước đây, không phải lỗi riêng của e5.
     **Cutoff tuyệt đối không dùng được như với Cohere:** cosine e5 dồn hẹp (trung vị rel 2 = 0,882, rel 0 = 0,861, câu ngoài catalog top-1
     0,857–0,866); ngưỡng tạm 0,84 giữ 95 % rel ≥ 1 nhưng 3/3 câu ngoài catalog vẫn có kết quả và `no_diacritics` tụt 14,5 điểm. Cutoff cho e5
     phải hiệu chỉnh trên dev/test (hoặc chuyển sang ngưỡng theo margin so với nền), không chép 0,62. Với hai cờ mới của backend (lọc điểm đến
     suy từ câu — FR-SRC-03 — và cutoff riêng 0,80 cho câu không dấu) trên mốc cutoff 0,84: WIN theo win rule của bench, nDCG@10 **0,701** full /
     0,715 condensed (Δrecall +2,82 [+1,41; +4,34]); mọi ngưỡng là số trong mẫu, chờ dev/test.
2. **Vận hành với Cohere đang là điểm nghẽn của sản phẩm chạy.** Trên VM (`eval-2026-10-01-search-cloud-latency.md`): embed miss p95
   **437 ms** chỉ riêng bước gọi Cohere (bench đo API 735 ms p95), vượt ngân sách 250 ms của NFR-PERF-01 ngay cả trước khi cộng Weaviate;
   ngày 01/10 `/search` trả **500 sau ≈ 64 s** retry khi Cohere lỗi; key Trial 100 lượt/phút, quota tháng không rõ (đề xuất 30/09 từng ghi
   429 khi index). Cache vector truy vấn (1.12.0) chỉ che được câu lặp lại.
3. **Chi phí và phụ thuộc.** Model local chạy CPU trong tiến trình backend, không key, không quota, không rate limit; chi phí là CPU của VM
   app (e2-medium, chưa đo) và dung lượng image.
4. **Khác đề xuất 30/09 đã bị từ chối** (`docs/prd/update-archive/2026-09-30-embedding-local-cho-demo.md`: local chỉ cho demo khi hết quota,
   chưa có bench). Đề xuất này thay provider cho **production**, có số trên gold_v3, có gate nghiệm thu và đường lui.

## Nội dung đề xuất

- `requirements.md` **FR-SRC-02** hiện: "vector hóa … bằng Cohere `embed-multilingual-v3.0` (1024 chiều) … truy vấn phải dùng
  `input_type=search_query`, nạp dùng `input_type=search_document`" → thay bằng: "vector hoá bằng model local `intfloat/multilingual-e5-small`
  (384 chiều, revision pin trong `core/config.py`), chạy trong tiến trình backend bằng `transformers` + `torch` CPU, mean pooling, L2-normalize;
  **câu truy vấn thêm tiền tố `query: `, document thêm `passage: `** (tương đương `input_type` của Cohere — thiếu tiền tố làm giảm chất
  lượng mà không báo lỗi). Query và document luôn cùng model, cùng revision, cùng text builder; `modelVersion` =
  `intfloat/multilingual-e5-small:<text builder>`."
- `requirements.md` **NFR-PERF-03** hiện nhắc "ngân sách thời gian của Cohere Embed API … nếu vượt thì cache" → "ngân sách tạo vector câu hỏi
  (model local trên CPU của backend) phải nằm trong p95 250 ms của NFR-PERF-01, đo trên máy đích; cache vector truy vấn giữ nguyên".
- `architecture.md` §4 bảng công nghệ dòng Mô hình Embedding → e5-small local; §5 mục 5: "Backend tự sinh vector bằng model local rồi tự
  ghi; Weaviate không giữ khoá, không tự vector hoá" (ý "job embed gọi Cohere" → "job embed chạy model local"); cây thư mục
  `infrastructure/embeddings/` thêm adapter local, `CohereEmbedder` giữ làm đường lui có cờ.
- `data-model.md` §1 và entity Weaviate: collection **mới** `ProductE5` (hoặc tên chốt khi áp dụng) 384 chiều, `vectorizer: none`, cosine,
  HNSW / hfresh như cũ; collection `Product` (Cohere, 1024) **giữ** cho tới khi gate đạt rồi mới xoá — đổi collection bằng cấu hình, rollback
  là đổi lại cấu hình.
- `deployment-plan.md` §2: `COHERE_API_KEY` trở thành tuỳ chọn (đường lui); thêm `EMBED_PROVIDER=local|cohere`, `EMBED_MODEL`,
  `EMBED_MODEL_REVISION`, `EMBED_DIMENSION`, `WEAVIATE_COLLECTION`; §5 health check: "model đã tải và embed thử một câu" thay cho "Cohere
  sẵn sàng".
- `implementation-plan.md`: job embed chạy model local; thời gian re-index đo trên VM.

**Gate nghiệm thu trước khi bật trên production (ghi vào đề xuất để Lead chốt):**

1. Trên dev/test split của gold_v3 (chốt 05/10, chờ `devtest.py`): arm APP e5-small (hybrid + normalize, cutoff hiệu chỉnh riêng — **không
   chép 0,62 của Cohere**, cosine e5 dồn 0,72–0,78 cho cặp không liên quan) **không thua** arm APP Cohere v3 hiện tại trên test split theo
   win rule của bench (`min_delta_recall 2.0`, `max_slice_loss 3.0`), đo cùng thang (condensed hoặc bù nhãn hole).
2. HTTP `/search` trên VM: p95 cache-miss ≤ 250 ms, cache-hit ≤ 250 ms (`sb latency http`); zero-result trong catalog ≤ 2 %.
3. `sb parity`: offline = HTTP trên 20 câu.
4. RecSys dùng chung vector: chạy lại bench recsys bằng vector e5 (đang làm, Day 6), so với `baseline_v1`; `modelVersion` đổi → ghi
   `baseline_v1` mới theo chính sách `recsys-offline-eval.md` §3.1. `/similar` và Agent (gọi `SearchProducts` trong tiến trình) đi theo.
5. Job index định kỳ trên VM (crawler đổi catalog hằng ngày) chạy được bằng CPU của VM trong thời gian chấp nhận.

## Thay đổi source sau khi chốt

- PRD các mục trên **trước**, rồi: `src/backend/app/core/config.py` (bỏ `Literal` khoá `embed_model` / `embed_dimension`; thêm provider,
  revision, tiền tố); adapter `src/backend/app/infrastructure/embeddings/` dùng `transformers` + `torch` (không `sentence-transformers`: kéo
  scipy, DLL bị Application Control chặn trên máy dev — cùng cách `src/evaluation/search_bench/embed/local_hf.py`); `main.py` composition
  root; `src/backend/jobs/embed_products.py`; `Dockerfile.backend` (torch CPU, cache model); `.env.example`; `src/backend/README.md`.
- Contract: `modelVersion` đổi giá trị (không đổi schema); `docs/spec/hop-dong-tich-hop-search-recommendation.md` §2.2 (tiền tố thay
  `input_type`), §7.1 (dòng embed), §10 S7.
- Test: identity model + revision, tiền tố query/passage, không trộn collection khác chiều, integration index → retrieval; `sb parity`.
- Cutoff và `lexicalCutoff` hiệu chỉnh trên dev split rồi ghi `.env.example` + contract §2.4; không chép ngưỡng Cohere.
- Hướng dẫn chuyển / hoàn tác (`docs/guide/`): dựng collection mới song song → đổi env → kiểm parity → xoá collection cũ sau một tuần.
- RecSys: `baseline_v1` mới sau khi bench recsys bằng vector e5 xong.
