# Áp dụng đề xuất checkout nhiều bước và hành khách vào PRD

- Ngày: 2026-09-29
- Tác giả: mihhquan / Claude Code
- Nhánh: feat/booking
- Trạng thái: hoàn thành
- Phạm vi: docs

## Mục tiêu

Người dùng chốt toàn bộ Q1–Q10 của đề xuất `2026-09-29-checkout-nhieu-buoc-hanh-khach`; áp dụng vào PRD và lưu trữ đề xuất (AGENTS.md mục 8, bước 3–4). Chưa sửa source.

## File thay đổi

- `docs/prd/requirements.md` — sửa: FR-BKG-02 (tổng theo dòng giá), thêm FR-BKG-08, AC-BKG-05/06/07
- `docs/prd/user-flow.md` — sửa: §2 route `/checkout`, §3.3 (ba bước, sơ đồ lỗi về đúng bước), §4.3 (hành khách và dòng giá), §4.4 (wireframe bước ①)
- `docs/prd/data-model.md` — sửa: thêm `APP_BOOKING_TRAVELERS` và quan hệ, mô tả `metadata`, ghi chú giỏ hàng
- `docs/prd/update/2026-09-29-checkout-nhieu-buoc-hanh-khach.md` — đổi tên sang `docs/prd/update-archive/`, trạng thái `đã áp dụng`

## Quyết định

- Giữ mã FR-BKG-08 và AC-BKG-05…07 như đề xuất; FR-BKG-10/11/12 và AC-BKG-09/10 đã do các đề xuất vé máy bay cấp, không trùng.
- Các thay đổi PRD khác trong working tree (vé máy bay) không đụng tới.

## Kiểm tra

- Chỉ sửa tài liệu; không chạy validate_contract.py (chưa đổi contract).

## Còn lại / rủi ro

- Source chưa sửa: hoàn thiện spec `docs/spec/booking/checkout-nhieu-buoc-hanh-khach.md` (§10–§16), contract 1.8.0, DDL + migration 0005, backend, frontend, test — theo mục "Thay đổi source sau khi chốt" của đề xuất đã lưu trữ.
- Đề xuất vé máy bay "thông tin hành khách" được nhắc tên trong đề xuất này nhưng file tương ứng không còn ở `update/` lẫn `update-archive/`; cần đối chiếu khi làm phần vé bay.
