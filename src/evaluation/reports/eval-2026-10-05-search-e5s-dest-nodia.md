# Search e5-small qua pipeline thật — lọc điểm đến từ câu (F1), câu không dấu (F2) và cutoff tạm

> **Ghi chú sau merge 05/10 (nhánh `bench_search_recomSys`):** máy khác cũng tạo cổng APP e5-small với `APP.e5s.hybrid_norm` = cutoff **0,62** (`regression/baseline_v1.json`). Trong report này các arm `APP.e5s.hybrid_norm*` có cutoff **0,84** nay đổi tên thành `APP.e5s.hybrid_norm_c84*` (yaml trong `arms/`); collection `ProductBench_e5_small` của máy này tương ứng `ProductBench__e5_small` theo quy ước đã hợp nhất. Số và run id giữ nguyên.

- Ngày chạy và viết: **05/10/2026**.
- Phục vụ: **FR-SRC-01, FR-SRC-03, FR-SRC-04, AC-SRC-01** (chất lượng truy xuất, điểm đến do câu quyết định, không trả rỗng vô cớ). Số
  về e5-small chỉ là bằng chứng cho đề xuất `docs/prd/update-archive/2026-10-05-fr-src-02-embedding-local-e5-small.md` (**chờ chốt**) — PRD
  FR-SRC-02 vẫn quy định Cohere v3 / 1024. Latency chỉ đo bước tạo vector câu hỏi local (NFR-PERF-01, một phần).
- Nhánh: `fix/search` (tách từ `bench_search_recomSys`), HEAD `942f5aa`. Code backend F1/F2 và code bench trong report này nằm ở working
  tree **chưa commit** lúc chạy — xem `history/2026-10-05-search-dest-filter-no-diacritics.md`, `history/2026-10-05-search-bench-app-e5s.md`.
- Run: `2026-10-05-fix-search-e5s` (12 arm `APP.e5s.*`), `2026-10-05-e5s-det` (2 arm, kiểm tái lập — §9). Weaviate bench local
  (Docker, `src/evaluation/search_bench/docker/compose.yml`), collection `ProductBench_e5_small` 3.183 object (hnsw), vector
  `vec_T3+R_e5-small.npy` (384 chiều, prefix `passage:`), câu hỏi embed local prefix `query:`; `modelVersion`
  `intfloat/multilingual-e5-small:catalog-text-v2`. Mỗi arm `query embed: cache 131/131` sau arm đầu.
- Gold: `gold_v3`, SHA-256 `4d2ac02fa960ceaf2c9286bf546da1b77023435a9337ecadee22dd7cc62f5784`; 131 câu active (128 trong catalog, 3
  `out_of_catalog`), 4.991 nhãn active. **Không thêm nhãn nào**; Judged@10 của e5-small 0,79–0,87 → mọi số full đi kèm condensed.
- Engine: đúng `application/search/use_cases.SearchProducts` của backend (`src/evaluation/search_bench/app_adapter.py`), cấu hình
  production hybrid + normalize: `candidate_k 200, rrf_k 60, lexical_k 10, lexical_cutoff 0.50, min_coverage 0.6, lexical_candidate_k 50`.
- **Không có arm Cohere.** Người dùng chốt 05/10 chuyển hẳn sang e5-small và không gọi Cohere nữa, nên mọi số ở đây là trên e5-small;
  **chưa đo F1/F2 trên pipeline Cohere đang chạy production, chưa đo qua HTTP.**

## 1. Kết luận ngắn

1. **F1 — lọc cứng điểm đến suy từ câu (`SEARCH_DEST_FILTER`) là đòn bẩy chính.** Trên mốc không cutoff: **WIN** theo win rule của bench
   (Δrecall@10 **+2,34** điểm, CI95 [+1,03; +3,84], p 0,000; ΔnDCG@10 +2,56 [+0,67; +4,63]; slice thua nặng nhất `abbrev_typo` −2,86 full /
   `parent_child` −2,01 condensed, trong ngưỡng 3,0). Áp cho 108/131 câu; 10 câu bỏ vì là câu vé máy bay, 1 câu vì ≥ 2 địa danh; 0 lần
   fallback; `filter_recall_loss` Σ 10 (nhãn rel ≥ 1 bị filter loại — §6). Slice tăng: `audience_style` +11,7, `dest_type` +4,95,
   `cross_vertical` +4,13, `named_entity` +3,11, `amenity_single` +3,1.
2. **F2 — nới cổng vớt BM25 cho câu không dấu (`SEARCH_NO_DIACRITICS_MODE=relax`) không đổi top-10 câu nào khi không cutoff** (131/131
   giống mốc, 19 câu được gắn profile). Lý do nằm ở RRF: hit chỉ có trong danh sách BM25 luôn xếp dưới hit có ở cả hai danh sách, nên nới
   `lexicalK` / độ phủ không đưa được gì vào top-10 khi dense còn đủ 200 ứng viên. F2 chỉ có tác dụng khi cutoff cắt bớt dense (§7) và
   knob quyết định là **`no_diacritics.cutoff`** (`SEARCH_NO_DIACRITICS_CUTOFF`), không phải `lexical_k` / `min_coverage`.
