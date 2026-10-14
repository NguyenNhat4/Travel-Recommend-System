# Bench search 1.28.0 trên gold_v7: cổng bằng chứng, câu không giải thích được, thời lượng, phục hồi dấu

- Phục vụ: FR-SRC-01, FR-SRC-03, FR-SRC-04, AC-SRC-01, NFR-PERF-01 — plan `docs/plan/2026-10-13-search-evidence-gate-no-answer.md` §4 (Bước 11).
- Commit code: nhánh `feat/search-evidence-gate` @bd34305d + sửa sau lượt r1 (commit đi cùng report này).
- Run: `2026-10-14-gold-v7` (r1, trước sửa) và `2026-10-14-gold-v7-r2` (r2, số trích dẫn). Gold: tag `gold_v7` (sha256 `c2150ef3…f803`,
  252 câu active), split `devtest@gold_v7.json` (126 dev / 126 test). Catalog bench 3.183 unit; model e5-small; collection
  `ProductBench__e5_small` (text `catalog-text-v2`, embed cục bộ 183 s, không gọi API).
- Mốc: `APP.e5s.prod_f12356` (cấu hình production). Arm: `_ev` (evidence_gate), `_dm` (duration_filter + duration_mask),
  `_er` (+ embed_residual), `_ue` (unexplained_empty), `_rs` (no_diacritics_mode restore), `_all` (mọi cờ 1.28.0 + ba họ 1.18.0).

## Toàn gold (r2, 252 câu)

| arm | nDCG@10 | R@10 | Forbidden@10 | forbidden_query_rate | constraint_precision | zero-result in-catalog | zero-result ngoài catalog |
|---|---:|---:|---:|---:|---:|---:|---:|
| base | 0.693 | 0.357 | 0.112 | 0.207 | 0.809 | 0.000 | 0.452 |
| _ev | 0.694 | 0.357 | 0.111 | 0.171 | 0.809 | 0.000 | 0.613 |
| _dm | 0.697 | 0.366 | 0.116 | 0.195 | 0.819 | 0.005 | 0.452 |
| _er | 0.703 | 0.373 | 0.115 | 0.195 | 0.821 | 0.000 | 0.452 |
| _ue | 0.693 | 0.357 | 0.110 | 0.183 | 0.809 | 0.000 | 0.661 |
| _rs | 0.696 | 0.358 | 0.112 | 0.220 | 0.809 | 0.000 | 0.452 |
| _all | 0.712 | 0.375 | 0.043 | 0.061 | 0.911 | 0.000 | 0.742 |

Weaviate p95 (ms): base 124 · _ev 110 · _dm 111 · _er 106 · _ue 105 · _rs 110 · _all 109 (guard 250 ms đạt).

## So với mốc theo split (r2, `compare`, Δ nDCG@10 điểm %, CI95; slice tụt/tăng ≥ 3 điểm)

| arm | dev | test | slice tụt ≥ 3 | slice tăng ≥ 3 |
|---|---|---|---|---|
| _ev | +0.53 [+0.00, +1.14] TIE | −0.43 [−1.19, +0.20] TIE | test: parent_child −3.27 (n 5) | duration_stay +3.1 / +3.3 |
| _dm | +0.34 TIE | +0.35 TIE | duration_false_positive −25.66 (dev) / −7.01 (test) | duration_only +42.2 / +15.3 |
| _er | +0.52 TIE | +1.40 TIE | duration_false_positive −25.66 / −7.01 | duration_only +48.5 / +40.3 |
| _ue | +0.00 TIE | +0.02 TIE | — | — |
| _rs | +0.01 TIE | +0.63 TIE | — | abbrev_typo +3.3, duration_false_positive +8.8 (test) |
| _all | +2.08 **LOSE** (luật slice) | +1.60 TIE | duration_false_positive −25.6 / −7.0; multi_constraint −3.7 (dev); parent_child −7.9 (test) | duration_only +48.5 / +40.3; poi_resolution +20.9 / +13.0 |

## r3 — thời lượng chỉ lọc cứng khi câu chỉ có thời lượng (chốt 14/10)

Run `2026-10-14-gold-v7-r3`, cùng gold/split/catalog; luật mới: câu còn nội dung ngoài thời lượng (kể cả tên điểm vui chơi
"VinWonders") → role `soft`, không lọc.

| arm | nDCG@10 toàn gold | duration_only | duration_false_positive | dev Δ nDCG | test Δ nDCG | slice tụt ≥ 3 |
|---|---:|---:|---:|---|---|---|
| base | 0.693 | 0.271 | 0.703 | — | — | — |
| _dm | 0.705 | 0.558 | 0.707 | +1.39 TIE | +0.99 TIE | dev duration_false_positive −5.66 |
| _er | 0.711 | 0.715 | 0.707 | +1.57 TIE | +2.03 [+0.07, +4.77] (nhãn LOSE: Δndcg ≥ 2 mà recall không có ý nghĩa thống kê — luật `metrics.py:859-867`) | dev duration_false_positive −5.66 |
| _all | 0.721 | 0.715 | 0.720 | +3.13 [+0.45, +6.33] (nhãn LOSE, cùng lý do + slice) | +2.35 (nhãn LOSE) | dev duration_false_positive −5.55, multi_constraint −3.67; test parent_child −7.86 |

