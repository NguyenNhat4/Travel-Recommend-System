# RecSys eval-v2 — bộ dữ liệu đánh giá đủ tín hiệu + 4 đề thi đóng băng (bàn giao tqanh123, 05/10)

- Phục vụ: FR-REC-01..04, FR-CDP-01, NFR-PERF-01; `docs/prd/test-plan.md` §2.5. Người dùng chốt 05/10: bộ dữ liệu riêng đủ để đánh giá mọi
  thuật toán (CF, chuyến kế tiếp, bỏ giỏ, khách mới); tqanh123 tự đo đầy đủ; lượt này chỉ là **chạy thử kiểm harness + số sơ bộ**.
- Spec: `docs/spec/MOCK_DATA_SPEC.md` §4.1 (profile `eval-v2`, `--history-only`), `docs/spec/bench/recsys-offline-eval.md` §3.2 (split mới).
- Commit: `bb41479` + thay đổi chưa commit (entry `history/2026-10-05-recsys-eval-v2-du-lieu-va-split.md`). Engine không đổi
  (`configHash b0aee886`).

> Dữ liệu sinh (handbook §12): số cho biết thuật toán chạy đúng và so tương đối trên cùng dữ liệu, không nói gì về khách thật.

## 1. Dữ liệu

`python -m data_collection.seed.seed_histories --profile eval-v2` (catalog snapshot 30/09, 11.718 sản phẩm; `as_of` 2026-10-05; seed 42).
Bộ demo không đổi một byte (sha output trước / sau thay đổi trùng: `5fdbb170…`, 7.321 event).

| Chỉ số | Demo (2.000) | eval-v2 |
|---|---:|---:|
| Khách | 2.000 | 5.000 |
| Event | 7.321 | 32.782 (view 13.267 · purchase 10.937 · giỏ 6.733 · search 1.845) |
| Khách có mua / quay lại ≥ 2 chuyến | 1.480 / 270 (18 %) | 3.722 / 1.502 (**40 %**) |
| add_to_cart không mua (bỏ giỏ) | 27 (cạnh lộn xộn) | 2.482 (~20 % số chuyến) |
| Event tối đa / khách | 15 | 36 (giới hạn 40) |

DB local: `vota_recsys_evalv2_20261005` (Postgres bench cổng 55433, `db/vota_schema.sql` + `load_vota`); `db/verify.sql` FAIL đúng 3 cổng quy mô
của demo (profiles, events, max events/khách) — theo thiết kế. Vector: `bench_out/recsys-enriched-20261005/vec_enriched_e5-small` (e5-small,
cùng catalog 30/09, `vectorsMissing 0`).

## 2. Bốn đề thi đóng băng (`src/evaluation/recsys_bench/frozen/split-*-evalv2-asof20261005.json`)

| Split | Câu hỏi | Khách | sha256 | Target theo loại | Target có sẵn trong lịch sử của khách |
|---|---|---:|---|---|---:|
| `llbo` | món tiếp theo (thường trong chuyến đang mở) | 2.876 | `a2d8ae24b77b` | attraction 1.170 · flight 888 · combo 422 · hotel 271 · golf 125 | 1.585 (55 %) |
| `temporal` | mua gì sau mốc T chung | 658 | `8ae501115c20` | hotel 524 · attraction 58 · flight 55 · combo 21 | — |
| `nexttrip` | **chuyến sau** (chuyến trước đã đi xong; `as_of` = lúc bắt đầu duyệt chuyến mới) | 1.493 | `a309dc74c2d4` | hotel 1.194 · attraction 133 · flight 114 · combo 52 | 28 (21 do lần bỏ giỏ trước đó) |
| `coldstart` | lần mua đầu (có ≥ 1 event trước) | 3.705 | `3b150ca38aa9` | hotel 2.990 · flight 288 · attraction 280 · combo 147 | 3.637 (đã xem / bỏ giỏ ngay trước) |

Nhãn `targetInOwnHistory` / `targetInOwnCart` / `targetViewed` có trong `per_user.jsonl` của mọi run; split cũ `asof20260924` giữ nguyên sha.

## 3. Kết quả chạy thử (engine + baseline toàn bộ khách; CF 200 khách)

Run: `bench_out/recsys-evalv2-20261005/runs/20261005-evalv2-{split}-v5`, `…-algos-smoke`. Mọi run exit 0, split khớp sha, `vectorsMissing 0`;
algos `expectFailed []`, leak 0.

**Engine so với `most_popular_in_destination`** (`compare`, paired bootstrap 10.000 lượt, seed 42; điểm ×100):

| Split | n | Engine hit@20 / NDCG@10 | mpd hit@20 / NDCG@10 | Δ hit@20 [CI95] | Δ NDCG@10 [CI95] |
|---|---:|---|---|---|---|
| llbo | 2.876 | 0,848 / 0,484 | 0,693 / 0,385 | +15,51 [+13,87; +17,14] | +9,96 [+9,10; +10,81] |
| temporal | 658 | 0,134 / 0,050 | 0,082 / 0,026 | +5,17 [+2,58; +7,75] | +2,38 [+1,29; +3,47] |
| **nexttrip** | 1.493 | **0,074** / 0,025 | 0,062 / 0,023 | **+1,21 [−0,20; +2,68]** | +0,17 [−0,41; +0,76] |
| coldstart | 3.705 | 0,787 / 0,381 | 0,330 / 0,121 | +45,67 [+43,97; +47,37] | +26,00 [+25,14; +26,84] |

`random` hit@20 0,008–0,011 · `most_popular` 0,056–0,252 ở mọi split. Coverage engine 0,44–0,98.

