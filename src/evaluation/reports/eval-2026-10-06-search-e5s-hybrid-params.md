# Search e5-small — sweep tham số hybrid còn lại (`min_coverage`, `rrf_k`, `candidate_k`, `lexical_candidate_k`, `lexical_k`, cutoff) và thử filter điểm đến cho `cross_vertical` (05–06/10/2026)

- Phục vụ: FR-SRC-01..04, NFR-PERF-01 (chất lượng, không đo latency); việc mở của `eval-2026-10-05-search-day5-e5s-app.md` §11 (`cross_vertical`)
  và §13 ("`lexical_k` và `min_coverage` chưa sweep"); đề xuất đổi model `docs/prd/update/2026-10-05-fr-src-02-embedding-local-e5-small.md`
  (chờ chốt); đề xuất rút ra từ report này: `docs/prd/update/2026-10-06-search-hybrid-min-coverage-rrf.md`.
- Commit: `ac7642a` + working tree chưa commit; **không sửa code / config**. Đo bằng `SearchProducts` thật của backend qua cổng APP
  (`app_adapter.retrieve_app`), arm gốc `APP.e5s.hybrid_norm` (hybrid + QueryNormalizer = cấu hình production), collection
  `ProductBench__e5_small` trên Weaviate bench local (`sbench-weaviate-1`, đã nạp từ 05/10 — guard BM25 đã ổn định), gold `gold_v3`,
  split `gold/splits/devtest@gold_v3.json` (dev 66 / test 65 câu; 2 câu không có kết quả kỳ vọng nằm ngoài catalog).
- Mốc so sánh: arm gốc với `cutoff 0,85` (giá trị trong đề xuất PRD), còn lại như arm: `rrf_k 60 · lexical_k 10 · lexical_cutoff 0,50 ·
  min_coverage 0,6 · candidate_k 200 · lexical_candidate_k 50`. Mỗi lần đổi một tham số (hoặc tổ hợp ở §2); chọn trên dev, kiểm trên test.
  CI = paired bootstrap 10.000 lượt theo câu, seed 42 (`metrics.paired_bootstrap`), Δ = mới − mốc, điểm ×100.

> **Đọc cùng PR #108** (`eval-2026-10-05-search-e5s-dest-nodia.md`, merge vào nhánh sau khi lượt đo này chạy): F1 lọc điểm đến và F2 cutoff
> riêng cho câu không dấu, mốc cutoff tạm 0,84, gold_v4 đã có. Số ở đây đo **không bật F1/F2**, cutoff 0,85, gold_v3 — chưa so trực tiếp được.
> Hai report nhất quán ở một điểm: `min_coverage` / `lexical_k` chỉ có tác dụng khi cutoff cắt bớt nhánh dense.

> Gold 131 câu: một câu = ~1,5 điểm nDCG ở mỗi nửa. Các cấu hình mới đưa lên top-10 một số sản phẩm **chưa có nhãn** (cột judged@10) — chưa
> nhãn tính là không liên quan, nên Δ có thể bị đánh giá thấp hoặc cao tuỳ chất lượng phần chưa nhãn; cần gán nhãn (đợt D6a) trước khi chốt.

## 1. Kết luận nhanh

1. **`min_coverage` là tham số có tác động lớn nhất còn lại.** 0,6 → 0,1: nDCG@10 dev +2,59 [−0,53; +6,43], test +1,59 [−0,77; +4,55],
   gộp 128 câu **+2,10 [+0,03; +4,44]**; zero-result trong catalog 1,6 % → **0 %**; câu không dấu (`no_diacritics`) 0,284 → **0,583** gộp
   (dev 0,327 → 0,676, test 0,240 → 0,490). Slice tụt: `audience_style` −5,6 (n = 11), `multi_constraint` −6,6 dev (n = 5).
   `min_coverage` 0,0 / 0,1 / 0,2 cho test như nhau (0,664–0,666); 0,3 trở lên mất phần lớn lợi ích câu không dấu.
2. **`rrf_k` nhỏ giúp `cross_vertical`**: `rrf_k` 10 → slice này dev 0,604 → 0,757, test 0,564 → 0,665 (gộp 0,584 → 0,711, n = 10) nhưng
   tổng nDCG không đổi có ý nghĩa (+0,82 [−0,44; +2,19]). `rrf_k` 30 nhẹ hơn và đều hơn: gộp **+0,72 [+0,10; +1,45]**.
3. **Tổ hợp tốt nhất: `min_coverage 0,1 + rrf_k 30`** — dev +3,09 [−0,20; +7,05], test +1,84 [−0,73; +4,96], gộp **+2,48 [+0,29; +4,92]**,
   Recall@10 gộp +1,89 [+0,61; +3,33], zero-result 0 %, `no_diacritics` 0,284 → 0,589, `cross_vertical` 0,584 → 0,625. Thêm
   `lexical_candidate_k 20` không tăng thêm trên test.
4. **Giữ nguyên:** `candidate_k` 200 (50 / 100 / 400 không hơn trên test), `lexical_k` 10 (5 / 20 / 50 bằng hoặc kém), `lexical_candidate_k`
   50 (100 / 200 kém rõ: test −1,3 nDCG; 20 hơn nhẹ không ý nghĩa), **cutoff 0,85** — với `min_coverage 0,1` cutoff 0,85 vẫn tốt nhất cả
   dev (0,704) lẫn test (0,664) trong 0,80–0,87, khớp đề xuất PRD.
5. **Filter điểm đến (oracle — cận trên của QU) cho 10 câu `cross_vertical`:** 0,584 → 0,657, Δ +7,35 [−1,90; +17,19] — không đủ bằng chứng,
   không lấp được khoảng cách −26 so với Cohere. 4 câu tăng mạnh (Hải Phòng +0,38, Nha Trang +0,20, Nghệ An +0,17, Cần Thơ +0,16), 3 câu
   giảm (Buôn Ma Thuột −0,18, Huế −0,07, Hạ Long −0,04); judged@10 0,70 → 0,68 nên một phần do kết quả chưa nhãn. `rrf_k` nhỏ (mục 2) đem
   lại cùng cỡ cải thiện mà không cần QU.
6. **Đề xuất (chưa áp dụng; phải đối chiếu F1/F2 và đo lại trên gold_v4 trước khi chốt):** khi đổi production sang e5-small, cân nhắc `SEARCH_MIN_COVERAGE` 0,1–0,2 và `rrf_k` 30 cùng `cutoff 0,85`.
   Trước khi chốt: gán nhãn các cặp mới vào top-10 (judged@10 giảm ~1 điểm), rescore, đặt lại `baseline_v1`, rồi `sb regress`. Nếu các giá
   trị này khác điều PRD / contract đang ghi, đưa vào đề xuất `docs/prd/update/` trước khi sửa config.

