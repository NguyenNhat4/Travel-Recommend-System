# Gate `baseline_v4` và latency đầu-cuối sau khi áp [D] (chuyến đã đặt ưu tiên) và [E] (dormant 365 ngày)

- Ngày chạy: 2026-10-09 · Người chạy: tqanh123 / Claude Code
- Phục vụ: FR-REC-02 (đề xuất `update-archive/2026-10-09-recsys-uu-tien-chuyen-da-dat.md`), FR-REC-01 / persona
  (`update-archive/2026-10-09-persona-trang-thai-cold-start-va-phong-cach-du-lich.md`), NFR-PERF-01; tiêu chí G1 latency
  (Δp95 `latencyMs` ≤ 50 ms, `docs/plan/2026-10-08-recsys-trien-khai-theo-giai-doan.md` §1)
- Engine SAU: nhánh `feat/recSys_update-2` commit `3b37226` (`ENGINE_RULES_VERSION = "2026-10-09-booked-first"`,
  `DORMANT_AFTER_DAYS = 365`, `configHash dcbf67ca`). TRƯỚC: PR-A `feat/recSys_update` `2600ca5` (`2026-10-09-p2-combo-explore`,
  `configHash 3c6ca566`, `baseline_v3`).
- Môi trường như `eval-2026-10-09-recsys-pr-a-gate-v3-latency-sau.md`: DB `vota_prodcopy` (container `vota-prodcopy-pg` :55433),
  vector `.npy` gói bàn giao (gate, cùng file với v3 — đường dẫn khác), Weaviate local `ProductE5SmallProdcopy`
  (127.0.0.1:58080, gRPC 55051) cho backend; hai tập khách `theme_study/results/2026-10-08-lane-a/users-strata.json`,
  `users60-prodcopy.json`. Run id: `20261009-gate-<kind>-prodcopy-v4`; `2026-10-09-e2e-oph-{before1,after1,before2,after2}-{strata,users60,guest}`.

## 1. Gate

`regress --baseline baseline_v3-*`: **KHÔNG SO ĐƯỢC (exit 2) theo thiết kế** cả 4 kind — `configHash 3c6ca566 → dcbf67ca`,
`engineRulesVersion 2026-10-09-p2-combo-explore → 2026-10-09-booked-first`. Ghi `baseline_v4-<kind>-prodcopy-asof20261008.json`
từ chính run v4; `regress` lại run đó: exit 0, 4/4. Split đóng băng khớp sha (`0bff46bb…`, `6b430216…`, `f5bd9dc9…`, `7c27c631…`).

Đối chiếu tay arm `engine` v3 → v4 (cùng split, cùng khách):

| split (khách) | recall@5 | recall@10 | recall@20 | ndcg@10 | strategy v4 |
|---|---|---|---|---|---|
| llbo (4.023) | 0,6214 → 0,6212 | 0,7171 → 0,7169 | 0,8071 → 0,8069 | 0,4949 → 0,4946 | cross_vertical 3.404 · recent_activity 619 |
| temporal (773) | 0,1151 → 0,1151 | 0,1294 → 0,1294 | 0,1565 → 0,1565 | 0,0927 → 0,0927 | long_term 552 · recent_activity 107 · **cross_vertical 64** · cold_start_content 50 |
| nexttrip (1.835) | 0,0278 → 0,0278 | 0,0485 → 0,0485 | 0,0747 → 0,0747 | 0,0247 → 0,0247 | long_term 1.669 · recent_activity 166 (v3: long_term 1.222 · **dormant 447** · recent_activity 166) |
| coldstart (5.233) | 0,7361 → 0,7361 | 0,7699 → 0,7699 | 0,8091 → 0,8091 | 0,6086 → 0,6086 | cold_start_content 2.668 · recent_activity 2.564 · long_term 1 |

- Recall gần như không đổi (llbo −0,0002): [D] chỉ đổi chuyến mở của khách có chuyến đã đặt **và** một lượt xem lẻ đến sau — hiếm
  trên dữ liệu seed (bench 09/10: không đổi số nào trên split thật). Bằng chứng hành vi là kịch bản `booked_browse`
  (`eval-2026-10-09-recsys-cong-thuc-oph.md` §4: cross_vertical 0 → 100 %).
- [E] đổi **nhãn** `strategy`: `dormant` biến mất trên nexttrip (447 → 0) vì seed sinh khoảng cách giữa hai chuyến 60–240 ngày; danh
  sách gợi ý không đổi (nhánh dormant và long_term chấm điểm như nhau).
- Harness arm `content_profile` lệch engine 1 khách về `strategy` ở nexttrip (long_term 1.668 vs 1.669) — **có sẵn ở v3** (1.221 vs
  1.222): `models/seeds.profile_for` lấy "hôm nay" theo ngày UTC, engine theo giờ Việt Nam (`local_today`). Không do thay đổi này.

## 2. Latency đầu-cuối (G1)