3. **Cutoff tuyệt đối không làm được việc của nó trên e5-small.** Cosine e5 dồn hẹp: trung vị rel 2 = 0,882, rel 0 = 0,861, chưa nhãn
   0,846; top-1 của 3 câu ngoài catalog 0,857–0,866 (§5). Ngưỡng tạm 0,84 (giữ 95 % rel ≥ 1) vẫn trả kết quả cho 3/3 câu ngoài catalog,
   trong khi `no_diacritics` mất **14,5 điểm** nDCG (5/12 câu trả < 10 kết quả) và `named_entity` 8 câu trả < 10 kết quả.
4. **Cutoff riêng 0,80 cho câu không dấu (`*_nc80`) bù lại toàn bộ phần mất:** `no_diacritics` 0,381 → 0,525 (= mức không cutoff), các slice
   khác không đổi. Tổ hợp **`hybrid_norm` (cutoff 0,84) + F1 + F2 với cutoff riêng 0,80**: **WIN** — Δrecall +2,82 [+1,41; +4,34], ΔnDCG
   **+3,54** [+1,48; +5,78] full / +3,90 [+1,85; +6,18] condensed, slice thua nặng nhất `parent_child` −1,67 / −2,01; nDCG@10 **0,701** full /
   0,715 condensed, Judged@10 0,863. Tổ hợp này so với mốc không cutoff: TIE (+0,40), tức giữ cutoff mà không mất chất lượng trong mẫu.
5. **Khuyến nghị:** giữ hai cờ **mặc định tắt** tuần này — mọi số là **trong mẫu** trên toàn gold_v3 (chưa có dev/test split, chờ
   `devtest.py`), 0,84 và 0,80 chọn từ phân bố của chính bộ câu này. Khi có split: hiệu chỉnh cutoff chung + `SEARCH_NO_DIACRITICS_CUTOFF`
   trên dev, kiểm trên test; nếu hình dạng giữ nguyên thì bật `SEARCH_DEST_FILTER=true`, `SEARCH_NO_DIACRITICS_MODE=relax` cùng cutoff riêng.
   Cutoff tuyệt đối cho e5 nên thay bằng ngưỡng theo margin so với nền (S2 của contract) — việc tuần sau.
6. **Phát hiện về bench (quan trọng cho mọi run APP sau này):** ba arm hybrid chạy trong ~30 s đầu sau khi nạp collection cho kết quả sai
   hẳn (`hybrid_norm_nocut` nDCG 0,422, Judged 0,509; chỉ 3/131 câu trùng với bản chạy lại) — index BM25 của Weaviate chưa ổn định ngay sau
   import. Đã thêm `wait_bm25_stable` vào `app_adapter.load_collection` và chạy lại ba arm với `--force`; bản chạy lại trùng **131/131** với run
   kiểm `2026-10-05-e5s-det`. Mọi số dưới đây là bản đã chạy lại (§9).

## 2. Cấu hình arm

Khối `app` chung cho mọi arm: `candidate_k 200, hybrid true, normalize true, rrf_k 60, lexical_k 10, lexical_cutoff 0.50, min_coverage 0.6,
lexical_candidate_k 50, dest_filter_fallback true, no_diacritics {lexical_k 20, lexical_cutoff 0.0, min_coverage 0.4, min_tokens 3}`;
`text_variant T3+R`, `model e5-small`, `query_input_type query`. Khác nhau:

| Arm | cutoff | dest_filter | no_diacritics_mode | no_diacritics.cutoff | hybrid / normalize | hash |
|---|---:|---|---|---:|---|---|
| `APP.e5s.dense_nocut` | −1 | false | off | null | false / false | `6fab6069` |
| `APP.e5s.hybrid_nocut` | −1 | false | off | null | true / false | `8f8a9eeb` |
| `APP.e5s.hybrid_norm_nocut` (**mốc**) | −1 | false | off | null | true / true | `c6bccdb7` |
| `APP.e5s.hybrid_norm_nocut_dest` | −1 | **true** | off | null | true / true | `03865537` |
| `APP.e5s.hybrid_norm_nocut_nodia` | −1 | false | **relax** | null | true / true | `faedf2aa` |
| `APP.e5s.hybrid_norm_nocut_dest_nodia` | −1 | **true** | **relax** | null | true / true | `4ede4ab3` |
| `APP.e5s.hybrid_norm` (mốc có cutoff) | **0,84 tạm** | false | off | null | true / true | `bb826010` |
| `APP.e5s.hybrid_norm_dest` | 0,84 | **true** | off | null | true / true | `224ab9d1` |
| `APP.e5s.hybrid_norm_nodia` | 0,84 | false | **relax** | null (= 0,84) | true / true | `b3b7753b` |
| `APP.e5s.hybrid_norm_dest_nodia` | 0,84 | **true** | **relax** | null (= 0,84) | true / true | `edf7fc16` |
| `APP.e5s.hybrid_norm_nodia_nc80` | 0,84 | false | **relax** | **0,80** | true / true | `8d6802c8` |
| `APP.e5s.hybrid_norm_dest_nodia_nc80` | 0,84 | **true** | **relax** | **0,80** | true / true | `ebb6b6ee` |

Vì sao 0,84 và 0,80 (§5): 0,84 là ngưỡng trên phân bố cosine top-10 của `dense_nocut` giữ 95 % kết quả rel ≥ 1 và chỉ làm 6/128 câu
dense-only rỗng; 0,80 là ngưỡng không cắt kết quả nào trong catalog. Cả hai **tạm, trong mẫu**, không phải giá trị chốt; cutoff 0,62 của
contract là của Cohere, không áp cho e5.

## 3. Bảng tổng

