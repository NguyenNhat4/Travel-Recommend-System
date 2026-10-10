# Search bench: cổng APP theo model (e5-small), đo F1 lọc điểm đến / F2 câu không dấu / cutoff tạm trên pipeline thật

- Ngày: 2026-10-05
- Tác giả: tqanh123 (haisonqn2003) / Claude (agent)
- Nhánh: `fix/search`
- Trạng thái: hoàn thành
- Phạm vi: evaluation, docs

## Mục tiêu

Chạy e5-small qua **pipeline thật** (`SearchProducts` hybrid + normalize + F1/F2 của backend) thay vì chỉ qua arm E2 (cosine thuần), để
có số cho hai cờ mới (`history/2026-10-05-search-dest-filter-no-diacritics.md`) và cho đề xuất FR-SRC-02. Người dùng chốt 05/10: chuyển hẳn
sang e5-small, **không gọi Cohere nữa** → cổng APP phải tham số hoá theo model (trước đây hard-code `ProductBench` / Cohere v3 / 1024).
Phục vụ FR-SRC-01/03/04, AC-SRC-01; FR-SRC-02 (bằng chứng cho đề xuất chờ chốt).

## File thay đổi

- `src/evaluation/search_bench/app_adapter.py` — sửa: `AppModel` / `app_model(cfg, model)` (collection `ProductBench` cho cohere-v3,
  `ProductBench_<model>` cho model khác; `model_version = <hf_model>:catalog-text-v2`; số chiều từ `model_cfg`), `build_app_catalog` /
  `product_bench_status` / `load_product_bench` nhận `model_version` và kiểm `cache_model` + dimension; `load_collection` thêm
  `wait_bm25_stable` sau `wait_index_ready`; `APP_DEFAULTS` thêm `dest_filter`, `dest_filter_fallback`, `no_diacritics_mode`,
  `no_diacritics {…}` (`NO_DIACRITICS_KEYS`, `app_params` kiểm chặt); `AppSearch.search` ghi `derivedDestinations`, `destinationFilter`,
  `queryProfile`, `appliedFilters`, `cutoff` vào `extra`; `applied_filter_of(diag)` → `Retrieved.applied_filter`; `AppContext(model,
  dimension)`, `AppContext.open(cfg, dataset, model=…)`; `make_search` dựng `HybridConfig` thứ hai và truyền 5 tham số mới vào `SearchProducts`.
- `src/evaluation/search_bench/__main__.py` — sửa: `run` mở một `AppContext` cho mỗi model xuất hiện trong arm; `sanity` lấy collection qua
  `app_model`; `app-load --model`.
- `src/evaluation/search_bench/arms/APP.dense.yaml`, `APP.dense_nocut.yaml`, `APP.hybrid.yaml`, `APP.hybrid_nocut.yaml`,
  `APP.hybrid_norm.yaml`, `APP.hybrid_norm_nocut.yaml` — sửa: thêm khoá F1/F2 với giá trị production hôm nay (`no_diacritics_mode: "off"`
  phải **quote**: YAML 1.1 đọc `off` thành `false`).
- `src/evaluation/search_bench/arms/APP.e5s.dense_nocut.yaml`, `APP.e5s.hybrid_nocut.yaml`, `APP.e5s.hybrid_norm_nocut.yaml`,
  `APP.e5s.hybrid_norm_nocut_dest.yaml`, `APP.e5s.hybrid_norm_nocut_nodia.yaml`, `APP.e5s.hybrid_norm_nocut_dest_nodia.yaml` (cutoff −1),
  `APP.e5s.hybrid_norm.yaml`, `APP.e5s.hybrid_norm_dest.yaml`, `APP.e5s.hybrid_norm_nodia.yaml`, `APP.e5s.hybrid_norm_dest_nodia.yaml`
  (cutoff 0,84 tạm), `APP.e5s.hybrid_norm_nodia_nc80.yaml`, `APP.e5s.hybrid_norm_dest_nodia_nc80.yaml` (`no_diacritics.cutoff 0.80`) — thêm.
- `src/evaluation/search_bench/tests/test_app_adapter.py` — sửa: `E5_ARMS`; test F1/F2 bật đúng và hash khác nhau giữa mọi arm APP;
  `app_model` (collection, chiều, `model_version`); `applied_filter_of`; fake engine trả `extra` mới.
- `docs/spec/bench/arms.md` — sửa: 12 hàng `APP.e5s.*` và hàng knob `APP.e5s.*` trong bảng tham số cổng APP.
- `src/evaluation/reports/eval-2026-10-05-search-e5s-dest-nodia.md` — thêm: report kết quả chạy (commit, run id, gold sha, cấu hình arm,
  bảng nguyên văn, CI, cutoff, tái lập, caveat, lệnh tái sinh).
- `docs/plan/2026-09-28-lich-10-ngay-3-engine.md` — sửa: §8 log Day 6 (S). `docs/plan/2026-10-01-chia-task-day4-search-rec.md` — sửa: §5.4
  ba hàng S ngày 05/10, §5.5 điểm chờ chốt FR-SRC-02.

## Quyết định

- **Không dựng lại `ProductBench` (Cohere)**, không có arm Cohere trong run: người dùng chốt 05/10 không gọi Cohere nữa. Sáu arm `APP.*.yaml`
  Cohere giữ trong repo (vẫn load, vẫn test) nhưng không chạy ở máy này → report ghi rõ "chưa đo trên pipeline Cohere production".
