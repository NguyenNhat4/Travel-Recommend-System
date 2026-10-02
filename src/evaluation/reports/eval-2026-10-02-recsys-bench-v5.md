# RecSys bench — v3 → v4 → v5 trên split đóng băng (FR-REC-02: trip mở theo `usingDate`, N = 14)

- Commit engine/harness: nhánh `bench/m6-trip-ended` (sau `3c14a35`), áp dụng đề xuất `docs/prd/update-archive/2026-10-01-category-exclusion-theo-chuyen-dang-dien-ra.md`
- Chạy lúc: 2026-10-01 (tên file, run id và `ENGINE_RULES_VERSION` ghi 2026-10-02 do nhầm ngày; giữ nguyên để khớp `bench_out/` và configHash), máy dev (Postgres `localhost:5432/vota` seed 21/09 → as_of 2026-09-22; Weaviate `http://127.0.0.1:8080`, `vectorsMissing 0`)
- Split đóng băng: `src/evaluation/recsys_bench/frozen/split-llbo-asof20260922.json` (sha `29033b34…`, 1.007 khách) · `split-temporal-asof20260922.json` (sha `a7735af1…`, 102 khách, T = 2026-07-07T15:23Z)
- Arm: `random` (3 seed) · `most_popular` · `most_popular_in_destination` (mpd) · `engine` (mode eval, bỏ cap) · `engine_prod` (cap 2 món/taxonomy) · `engine_nommr` (pool 200 theo score, chẩn đoán); k = 20
- Phục vụ: FR-REC-01/02, test-plan §2.5; phân tích ở `docs/spec/bench/recsys-offline-eval.md` §4.6–4.14

## 1. Ba bước, cùng split, cùng model `embed-multilingual-v3.0:catalog-text-v2`

| Run | Luật engine | configHash eval / prod |
|---|---|---|
| `2026-10-01-{llbo,temporal}-v3` | trip mở = event gần nhất ≤ 60 ngày | `21577d17` / `a19bf1e1` |
| `2026-10-02-{llbo,temporal}-v4` | + trip có `usingDate` mở tới hết ngày sử dụng (`ENGINE_RULES_VERSION 2026-10-02-trip-ended`), N = 60 | `738cdf77` / `8aabd24c` |
| `2026-10-02-{llbo,temporal}-v5` | như v4, N = 14 cho trip không `usingDate` (hằng trong code) | `b0aee886` / `81d16abd` |

## 2. Temporal (102 khách) — nguyên văn `run`

v3:

| Arm | Khách | Recall@5 | NDCG@5 | Recall@10 | Recall@20 | NDCG@10 | Coverage | Trả về (TB) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| most_popular_in_destination | 102 | 0.0294 | 0.0149 | 0.0784 | 0.0980 | 0.0312 | 0.140 | 20.0 |
| engine | 102 | 0.1667 | 0.1348 | 0.1961 | 0.1961 | 0.1438 | 0.379 | 18.9 |
| engine_prod | 102 | 0.1176 | 0.1127 | 0.1176 | 0.1176 | 0.1127 | 0.091 | 6.1 |

v4:

| Arm | Khách | Recall@5 | NDCG@5 | Recall@10 | Recall@20 | NDCG@10 | Coverage | Trả về (TB) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| engine | 102 | 0.1667 | 0.1348 | 0.1961 | 0.1961 | 0.1438 | 0.378 | 19.6 |
| engine_prod | 102 | 0.1176 | 0.1127 | 0.1176 | 0.1176 | 0.1127 | 0.094 | 6.4 |
| engine_nommr | 102 | 0.1569 | 0.1325 | 0.1667 | 0.1961 | 0.1360 | 0.431 | 166.0 |

v5:

| Arm | Khách | Recall@5 | NDCG@5 | Recall@10 | Recall@20 | NDCG@10 | Coverage | Trả về (TB) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| most_popular_in_destination | 102 | 0.0294 | 0.0149 | 0.0784 | 0.0980 | 0.0312 | 0.140 | 20.0 |
| engine | 102 | 0.1863 | 0.1452 | 0.2157 | 0.2157 | 0.1542 | 0.355 | 19.6 |
| engine_prod | 102 | 0.1275 | 0.1189 | 0.1275 | 0.1275 | 0.1189 | 0.086 | 6.4 |
| engine_nommr | 102 | 0.1667 | 0.1363 | 0.1765 | 0.2157 | 0.1398 | 0.416 | 174.2 |

