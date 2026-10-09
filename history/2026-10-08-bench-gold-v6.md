# Benchmark 5 arms tren toan bo Gold Set v6 (175 cau active)

- Ngày: 2026-10-08
- Tác giả: người dùng / Antigravity
- Nhánh: fix/search-production
- Trạng thái: hoàn thành
- Phạm vi: evaluation

## Mục tiêu

Chạy đo lường chính thức 5 arms trên bộ dữ liệu vàng mở rộng `gold_v6` (175 câu active) với phân chia split mới `devtest@gold_v6.json` (88 Dev / 87 Test) theo yêu cầu của người dùng để đánh giá toàn diện cải thiện của các tính năng tìm kiếm mới (F7 thời lượng, POI gazetteer, Entity gate).

## File thay đổi

- `src/evaluation/reports/eval-2026-10-07-search-duration-entity-poi.md` — sửa: bổ sung mục 4.2 và chi tiết kết quả chạy run `2026-10-08-gold-v6`.

## Quyết định

- Chạy đầy đủ 5 arms: `APP.e5s.prod_f12356` (baseline), `_dur`, `_poi`, `_ent`, `_dur_poi_ent` trên Weaviate local với toàn bộ 175 câu của `gold_v6`.
- Đánh giá trên cả 3 góc nhìn:
  - Toàn bộ 175 câu: nDCG@10 tăng từ 0.764 lên 0.777 (+1.3%), recall@10 tăng từ 0.374 lên 0.382 (+0.8%), constraint precision tăng từ 0.775 lên 0.899 (+12.4%).
  - Theo khối Rubric: khối v3 (131 câu cũ) đạt zero-regression (Δ = 0.00%); khối v4 (44 câu mở rộng) nDCG@10 tăng +5.62% full và +5.94% condensed.
  - Trên tập Test độc lập (87 câu): slice `duration_false_positive` tăng +12.68% nDCG@10; slice `poi_resolution` tăng +13.52% nDCG@10.
  - Guards Phase A: 100% parse accuracy trên cả 7 trường mới; `forbidden_at_10` giảm từ 0.162 xuống 0.059.

## Kiểm tra

- `python -m evaluation.search_bench --run-id 2026-10-08-gold-v6 run --arm APP.e5s.prod_f12356 ...`: hoàn thành 5 arms.
- `python -m evaluation.search_bench --run-id 2026-10-08-gold-v6 compare APP.e5s.prod_f12356 APP.e5s.prod_f12356_dur_poi_ent --split all`: PASS, khối v4 +5.62% nDCG.
- `python -m evaluation.search_bench --run-id 2026-10-08-gold-v6 compare APP.e5s.prod_f12356 APP.e5s.prod_f12356_dur_poi_ent --split test`: PASS, test v4 +6.28% nDCG.
- `python -m evaluation.search_bench --run-id 2026-10-08-gold-v6 guards --arms APP.e5s.prod_f12356,APP.e5s.prod_f12356_dur_poi_ent`: PASS parse accuracy 1.000 trên cả 7 trường mới.

## Còn lại / rủi ro

- Bật các cờ tính năng (`SEARCH_DURATION_FILTER`, `SEARCH_POI_RESOLVE`, `SEARCH_ENTITY_FILTER`) khi triển khai staging/production.