## 2. CI so cặp các ứng viên (`search_ci.py`, phụ lục A)

| Cấu hình (so với mốc cutoff 0,85) | split | n | nDCG@10 mốc → mới | Δ nDCG@10 [CI95] p | Δ Recall@10 [CI95] | Δ MRR@10 | zero-result mốc → mới | judged@10 mốc → mới | cross_vertical | no_diacritics | slice thấp nhất |
|---|---|---:|---|---|---|---:|---|---|---|---|---|
| min_coverage=0.1 | dev | 65 | 0.678 → 0.704 | +2.59 [-0.53; +6.43] p 0.057 | +1.90 [+0.14; +4.09] | +1.85 | 0.015 → 0.000 | 0.873 → 0.867 | 0.604 → 0.604 | 0.327 → 0.676 | multi_constraint -6.6 (n=5) |
| min_coverage=0.1 | test | 63 | 0.648 → 0.664 | +1.59 [-0.77; +4.55] p 0.116 | +1.41 [-0.23; +3.29] | +0.98 | 0.016 → 0.000 | 0.850 → 0.838 | 0.564 → 0.564 | 0.240 → 0.490 | audience_style -6.9 (n=6) |
| min_coverage=0.1 | all | 128 | 0.663 → 0.684 | **+2.10** [+0.03; +4.44] p 0.023 | +1.66 [+0.43; +3.06] | +1.42 | 0.016 → 0.000 | 0.862 → 0.853 | 0.584 → 0.584 | 0.284 → 0.583 | audience_style -5.6 (n=11) |
| rrf_k=10 | dev | 65 | 0.678 → 0.691 | +1.30 [-0.50; +3.38] p 0.087 | +0.88 [-0.24; +2.10] | -0.85 | 0.015 → 0.015 | 0.873 → 0.898 | 0.604 → 0.757 | 0.327 → 0.329 | amenity_negation -5.7 (n=3) |
| rrf_k=10 | test | 63 | 0.648 → 0.651 | +0.33 [-1.40; +2.19] p 0.374 | +0.23 [-0.43; +0.92] | -0.15 | 0.016 → 0.016 | 0.850 → 0.874 | 0.564 → 0.665 | 0.240 → 0.210 | no_diacritics -3.1 (n=6) |
| rrf_k=10 | all | 128 | 0.663 → 0.672 | +0.82 [-0.44; +2.19] p 0.108 | +0.56 [-0.10; +1.26] | -0.51 | 0.016 → 0.016 | 0.862 → 0.886 | 0.584 → 0.711 | 0.284 → 0.270 | amenity_negation -2.1 (n=5) |
| rrf_k=30 | dev | 65 | 0.678 → 0.687 | +0.85 [-0.09; +2.06] p 0.041 | +0.46 [-0.09; +1.12] | +0.06 | 0.015 → 0.015 | 0.873 → 0.889 | 0.604 → 0.664 | 0.327 → 0.340 | parent_child -1.3 (n=6) |
| rrf_k=30 | test | 63 | 0.648 → 0.654 | +0.58 [-0.18; +1.45] p 0.077 | +0.20 [-0.07; +0.48] | +0.74 | 0.016 → 0.016 | 0.850 → 0.866 | 0.564 → 0.599 | 0.240 → 0.236 | no_diacritics -0.5 (n=6) |
| rrf_k=30 | all | 128 | 0.663 → 0.670 | **+0.72** [+0.10; +1.45] p 0.010 | +0.33 [+0.03; +0.68] | +0.39 | 0.016 → 0.016 | 0.862 → 0.878 | 0.584 → 0.632 | 0.284 → 0.288 | abbrev_typo -0.7 (n=12) |
| lexical_candidate_k=20 | dev | 65 | 0.678 → 0.687 | +0.89 [-0.80; +2.57] p 0.146 | +0.84 [-0.09; +1.79] | -1.25 | 0.015 → 0.015 | 0.873 → 0.906 | 0.604 → 0.614 | 0.327 → 0.357 | multi_constraint -5.0 (n=5) |
| lexical_candidate_k=20 | test | 63 | 0.648 → 0.660 | +1.22 [-1.06; +3.60] p 0.153 | -0.13 [-1.67; +1.14] | +1.50 | 0.016 → 0.016 | 0.850 → 0.876 | 0.564 → 0.599 | 0.240 → 0.235 | multi_constraint -2.2 (n=4) |
| lexical_candidate_k=20 | all | 128 | 0.663 → 0.674 | +1.05 [-0.36; +2.52] p 0.074 | +0.36 [-0.52; +1.16] | +0.10 | 0.016 → 0.016 | 0.862 → 0.891 | 0.584 → 0.607 | 0.284 → 0.296 | multi_constraint -3.7 (n=9) |
| candidate_k=50 | dev | 65 | 0.678 → 0.687 | +0.83 [-0.24; +2.31] p 0.090 | +0.46 [-0.11; +1.22] | -0.17 | 0.015 → 0.015 | 0.873 → 0.884 | 0.604 → 0.671 | 0.327 → 0.327 | abbrev_typo -1.6 (n=6) |
| candidate_k=50 | test | 63 | 0.648 → 0.645 | -0.31 [-1.23; +0.46] p 0.754 | -0.05 [-0.34; +0.22] | -1.72 | 0.016 → 0.016 | 0.850 → 0.858 | 0.564 → 0.562 | 0.240 → 0.195 | no_diacritics -4.6 (n=6) |
| candidate_k=50 | all | 128 | 0.663 → 0.666 | +0.27 [-0.46; +1.10] p 0.252 | +0.21 [-0.12; +0.61] | -0.93 | 0.016 → 0.016 | 0.862 → 0.871 | 0.584 → 0.616 | 0.284 → 0.261 | no_diacritics -2.3 (n=12) |
| min_coverage=0.1 + rrf_k=10 | dev | 65 | 0.678 → 0.708 | +3.02 [-0.59; +7.19] p 0.055 | +2.36 [+0.33; +4.68] | +0.19 | 0.015 → 0.000 | 0.873 → 0.892 | 0.604 → 0.710 | 0.327 → 0.663 | multi_constraint -8.5 (n=5) |
| min_coverage=0.1 + rrf_k=10 | test | 63 | 0.648 → 0.661 | +1.26 [-1.90; +4.83] p 0.237 | +1.43 [-0.32; +3.43] | +2.78 | 0.016 → 0.000 | 0.850 → 0.865 | 0.564 → 0.620 | 0.240 → 0.499 | audience_style -9.2 (n=6) |
| min_coverage=0.1 + rrf_k=10 | all | 128 | 0.663 → 0.685 | +2.15 [-0.33; +4.83] p 0.043 | +1.90 [+0.54; +3.39] | +1.46 | 0.016 → 0.000 | 0.862 → 0.879 | 0.584 → 0.665 | 0.284 → 0.581 | audience_style -7.9 (n=11) |
| min_coverage=0.1 + rrf_k=30 | dev | 65 | 0.678 → 0.709 | +3.09 [-0.20; +7.05] p 0.033 | +2.23 [+0.40; +4.45] | +2.11 | 0.015 → 0.000 | 0.873 → 0.883 | 0.604 → 0.651 | 0.327 → 0.696 | multi_constraint -6.9 (n=5) |
| min_coverage=0.1 + rrf_k=30 | test | 63 | 0.648 → 0.666 | +1.84 [-0.73; +4.96] p 0.094 | +1.53 [-0.17; +3.45] | +1.77 | 0.016 → 0.000 | 0.850 → 0.859 | 0.564 → 0.598 | 0.240 → 0.482 | audience_style -8.0 (n=6) |
| min_coverage=0.1 + rrf_k=30 | all | 128 | 0.663 → 0.688 | **+2.48** [+0.29; +4.92] p 0.012 | +1.89 [+0.61; +3.33] | +1.94 | 0.016 → 0.000 | 0.862 → 0.871 | 0.584 → 0.625 | 0.284 → 0.589 | audience_style -6.7 (n=11) |
| min_coverage=0.1 + rrf_k=10 + lexical_candidate_k=20 | dev | 65 | 0.678 → 0.709 | +3.10 [-0.59; +7.35] p 0.052 | +2.07 [-0.03; +4.39] | +1.93 | 0.015 → 0.000 | 0.873 → 0.927 | 0.604 → 0.666 | 0.327 → 0.663 | multi_constraint -9.7 (n=5) |
| min_coverage=0.1 + rrf_k=10 + lexical_candidate_k=20 | test | 63 | 0.648 → 0.660 | +1.16 [-2.24; +4.73] p 0.260 | +0.66 [-1.58; +2.93] | +4.35 | 0.016 → 0.000 | 0.850 → 0.891 | 0.564 → 0.633 | 0.240 → 0.488 | multi_constraint -10.1 (n=4) |
| min_coverage=0.1 + rrf_k=10 + lexical_candidate_k=20 | all | 128 | 0.663 → 0.685 | +2.15 [-0.42; +4.85] p 0.052 | +1.37 [-0.16; +2.99] | +3.12 | 0.016 → 0.000 | 0.862 → 0.909 | 0.584 → 0.650 | 0.284 → 0.576 | multi_constraint -9.9 (n=9) |

