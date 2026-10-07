# Search bench: ống dẫn cho query plan Phase A — arm F3–F6, metric guard (Forbidden@10, direction, filter pass, parse), `gold-scan`, `topids-diff`

- Ngày: 2026-10-05
- Tác giả: tqanh123 (haisonqn2003) / Claude (agent; hai khối con do workflow agent triển khai, verifier độc lập, orchestrator sửa và chạy)
- Nhánh: `fix/search`
- Trạng thái: hoàn thành (Sprint 1 — số trong mẫu trên gold_v3; đo thật chờ gold v4)
- Phạm vi: evaluation, docs

## Mục tiêu

Đo bốn họ filter mới của backend (`history/2026-10-05-search-query-plan-f3-f6.md`) qua đúng `SearchProducts` trong bench mà **không
cần nhãn mới**: guard theo kiến trúc Phase A (Forbidden@10, direction accuracy, filter pass rate, parse accuracy) tính được từ định nghĩa
câu + cấu trúc catalog; kiểm "cờ tắt ≡ hôm nay" bằng so `top_ids`; chuẩn bị lớp đọc trường gold v4 với tên trường cấu hình được (người
dùng sẽ gửi bộ tên từ máy gán nhãn). Phục vụ FR-SRC-01/03/04; `docs/prd/test-plan.md` §2.4–2.5.

## File thay đổi

- `src/evaluation/search_bench/app_adapter.py` — sửa: `APP_DEFAULTS` thêm 4 khoá `negation_filter / taxonomy_filter / route_filter /
  numeric_filter` (bắt buộc ở mọi arm APP → `config_hash` của 24 arm APP đổi, chấp nhận); `make_search` truyền vào `SearchProducts`;
  `AppSearch.search` ghi `queryPlan` vào `extra`; `applied_filter_of` dựng AST từ mọi hard filter (`destination`, `taxonomy`, `origin_city`,
  `not contains_any features`, `not eq brand`, `gte/lte unit_price_min`).
- `src/evaluation/search_bench/arms/APP.*.yaml` (6 Cohere) và `APP.e5s.*.yaml` (12) — sửa: thêm 4 khoá (false). Thêm 6 arm:
  `APP.e5s.hybrid_norm_nocut_{neg,tax,route,num,qp}` (parent `hybrid_norm_nocut`, cutoff −1), `APP.e5s.hybrid_norm_dest_nodia_nc80_qp`
  (F1 + F2(0,80) + F3–F6, cutoff 0,84).
- `src/evaluation/search_bench/store/filters.py` — sửa: trường `origin_city`, `destination_city` (nullable), `brand` cho `not eq`; mảng
  chuỗi `features`; `not` bọc `and/or`; `to_weaviate` từ chối các dạng chỉ dành cho evaluator pandas (`FilterError`).
- `src/evaluation/search_bench/runner.py` — sửa: `attach_unit_columns` gắn cột **trong RAM** `origin_city`, `destination_city`, `features`
  (= `amenity_keys` của backend trên `amenities_raw` → cùng một từ vựng với backend; không đổi `ITEM_SCHEMA`/`items_sha256`);
  `score_arm`/`rescore_arm` truyền `extra` và **giữ `extra`** sau rescore.
- `src/evaluation/search_bench/metrics.py` — sửa: `GoldQuery` thêm `forbidden_filter`, `forbidden`, `origin`, `destination_city`,
  `expected_parse`, `family` đọc qua `MetricsConfig.gold_fields` (tên đổi được); `forbidden_hits`, `direction_ok`, `filter_pass`,
  `plan_fields`/`parse_ok`; `aggregate` thêm `forbidden_at_10`, `forbidden_query_rate`, `direction_accuracy`, `filter_pass_rate`,
  `parse_accuracy` (None-safe; metric cũ không đổi — kiểm bit-identical với results.json run 05/10).
- `src/evaluation/search_bench/config.py`, `config/sbench.yaml` — sửa: `Guards` thêm 4 khoá tuỳ chọn (None; giá trị đề xuất ghi comment
  "chờ chốt — Sprint 2"); `MetricsConfig.gold_fields`, `forbidden_overrides`.
- `src/evaluation/search_bench/config/forbidden_v3.yaml` — thêm: AST cấm cho 8 câu gold_v3 (5 phủ định theo `features`, c0373 chiều
  BMT→HN, c0070 đích Hà Nội, c0088 taxonomy attraction) — **chẩn đoán, không phải gold**; gold có trường thì gold thắng.
- `src/evaluation/search_bench/__main__.py` — sửa: `sb qu gold-scan` (parser trên 131 câu gold_v3, đối chiếu định nghĩa câu, không dùng
  judgments), `sb topids-diff` (so `top_ids` hai run/arm).
- `docs/spec/bench/arms.md` — sửa: 6 hàng arm mới, hàng knob `APP.e5s.*`.
- Test thêm: `src/evaluation/search_bench/tests/test_filters_phase_a.py`, `test_metrics_phase_a.py`, `test_cli_phase_a.py`; sửa
  `test_app_adapter.py`, `test_filters.py` (ca `not(eq brand)` đổi sang `province`: brand nay được phép phủ định).