Nguyên văn từ `per_query.parquet` (script §11). recall/nDCG tính trên 128 câu trong catalog; Judged@10 trên 131; "dest query" = số câu
filter suy từ câu được áp; "skipped" = số câu bỏ lọc vì ≥ 2 địa danh / câu vé máy bay; "no_dia profile" = số câu gắn `queryProfile`.

### 3.1 Không cutoff

| arm | R@10 full | nDCG@10 full | Judged@10 | R@10 cond | nDCG@10 cond | zero in-cat | zero OOC (3) | fallback | dest query | skipped multi/flight | no_dia profile | filter_recall_loss Σ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| APP.e5s.dense_nocut | 0.3175 | 0.6346 | 0.789 | 0.3175 | 0.6471 | 0 | 0 | 0 | 0 | 0/0 | 0 | 0 |
| APP.e5s.hybrid_nocut | 0.3179 | 0.6520 | 0.837 | 0.3179 | 0.6625 | 0 | 0 | 0 | 0 | 0/0 | 0 | 0 |
| APP.e5s.hybrid_norm_nocut | 0.3346 | 0.6769 | 0.842 | 0.3346 | 0.6870 | 0 | 0 | 0 | 0 | 0/0 | 0 | 0 |
| APP.e5s.hybrid_norm_nocut_dest | 0.3580 | 0.7024 | 0.838 | 0.3580 | 0.7158 | 0 | 0 | 0 | 108 | 1/10 | 0 | 10 |
| APP.e5s.hybrid_norm_nocut_nodia | 0.3346 | 0.6769 | 0.842 | 0.3346 | 0.6870 | 0 | 0 | 0 | 0 | 0/0 | 19 | 0 |
| APP.e5s.hybrid_norm_nocut_dest_nodia | 0.3580 | 0.7024 | 0.838 | 0.3580 | 0.7158 | 0 | 0 | 0 | 108 | 1/10 | 19 | 10 |

### 3.2 Cutoff 0,84 tạm

| arm | R@10 full | nDCG@10 full | Judged@10 | R@10 cond | nDCG@10 cond | zero in-cat | zero OOC (3) | fallback | dest query | skipped multi/flight | no_dia profile | filter_recall_loss Σ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| APP.e5s.hybrid_norm | 0.3281 | 0.6659 | 0.865 | 0.3281 | 0.6759 | 0 | 0 | 0 | 0 | 0/0 | 0 | 0 |
| APP.e5s.hybrid_norm_dest | 0.3434 | 0.6811 | 0.857 | 0.3434 | 0.6942 | 0 | 0 | 1 | 108 | 1/10 | 0 | 10 |
| APP.e5s.hybrid_norm_nodia | 0.3303 | 0.6687 | 0.861 | 0.3303 | 0.6790 | 0 | 0 | 0 | 0 | 0/0 | 19 | 0 |
| APP.e5s.hybrid_norm_dest_nodia | 0.3458 | 0.6852 | 0.857 | 0.3458 | 0.6989 | 0 | 0 | 0 | 108 | 1/10 | 19 | 10 |
| APP.e5s.hybrid_norm_nodia_nc80 | 0.3370 | 0.6809 | 0.862 | 0.3370 | 0.6919 | 0 | 0 | 0 | 0 | 0/0 | 19 | 0 |
| APP.e5s.hybrid_norm_dest_nodia_nc80 | 0.3562 | 0.7013 | 0.863 | 0.3562 | 0.7149 | 0 | 0 | 0 | 108 | 1/10 | 19 | 10 |

`zero_result` = 0 ở mọi arm hybrid, kể cả 3 câu ngoài catalog: cutoff chỉ cắt dense, phần vớt BM25 vẫn trả kết quả (dense-only ở 0,84
làm 6/128 câu trong catalog rỗng — §5). Nghĩa là trên e5, cutoff 0,84 **không** tạo ra hành vi "ngoài catalog → rỗng" mà `out_of_catalog`
đòi hỏi.

## 4. nDCG@10 theo slice — full / condensed (J = Judged@10 của slice)

### 4.1 Không cutoff

