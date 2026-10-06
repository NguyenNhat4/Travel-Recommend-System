# Hoàn thành Search Day 4: local benchmark, gold D4b/D5a và condensed evaluation

- Ngày: 2026-10-01
- Tác giả: người dùng / Codex
- Nhánh: `bench_search_recomSys`
- Trạng thái: hoàn thành kỹ thuật, chờ người dùng review và commit
- Phạm vi: evaluation, docs
- Phục vụ: FR-SRC-01..04, AC-SRC-01, NFR-PERF-01

## Mục tiêu

Hoàn thành S1–S7 và phần condensed của S8 trong kế hoạch Search Day 4. Chỉ làm Search, không làm Recommendation. So sánh các arm trên cùng catalog/gold, bổ sung nhãn theo cap 700, giữ full metrics cạnh condensed metrics, cập nhật report và file bàn giao.

## File thay đổi

- `docs/plan/2026-10-01-chia-task-day4-search-rec.md` — cập nhật checklist, trạng thái S1–S8 và bảng bàn giao Search.
- `docs/spec/bench/arms.md` — mô tả 7 arm E mới và ranh giới benchmark.
- `docs/spec/bench/search-eval-local-spec.md` — bổ sung compare theo gold version, latency embed và condensed/coverage.
- `docs/spec/bench/search-gold-summary.md` — hồ sơ gold đến D5a/gold_v3, 5.021 nhãn.
- `src/evaluation/reports/eval-2026-10-01-search-day4-local.md` — report cuối 7 arm, full/condensed, vector và latency.
- `src/evaluation/reports/eval-2026-10-01-search-v1-3arm.md` — report cuối dense/hybrid/hybrid+normalize.
- `src/evaluation/search_bench/__main__.py` — compare đọc rescore theo version, `--condensed`, latency embed và CLI liên quan.
- `src/evaluation/search_bench/metrics.py` — metric/query view/aggregate condensed và coverage.
- `src/evaluation/search_bench/runner.py` — ghi condensed vào run/rescore, đọc list Parquet, compare condensed; tolerance gate tại đúng ngưỡng.
- `src/evaluation/search_bench/config.py`, `config/sbench.yaml` — model/input type cho e5-small, GTE, BGE-M3, Cohere v4 nhiều chiều.
- `src/evaluation/search_bench/embed/local_hf.py` — tải safetensors cho model local.
- `src/evaluation/search_bench/gold.py`, `sanity.py`, `holes.py`, `latency.py` — sanity gold, symmetric model, cap pool cân bằng, latency cache-off.
- `src/evaluation/search_bench/arms/E2.bge.yaml`, `E2.e5s.yaml`, `E2.gte.yaml`, `E2.v4-1536.yaml`, `E2.v4-1024.yaml`, `E2.v4-512.yaml`, `E2.v4-256.yaml` — 7 arm dense.
- `src/evaluation/search_bench/gold/gold.jsonl`, `gold/changelog.yaml` — append-only D4b + D5a, version gold_v3.
- `src/evaluation/search_bench/gold/holes/gold_v2__D4b/*` — pool/meta/auto/holes và nhãn 278/278.
- `src/evaluation/search_bench/gold/holes/gold_v3__D5a/*` — pool/meta/auto/holes và nhãn 700/700.
- `src/evaluation/search_bench/tests/test_gold_cli.py`, `test_holes_import_rescore.py`, `test_latency_parity.py`, `test_metrics.py`, `test_runner.py`, `test_sanity.py`, `test_store_arms.py` — test các hành vi trên.
- `history/2026-10-01-search-day4-local.md` — entry này.

## Dữ liệu và quyết định

- Gold cuối: 131 active / 13 slice / 4.991 nhãn active; 1 retired / 30 nhãn; tổng 5.021. SHA-256 `4d2ac02fa960ceaf2c9286bf546da1b77023435a9337ecadee22dd7cc62f5784`.
- D4b: 278/278 nhãn người. D5a: 700/700 nhãn người (190/170/340 cho nhãn 0/1/2) + 72 auto-OOC.
- D5a pool hợp 7 arm có 2.024 human hole trước cap. Sau cap vẫn còn hole nên dùng condensed theo plan, luôn báo cạnh full/coverage.
- Tạo 8 bộ vector document × 3.183 = 25.464 vector. Cohere chỉ dùng khi người dùng cho phép; khóa chỉ ở môi trường, không ghi repo.
- E2.v4-512 và E2.v4-1024 đạt cổng judged sau khi gate dùng tolerance 1e-12 cho giá trị đúng ngưỡng 0,700. So condensed 512 với 1024/1536 đều TIE; shortlist giữ 512 (mặc định hiệu quả) và 1024 (quality-first). Không đổi model production Cohere v3/1024.
- APP hybrid+normalize tăng Recall so với dense nhưng vi phạm guard slice; dense giữ làm mốc APP.
- V4 API latency gặp 429 nên loại lượt đo; không trộn retry vào percentile. Local CPU, Cohere API và Weaviate local được ghi thành điều kiện riêng.
- Report có bảng so sánh production toàn diện cho 8 phương án: chất lượng, gate, latency, footprint ở 1 triệu sản phẩm, chi phí ở 100 triệu query/tháng, API/storage/CPU, ưu nhược điểm, rủi ro vận hành và vai trò đề xuất. Tiền trial thực trả (0 USD) được tách khỏi working estimate production; working estimate không được coi là báo giá chính thức.
- Không sửa PRD, contract, DDL hay Recommendation.

## Kiểm tra

- `python -m evaluation.search_bench gold check`: PASS, 131 active / 13 slice.
- `python -m evaluation.search_bench gold verify-append gold_v2`: PASS, +0 query / +1.050 label / +0 retired.
- Focused condensed/rescore: 20 passed.
- Full Search suite sau condensed và tolerance gate: 346 passed, 11 skipped, 1 deselected trong 20,73 giây. Test deselect ghi launcher ngoài workspace và bị PermissionError trong sandbox.
- Cả 8 collection có 3.183 object; sanity 4/4 PASS từng model/arm.
- `git diff --check` và secret scan chạy trước commit.

## Kết quả và việc chuyển Day 5

Search Day 4 hoàn thành. Không cần thêm label để chốt Day 4. Các mục S8 còn lại — stages/regression và dev/test split — chuyển Day 5; 131 câu không đủ split 100/100 nên cần chốt kích thước hợp lệ. Latency end-to-end `/search` và lỗi cloud 500 cũng thuộc Day 5.
