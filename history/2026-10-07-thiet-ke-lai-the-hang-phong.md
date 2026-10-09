# Thiết kế lại thẻ hạng phòng

- Ngày: 2026-10-07
- Tác giả: mihhquan / Claude
- Nhánh: feat/fix-bug
- Trạng thái: hoàn thành
- Phạm vi: frontend, docs

## Mục tiêu

Người dùng muốn danh sách "Chọn hạng phòng" ở trang chi tiết khách sạn đẹp và sang hơn, dùng nhiều icon hơn. Dùng skill ui-ux-pro-max: tra hệ thiết kế (navy sang trọng, SVG thay emoji, trạng thái chọn và focus rõ), giữ tông xanh V-OTA và font hiện có. Không lệch PRD (giao diện trang chi tiết thuộc spec).

## File thay đổi

- `src/frontend/src/components/detail/RoomCard.tsx` — thêm: thẻ hạng phòng (ảnh lớn, thông số có icon, tiện ích nổi bật có icon, giá lớn, nhãn "Giá tốt nhất", trạng thái "Chọn phòng" / "Đã chọn" / "Hết chỗ", bảng tiện ích mở rộng hai cột).
- `src/frontend/src/components/detail/amenityIcons.ts` — thêm: `amenityIcon` (bản đồ chữ tiếng Việt sang icon lucide) và `pickHighlights`.
- `src/frontend/src/components/detail/AmenityList.tsx` — sửa: mỗi mục một icon theo loại, tuỳ chọn hai cột; áp dụng cả mục "Tiện ích khách sạn".
- `src/frontend/src/components/detail/ProductDetailView.tsx` — sửa: hạng phòng khách sạn dùng `RoomCard`; tính hạng rẻ nhất; chuyến bay giữ hàng gọn cũ.
- `src/frontend/tests/unit/amenityIcons.test.ts` — thêm; `tests/unit/productDetailView.test.tsx` — sửa: thêm test thẻ phòng.
- `docs/spec/hop-dong-tich-hop-frontend.md` (§4.3) — sửa.
- `history/2026-10-07-thiet-ke-lai-the-hang-phong.md` — thêm: entry này.

## Quyết định

- Cả thẻ là một ô chọn (`role="radio"` phủ kín thẻ, nằm dưới nội dung); nút ảnh và tiện ích nằm trên nó nên không đổi lựa chọn và không có nút lồng nút. Nút "Chọn phòng" / "Đã chọn" chỉ là nhãn trạng thái.
- Tiện ích nổi bật chỉ lấy loại có icon riêng, theo thứ tự quan trọng với người đặt phòng, mỗi loại icon một lần.
- Giá dùng Inter đậm thay vì font hiển thị, vì Cal Sans làm các chữ số giãn rộng.
- Quy tắc `ăn sáng` dùng ranh giới từ để "Rèm cản sáng" không nhận nhầm là bữa sáng.

## Kiểm tra

- `node_modules/.bin/vitest run tests/unit` (từ `src/frontend`): 676 pass, 1 test của trang thanh toán (`checkoutView`, "chặn trẻ em đã đủ 12 tuổi…") vượt 5 giây khi chạy cả bộ song song (5047 ms); chạy riêng `checkoutView.test.tsx` hai lần đều 39/39 pass. Test này không dùng thẻ phòng.
- `tsc --noEmit` sạch; `eslint`: 0 lỗi, 2 cảnh báo cũ ở `ItineraryMap.tsx`.
- Trình duyệt thật (Vinpearl Empire Nha Trang, backend thật): bốn thẻ phòng, một thẻ "Đã chọn", nhãn "Giá tốt nhất", bảng tiện ích mở rộng hai cột, không cuộn ngang ở 1280px và 390px. Chụp màn hình trước khi sửa hai lỗi nhỏ (chữ số giá giãn rộng, icon "Rèm cản sáng"); chưa chụp lại sau khi sửa.

## Còn lại / rủi ro

- Ảnh phòng nguồn nặng vài MB: ảnh đầu thẻ tải chậm trên mạng yếu (đã nêu ở `2026-10-07-anh-tien-ich-chi-tiet-bo-tuong-tu.md`).
- Bản đồ icon dựa trên chữ của nguồn; tiện ích lạ hiện dấu tích.
- Test thanh toán nêu trên chạm giới hạn thời gian khi tải nặng; chưa tăng mức chờ.
