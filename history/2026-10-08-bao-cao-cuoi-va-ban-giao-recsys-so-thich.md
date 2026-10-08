# Báo cáo cuối và bàn giao nghiên cứu RecSys bám sở thích cho tqanh123

- Ngày: 2026-10-08
- Tác giả: Pham Nguyen Dang Khoi / Claude Code
- Nhánh: bench_search_recomSys
- Trạng thái: hoàn thành
- Phạm vi: evaluation, docs
- Thay thế: `history/2026-10-08-tam-dung-buoc-2-recsys.md`, `history/2026-10-08-tong-hop-recsys-bam-so-thich.md` (hai entry dang dở)

## Mục tiêu

Gộp toàn bộ nghiên cứu 07–08/10 thành một báo cáo cuối đúng số, chuẩn bị file và plan + checklist để bàn giao cho tqanh123 trên nhánh
`bench_search_recomSys`. FR-REC-01, FR-REC-02, FR-REC-04, AC-REC-02.

## File thay đổi

- `docs/spec/bench/recsys-bam-so-thich-tong-hop.md` — sửa (viết lại): báo cáo cuối; thêm bước 2 đầy đủ (F13a, F14), bảng số sinh từ JSON,
  ước lượng ý nghĩa thống kê, nguồn engine từng nhóm số, đính chính lỗi cap lặp đã sửa trên main, đối chiếu nhận xét reviewer, khuyến nghị + tiêu chí.
- `src/evaluation/reports/eval-2026-10-08-recsys-so-thich-chu-de.md` — sửa: provenance engine của bước 1–2; thay mục "Bước 2 — hai job còn
  chạy" bằng kết quả hoàn tất; đính chính ca xfail `production-known-bug`.
- `docs/plan/2026-10-08-ban-giao-recsys-bam-so-thich.md` — thêm: plan bàn giao WP0–WP7, gate cần chốt, checklist.
- `src/evaluation/recsys_bench/theme_study/results/2026-10-08/` — thêm: 17 file JSON kết quả gốc chép từ `~/code/recsys-theme-2026-10-08/`,
  `formula_prod_F7_F10.json` (trích nguyên văn từ `formula_prod_F78.log` / `formula_prod_F910.log`, kèm SHA-256 log gốc) và `SHA256SUMS`.
- `history/2026-10-08-tam-dung-buoc-2-recsys.md`, `history/2026-10-08-tong-hop-recsys-bam-so-thich.md` — sửa: chỉ thêm dòng `Bị thay thế bởi`.
- `history/2026-10-08-bao-cao-cuoi-va-ban-giao-recsys-so-thich.md` — thêm: entry này.
- (commit riêng) `src/backend/app/domain/recommendation/profile.py`, đề xuất 06/10 → `update-archive/`, `history/2026-10-07-recsys-trong-so-0-7-0-15.md`,
  `src/evaluation/reports/eval-2026-10-07-recsys-grid-llbo-coldstart.md` — nội dung việc 07/10, chỉ commit hộ.

## Quyết định

- Báo cáo cuối đặt ở `docs/spec/bench/` (phân tích / quyết định, AGENTS.md §7); số thô ở report `src/evaluation/reports/`.
- Kết quả JSON đưa vào repo (160 KB, không chứa DSN — đã grep). Không đưa `.npy` (6 MB), `prodcopy.env`, log gốc (`*.log` bị `.gitignore`;
  thông tin cần thiết đã có trong JSON). Không sửa `.gitignore`.
- Không sửa engine, test, đề xuất PRD chờ chốt; các việc đó nằm trong plan (WP1, WP5).
- Người dùng yêu cầu commit + push lên `bench_search_recomSys`. Hai commit: trọng số 0,7/0,15/0,15 (việc 07/10 đã chốt, chưa commit) và
  bàn giao nghiên cứu. Rebase lên 6 commit search của `origin/bench_search_recomSys` (06/10). Thay đổi của các việc khác không commit,
  được cất vào stash rồi trả lại; xung đột duy nhất `src/backend/README.md` gộp cả hai phía (đoạn embedding e5 của remote + câu mã băm catalog).
  Không commit trailer Co-Authored-By (quy ước người dùng).

## Kiểm tra

- Bước 2 hoàn tất: `step2_x.log` `done 2238s`, `step2_y.log` `done 2218s`, `profile_p2f7.log` `done 1207s`; `parity_mismatch_llbo200 = 0` ở mọi
  JSON; 16:24 không còn tiến trình đo (`ps`).
- Bảng số trong báo cáo cuối và report sinh bằng script Python đọc thẳng JSON.
- `build_profile` của `origin/main` (lấy bằng `git show`) chạy kịch bản 3 view + purchase cùng chuyến: `bought_units`, `ends_on`, `active_trip`,
  `strategy = cross_vertical` đúng; purchase không nằm trong `trip.events`. Nhánh bench: sai cả bốn.
- `pytest test_profile_variants.py test_parity.py test_engine_no_leak.py` (env `vsf2`): 20 passed, 2 xfailed.
- `git rev-list --left-right --count`: chậm `origin/main` 71 commit, chậm `origin/bench_search_recomSys` 6 commit; 7 file sửa local trùng 6 commit đó.
- `sha256sum` các file trong `results/2026-10-08/` → `SHA256SUMS`.
- Sau rebase: `pytest src/evaluation/recsys_bench/tests` 137 passed, 2 xfailed; `pytest src/backend/tests/architecture` + unit recommendation
  33 passed; `embed_prodcopy` import được. Diff khôi phục sau stash khớp đúng stash (17 file, +350 / −58).

## Còn lại / rủi ro

- Toàn bộ việc còn lại theo `docs/plan/2026-10-08-ban-giao-recsys-bam-so-thich.md` (WP0–WP7, gate G1–G6).
- CI chỉ là ước lượng thô hai tỷ lệ độc lập; CI ghép cặp cần lưu kết quả từng khách (WP2).
- Lệnh gốc của `step2_x` / `step2_y` không được lưu; lệnh trong report dựng lại từ tên cấu hình.
- Bước nạp jsonl của `dump_prod.py` vào `vota_prodcopy` chưa được ghi lại → bàn giao bằng `pg_dump`.
- Báo tqanh123: `askpass.cmd` chứa mật khẩu trên `origin/fix/search-production` (`b80acb6`).
