# PR-A RecSys: áp dụng [A] + [C] vào PRD, engine P2 + loại combo ↔ thành phần + ô khám phá, gate baseline_v3, latency SAU

- Ngày: 2026-10-09
- Tác giả: tqanh123 / Claude Code
- Nhánh: feat/recSys_update (PR đích `origin/release-mvp-v2`)
- Trạng thái: hoàn thành
- Phạm vi: backend, evaluation, docs
- Tiếp theo: `history/2026-10-09-recsys-g6-do-lai-tren-du-lieu-co-so-thich.md`, `history/2026-10-08-de-xuat-prd-recsys-o-kham-pha-combo-cong-thuc.md`
  (phần [A], [C] của entry đó hoàn tất ở đây; [B] vẫn chờ chốt G5b)

## Mục tiêu

Người dùng chốt 09/10: **G5a = chốt cả [A] và [C]**, **G2 chốt lại = (a)** (chấp nhận C3 với D1 trên hit@4). Theo AGENTS.md §8.3:
cập nhật PRD trước, rồi engine theo PRD mới — PR-A của `docs/plan/2026-10-08-recsys-trien-khai-theo-giai-doan.md` §3:
P2 (độ tin cậy chuyến), loại trừ sản phẩm đã mua + combo ↔ thành phần (FR-REC-02, AC-REC-02/03), ô khám phá khi có chuyến mở
(FR-REC-02), gate `baseline_v3`, latency đầu-cuối SAU (tiêu chí G1: Δp95 ≤ 50 ms). FR-REC-01, FR-REC-02, NFR-PERF-01.

## File thay đổi

PRD / đề xuất (bước 8.3–8.4):
- `docs/prd/requirements.md` — sửa: FR-REC-02 thêm câu ô khám phá ([A]) và câu không gợi lại món đã mua + combo ↔ thành phần
  ([C]); AC-REC-02 viết lại (bỏ "Hội An", thêm điều kiện combo / ô trống); AC-REC-03 mới.
- `docs/prd/update-archive/2026-10-08-recsys-loai-san-pham-da-mua-va-combo.md`, `…-recsys-o-kham-pha-khi-co-chuyen-mo.md` —
  đổi tên từ `docs/prd/update/`: trạng thái `đã áp dụng`, chốt bởi tqanh123 09/10.
- `docs/prd/update/2026-10-08-recsys-chuan-hoa-so-thich-giua-hai-chuyen.md` — sửa: trình chốt G5b với D1 trên hit@4 (G2 = (a)).
- `docs/spec/bench/recsys-bam-so-thich-quyet-dinh.md` — sửa: §7.7 chốt 09/10 (G2 = (a), G5a).
- `docs/plan/2026-10-08-recsys-trien-khai-theo-giai-doan.md` — sửa: bảng đề xuất, checklist G5a / PR-A / G2.

Engine (backend):
- `src/backend/app/application/ports/unit_index.py` — sửa: `combo_members` (field có default), `components_of` / `combos_with`
  theo search unit, `purchase_closure()` một bậc.
- `src/backend/app/infrastructure/vectors/postgres_store.py` — sửa: `_COMBO_QUERY` đọc thêm `item_product_id, confidence, source`
  (mã băm catalog đổi một lần → nạp lại đầy đủ; text / vector không đổi); `combo_members_of` (`COMBO_MEMBER_MIN_CONFIDENCE = 0.8`
  hoặc `source = 'manual'`); `CatalogUnits.combo_members` → `to_index`.
- `src/backend/app/domain/recommendation/profile.py` — sửa: `CAP_EXEMPT_EVENTS` (purchase / add_to_cart không bị cap lặp),
  `Trip.confidence`, `u_long` nhân confidence, `explain(..., long_term=)` phân rã theo confidence, `EXPLORE_TAXONOMIES`,
  `EXPLORE_MAX_PER_DESTINATION`, `ENGINE_RULES_VERSION = "2026-10-09-p2-combo-explore"`.
- `src/backend/app/application/recommendation/use_cases.py` — sửa: `bought_units(index, events)` (purchase thô theo search unit,
  kể cả món chưa có vector, + closure combo) thay `profile.bought_units` ở mask; hàm `explore_fill()` dùng chung; `RecommendForUser`
  có `explore_fill` / `explore_candidate_k`, lấp ô trống sau MMR khi có chuyến mở, `diagnostics.exploreFilled`; `because[]` ô
  khám phá theo u_long.