Ghi chú: "gộp" (all) gồm cả nửa dev đã dùng để chọn giá trị nên lạc quan; đọc nửa test làm bằng chứng độc lập — ở test không cấu hình nào có
CI cắt 0 (n = 63), cùng hướng với dev.

## 3. `cross_vertical` với filter `destination` oracle (`search_extra.py`, phụ lục B; cutoff 0,85, `min_coverage` 0,6)

Điểm đến lấy bằng khớp chuỗi tên điểm đến của catalog (dài nhất trước) trong câu hỏi, truyền vào `SearchProducts(destination=…)` — đúng filter
`/search` đã nhận; các câu khác giữ kết quả không filter.

| qid | split | destination | nDCG@10 không → có filter | judged@10 không → có |
|---|---|---|---|---|
| c0541 | dev | Buôn Ma Thuột | 1.00 → 0.82 | 1.00 → 0.80 |
| c0546 | dev | Cần Thơ | 0.49 → 0.65 | 0.50 → 0.60 |
| c0547 | test | Huế | 0.78 → 0.71 | 0.70 → 0.60 |
| c0551 | test | Hà Nội | 0.50 → 0.56 | 0.80 → 0.50 |
| c0555 | dev | Hà Tĩnh | 0.94 → 0.95 | 0.90 → 1.00 |
| c0556 | test | Hạ Long | 0.87 → 0.83 | 0.80 → 0.80 |
| c0560 | dev | Hải Phòng | 0.40 → 0.78 | 0.30 → 0.70 |
| c0564 | test | Hội An | 0.37 → 0.39 | 0.70 → 0.60 |
| c0565 | dev | Nghệ An | 0.20 → 0.37 | 1.00 → 0.80 |
| c0569 | test | Nha Trang | 0.31 → 0.51 | 0.30 → 0.40 |
| **TB** | | | 0.584 → 0.657 (Δ +7.35 [-1.90; +17.19]) | 0.70 → 0.68 |

## 4. Bảng sweep nguyên văn (`sweep_app.py` của `eval-2026-10-05-search-day5-e5s-app.md` phụ lục E, không sửa)

Cột: nDCG@10, Recall@10, MRR@10, judged@10, nDCG@10 condensed, zero-result trong / ngoài catalog, số kết quả vớt từ BM25 (p50 / tổng) và
nDCG@10 theo slice `named_entity`, `no_diacritics`, `abbrev_typo`, `cross_vertical`. Lần sweep `min_coverage` dev đầu tiên in lặp ba dòng cuối
do hai lệnh ghi chung một log (đã bỏ dòng trùng).


**APP.e5s.hybrid_norm · e5-small · gold gold_v3 · split dev · cố định {'cutoff': 0.85} · sweep lexical_k**

| lexical_k | n | nDCG@10 | Recall@10 | MRR@10 | judged@10 | nDCG@10 condensed | zero-result trong catalog | zero-result ngoài catalog | kết quả vớt từ BM25 p50 / tổng | nDCG named_entity | nDCG no_diacritics | nDCG abbrev_typo | nDCG cross_vertical |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|
| 3.00 | 66 | 0.676 | 0.333 | 0.811 | 0.872 | 0.685 | 0.015 | 0.000 (n=1) | 0 / 9 | 0.805 | 0.315 | 0.602 | 0.604 |
| 5.00 | 66 | 0.677 | 0.334 | 0.811 | 0.872 | 0.686 | 0.015 | 0.000 (n=1) | 0 / 12 | 0.805 | 0.321 | 0.602 | 0.604 |
| 10.00 | 66 | 0.678 | 0.335 | 0.811 | 0.873 | 0.687 | 0.015 | 0.000 (n=1) | 0 / 19 | 0.805 | 0.327 | 0.610 | 0.604 |
| 20.00 | 66 | 0.678 | 0.335 | 0.811 | 0.872 | 0.687 | 0.015 | 0.000 (n=1) | 0 / 29 | 0.805 | 0.327 | 0.610 | 0.604 |
| 30.00 | 66 | 0.679 | 0.336 | 0.811 | 0.874 | 0.687 | 0.015 | 0.000 (n=1) | 0 / 34 | 0.805 | 0.327 | 0.614 | 0.604 |
| 50.00 | 66 | 0.679 | 0.336 | 0.811 | 0.874 | 0.687 | 0.015 | 0.000 (n=1) | 0 / 36 | 0.805 | 0.327 | 0.614 | 0.604 |

