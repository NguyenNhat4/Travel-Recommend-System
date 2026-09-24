# sbench — `metrics.py`, paired bootstrap và unit test trên fixture tay (ngày 2, việc 1–3 của Người A)

- Ngày: 2026-09-24
- Tác giả: tqanh123 / Claude Code
- Nhánh: bench/embed-search
- Trạng thái: hoàn thành
- Phạm vi: evaluation, docs

## Mục tiêu

Người dùng giao việc 1–3 của Người A ngày 2 trong `docs/spec/bench/search-eval-checklist.md`:
- `metrics.py`;
- paired bootstrap 1.000 lần;
- unit test trên fixture `tests/fixtures/gold_small.jsonl`.

Việc 3 làm từng bước, có người dùng duyệt ở mỗi bước:
1. Đưa đề xuất.
2. Người dùng yêu cầu làm ý 1–2 (định dạng file, nguồn product_id), còn ý 3 (bộ 10 query) thì tạo ra để review.
3. Người dùng **đồng ý bộ query** (24/09).
4. Làm tiếp fixture kết quả của hai arm và các test.

Phục vụ `docs/prd/test-plan.md` §2.5: NDCG@10, Recall@K với K = 5, 10.

## File thay đổi

- `src/evaluation/search_bench/metrics.py` — thêm:
  - `load_gold` (bỏ query retired);
  - metric theo query: `recall_at_k`, `ndcg_at_k`, `mrr_at_k`, `judged_at_k`, `ranks_of_relevant`, `dup_parent_count`, `constraint_hits`, `filter_recall_loss`, `hub_scores`;
  - `evaluate_query` → một dòng per_query;
  - `aggregate` → overall / by_slice / n_defined;
  - `paired_bootstrap`, `slice_deltas`, `win_verdict`, `compare_rows`.
- `src/evaluation/search_bench/config.py` — sửa: mục `metrics` thành model chặt (`MetricsConfig`, `WinRule`, `Guards`) thay cho model mở.
- `src/evaluation/search_bench/config/sbench.yaml`, `docs/spec/bench/search-eval-local-spec.md` §1.2 — sửa: thêm `metrics.extra_recall_k: [5]` (đề xuất).
- `src/evaluation/search_bench/tests/test_config.py` — sửa: đọc `guards` theo thuộc tính.
- `src/evaluation/search_bench/tests/fixtures/gold_small.jsonl` — thêm: 10 query nhãn giả (đã được người dùng duyệt).
  - Đúng định dạng `gold.jsonl` (spec Part 5).
  - product_id lấy từ 26 search unit của `products-sample.jsonl`.
  - Filter ghi bằng khoá amenity.
  - Mỗi query kiểm một nhánh metric.
- `src/evaluation/search_bench/tests/fixtures/run_small.json` — thêm: top_ids giả của arm A và arm B, kèm filter cứng mà B áp ở q007. B giống A trừ q001, q007, q010.
- `src/evaluation/search_bench/tests/test_metrics.py` — thêm: 13 test.
  - 3 query tính tay: q001, q004, q007.
  - Các nhánh còn lại.
  - Gộp overall / by_slice của arm A.
  - Bỏ query retired.
  - So A với chính nó: Δ 0, p 0,5.
  - A vs B: Δ tính tay, kết quả LOSE theo win_rule.
  - Bootstrap với mức cải thiện rõ; 3 nhánh win_rule.
  - hub_score, dup parent.
- `docs/spec/bench/search-eval-checklist.md` — sửa: tick 3 việc ngày 2 của Người A.
- `history/2026-09-24-search-bench-metrics-bootstrap.md` — thêm: entry này.

## Quyết định

- **(a) Metric không xác định thì loại, không tính 0.** Query bị loại khỏi trung bình của metric đó và được đếm vào `n_defined` (spec Part 8; Phụ lục B với bootstrap).
  - recall / nDCG: không có sản phẩm rel ≥ 1;
  - MRR: không có nhãn 2 nào;
  - judged: 0 kết quả.