- `src/backend/app/core/config.py` — sửa: `recommend_explore_fill: bool = True` (`RECOMMEND_EXPLORE_FILL`).
- `src/backend/app/core/logging_config.py` — sửa: sự kiện `recsys.explore_fill` (`filled`).
- `src/backend/app/main.py` — sửa: truyền `explore_fill=settings.recommend_explore_fill`.
- `src/backend/tests/fakes/in_memory_vector_store.py` — sửa: đọc đủ dòng `combo_items.jsonl`, dựng `combo_members` như adapter thật.
- `src/backend/tests/unit/application/test_recommendation_combo_exclusion.py` — thêm: 9 test (mapping tin cậy, closure, mask,
  AC-REC-02/03, mọi lần mua, mua món chưa có vector).
- `src/backend/tests/unit/application/test_recommendation_explore_fill.py` — thêm: 6 test (chỉ lấp ô trống, 1 món / điểm đến,
  không gọi thêm near_vector khi đủ k, closure combo, cờ tắt = list cũ, không chuyến mở, request khoá destination).
- `src/backend/tests/unit/domain/test_recommendation_profile_confidence.py` — thêm: 4 test P2.
- `src/backend/tests/unit/domain/test_recommendation_trip_open.py` — sửa: nhãn ENGINE_RULES_VERSION; purchase thứ 4 vào vector.
- `src/backend/tests/unit/application/test_engines.py` — sửa: AC-REC-02 chỉ đòi ≥ 1 món có because[] (FakeEmbedder băm bằng
  `hash()` ngẫu nhiên theo tiến trình nên test cũ 6/6 lần chạy đơn lẻ đều fail trước cả thay đổi này).

Harness bench (gương engine):
- `src/evaluation/recsys_bench/models/funnel.py` — sửa: `engine_mask` / `raw_mask` nhận `bought`; `CtxCache` dùng `bought_units`;
  `AlgoArm` lấp ô khám phá bằng chính `explore_fill` ở cấu hình gương engine (funnel + pool engine + mmr), `exploreFilled` vào
  `mean_meta`.
- `src/evaluation/recsys_bench/models/because.py` — sửa: nhánh u_long nhân confidence (như `explain`).
- `src/evaluation/recsys_bench/ceiling.py` — sửa: `bought_units` qua `purchase_closure`.
- `src/evaluation/recsys_bench/splits.py` — sửa: meta `comboRelatedTarget` (fingerprint split không đổi).
- `src/evaluation/recsys_bench/arms.py` — sửa: `engine_nommr` tắt ô khám phá (không phải pool); `exploreFilled` vào meta arm engine.
- `src/evaluation/recsys_bench/engine.py` — sửa: `OfflineEngine(explore_fill=)`, `engine_config.exploreFill`.
- `src/evaluation/recsys_bench/theme_study/profile_variants.py` — sửa: bản viết lại khớp production mới (confidence mặc định bật,
  event mạnh không bị cap); thêm `P0_legacy`; `P2_confidence` = `P0_prod`.
- `src/evaluation/recsys_bench/theme_study/eval_slots.py`, `theme_exp.py` — sửa: tập đã mua qua `purchase_closure`.
- `src/evaluation/recsys_bench/tests/test_profile_variants.py`, `test_models_funnel_regression.py`, `test_arms_metrics.py` — sửa:
  bỏ xfail production / P2; G2 so phần pool (ô khám phá không thuộc pool).
- `src/evaluation/recsys_bench/frozen/baseline_v3-{llbo,temporal,nexttrip,coldstart}-prodcopy-asof20261008.json` — thêm.
- `src/evaluation/reports/eval-2026-10-09-recsys-pr-a-gate-v3-latency-sau.md` — thêm: gate + latency SAU.

Spec:
- `docs/spec/hop-dong-tich-hop-search-recommendation.md` — sửa: §4.3 (P2), §4.5 (luật đã mua + combo), §4.7 (ô khám phá),
  §9 tiêu chí 27–28.