- `src/evaluation/reports/eval-2026-10-05-search-query-plan-plumbing.md` — thêm: số chẩn đoán Sprint 1 (xem Kiểm tra).
- `docs/plan/2026-09-28-lich-10-ngay-3-engine.md` §8, `docs/plan/2026-10-01-chia-task-day4-search-rec.md` §5.4 — sửa: log.

## Quyết định

- Cột lọc mới nằm **trong RAM** lúc `load_env`, không đổi `items.parquet`: đổi `ITEM_SCHEMA` kéo `items_sha256` → collection e5 bị
  `check_ready` từ chối và phải dựng lại. `features` tính bằng đúng hàm `amenity_keys` của backend nên forbidden/filter_recall_loss không
  lệch từ vựng với mask backend (vocab `amenity_ids` của bench giữ nguyên, không dùng cho Phase A).
- Forbidden@10 là metric **độc lập nhãn** (như `constraint_precision`): Sprint 1 lấy AST từ `config/forbidden_v3.yaml`; gold v4 có
  trường thì gold thắng. Guard chỉ **khai**, chưa enforce (spec bench "không đặt ngưỡng mới"; chưa có `select()`).
- Tên trường gold v4 chưa chốt → `gold_fields` cấu hình được; không sửa `gold_schema.py` (chờ bộ tên người dùng gửi — Sprint 2 bước 0).
- `direction_ok` = None khi top-k không có tuyến bay (không tính vacuous 1). `rescore` giữ `extra` để parse accuracy sống sau rescore.
- Verifier bench chỉ ra và đã sửa: `applied_filter_of` bỏ sót `mustNotBrands` (nay `not eq brand`, `brand` vào `NOT_EQ_NULLABLE`);
  `direction_ok` không tính vacuous 1 khi top-k không có tuyến bay (→ None); `apply_forbidden_overrides` không ghi đè câu đã có `forbidden`
  ids; `expected_parse` có khoá lạ → `MetricsError` thay vì im lặng; hàng knob `arms.md` tách bảng vì một dòng trống.
- `gold-scan` dùng chính `_plan_gazetteers` của backend để gazetteer (brand guard, IATA, thành phố bay) khớp production.

## Kiểm tra

- `PYTHONUTF8=1 .venv-sbench/Scripts/python -m pytest -q src/evaluation/search_bench/tests` → 48 fail **có sẵn** (fixture `gold_small/*`
  CRLF, streamlit; số 05/10 ghi 41 là thiếu) không tăng; passed 302 → **361**.
- `sb qu gold-scan` (gold_v3, 131 câu, 19 thành phố bay, 19 IATA, mọi cờ bật): amenity_negation must_not 5/5 · cross_vertical taxonomy
  None 10/10 · dest_type ≤ 1 vertical 12/12 · multi_constraint destination 9/9, price_max 9/9, star_min 9/9 · route c0373 1/1.
- Identity cờ tắt trên bench thật: mốc `APP.e5s.hybrid_norm_nocut` chạy lại (config_hash mới) trùng **131/131** `top_ids` với run
  `2026-10-05-e5s-det`; mốc `hybrid_norm_dest_nodia_nc80` trùng **131/131** với run 05/10. Lần đầu 124/131 → tìm ra lỗi sắp xếp sao mềm khi
  cờ tắt (sửa ở backend, xem entry F3–F6).
- Run `2026-10-05-fix-search-qp` (8 arm, exit 0): F3 Forbidden@10 trên 5 câu phủ định 7/7/2/8/4 → **0/10 cả năm**, `amenity_negation` nDCG
  +8,95 full / +19,58 cond; F6 `multi_constraint` +11,04; F5 c0373 9/10 sai chiều → 0/1; F4 `abbrev_typo` −6,09, `filter_recall_loss` 148
  → **chưa bật được** với bảng cue hiện tại; `_qp` Forbidden@10 0/0 trên 8 câu, `revalidatedDrops` = 0, `emptyReason` không xuất hiện. Chi
  tiết + CI: `src/evaluation/reports/eval-2026-10-05-search-query-plan-plumbing.md`.

## Còn lại / rủi ro

- Mọi số là chẩn đoán trong mẫu (5 câu phủ định, 1–2 câu bay, 3 câu lẫn loại); kết luận bật cờ chờ gold v4 + dev/test split.
- `load_env` nay import backend (`amenity_keys`) và đọc lại catalog jsonl (~0,9 s) cho mọi lệnh dựng RunEnv — chấp nhận, ghi ở đây.
- `ROUTE_EXPECTED_V3` (c0373) hard-code trong `gold-scan` song song với `forbidden_v3.yaml`; thay bằng trường gold v4 khi có.
- `to_weaviate` từ chối `features`/`origin_city`/`not(and)`: các dạng này chỉ dùng trong `forbidden_filter`, không dùng cho `filter` truy xuất
  của arm không phải APP — ghi vào guide gold khi làm schema v4.
