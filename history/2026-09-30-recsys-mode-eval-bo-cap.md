# RecSys harness: mode eval bỏ cap 2 món / taxonomy (`max_per_vertical`), arm `engine_prod`

- Ngày: 2026-09-30
- Tác giả: tqanh123 / Claude Code
- Nhánh: bench/embed-search
- Trạng thái: hoàn thành
- Phạm vi: evaluation, backend, docs

## Mục tiêu

Bảng 4 arm 30/09 (`history/2026-09-30-recsys-baselines-most-popular.md`) cho thấy engine thua most_popular_in_destination
ở Recall@20 chỉ vì trả ≤ 9 món (cap `MAX_PER_VERTICAL = 2` + category exclusion, Issue I-5). Người dùng chốt: làm wrapper
`mode="eval"` để engine có đủ 20 món khi đánh giá (kế hoạch Day 3 B), production giữ nguyên. Phục vụ FR-REC-01..04,
test-plan §2.5, M5 lịch 10 ngày.

## File thay đổi

- `src/backend/app/domain/recommendation/profile.py` — sửa: `mmr_select(..., max_per_vertical=MAX_PER_VERTICAL)`; `None`
  = không giới hạn. Mặc định không đổi.
- `src/backend/app/application/recommendation/use_cases.py` — sửa: `RecommendForUser.max_per_vertical` (mặc định
  `MAX_PER_VERTICAL`) truyền vào `mmr_select`; `main.py` không đổi.
- `src/backend/tests/unit/domain/test_recommendation_mmr_cap.py` — thêm: cap mặc định 2 / None bỏ cap / cap 3.
- `src/evaluation/recsys_bench/engine.py` — sửa: `OfflineEngine(mode="eval" | "prod")`; eval → `max_per_vertical=None`.
- `src/evaluation/recsys_bench/arms.py` — sửa: `EngineArm.key` = `engine` (eval) | `engine_prod` (prod).
- `src/evaluation/recsys_bench/__main__.py` — sửa: `run --arm engine_prod`; lệnh `user` dùng mode prod (như production).
- `src/evaluation/recsys_bench/tests/test_engine_no_leak.py` — thêm: test eval ≥ prod về số món, prod ≤ 2 mỗi taxonomy.
- `docs/spec/bench/recsys-offline-eval.md` — sửa: §4.3, §4.4 (hai dòng engine, đọc số, lệnh), §7.
- `docs/plan/2026-09-30-plan-day3.md` — đổi tên/chuyển từ `docs/spec/bench/plan_day3.md` (AGENTS.md §7), thêm dòng
  "Phục vụ" và trỏ tới lịch ở `docs/plan/`.
- `docs/plan/2026-09-30-bench-search-recsys-3-ngay.md`, `docs/plan/2026-09-28-lich-10-ngay-3-engine.md` — sửa: số mới.

## Quyết định

- Bỏ cap chỉ qua tham số của use case (`max_per_vertical=None`), không thêm nhánh logic riêng: list eval và list
  production cùng một xếp hạng, chỉ khác điểm cắt — đo được đúng "cap làm mất bao nhiêu".
- Báo **cả hai** arm trong mọi bảng: `engine` (eval, k = 20) cho tiêu chí handbook §12, `engine_prod` cho "khách thật sự
  thấy gì" (top-5 có cap).
- Không đổi spec §4.7 hay production; lệch spec (2 / `parentProductId`) vs code (2 / taxonomy) ghi lại cho C (M6).

## Kiểm tra

- `pytest -q src/evaluation/recsys_bench/tests`: **31 passed**; backend `test_recommendation_mmr_cap.py` +
  `test_engines.py` + `test_recommendation_cdp_fallback.py`: **18 passed**.
- LLBO `2026-09-30-llbo-v2` (1.007 khách): engine (eval) Recall@5/10/20 0,669 / 0,753 / **0,851**, NDCG@10 **0,524**,
  coverage 0,583, cross-category 0,898, trả TB 15,2 món, p95 185 ms; engine_prod 0,572 / 0,591 / 0,591, NDCG 0,460 (= v1);
  mpd 0,635 / 0,389. **Tiêu chí M5 đạt** (thắng rõ mpd ở Recall@20 và NDCG@10; availability 100 %; coverage > 20 %).
- Temporal `2026-09-30-temporal-v2` (102 khách): engine (eval) Recall@20 0,196, NDCG@10 0,144; engine_prod 0,118 / 0,113;
  mpd 0,098 / 0,031.

## Còn lại / rủi ro

- Engine eval trả TB 15,2 món (không đủ 20 ở một số khách: hết ứng viên sau exclusion) — ghi nhận, chưa sửa.
- Số trên seed 2026-09-21 (máy A); muốn thống nhất với Day 1 (seed 09-23) thì seed lại và chạy lại.
