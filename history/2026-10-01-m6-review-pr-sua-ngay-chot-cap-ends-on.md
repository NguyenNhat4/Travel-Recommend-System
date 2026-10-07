# Review đối kháng PR M6 trước khi mở: sửa ngày chốt 02/10 → 01/10, tuổi / ends_on / món đã mua trước cap lặp, hôm nay theo giờ VN

- Ngày: 2026-10-01
- Tác giả: tqanh123 / Claude Code
- Nhánh: bench/m6-trip-ended (sau `c25f2ac`)
- Trạng thái: hoàn thành
- Phạm vi: PRD (ngày chốt), docs/prd/update-archive, spec search + spec bench, plan, backend (domain + application recommendation), evaluation (recsys_bench + report), history

## Mục tiêu

Người dùng yêu cầu "push lên và mở PR". `feat/recsys-trip-ended` (cherry-pick M6 lên release cũ) đã lệch 32 commit và xung đột với
`release-mvp-v2` sau PR #68, còn `bench/m6-trip-ended` merge sạch → PR mở từ nhánh bench. Trước khi mở, chạy review đối kháng
(workflow 3 lens: tuân thủ AGENTS.md, đúng đắn engine, chính xác mô tả PR; mỗi ghi nhận có agent bác bỏ): 12 ghi nhận → 9 còn lại,
đều minor. Entry này áp dụng 8 ghi nhận, ghi 1 (FR-REC-02, FR-REC-01; AGENTS.md §4, §5, §8).

## File thay đổi

- `docs/prd/requirements.md` — sửa: FR-REC-02 ghi chú chốt `2026-10-02` → `2026-10-01` (ngày chốt thật theo dấu thời gian commit
  `8842c3a` 01/10 10:29 và lịch sử hội thoại; 02/10 là ngày nhầm của phiên trước).
- `docs/prd/update-archive/2026-10-01-category-exclusion-theo-chuyen-dang-dien-ra.md` — sửa: "Chốt bởi / ngày" 2026-10-01 (ghi rõ bản
  đầu nhầm), dòng kết quả áp dụng.
- `docs/spec/hop-dong-tich-hop-search-recommendation.md` — sửa: §4.4 ghi chú luật 60 ngày chỉ tới 01/10; bổ sung đổi ngày 01/10;
  0,216 là số §4.14 v5 (grid §4.13 luật tuổi N = 14 đơn thuần: 0,225); `usingDate` là ngày bắt đầu sử dụng (kỳ nghỉ nhiều đêm coi là
  xong từ ngày sau check-in — giới hạn dữ liệu CDP, không phải lệch PRD); tuổi / ngày kết thúc / món đã mua xét trên mọi event; "hôm
  nay" theo giờ VN; §4.5 và tiêu chí 17 đổi ngày.
- `docs/spec/bench/recsys-offline-eval.md` — sửa: ngày cập nhật, §4.1 và §4.7 ghi chú luật trip mở đã đổi, §4.14 tiêu đề/ngày + một
  đoạn giải thích vì sao v5 (0,2157) thấp hơn điểm grid N = 14 đơn thuần (0,225) đúng 1 khách, §7 ngày.
- `docs/plan/2026-09-28-lich-10-ngay-3-engine.md` — sửa: dòng log "Day 5 (B — 02/10)" → "Day 4 (B, sáng — 01/10)" (thứ tự log đọc đúng
  thời gian).
- `src/evaluation/reports/eval-2026-10-02-recsys-bench-v5.md` — sửa: "Chạy lúc" 01/10 (tên file, run id, `ENGINE_RULES_VERSION` giữ
  nhãn 02/10 để khớp `bench_out/` và configHash), lệnh tái sinh v3 trỏ commit thay vì ngày.
- `src/backend/app/domain/recommendation/profile.py` — sửa: `build_profile` tính `age_days`, `ends_on`, `purchased_taxonomies`,
  `bought_units` trên **mọi** event của trip (cap `MAX_REPEAT_PER_TRIP` chỉ còn giới hạn trọng số vector, `events`, `n_events`,
  điểm đến); thêm `parse_using_date` (parser chung), `CATALOG_TZ` (UTC+7) + `local_today(now)`; sửa comment ngày và docstring
  `trip_is_open` (ngày sử dụng = ngày bắt đầu). `ENGINE_RULES_VERSION` giữ nguyên.
- `src/backend/app/application/recommendation/use_cases.py` — sửa: `_using_date` → `parse_using_date`; `today=local_today(now)`.
- `src/backend/tests/unit/domain/test_recommendation_trip_open.py` — thêm: test cap không rút ngắn trip / không sót purchase;
  test `local_today` (18:30Z = 01:30 VN hôm sau) và `parse_using_date`; sửa ngày trong docstring.
- `src/backend/tests/unit/application/test_recommendation_strategy_contract.py` — sửa: comment "> 60 ngày" → luật hiện tại.
- `src/evaluation/recsys_bench/events.py` — thêm: `trip_ends_on(events)` dùng `profile.parse_using_date` (thay `ceiling.ends_on`).
- `src/evaluation/recsys_bench/ceiling.py` — sửa: `engine_view` xét tuổi / `ends_on` / món đã mua trên mọi event, `local_today`;
  bỏ `ends_on` cục bộ; docstring luật trip mở.
