# PR-A RecSys: gate `baseline_v3` trên bản sao production và latency đầu-cuối SAU

- Ngày: 2026-10-09 · Người chạy: tqanh123 / Claude Code
- Phục vụ: FR-REC-01, FR-REC-02 (P2, loại combo ↔ thành phần, ô khám phá — `docs/prd/requirements.md` §1.3, AC-REC-02/03),
  NFR-PERF-01; tiêu chí G1 của `docs/plan/2026-10-08-recsys-trien-khai-theo-giai-doan.md` §1 (Δp95 `latencyMs` ≤ 50 ms)
- Engine: cây làm việc PR-A trên `2f3b593` (chưa commit lúc đo; `ENGINE_RULES_VERSION = "2026-10-09-p2-combo-explore"`,
  `configHash 3c6ca566`); TRƯỚC = worktree `2f3b593` (`2026-10-02-trip-ended`, `configHash c893694f`)
- Môi trường: như `eval-2026-10-08-recsys-latency-dau-cuoi-truoc.md` §2 — DB `vota_prodcopy` (container `vota-prodcopy-pg`,
  :55433), vector `.npy` gói bàn giao (gate) / collection Weaviate local `ProductE5SmallProdcopy` (backend), cùng hai tập khách
  `users-strata.json`, `users60-prodcopy.json`. Run id: `20261009-gate-<kind>-prodcopy-v3`, `2026-10-09-e2e-{before1,after1,before2,after2}-{strata,users60,guest}`,
  parity `20261009-023430-parity`, `20261009-023445-parity`.
- History: `history/2026-10-09-recsys-pr-a-p2-loai-combo-o-kham-pha.md`

## 1. Gate: `regress` vs `baseline_v2` và `baseline_v3`

`regress --baseline baseline_v2-*`: **KHÔNG SO ĐƯỢC (exit 2) theo thiết kế** — `configHash c893694f → 3c6ca566`,
`engineRulesVersion 2026-10-02-trip-ended → 2026-10-09-p2-combo-explore`. `baseline_v3-<kind>-prodcopy-asof20261008.json` ghi từ
cùng run; `regress` lại chính run đó: exit 0, 4/4 kind. Split đóng băng không đổi (sha `0bff46bb…`, `6b430216…`, `f5bd9dc9…`,
`7c27c631…`); meta split có thêm `comboRelatedTarget` (llbo 1, còn lại 0 — fingerprint split không gồm meta).

Đối chiếu tay run v3 với run v2 cùng split (cùng số khách; arm `engine` = `content_profile+mmr` = `star_blend_a1+mmr` ở mọi
chỉ số — gương harness vẫn đúng kể cả ô khám phá):

| split (khách) | arm | recall@5 v2 → v3 | recall@10 | recall@20 | ndcg@10 | catalog_coverage | `explore_filled` (món / khách) |
|---|---|---|---|---|---|---|---|
| llbo (4.023) | engine | 0,6214 → 0,6214 (0) | 0,7189 → 0,7171 (−0,0017) | 0,8071 → 0,8071 (0) | 0,4977 → 0,4949 (−0,0028) | 0,7492 → 0,8445 (+0,095) | 1,48 |
| llbo | engine_nommr | 0,6264 → 0,6261 | 0,7283 → 0,7271 | 0,8245 → 0,8250 | 0,5057 → 0,5030 | 0,7240 → 0,7250 | 0 |
| temporal (773) | engine | 0,1177 → 0,1151 (−0,0026) | 0,1320 → 0,1294 (−0,0026) | 0,1604 → 0,1565 (−0,0039) | 0,0950 → 0,0927 (−0,0023) | 0,6278 → 0,6131 | 0,21 |
| temporal | engine_nommr | 0,1087 → 0,1100 | 0,1229 → 0,1229 | 0,1514 → 0,1488 | 0,0889 → 0,0885 | 0,6346 → 0,6097 | 0 |
| nexttrip (1.835) | engine | 0,0283 → 0,0278 (−0,0005) | 0,0469 → 0,0485 (+0,0016) | 0,0785 → 0,0747 (−0,0038) | 0,0242 → 0,0247 (+0,0005) | 0,7074 → 0,6792 | 0 |
| nexttrip | engine_nommr | 0,0207 → 0,0207 | 0,0398 → 0,0376 | 0,0638 → 0,0599 | 0,0200 → 0,0193 | 0,6835 → 0,6407 | 0 |
| coldstart (5.233) | engine | 0,7369 → 0,7361 (−0,0008) | 0,7703 → 0,7699 (−0,0004) | 0,8095 → 0,8091 (−0,0004) | 0,6111 → 0,6086 (−0,0025) | 0,8783 → 0,8783 | 0,006 |
| coldstart | engine_nommr | 0,7285 → 0,7283 | 0,7634 → 0,7623 | 0,8051 → 0,8034 | 0,6118 → 0,6088 | 0,8639 → 0,8636 | 0 |

