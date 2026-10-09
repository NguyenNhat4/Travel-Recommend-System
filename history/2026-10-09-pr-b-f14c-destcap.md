# PR-B: áp dụng đề xuất [B] — F14c + tối đa 2 món / điểm đến khi không có chuyến mở

- Ngày: 2026-10-09
- Tác giả: tqanh123 / Claude Code
- Nhánh: feat/recSys_update-2
- Trạng thái: hoàn thành (code + đo); deploy PR-B chưa làm
- Phạm vi: backend, evaluation, docs

## Mục tiêu

Người dùng chốt G5b (đề xuất [B]) ngày 09/10 sau khi G2 chốt lại = (a). Áp theo AGENTS.md §8: PRD → engine → spec → test → parity / gate / latency, theo PR-B của `docs/plan/2026-10-08-recsys-trien-khai-theo-giai-doan.md`. FR-REC-04, FR-REC-02, NFR-PERF-01.

## File thay đổi

- `docs/prd/requirements.md` — sửa: FR-REC-04 (chuẩn hoá cos khi không có chuyến mở, tối đa 2 món / điểm đến), câu cuối FR-REC-02
- `docs/prd/update/2026-10-08-recsys-chuan-hoa-so-thich-giua-hai-chuyen.md` → `docs/prd/update-archive/` — đổi tên (git mv), trạng thái "đã áp dụng", chốt bởi tqanh123 09/10
- `src/backend/app/domain/recommendation/profile.py` — sửa: `SEMANTIC_Q_LOW/HIGH`, `SEMANTIC_CALIBRATION_MODEL_VERSION`, `W_NEXT_*`, `MAX_PER_DESTINATION`, `calibration_applies`, `calibrated_similarity`, `score_candidates(..., next_trip_scoring)`, `mmr_select(..., destination, max_per_destination)`; `ENGINE_RULES_VERSION = "2026-10-09-next-trip-f14c"`
- `src/backend/app/application/recommendation/use_cases.py` — sửa: F14c khi tag model khớp, ngược lại công thức cũ + WARNING một lần; cap điểm đến tại thời điểm MMR, không áp khi request khoá `destination`
- `src/backend/app/core/config.py`, `src/backend/app/main.py` — sửa: `RECOMMEND_NEXT_TRIP_SCORING`, `RECOMMEND_MAX_PER_DESTINATION` (rollback không redeploy)
- `src/backend/tests/unit/domain/test_recommendation_next_trip.py`, `src/backend/tests/unit/application/test_recommendation_next_trip_use_case.py` — thêm: công thức, tag, cap, luật điểm xuất phát sau F14c, fallback + WARNING, khoá điểm đến
- `src/backend/tests/unit/domain/test_recommendation_trip_open.py` — sửa: version mới
- `src/backend/tests/unit/application/test_recommendation_combo_exclusion.py` — sửa: tắt cap trong fixture (catalog giả rất nhỏ; test chỉ kiểm luật loại combo)
- `src/evaluation/recsys_bench/engine.py` — sửa: `OfflineEngine(next_trip_scoring, max_per_destination)`, ghi vào `engine_config`
- `src/evaluation/recsys_bench/arms.py` — sửa: `EngineNoMmrArm._by_score` nhận tham số cap mới (bỏ qua — arm trả nguyên pool)
- `src/evaluation/recsys_bench/models/{base,content,funnel,star}.py` — sửa: gương funnel gọi thẳng hàm điểm engine (`content.engine_score`: điểm xuất phát [F] + F14c), cap điểm đến ở cấu hình gương engine; `star_blend` = engine + phần pha cộng tác (a = 1 trùng bit `content_profile`)
- `src/evaluation/recsys_bench/theme_study/{oph_scorer,step2_scorers,eval_formula,dest_diversity,registry}.py` — sửa: nhận `next_trip_scoring` / tham số cap mới; F14c của harness dạng ba hạng như [B]; token `noNext`
- `src/evaluation/recsys_bench/theme_study/calibrate.py` — thêm: CLI calibrate lại ngưỡng khi đổi model / text builder
- `src/evaluation/recsys_bench/frozen/baseline_v6-{llbo,temporal,nexttrip,coldstart}-prodcopy-asof20261008.json` — thêm
- `src/evaluation/recsys_bench/theme_study/results/2026-10-09-pr-b/` — thêm: golden / after JSON tổng hợp, parity, CI prodcopy + G6, calibrate, `SHA256SUMS`
- `src/evaluation/reports/eval-2026-10-09-recsys-pr-b-f14c-destcap.md` — thêm: report
- `docs/spec/hop-dong-tich-hop-search-recommendation.md` — sửa: §4.7 công thức không chuyến mở, guard, cap, rollback
- `docs/spec/bench/recsys-bam-so-thich-quyet-dinh.md` — sửa: thêm §9
- `docs/plan/2026-10-08-recsys-trien-khai-theo-giai-doan.md` — sửa: trạng thái + checklist G5b / PR-B

## Quyết định

- Engine cài đúng C3 của harness: parity nDiscordant = 0 trên toàn bộ khách (llbo 4.023, temporal 773, nexttrip 1.835, coldstart 5.233, 1.392 khách giả lập). F14c viết dạng ba hạng `0,50·s + 0,35·pop + 0,15·s` như [B]; harness đổi theo cho khớp từng bit.
- Luật điểm xuất phát chuyến bay ([F], FR-REC-04) vẫn áp sau F14c (route sai điểm xuất phát bị loại khi không có chuyến mở).
- Đo lại tiêu chí G2 trên mốc mới (production đã có chuỗi O): DB G6 D1 hit@4 −0,0026 [−0,0077, +0,0026] đạt, D2/D3/D4 đạt; prodcopy hit@4 −0,0065 (CI không chứa 0) — ghi trong report, D1 chốt trên DB G6 theo §7.7.
- Ngưỡng Q giữ 0,8529 / 0,9387: `calibrate` seed 99 tái lập đúng, seed 7 / 2026 lệch ≤ 0,002.
- Gương funnel trước đây tự chép công thức engine (nên lệch sau [F] mà test fixture không bắt được); nay gọi thẳng `score_candidates`.

## Kiểm tra

- `PYTHONHASHSEED=0 PYTHONUTF8=1 pytest src/backend/tests src/evaluation/recsys_bench/tests`: 2079 passed, 39 skipped.
- Gate v6 4 kind: run exit 0 (`expect_equal_to` star_blend_a1 ≡ content_profile đạt; content_profile+mmr ≡ engine); `regress` vs v5 exit 2 (không so được, theo thiết kế); `regress` vs v6 exit 0 4/4.
- Latency đầu-cuối 4 lượt xen kẽ: p95 SAU ≤ TRƯỚC; chênh theo strategy ≤ +3,3 ms (n ≥ 15) → đạt G1; parity HTTP SAU 60/60.

## Còn lại / rủi ro

- Với k = 4 một số khách không có chuyến mở nhận 3 món (cap 2 / điểm đến) — [B] không nói về lấp ô thiếu; cần người dùng quyết nếu muốn luôn đủ k.
- Deploy PR-A + chuỗi O + PR-B lên `release-mvp-v2`; theo dõi `recommendation_logs` cho chi phí nexttrip (§7.7).
- Lệch 1 khách (ngày UTC) giữa gương funnel và engine ở nexttrip có sẵn từ v3.
