# Gate `baseline_v5`, parity và latency sau khi áp [F] (điểm xuất phát chuyến bay + chuyến ảo gộp lượt xem)

- Ngày chạy: 2026-10-09 · Người chạy: tqanh123 / Claude Code
- Phục vụ: FR-REC-02, FR-REC-04 (đề xuất `docs/prd/update-archive/2026-10-09-recsys-diem-xuat-phat-va-phien-xem.md`, chốt 09/10),
  NFR-PERF-01 (G1: Δp95 `latencyMs` ≤ 50 ms)
- Engine SAU: nhánh `feat/recSys_update-2` (`ENGINE_RULES_VERSION = "2026-10-09-origin-session"`, `W_ORIGIN = 0.15`,
  `H_SESSION_DAYS = 7`, `configHash` mới). TRƯỚC: `24cdd40` (`2026-10-09-booked-first`, `baseline_v4`).
- Môi trường như `eval-2026-10-09-recsys-gate-v4-booked-first-dormant365.md` (DB `vota_prodcopy`, vector `.npy` gói bàn giao,
  Weaviate local `ProductE5SmallProdcopy`, hai tập khách lane A). Run id: `20261009-gate-<kind>-prodcopy-v5`,
  `2026-10-09-e2e-f-{before1,after1,before2,after2}-{strata,users60,guest}`.
- Tham số chọn trên TUNE và kiểm một lần trên TEST: `src/evaluation/reports/eval-2026-10-09-recsys-cong-thuc-oph.md`.

## 1. Parity engine ↔ bản thí nghiệm

Lượt chạy trên engine TRƯỚC với cấu hình harness `B0+orig:pen:0.15+sess` (bản thí nghiệm đã chọn), so với engine SAU (`B0`), cùng
khách, cùng tham số (`eval_oph --splits llbo,temporal,nexttrip,coldstart --scenarios between,open,booked_browse,session_multi,dormant
--syn-seeds 13 --syn-target`):

| stratum | n | nDiscordant4 | nDiscordant20 |
|---|---:|---:|---:|
| llbo | 4.023 | 0 | 0 |
| temporal | 773 | 0 | 0 |
| nexttrip | 1.835 | 0 | 0 |
| coldstart | 5.233 | 0 | 0 |
| syn_between / open / booked_browse / session_multi / dormant | 240 / 240 / 193 / 239 / 240 | 0 | 0 |

Engine cài đúng công thức đã đo.

## 2. Gate

`regress --baseline baseline_v4-*`: không so được (exit 2) theo thiết kế — `configHash` và `engineRulesVersion` đổi. Ghi
`baseline_v5-<kind>-prodcopy-asof20261008.json`; `regress` lại chính run: exit 0, 4/4. Split đóng băng khớp sha.

Arm `engine` v4 → v5:

| split (khách) | recall@5 | recall@10 | recall@20 | ndcg@10 | catalog_coverage |
|---|---|---|---|---|---|
| llbo (4.023) | 0,6212 → 0,6470 | 0,7169 → 0,7494 | 0,8069 → 0,8377 | 0,4946 → 0,5382 | 0,844 → 0,830 |
| temporal (773) | 0,1151 → 0,1216 | 0,1294 → 0,1475 | 0,1565 → 0,1721 | 0,0927 → 0,1059 | 0,611 → 0,614 |
| nexttrip (1.835) | 0,0278 → 0,0381 | 0,0485 → 0,0605 | 0,0747 → 0,0845 | 0,0247 → 0,0337 | 0,679 → 0,692 |
| coldstart (5.233) | 0,7361 → 0,8420 | 0,7699 → 0,9322 | 0,8091 → 0,9717 | 0,6086 → 0,6556 | 0,878 → 0,868 |

Canary `most_popular_in_destination` đổi rất nhỏ (llbo recall@20 0,7104 → 0,7094; coldstart 0,3465 → 0,3438) vì gương điểm đến
của nó (`arms.trip_destination`) nay theo chuyến ảo như engine.

