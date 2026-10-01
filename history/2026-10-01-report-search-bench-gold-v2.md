# Report bench search B0 vs E2.e5 (gold_v1 → gold_v2) vào `src/evaluation/reports/`

- Ngày: 2026-10-01
- Tác giả: tqanh123 / Claude Code
- Nhánh: bench/m6-trip-ended
- Trạng thái: hoàn thành
- Phạm vi: evaluation

## Mục tiêu

Người dùng yêu cầu ghi lại các lượt chạy bench hôm nay vào `src/evaluation/reports/` (cùng chỗ với report golden
eval — report kết quả chạy job, không phải spec). Phục vụ FR-SRC-01..04, AC-SRC-01, test-plan §2.5.

## File thay đổi

- `src/evaluation/reports/eval-2026-10-01-search-bench-gold-v2.md` — thêm: sanity 6/6 PASS; run `20261001-0623-ec5fbd2`
  trên gold_v1 (B0 judged 0,967 · e5 0,550 — thiên lệch pooling); vòng hole D4a (597 cặp máy gán, duyệt QAnh 597/597);
  rescore gold_v2: judged 1,000 cả hai, **TIE** (Δrecall −0,25 [CI −2,82, +2,27] · ΔnDCG +1,37 [CI −2,16, +5,24]);
  bảng nDCG theo slice; caveat (slice n≤5 ồn, abbrev_typo in-sample, compare CLI chưa đọc bản rescore); lệnh tái sinh.

## Quyết định

- Report đặt ở `src/evaluation/reports/` theo chỉ định của người dùng — cùng quy ước với
  `eval-2026-09-23/24-golden.md` (kết quả chạy của workstream evaluation; spec/plan vẫn ở `docs/`).

## Kiểm tra

- Số liệu chép nguyên văn từ output `sb sanity` / `sb run` / `sb rescore` / `runner.compare` trong phiên 01/10
  (history: `2026-10-01-nhan-may-hole-d4a.md`, `2026-10-01-duyet-nhan-may-d4a-tag-gold-v2.md`).

## Còn lại / rủi ro

- Vá `sb compare` để đọc `results@<gold_version>.json` của rescore (hiện phải gọi `read_results_at` tay).
- Bảng tổng hợp chính thức cho spec (`docs/spec/bench/search-eval-results.md`) viết ở bước 02/10 chiều theo plan.