| slice | n | dense_nocut | hybrid_nocut | hybrid_norm_nocut (mốc) | +F1 (`_dest`) | +F2 (`_nodia`) | +F1+F2 |
|---|---:|---|---|---|---|---|---|
| no_diacritics | 12 | 0.185 / 0.205 (J 0.37) | 0.445 / 0.478 (J 0.62) | 0.525 / 0.558 (J 0.62) | 0.541 / 0.569 (J 0.67) | 0.525 / 0.558 (J 0.62) | 0.541 / 0.569 (J 0.67) |
| dest_type | 12 | 0.785 / 0.794 (J 0.92) | 0.719 / 0.722 (J 0.92) | 0.719 / 0.722 (J 0.92) | 0.769 / 0.779 (J 0.89) | 0.719 / 0.722 (J 0.92) | 0.769 / 0.779 (J 0.89) |
| named_entity | 18 | 0.829 / 0.832 (J 0.74) | 0.828 / 0.828 (J 0.82) | 0.832 / 0.833 (J 0.81) | 0.863 / 0.866 (J 0.74) | 0.832 / 0.833 (J 0.81) | 0.863 / 0.866 (J 0.74) |
| abbrev_typo | 12 | 0.329 / 0.347 (J 0.69) | 0.458 / 0.471 (J 0.81) | 0.636 / 0.648 (J 0.82) | 0.607 / 0.638 (J 0.76) | 0.636 / 0.648 (J 0.82) | 0.607 / 0.638 (J 0.76) |
| cross_vertical | 10 | 0.740 / 0.751 (J 0.91) | 0.539 / 0.555 (J 0.85) | 0.539 / 0.555 (J 0.85) | 0.580 / 0.599 (J 0.87) | 0.539 / 0.555 (J 0.85) | 0.580 / 0.599 (J 0.87) |
| out_of_catalog | 3 | zero 0/3 | zero 0/3 | zero 0/3 | zero 0/3 | zero 0/3 | zero 0/3 |
| amenity_negation | 5 | 0.338 / 0.360 (J 0.82) | 0.355 / 0.368 (J 0.84) | 0.355 / 0.368 (J 0.84) | 0.339 / 0.355 (J 0.82) | 0.355 / 0.368 (J 0.84) | 0.339 / 0.355 (J 0.82) |
| amenity_single | 13 | 0.712 / 0.726 (J 0.81) | 0.779 / 0.787 (J 0.85) | 0.779 / 0.787 (J 0.85) | 0.810 / 0.824 (J 0.90) | 0.779 / 0.787 (J 0.85) | 0.810 / 0.824 (J 0.90) |
| audience_style | 11 | 0.676 / 0.698 (J 0.84) | 0.590 / 0.606 (J 0.90) | 0.590 / 0.606 (J 0.90) | 0.707 / 0.720 (J 0.91) | 0.590 / 0.606 (J 0.90) | 0.707 / 0.720 (J 0.91) |
| multi_constraint | 9 | 0.786 / 0.801 (J 0.90) | 0.700 / 0.707 (J 0.84) | 0.700 / 0.706 (J 0.90) | 0.738 / 0.748 (J 0.92) | 0.700 / 0.706 (J 0.90) | 0.738 / 0.748 (J 0.92) |
| parent_child | 11 | 0.674 / 0.676 (J 0.88) | 0.679 / 0.684 (J 0.92) | 0.679 / 0.684 (J 0.92) | 0.662 / 0.664 (J 0.92) | 0.679 / 0.684 (J 0.92) | 0.662 / 0.664 (J 0.92) |
| amenity_multi | 10 | 0.787 / 0.797 (J 0.88) | 0.873 / 0.879 (J 0.93) | 0.873 / 0.879 (J 0.93) | 0.874 / 0.881 (J 0.95) | 0.873 / 0.879 (J 0.93) | 0.874 / 0.881 (J 0.95) |
| amenity_offtaxonomy | 5 | 0.514 / 0.533 (J 0.76) | 0.568 / 0.576 (J 0.78) | 0.568 / 0.576 (J 0.78) | 0.581 / 0.592 (J 0.78) | 0.568 / 0.576 (J 0.78) | 0.581 / 0.592 (J 0.78) |

Hybrid so dense-only trên e5 có cùng hình dạng đã thấy với Cohere (`eval-2026-10-01-search-v1-3arm.md`): `abbrev_typo` +30,7 và
`no_diacritics` +34,1 điểm nhờ BM25 trên trường không dấu, nhưng `cross_vertical` **−20,1** và `dest_type` −6,6 vì luật vớt theo tên kéo sản
phẩm cùng tên khác loại / khác nơi lên. F1 lấy lại một phần `cross_vertical` (+4,1) và `dest_type` (+5,0) mà không chạm luật vớt.

### 4.2 Cutoff 0,84 tạm

