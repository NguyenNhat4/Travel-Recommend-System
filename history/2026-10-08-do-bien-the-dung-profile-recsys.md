# Đo biến thể dựng profile RecSys (bước 1) và kịch bản lướt xem nhiễu

- Ngày: 2026-10-08
- Tác giả: Pham Nguyen Dang Khoi / Claude Code
- Nhánh: bench_search_recomSys
- Trạng thái: hoàn thành
- Phạm vi: evaluation

## Mục tiêu

Kiểm chứng các vấn đề dựng profile (giới hạn lặp bỏ event, lượt xem lẻ lấn át u_long) trước khi đề xuất sửa engine. FR-REC-01, FR-REC-04.

## File thay đổi

- `src/evaluation/recsys_bench/theme_study/profile_variants.py` — thêm: `build_profile` viết lại với công tắc cap_fix / confidence / session
- `src/evaluation/recsys_bench/theme_study/eval_profile.py` — thêm: đo profile × công thức, kiểm khớp production, thống kê cấu trúc profile
- `src/evaluation/recsys_bench/theme_study/theme_exp.py` — sửa: thêm kịch bản `noisy` (kịch bản cũ giữ nguyên seed)
- `src/evaluation/reports/eval-2026-10-08-recsys-so-thich-chu-de.md` — sửa: thêm bảng bước 1

## Quyết định

- Không sửa engine; chỉ đo. Ứng viên: P2 (trọng số độ tin cậy chuyến) + sửa giới hạn lặp (P1, đúng logic dù không đổi số).

## Kiểm tra

- Bản viết lại khớp production: 0/200 khách LLBO lệch. P0 + F0 ra lại đúng số production (LLBO 0.8363, theme 0.438).
- 3 lượt split thật + 1 lượt khách giả lập trên `vota_prodcopy`, số trong report.

## Còn lại / rủi ro

- Chưa đo P2 + F7 trên split thật (LLBO / temporal / nexttrip).
- Kịch bản `noisy` là giả lập; tỷ lệ xem/mua chọn gần dữ liệu thật (4,26 / 1,52) nhưng chủ đề lượt xem nhiễu là ngẫu nhiên.
