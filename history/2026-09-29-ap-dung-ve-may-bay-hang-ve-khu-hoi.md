# Áp dụng đề xuất hạng vé và khứ hồi vào PRD

- Ngày: 2026-09-29
- Tác giả: mihhquan / Claude Code
- Nhánh: feat/booking
- Trạng thái: hoàn thành
- Phạm vi: docs

## Mục tiêu

Người dùng chốt đề xuất hạng vé theo chặng và hiển thị khứ hồi (Q1–Q7); áp dụng vào PRD và lưu trữ đề xuất.

## File thay đổi

- `docs/prd/requirements.md` — sửa: FR-CAT-03 thêm `attributes.fareClasses`; thêm FR-BKG-10 và AC-BKG-09
- `docs/prd/data-model.md` — sửa: §3.1 `flight_instance` thay `cabinClass`/`baggageAllowanceKg` bằng `fareClasses`
- `docs/prd/user-flow.md` — sửa: §4.4 thêm wireframe thẻ vé khứ hồi
- `docs/prd/update/2026-09-29-ve-may-bay-hang-ve-va-khu-hoi.md` — chuyển sang `docs/prd/update-archive/`, trạng thái `đã áp dụng`

## Quyết định

- Chốt cả Q1–Q7 theo đề xuất: FR-BKG-07 giữ nguyên cho vé máy bay, khứ hồi = tổng hai chặng, không hiện số ghế còn.

## Kiểm tra

- Chỉ sửa tài liệu; chưa chạy validate_contract.py vì chưa đổi contract.

## Còn lại / rủi ro

- Đề xuất phụ thuộc `2026-09-29-checkout-nhieu-buoc-hanh-khach.md` vẫn `chờ chốt`; phần source chưa làm cho tới khi đề xuất đó chốt.
- Chưa làm: Data cào `fareClasses` và cập nhật `docs/spec/data-collection/schema.md`, spec hạng vé/khứ hồi, contract (`fareClass`), DDL `app.cart_items.fare_class` + migration, backend `fares.py`, frontend.
