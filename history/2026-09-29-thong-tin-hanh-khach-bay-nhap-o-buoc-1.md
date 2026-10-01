# Đề xuất thông tin hành khách bay: nhập một lần ở bước ①

- Ngày: 2026-09-29
- Tác giả: mihhquan / Claude Code
- Nhánh: feat/booking
- Trạng thái: hoàn thành
- Phạm vi: docs

## Mục tiêu

Mock giao diện đã chốt: thông tin hành khách bay bị điền lặp ở nhiều chỗ, nên nhập một lần ở bước ① Hành khách. Sửa đề xuất `2026-09-29-ve-may-bay-thong-tin-hanh-khach.md` cho khớp mock (trước đó ghi nhập ở bước ②).

## File thay đổi

- `docs/prd/update/2026-09-29-ve-may-bay-thong-tin-hanh-khach.md` — sửa: Q2 chuyển sang bước ①, họ và tên tách hai ô, Q5 thành không còn xảy ra, cập nhật FR-BKG-09, AC-BKG-08, `user-flow.md` §3.3/§4.4, `data-model.md` §2.2 và mục frontend.

## Quyết định

- Họ và tên tách hai ô ngay ở bước ① lệch Q7 của đề xuất nền (một ô "Họ và tên"). Đề xuất này ghi rõ và giữ cột `full_name` (nối từ hai ô). Đề xuất nền chưa sửa; cần đồng bộ khi chốt.
- Đề xuất vẫn `chờ chốt`; chưa sửa PRD hay source.

## Kiểm tra

- Không có lệnh kiểm tra (chỉ sửa tài liệu). Đã grep không còn chỗ nào ghi nhập ở bước ②.

## Còn lại / rủi ro

- Đồng bộ Q7 và `data-model.md` trong đề xuất nền `2026-09-29-checkout-nhieu-buoc-hanh-khach.md` (chưa sửa) và spec `docs/spec/booking/checkout-nhieu-buoc-hanh-khach.md`.