**Theo nhãn** (hit@20, engine / mpd):

| Split | Target có sẵn trong lịch sử | Không có |
|---|---|---|
| llbo | 1.585 khách: 0,842 / 0,665 | 1.291 khách: 0,856 / 0,728 |
| nexttrip | 28 khách: 0,464 / 0,643 | 1.465 khách: **0,066 / 0,051** |
| coldstart | 3.637 khách: 0,791 / 0,322 | 68 khách: 0,574 / 0,779 |

**CF chạy thử (200 khách, funnel, pool mask, rerank none — chỉ để kiểm chạy được, không kết luận)**, hit@20:

| Split | content | star_blend | pop_funnel | cooc_trip | itemknn | ease | rp3beta | ials | bpr | bpr_dest |
|---|---|---|---|---|---|---|---|---|---|---|
| llbo | 0,88 | 0,89 | 0,82 | 0,79 | 0,79 | 0,70 | 0,79 | 0,79 | 0,61 | 0,83 |
| temporal | 0,14 | 0,14 | 0,13 | 0,08 | 0,07 | 0,07 | 0,09 | 0,07 | 0,04 | 0,12 |
| nexttrip | 0,09 | 0,09 | 0,09 | 0,06 | 0,06 | 0,06 | 0,06 | 0,05 | 0,04 | 0,07 |
| coldstart | 0,81 | 0,77 | 0,34 | 0,34 | 0,34 | 0,34 | 0,34 | 0,57 | 0,31 | 0,41 |

## 4. Đọc nhanh (sơ bộ, chờ tqanh đo đủ)

1. **Chưa chứng minh engine tốt hơn mpd ở chuyến kế tiếp:** hit@20 0,074, hoà mpd (CI chứa 0); bỏ 28 khách có lần bỏ giỏ trước, còn 0,066. Khi khách chưa
   duyệt gì cho chuyến mới, engine không biết điểm đến kế. Đây là khoảng trống lớn nhất — đúng câu hỏi ADR 2 "split next trip" đặt ra.
2. LLBO / temporal / coldstart: engine thắng mpd rõ (CI > 0). Coldstart cao vì khách mới đã xem đúng món ngay trước khi mua (98 %).
3. LLBO: 55 % khách có target sẵn trong lịch sử (giỏ / xem) — engine vẫn 0,856 ở nhóm không có, nên lợi thế không chỉ nhờ tín hiệu giỏ.
4. CF 200 khách: không thuật toán nào vượt content ở `nexttrip` / `temporal`; cần chạy đủ để kết luận (mục 5).

## 5. Việc của tqanh123 — lệnh chạy đủ

```bash
# DB: tự dựng (tất định) hoặc dùng DB bench của Khôi
git worktree add --detach <wt> HEAD && cd <wt>/src
python -m data_collection.seed --products data_collection/snapshots/2026-09-30/products.jsonl.gz --as-of 2026-10-05 --seed 42 --profile eval-v2 --generate-only
# tạo DB rỗng, áp db/vota_schema.sql, rồi: python -c "from data_collection.seed.database import load_vota; load_vota('<dsn>', Path('<data dir>'), False)"
# env: DATABASE_URL / EVAL_DATABASE_URL trỏ DB đó; RECSYS_HOME=bench_out/recsys-evalv2-20261005
V=npy:bench_out/recsys-enriched-20261005/vec_enriched_e5-small   # hoặc vector e5-small của catalog 30/09
for sp in llbo temporal nexttrip coldstart; do SF=src/evaluation/recsys_bench/frozen/split-$sp-evalv2-asof20261005.json
  python -m src.evaluation.recsys_bench run --algos src/evaluation/recsys_bench/algos_v1.yaml --mode funnel --funnel-pool mask \
    --funnel-rerank none --funnel-rerank mmr --max-tier 2 --split $sp --vectors $V --split-file $SF --run-id <date>-evalv2-$sp-algos-funnel
  python -m src.evaluation.recsys_bench run --algos src/evaluation/recsys_bench/algos_v1.yaml --mode raw … --run-id <date>-evalv2-$sp-algos-raw
  python -m src.evaluation.recsys_bench analyze --run-id 20261005-evalv2-$sp-v5
done
```

Gợi ý theo thứ tự: (a) bảng CF đủ khách trên `nexttrip` (CF / đồng mua có lợi thế đúng ở câu hỏi này); (b) phân khúc theo `targetInOwnHistory`
cho LLBO (ADR 2 #2); (c) grid `W_SHORT/W_POP` trên `temporal` 658 khách (CI hẹp hơn bộ cũ 98 khách); (d) thử tín hiệu bỏ giỏ (`targetInOwnCart`).

## 6. Staging — đổi sang bổ sung, không thay lịch sử

Người dùng chốt bổ sung khách tổng hợp mới, giữ toàn bộ lịch sử cũ và persona. Không chạy lệnh `--history-only` cho đợt này.
Theo dõi trạng thái nạp và bàn giao tại [report append](eval-2026-10-05-cdp-append-recsys-handoff.md).
Bảng điểm phía trên vẫn thuộc **eval-v2 riêng**, không phải kết quả trên staging sau làm giàu.

## 7. Caveat

- Dữ liệu sinh; phân bố eval-v2 do người dùng chốt (40 % quay lại, ~20 % bỏ giỏ) — kết luận phụ thuộc giả định này.
- `nexttrip` / `coldstart` vẫn chủ yếu target hotel (80 %) vì món đầu của chuyến thường là khách sạn.
- CF chỉ chạy 200 khách; số trong bảng CF không dùng để xếp hạng thuật toán.
- p95 offline (bench) không phải độ trễ API.
