# Thêm phụ lục dịch vụ thêm của vé máy bay vào spec checkout

- Ngày: 2026-09-29
- Tác giả: mihhquan / Claude Code
- Nhánh: feat/booking
- Trạng thái: hoàn thành
- Phạm vi: docs

## Mục tiêu

Cập nhật spec sau khi PRD đã áp dụng FR-BKG-11 (`history/2026-09-29-ap-dung-ve-may-bay-dich-vu-them.md`).

## File thay đổi

- `docs/spec/booking/checkout-nhieu-buoc-hanh-khach.md` — sửa: §3.3 bỏ "chọn ghế, hành lý" khỏi ngoài phạm vi, thêm Phụ lục A (quy tắc R-EXT, dòng giá `BAG`/`SEAT`, thay đổi contract, backend, kiểm thử).

## Quyết định

- Đặt thành phụ lục thay vì đánh số lại các mục 10–16 của spec bản nháp.
- Tên trường `extras` và mã `reason` là đề xuất trong spec, chưa vào contract.

## Kiểm tra

- Chỉ sửa tài liệu; không chạy lệnh nào.

## Còn lại / rủi ro

- Spec vẫn là bản nháp; phụ thuộc đề xuất checkout nhiều bước chờ chốt.
- Chưa sửa contract, `docs/spec/data-collection/schema.md`, backend, frontend.
