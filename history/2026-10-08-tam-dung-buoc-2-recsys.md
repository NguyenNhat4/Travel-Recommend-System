# Tạm dừng: bước 2 so cách phối hợp điểm RecSys trên profile P2

- Ngày: 2026-10-08
- Tác giả: Pham Nguyen Dang Khoi / Claude Code
- Nhánh: bench_search_recomSys
- Trạng thái: dang dở
- Phạm vi: evaluation
- Bị thay thế bởi: `history/2026-10-08-bao-cao-cuoi-va-ban-giao-recsys-so-thich.md`

## Mục tiêu

So F7 / F12b / F13 centering / F14 calibration phân vị trên profile P2 (trọng số độ tin cậy chuyến). FR-REC-04.

## File thay đổi

- `src/evaluation/recsys_bench/theme_study/step2_scorers.py` — thêm: scorer centering (F13a/b) và calibration phân vị (F14)
- `src/evaluation/recsys_bench/theme_study/eval_profile.py` — sửa: dựng F13 / F14 lúc chạy, tập calibration riêng seed 99, `--splits`
- `src/evaluation/reports/eval-2026-10-08-recsys-so-thich-chu-de.md` — sửa: mục "Bước 2 — đang chạy"

## Quyết định

- Không sửa engine. Ứng viên sau bước 1: P2 + (cách phối hợp thắng ở bước 2) + sửa giới hạn lặp.

## Kiểm tra

- Chạy thử nhỏ F13a / F14: không lỗi, profile viết lại khớp production 0/200 lệch.
- Ba lượt đầy đủ đang chạy nền khi dừng; kết quả: `~/code/recsys-theme-2026-10-08/{profile_p2f7,step2_x,step2_y}.json`.

## Còn lại / rủi ro

- Đọc ba file kết quả, thêm bảng bước 2 vào report, chọn phương án, cập nhật đề xuất PRD chờ chốt.
- Sau đó (bước 3): tín hiệu chủ đề trong text / attributes cùng team Search + Data; tracking impression / source / position.
- Báo tqanh123: `askpass.cmd` chứa mật khẩu trên `origin/fix/search-production` (commit b80acb6) — đổi mật khẩu, gỡ khỏi lịch sử.