| slice | n | hybrid_norm (mốc 0,84) | +F1 (`_dest`) | +F2 (`_nodia`) | +F2 nc80 | +F1+F2 | +F1+F2 nc80 |
|---|---:|---|---|---|---|---|---|
| no_diacritics | 12 | 0.381 / 0.403 (J 0.67) | 0.341 / 0.364 (J 0.63) | 0.410 / 0.436 (J 0.62) | 0.525 / 0.558 (J 0.62) | 0.383 / 0.413 (J 0.62) | 0.541 / 0.569 (J 0.67) |
| dest_type | 12 | 0.722 / 0.724 (J 0.92) | 0.777 / 0.789 (J 0.89) | 0.722 / 0.724 (J 0.92) | 0.722 / 0.724 (J 0.92) | 0.777 / 0.789 (J 0.89) | 0.777 / 0.789 (J 0.89) |
| named_entity | 18 | 0.819 / 0.820 (J 0.96) | 0.850 / 0.853 (J 0.93) | 0.819 / 0.820 (J 0.96) | 0.819 / 0.820 (J 0.95) | 0.850 / 0.853 (J 0.93) | 0.850 / 0.853 (J 0.92) |
| abbrev_typo | 12 | 0.621 / 0.633 (J 0.79) | 0.591 / 0.621 (J 0.73) | 0.621 / 0.633 (J 0.79) | 0.636 / 0.648 (J 0.82) | 0.592 / 0.623 (J 0.73) | 0.607 / 0.638 (J 0.76) |
| cross_vertical | 10 | 0.545 / 0.563 (J 0.85) | 0.580 / 0.599 (J 0.87) | 0.545 / 0.563 (J 0.85) | 0.545 / 0.563 (J 0.85) | 0.580 / 0.599 (J 0.87) | 0.580 / 0.599 (J 0.87) |
| out_of_catalog | 3 | zero 0/3 | zero 0/3 | zero 0/3 | zero 0/3 | zero 0/3 | zero 0/3 |
| amenity_negation | 5 | 0.355 / 0.368 (J 0.84) | 0.339 / 0.355 (J 0.82) | 0.355 / 0.368 (J 0.84) | 0.355 / 0.368 (J 0.84) | 0.339 / 0.355 (J 0.82) | 0.339 / 0.355 (J 0.82) |
| amenity_single | 13 | 0.773 / 0.781 (J 0.85) | 0.810 / 0.824 (J 0.90) | 0.773 / 0.781 (J 0.85) | 0.773 / 0.781 (J 0.85) | 0.810 / 0.824 (J 0.90) | 0.810 / 0.824 (J 0.90) |
| audience_style | 11 | 0.632 / 0.655 (J 0.91) | 0.707 / 0.720 (J 0.91) | 0.632 / 0.655 (J 0.91) | 0.632 / 0.655 (J 0.91) | 0.707 / 0.720 (J 0.91) | 0.707 / 0.720 (J 0.91) |
| multi_constraint | 9 | 0.720 / 0.728 (J 0.92) | 0.738 / 0.748 (J 0.92) | 0.720 / 0.728 (J 0.92) | 0.720 / 0.728 (J 0.92) | 0.738 / 0.748 (J 0.92) | 0.738 / 0.748 (J 0.92) |
| parent_child | 11 | 0.679 / 0.684 (J 0.92) | 0.662 / 0.664 (J 0.92) | 0.679 / 0.684 (J 0.92) | 0.679 / 0.684 (J 0.92) | 0.662 / 0.664 (J 0.92) | 0.662 / 0.664 (J 0.92) |
| amenity_multi | 10 | 0.879 / 0.885 (J 0.92) | 0.874 / 0.881 (J 0.95) | 0.879 / 0.885 (J 0.92) | 0.879 / 0.885 (J 0.92) | 0.874 / 0.881 (J 0.95) | 0.874 / 0.881 (J 0.95) |
| amenity_offtaxonomy | 5 | 0.568 / 0.576 (J 0.78) | 0.581 / 0.592 (J 0.78) | 0.568 / 0.576 (J 0.78) | 0.568 / 0.576 (J 0.78) | 0.581 / 0.592 (J 0.78) | 0.581 / 0.592 (J 0.78) |

`no_diacritics` có Judged@10 0,62–0,67 (< 0,7, `NEEDS_LABELS`) — số slice này kém tin cậy nhất trong report; hướng (dấu) của các Δ lớn
(±14–16 điểm) vẫn đọc được vì condensed cùng chiều.

## 5. Cutoff trên e5-small — phân bố cosine và trade-off

`e5_cutoff.py` trên `APP.e5s.dense_nocut` (1.310 kết quả top-10, cosine thật của dense), nguyên văn:

```
phân vị cosine theo nhãn (p5 / p25 / p50 / p75 / p95):
  rel2      n= 555  0.841  0.871  0.882  0.893  0.909
  rel1      n= 247  0.838  0.866  0.876  0.890  0.900
  rel0      n= 231  0.827  0.849  0.861  0.877  0.895
  unjudged  n= 277  0.820  0.834  0.846  0.868  0.889
câu ngoài catalog (expected_no_result): top-1 cosine = [0.86, 0.861, 0.866]

cutoff | giữ rel≥1 | cắt rel≥1 | loại rel0 | loại unjudged | câu in-catalog rỗng | câu OOC rỗng
0.78   |       802 |         0 |         0 |             0 |   0/128 | 0/3
0.80   |       802 |         0 |         0 |             0 |   0/128 | 0/3
0.82   |       802 |         0 |         4 |            15 |   0/128 | 0/3
0.83   |       788 |        14 |        19 |            48 |   2/128 | 0/3
0.84   |       760 |        42 |        40 |           117 |   6/128 | 0/3
0.85   |       722 |        80 |        63 |           147 |  14/128 | 0/3
0.86   |       671 |       131 |        82 |           183 |  21/128 | 0/3
0.87   |       575 |       227 |       120 |           214 |  28/128 | 3/3
0.88   |       420 |       382 |       149 |           248 |  47/128 | 3/3
0.90   |        85 |       717 |       195 |           273 |  97/128 | 3/3
```

Trên `hybrid_norm_nocut` (bản chạy lại) phân vị tương tự: rel2 p50 0,880, rel1 0,871, rel0 0,858, unjudged 0,849; top-1 OOC 0,857 / 0,857 / 0,866.

Đọc: để 3 câu ngoài catalog rỗng cần cutoff ≥ 0,87, khi đó 28/128 câu trong catalog cũng rỗng và 227 kết quả rel ≥ 1 bị cắt — không có
ngưỡng tuyệt đối nào tách được hai nhóm. Khoảng cách rel 2 ↔ rel 0 chỉ ≈ 0,02 cosine (Cohere v3 rộng hơn nhiều, cutoff 0,62 tách được).
Hệ quả cho sản phẩm: trên e5, `out_of_catalog` phải xử lý bằng ngưỡng theo margin so với nền (S2 contract §2.4) hoặc bằng tín hiệu khác
(BM25 không khớp token nào), không bằng cosine tuyệt đối.

## 6. F1 — lọc điểm đến suy từ câu, chi tiết

- Quyết định trên 131 câu (`diagnostics.destinationFilter`): `source = query` 108; bỏ vì câu vé máy bay 10; bỏ vì ≥ 2 địa danh 1; không có địa
  danh 12. Fallback `dropped_empty`: 0 (nocut) / 1 (`hybrid_norm_dest`, cutoff 0,84; biến mất khi thêm F2).