- `src/evaluation/recsys_bench/splits.py` — sửa: `excluded_taxonomies` không cap (tuổi, ngày kết thúc, taxonomy đã mua trên mọi event),
  `local_today`, import ở đầu module; docstring.
- `src/evaluation/recsys_bench/arms.py` — sửa: `trip_destination` tuổi / ngày kết thúc trên mọi event (điểm đến vẫn sau cap như engine),
  `local_today`, import ở đầu module.
- `src/evaluation/recsys_bench/analysis.py` — sửa: docstring `target_trip_kind` (bỏ "60 ngày").
- `src/evaluation/recsys_bench/tests/test_ceiling.py` — thêm: test mirror cap + giờ VN trùng diagnostics engine (engine_view,
  `excluded_taxonomies`, `trip_destination`).
- `src/evaluation/recsys_bench/tests/test_splits.py` — sửa: test cap đổi kỳ vọng theo luật mới (lần xem thứ 4 bị cap vẫn tính tuổi
  trip → `_solo_A1` mở, không loại taxonomy; bỏ lần xem đó → `{hotel}`), engine trùng.
- `history/2026-10-01-m6-review-pr-sua-ngay-chot-cap-ends-on.md` — entry này.

## Quyết định

- Ngày chốt đề xuất M6 là **2026-10-01** (không phải 02/10): sửa ở PRD + đề xuất archive (hồ sơ con người review theo AGENTS.md
  §8 bước 3) và các spec/plan; **không** đổi tên `history/2026-10-02-recsys-fr-rec-02-trip-ended.md`, report `eval-2026-10-02-…`,
  run id `2026-10-02-*` và `ENGINE_RULES_VERSION = "2026-10-02-trip-ended"` (nhãn mờ; đổi `ENGINE_RULES_VERSION` sẽ đổi
  configHash của bảng v5; history/README.md không cho sửa entry cũ).
- Đính chính history M6: đề xuất bị `git mv` sang `update-archive/` trong `11b60e3` (không phải `b4d7968`), tức trước khi chốt — sai
  thứ tự AGENTS.md §8 bước 4; PR này hoàn tất bước 3–4 (trạng thái `đã áp dụng`, ngày chốt). Không sửa entry cũ.
- Cap lặp chỉ giới hạn trọng số vector: purchase thứ 4 cùng unit (chặng về) hay purchase sau 3 view cùng unit không được làm chuyến
  "kết thúc sớm" hay bị sót khỏi món đã mua. Đúng ý PRD FR-REC-02 ("ngày sử dụng của các sản phẩm trong chuyến chưa qua"), không
  lệch PRD. Kiểm trên seed (`bench_out/recsys/cache/events-a25cd720-all.jsonl`, 7.131 event, 5.816 trip): **không trip nào > 3
  event** (tối đa 2 event / sản phẩm / trip) → số bench v5 không đổi.
- "Hôm nay" theo giờ Việt Nam (`CATALOG_TZ` UTC+7, như `agents/steps/classification.py` và `domain/booking/cancellation.py`) vì
  `usingDate` là ngày địa phương; lấy ngày UTC làm chuyến hôm qua còn mở tới 06:59 VN. Kiểm trên hai split đóng băng: 0/1.109 as_of
  sau 17:00Z, 0 trip đổi trạng thái → số bench không đổi. `CATALOG_TZ` không vào configHash (`engine_config` chỉ chụp số/chuỗi).
- Ghi nhận không sửa: `Trip.ended` chưa có production dùng (dành cho `tripFactor` 0,2 spec §4.3, chưa hiện thực) — giữ.
- Giới hạn dữ liệu ghi vào spec, không đổi engine: CDP chỉ có ngày bắt đầu sử dụng; muốn giữ trip mở suốt kỳ nghỉ cần đề xuất PRD thêm
  số đêm / ngày kết thúc vào event.

## Kiểm tra

- Harness: `pytest src/evaluation/recsys_bench/tests` → **63 passed** (62 cũ + 1 mới; `test_splits` cap đổi kỳ vọng).
- Backend: `tests/unit/domain tests/unit/application tests/unit/api tests/architecture` → **349 passed** (347 trước + 2 test mới), 1 warning.
- Temporal đóng băng chạy lại (`run --arm engine --arm engine_prod --split temporal --vectors weaviate --split-file … --run-id
  2026-10-01-temporal-v5-recheck`): **trùng v5 từng số** — engine Recall@5/10/20 0,1863 / 0,2157 / 0,2157, NDCG@5/10 0,1452 / 0,1542,
  coverage 0,355; engine_prod 0,1275 / 0,1189; configHash **b0aee886 / 81d16abd** như v5 (`CATALOG_TZ` không vào hash); split sha
  a7735af1 khớp bản đóng băng; phân bố strategy giống hệt (long_term 57, dormant 19, cold_start_content 13, cross_vertical 10,
  recent_activity 3).
- Cây merge thử `bench/m6-trip-ended` → `release-mvp-v2 @ fe7e04d` trước khi sửa: 547 passed (backend unit/api/architecture), 62 passed
  harness; merge sạch.

## Còn lại / rủi ro

- `feat/recsys-trip-ended` trên remote đã bị thay thế bởi PR này — xoá khi người dùng đồng ý.
- Split "next trip" cho harness; `tripFactor` 0,2 (spec §4.3) chưa hiện thực; kỳ nghỉ nhiều đêm (cần ngày kết thúc trên event CDP).
