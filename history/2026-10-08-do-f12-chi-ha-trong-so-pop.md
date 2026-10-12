# Đo thêm biến thể F12 (chỉ hạ trọng số pop, không giãn cos)

- Ngày: 2026-10-08
- Tác giả: Pham Nguyen Dang Khoi / Claude Code
- Nhánh: bench_search_recomSys
- Trạng thái: hoàn thành
- Phạm vi: evaluation

## Mục tiêu

Người dùng hỏi sao không chỉ giảm trọng số thay vì giãn cos; đo so sánh công bằng với F7 (cùng chỉ áp khi không có chuyến mở). FR-REC-04.

## File thay đổi

- `src/evaluation/recsys_bench/theme_study/eval_formula.py` — sửa: thêm F12, F12b
- `src/evaluation/reports/eval-2026-10-08-recsys-so-thich-chu-de.md` — sửa: thêm bảng F12

## Quyết định

- F7 không thua F12 / F12b ở chỉ số nào; chênh lệch sát sai số.

## Kiểm tra

- `eval_formula --n-syn 80 --max-users 800 --variants F12_betweenRawPop03,F12b_betweenRawPop05` trên `vota_prodcopy`: xong 1.128 s.

## Còn lại / rủi ro

- Chưa đo F13 (centering vector).