**APP.e5s.hybrid_norm · e5-small · gold gold_v3 · split dev · cố định {'cutoff': 0.85} · sweep min_coverage**

| min_coverage | n | nDCG@10 | Recall@10 | MRR@10 | judged@10 | nDCG@10 condensed | zero-result trong catalog | zero-result ngoài catalog | kết quả vớt từ BM25 p50 / tổng | nDCG named_entity | nDCG no_diacritics | nDCG abbrev_typo | nDCG cross_vertical |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|
| 0.30 | 66 | 0.698 | 0.346 | 0.834 | 0.866 | 0.708 | 0.000 | 0.000 (n=1) | 0 / 112 | 0.813 | 0.520 | 0.641 | 0.604 |
| 0.40 | 66 | 0.689 | 0.342 | 0.834 | 0.862 | 0.699 | 0.000 | 0.000 (n=1) | 0 / 69 | 0.813 | 0.430 | 0.610 | 0.604 |
| 0.50 | 66 | 0.684 | 0.340 | 0.818 | 0.861 | 0.694 | 0.000 | 0.000 (n=1) | 0 / 43 | 0.813 | 0.376 | 0.610 | 0.604 |
| 0.60 | 66 | 0.678 | 0.335 | 0.811 | 0.873 | 0.687 | 0.015 | 0.000 (n=1) | 0 / 19 | 0.805 | 0.327 | 0.610 | 0.604 |
| 0.70 | 66 | 0.671 | 0.329 | 0.803 | 0.865 | 0.679 | 0.031 | 0.000 (n=1) | 0 / 1 | 0.805 | 0.276 | 0.581 | 0.604 |
| 0.80 | 66 | 0.671 | 0.329 | 0.803 | 0.865 | 0.679 | 0.031 | 0.000 (n=1) | 0 / 1 | 0.805 | 0.276 | 0.581 | 0.604 |
| 1.00 | 66 | 0.671 | 0.329 | 0.803 | 0.865 | 0.679 | 0.031 | 0.000 (n=1) | 0 / 1 | 0.805 | 0.276 | 0.581 | 0.604 |

**APP.e5s.hybrid_norm · e5-small · gold gold_v3 · split dev · cố định {'cutoff': 0.85} · sweep min_coverage**

| min_coverage | n | nDCG@10 | Recall@10 | MRR@10 | judged@10 | nDCG@10 condensed | zero-result trong catalog | zero-result ngoài catalog | kết quả vớt từ BM25 p50 / tổng | nDCG named_entity | nDCG no_diacritics | nDCG abbrev_typo | nDCG cross_vertical |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|
| 0.00 | 66 | 0.703 | 0.354 | 0.829 | 0.868 | 0.716 | 0.000 | 0.000 (n=1) | 3 / 261 | 0.813 | 0.676 | 0.641 | 0.604 |
| 0.10 | 66 | 0.704 | 0.354 | 0.829 | 0.867 | 0.717 | 0.000 | 0.000 (n=1) | 3 / 237 | 0.813 | 0.676 | 0.641 | 0.604 |
| 0.20 | 66 | 0.697 | 0.352 | 0.822 | 0.865 | 0.711 | 0.000 | 0.000 (n=1) | 1 / 176 | 0.813 | 0.547 | 0.641 | 0.604 |
| 0.25 | 66 | 0.696 | 0.349 | 0.822 | 0.870 | 0.708 | 0.000 | 0.000 (n=1) | 1 / 139 | 0.813 | 0.533 | 0.641 | 0.604 |

**APP.e5s.hybrid_norm · e5-small · gold gold_v3 · split test · cố định {'cutoff': 0.85} · sweep min_coverage**

| min_coverage | n | nDCG@10 | Recall@10 | MRR@10 | judged@10 | nDCG@10 condensed | zero-result trong catalog | zero-result ngoài catalog | kết quả vớt từ BM25 p50 / tổng | nDCG named_entity | nDCG no_diacritics | nDCG abbrev_typo | nDCG cross_vertical |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|
| 0.00 | 65 | 0.666 | 0.327 | 0.738 | 0.848 | 0.677 | 0.000 | 0.000 (n=2) | 2 / 235 | 0.829 | 0.510 | 0.623 | 0.564 |
| 0.20 | 65 | 0.666 | 0.325 | 0.739 | 0.840 | 0.677 | 0.000 | 0.000 (n=2) | 1 / 162 | 0.834 | 0.490 | 0.623 | 0.564 |
| 0.30 | 65 | 0.654 | 0.318 | 0.717 | 0.826 | 0.666 | 0.000 | 0.000 (n=2) | 0 / 98 | 0.834 | 0.323 | 0.623 | 0.564 |
| 0.40 | 65 | 0.652 | 0.312 | 0.732 | 0.836 | 0.664 | 0.000 | 0.000 (n=2) | 0 / 54 | 0.829 | 0.303 | 0.624 | 0.564 |
| 0.50 | 65 | 0.653 | 0.312 | 0.734 | 0.842 | 0.665 | 0.016 | 0.000 (n=2) | 0 / 39 | 0.829 | 0.305 | 0.624 | 0.564 |
| 0.60 | 65 | 0.648 | 0.311 | 0.728 | 0.850 | 0.660 | 0.016 | 0.000 (n=2) | 0 / 21 | 0.829 | 0.240 | 0.624 | 0.564 |

**APP.e5s.hybrid_norm · e5-small · gold gold_v3 · split dev · cố định {'cutoff': 0.85} · sweep rrf_k**

| rrf_k | n | nDCG@10 | Recall@10 | MRR@10 | judged@10 | nDCG@10 condensed | zero-result trong catalog | zero-result ngoài catalog | kết quả vớt từ BM25 p50 / tổng | nDCG named_entity | nDCG no_diacritics | nDCG abbrev_typo | nDCG cross_vertical |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|
| 10.00 | 66 | 0.691 | 0.344 | 0.802 | 0.898 | 0.698 | 0.015 | 0.000 (n=1) | 0 / 19 | 0.819 | 0.329 | 0.592 | 0.757 |
| 30.00 | 66 | 0.687 | 0.340 | 0.811 | 0.889 | 0.695 | 0.015 | 0.000 (n=1) | 0 / 19 | 0.808 | 0.340 | 0.600 | 0.664 |
| 60.00 | 66 | 0.678 | 0.335 | 0.811 | 0.873 | 0.687 | 0.015 | 0.000 (n=1) | 0 / 19 | 0.805 | 0.327 | 0.610 | 0.604 |
| 100.00 | 66 | 0.679 | 0.336 | 0.811 | 0.872 | 0.688 | 0.015 | 0.000 (n=1) | 0 / 19 | 0.804 | 0.327 | 0.607 | 0.591 |
| 200.00 | 66 | 0.679 | 0.336 | 0.809 | 0.872 | 0.687 | 0.015 | 0.000 (n=1) | 0 / 19 | 0.800 | 0.327 | 0.607 | 0.593 |