So với r2 (gate cứng): duration_false_positive dev −25.66 → −5.66, test −7.01 → +8.00.

## Quyết định bật cờ (người dùng chốt 14/10)

- Bật mặc định production: `SEARCH_EVIDENCE_GATE=true`, `SEARCH_UNEXPLAINED_EMPTY=true`, `SEARCH_NO_DIACRITICS_MODE=restore`.
- Giữ tắt: `SEARCH_DURATION_MASK`, `SEARCH_EMBED_RESIDUAL` (duration_false_positive dev còn −5.66, n 4–5), `SEARCH_EMIT_BACKGROUND`
  (ngưỡng banner chưa đo được bằng bench).

## Câu âm (r2, tỉ lệ trả rỗng; Forbidden@10)

| slice | n | base | _ev | _ue | _all |
|---|---:|---:|---:|---:|---:|
| no_answer | 40 | 0.57 | 0.65 | 0.65 | 0.70 |
| name_collision | 12 | 0.42 (fb 0.23) | 1.00 | 0.75 (fb 0.14) | 1.00 |
| out_of_catalog | 10 | 0.00 | 0.00 | 0.60 | 0.60 |

`_all` còn trả kết quả cho 16 câu âm: tên nơi nước ngoài kèm điểm đến thật ("tháp Eiffel Hà Nội", 8 câu — luật giữ phần câu đã
hiểu là điểm đến, theo Q2 của plan), tỉnh không có sản phẩm nhưng có trong mô tả ("Cao Bằng", "Hà Giang", "Lai Châu", "Ba Bể"),
tên người trùng tên khách sạn ("Phạm Hoàng Long", "Hoàng Kim Ngân", "Đỗ Quốc Bảo"), "ks ks ks ks".

## Sửa giữa r1 và r2 (r1 lộ ra)

- `_ue` r1 chặn nhầm 3 câu có đáp án ("combo VinWonders 3N2Đ", "combo 3N2Đ", "ks gan ho guom"): thời lượng / địa danh không được
  tính là phần câu đã hiểu khi cờ lọc của họ đó tắt → sửa: luôn parse để giải thích (r2: 0 câu chặn nhầm, không slice tụt).
- `_ev` r1 tụt abbrev_typo −10.4, dest_type −14.3, taxonomy_collision −10.0 ("combo trải nghiệm tại Phú Quốc" 1.00 → 0.16): đòi
  cặp âm tiết cho phần cộng RRF quá chặt → sửa: phần cộng RRF chỉ cần một âm tiết giữ dấu; vớt BM25 vẫn đòi cụm (r2: hết tụt).

## Caveat khi trích dẫn

- Nhãn 77 câu mới là nhãn máy (`pool:machine@gold_v7`), chưa duyệt người. judged@10 thấp: duration_stay 0.07, slang_residual 0.09,
  duration_only 0.53 → nDCG ba slice này chưa đáng tin (NEEDS_LABELS, `sb gold holes`).
- `name_collision` gắn `expected_no_result` cả tên đường có trong catalog ("Lý Tự Trọng": khách sạn "HAKU Boutique Hotel Da Lat -
  Ly Tu Trong", 45 mô tả) — nên duyệt lại.
- Mỗi slice dev/test chỉ 3–20 câu; Δ slice ≥ 3 điểm có thể do 1 câu (parent_child n 5).
- `backgroundScore` / ngưỡng banner frontend không đo bằng bench (cần log production).

## Lệnh tái sinh

```
cd src
python -m evaluation.search_bench text --variant "T3+R"
python -m evaluation.search_bench embed --variant "T3+R" --model e5-small
python -m evaluation.search_bench app-load --model e5-small
python -m evaluation.search_bench --run-id 2026-10-14-gold-v7-r2 run --arm APP.e5s.prod_f12356 --arm APP.e5s.prod_f12356_ev --arm APP.e5s.prod_f12356_dm --arm APP.e5s.prod_f12356_er --arm APP.e5s.prod_f12356_ue --arm APP.e5s.prod_f12356_rs --arm APP.e5s.prod_f12356_all
python -m evaluation.search_bench --run-id 2026-10-14-gold-v7-r2 compare APP.e5s.prod_f12356 APP.e5s.prod_f12356_<arm> --split dev|test
python -m evaluation.search_bench --run-id 2026-10-14-gold-v7-r2 guards --arms <danh sách arm>
```
(`.venv-sbench`, `PYTHONPATH=.`, `PYTHONUTF8=1`; output ở `bench_out/search/runs/2026-10-14-gold-v7-r2/`.)
