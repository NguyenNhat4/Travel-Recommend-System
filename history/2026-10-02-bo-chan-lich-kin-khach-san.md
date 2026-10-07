# Bỏ chặn đặt phòng theo lịch kín của khách sạn

- Ngày: 2026-10-02
- Tác giả: mihhquan / Claude
- Nhánh: feat/booking
- Trạng thái: hoàn thành
- Phạm vi: docs, backend, frontend
- Thay thế một phần: `2026-10-02-quy-tac-ngay-nhan-phong-khach-san.md` (phần "hạng phòng kín thì báo hết chỗ")

## Mục tiêu

Sau khi áp quy tắc ngày mới, trang chi tiết phòng báo "Hạng phòng này đã hết chỗ trong thời gian bạn chọn" cho ngày 03–04/10. Nguyên nhân: `attributes.availability.calendar` của phòng gần như toàn `0` (ví dụ Phòng Premier Vinpearl Landmark 81: cả 30 ngày từ 29/09 đều `0`; phòng Club chỉ ngày 15/10 là `1`). `0` ở đây là nguồn không có giá ngày đó, không phải hết phòng. mihhquan quyết định mở cho mọi ngày: không dùng lịch để chặn khách sạn.

## File thay đổi

- `docs/prd/requirements.md` — sửa: FR-CAT-03 bỏ quy tắc "kín thì báo hết chỗ", ghi lịch chỉ để tham khảo.
- `docs/spec/hop-dong-tich-hop-backend.md` — sửa: dòng `DATE_OUT_OF_RANGE` bỏ ý kiểm lịch kín.
- `src/backend/app/domain/booking/pricing.py` — sửa: bỏ `_sold_out_in_calendar` và tham số `nights` của `check_product`.
- `src/backend/app/application/booking/lines.py`, `create_hold.py` — sửa: bỏ truyền `nights` vào `check_product`.
- `src/backend/tests/unit/domain/booking/test_booking_domain.py` — sửa: thay test lịch kín bằng test lịch bị bỏ qua.
- `src/frontend/src/components/detail/ProductDetailView.tsx` — sửa: bỏ `soldOutInCalendar` và thông báo hết chỗ.

## Quyết định

- Khách sạn còn `available` thì mở cho mọi ngày trong cửa sổ hôm nay → +3 tháng, tối đa 30 đêm.
- Không tạo đề xuất riêng trong `docs/prd/update/`: người dùng chốt trực tiếp trong phiên sau khi được báo nguyên nhân; PRD được sửa trước, rồi mới sửa code.

## Kiểm tra

- `pytest` các thư mục `tests/unit/domain/booking`, `tests/unit/application/booking`, `tests/contract/test_booking_contract.py`: 240 passed.
- `vitest run tests/unit/productDetailView.test.tsx`: 13 passed; `tsc --noEmit` sạch.
- Chưa chạy lại toàn bộ test backend và frontend.

## Còn lại / rủi ro

- Chưa kiểm tay trên trình duyệt.
- Backend không có tồn kho thật nên khách sạn nhận mọi ngày trong cửa sổ; đúng với phạm vi PRD (không nối tồn kho thời gian thực).
