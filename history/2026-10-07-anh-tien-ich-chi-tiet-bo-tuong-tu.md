# Trang chi tiết: bộ ảnh, ảnh và tiện ích từng hạng phòng; bỏ mục Tương tự

- Ngày: 2026-10-07
- Tác giả: mihhquan / Claude
- Nhánh: feat/fix-bug
- Trạng thái: hoàn thành
- Phạm vi: frontend, docs

## Mục tiêu

Dữ liệu có nhiều ảnh cho mỗi khách sạn (`attributes.images`, ví dụ 16 ảnh) và mỗi hạng phòng có ảnh riêng (`images`, `imageUrl`) cùng danh sách tiện ích riêng (~31 mục) mà trang chi tiết chưa dùng: chỉ hiện một `imageUrl`. Người dùng cũng muốn bỏ mục "Tương tự" vì lý do đề xuất không đúng. Không lệch PRD: `docs/prd/user-flow.md` §2 đã ghi "Image Gallery" ở trang chi tiết và không có mục "Tương tự"; mục này chỉ có ở spec (`docs/spec/`).

## File thay đổi

- `src/frontend/src/components/detail/ProductGallery.tsx` — thêm: `imagesOf`, `ProductGallery` (một ảnh lớn + tối đa bốn ảnh nhỏ, nút "N ảnh", điện thoại chỉ ảnh lớn), `ImageLightbox` (← → đổi ảnh, Esc đóng, giữ tiêu điểm, dải ảnh nhỏ).
- `src/frontend/src/components/detail/AmenityList.tsx` — thêm: `amenityList` (bỏ trùng, bỏ rỗng/không phải chuỗi) và `AmenityList` (12 mục đầu, "Xem tất cả (N)" / "Thu gọn").
- `src/frontend/src/components/detail/ProductDetailView.tsx` — sửa: dùng `ProductGallery`; mục "Tiện ích khách sạn"; mỗi hạng phòng có ảnh nhỏ, "Xem ảnh phòng (N)" và "Tiện ích phòng (N)"; bỏ gọi `getSimilarProducts` và toàn bộ mục "Tương tự".
- `src/frontend/tests/unit/productDetailView.test.tsx` — sửa: bỏ test Tương tự, thêm bốn test (không còn Tương tự, bộ ảnh + lightbox, tiện ích khách sạn, ảnh/tiện ích hạng phòng).
- `docs/spec/hop-dong-tich-hop-frontend.md` (§4.3, mock), `docs/spec/product.md` (§4.3) — sửa.
- `history/2026-10-07-anh-tien-ich-chi-tiet-bo-tuong-tu.md` — thêm: entry này.

## Quyết định

- Không đổi API: `GET /products/{id}` và `GET /products?parentProductId=` đã trả `attributes.images` và `attributes.amenities`.
- Nút xem ảnh và tiện ích của hạng phòng nằm ngoài nút chọn phòng, nên bấm không đổi lựa chọn và không lồng nút trong nút.
- Tiện ích hiển thị đúng chuỗi của nguồn (bỏ trùng), không map key sang icon: nguồn là chuỗi tự do.
- Endpoint `/products/{id}/similar`, `getSimilarProducts` và mock giữ lại: Backend vẫn dùng cho Agent.

## Kiểm tra

- `node_modules/.bin/vitest run tests/unit` (từ `src/frontend`): 63 file, 672 test pass. `tsc --noEmit` sạch. `eslint`: 0 lỗi, 2 cảnh báo cũ ở `ItineraryMap.tsx`. Playwright (dev server :3000) `routes.spec.ts`, `widget-detail.spec.ts`: 17 pass.
- Trình duyệt thật với backend thật, Vinpearl Empire Nha Trang: bộ ảnh 1 + 4 và nút "16 ảnh"; lightbox mở ở "1 / 16"; 4 hạng phòng đều có ảnh nhỏ, "Xem ảnh phòng (3–4)" và "Tiện ích phòng (31–33)"; không có mục Tương tự và không có request `/similar`; không cuộn ngang ở 1280px và 390px.

## Còn lại / rủi ro

- Ảnh nguồn rất nặng: vd 3,4–4,3 MB mỗi ảnh khách sạn, kích thước gốc tới 8659×5772 px, mất khoảng 6 giây mỗi ảnh khi tải riêng; máy chủ ảnh không thu nhỏ theo tham số. Trang tải 16 ảnh khách sạn lẫn ảnh phòng sẽ chậm trên mạng yếu (thẻ kết quả tìm kiếm cũng đang tải ảnh gốc). Đã cho ảnh lớn đầu tiên tải trước (`fetchPriority`), ảnh nhỏ tải sau. Giải pháp đúng là một lớp thu nhỏ ảnh (next/image hoặc proxy ở BFF có danh sách tên miền cho phép): cần quyết định riêng.
- Tiện ích của nguồn có nhiều mục gần trùng nghĩa ("Bể bơi", "Bể bơi [ngoài trời]", "Hồ bơi ngoài trời"); chỉ bỏ trùng đúng chữ.
- Mô tả ảnh (`alt`) của ảnh nhỏ để trống; chưa có chú thích từng ảnh trong dữ liệu.