- `filter_recall_loss` Σ 10 trên 108 câu: 10 nhãn rel ≥ 1 nằm ngoài điểm đến suy ra (nhãn gán cho sản phẩm nơi khác hoặc gazetteer suy sai).
- Trên mốc không cutoff, 80/108 câu đổi recall hoặc nDCG. Tăng mạnh nhất (recall@10 full trước → sau): c0147 `audience_style` 0,30 → 0,90;
  c0165 `audience_style` 0,05 → 0,36; c0531 `multi_constraint` 0,21 → 0,36; c0555 `cross_vertical` 0,15 → 0,37; c0202 `amenity_single` 0,13 →
  0,27; c0052 `dest_type` 0,05 → 0,18; c0085 `dest_type` 0,11 → 0,21; c0321 `named_entity` 0,20 → 0,60; c0304 `parent_child` 0,33 → 0,58.
  Giảm mạnh nhất: c0460 `abbrev_typo` 0,45 → 0,30 (nDCG 0,671 → 0,453); c0403 `no_diacritics` 0,38 → 0,31 (nDCG 1,000 → 0,832); c0307
  `parent_child` 0,23 → 0,18; c0284 `parent_child` 0,38 → 0,29; c0514 `multi_constraint` 0,28 → 0,22; c0259 `amenity_offtaxonomy` 0,23 →
  0,21. Mẫu thua lặp lại: câu viết tắt / không dấu mà gazetteer bắt địa danh đồng âm, và câu `parent_child` có nhãn cho sản phẩm ở nơi lân cận.
- Latency: arm có F1 có Weaviate p50 **10,5–13,1 ms** so 50–54 ms ở arm không lọc (p95 ≈ 52–57 ms cả hai), vì mask id gửi lên Weaviate thu
  hẹp từ gần toàn bộ catalog xuống một điểm đến — khớp đòn bẩy "bỏ mask khi mask ≈ toàn bộ" đã ghi ở `eval-2026-10-01-search-cloud-latency.md`.
  Số đo trên Docker local 3.183 object, không phải số cloud.

## 7. F2 — câu không dấu, chi tiết

- 19/131 câu gắn `queryProfile = no_diacritics` (`is_unaccented`, ≥ 3 token chữ): 12 câu slice `no_diacritics` + 7 câu slice khác gõ không
  dấu (`abbrev_typo`, …).
- Không cutoff: 0/19 câu đổi top-10 (131/131 giống mốc) — kết luận 2 ở §1.
- Cutoff 0,84, `no_diacritics.cutoff = null`: 4 câu đổi, +2,96 điểm trên slice `no_diacritics` (c0426 0,18 → 0,36 recall; c0388 0,08 → 0,20;
  c0379 0,21 → 0,24; c0394 0,25 → 0,20).
- Cutoff 0,84, `no_diacritics.cutoff = 0,80` (`_nc80`): 11 câu đổi, **+14,47** điểm trên `no_diacritics` (về đúng 0,525 của mốc không cutoff);
  tăng: c0433 0,04 → 0,30, c0385 0,10 → 0,35, c0426 0,18 → 0,45, c0388 0,08 → 0,24, c0400 0,24 → 0,38, c0466 (`abbrev_typo`) 0,21 → 0,31;
  giảm: c0394 0,25 → 0,15, c0383 0,20 → 0,15. Slice khác không đổi (các câu có dấu không qua profile).
- Khoá cache embed và vector câu không đổi; F2 không phục hồi dấu trước khi embed (unigram sai ở sạn/sân, hồ/hộ — ghi là hướng tuần sau).

## 8. So cặp có CI (paired bootstrap, `sb compare`, Δ = B − A, điểm %)

Win rule `config/sbench.yaml`: WIN nếu Δrecall ≥ 2,0 **và** p < 0,05 **và** không slice nào thua > 3,0; không WIN thì TIE nếu |ΔnDCG| < 2,0;
còn lại LOSE. **Cách đọc:** nhãn LOSE ở đây xuất hiện cả khi B tốt hơn A có ý nghĩa nhưng Δrecall < 2,0 (ví dụ cặp 2, 10) — luôn đọc kèm CI.

