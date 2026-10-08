# RecSys bám sở thích — triển khai theo giai đoạn (sau khi chốt gate 08/10)

- Ngày: 2026-10-08
- Người lập: tqanh123 (soạn cùng Claude Code)
- Phục vụ: FR-REC-01, FR-REC-02, FR-REC-04, AC-REC-01/02 (`docs/prd/requirements.md` §1.3, §3), NFR-PERF-01
- Tiếp theo: `docs/plan/2026-10-08-ban-giao-recsys-bam-so-thich.md` (WP0–WP4 đã xong) và
  `docs/spec/bench/recsys-bam-so-thich-quyet-dinh.md` §7 (điều tra G2)
- Trạng thái: đang làm. Gate còn mở: G5a (đề xuất [A], [C]), G6-tham-số, G2 chốt lại, G5b (đề xuất [B])

## 1. Những gì đã chốt (08/10)

| Gate | Chốt |
|---|---|
| G1 | Tiêu chí nghiệm thu: temporal h@20 giảm ≤ 0,04 (điểm ước lượng); LLBO h@4 CI chứa 0; theme ≥ +0,15; `open` không đổi; **latency**: Δp95 `diagnostics.latencyMs` của `/recommendations` ≤ 50 ms, đo đầu-cuối trên backend local + Weaviate local, tổng và theo `strategy` |
| G2 | **Làm theo giai đoạn**: ship phần miễn phí trước (P2 + ô B + loại combo) → G6 đổi bộ sinh event cho có sở thích, đo lại → chốt lại G2 cho F14c + destCap2 trên số mới |
| G3 | Công thức khi không có chuyến mở: **P2 + F14c** (pop 0,35) — kèm **destCap2** (giới hạn 2 món / điểm đến) theo điều tra §7.3 |
| G4 | **Có** làm ô khám phá B (chỉ lấp ô trống) |
| Loại combo | Mua sản phẩm → không gợi combo chứa nó; mua combo → không gợi thành phần; **mọi lần mua** (như `bought_units`); sửa PRD |
| WP0.6 | PR đích **`release-mvp-v2`** (`origin/release-mvp-v2`, không dùng nhánh local đã lệch). Đưa W 0,7/0,15/0,15 lên `main` là PR riêng, ngoài plan này |

## 2. Lệch PRD → đề xuất (AGENTS.md §8)

| Mã | File `docs/prd/update/` | Lệch gì | Chốt |
|---|---|---|---|
| [C] | `2026-10-08-recsys-loai-san-pham-da-mua-va-combo.md` | FR-REC-02: không gợi lại món đã mua; combo ↔ thành phần cùng lần mua; AC-REC-03 mới; sửa câu AC-REC-02 (bỏ "Hội An") | G5a |
| [A] | `2026-10-08-recsys-o-kham-pha-khi-co-chuyen-mo.md` (đổi tên từ `...bam-so-thich-va-o-kham-pha.md`) | FR-REC-02: ô khám phá khi có chuyến mở | G5a |
| [B] | `2026-10-08-recsys-chuan-hoa-so-thich-giua-hai-chuyen.md` | FR-REC-04 + FR-REC-02: F14c + destCap2 khi không có chuyến mở | **sau G6 + G2** → G5b |

Không phải lệch PRD (không cần đề xuất): P2 (PRD chỉ nói "dùng lịch sử dài hạn"), G6 (PRD không mô tả bộ sinh event; tiền lệ
eval-v2 / append-v1 là profile opt-in + `MOCK_DATA_SPEC` §4.x + history, demo không đổi byte), đo latency, coldstart, AC,
baseline gate.

## 3. Các luồng việc

```
B0 sửa 2 commit (xong) ─► B1 merge release + plan này ─► B2 ba đề xuất ─┬─► [G5a] ─► PR-A ─► latency SAU ─► deploy
Lane A (không lệch PRD): A1 latency TRƯỚC · A2 coldstart + AC-REC-01/02 + ô B theo cos(u_long) · A3 split prodcopy + baseline_v2 ┘
Lane B: B1 profile seed g6-pref-v1 · B2 DB nghiên cứu + đo lại ─► [G2 chốt lại] ─► [G5b] ─► PR-B ─► deploy
```

### Lane A — số phải có trước mọi PR

- **A1 latency đầu-cuối TRƯỚC:** collection Weaviate local mới `ProductE5SmallProdcopy` nạp từ `.npy` của gói bàn giao
  (không dùng `ProductBench_e5_small`: chỉ 3.183 / 3.991 unit); backend `.venv` chạy trên `vota_prodcopy`
  (`SEARCH_PREWARM=false`, `INTERNAL_API_ENABLED=true`, `X-Service-Token`); `recsys_bench parity` 60/60; `http-latency --users`
  k = 4, p50/p95 tổng và theo `strategy`. Số này tái dùng cho mọi lượt SAU.
- **A2:** thêm `coldstart` vào `theme_study/eval_profile.py` (+ `destHit@20`); AC-REC-01 bằng `recsys_bench user --id VP0000001`
  ở `--as-of 2026-09-21` (chuyến mở) và `2026-10-08` (chuyến NT của P1 đã kết thúc 05/10); AC-REC-02 bằng lịch sử tổng hợp
  (không ghi DB) + unit test fakes; đo lại ô B với `eval_slots --how ulong` (lượt 08/10 dùng `destsim`).
