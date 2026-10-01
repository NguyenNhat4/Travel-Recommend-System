# Plan: normalize ổn định theo từng bước

- Ngày: 2026-09-28
- Tác giả: Đăng Khôi / Claude Code
- Nhánh: test/newcrawl
- Trạng thái: hoàn thành
- Phạm vi: docs

## Mục tiêu

Người dùng (theo định hướng mentor về độ ổn định) yêu cầu plan chi tiết cho bước 1: làm normalize ổn định trong code
trước khi đưa DAG Airflow vào. Cần có checkpoint tuần tự, lý do, khác gì so với trước, và test cho mỗi checkpoint.
Phục vụ FR-CAT-01..04.

## File thay đổi

- `docs/plan/2026-09-28-normalize-on-dinh-theo-buoc.md` — thêm: plan gồm CP0 (golden test) → CP1 (đo từng bước) → CP2 (cô lập lỗi theo bản ghi) → CP3 (phân loại lỗi và chiến thuật) → CP4 (tách bước có checkpoint) → CP5 (normalize theo nguồn song song) → CP6 (chạy lại từ bước lỗi).
- `history/2026-09-28-plan-normalize-on-dinh.md` — thêm: entry này.

## Quyết định

- Chưa đưa Airflow vào: làm các bước trong code trước, để DAG sau này chỉ còn là bọc lại (người dùng đồng ý thứ tự này).
- Giữ quy tắc nạp DB "được cả hoặc không có gì" trong plan; nạp phần thành công (A/B) để người dùng/mentor quyết sau.
- Plan không lệch PRD: output `products.jsonl` phải giữ nguyên, có golden test làm điều kiện.

## Kiểm tra

- Chỉ là tài liệu; không chạy test. Các số đo trong plan lấy từ lần profile trước (interim 49 MB, ~22 giây).

## Còn lại / rủi ro

- Chờ người dùng chọn cách làm việc (ai code, ai kiểm) và đồng ý bắt đầu CP0.
- Chưa commit.
