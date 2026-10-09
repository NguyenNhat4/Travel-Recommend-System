# PR-B: F14c + 2 món / điểm đến khi không có chuyến mở — parity, D1–D5 trên mốc mới, gate `baseline_v6`, latency

- Ngày chạy: 2026-10-09 · Người chạy: tqanh123 / Claude Code
- Phục vụ: FR-REC-04, FR-REC-02 (đề xuất `docs/prd/update-archive/2026-10-08-recsys-chuan-hoa-so-thich-giua-hai-chuyen.md`, G2 chốt
  lại = (a) theo `docs/spec/bench/recsys-bam-so-thich-quyet-dinh.md` §7.7, G5b chốt 09/10), NFR-PERF-01 (G1)
- Engine SAU: nhánh `feat/recSys_update-2` (`ENGINE_RULES_VERSION = "2026-10-09-next-trip-f14c"`, `SEMANTIC_Q_LOW/HIGH = 0.8529 /
  0.9387`, `W_NEXT_* = 0.50 / 0.35 / 0.15`, `MAX_PER_DESTINATION = 2`, `configHash 54b42809`). TRƯỚC: `603aac6`
  (`2026-10-09-origin-session`, `configHash 8c717872`, `baseline_v5`) — đã gồm PR-A + [D] + [E] + [F].
- Môi trường như `eval-2026-10-09-recsys-gate-v5-diem-xuat-phat-phien-xem.md` (DB `vota_prodcopy`, DB G6 `vota_g6pref_v1`, vector
  `.npy` gói bàn giao, Weaviate local `ProductE5SmallProdcopy`). Run id: `20261009-gate-<kind>-prodcopy-v6`,
  `2026-10-09-e2e-b-{before1,after1,before2,after2}-{strata,users60,guest}`. Kết quả gốc:
  `src/evaluation/recsys_bench/theme_study/results/2026-10-09-pr-b/`.

## 1. Parity engine ↔ cấu hình đã chốt (C3)

Trên engine TRƯỚC chạy cấu hình harness `B2` (= C3: production + F14c + destCap2; F14c tính đúng dạng ba hạng của [B]), so với engine
SAU (`B0`), cùng khách / tham số (`eval_oph --splits llbo,temporal,nexttrip,coldstart --scenarios
between,open,noisy_paired,booked_browse,session_multi,dormant --syn-seeds 13 --syn-target`) — `parity_b2_vs_engine.txt`:

| stratum | n | nDiscordant4 | nDiscordant20 |
|---|---:|---:|---:|
| llbo / temporal / nexttrip / coldstart | 4.023 / 773 / 1.835 / 5.233 | 0 | 0 |
| syn_between / open / noisy_paired / booked_browse / session_multi / dormant | 240 / 240 / 240 / 193 / 239 / 240 | 0 | 0 |

## 2. Calibration (`calibrate.json`)

`theme_study/calibrate` trên engine hiện tại, 120 request khách giả lập `between` mỗi seed: seed 99 → **0,8529 / 0,9387** (trùng hằng
ship), seed 7 → 0,8510 / 0,9403, seed 2026 → 0,8544 / 0,9379 (lệch ≤ 0,002). `modelVersion` khớp tag
`intfloat/multilingual-e5-small:catalog-text-v2`.

## 3. Tiêu chí G2 / G1 trên mốc mới (production đã có chuỗi O → C3)

**DB G6** (dữ liệu có sở thích — nơi định nghĩa luật đóng G2; `g6_ci.txt`, bootstrap ghép cặp 10.000 lần, TUNE + TEST gộp):

| Tiêu chí | Kết quả | |
|---|---|---|
| D1 nexttrip **hit@4** (G2 = (a)) | −0,0026 [−0,0077, +0,0026] | ✅ CI chứa 0 |
| D2 nexttrip destHit@20 | +0,0245 [+0,0026, +0,0464] | ✅ |
| D3 LLBO h@4 / coldstart h@4 | +0,0000 / −0,0003 [−0,0008, +0,0000] | ✅ |
| D4 temporal h@20 | −0,0242 [−0,0379, −0,0121] | ✅ (≥ −0,04) |
| D5 syn_between tgtHit@20 / nextDestHit@20 | +0,0333 [+0,0125, +0,0583] / −0,0167 [−0,0792, +0,0458] | nửa đạt (như lane B) |
| theme between / noisy_paired | +0,3038 / +0,3448 | ✅ (≥ +0,15) |
| `open` | +0,0000 | ✅ |
| nexttrip h@20 (chỉ theo dõi) | −0,0387 [−0,0490, −0,0284] | ghi nhận theo §7.7 |

**Bản sao production** (seed không có sở thích; `prodcopy_ci.txt`): nexttrip hit@4 −0,0065 [−0,0120, −0,0016] (CI **không** chứa 0),
nexttrip h@20 −0,0300, temporal h@20 −0,0233 (đạt G1 0,04), LLBO không đổi, theme +0,3295 / +0,3208, `open` không đổi.
Luật D1 được chốt trên DB G6; trên prodcopy hit@4 giảm nhỏ có ý nghĩa — cùng nguyên nhân §7.1 (bộ sinh bốc điểm đến độc lập với
khách, chọn món trong điểm đến theo pop). Theo dõi sau deploy bằng `recommendation_logs` như §7.7.

## 4. Gate `baseline_v6`

`regress --baseline baseline_v5-*`: không so được (exit 2) theo thiết kế (`configHash 8c717872 → 54b42809`). Ghi
`baseline_v6-<kind>-prodcopy-asof20261008.json`; `regress` lại chính run: exit 0, 4/4. Arm `engine` v5 → v6:

