# RecSys ablation Day 7 — category exclusion bật / tắt (vector e5-small, 05/10)

- Phục vụ: FR-REC-02 (loại vertical đã mua trong chuyến đang mở), M7 lịch 10 ngày (ablation recsys); `docs/prd/test-plan.md` §2.5.
- Commit: `bb41479` + thay đổi chưa commit: funnel thêm mode `noexcl` (`src/evaluation/recsys_bench/models/funnel.py`) — mask engine giữ khoá
  điểm đến của trip mở và bỏ món đã mua, **chỉ tắt** loại taxonomy đã mua. Engine production không đổi (`configHash b0aee886`).
- Dữ liệu: DB bench local seed 09-23, `as_of` 2026-09-24 (như `eval-2026-10-05-recsys-e5-small-vs-e5-base.md`); split đóng băng
  `split-{llbo,temporal}-asof20260924.json`; vector `npy:bench_out/search/data/vec_T3+R_e5-small` (`vectorsMissing 0`).
- Run: `2026-10-05-{llbo,temporal}-ablate-{funnel,noexcl}-e5s` — `--algos algos_v1.yaml --only content_profile --only pop_funnel --funnel-pool
  mask --funnel-rerank none --funnel-rerank mmr`; `expectFailed []` cả 4 run. Δ = tắt − bật, paired bootstrap 10.000 lượt seed 42
  (`compare.compare_arms` ghép hai run theo khách).

> Dữ liệu sinh (handbook §12). Temporal 98 khách: 1 khách = 1,02 điểm.

## Kết quả

| Split | Arm | Hit@20 bật / tắt | Δ hit@20 [CI95] | Δ NDCG@10 [CI95] | Cross-cat chuyến mở có mua bật → tắt |
|---|---|---|---|---|---|
| LLBO (1.016) | `content_profile` (= `engine_nommr`) | 0,871 / 0,598 | **−27,26 [−30,02; −24,61]** | −15,24 [−16,51; −14,02] | 1,000 → 0,167 |
| LLBO | `content_profile+mmr` (= `engine`) | 0,860 / 0,605 | **−25,49 [−28,15; −22,93]** | −14,69 [−15,85; −13,55] | 1,000 → 0,177 |
| LLBO | `pop_funnel` (mpd qua funnel) | 0,820 / 0,636 | −18,41 [−20,87; −16,04] | −9,61 [−10,65; −8,64] | 1,000 → 0,300 |
| Temporal (98) | `content_profile` | 0,184 / 0,174 | −1,02 [−3,06; 0,00] | −0,44 [−1,32; 0,00] | 1,000 → 0,283 |
| Temporal | `content_profile+mmr` | 0,184 / 0,174 | −1,02 [−3,06; 0,00] | −0,44 [−1,32; 0,00] | 1,000 → 0,289 |
| Temporal | `pop_funnel` | 0,102 / 0,102 | 0,00 [0,00; 0,00] | −0,04 [−0,13; 0,00] | 1,000 → 0,350 |

MMR on / off (cùng run, bật exclusion): LLBO `content_profile` 0,871 → `+mmr` 0,860 (−1,1 điểm); temporal không đổi.

## Đọc

- **Category exclusion là phần đóng góp lớn nhất cho khách đang trong chuyến:** tắt nó engine mất ~25 điểm hit@20 ở LLBO và gần như chỉ gợi
  lại đúng loại vừa mua (cross-cat 1,00 → 0,18 — "thêm một khách sạn nữa"). Đúng ý FR-REC-02 và phát hiện tuần 3 "bộ lọc cứng đóng góp nhiều
  hơn thuật toán" (`report_week_3.md` §3.3), nay tách riêng được phần exclusion khỏi khoá điểm đến.
- **Temporal gần như không đổi** vì 73/98 khách không có chuyến mở tại T (exclusion không áp).
- Decay on/off đã đo ở Day 5 (`content-nodecay`, Δ < 0,2 điểm) — §4.17 spec recsys.

## Tái sinh

```bash
# env: DATABASE_URL / EVAL_DATABASE_URL trỏ DB bench seed 09-23 (as_of 2026-09-24), WEAVIATE_API_KEY rỗng
for sp in llbo temporal; do for mode in funnel noexcl; do
  python -m src.evaluation.recsys_bench run --algos src/evaluation/recsys_bench/algos_v1.yaml --only content_profile --only pop_funnel \
    --mode $mode --funnel-pool mask --funnel-rerank none --funnel-rerank mmr --split $sp \
    --vectors npy:bench_out/search/data/vec_T3+R_e5-small --split-file src/evaluation/recsys_bench/frozen/split-$sp-asof20260924.json \
    --run-id 2026-10-05-$sp-ablate-$mode-e5s
done; done
# so cặp: compare.compare_arms({"on": per_user[funnel][arm], "off": per_user[noexcl][arm]}, "off", "on") theo khách
```
