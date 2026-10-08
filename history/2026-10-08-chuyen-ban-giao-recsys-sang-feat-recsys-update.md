# Chuyển bàn giao RecSys bám sở thích sang nhánh feat/recSys_update

- Ngày: 2026-10-08
- Tác giả: Pham Nguyen Dang Khoi / Claude Code
- Nhánh: feat/recSys_update
- Trạng thái: hoàn thành
- Phạm vi: evaluation, docs

## Mục tiêu

Người dùng tạo nhánh `feat/recSys_update` trên GitHub (từ `release-mvp-v2` @ `6f77e80`) để tqanh123 kéo về mà không xung đột với
`bench_search_recomSys`. Đưa bàn giao nghiên cứu RecSys bám sở thích sang nhánh này. FR-REC-01, FR-REC-02, FR-REC-04.
Tiếp theo `history/2026-10-08-bao-cao-cuoi-va-ban-giao-recsys-so-thich.md`.

## File thay đổi

- Cherry-pick từ `bench_search_recomSys`: commit bàn giao `0ccc948` (script `theme_study/`, kết quả JSON, test, report, báo cáo cuối,
  plan, đề xuất PRD chờ chốt, history 08/10) và từ commit `235e92e` chỉ còn `src/evaluation/reports/eval-2026-10-07-recsys-grid-llbo-coldstart.md`
  (trọng số 0,7/0,15/0,15, đề xuất 06/10 lưu trữ và history 07/10 đã có sẵn trên `release-mvp-v2`).
- `docs/plan/2026-10-08-ban-giao-recsys-bam-so-thich.md` — sửa: nhánh bàn giao, §1, §2.1–2.2, WP0 viết lại theo base production, checklist.
- `docs/spec/bench/recsys-bam-so-thich-tong-hop.md` — sửa: đầu tài liệu, §0 mục 6, §7 theo nhánh mới.
- `history/2026-10-08-chuyen-ban-giao-recsys-sang-feat-recsys-update.md` — thêm: entry này.

## Quyết định

- Làm trong worktree riêng để không đụng thay đổi chưa commit của các việc khác ở thư mục chính.
- Không đổi `bench_search_recomSys` (không force push); hai commit trên đó giữ nguyên, tài liệu ghi rõ làm tiếp ở `feat/recSys_update`.
- Không commit trailer Co-Authored-By (quy ước người dùng).

## Kiểm tra

- Trên `feat/recSys_update`: `pytest src/evaluation/recsys_bench/tests` 138 passed, 2 xfailed; `pytest src/backend/tests/architecture` 8 passed;
  import mọi module `theme_study` không lỗi.
- `eval_profile --profiles P0_prod --scorers F0_prod --n-syn 2 --max-users 50 --splits ""` trên `vota_prodcopy`:
  `parity_mismatch_llbo200 = 0` với `build_profile` của nhánh này (69 s).

## Còn lại / rủi ro

- Số bước 1–2 chạy trên engine cũ; đo lại mốc trên engine production (plan WP0).
- Còn lại theo plan WP0–WP7 và gate G1–G6.