- **A3:** đóng băng split prodcopy `asof20261008` (llbo / temporal / nexttrip / coldstart) và ghi `baseline_v2` **trước** khi
  đổi engine — `baseline_v1` là Cohere-era (`configHash b0aee886`) nên `make recsys-regress` đã NotComparable.

### Lane B — G6

- Profile `g6-pref-v1` trong `src/data_collection/seed/config.py` (`THEME_PREF_RATE` 0,8; 30 % khách không sở thích; mix theo
  khối lượng bookable; `DEST_THEMES` chép từ `theme_exp.THEME`; 7 điểm đến chưa nhãn = không chủ đề). Nhãn chủ đề **ẩn** (RNG
  stream `{seed}|theme|{user}`, sidecar JSON, không thêm cột). Demo không đổi byte (test). `append_histories --profile`.
- DB nghiên cứu riêng: `createdb -T vota_prodcopy vota_g6pref_v1` → TRUNCATE chỉ `cdp.events, cdp.profiles` → `append_histories
  prepare/apply`. **Không** `seed --reset` (mất catalog). Split đóng băng riêng `-g6pref-v1-`; không ghi baseline gate trên DB này.
- Đo lại C0 production · C1 P2 · C2 P2+F14c · C3 C2+destCap2, 4 split + `--syn-target` + ô B; ghim q = 0,8529/0,9387; CI ghép cặp.
  Luật đóng G2 đề nghị: D1 nexttrip h@20 cận dưới CI ≥ −0,01 · D2 nexttrip `destHit@20` cận dưới > 0 · D3 LLBO/coldstart CI
  chứa 0 · D4 temporal ≥ −0,04 · D5 `tgtHit@20` / `nextDestHit@20` cận dưới > 0. Người dùng chốt lại G2.

### PR-A (sau G5a) — P2 + loại combo + ô B

1. Combo plumbing: `postgres_store._COMBO_QUERY` thêm `item_product_id, confidence, source`; `UnitIndex.combo_members` (field có
   default) → `components_of` / `combos_with` / `purchase_closure()` (một bậc, theo search unit).
2. Loại combo ON: `use_cases.py` tính tập đã mua từ raw event qua `idx.resolve` rồi `purchase_closure`; gương harness
   (`models/funnel.py`, `ceiling.py`, `splits._meta_for_targets`, `theme_exp.explore`, `eval_slots`).
3. P2: `CAP_EXEMPT_EVENTS`, `Trip.confidence`, `u_long` nhân confidence, `explain()` theo; bỏ xfail ở `test_profile_variants`.
4. Ô B: `_explore_fill` sau `mmr_select`, một `near_vector(u_long)` chỉ khi `len(chosen) < k`; `Settings.recommend_explore_fill`
   làm công tắc; contract không đổi.
5. `ENGINE_RULES_VERSION` bump; spec §4.3/§4.4/§4.5/§4.7 + §9; unit test ≥ 80 % domain/application; gate → `baseline_v3`;
   **latency SAU** (xen kẽ trước/sau); nếu ô B vỡ ngưỡng → ship với `RECOMMEND_EXPLORE_FILL=false`; `git mv` [A], [C] →
   `update-archive/`; history. Merge → auto deploy staging (`backend-ci-cd.yml`); kiểm sau deploy theo §5 của kế hoạch gốc.

### PR-B (sau G2 chốt lại + G5b) — F14c + destCap2

`SEMANTIC_Q_LOW/Q_HIGH`, `SEMANTIC_CALIBRATION_MODEL_VERSION`, `W_NEXT_*`, `MAX_PER_DESTINATION`; `score_candidates(...,
next_trip_scoring)`, `mmr_select(..., destination, max_per_destination)` (truyền `space.destination` tại thời điểm MMR; không áp khi
request khoá `destination`); fallback về production + WARNING khi `model_version` lệch tag; `Settings` để rollback bằng env;
test tag == `f"{embed_model}:{TEXT_BUILDER_VERSION}"`; engine thật phải tái sinh số nghiên cứu (LLBO h@4 0,5324, nexttrip h@20
0,0469, nextDestHit 0,4181); gate → `baseline_v4`; latency SAU; archive [B]; deploy.

## 4. Việc người dùng chốt

- **G5a:** [A] (whitelist hotel/attraction/combo; không loại taxonomy đã mua — theo bản đã đo) và [C] (dòng mapping tin cậy
  `confidence ≥ 0,8` hoặc `source = 'manual'`; sửa câu AC-REC-02; "combo kéo theo hotel" ngoài phạm vi).
- **G6 tham số** khi review lane B. **Luật đóng G2** D1–D5. **G2 chốt lại** → **G5b**.

## 5. Checklist

- [x] B0 sửa 2 commit (`7b0fcde`, `4dd271e`; tree không đổi; force-with-lease 08/10)
- [x] B1 merge `origin/release-mvp-v2` (`d8a86ac`) vào feat — sạch, không trùng file
- [ ] B2 ba đề xuất viết xong, `chờ chốt`
- [ ] A1 latency TRƯỚC · [ ] A2 coldstart + AC + ô B ulong · [ ] A3 split prodcopy + baseline_v2
- [ ] B1 profile g6-pref-v1 · [ ] B2 DB G6 + đo lại + report
- [ ] G5a · [ ] PR-A · [ ] latency SAU · [ ] deploy PR-A
- [ ] G2 chốt lại · [ ] G5b · [ ] PR-B · [ ] deploy PR-B