**APP.e5s.hybrid_norm · e5-small · gold gold_v3 · split dev · cố định {'cutoff': 0.85} · sweep candidate_k**

| candidate_k | n | nDCG@10 | Recall@10 | MRR@10 | judged@10 | nDCG@10 condensed | zero-result trong catalog | zero-result ngoài catalog | kết quả vớt từ BM25 p50 / tổng | nDCG named_entity | nDCG no_diacritics | nDCG abbrev_typo | nDCG cross_vertical |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|
| 50.00 | 66 | 0.687 | 0.340 | 0.809 | 0.884 | 0.695 | 0.015 | 0.000 (n=1) | 0 / 19 | 0.805 | 0.327 | 0.594 | 0.671 |
| 100.00 | 66 | 0.680 | 0.336 | 0.811 | 0.878 | 0.690 | 0.015 | 0.000 (n=1) | 0 / 19 | 0.805 | 0.327 | 0.608 | 0.632 |
| 200.00 | 66 | 0.678 | 0.335 | 0.811 | 0.873 | 0.687 | 0.015 | 0.000 (n=1) | 0 / 19 | 0.805 | 0.327 | 0.610 | 0.604 |
| 400.00 | 66 | 0.679 | 0.335 | 0.818 | 0.873 | 0.688 | 0.015 | 0.000 (n=1) | 0 / 19 | 0.805 | 0.336 | 0.610 | 0.604 |

**APP.e5s.hybrid_norm · e5-small · gold gold_v3 · split dev · cố định {'cutoff': 0.85} · sweep lexical_candidate_k**

| lexical_candidate_k | n | nDCG@10 | Recall@10 | MRR@10 | judged@10 | nDCG@10 condensed | zero-result trong catalog | zero-result ngoài catalog | kết quả vớt từ BM25 p50 / tổng | nDCG named_entity | nDCG no_diacritics | nDCG abbrev_typo | nDCG cross_vertical |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|
| 20.00 | 66 | 0.687 | 0.344 | 0.798 | 0.906 | 0.695 | 0.015 | 0.000 (n=1) | 0 / 17 | 0.809 | 0.357 | 0.599 | 0.614 |
| 50.00 | 66 | 0.678 | 0.335 | 0.811 | 0.873 | 0.687 | 0.015 | 0.000 (n=1) | 0 / 19 | 0.805 | 0.327 | 0.610 | 0.604 |
| 100.00 | 66 | 0.660 | 0.331 | 0.774 | 0.860 | 0.670 | 0.015 | 0.000 (n=1) | 0 / 19 | 0.803 | 0.310 | 0.588 | 0.577 |
| 200.00 | 66 | 0.659 | 0.332 | 0.773 | 0.861 | 0.673 | 0.015 | 0.000 (n=1) | 0 / 19 | 0.792 | 0.311 | 0.581 | 0.610 |

**APP.e5s.hybrid_norm · e5-small · gold gold_v3 · split dev · cố định {'min_coverage': 0.1} · sweep cutoff**

| cutoff | n | nDCG@10 | Recall@10 | MRR@10 | judged@10 | nDCG@10 condensed | zero-result trong catalog | zero-result ngoài catalog | kết quả vớt từ BM25 p50 / tổng | nDCG named_entity | nDCG no_diacritics | nDCG abbrev_typo | nDCG cross_vertical |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|
| 0.80 | 66 | 0.693 | 0.347 | 0.825 | 0.849 | 0.704 | 0.000 | 0.000 (n=1) | 0 / 31 | 0.830 | 0.605 | 0.642 | 0.590 |
| 0.82 | 66 | 0.698 | 0.352 | 0.825 | 0.857 | 0.709 | 0.000 | 0.000 (n=1) | 0 / 72 | 0.836 | 0.638 | 0.642 | 0.590 |
| 0.84 | 66 | 0.702 | 0.352 | 0.830 | 0.863 | 0.714 | 0.000 | 0.000 (n=1) | 1 / 172 | 0.813 | 0.652 | 0.640 | 0.603 |
| 0.85 | 66 | 0.704 | 0.354 | 0.829 | 0.867 | 0.717 | 0.000 | 0.000 (n=1) | 3 / 237 | 0.813 | 0.676 | 0.641 | 0.604 |
| 0.86 | 66 | 0.701 | 0.352 | 0.822 | 0.889 | 0.715 | 0.000 | 0.000 (n=1) | 4 / 302 | 0.808 | 0.706 | 0.645 | 0.621 |
| 0.87 | 66 | 0.694 | 0.347 | 0.810 | 0.879 | 0.704 | 0.000 | 0.000 (n=1) | 6 / 400 | 0.813 | 0.722 | 0.683 | 0.685 |

**APP.e5s.hybrid_norm · e5-small · gold gold_v3 · split dev · cố định {'cutoff': 0.85, 'min_coverage': 0.1} · sweep lexical_k**

| lexical_k | n | nDCG@10 | Recall@10 | MRR@10 | judged@10 | nDCG@10 condensed | zero-result trong catalog | zero-result ngoài catalog | kết quả vớt từ BM25 p50 / tổng | nDCG named_entity | nDCG no_diacritics | nDCG abbrev_typo | nDCG cross_vertical |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|
| 5.00 | 66 | 0.699 | 0.348 | 0.834 | 0.884 | 0.711 | 0.000 | 0.000 (n=1) | 1 / 115 | 0.805 | 0.608 | 0.651 | 0.604 |
| 10.00 | 66 | 0.704 | 0.354 | 0.829 | 0.867 | 0.717 | 0.000 | 0.000 (n=1) | 3 / 237 | 0.813 | 0.676 | 0.641 | 0.604 |
| 20.00 | 66 | 0.702 | 0.352 | 0.828 | 0.864 | 0.715 | 0.000 | 0.000 (n=1) | 6 / 451 | 0.813 | 0.644 | 0.647 | 0.604 |
| 50.00 | 66 | 0.699 | 0.349 | 0.831 | 0.855 | 0.710 | 0.000 | 0.000 (n=1) | 12 / 938 | 0.813 | 0.653 | 0.631 | 0.603 |

**APP.e5s.hybrid_norm · e5-small · gold gold_v3 · split test · cố định {'cutoff': 0.85} · sweep rrf_k**