| # | A → B | thang | Δrecall@10 [CI95], p | ΔnDCG@10 [CI95], p | slice thua nặng nhất | kết luận |
|---|---|---|---|---|---|---|
| 1 | dense_nocut → hybrid_nocut | full | +0,05 [−1,65; +1,82], 0,487 | +1,74 [−1,90; +5,37], 0,160 | cross_vertical −20,13 | TIE |
| 1 | | cond | +0,05 [−1,65; +1,82] | +1,54 [−2,03; +5,17] | cross_vertical −19,64 | TIE |
| 2 | hybrid_nocut → hybrid_norm_nocut | full | +1,66 [+0,52; +3,02], 0,000 | +2,49 [+0,84; +4,43], 0,000 | multi_constraint −0,00 | LOSE (Δrecall < 2,0) |
| 2 | | cond | +1,66 [+0,52; +3,02] | +2,45 [+0,81; +4,42] | multi_constraint −0,15 | LOSE (Δrecall < 2,0) |
| 3 | dense_nocut → hybrid_norm_nocut | full | +1,71 [−0,46; +3,94], 0,063 | +4,23 [+0,18; +8,61], 0,018 | cross_vertical −20,13 | LOSE |
| 3 | | cond | +1,71 [−0,46; +3,94] | +4,00 [−0,05; +8,19], 0,028 | cross_vertical −19,64 | LOSE |
| 4 | hybrid_norm_nocut → nocut_dest (F1) | full | **+2,34 [+1,03; +3,84], 0,000** | +2,56 [+0,67; +4,63], 0,006 | abbrev_typo −2,86 | **WIN** |
| 4 | | cond | +2,34 [+1,03; +3,84] | +2,88 [+1,03; +4,84], 0,001 | parent_child −2,01 | **WIN** |
| 5 | hybrid_norm_nocut → nocut_nodia (F2) | full / cond | +0,00 [+0,00; +0,00] | +0,00 | — | TIE (giống hệt) |
| 6 | hybrid_norm_nocut → nocut_dest_nodia | full / cond | như cặp 4 | như cặp 4 | như cặp 4 | **WIN** (giống hệt nocut_dest) |
| 7 | hybrid_norm_nocut → hybrid_norm (cutoff 0,84) | full | −0,65 [−1,98; +0,61], 0,853 | −1,10 [−2,84; +0,42] | **no_diacritics −14,47** | TIE |
| 7 | | cond | −0,65 [−1,98; +0,61] | −1,11 [−3,02; +0,57] | no_diacritics −15,48 | TIE |
| 8 | hybrid_norm → _dest (F1, cutoff) | full | +1,53 [+0,41; +2,82], 0,001 | +1,52 [−0,19; +3,32], 0,040 | no_diacritics −3,91 | TIE |
| 8 | | cond | +1,53 [+0,41; +2,82] | +1,83 [+0,16; +3,69], 0,016 | no_diacritics −3,83 | TIE |
| 9 | hybrid_norm → _nodia (F2, cutoff) | full | +0,22 [−0,05; +0,64], 0,078 | +0,28 [−0,07; +0,77] | — (no_diacritics +2,96) | TIE |
| 9 | | cond | +0,22 [−0,05; +0,64] | +0,31 [−0,10; +0,88] | — (no_diacritics +3,32) | TIE |
| 10 | hybrid_norm → _dest_nodia | full | +1,77 [+0,65; +3,02], 0,000 | +1,93 [+0,32; +3,67], 0,010 | abbrev_typo −2,86 | TIE |
| 10 | | cond | +1,77 [+0,65; +3,02] | +2,30 [+0,71; +4,11], 0,004 | parent_child −2,01 | LOSE (Δrecall < 2,0) |
| 11 | hybrid_norm → _nodia_nc80 | full | +0,89 [+0,18; +1,82], 0,001 | +1,49 [+0,41; +3,05], 0,000 | — (no_diacritics **+14,47**) | TIE |
| 11 | | cond | +0,89 [+0,18; +1,82] | +1,59 [+0,42; +3,17] | — (no_diacritics +15,48) | TIE |
| 12 | hybrid_norm_nodia → _nodia_nc80 | full | +0,67 [+0,11; +1,44], 0,007 | +1,22 [+0,28; +2,60], 0,001 | — (no_diacritics +11,51) | TIE |
| 13 | hybrid_norm → _dest_nodia_nc80 | full | **+2,82 [+1,41; +4,34], 0,000** | **+3,54 [+1,48; +5,78], 0,000** | parent_child −1,67 | **WIN** |
| 13 | | cond | +2,82 [+1,41; +4,34] | **+3,90 [+1,85; +6,18], 0,000** | parent_child −2,01 | **WIN** |
| 14 | hybrid_norm_dest_nodia → _dest_nodia_nc80 | full | +1,05 [+0,26; +2,12], 0,000 | +1,61 [+0,41; +3,30] | — (no_diacritics +15,74) | TIE |
| 15 | hybrid_norm_nocut → hybrid_norm_nodia_nc80 | full | +0,24 [−0,74; +1,26], 0,323 | +0,40 [−0,37; +1,37], 0,215 | named_entity −1,28 | TIE |
| 15 | | cond | +0,24 [−0,74; +1,26] | +0,48 [−0,36; +1,59] | named_entity −1,30 | TIE |

Slice Δ nDCG (full) của cặp 13 — tổ hợp đề nghị so mốc có cutoff: no_diacritics +16,00 · dest_type +5,52 · cross_vertical +3,45 ·
named_entity +3,05 · abbrev_typo −1,39 · parent_child −1,67 (condensed: +16,62 / +6,45 / +3,61 / +3,38 / +0,45 / −2,01).

## 9. Tái lập và phát hiện index chưa ổn định

- Run kiểm `2026-10-05-e5s-det` (2 arm, chạy lại từ đầu sau khi collection đã nạp > 10 phút): `dense_nocut` trùng **131/131** top-10 với run
  chính; `hybrid_norm_nocut` của run chính (bản ghi lúc 12:33:52, ~25 s sau khi nạp collection) chỉ trùng **3/131**, nDCG 0,422 / Judged 0,509 —
  trong khi bản det trùng **131/131** với `hybrid_norm_nocut_nodia` của run chính (ghi 12:34:02, không câu nào có profile đổi kết quả ở
  nocut). Hai arm khác ghi trong cùng cửa sổ (`hybrid_nocut` 12:33:39, `hybrid_norm_nocut_dest` 12:33:55) cũng lệch; mọi arm ghi từ 12:34:02
  trở đi ổn định. Engine chạy trực tiếp cho kết quả xác định.