- **(b) p một phía theo mid-p**: P(Δ* < 0) + ½·P(Δ* = 0).
  - Cách này cho arm so với chính nó p = 0,5, đúng tiêu chí "Done khi" của spec.
  - Công thức chữ P(Δ ≤ 0) sẽ cho 1,0.
  - Δ tính theo điểm phần trăm (×100), như ví dụ trong `results.json`.
- **(c) constraint_precision gộp theo kết quả (micro)**: tổng kết quả thoả / tổng kết quả của các query có filter. Filter trong gold ghi khoá amenity, được resolve bằng `amenity_vocab.json`; evaluator là `store/filters.mask`.
- **(d) win_rule theo đúng thứ tự spec**: WIN → TIE → LOSE.
  - "Slice thua > 3" đo bằng Δ nDCG@10 theo slice, cùng thước đo với `select()` / Bảng 2.
  - Kết luận chỉ để đọc report.
- **Recall@5**: thêm vì `docs/prd/test-plan.md` §2.5 yêu cầu; khoá config `extra_recall_k` (đề xuất).
- **Zero-result**:
  - `out_of_catalog` = tỷ lệ query `expected_no_result` trả 0 kết quả (runner đã áp cutoff);
  - `in_catalog` = tỷ lệ các query còn lại trả 0 kết quả.
- **Số kỳ vọng trong test ghi cứng**, tính bằng phép tính độc lập (không gọi `metrics.py`), phép tính ghi ở comment. Mục đích là tránh test tự so với chính nó.
- **Test bắt được lỗi thật.** Cột `parent_product_id` đọc từ parquet cho `NaN`, và `NaN` bị coi là "có cha", nên parent_dup_rate ra 5,1 thay vì 0. Đã sửa `dup_parent_count` chỉ tính cha là chuỗi khác rỗng, và thêm test hồi quy.

## Kiểm tra

- Chạy tay trước khi viết test: các số khớp tính tay (recall 2/3, nDCG 0,4308, MRR 1/2, judged 3/5…).
- `pytest evaluation/search_bench/tests/test_metrics.py`: **13 passed**.
- Cả bộ `pytest evaluation/search_bench/tests`: **138 passed, 9 skipped** (integration).
- `pyflakes`: sạch.
- Arm A trên fixture:

  | metric | giá trị |
  |---|---|
  | recall@10 | 0,7130 |
  | recall@5 | 0,6481 |
  | nDCG@10 | 0,5551 |
  | MRR@10 | 0,4444 |
  | judged@10 | 0,425 |
  | constraint_precision | 5/11 |
  | zero_result in / out | 1/9 / 1,0 |

  `n_defined`: judged = 8, các metric còn lại = 9.
- A vs B: Δrecall −2,78 điểm, Δndcg +5,03 điểm → LOSE, đúng theo chữ của win_rule.

## Còn lại / rủi ro

- `gold check` (Part 5, ngày 4) trên `gold_small.jsonl` sẽ trượt điều kiện `min_per_slice: 10` (10 query cho 9 slice), trong khi spec Part 5 ghi check phải xanh trên fixture này. Đề xuất: test của `check` dùng config thu nhỏ riêng (ví dụ `min_per_slice: 1`), không đổi config thật.
- Việc 4 ngày 2 của A (`docs/spec/bench/gold-guide.md`) chưa làm.
- Quyết định (a)–(d) đã được mã hoá trong test. Người dùng đã duyệt bộ query nhưng chưa phản hồi riêng từng quyết định; nếu đổi thì sửa test tương ứng.
- Chưa cài:
  - runner Part 8 (sinh per_query từ arm);
  - `sb compare`;
  - `select()` của Part 10;
  - nguồn 500 query ngẫu nhiên cho hub_score.