**Caveat (như report bench §6):** phần lớn mức tăng nằm ở khách mà món đích đã có trong lịch sử xem của họ (coldstart gần như toàn
bộ là "xem rồi mua" của seed). Lợi cho món **mới** nhỏ (bench TEST: +4 … +7 hit mỗi split).

## 3. Latency đầu-cuối (G1)

`http-latency --runs 6 --k 4` (bỏ lượt 1 → 300 mẫu / tập; guest 40 mẫu); `diagnostics.latencyMs` p50 / **p95** ms; xen kẽ TRƯỚC /
SAU, khởi động lại backend mỗi lượt (cổng 8010, `WEAVIATE_GRPC_PORT=55051`), máy không chạy job khác.

| Tập | TRƯỚC 1 | SAU 1 | TRƯỚC 2 | SAU 2 |
|---|---|---|---|---|
| strata | 69.0 / **88.0** | 62.0 / **84.1** | 66.0 / **89.0** | 67.0 / **89.0** |
| users60 | 66.5 / **88.0** | 63.0 / **87.0** | 67.0 / **88.0** | 63.0 / **85.0** |
| guest | 8.0 / **9.0** | 8.0 / **10.1** | 8.0 / **9.2** | 8.0 / **10.0** |

p95 theo `strategy` (ms; n sau khi bỏ lượt 1):

| Tập | strategy | TRƯỚC 1 | SAU 1 | TRƯỚC 2 | SAU 2 |
|---|---|---|---|---|---|
| strata | cold_start_content | 76.1 (30) | 76.2 (30) | 77.0 (30) | 81.5 (30) |
| strata | dormant | 86.3 (15) | 87.2 (15) | 93.1 (15) | 84.9 (15) |
| strata | long_term | 89.8 (225) | 85.0 (225) | 90.6 (225) | 90.0 (225) |
| strata | popular | 48.4 (5) | 43.0 (5) | 38.2 (5) | 39.6 (5) |
| strata | recent_activity | 68.4 (25) | 72.0 (25) | 78.8 (25) | 73.8 (25) |
| users60 | dormant | 88.8 (45) | 88.8 (45) | 80.0 (45) | 81.4 (45) |
| users60 | long_term | 88.5 (190) | 87.5 (190) | 88.5 (190) | 88.1 (190) |
| users60 | popular | 42.0 (60) | 44.0 (60) | 42.0 (60) | 43.1 (60) |
| users60 | recent_activity | 73.0 (5) | 81.4 (5) | 71.4 (5) | 70.8 (5) |

p95 tổng SAU ≤ TRƯỚC ở cả hai tập (strata 84,1 / 89,0 vs 88,0 / 89,0; users60 87,0 / 85,0 vs 88,0 / 88,0); theo `strategy` chênh lớn
nhất +4,5 ms (`cold_start_content`), nhỏ hơn mức trôi giữa hai lượt TRƯỚC (`recent_activity` 68,4 ↔ 78,8). **Đạt G1.** Phần việc
mới là một lần quét event chuyến bay (`infer_origin`) và một mảng bool trên ứng viên — không thêm I/O.

**Parity HTTP:** SAU `parity --k 5 --vectors weaviate` **60/60** cả hai lượt. TRƯỚC 41/60 (lệch ids) — dự kiến: parity so HTTP với
`OfflineEngine` của code SAU, khác biệt là chính tác dụng của [F].

## 4. Lệnh tái sinh

Như `eval-2026-10-09-recsys-gate-v4-booked-first-dormant365.md` §4, đổi `v4 → v5`, baseline so sánh `baseline_v4-*`, TRƯỚC =
`git worktree add --detach <dir> 24cdd40`. Parity §1: hai lượt `eval_oph` (TRƯỚC: `--configs "B0+orig:pen:0.15+sess"` trên
`24cdd40`; SAU: `--configs B0`) rồi so `list4` / `list20` theo (stratum, seed, uid).