| rrf_k | n | nDCG@10 | Recall@10 | MRR@10 | judged@10 | nDCG@10 condensed | zero-result trong catalog | zero-result ngoài catalog | kết quả vớt từ BM25 p50 / tổng | nDCG named_entity | nDCG no_diacritics | nDCG abbrev_typo | nDCG cross_vertical |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|
| 10.00 | 65 | 0.651 | 0.313 | 0.727 | 0.874 | 0.660 | 0.016 | 0.000 (n=2) | 0 / 21 | 0.828 | 0.210 | 0.613 | 0.665 |
| 30.00 | 65 | 0.654 | 0.313 | 0.736 | 0.866 | 0.664 | 0.016 | 0.000 (n=2) | 0 / 21 | 0.829 | 0.236 | 0.620 | 0.599 |
| 60.00 | 65 | 0.648 | 0.311 | 0.728 | 0.850 | 0.660 | 0.016 | 0.000 (n=2) | 0 / 21 | 0.829 | 0.240 | 0.624 | 0.564 |
| 100.00 | 65 | 0.650 | 0.312 | 0.739 | 0.852 | 0.662 | 0.016 | 0.000 (n=2) | 0 / 21 | 0.829 | 0.256 | 0.628 | 0.561 |
| 200.00 | 65 | 0.650 | 0.313 | 0.739 | 0.853 | 0.662 | 0.016 | 0.000 (n=2) | 0 / 21 | 0.829 | 0.256 | 0.641 | 0.546 |

**APP.e5s.hybrid_norm · e5-small · gold gold_v3 · split test · cố định {'cutoff': 0.85} · sweep candidate_k**

| candidate_k | n | nDCG@10 | Recall@10 | MRR@10 | judged@10 | nDCG@10 condensed | zero-result trong catalog | zero-result ngoài catalog | kết quả vớt từ BM25 p50 / tổng | nDCG named_entity | nDCG no_diacritics | nDCG abbrev_typo | nDCG cross_vertical |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|
| 50.00 | 65 | 0.645 | 0.310 | 0.711 | 0.858 | 0.657 | 0.016 | 0.000 (n=2) | 0 / 21 | 0.829 | 0.195 | 0.613 | 0.562 |
| 100.00 | 65 | 0.643 | 0.309 | 0.723 | 0.850 | 0.654 | 0.016 | 0.000 (n=2) | 0 / 21 | 0.829 | 0.205 | 0.624 | 0.549 |
| 200.00 | 65 | 0.648 | 0.311 | 0.728 | 0.850 | 0.660 | 0.016 | 0.000 (n=2) | 0 / 21 | 0.829 | 0.240 | 0.624 | 0.564 |
| 400.00 | 65 | 0.648 | 0.311 | 0.728 | 0.850 | 0.660 | 0.016 | 0.000 (n=2) | 0 / 21 | 0.829 | 0.241 | 0.624 | 0.564 |

**APP.e5s.hybrid_norm · e5-small · gold gold_v3 · split test · cố định {'cutoff': 0.85} · sweep lexical_candidate_k**

| lexical_candidate_k | n | nDCG@10 | Recall@10 | MRR@10 | judged@10 | nDCG@10 condensed | zero-result trong catalog | zero-result ngoài catalog | kết quả vớt từ BM25 p50 / tổng | nDCG named_entity | nDCG no_diacritics | nDCG abbrev_typo | nDCG cross_vertical |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|
| 20.00 | 65 | 0.660 | 0.309 | 0.743 | 0.876 | 0.668 | 0.016 | 0.000 (n=2) | 0 / 20 | 0.820 | 0.235 | 0.637 | 0.599 |
| 50.00 | 65 | 0.648 | 0.311 | 0.728 | 0.850 | 0.660 | 0.016 | 0.000 (n=2) | 0 / 21 | 0.829 | 0.240 | 0.624 | 0.564 |
| 100.00 | 65 | 0.635 | 0.309 | 0.733 | 0.837 | 0.652 | 0.016 | 0.000 (n=2) | 0 / 21 | 0.834 | 0.204 | 0.577 | 0.544 |
| 200.00 | 65 | 0.634 | 0.306 | 0.731 | 0.834 | 0.653 | 0.016 | 0.000 (n=2) | 0 / 21 | 0.834 | 0.204 | 0.550 | 0.537 |

**APP.e5s.hybrid_norm · e5-small · gold gold_v3 · split test · cố định {'min_coverage': 0.1} · sweep cutoff**

| cutoff | n | nDCG@10 | Recall@10 | MRR@10 | judged@10 | nDCG@10 condensed | zero-result trong catalog | zero-result ngoài catalog | kết quả vớt từ BM25 p50 / tổng | nDCG named_entity | nDCG no_diacritics | nDCG abbrev_typo | nDCG cross_vertical |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|
| 0.80 | 65 | 0.655 | 0.319 | 0.731 | 0.794 | 0.666 | 0.000 | 0.000 (n=2) | 0 / 19 | 0.835 | 0.437 | 0.623 | 0.509 |
| 0.82 | 65 | 0.655 | 0.319 | 0.731 | 0.795 | 0.666 | 0.000 | 0.000 (n=2) | 0 / 55 | 0.835 | 0.437 | 0.623 | 0.509 |
| 0.84 | 65 | 0.655 | 0.320 | 0.732 | 0.821 | 0.667 | 0.000 | 0.000 (n=2) | 1 / 153 | 0.835 | 0.436 | 0.623 | 0.509 |
| 0.85 | 65 | 0.664 | 0.325 | 0.738 | 0.838 | 0.675 | 0.000 | 0.000 (n=2) | 2 / 205 | 0.829 | 0.490 | 0.623 | 0.564 |
| 0.86 | 65 | 0.655 | 0.314 | 0.736 | 0.845 | 0.666 | 0.000 | 0.000 (n=2) | 3 / 251 | 0.820 | 0.480 | 0.623 | 0.563 |
| 0.87 | 65 | 0.636 | 0.299 | 0.735 | 0.847 | 0.646 | 0.000 | 0.000 (n=2) | 5 / 317 | 0.820 | 0.476 | 0.612 | 0.574 |

**APP.e5s.hybrid_norm · e5-small · gold gold_v3 · split test · cố định {'cutoff': 0.85, 'min_coverage': 0.1} · sweep lexical_k**

| lexical_k | n | nDCG@10 | Recall@10 | MRR@10 | judged@10 | nDCG@10 condensed | zero-result trong catalog | zero-result ngoài catalog | kết quả vớt từ BM25 p50 / tổng | nDCG named_entity | nDCG no_diacritics | nDCG abbrev_typo | nDCG cross_vertical |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|
| 5.00 | 65 | 0.659 | 0.319 | 0.746 | 0.845 | 0.670 | 0.000 | 0.000 (n=2) | 1 / 104 | 0.836 | 0.399 | 0.623 | 0.564 |
| 10.00 | 65 | 0.664 | 0.325 | 0.738 | 0.838 | 0.675 | 0.000 | 0.000 (n=2) | 2 / 205 | 0.829 | 0.490 | 0.623 | 0.564 |
| 20.00 | 65 | 0.663 | 0.325 | 0.737 | 0.820 | 0.675 | 0.000 | 0.000 (n=2) | 3 / 365 | 0.835 | 0.474 | 0.623 | 0.564 |
| 50.00 | 65 | 0.657 | 0.322 | 0.736 | 0.801 | 0.671 | 0.000 | 0.000 (n=2) | 8 / 785 | 0.835 | 0.451 | 0.623 | 0.522 |