- Mỗi model một collection (`ProductBench_e5_small`, 384 chiều), không trộn không gian vector; `load_product_bench` từ chối khi `cache_model`
  hoặc dimension lệch.
- Cutoff e5: arm `*_nocut` làm mốc vì 0,62 là ngưỡng của Cohere; 0,84 và 0,80 chọn từ phân bố cosine top-10 của `dense_nocut` trên toàn gold
  (**tạm, trong mẫu**, chờ `devtest.py`) chỉ để đọc zero-result và F2. Phát hiện: cutoff tuyệt đối không tách được câu ngoài catalog trên
  e5 (top-1 OOC 0,857–0,866 ≈ trung vị rel 0 0,861) → hướng S2 (ngưỡng theo margin), không chốt ở đây.
- Thêm hai arm `_nc80` ngoài plan ban đầu sau khi thấy cutoff 0,84 làm `no_diacritics` −14,5 điểm còn F2 với `no_diacritics.cutoff = null` chỉ
  bù +3,0: knob `no_diacritics.cutoff` có sẵn trong backend chính là để tách cutoff cho câu không dấu, cần số để biết knob đó có bù được không
  (bù được toàn bộ).
- **`wait_bm25_stable`**: ba arm hybrid chạy trong ~30 s đầu sau khi nạp collection cho kết quả sai (`hybrid_norm_nocut` nDCG 0,422, chỉ 3/131
  câu trùng với bản chạy lại; dense không bị). Chẩn đoán bằng run kiểm `2026-10-05-e5s-det` + chạy engine trực tiếp (xác định). Thêm bước dò
  BM25 tới khi kết quả đứng yên (3 câu, 2 s, timeout 120 s) rồi chạy lại ba arm `--force`; report dùng bản chạy lại. Các run APP cũ trên Cohere
  (30/09, 01/10) có thể chịu cùng lỗi ở arm hybrid đầu tiên — ghi ở report §9, chưa kiểm lại.
- Backend không đổi trong task này; F1/F2 đo qua đúng `SearchProducts` của `history/2026-10-05-search-dest-filter-no-diacritics.md`.

## Kiểm tra

- `PYTHONUTF8=1 .venv-sbench/Scripts/python -m pytest -q src/evaluation/search_bench/tests/test_app_adapter.py` → **8 passed, 1 skipped**
  (skip: test cần Weaviate thật). Toàn bộ `search_bench/tests` còn 41 fail có sẵn trước thay đổi này (fixture gold CRLF/sha, streamlit) —
  xác nhận bằng `git stash`; không thuộc phạm vi.
- `sb app-load --model e5-small` → `ProductBench_e5_small` 3.183 object; `sb sanity --arm APP.e5s.hybrid_norm_nocut` → **PASS 4/4**.
- `sb --run-id 2026-10-05-fix-search-e5s run …` 12 arm exit 0 (3 arm chạy lại `--force`); `sb --run-id 2026-10-05-e5s-det run` 2 arm exit 0;
  `dense_nocut` trùng 131/131 giữa hai run, `hybrid_norm_nocut` (bản chạy lại) trùng 131/131.
- `sb compare` 15 cặp full + condensed (report §8). Số chính: mốc `hybrid_norm_nocut` nDCG@10 0,677 full / 0,687 condensed, Judged 0,842;
  F1 trên mốc **WIN** Δrecall +2,34 [+1,03; +3,84], ΔnDCG +2,56 [+0,67; +4,63], slice thua nặng nhất −2,86; F2 không đổi top-10 khi không
  cutoff (131/131); cutoff 0,84 làm `no_diacritics` −14,47; `hybrid_norm + F1 + F2(no_diacritics.cutoff 0,80)` so mốc 0,84 **WIN** Δrecall
  +2,82 [+1,41; +4,34], ΔnDCG +3,54 [+1,48; +5,78] (condensed +3,90 [+1,85; +6,18]), nDCG@10 0,701 / 0,715.
- `sb latency embed --models e5-small` → p50 6,7 / p95 10,3 ms (131 câu, warmup 20, CPU laptop).
- Backend không đổi: 610 passed và `validate_contract.py` PASS ở entry F1/F2 vẫn đúng.

## Còn lại / rủi ro

- Không có số F1/F2 trên pipeline Cohere production; không có số HTTP (adapter e5 backend chờ chốt đề xuất FR-SRC-02).
- Mọi ngưỡng (0,84, 0,80, bộ F2) là trong mẫu; chốt trên dev/test khi S đẩy `devtest.py`. Cờ `SEARCH_DEST_FILTER` / `SEARCH_NO_DIACRITICS_MODE`
  vẫn mặc định tắt.
- `out_of_catalog` trên e5 không xử lý được bằng cutoff tuyệt đối → cần S2 (margin so với nền) hoặc tín hiệu BM25; `no_diacritics` Judged
  0,62–0,67 (`NEEDS_LABELS`) — bù nhãn khi gold mở lại.
- Kiểm lại arm hybrid đầu tiên của các run APP cũ (Cohere) xem có dính lỗi index chưa ổn định không.
- Phủ định, chiều bay chờ câu gold mới (người dùng làm ở máy khác).
