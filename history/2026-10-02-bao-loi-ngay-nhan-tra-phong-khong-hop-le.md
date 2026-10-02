# Báo lỗi ngày nhận/trả phòng không hợp lệ ở khung đặt phòng

- Ngày: 2026-10-02
- Tác giả: mihhquan / Claude
- Nhánh: feat/booking
- Trạng thái: hoàn thành
- Phạm vi: frontend

## Mục tiêu

Ở trang chi tiết khách sạn, khi người dùng nhập tay ngày sai (trả phòng không sau nhận phòng, ngày trống, ngoài cửa sổ mở bán) thì "Đặt ngay" vẫn bấm được, và `TravelContext` âm thầm sửa ngày (`nightsBetween` ép tối thiểu 1 đêm, `defaultUsingDate` thay ngày trống) rồi vào `/checkout`. Yêu cầu: phải báo lỗi hoặc khoá nút, không tự sửa.

## File thay đổi

- `src/frontend/src/components/detail/ProductDetailView.tsx` — sửa: thêm `validateDates`, hiện thông báo lỗi `date-error`, khoá Đặt ngay / Thêm vào giỏ khi ngày sai; `DateInput` đổi từ `input[type=date]` sang ô gõ dd/mm/yyyy (có mask) kèm nút mở lịch gốc, không phụ thuộc locale trình duyệt; đổi ngày nhận thì tự dời ngày trả thành +1 đêm khi trống hoặc không sau ngày nhận (lịch gốc chặn chọn ngày trả khi min > ngày chọn được).
- `src/frontend/tests/unit/productDetailView.test.tsx` — sửa: thêm test ngày không hợp lệ; test "Đặt ngay không có variant" chờ ngày mặc định điền xong trước khi bấm.

## Quyết định

- Chỉ sửa frontend; backend vẫn kiểm lại cửa sổ bán (DATE_OUT_OF_RANGE). Không lệch PRD, không đổi contract.
- Không sửa `TravelContext` vì các luồng thêm nhanh khác (trợ lý, widget) vẫn dựa vào ngày mặc định.

## Kiểm tra

- `tsc --noEmit` (src/frontend): sạch.
- `vitest run` (src/frontend): 51 file, 541 test PASS.

## Còn lại / rủi ro

- Chưa kiểm tay trên trình duyệt.
