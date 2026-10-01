# Áp dụng đề xuất xuất vé máy bay mô phỏng vào PRD

- Ngày: 2026-09-29
- Tác giả: mihhquan / Claude Code
- Nhánh: feat/booking
- Trạng thái: hoàn thành
- Phạm vi: docs

## Mục tiêu

Người dùng chốt đề xuất xuất vé mô phỏng (Q1–Q5); áp dụng vào PRD và lưu trữ đề xuất.

## File thay đổi

- `docs/prd/project-brief.md` — sửa: §4.2 thêm câu xuất vé chỉ mô phỏng
- `docs/prd/requirements.md` — sửa: FR-BKG-04; thêm FR-BKG-12
- `docs/prd/user-flow.md` — sửa: §4.3 thêm khối thông tin vé máy bay
- `docs/prd/data-model.md` — sửa: `booking_items.metadata.ticketing`, ghi chú dưới §4.1
- `docs/prd/update/2026-09-29-ve-may-bay-xuat-ve-mo-phong.md` — chuyển sang `docs/prd/update-archive/`, trạng thái `đã áp dụng`

## Quyết định

- Chốt cả Q1–Q5 theo đề xuất; không thêm trạng thái vào vòng đời đơn.

## Kiểm tra

- Chỉ sửa tài liệu; chưa chạy validate_contract.py vì chưa đổi contract.

## Còn lại / rủi ro

- Đề xuất phụ thuộc `2026-09-29-ve-may-bay-thong-tin-hanh-khach.md` (và checkout-nhieu-buoc) vẫn `chờ chốt`; FR-BKG-12 dùng `travelerRef` của đề xuất đó.
- Chưa làm: spec §6.8, contract `BookingItem.ticketing`, backend job, frontend.
