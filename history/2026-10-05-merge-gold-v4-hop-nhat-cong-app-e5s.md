# Merge `bench_search_recomSys` (gold_v4, PR #107) vào `fix/search` — hợp nhất hai bản cổng APP e5-small, đổi tên họ arm cutoff 0,84 → `*_c84`

- Ngày: 2026-10-05
- Tác giả: tqanh123 (haisonqn2003) / Claude (agent)
- Nhánh: `fix/search`
- Trạng thái: hoàn thành (merge); đo trên gold_v4 là việc tiếp theo
- Phạm vi: evaluation, docs

## Mục tiêu

Người dùng báo gold_v4 đã PR vào `bench_search_recomSys` → commit việc Phase A trên `fix/search` (`8bb06f3`) rồi merge nhánh đó về. Hai máy
cùng ngày đã làm trùng "cổng APP theo model e5-small" với API khác nhau nên phải hợp nhất tay 7 file xung đột.

## File thay đổi (ngoài phần git tự merge)

- `src/evaluation/search_bench/app_adapter.py` — hợp nhất: **lấy lớp model của nhánh bench** (`PRODUCTION_MODEL`, `app_collection` →
  `ProductBench__<model>`, `model_vectors` đọc `modelVersion`/số chiều từ meta vector, `AppContext.cache_model`, guard `wait_bm25_settled` +
  `bm25_snapshot` có test); **bỏ** `AppModel`/`app_model`/`DEFAULT_APP_MODEL` và `wait_bm25_stable` của `fix/search` (cùng mục đích, không
  test); **giữ** của `fix/search`: `attrs` cho `UnitIndex`, khoá F1/F2/QP trong `APP_DEFAULTS`/`app_params`, `make_search` truyền cờ,
  `AppSearch.extra` có `queryPlan`, `applied_filter_of`.
- `src/evaluation/search_bench/__main__.py` — hợp nhất: `run`/`app-load`/`sanity` theo lớp model của nhánh bench (`app_collection`,
  `AppContext.cache_model`); giữ `topids-diff`, `qu gold-scan` của `fix/search` và `gold devtest`, `regress baseline|check` của nhánh bench.
- `src/evaluation/search_bench/tests/test_app_adapter.py` — bỏ test `app_model`; danh sách arm thêm 3 arm base của nhánh bench + họ `_c84`.
- `src/evaluation/search_bench/arms/APP.e5s.{dense,dense_nocut,hybrid,hybrid_nocut,hybrid_norm,hybrid_norm_nocut}.yaml` — bản của nhánh bench
  (parent/description/cutoff 0,62 ở `dense`/`hybrid`/`hybrid_norm`) + khoá F1/F2/QP bắt buộc của `app_params`.
- Đổi tên 7 arm của `fix/search` có cutoff **0,84**: `APP.e5s.hybrid_norm` → `APP.e5s.hybrid_norm_c84`; `_dest`, `_nodia`, `_dest_nodia`,
  `_nodia_nc80`, `_dest_nodia_nc80`, `_dest_nodia_nc80_qp` → `hybrid_norm_c84_*` (parent đổi theo). Comment "ProductBench_e5_small" → `ProductBench__e5_small`.
- `docs/spec/bench/arms.md` — hợp nhất bảng: 6 hàng base của nhánh bench + 15 hàng F1/F2/QP của `fix/search` (đã đổi tên `_c84`).
- `src/evaluation/reports/eval-2026-10-05-search-e5s-dest-nodia.md`, `eval-2026-10-05-search-query-plan-plumbing.md` — thêm ghi chú đầu file:
  tên arm cũ ↔ mới, collection cũ ↔ mới; **số và run id không đổi**.

## Quyết định

- `APP.e5s.hybrid_norm` giữ nghĩa **cutoff 0,62** của nhánh bench vì `regression/baseline_v1.json` và report `eval-2026-10-05-search-day5-e5s-app.md`
  đã trỏ vào nó; họ 0,84 của `fix/search` là thí nghiệm "tạm" → nhận hậu tố `_c84`.
- Collection e5 theo nhánh bench `ProductBench__e5_small` (hai gạch). Máy này hiện có `ProductBench_e5_small` (một gạch, cùng vector) → lần
  `sb run` tới sẽ dựng collection mới (~1–2 phút, 0 API); run cũ `2026-10-05-fix-search-e5s` / `-qp` giữ nguyên trong `bench_out/`.
- `config_hash` của mọi arm APP đã đổi (khoá F1/F2/QP bắt buộc) → `sb regress check` so với `baseline_v1` sẽ cảnh báo hash khác; **không tự đặt
  lại baseline** — việc đó là quyết định của người dùng sau khi đo trên gold_v4.
- Gold_v4 (155 câu; slice mới `taxonomy_collision` 5, `flight_direction` 6; `amenity_negation` 13; không có trường `forbidden`/`expected_parse`)
  **chưa có tag `gold_v4`** trên remote → `sb run` cần `--allow-untagged` hoặc người dùng tạo tag. `MetricsConfig.gold_fields` của `fix/search`
  giữ nguyên (không có trường mới để nối).

## Kiểm tra

- `git diff --diff-filter=U` rỗng; không còn marker; 27 arm APP load được, `app_params` qua hết, `config_hash` phân biệt.
- Bench `pytest src/evaluation/search_bench/tests` → 54 failed / 391 passed / 11 skipped: toàn bộ 54 nằm trong 6 file fail có sẵn
  (fixture `gold_small/*` CRLF, streamlit; `test_gold_cli` 18 → 24 vì nhánh bench thêm 6 test `import --append` cùng phụ thuộc fixture) —
  không có fail mới. Backend: `test_unit_index_mask`, `test_query_plan_filters`, `test_dest_filter`,
  `test_search_prewarm` (nhánh bench đổi prewarm list), `architecture` → 43 passed.

## Còn lại / rủi ro

- Chạy mốc + arm F3–F6 trên gold_v4 (chờ tag hoặc `--allow-untagged`), mở rộng `config/forbidden_v3.yaml` cho 8 câu phủ định mới + 6 câu chiều
  bay + 5 câu lẫn loại (hoặc nối trường gold khi máy gán nhãn bổ sung), đọc `direction_accuracy` thật.
- `baseline_v1` cần đặt lại sau khi người dùng chốt arm/cutoff; `sb regress check` tạm cảnh báo hash.
