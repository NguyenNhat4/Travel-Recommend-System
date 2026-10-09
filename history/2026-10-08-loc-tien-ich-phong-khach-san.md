# Bộ lọc tiện ích phòng ở trang chi tiết khách sạn

- Ngày: 2026-10-08
- Tác giả: mihhquan / Claude
- Nhánh: feat/fix-bug
- Trạng thái: hoàn thành
- Phạm vi: frontend, docs

## Mục tiêu

Thêm bộ lọc tiện ích cho phần chọn hạng phòng ở trang chi tiết khách sạn (nối tiếp `2026-10-08-bo-hop-dat-khach-san-nut-dat-tren-the-phong.md`). Mã yêu cầu: FR-CAT-02. Không lệch PRD: chỉ lọc phía trình duyệt trên dữ liệu `attributes.amenities` đã có, không đổi contract hay backend.

## File thay đổi

- `src/frontend/src/components/detail/RoomAmenityFilter.tsx` — thêm: `amenityOptions`, `matchesAmenities`, chip lọc nhiều lựa chọn.
- `src/frontend/src/components/detail/ProductDetailView.tsx` — sửa: gắn bộ lọc trên danh sách phòng, trạng thái rỗng, đặt lại bộ lọc khi đổi khách sạn.
- `src/frontend/tests/unit/productDetailView.test.tsx` — sửa: thêm hai test (lọc đủ mọi tiện ích, không hiện khi không có tiện ích).
- `docs/spec/hop-dong-tich-hop-frontend.md` (§4.3), `docs/spec/product.md` (§4.3.2) — sửa.
- `history/2026-10-08-loc-tien-ich-phong-khach-san.md` — thêm: entry này.

## Quyết định

- Lọc theo tiện ích của **hạng phòng** (không phải tiện ích chung của khách sạn, vốn giống nhau cho mọi phòng nên không lọc được gì). Nếu ý là lọc khách sạn theo tiện ích thì đó là bộ lọc ở trang danh mục, chưa làm.
- Logic AND: phòng phải có đủ mọi tiện ích đã chọn. Chip kèm số phòng có tiện ích đó; mặc định hiện 10 chip, "Xem tất cả" mở hết, chip đã chọn luôn hiện.
- Bỏ mục chỉ là diện tích ("20 m²") lẫn trong `amenities` của nguồn vì đã có ở thông số phòng.
- Ẩn bộ lọc khi chỉ có một hạng phòng hoặc không phòng nào có tiện ích.

## Kiểm tra

- `node_modules/.bin/vitest run tests/unit` (từ `src/frontend`): 64 file, 680 test pass. `tsc --noEmit` sạch. `eslint`: không báo lỗi ở file đã sửa.
- Trình duyệt thật: khách sạn 3 hạng phòng hiện bộ lọc chip kèm số phòng; chưa kiểm trên điện thoại.

## Còn lại / rủi ro

- Bộ lọc không lưu vào URL, tải lại trang thì mất.