- Kết luận: ngay sau `load_collection` (import batch 3.183 object), truy vấn BM25 của Weaviate trả tập khác trong khoảng ~30 s đầu (inverted
  index đang hoàn tất); dense không bị ảnh hưởng. Sửa: `app_adapter.load_collection` thêm `wait_bm25_stable` (dò 3 câu BM25 tới khi kết quả
  đứng yên 2 s, timeout 120 s) sau `wait_index_ready`; ba arm bị ảnh hưởng chạy lại `--force` (12:45): `hybrid_norm_nocut` trùng 131/131 với
  det và với `_nodia`; `nocut_dest` trùng 131/131 với `nocut_dest_nodia`. Mọi số trong report là bản chạy lại.
- Hệ quả cho run cũ: các run APP trước (30/09, 01/10 trên Cohere) nạp collection rồi chạy ngay — cần kiểm lại arm hybrid đầu tiên của mỗi run
  bằng cách so với bản chạy lại; chưa làm trong report này.

## 10. Latency và sanity

- `sb latency embed --models e5-small` (131 câu gold, warmup 20, CPU laptop i5, transformers + torch): **p50 6,7 ms / p95 10,3 ms** →
  `bench_out/search/runs/2026-10-05-fix-search-e5s/latency-embed.json`. So Cohere API miss p95 437 ms trên VM (`eval-2026-10-01-search-cloud-latency.md`).
- `sb sanity --arm APP.e5s.hybrid_norm_nocut`: 4/4 PASS — `input_type_vectors_differ` (mean 1 − cos(query, document) = 0,0475 > 0,005),
  `cache_recheck` (min cos 1,000000), `collection_counts` (`ProductBench_e5_small` = 3.183), `gold_append_ok`.
- Weaviate p50/p95 từng arm (Docker local, đã gồm mask id): dense_nocut 33,5 / 39,7 ms; hybrid không lọc 50–54 / 55–71 ms; hybrid có F1
  10,5–13,1 / 51,7–56,4 ms.

## 11. Caveat

1. **Chưa đo trên pipeline Cohere đang chạy production** — không có arm Cohere trong run (người dùng chốt 05/10 không gọi Cohere). F1/F2
   trên Cohere có thể khác về độ lớn, nhất là F2 vì phụ thuộc cutoff.
2. **Chưa đo qua HTTP** (`sb latency http`, `sb parity`): backend chưa có adapter e5 (chờ chốt đề xuất FR-SRC-02); số ở đây là offline qua
   `SearchProducts` trong tiến trình bench.
3. **Trong mẫu:** 0,84 / 0,80 và các ngưỡng F2 chọn trên toàn gold_v3; không có dev/test split (chờ `devtest.py`). Không chốt ngưỡng từ report này.
4. **Hole nhãn:** Judged@10 0,79–0,87 (full), `no_diacritics` 0,62–0,67 → không bù nhãn, đọc condensed cạnh full; không nói thắng/thua Cohere.
5. `abbrev_typo` là slice từng dùng để viết `QueryNormalizer` (số trong mẫu, caveat đã ghi ở `docs/spec/bench/arms.md`).
6. F2 chỉ chạm 19 câu; mọi Δ của nó dựa trên ≤ 12 câu slice.
7. Phủ định (`amenity_negation`) và chiều bay chưa làm (chờ câu gold mới của người dùng); F1 cố ý bỏ lọc câu vé máy bay.

## 12. Lệnh tái sinh

Từ `src/` với `.venv-sbench`, biến môi trường theo `localenv` (Weaviate bench `127.0.0.1:58080/55051`), không cần khoá API nào:

```bash
docker compose -f evaluation/search_bench/docker/compose.yml up -d --wait
sb embed --variant T3+R --model e5-small                       # vector document, prefix passage:
sb app-load --model e5-small                                   # ProductBench_e5_small 3.183, có wait_bm25_stable
sb sanity --arm APP.e5s.hybrid_norm_nocut
sb --run-id 2026-10-05-fix-search-e5s run \
  --arm APP.e5s.dense_nocut --arm APP.e5s.hybrid_nocut --arm APP.e5s.hybrid_norm_nocut \
  --arm APP.e5s.hybrid_norm_nocut_dest --arm APP.e5s.hybrid_norm_nocut_nodia --arm APP.e5s.hybrid_norm_nocut_dest_nodia \
  --arm APP.e5s.hybrid_norm --arm APP.e5s.hybrid_norm_dest --arm APP.e5s.hybrid_norm_nodia --arm APP.e5s.hybrid_norm_dest_nodia \
  --arm APP.e5s.hybrid_norm_nodia_nc80 --arm APP.e5s.hybrid_norm_dest_nodia_nc80
sb --run-id 2026-10-05-fix-search-e5s compare APP.e5s.hybrid_norm_nocut APP.e5s.hybrid_norm_nocut_dest [--condensed]   # và các cặp §8
sb --run-id 2026-10-05-fix-search-e5s latency embed --models e5-small
```

`sb` = `python -m evaluation.search_bench` (`PYTHONPATH=<repo>/src`, `PYTHONUTF8=1`). Bảng §3–§4 từ `per_query.parquet` (script
`e5_tables.py`: đếm `extra.destinationFilter.source / skipped / fallback`, `extra.queryProfile`, `filter_recall_loss`, nDCG full /
condensed theo slice); §5 từ `e5_cutoff.py` (ghép `top_ids` / `top_scores` với `gold.jsonl`). Hai script là tiện ích đọc parquet, không chạy
retrieval; logic giống `sb compare --condensed`.
