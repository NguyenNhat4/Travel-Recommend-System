# Đo phân bố ba thành phần điểm RecSys trước trọng số

- Ngày: 2026-10-08
- Tác giả: Pham Nguyen Dang Khoi / Claude Code
- Nhánh: bench_search_recomSys
- Trạng thái: hoàn thành
- Phạm vi: evaluation

## Mục tiêu

Người dùng cần vùng giá trị của cos(u_short), pop, cos(u_long) trước khi nhân trọng số và cách lấy số. FR-REC-04.

## File thay đổi

- `src/evaluation/recsys_bench/theme_study/component_stats.py` — thêm: bọc `score_candidates`, ghi phân bố theo request
- `src/evaluation/reports/eval-2026-10-08-recsys-so-thich-chu-de.md` — sửa: thêm bảng phân bố + đính chính tỷ lệ pop = 0

## Quyết định

- Đo trên đúng ma trận `E` engine chấm mỗi request, không đổi điểm hay thứ hạng.

## Kiểm tra

- `component_stats --max-users 300 --n-syn 50` trên `vota_prodcopy`: chạy xong, số ghi trong report.

## Còn lại / rủi ro

- Không có.
