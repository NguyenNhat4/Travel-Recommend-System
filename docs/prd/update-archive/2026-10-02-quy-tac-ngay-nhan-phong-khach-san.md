# Quy tắc ngày nhận phòng khách sạn: theo lịch, không qua khứ, đặt trước tối đa 3 tháng

- Ngày: 2026-10-02
- Người đề xuất: mihhquan / Claude
- Trạng thái: đã áp dụng
- Chốt bởi / ngày: mihhquan, 2026-10-02
- PRD bị ảnh hưởng: `docs/prd/requirements.md` FR-CAT-03 (cửa sổ mở bán `available_from`/`available_to`); `data-model.md` không đổi vì dữ liệu giữ nguyên
- Mã FR/NFR: FR-CAT-03

## Lý do

Trang chi tiết phòng khách sạn đang báo "Ngày nhận phòng phải trong khoảng 15/10/2026 – 16/10/2026". Khoảng này là `availableFrom`–`availableTo` của hạng phòng, một cửa sổ kỹ thuật lấy từ dữ liệu nạp (giao của cửa sổ 30 ngày từ `as_of` với khoảng của nguồn), không phải quy tắc nghiệp vụ. Với khách sạn, khoảng 2 ngày là vô lý với người dùng. Quy tắc mong muốn là quy tắc theo lịch.

## Nội dung đề xuất

Với sản phẩm khách sạn (`hotel_room`), ngày nhận phòng hợp lệ khi:

1. Là ngày có thật trên lịch: tháng 1–12, ngày không âm và không vượt số ngày của tháng (31 ngày với tháng 31 ngày, 30 với tháng 30, tháng 2 theo năm nhuận).
2. Không ở quá khứ: nhỏ nhất là hôm nay (giờ Việt Nam); được nhận phòng ngay hôm nay.
3. Đặt trước tối đa 3 tháng: lớn nhất là hôm nay + 3 tháng (cùng ngày của tháng, cắt về ngày cuối tháng nếu tháng đó ngắn hơn).
4. Ngày trả phòng phải sau ngày nhận ít nhất 1 đêm và tối đa 30 đêm (ngày trả ≤ ngày nhận + 30 ngày). Ngày trả cũng phải là ngày có thật trên lịch.

Hệ quả: với khách sạn, `availableFrom`/`availableTo` không còn là cơ sở kiểm tra ngày nhận phòng. Thay thế câu hiện hành "ngày nhận trong [availableFrom, availableTo]" bằng quy tắc 1–4. Lịch phòng kín/trống `attributes.availability` (đọc-only) giữ nguyên. Vé máy bay và hoạt động giữ cửa sổ hiện tại.

## Các điểm đã trả lời (2026-10-02, người dùng)

- Nhận phòng được ngay hôm nay.
- Backend áp dụng cùng quy tắc với Web (như FR-BKG-08). Backend vẫn quyết định cuối; `DATE_OUT_OF_RANGE` trả `availableFrom` = hôm nay, `availableTo` = hôm nay + 3 tháng cho khách sạn, không đổi contract.
- Tình trạng phòng tách khỏi kiểm tra ngày: khi không có dữ liệu lịch (`attributes.availability`) cho ngày đó thì không chặn. Khi dữ liệu cho biết hạng phòng kín thì hệ thống báo "hạng phòng đã hết chỗ" (không phải lỗi ngày không hợp lệ).

## Thay đổi source sau khi chốt

- `docs/prd/requirements.md`, `docs/prd/data-model.md`: cập nhật theo nội dung đã chốt (làm trước).
- `docs/spec/hop-dong-tich-hop-backend.md` (dòng `DATE_OUT_OF_RANGE`), `docs/spec/hop-dong-tich-hop-frontend.md` §tripContext và bảng lỗi.
- `src/backend/app/domain/booking/pricing.py`: nhánh kiểm ngày cho `hotel_room`.
- `src/frontend/src/components/detail/ProductDetailView.tsx`: `validateDates`, `defaultStart`, `min`/`max` của `DateInput`; `src/frontend/src/context/TravelContext.tsx` (`defaultUsingDate`).
- Test: `src/frontend/tests/unit/productDetailView.test.tsx`, test backend của `pricing.py`.