`http-latency --runs 6 --k 4` (bỏ lượt 1 → 300 mẫu / tập; guest `--runs 11` → 40 mẫu); số = `diagnostics.latencyMs` (server) p50 /
**p95** ms; xen kẽ TRƯỚC / SAU, khởi động lại backend mỗi lượt, máy không chạy job khác.

| Tập | TRƯỚC 1 | SAU 1 | TRƯỚC 2 | SAU 2 |
|---|---|---|---|---|
| strata | 63.0 / **81.0** | 62.0 / **79.1** | 61.5 / **79.0** | 61.0 / **81.0** |
| users60 | 62.0 / **81.0** | 58.0 / **79.0** | 56.0 / **78.0** | 57.0 / **81.0** |
| guest | 8.0 / **9.0** | 8.5 / **10.0** | 8.0 / **9.0** | 9.0 / **12.0** |

Δp95 SAU − TRƯỚC tối đa **+3 ms** (users60 lượt 2 so lượt 2), nằm trong mức trôi giữa hai lượt TRƯỚC cùng engine (3 ms). **Đạt G1.**

p95 theo `strategy` (ms; n sau khi bỏ lượt 1):

| Tập | strategy | TRƯỚC 1 | SAU 1 | TRƯỚC 2 | SAU 2 |
|---|---|---|---|---|---|
| strata | cold_start_content | 67.0 (30) | 62.9 (30) | 68.6 (30) | 65.5 (30) |
| strata | dormant | 80.8 (45) | 78.3 (15) | 77.8 (45) | 76.3 (15) |
| strata | long_term | 82.3 (195) | 80.0 (225) | 80.0 (195) | 82.0 (225) |
| strata | recent_activity | 72.4 (25) | 67.8 (25) | 66.2 (25) | 67.4 (25) |
| strata | popular | 38.8 (5) | 39.0 (5) | 41.2 (5) | 20.8 (5) |
| users60 | dormant | 82.5 (90) | 79.0 (45) | 79.1 (90) | 80.0 (45) |
| users60 | long_term | 80.0 (145) | 80.0 (190) | 78.0 (145) | 81.0 (190) |
| users60 | recent_activity | 66.2 (5) | 65.8 (5) | 48.6 (5) | 66.0 (5) |
| users60 | popular | 42.0 (60) | 42.0 (60) | 43.0 (60) | 42.0 (60) |

Nhóm `dormant` nhỏ đi đúng như [E] (khách 180–365 ngày chuyển sang `long_term`).

**Parity offline ↔ HTTP:** SAU `parity --k 5 --vectors weaviate` **60/60** cả hai lượt. TRƯỚC 51/60 (lệch trường, ids trùng hết) —
dự kiến, vì parity so HTTP với `OfflineEngine` của code SAU: 9 khách khác nhãn `strategy` (dormant 180 → 365).

## 3. Caveat

- Không có mẫu `cross_vertical` trong hai tập khách (bản sao 08/10 hầu như không có chuyến đã đặt còn mở), nên latency của nhánh [D]
  được đại diện gián tiếp; [D] chỉ đổi một phép chọn trong danh sách chuyến mở (không thêm I/O).
- Weaviate Cloud khác region không đo ở đây (như report v3 §2).

## 4. Lệnh tái sinh

```bash
# gate (env DSN 55433, WEAVIATE_URL không tới được, PYTHONUTF8=1)
for k in llbo temporal nexttrip coldstart; do
  python -m src.evaluation.recsys_bench run --arm engine --arm engine_nommr --arm most_popular_in_destination \
    --algos src/evaluation/recsys_bench/algos_v1.yaml --only content_profile --only star_blend_a1 --funnel-pool engine --mode funnel \
    --split $k --vectors npy:<gói bàn giao>/vectors/vec_prodcopy_e5s --split-file src/evaluation/recsys_bench/frozen/split-$k-prodcopy-asof20261008.json \
    --run-id 20261009-gate-$k-prodcopy-v4
  python -m src.evaluation.recsys_bench regress --run-id 20261009-gate-$k-prodcopy-v4 --baseline src/evaluation/recsys_bench/frozen/baseline_v3-$k-prodcopy-asof20261008.json  # exit 2
  python -m src.evaluation.recsys_bench analyze --run-id 20261009-gate-$k-prodcopy-v4
  python -m src.evaluation.recsys_bench baseline --run-id 20261009-gate-$k-prodcopy-v4 --note "baseline_v4: …" --out src/evaluation/recsys_bench/frozen/baseline_v4-$k-prodcopy-asof20261008.json
done
# latency: backend env như eval-2026-10-08-recsys-latency-dau-cuoi-truoc.md §2 + WEAVIATE_GRPC_PORT=55051 (Weaviate local), cổng 8010;
# mỗi lượt: parity --users users60-prodcopy.json --k 5 --vectors weaviate; http-latency --users {users-strata,users60-prodcopy}.json --runs 6 --k 4;
# http-latency --runs 11 --k 4 (guest). TRƯỚC = git worktree add --detach <dir> 2600ca5.
```