| split | recall@5 | recall@10 | recall@20 | ndcg@10 | catalog_coverage |
|---|---|---|---|---|---|
| llbo (4.023) | 0,6470 → 0,6470 | 0,7494 → 0,7494 | 0,8377 → 0,8377 | 0,5382 → 0,5382 | 0,830 → 0,830 |
| temporal (773) | 0,1216 → 0,1164 | 0,1475 → 0,1307 | 0,1721 → 0,1449 | 0,1059 → 0,1002 | 0,614 → 0,693 |
| nexttrip (1.835) | 0,0381 → 0,0289 | 0,0605 → 0,0420 | 0,0845 → 0,0545 | 0,0337 → 0,0252 | 0,692 → 0,777 |
| coldstart (5.233) | 0,8420 → 0,8418 | 0,9322 → 0,9320 | 0,9717 → 0,9715 | 0,6556 → 0,6554 | 0,868 → 0,868 |

LLBO không đổi (mọi khách LLBO có chuyến mở tại `as_of`). Trong run v6: `content_profile+mmr` ≡ `engine` (gương funnel nay gọi thẳng
hàm điểm engine + cap điểm đến) và `star_blend_a1` ≡ `content_profile` (`expect_equal_to` đạt, exit 0); nexttrip còn lệch 1 khách
ở nDCG giữa gương và engine — có sẵn từ v3 (ngày UTC trong `models/seeds.profile_for`).

## 5. Latency đầu-cuối (G1)

`http-latency --runs 6 --k 4` (bỏ lượt 1 → 300 mẫu / tập; guest 40 mẫu); `diagnostics.latencyMs` p50 / **p95** ms; xen kẽ TRƯỚC /
SAU, khởi động lại backend mỗi lượt (cổng 8010, `WEAVIATE_GRPC_PORT=55051`), máy không chạy job khác.

| Tập | TRƯỚC 1 | SAU 1 | TRƯỚC 2 | SAU 2 |
|---|---|---|---|---|
| strata | 64.0 / **82.1** | 62.0 / **81.0** | 64.0 / **80.0** | 64.0 / **81.0** |
| users60 | 59.0 / **83.1** | 59.5 / **81.0** | 59.0 / **81.0** | 59.0 / **78.1** |
| guest | 9.0 / **9.0** | 9.0 / **9.0** | 9.0 / **10.0** | 9.0 / **10.0** |

p95 theo `strategy` (ms; n sau khi bỏ lượt 1):

| Tập | strategy | TRƯỚC 1 | SAU 1 | TRƯỚC 2 | SAU 2 |
|---|---|---|---|---|---|
| strata | cold_start_content | 69.8 (25) | 61.6 (25) | 68.0 (25) | 65.0 (25) |
| strata | dormant | 83.3 (15) | 82.0 (15) | 76.3 (15) | 79.6 (15) |
| strata | long_term | 82.5 (230) | 81.0 (230) | 81.0 (230) | 82.0 (230) |
| strata | popular | 39.8 (5) | 38.6 (5) | 42.6 (5) | 37.2 (5) |
| strata | recent_activity | 65.8 (25) | 63.0 (25) | 67.4 (25) | 66.4 (25) |
| users60 | dormant | 84.6 (45) | 80.6 (45) | 80.8 (45) | 81.8 (45) |
| users60 | long_term | 84.0 (190) | 82.0 (190) | 82.0 (190) | 79.0 (190) |
| users60 | popular | 44.0 (60) | 43.0 (60) | 43.0 (60) | 44.0 (60) |
| users60 | recent_activity | 72.2 (5) | 67.6 (5) | 65.6 (5) | 73.4 (5) |

p95 tổng SAU ≤ TRƯỚC ở cả hai tập; theo `strategy` chênh lớn nhất +3,3 ms (`dormant` strata lượt 2) và +7,8 ms ở nhóm n = 5
(`recent_activity` users60) — trong mức trôi giữa hai lượt TRƯỚC. **Đạt G1.** Phần việc mới: một phép clip trên cos đã tính và một
bộ đếm điểm đến trong MMR, không thêm I/O.

**Parity HTTP:** SAU `parity --k 5 --vectors weaviate` **60/60** cả hai lượt; TRƯỚC 13/60 — dự kiến (parity so HTTP với
`OfflineEngine` của code SAU; khác biệt là chính tác dụng của [B] ở khách không có chuyến mở).

**Caveat hành vi:** với k = 4, một số khách không có chuyến mở nhận **3 món** (`items tối thiểu 3` ở SAU, TRƯỚC luôn 4) — cap
2 món / điểm đến loại món khi pool ứng viên dồn vào ít điểm đến. Đề xuất [B] không nói gì về lấp ô thiếu; nếu cần luôn đủ k món
thì phải có quyết định riêng (vd lấp phần còn lại bỏ cap).

## 6. Lệnh tái sinh

```bash
# parity (TRƯỚC = 603aac6, SAU = nhánh này): eval_oph --configs "B0,B2" trên TRƯỚC, --configs B0 trên SAU, rồi so list4 / list20
# D1–D5 G6: DATABASE_URL=…/vota_g6pref_v1, eval_oph --configs "B0,B2" --frozen-tag g6pref-v1-asof20261008 --scenarios between,noisy_paired,open
#           paired_ci --per-user g6.jsonl --compare "B0:B2" --boot 10000
python -m src.evaluation.recsys_bench.theme_study.calibrate --vec npy:<prefix> --as-of 2026-10-08T00:00:00+00:00 --seeds 99,7,2026 --out calibrate.json
# gate: như eval-2026-10-09-recsys-gate-v4-booked-first-dormant365.md §4, run-id …-v6, regress so baseline_v5-*, baseline --out baseline_v6-*
# latency: như report v5 §3, TRƯỚC = git worktree add --detach <dir> 603aac6
```
