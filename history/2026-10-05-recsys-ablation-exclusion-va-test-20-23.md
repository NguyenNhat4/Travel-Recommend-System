# RecSys: ablation category exclusion (Day 7) + test tiêu chí 20–23 (Day 4) + cập nhật tick lịch 10 ngày

- Ngày: 2026-10-05
- Tác giả: Pham Nguyen Dang Khoi / Claude Code
- Nhánh: `bench_search_recomSys`
- Trạng thái: hoàn thành (chưa commit theo yêu cầu người dùng)
- Phạm vi: evaluation, backend (test), docs
- Phục vụ: FR-REC-02, FR-REC-01, M7 lịch 10 ngày; tiêu chí 20–23 `docs/spec/hop-dong-tich-hop-search-recommendation.md`

## Mục tiêu

Người dùng chọn làm tiếp (không cần VM): ablation recsys exclusion on/off, test tiêu chí 20–23, `stageMs` cho `/recommendations`; cập nhật tick
lịch 10 ngày cho việc đã xong, chưa commit.

## File thay đổi

- `src/evaluation/recsys_bench/models/funnel.py` — sửa: mode `noexcl` (mask engine không loại taxonomy đã mua; giữ khoá điểm đến, bỏ món đã mua);
  `engine_mask(..., exclude_taxonomy=)`.
- `src/evaluation/recsys_bench/__main__.py` — sửa: help `--mode` nêu `noexcl`.
- `src/backend/tests/unit/domain/test_recommendation_criteria_20_23.py` — thêm: 4 test tiêu chí 20–23 ở tầng domain.
- `src/evaluation/reports/eval-2026-10-05-recsys-ablation-exclusion.md` — thêm: report ablation.
- `docs/plan/2026-09-28-lich-10-ngay-3-engine.md` — sửa: tick Day 4 C (tiêu chí 20–23), Day 7 ablation search + recsys; ghi chú Day 5 A (S0–S9 không
  làm), Day 7 latency, Day 8 gate F1 / P.
- `history/2026-10-05-recsys-ablation-exclusion-va-test-20-23.md` — thêm: entry này.

## Quyết định

- Exclusion gắn cứng trong `RecommendForUser` (không phải hằng `--override`) → ablation qua funnel của harness, không sửa engine production.
- Tiêu chí 22 (`diagnostics.userVectorNorm`) kiểm ở domain; response chưa có trường này — thêm là đổi contract, chưa làm.
- `stageMs` cho `/recommendations`: dừng hỏi người dùng (đổi contract cần sinh lại `api.gen.ts` mà máy không có Node; muốn đo trên cloud phải đi
  nhánh deploy `release-mvp-v2`).
- Scratchpad bị dọn khi phiên trước kết thúc (14:18) → tạo lại file env của bench; DB bench `wt-seed-postgres-1` đã dừng (mã 255) → `docker start`,
  dữ liệu còn nguyên (7.145 event).

## Kiểm tra

- `pytest src/evaluation/recsys_bench/tests` (vsf2): 127 passed.
- `pytest src/backend/tests/unit/domain/test_recommendation_criteria_20_23.py test_recommendation_trip_open.py`: 6 passed.
- 4 run ablation exit 0, `expectFailed []`, split khớp bản đóng băng; số ở report.

## Còn lại / rủi ro

- `stageMs` cho `/recommendations` chờ người dùng chốt cách làm.
- Chưa chạy toàn bộ test backend.