`analyze` (ceiling = target tới được mask ứng viên): v3 **0,784** (80/102) · v4 **0,794** (81/102) · v5 **0,892** (91/102; còn 6 `taxonomy_excluded`, 9 `destination_mismatch`, 1 `already_bought`). Engine trượt top-20 mà mpd trúng: v3 4/102 · v5 4/102.

## 3. LLBO (1.007 khách) — v5 (v3, v4 bằng đúng từng số)

| Arm | Khách | Recall@5 | NDCG@5 | Recall@10 | Recall@20 | NDCG@10 | Coverage | Trả về (TB) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| random (3 seed) | 1007 | 0.0023 ± 0.0005 | 0.0012 ± 0.0001 | 0.0040 ± 0.0008 | 0.0083 ± 0.0026 | 0.0017 ± 0.0003 | 0.999 ± 0.000 | 20.0 |
| most_popular | 1007 | 0.0993 | 0.0611 | 0.1867 | 0.2929 | 0.0891 | 0.068 | 20.0 |
| most_popular_in_destination | 1007 | 0.4965 | 0.3624 | 0.5780 | 0.6346 | 0.3890 | 0.416 | 20.0 |
| engine | 1007 | 0.6693 | 0.4973 | 0.7527 | 0.8510 | 0.5244 | 0.583 | 15.2 |
| engine_prod | 1007 | 0.5720 | 0.4536 | 0.5909 | 0.5909 | 0.4602 | 0.205 | 4.8 |
| engine_nommr | 1007 | 0.6912 | 0.5173 | 0.7855 | 0.8630 | 0.5481 | 0.582 | 46.3 |

Ceiling LLBO 0,990 (997/1.007, 10 `already_bought`) ở cả ba bước; 21/1.007 ca engine trượt-mpd trúng (`filtered` 9, `mmr_demoted` 6, `ranked_low` 6).

## 4. Caveat khi trích dẫn

- Temporal 102 khách: chênh 0,02 Recall@20 = 2 khách; đọc như hướng, không như kết luận thống kê.
- 10/21 target temporal bị chặn ở v3 là chuyến chưa đi tại T (`usingDate` ≥ T): split temporal (as_of = T) hỏi "mua gì sau T", không phải "gợi gì ngay trước lúc mua chuyến kế" — cần split "next trip" (chưa làm).
- `activeTripIsSolo` (view lẻ ngay trước purchase) chiếm phần lớn hit của LLBO `recent_activity` — hành vi seed tạo ra.
- p95/p99 ms là thời gian xếp hạng offline trên máy dev đang chạy song song, không phải latency HTTP.
- Số LLBO không đổi qua ba bước vì 911 khách `cross_vertical` đều có trip có `usingDate` còn mở tại as_of.

## 5. Lệnh tái sinh

```bash
export WEAVIATE_URL=http://127.0.0.1:8080 WEAVIATE_API_KEY= EVAL_DATABASE_URL=<dsn cdp_eval_login>
python -m src.evaluation.recsys_bench run --arm random --arm most_popular --arm most_popular_in_destination --arm engine --arm engine_prod --arm engine_nommr \
    --split temporal --vectors weaviate --split-file src/evaluation/recsys_bench/frozen/split-temporal-asof20260922.json --run-id 2026-10-02-temporal-v5
python -m src.evaluation.recsys_bench run ... --split llbo --split-file src/evaluation/recsys_bench/frozen/split-llbo-asof20260922.json --run-id 2026-10-02-llbo-v5
python -m src.evaluation.recsys_bench analyze --run-id 2026-10-02-temporal-v5   # ceiling.md, segments.md, strict.md, cases.md
# v3 / v4 tái tạo bằng --override ACTIVE_TRIP_MAX_AGE_DAYS=60 (v4) trên code hiện tại; v3 cần checkout commit trước 8842c3a
```