- `docs/spec/PRODUCT_SCHEMA.md` — sửa: §5 luật 5 ghi trạng thái (loại vertical theo combo chưa cài; luật sản phẩm đang chạy).
- `history/2026-10-09-recsys-pr-a-p2-loai-combo-o-kham-pha.md` — thêm: entry này.

## Quyết định

- P2 ship đúng bản đã đo (`confidence` tính trên event sau cap, không suy giảm) **cộng** phần còn lại của P1 (purchase / cart
  không bị cap lặp — `tong-hop.md` §3.D, không đổi số); không đổi thứ tự giữ event yếu (vẫn 3 event cũ nhất).
- Tập đã mua tính từ **event thô** qua `idx.resolve` chứ không từ `profile.bought_units` (chỉ gồm event có vector) — đóng khe "mua
  món chưa index vẫn được gợi lại". Ngưỡng dòng combo tin cậy theo [C]: `item_product_id` + (`confidence ≥ 0,8` ∨ `manual`).
- Ô khám phá: một `near_vector(u_long)` chỉ khi còn ô trống; `strategy` / `nextVertical` tính trên món tại X; `score` của món
  khám phá = cos(u_long, v) (không cùng thang với `final` của món tại X — ghi rõ ở spec §4.7); contract OpenAPI không đổi
  (`diagnostics` là object mở — `exploreFilled` thêm vào không phá schema; không chạy `validate_contract.py` vì không sửa
  `src/shared/contracts`).
- Harness: arm `content_profile+mmr` gương cả ô khám phá (cùng hàm) để gate G1 "= engine" còn ý nghĩa; `engine_nommr` và các
  arm không MMR không lấp (pool ≠ ô khám phá). `exploreFilled` trung bình ghi vào summary để tách phần ô B.
- `profile_variants` đổi mặc định `confidence=True` để `parity()` của `eval_profile` vẫn so với production hiện hành; lệnh cũ
  dùng `P2_confidence` vẫn chạy (= production), `P0_legacy` giữ công thức cũ cho ablation.
- Không sửa `src/evaluation/reports/*` và `history/*` cũ đang trỏ `docs/prd/update/...` (bản ghi theo thời điểm).

## Kiểm tra

- `pytest src/backend/tests/unit src/backend/tests/architecture src/evaluation/recsys_bench/tests`: **1.934 passed, 5 skipped**
  (trước PR: 1.749 + 160).
- Gate (`eval-2026-10-09-recsys-pr-a-gate-v3-latency-sau.md`): 4 split prodcopy, `regress` vs `baseline_v2` exit 2 (NotComparable,
  `configHash c893694f → 3c6ca566`) theo thiết kế; `baseline_v3` ghi 4 kind, `regress` lại exit 0. Chênh so run v2: recall ≤ 0,004
  tuyệt đối ở mọi split (llbo recall@10 −0,0017, temporal recall@20 −0,0039, nexttrip recall@10 +0,0016, coldstart ≈ 0);
  `engine` = `content_profile+mmr` ở mọi chỉ số; `explore_filled` llbo 1,48 món / khách (k = 20).
- Latency đầu-cuối SAU (cùng report): xen kẽ TRƯỚC (worktree `2f3b593`) / SAU × 2; p95 server strata 87 / 84 / 87 / 91 ms,
  users60 85 / 95 / 92 / 90 ms; Δp95 tối đa +6,5 ms tổng, ≤ +10 ms theo strategy (n = 5) — **đạt G1 ≤ 50 ms**. Parity offline ↔
  HTTP 60/60 ở cả hai tập trên engine mới.

## Còn lại / rủi ro

- G5b: [B] đã viết lại, chờ người dùng chốt → PR-B (F14c + destCap2).
- Trên staging / production, lần nạp catalog đầu sau deploy kéo lại toàn bộ (mã băm combo đổi) — một lần, như mọi lần đổi query.
- Weaviate Cloud khác region: ô khám phá thêm một lượt near_vector chỉ khi còn ô trống; nếu p95 vượt ngưỡng sau deploy →
  `RECOMMEND_EXPLORE_FILL=false` không cần redeploy.
- `test_ac_rec_02` của backend vẫn phụ thuộc vector giả ngẫu nhiên (`hash()`); nếu muốn chặt hơn cần FakeEmbedder tất định (md5)
  — việc riêng, không làm ở đây.
