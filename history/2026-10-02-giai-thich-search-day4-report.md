# Giải thích report Search Day 4 và xếp hạng model local trên gold_v3

- Ngày: 2026-10-02
- Tác giả: người dùng / Codex
- Nhánh: `bench_search_recomSys`
- Trạng thái: hoàn thành
- Phạm vi: evaluation, report
- Phục vụ: FR-SRC-01..04, AC-SRC-01, NFR-PERF-01

## Mục tiêu

Viết lại report Day 4 để giải thích metric, cách đo, PASS/FAIL và quy mô vector; đo thêm `multilingual-e5-large-instruct`; chạy lại e5-base; rồi xếp hạng năm model local miễn phí trên cùng `gold_v3` và cùng điều kiện retrieval.

## File thay đổi

- `src/evaluation/reports/eval-2026-10-01-search-day4-local.md` — bổ sung giải thích metric/gate/latency; số đo e5-base và e5-large-instruct; điều kiện so sánh khóa trên gold_v3; bảng xếp hạng local-only và lệnh tái sinh.
- `src/evaluation/search_bench/config/sbench.yaml` — khai báo `intfloat/multilingual-e5-large-instruct`, 1024 chiều, batch CPU 4 và query instruction chính thức.
- `src/evaluation/search_bench/arms/E2.e5L.yaml` — thêm arm dense T3+R/top-10 cho e5-large-instruct.
- `src/evaluation/search_bench/tests/test_store_arms.py` — kiểm dimension, collection riêng và query/document prefix của arm mới.
- `history/2026-10-02-giai-thich-search-day4-report.md` — entry này.

## Quyết định

- So sánh local-only gồm e5-base, e5-small, BGE-M3, GTE multilingual-base và e5-large-instruct. Cohere chỉ còn là dữ liệu lịch sử Day 4, không tham gia xếp hạng và không được gọi trong run xếp hạng.
- Khóa cùng `gold_v3` SHA-256 `4d2ac02fa960ceaf2c9286bf546da1b77023435a9337ecadee22dd7cc62f5784`, 131 query, catalog 3.183 search unit, text T3+R, dense cosine top-10, Weaviate flat, không filter/cutoff/normalize.
- Prefix/instruction được dùng đúng theo từng model. E5-large-instruct dùng `Instruct: ...\nQuery:` cho query và document không có instruction, theo model card; đây là phần cấu hình model, không phải thay đổi dataset.
- Run `20261002-day5-local-ranking` chứa cả năm arm. Mỗi arm có query cache hit 131/131 và `gold_version=gold_v3`, nên paired bootstrap đọc trực tiếp cùng một run.
- Xếp hạng khuyến nghị: (1) e5-base, (2) e5-small, (3) BGE-M3, (4) GTE, (5) e5-large-instruct. E5-base đứng đầu chất lượng và coverage; e5-small đứng trên BGE vì hai model TIE về chất lượng nhưng e5-small nhẹ/nhanh hơn nhiều.
- Đây là benchmark Tier 2 đã có trong plan, không thay đổi model production. PRD vẫn quy định Cohere v3/1024; nếu muốn đổi sang e5-base phải qua đề xuất PRD được người dùng chốt.

## Kết quả đo

- E5-base: Recall@10 0,347525; nDCG@10 0,696969; MRR@10 0,756830; Judged@10 1,000; query embed p95 64,990 ms; re-index 3.183 document 11m57s.
- E5-large-instruct: Recall@10 0,304645; nDCG@10 0,610243; MRR@10 0,695799; Judged@10 0,793; query embed p95 284,236 ms; re-index 34m33s; peak RSS khoảng 4,16 GB.
- E5-large-instruct `NEEDS_LABELS`: overall 0,793 < 0,80 và `no_diacritics` 0,417 < 0,70. Cần thêm tối thiểu 34 nhãn trong slice này để đạt gate slice; điều đó không giải quyết latency.
- Paired bootstrap full trên cùng run: e5-small, BGE, GTE và e5-large lần lượt thấp hơn e5-base 6,24; 6,09; 11,42; 8,67 điểm nDCG, với CI95 hoàn toàn dưới 0. E5-small so với BGE là TIE, ΔnDCG +0,15 điểm, CI95 [−2,56; +3,10].

## Kiểm tra đã chạy

- Token gate e5-base và e5-large-instruct: PASS; p99 lần lượt 236 và 234, dưới hard max 512.
- Sanity e5-base: 4/4 PASS. Sanity e5-large-instruct: 4/4 PASS.
- `python -m evaluation.search_bench --dataset jsonl --run-id 20261002-day5-local-ranking run --arm E2.e5 --arm E2.e5s --arm E2.bge --arm E2.gte --arm E2.e5L`: PASS, năm arm trên gold_v3, 0 lỗi retrieval.
- Năm lệnh `compare` ở report §10: PASS; số CI/verdict được chép từ output CLI.
- `/home/dangkhoi/miniconda3/envs/vsf2/bin/python -m pytest evaluation/search_bench/tests/test_store_arms.py evaluation/search_bench/tests/test_local_hf.py -q`: **15 passed**.
- `git diff --check`: PASS.

## Còn lại / rủi ro

- Chưa có HTTP end-to-end/load test, concurrency, cache hit/miss, RAM phục vụ hay HNSW trên máy gần production. Bench flat 3.183 vector không chứng nhận NFR production.
- Coverage của các hạng 2–5 chưa đồng đều; xếp hạng phụ là tạm thời. E5-base có coverage 1,000 và là ứng viên tiếp theo, chưa phải model production đã chốt.
- Artifact trong `bench_out/` là local/ignored; clone sạch phải tái chạy các lệnh ở report §10.
