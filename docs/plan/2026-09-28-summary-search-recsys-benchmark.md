# Tổng hợp trạng thái Search, Similar, Recommendation và các benchmark

- Ngày: 2026-09-28
- Phục vụ: **FR-SRC-01..04**, **FR-REC-01..04**, **NFR-PERF-01**, **NFR-PERF-03**, **AC-SRC-01** (`docs/prd/requirements.md`); đánh giá theo `docs/prd/test-plan.md` §2.4–2.5.
- Căn cứ: nhánh `bench/embed-search` @ `a0efb2f` (đã merge `release-mvp-v1`), ref remote ở lần fetch gần nhất, và các entry `history/` ghi ở cuối file.
- Đây là ảnh chụp trạng thái, không thay PRD hay spec. Chi tiết hành vi: `docs/spec/hop-dong-tich-hop-search-recommendation.md`; checklist bench: `docs/spec/bench/search-eval-checklist.md`.

**Tóm tắt:** ba endpoint đều chạy trên backend, nhưng **chưa có số chất lượng search nào**. Gold chưa gán nhãn, nên mọi ngưỡng hiện tại vẫn là giá trị tạm.

## 1. Engine trên backend

### 1.1. Nền chung

- Embedding: Cohere `embed-multilingual-v3.0` (1024 chiều), vector ở Weaviate. Snapshot catalog 2026-09-23 có 3.183 search unit.
- Metadata để lọc (taxonomy, điểm đến, giá, còn chỗ) nạp từ Postgres, nạp lại mỗi `CATALOG_REFRESH_SECONDS` (900 giây).
- Từ 24/09, mỗi request truy vấn top-K sang Weaviate (`candidateK` = 200, lọc theo id). Trước đó backend tải toàn bộ vector lúc khởi động, mất 453 giây. Vì chỉ lấy top-K nên `total`/`facets` là số xấp xỉ (`approximate: true`, `totalExact: false`).

### 1.2. Search — `/search`, chế độ `HYBRID_CANDIDATE_SCORE` (xong 25/09)

- **Chuẩn hoá truy vấn** (`domain/search/normalize.py`):
  - viết tắt (KS, KDL, NT, PQ, SG…);
  - sửa chính tả tên riêng theo từ vựng catalog;
  - tên điểm đến về dạng chuẩn;
  - nhận diện kiểu đi (`party`: SOLO/COUPLE/FAMILY/FRIENDS/BUSINESS) — mới chỉ khai ở diagnostics, chưa dùng để lọc.
- **Hybrid:**
  - dense top-200 ∪ BM25 top-50 trên `nameAscii`/`searchTextAscii` (đã fold dấu);
  - cutoff 0.62;
  - hit BM25 dưới cutoff vẫn được vớt khi rank ≤ 10, cosine ≥ 0.50 và tên phủ ≥ 60% token của truy vấn;
  - thứ tự cuối theo RRF (k = 60).
- **Đo tay:**
  - "VinWonders": 2 → 11 kết quả;
  - "KS biển tại NT": trước ra 2 căn hộ ở Nghệ An, nay ra 141 khách sạn Nha Trang;
  - "Vinpeal" tự sửa thành "Vinpearl".
- Cờ lùi: `SEARCH_HYBRID=false`, `SEARCH_NORMALIZE=false`. Test backend lần gần nhất: 495 passed, 19 skipped.

### 1.3. Similar — `/products/{id}/similar`, `ANN_CANDIDATE_SCORE`

- Lấy vector đã lưu của sản phẩm gốc, không embed lại.
- Chỉ trả cùng taxonomy; loại chính nó và các hạng phòng anh em; tối đa 2 kết quả mỗi `parentProductId`.
- `404 PRODUCT_NOT_FOUND` khi không có sản phẩm, `409 PRODUCT_NOT_INDEXED` khi chưa có vector.
- Chưa có nhánh BM25.

### 1.4. Recommendation — `/recommendations`, `ANN_CANDIDATE_SCORE`

- Profile dựng theo từng chuyến đi từ event CDP (`domain/recommendation/profile.py`).
- Ứng viên: top-K quanh vector ngắn hạn và dài hạn, cộng 50 sản phẩm phổ biến nhất.
- Điểm = 0.6 × ngắn hạn + 0.25 × popularity + 0.15 × dài hạn.
- MMR λ = 0.7, tối đa 2 sản phẩm mỗi taxonomy. `because[]` phân rã theo event, ngưỡng 0.15.
- `strategy`: cross_vertical / recent_activity / long_term / dormant / cold_start_content / popular. Khách không đăng nhập nhận `popular`.
- **Đo:** trùng 60/60 user so với bản quét toàn bộ vector; p50 127 ms, p95 143 ms với Weaviate local.

### 1.5. Chỗ còn hở

| # | Vấn đề | Ghi chú |
|---|---|---|
| 1 | Search mất 0,4–0,6 giây/truy vấn, phần lớn là gọi Cohere | Chưa đạt tiêu chí 11 của spec (p95 < 300 ms) |
| 2 | Tham số recommendation trong code khác spec §4.3–4.7 | Trọng số event 1 / 0.5 / 0.2 (spec 5 / 3 / 1); dormant 180 ngày (spec 90); công thức điểm cuối khác |
| 3 | Chưa thấy test cho tiêu chí 20–23 | Decay theo ngày, `userVectorNorm` ≈ 1, `tripFactor` — spec gọi là 4 tiêu chí quan trọng nhất |
| 4 | Weaviate Cloud chưa backfill property BM25 | Cần `python -m src.backend.jobs.embed_products --backfill-lexical`; trước đó `/search` trên cloud chạy dense-only |
| 5 | Mọi ngưỡng chưa benchmark | Spec §10: S1 cutoff 0.62, S2 weak 0.70 / 0.06, S9 tham số lexical, S10 bảng chuẩn hoá — chờ search bench |

