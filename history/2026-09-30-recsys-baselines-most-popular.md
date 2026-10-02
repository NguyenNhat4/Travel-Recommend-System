# RecSys harness: merge nhánh, hai baseline most-popular, bảng 4 arm × 2 split trên seed 2026-09-21

- Ngày: 2026-09-30
- Tác giả: tqanh123 / Claude Code
- Nhánh: bench/embed-search (merge `origin/bench/recsys-harness` → `dc9a22c`)
- Trạng thái: hoàn thành
- Phạm vi: evaluation, docs

## Mục tiêu

Kế hoạch 3 ngày (`docs/plan/2026-09-30-bench-search-recsys-3-ngay.md`) mục P6 và yêu cầu của người dùng 30/09: tuần
này phải có bảng bench recsys. Harness Day 1 (nhánh `bench/recsys-harness`) mới có `random` + `engine`; handbook §12 bắt
buộc thêm most-popular và most-popular-in-destination — baseline quan trọng nhất. Phục vụ FR-REC-01..04, AC-REC-01/02,
test-plan §2.5; M5 của lịch 10 ngày.

## File thay đổi

- Merge `origin/bench/recsys-harness` vào `bench/embed-search` (người dùng chốt; merge sạch, không xung đột): thêm
  `src/evaluation/recsys_bench/*`, `all_events()` cho `CdpHistoryReader` / `PostgresCdpReader`, `docs/spec/bench/
  recsys-offline-eval.md`, `docs/plan/2026-09-28-lich-10-ngay-3-engine.md`, note mentor, các entry history 29–30/09 của
  nhánh đó.
- `src/evaluation/recsys_bench/arms.py` — sửa: `POPULARITY_WINDOW_DAYS = 90`, `trip_destination` (điểm đến của chuyến
  đang mở ≤ 60 ngày, không có thì chuyến gần nhất; trip = `eventGroupId` / `_solo_<pid>` như engine), `MostPopularArm`
  (điểm `Popularity.unit_scores` tại `as_of` qua `OfflineEngine.popularity_at`, chỉ unit recommendable + còn chỗ),
  `MostPopularInDestinationArm` (lọc theo điểm đến, thiếu thì bù toàn cục, meta `destination` / `nInDestination` /
  `strategy`).
- `src/evaluation/recsys_bench/__main__.py` — sửa: `run --arm most_popular | most_popular_in_destination`; `OfflineEngine`
  dựng một lần cho cả baseline lẫn engine (cùng nguồn popularity).
- `src/evaluation/recsys_bench/tests/test_arms_metrics.py` — thêm: test hai baseline (tất định, cùng tập ứng viên với
  engine, cửa sổ trước `as_of`, điểm đến của chuyến đang mở, fallback khi không có event).
- `docs/spec/bench/recsys-offline-eval.md` — sửa: §4.3 điền số so với mpd; §4.4 mới (bảng LLBO + temporal đủ 4 arm trên
  seed 09-21, đọc số, lệnh sinh lại); §7 cập nhật việc còn lại.
- `docs/plan/2026-09-28-lich-10-ngay-3-engine.md` — sửa: §8 Log Day 3.

## Quyết định

- **Baseline dùng đúng `Popularity` của production** (cửa sổ 90 ngày = mặc định `unit_scores` mà engine dùng cho thành
  phần pop), tính tại `as_of` của từng khách từ purchase trước đó (`OfflineEngine.popularity_at`) → không rò rỉ tương lai
  và so được với engine trên cùng nguồn. Không thêm tham số tune; hằng ghi trong docstring.
- **Điểm đến của mpd** lấy từ chuyến đang mở của khách (như `active_trip` của engine), thiếu thì chuyến gần nhất; không
  nhìn target (target là purchase bị giấu, đã cắt khỏi train).
- Chạy trên **seed 2026-09-21** đang có ở Postgres local (quyết định D5, không seed lại DB dùng chung với TRP-release);
  ghi rõ trong report rằng số không so trực tiếp với Day 1 (seed 09-23).
- `WEAVIATE_URL` / `EVAL_DATABASE_URL` truyền bằng biến môi trường (`.env` trỏ Cloud và `eval_cdp_url()` chỉ đọc
  `os.environ`) — không sửa `.env`.

## Kiểm tra

- `PYTHONUTF8=1 .venv/Scripts/python -m pytest -q src/evaluation/recsys_bench/tests`: **30 passed** (29 + 1).
- `python -m src.evaluation.recsys_bench doctor` (URL local ghi đè): catalog OK 2.897 unit / 2.118 recommendable; CDP OK
  7.131 event, as_of 2026-09-22; Weaviate OK.
- LLBO (`2026-09-30-llbo-v1`, 1.007 khách, 2 phút 51): random Recall@20 0,0083 ± 0,0026 ≪ most_popular 0,2929 <
  most_popular_in_destination 0,6346; engine Recall@5/10/20 0,572 / 0,591 / 0,591, NDCG@10 0,460 (mpd 0,389), coverage
  0,205, cross-category 0,943, p95 214 ms, trả TB 4,8 món.
- Temporal (`2026-09-30-temporal-v1`, 102 khách, 39 s): random 0,0065 ≪ mp 0,0588 < mpd 0,0980 < engine 0,1176 (Recall@20);
  NDCG@10 engine 0,113, mpd 0,031.
- Thứ tự sanity đúng ở cả hai split trước khi đọc số engine (handbook §6).

## Còn lại / rủi ro

- **Engine thua mpd ở Recall@20 trên LLBO** (0,591 vs 0,635) vì chỉ trả ≤ 9 món (I-5: cap 2 món / taxonomy + category
  exclusion); thắng NDCG@10 và Recall@5/10. Cần người chốt wrapper `mode="eval"` bỏ cap (kế hoạch Day 3 B) hoặc chấp
  nhận đọc NDCG@10 / Recall@10 là chính — đổi hành vi engine là việc của C, có thể cần đề xuất.
- `sanity.py` (phân bố seed) chưa làm; số 30/09 trên seed 09-21 khác Day 1 (09-23).
- Temporal: engine gần như không trúng ở `long_term` / `dormant` / `cross_vertical` (15 target bị exclusion) — đầu vào
  cho grid-search Day 5.