`most_popular_in_destination` (canary) không đổi ở 4 split. Mọi chênh recall ≤ 0,004 tuyệt đối — dưới ngưỡng `maxDropPoints 1,0`
của gate và xa ngưỡng G1 0,04. Ô khám phá chỉ chạm nhánh chuyến mở (llbo: mọi khách đều có chuyến mở tại `as_of` = lúc mua →
1,48 món / khách ở k = 20; coldstart gần 0 vì các điểm đến đủ 20 món) và nâng `catalog_coverage` llbo +0,095 mà không đổi
recall@20 (món khám phá nối **sau** món tại X).

**Caveat:** k = 20 (mode eval, không cap taxonomy) nên `explore_filled` lớn hơn production (k = 4–5). Mức lệch nhỏ gồm cả ba
luật (P2, closure combo, ô B) — không tách riêng ở đây; từng luật đã đo riêng ở `eval-2026-10-08-recsys-g2-va-wp4.md`
(ô B, P2) và `eval-2026-10-09-recsys-g6-so-thich-do-lai.md` (P2). Closure combo không đo được bằng split (chỉ 1 target llbo
liên quan combo) — kiểm bằng unit test.

## 2. Latency đầu-cuối SAU (tiêu chí G1)

`http-latency --runs 6 --k 4 --drop-first` (300 mẫu / tập; guest `--runs 11`, 40 mẫu); số = `diagnostics.latencyMs` (server) p50 / p95
ms, xen kẽ TRƯỚC (worktree `2f3b593`) / SAU, restart backend giữa mỗi lượt, máy không chạy job khác:

| Tập khách | TRƯỚC 1 | SAU 1 | TRƯỚC 2 | SAU 2 | Δp95 SAU − TRƯỚC (max) |
|---|---|---|---|---|---|
| `users-strata.json` | 70,5 / **87,0** | 62,0 / **84,0** | 68,0 / **87,0** | 71,0 / **91,0** | **+4,0** |
| `users60-prodcopy.json` | 67,0 / **85,0** | 74,0 / **95,0** | 70,0 / **92,0** | 71,0 / **90,0** | **+6,5** (so trung bình TRƯỚC 88,5) |
| guest (`popular`) | 9 / 9 | 9 / 10 | 9 / 10 | 9 / 10 | +1 |

Theo `strategy` (p95, `users-strata.json`; n = 190 / 35 / 25 / 45 / 5 sau drop-first):

| strategy | TRƯỚC 1 | SAU 1 | TRƯỚC 2 | SAU 2 |
|---|---|---|---|---|
| `long_term` | 87,5 | 84,5 | 87,0 | 91,0 |
| `cold_start_content` (chuyến mở chỉ xem — nhánh ô B) | 72,2 | 69,0 | 76,0 | 75,3 |
| `recent_activity` (nhánh ô B) | 71,0 | 60,4 | 70,6 | 73,0 |
| `dormant` | 88,6 | 87,8 | 91,8 | 91,8 |
| `popular` (n = 5) | 41,0 | 37,4 | 44,8 | 31,8 |

