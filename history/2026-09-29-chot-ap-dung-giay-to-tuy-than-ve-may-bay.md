# Chốt và áp dụng PRD: giấy tờ tuỳ thân hành khách vé máy bay (FR-BKG-13)

- Ngày: 2026-09-29
- Tác giả: mihhquan / Claude Code
- Nhánh: feat/booking
- Trạng thái: hoàn thành
- Phạm vi: docs

## Mục tiêu

mihhquan chốt đề xuất `2026-09-29-ve-may-bay-giay-to-tuy-than.md` (tạo ở entry `2026-09-29-de-xuat-giay-to-tuy-than-ve-may-bay.md`) nguyên trạng, không yêu cầu sửa. Áp dụng nội dung đã chốt vào PRD trước khi sửa spec/contract/DDL/code, theo mục 8 bước 3–4 của AGENTS.md.

## File thay đổi

- `docs/prd/requirements.md` — sửa: thêm FR-BKG-13 vào §1.5 (sau FR-BKG-10); thêm AC-BKG-11, AC-BKG-12 vào bảng §3 (sau AC-BKG-10).
- `docs/prd/data-model.md` — sửa: entity `APP_BOOKING_TRAVELERS` (§2.2) thêm cột `documents` (jsonb).
- `docs/prd/update/2026-09-29-ve-may-bay-giay-to-tuy-than.md` → `docs/prd/update-archive/2026-09-29-ve-may-bay-giay-to-tuy-than.md` — đổi tên (chuyển thư mục) + sửa: trạng thái "chờ chốt" → "đã áp dụng", ghi "Chốt bởi / ngày: mihhquan, 2026-09-29".

## Quyết định

- Nội dung PRD áp dụng đúng như bản đề xuất (không sửa gì thêm): FR-BKG-13, AC-BKG-11/12, khối `documents` `{title, nationality, docType, docNumber, docExpiry}`.
- Không sửa `docs/prd/project-brief.md` §4.2 vì mục đó chưa từng liệt kê giấy tờ tuỳ thân là ngoài phạm vi (chỉ spec-level ở `docs/spec/booking/checkout-nhieu-buoc-hanh-khach.md` §3.3 ghi vậy); phần đó sẽ sửa ở bước cập nhật spec tiếp theo.

## Kiểm tra

- Không có thay đổi code/contract/DDL trong entry này. `validate_contract.py` chưa cần chạy (contract chưa đổi).

## Còn lại / rủi ro

- Chưa sửa `docs/spec/booking/checkout-nhieu-buoc-hanh-khach.md` (§3.3 và thiết kế chi tiết), contract, DDL, backend, frontend cho FR-BKG-13 — làm ở bước tiếp theo, entry riêng.
- FR-BKG-10 (hạng vé, khứ hồi): mihhquan chọn dùng dữ liệu minh hoạ tạm (không chờ Data bổ sung `attributes.fareClasses`, hiện = 0 sản phẩm trên snapshot thật). Cần quyết định kỹ thuật thêm: dữ liệu minh hoạ này đặt ở đâu (backend constant hay seed synthetic vào catalog) — xử lý ở bước triển khai FR-BKG-10, chưa làm trong entry này.
