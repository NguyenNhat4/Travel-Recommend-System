# Search v1 — dense, hybrid, hybrid+normalize sau gold D5a

- Phục vụ: FR-SRC-01..04, AC-SRC-01, NFR-PERF-01.
- Run ID: `20261001-day4-local`; gold hiện ở working tree, dự kiến tag `gold_v3` sau review.
- Gold: 131 câu active, 13 slice, 4.991 nhãn active; SHA-256 `4d2ac02fa960ceaf2c9286bf546da1b77023435a9337ecadee22dd7cc62f5784`.
- Cùng Cohere `embed-multilingual-v3.0`, 1024 chiều, text `T3+R`, collection `ProductBench` local 3.183 object. Ba arm chỉ khác retrieval/normalize; không sweep cutoff.
- Số được rescore từ top-k đã lưu sau D4b và D5a, không gọi mạng.

## Kết quả overall

| Arm | Config hash | Recall@10 | nDCG@10 | MRR@10 | Judged@10 | Zero in-catalog | Weaviate p50/p95 ms |
|---|---|---:|---:|---:|---:|---:|---|
| APP.dense | `9b5603cb85c0a5b39714d15d7d75b9efcefa9b3d` | 0,305920 | 0,619530 | 0,693304 | 1,000000 | 0,164062 | 75,180 / 99,976 |
| APP.hybrid | `154339f447230ab37195c8e61f4a989db080d886` | 0,306081 | 0,596552 | 0,643083 | 1,000000 | 0,156250 | 163,421 / 195,559 |
| APP.hybrid_norm | `b7c0f98691338a5f59bec8726020b49d5a3fd6a8` | 0,339702 | 0,647718 | 0,704021 | 1,000000 | 0,070312 | 171,994 / 694,708 |

## Paired bootstrap, B − A

| So sánh | Δ Recall@10; CI95; p | Δ nDCG@10; CI95; p | Verdict |
|---|---|---|---|
| dense → hybrid | +0,02; [−0,40; +0,42]; 0,436 | −2,30; [−4,60; −0,01]; 0,975 | LOSE; `dest_type` −13,19 |
| hybrid → hybrid+normalize | +3,36; [+1,46; +5,59]; <0,001 | +5,12; [+1,73; +9,14]; 0,001 | LOSE guard; `cross_vertical` −5,82 |
| dense → hybrid+normalize | +3,38; [+1,33; +5,67]; <0,001 | +2,82; [−1,21; +7,00]; 0,080 | LOSE guard; `dest_type` −13,19 |

Normalize sửa đáng kể hybrid, đặc biệt `abbrev_typo` và giảm zero-result. Tuy vậy hybrid+normalize chưa thắng dense theo win rule vì tổn thất slice vượt giới hạn. Dense tiếp tục là mốc APP của vòng này.

`no_diacritics` vẫn là lỗi hành vi rõ: dense và hybrid rỗng 12/12 câu; hybrid+normalize còn rỗng 8/12. Judged đầy đủ không biến câu rỗng thành câu tốt.

## Lệnh tái sinh

```bash
python -m evaluation.search_bench --dataset jsonl --run-id 20261001-day4-local rescore
python -m evaluation.search_bench --dataset jsonl --run-id 20261001-day4-local compare APP.dense APP.hybrid --gold gold_v3
python -m evaluation.search_bench --dataset jsonl --run-id 20261001-day4-local compare APP.hybrid APP.hybrid_norm --gold gold_v3
python -m evaluation.search_bench --dataset jsonl --run-id 20261001-day4-local compare APP.dense APP.hybrid_norm --gold gold_v3
```
