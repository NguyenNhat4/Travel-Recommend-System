# Quy tắc ngày nhận phòng khách sạn: theo lịch, tối đa 3 tháng, tối đa 30 đêm

- Ngày: 2026-10-02
- Tác giả: mihhquan / Claude
- Nhánh: feat/booking
- Trạng thái: hoàn thành
- Phạm vi: docs, contract, backend, frontend

## Mục tiêu

Trang chi tiết phòng khách sạn báo "Ngày nhận phòng phải trong khoảng 15/10/2026 – 16/10/2026", lấy từ cửa sổ mở bán của dữ liệu (`availableFrom`–`availableTo`). Đổi sang quy tắc theo lịch cho khách sạn (FR-CAT-03): nhận phòng từ hôm nay (giờ Việt Nam) đến hôm nay + 3 tháng, trả phòng sau 1–30 đêm, hạng phòng kín trong lịch thì báo hết chỗ. Đề xuất đã được mihhquan chốt ngày 2026-10-02 (`docs/prd/update-archive/2026-10-02-quy-tac-ngay-nhan-phong-khach-san.md`).

## File thay đổi

- `docs/prd/requirements.md` — sửa: FR-CAT-03 thêm quy tắc ngày khách sạn.
- `docs/prd/update-archive/2026-10-02-quy-tac-ngay-nhan-phong-khach-san.md` — thêm: đề xuất đã áp dụng, lưu trữ.
- `docs/spec/hop-dong-tich-hop-backend.md`, `docs/spec/hop-dong-tich-hop-frontend.md` — sửa: `DATE_OUT_OF_RANGE`, tripContext, bảng lỗi.
- `src/shared/contracts/schemas/booking.yaml` — sửa: `nights` thêm `maximum: 30` (thêm giỏ, sửa mục giỏ).
- `src/backend/app/api/v1/schemas/booking.py` — sửa: `nights` tối đa 30 (trước là 60).
- `src/backend/app/domain/booking/pricing.py` — sửa: `check_product` nhận `today`, `nights`; cửa sổ khách sạn, kiểm lịch kín.
- `src/backend/app/application/booking/lines.py`, `cart.py`, `drafts.py`, `create_hold.py` — sửa: truyền ngày hiện tại giờ Việt Nam và số đêm vào `check_product`.
- `src/backend/tests/unit/domain/booking/test_booking_domain.py` — sửa: thêm 4 test.
- `src/frontend/src/components/detail/ProductDetailView.tsx` — sửa: `validateDates`, ngày mặc định, `min`/`max` của ô ngày, ngữ cảnh chuyến đi theo quy tắc mới.
- `src/frontend/tests/unit/productDetailView.test.tsx` — sửa: thêm test ngày khách sạn.

## Quyết định

- Khách sạn không còn kiểm theo `available_from/to`; loại khác giữ nguyên.
- Lịch `attributes.availability` kín ở đêm đã chọn trả `PRODUCT_UNAVAILABLE`; ngày không có dữ liệu lịch thì không chặn.
- Không đổi `src/frontend/src/types/api.gen.ts` vì `maximum` không sinh ra kiểu TypeScript.

## Kiểm tra

- `src/backend/.venv/bin/python -m pytest src/backend/tests`: 1135 passed, 25 skipped, 1 failed lúc chạy lần đầu (test mới viết sai ngày kín); đã sửa, chạy lại `tests/unit/domain/booking`: 137 passed.
- `src/frontend/node_modules/.bin/vitest run`: 51 file, 542 test PASS; `tsc --noEmit` sạch.
- `validate_contract.py`: PASS.

## Còn lại / rủi ro

- Chưa kiểm tay trên trình duyệt.
- Cập nhật mục giỏ không gửi `nights` thì backend kiểm lịch kín theo 1 đêm.