## 2. Các benchmark

| Bench | Đo gì | Trạng thái |
|---|---|---|
| Vector DB (`src/evaluation/vector_bench`) | Chọn Qdrant / pgvector / pgvectorscale | Chạy fast-track 22–23/09. Catalog thật: cả ba đạt. Quy mô 1M: chưa chốt. Nhóm đã chọn Weaviate từ 22/09, nên bench này dừng. |
| Search bench (`src/evaluation/search_bench`, lệnh `sb`) | Embedding, text builder, hybrid, ngưỡng — đo trên gold | Cuối Ngày 2 của checklist 8 ngày (mục 2.1) |
| RecSys offline | So 10 kiến trúc recommender trên temporal holdout: Recall@10/20, NDCG@10, cross-category, availability, coverage, p95/p99 | Code ở nhánh `origin/khoa/recsys-research` (22/09), **chưa merge**, chưa chạy trên DB đã seed. Dữ liệu là lịch sử tổng hợp. |
| Itinerary Agent golden (`src/evaluation/agent`) | Grounding, structured output, tool calling | Chạy 24/09: ba chỉ số PRD đạt 100%; 74/89 lượt PASS; p95 11,3 giây (mục tiêu < 5 giây, không gate). Báo cáo đã gỡ cùng bộ golden cũ (lấy từ lịch sử git, commit `601f112`) |

### 2.1. Search bench — chi tiết

**Đã xong:**

- **Hạ tầng:** Weaviate 1.37.3 riêng cho bench; Cohere client có cache và pacer token; `sb doctor` xanh.
- **B0** = text builder production `catalog-text-v2`. Đã embed 3.183 vector (~$0,04); token p99 234, qua gate < 450.
- **`metrics.py`:** Recall@5/10, nDCG@10, MRR@10, Judged@10, constraint precision, parent dup rate, zero-result…, kèm paired bootstrap.
- **Gold draft:** 672 câu nháp → 200 câu trong `gold/drafts.txt`, đủ quota 13 slice. *(29/09: luật mới, chốt 132 câu — mỗi slice ≥ 3.)*
- **Hợp đồng gold:** `gold_schema.py` + fixture `gold_small/`.
- **CLI:** `sb gold pool / split / kappa / merge / import / check`, test khớp đáp án fixture.
- **Hướng dẫn gán nhãn:** `docs/spec/bench/gold-guide.md`.
- **Chạy thử pool** trên 200 draft (ghi ra `bench_out/`, chưa vào `gold/`): 5.046 cặp, p50 26 ứng viên/câu, 0 câu rỗng.

**Chưa làm, theo thứ tự:**

1. Rà 42 câu do `--fill` tự lấp; sửa `c0241`, `c0503`, `c0531`. Thêm 2 câu dự phòng cho 5 slice đang đúng 10 câu (`amenity_multi`, `amenity_negation`, `amenity_offtaxonomy`, `cross_vertical`, `out_of_catalog`). Sau đó đóng băng `drafts.txt`. *(29/09: xong — không cần câu dự phòng nữa; `drafts.txt` chốt 132 câu.)*
2. Hai người đọc `gold-guide.md` và thống nhất các ví dụ khó.
3. App gán nhãn 0/1/2 (việc máy 2, `docs/spec/bench/prompts/may2-label-app.md`). App Streamlit hiện có chỉ soát câu hỏi (KEEP / REJECT / NEEDS_EDIT).
4. Chạy pool thật vào `gold/` → split → gán nhãn (~2.000 cặp/người với 132 câu chốt 29/09) → κ ≥ 0,6 → merge → import → tag `gold_v1`.
5. Toàn bộ Ngày 4–8:
   - mới có `arms/B0.yaml`, chưa có `stages.yaml`;
   - chưa chạy cổng nào (SAN, E1–E6, S0–S9, F1, P, FINAL);
   - chưa có `qu.py`, chưa đo latency, chưa đặt baseline regression.
6. Điều kiện tiên quyết còn mở: mentor chưa xác nhận bằng văn bản việc lệch handbook (backend, vector store, embedding).

**Nút thắt:** gold. Chưa có nhãn relevance nào thì chưa có số chất lượng search nào, và các việc mở S1, S2, S9, S10 của spec chưa đóng được.

## 3. Nguồn

- Search hybrid: `history/2026-09-25-search-hybrid-bm25-rrf.md`
- Chuẩn hoá truy vấn: `history/2026-09-25-search-chuan-hoa-truy-van.md`
- Top-K mỗi request: `history/2026-09-24-recsys-weaviate-top-k.md`
- Vector DB bench: `history/2026-09-23-vector-bench-ket-qua-fast-track.md`
- Gold CLI: `history/2026-09-25-gold-cli-pool-kappa-merge-import-check.md`
- RecSys offline: `history/2026-09-22-recsys-10-architectures.md` (trên nhánh `origin/khoa/recsys-research`)