## 5. Tái sinh

```bash
cd src
export PYTHONPATH=.:<thư mục chứa script phụ lục> PYTHONUTF8=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
# Weaviate bench đang chạy và có ProductBench__e5_small (sb app-load --model e5-small; chờ guard BM25)
python sweep_app.py APP.e5s.hybrid_norm dev  lexical_k 3 5 10 20 30 50 --set cutoff=0.85
python sweep_app.py APP.e5s.hybrid_norm dev  min_coverage 0.0 0.1 0.2 0.25 0.3 0.4 0.5 0.6 0.7 0.8 1.0 --set cutoff=0.85
python sweep_app.py APP.e5s.hybrid_norm test min_coverage 0.0 0.2 0.3 0.4 0.5 0.6 --set cutoff=0.85
for sp in dev test; do
  python sweep_app.py APP.e5s.hybrid_norm $sp rrf_k 10 30 60 100 200 --set cutoff=0.85
  python sweep_app.py APP.e5s.hybrid_norm $sp candidate_k 50 100 200 400 --set cutoff=0.85
  python sweep_app.py APP.e5s.hybrid_norm $sp lexical_candidate_k 20 50 100 200 --set cutoff=0.85
  python sweep_app.py APP.e5s.hybrid_norm $sp cutoff 0.80 0.82 0.84 0.85 0.86 0.87 --set min_coverage=0.1
  python sweep_app.py APP.e5s.hybrid_norm $sp lexical_k 5 10 20 50 --set cutoff=0.85 --set min_coverage=0.1
done
python search_ci.py                    # §2
ONLY_CV=1 python search_extra.py       # §3 (bỏ ONLY_CV để in thêm CI min_coverage 0,1 / 0,2 / 0,3)
```

## Phụ lục A — `search_ci.py`

```python
"""CI so cặp các cấu hình app của APP.e5s.hybrid_norm so với mốc (cutoff 0.85, còn lại như arm). Từ src/: python search_ci.py"""
import numpy as np
from evaluation.search_bench import devtest as DT, paths, runner as R
from evaluation.search_bench.app_adapter import AppContext, retrieve_app
from evaluation.search_bench.arms import load_arm
from evaluation.search_bench.config import load_config, load_env
from evaluation.search_bench.embed import make_embedder
from evaluation.search_bench.metrics import paired_bootstrap

CANDS = {"min_coverage=0.1": {"min_coverage": 0.1}, "rrf_k=10": {"rrf_k": 10}, "rrf_k=30": {"rrf_k": 30},
         "lexical_candidate_k=20": {"lexical_candidate_k": 20}, "candidate_k=50": {"candidate_k": 50},
         "min_coverage=0.1 + rrf_k=10": {"min_coverage": 0.1, "rrf_k": 10},
         "min_coverage=0.1 + rrf_k=30": {"min_coverage": 0.1, "rrf_k": 30},
         "min_coverage=0.1 + rrf_k=10 + lexical_candidate_k=20": {"min_coverage": 0.1, "rrf_k": 10, "lexical_candidate_k": 20}}
load_env(); cfg = load_config(None)
env = R.load_env(cfg, "jsonl", paths.GOLD_JSONL, run_id="sweep")
assign = DT.load(env.gold_version)["assignment"]
arm0 = load_arm("APP.e5s.hybrid_norm")
ctx = AppContext.open(cfg, "jsonl", model=arm0.model)
emb = make_embedder(cfg, arm0.model, embedding_type=arm0.embedding_types, preflight=False)
run = lambda kw: {r["qid"]: r for r in R.score_arm(env, retrieve_app(arm0.model_copy(update={"app": {**arm0.app, "cutoff": 0.85, **kw}}), env, ctx, emb))[1]}
ok = lambda v: v is not None and not (isinstance(v, float) and np.isnan(v))
try:
    base = run({})
    print("| Cấu hình (so với mốc cutoff 0,85) | split | n | nDCG@10 mốc → mới | Δ nDCG@10 [CI95] p | Δ Recall@10 [CI95] | Δ MRR@10 | zero-result mốc → mới | judged@10 mốc → mới | cross_vertical | no_diacritics | slice thấp nhất |")
    print("|---|---|---:|---|---|---|---:|---|---|---|---|---|")
    for name, kw in CANDS.items():
        c = run(kw)
        for sp in ("dev", "test", "all"):
            q = [k for k in base if not base[k]["expected_no_result"] and (sp == "all" or assign.get(k) == sp)]
            g = lambda rr, m: {k: rr[k][m] for k in q}
            nd, rc, mr = (paired_bootstrap(g(base, m), g(c, m), n_boot=10000, seed=42) for m in ("ndcg@10", "recall@10", "mrr@10"))
            mean = lambda rr, m, qs=q: np.mean([rr[k][m] for k in qs if ok(rr[k][m])])
            sl = lambda s: [k for k in q if base[k]["slice"] == s]
            per = {}
            for k in q:
                if ok(base[k]["ndcg@10"]) and ok(c[k]["ndcg@10"]):
                    per.setdefault(base[k]["slice"], []).append((c[k]["ndcg@10"] - base[k]["ndcg@10"]) * 100)
            w = min(((s, np.mean(v), len(v)) for s, v in per.items()), key=lambda x: x[1])
            sig = "**" if nd["ci95"][0] > 0 or nd["ci95"][1] < 0 else ""
            print(f"| {name} | {sp} | {nd['n']} | {mean(base,'ndcg@10'):.3f} → {mean(c,'ndcg@10'):.3f} | {sig}{nd['delta']:+.2f}{sig} [{nd['ci95'][0]:+.2f}; {nd['ci95'][1]:+.2f}] p {nd['p_one_sided']:.3f} | "
                  f"{rc['delta']:+.2f} [{rc['ci95'][0]:+.2f}; {rc['ci95'][1]:+.2f}] | {mr['delta']:+.2f} | {mean(base,'zero_result'):.3f} → {mean(c,'zero_result'):.3f} | "
                  f"{mean(base,'judged@10'):.3f} → {mean(c,'judged@10'):.3f} | {mean(base,'ndcg@10',sl('cross_vertical')):.3f} → {mean(c,'ndcg@10',sl('cross_vertical')):.3f} | "
                  f"{mean(base,'ndcg@10',sl('no_diacritics')):.3f} → {mean(c,'ndcg@10',sl('no_diacritics')):.3f} | {w[0]} {w[1]:+.1f} (n={w[2]}) |", flush=True)
finally:
    ctx.close(); emb.close()
```

