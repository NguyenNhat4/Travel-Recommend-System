# Chốt nhánh đích release-mvp-v2, sửa 2 commit, lộ trình triển khai RecSys theo giai đoạn

- Ngày: 2026-10-08
- Tác giả: tqanh123 / Claude Code
- Nhánh: feat/recSys_update
- Trạng thái: hoàn thành
- Phạm vi: docs, evaluation
- Tiếp theo: `history/2026-10-08-g2-wp4-recsys-bam-so-thich.md`

## Mục tiêu

Người dùng chốt 08/10 (tối): G2 **làm theo giai đoạn** (ship phần miễn phí → G6 đổi bộ sinh event → chốt lại G2 cho
F14c + destCap2); loại combo hai chiều phạm vi mọi lần mua; WP0.6 nhánh đích PR = `release-mvp-v2`; latency đầu-cuối là điều
kiện trước deploy; coldstart + AC-REC-01/02 phải đo; và **sửa 2 commit đã push cho ngắn gọn trước**. FR-REC-01/02/04,
AC-REC-01/02, NFR-PERF-01.

## File thay đổi

- (git, không phải file) hai commit `c6165b1` → `7b0fcde` và `e4467d7` → `4dd271e`: chỉ đổi message thành một dòng
  (`eval(recsys): WP0-WP3 bam so thich - moc moi, CI ghep cap, quyet dinh` / `eval(recsys): dieu tra G2, do
  P2+F14c+destCap2, o kham pha B, latency`); tree và parent `d25ff4a` giữ nguyên; `push --force-with-lease` theo chấp thuận
  của người dùng.
- (git) merge `origin/release-mvp-v2` @ `d8a86ac` vào feat (`457e687`): sạch, không trùng file; không dùng nhánh local
  `release-mvp-v2` (`21d72ae`, đã lệch).
- `docs/plan/2026-10-08-recsys-trien-khai-theo-giai-doan.md` — thêm: kế hoạch từ WP5 trở đi (gate đã chốt, ba đề xuất PRD,
  lane A / lane B, PR-A / PR-B, checklist).
- `docs/plan/2026-10-08-ban-giao-recsys-bam-so-thich.md` — sửa: tick WP0.6, ghi tiêu chí latency đã chốt, trỏ sang plan mới.
- `docs/spec/bench/recsys-bam-so-thich-quyet-dinh.md` — sửa: đính chính G6 không cần đề xuất PRD (tiền lệ eval-v2 /
  append-v1); thêm §7.5 "Lộ trình đã chọn".
- `src/evaluation/recsys_bench/theme_study/eval_slots.py` — sửa: thêm `--how` (mặc định `destsim` = lượt 08/10 đầu, để số cũ
  tái sinh); `out["how"]`.
- `src/evaluation/recsys_bench/theme_study/results/2026-10-08-g2-wp4/wp4_slots_p2_f14c_ulong.json` + `SHA256SUMS` — thêm.
- `src/evaluation/reports/eval-2026-10-08-recsys-g2-va-wp4.md` — sửa: §4 thêm bảng `--how ulong` và lệnh tái sinh.
- `history/2026-10-08-wp0-6-nhanh-dich-va-lo-trinh-giai-doan.md` — thêm: entry này.

## Quyết định

- Commit message một dòng, không Co-Authored-By (quy ước người dùng 24/09, memory `commit-message-style`); force-push có
  chấp thuận tường minh 08/10. Ai đã pull nhánh phải `git fetch && git reset --hard origin/feat/recSys_update`.
- Merge (không rebase) release vào feat theo tiền lệ `history/2026-10-08-merge-release-mvp-v2-vao-feat-fix-bug.md`; làm
  trước khi viết đề xuất vì release đã sửa `docs/prd/requirements.md`.
- Ô B phải đo lại bằng `--how ulong`: `eval_slots.py` mặc định `destsim` (centroid điểm đến ×2 + 0,5·cos) không phải cách
  production sẽ xếp (`cos(u_long, v)` qua `near_vector`). Kết quả: hit@4 giống hệt (0,5324 / 0,1045), thêm điểm đến khác
  29,2 %, theme `open` 0,823 — số này mới được trích vào đề xuất.
- G6 là spec-only (PRD không mô tả bộ sinh event), sửa câu sai ở `quyet-dinh.md` §7.4.

## Kiểm tra

- Sau viết lại commit: `git diff --stat e4467d7 HEAD` rỗng; tree `HEAD~1` = `6aafc805…`, `HEAD` = `3b26c5d8…`; `HEAD~2` =
  `d25ff4a`; push `+ e4467d7...4dd271e (forced update)`; `origin/feat/recSys_update` = local.
- Merge: `comm` hai tập file đổi từ merge-base → rỗng (không trùng); `git status` chỉ còn zip chưa track.
- `eval_slots --how ulong` trên P2 + F14c, toàn bộ khách: 158 s, kết quả ở trên.

## Còn lại / rủi ro

- Ba đề xuất PRD ở entry `history/2026-10-08-de-xuat-prd-recsys-o-kham-pha-combo-cong-thuc.md`; lane A / lane B theo plan mới.
- Merge PR vào `release-mvp-v2` tự deploy staging (`.github/workflows/backend-ci-cd.yml`) — mọi PR engine phải sẵn sàng deploy.