`users60-prodcopy.json`: `long_term` 87,0 / 96,0 / 92,0 / 91,0; `dormant` 84,0 / 95,5 / 95,5 / 90,5; `popular` 44 / 44 / 43 / 44;
`recent_activity` (n = 5) 68,6 / 78,8 / 74,6 / 80,6. Chênh TRƯỚC-1 ↔ TRƯỚC-2 (cùng engine) tới 8 ms p95 — mức trôi máy; mọi
Δ SAU − TRƯỚC nằm trong mức trôi đó, tối đa +6,5 ms tổng và +10 ms ở nhóm n = 5. **Đạt G1 (≤ 50 ms).** Nhánh ô B
(`recent_activity` / `cold_start_content`) không chậm hơn: lượt `near_vector(u_long)` thứ hai chỉ chạy khi còn ô trống và
Weaviate local trả < 5 ms. Caveat cloud như report TRƯỚC §5: Weaviate Cloud khác region có thể thêm hàng chục ms cho lượt
này; nếu p95 staging vượt ngưỡng → `RECOMMEND_EXPLORE_FILL=false`.

Parity offline ↔ HTTP trên engine SAU: `parity --k 5 --vectors weaviate` **60/60** cả hai tập (ids, strategy, destination,
excludedVerticals trùng); log backend có sự kiện `recsys.explore_fill`.

## 3. Lệnh tái sinh

```bash
export PYTHONUTF8=1; VEC=npy:<gói bàn giao>/vectors/vec_prodcopy_e5s   # env: prodcopy.env.sh (DSN 55433)
for k in llbo temporal nexttrip coldstart; do
  python -m src.evaluation.recsys_bench run --arm engine --arm engine_nommr --arm most_popular_in_destination \
    --algos src/evaluation/recsys_bench/algos_v1.yaml --only content_profile --only star_blend_a1 --funnel-pool engine --mode funnel \
    --split $k --vectors $VEC --split-file src/evaluation/recsys_bench/frozen/split-$k-prodcopy-asof20261008.json --run-id 20261009-gate-$k-prodcopy-v3
  python -m src.evaluation.recsys_bench regress --run-id 20261009-gate-$k-prodcopy-v3 --baseline src/evaluation/recsys_bench/frozen/baseline_v2-$k-prodcopy-asof20261008.json  # exit 2
  python -m src.evaluation.recsys_bench analyze --run-id 20261009-gate-$k-prodcopy-v3
  python -m src.evaluation.recsys_bench baseline --run-id 20261009-gate-$k-prodcopy-v3 --note "baseline_v3: …" --out src/evaluation/recsys_bench/frozen/baseline_v3-$k-prodcopy-asof20261008.json
done
# latency: backend theo eval-2026-10-08-recsys-latency-dau-cuoi-truoc.md §2 (TRƯỚC: git worktree add <dir> 2f3b593), mỗi lượt:
python -m src.evaluation.recsys_bench http-latency --base-url http://127.0.0.1:8000 --users users-strata.json --token-env AUTH_SERVICE_TOKEN --runs 6 --k 4 --run-id 2026-10-09-e2e-<label>-strata
python -m src.evaluation.recsys_bench http-latency --base-url http://127.0.0.1:8000 --users users60-prodcopy.json --token-env AUTH_SERVICE_TOKEN --runs 6 --k 4 --run-id 2026-10-09-e2e-<label>-users60
python -m src.evaluation.recsys_bench http-latency --base-url http://127.0.0.1:8000 --runs 11 --k 4 --run-id 2026-10-09-e2e-<label>-guest
python -m src.evaluation.recsys_bench parity --base-url http://127.0.0.1:8000 --users users60-prodcopy.json --k 5 --vectors weaviate --token-env AUTH_SERVICE_TOKEN
# p95 theo strategy: nhóm samples[] của http_latency.json theo `strategy`, bỏ run 1
```