## Phụ lục B — `search_extra.py`

```python
"""05/10 tối: (1) CI so cặp min_coverage (cutoff 0,85 cố định) trên dev/test/all; (2) cross_vertical + filter destination oracle.
Chạy đúng SearchProducts (cổng APP). Không ghi run, không sửa config. Từ src/ với PYTHONPATH=. : python search_extra.py"""
import json, unicodedata
from time import perf_counter
import numpy as np
from evaluation.search_bench import devtest as DT, paths, runner as R
from evaluation.search_bench.app_adapter import AppContext, retrieve_app
from evaluation.search_bench.arms import load_arm
from evaluation.search_bench.config import load_config, load_env
from evaluation.search_bench.embed import make_embedder
from evaluation.search_bench.metrics import paired_bootstrap

load_env(); cfg = load_config(None)
env = R.load_env(cfg, "jsonl", paths.GOLD_JSONL, run_id="sweep")
assign = DT.load(env.gold_version)["assignment"]
arm0 = load_arm("APP.e5s.hybrid_norm")
ctx = AppContext.open(cfg, "jsonl", model=arm0.model)
emb = make_embedder(cfg, arm0.model, embedding_type=arm0.embedding_types, preflight=False)
def arm(**kw): return arm0.model_copy(update={"app": {**arm0.app, "cutoff": 0.85, **kw}})
def rows_of(a, retrieved=None):
    _, rows = R.score_arm(env, retrieved or retrieve_app(a, env, ctx, emb)); return {r["qid"]: r for r in rows}
try:
    base_ret = retrieve_app(arm(min_coverage=0.6), env, ctx, emb)
    base = rows_of(None, base_ret)
    import os
    print("## min_coverage vs 0.6 (cutoff 0.85), Δ = cand − 0.6, điểm ×100")
    print("| min_coverage | split | n | nDCG@10 0.6 → cand | Δ nDCG@10 [CI95] p | Δ Recall@10 [CI95] | Δ MRR@10 | judged@10 0.6 → cand | slice Δ nDCG thấp nhất |")
    print("|---:|---|---:|---|---|---|---:|---|---|")
    for mc in (() if os.environ.get("ONLY_CV") else (0.1, 0.2, 0.3)):
        cand = rows_of(arm(min_coverage=mc))
        for sp in ("dev", "test", "all"):
            q = [k for k in base if not base[k]["expected_no_result"] and (sp == "all" or assign.get(k) == sp)]
            f = lambda rr, m: {k: rr[k][m] for k in q}
            nd = paired_bootstrap(f(base, "ndcg@10"), f(cand, "ndcg@10"), n_boot=10000, seed=42)
            rc = paired_bootstrap(f(base, "recall@10"), f(cand, "recall@10"), n_boot=10000, seed=42)
            mr = paired_bootstrap(f(base, "mrr@10"), f(cand, "mrr@10"), n_boot=10000, seed=42)
            mean = lambda rr, m: np.nanmean([rr[k][m] for k in q if rr[k][m] is not None])
            sl = {}
            for k in q:
                if base[k]["ndcg@10"] is not None and cand[k]["ndcg@10"] is not None: sl.setdefault(base[k]["slice"], []).append((cand[k]["ndcg@10"] - base[k]["ndcg@10"]) * 100)
            worst = min(((s, float(np.mean(v)), len(v)) for s, v in sl.items()), key=lambda x: x[1])
            print(f"| {mc} | {sp} | {nd['n']} | {mean(base,'ndcg@10'):.3f} → {mean(cand,'ndcg@10'):.3f} | {nd['delta']:+.2f} [{nd['ci95'][0]:+.2f}; {nd['ci95'][1]:+.2f}] p {nd['p_one_sided']:.3f} | "
                  f"{rc['delta']:+.2f} [{rc['ci95'][0]:+.2f}; {rc['ci95'][1]:+.2f}] | {mr['delta']:+.2f} | {mean(base,'judged@10'):.3f} → {mean(cand,'judged@10'):.3f} | {worst[0]} {worst[1]:+.1f} (n={worst[2]}) |", flush=True)
    # (2) cross_vertical + destination oracle
    dests = sorted({d for d in ctx.cat.index.destination.tolist() if d}, key=len, reverse=True)
    nf = lambda s: unicodedata.normalize("NFC", s).lower()
    s = ctx.make_search(arm(min_coverage=0.6).app, emb)
    cv = [g for g in env.gold if g.slice == "cross_vertical"]
    out, dmap = [], {}
    for g in cv:
        d = next((d for d in dests if nf(d) in nf(g.text)), None); dmap[g.qid] = d
        t0 = perf_counter(); res = s.engine(g.text, destination=d, limit=env.k)
        out.append(R.Retrieved(qid=g.qid, top_ids=[r["productId"] for r in res["results"]], top_scores=[float(r["score"]) for r in res["results"]],
                               applied_filter=None, latency_ms=(perf_counter()-t0)*1000, extra={}))
    byq = {r.qid: r for r in out}
    filt = {r["qid"]: r for r in R.score_arm(env, [byq.get(r.qid, r) for r in base_ret])[1]}
    print("\n## cross_vertical: không filter vs filter destination oracle (cutoff 0.85, min_coverage 0.6)")
    print("| qid | split | destination | nDCG@10 không → có filter | judged@10 không → có |"); print("|---|---|---|---|---|")
    for g in cv:
        a, b = base[g.qid], filt[g.qid]
        print(f"| {g.qid} | {assign.get(g.qid)} | {dmap[g.qid]} | {a['ndcg@10'] or 0:.2f} → {b['ndcg@10'] or 0:.2f} | {a['judged@10'] or 0:.2f} → {b['judged@10'] or 0:.2f} |")
    q = [g.qid for g in cv]
    nd = paired_bootstrap({k: base[k]["ndcg@10"] for k in q}, {k: filt[k]["ndcg@10"] for k in q}, n_boot=10000, seed=42)
    print(f"| **TB** | | | {np.mean([base[k]['ndcg@10'] for k in q]):.3f} → {np.mean([filt[k]['ndcg@10'] for k in q]):.3f} (Δ {nd['delta']:+.2f} [{nd['ci95'][0]:+.2f}; {nd['ci95'][1]:+.2f}]) | "
          f"{np.mean([base[k]['judged@10'] for k in q]):.2f} → {np.mean([filt[k]['judged@10'] for k in q]):.2f} |")
finally:
    ctx.close(); emb.close()
```
